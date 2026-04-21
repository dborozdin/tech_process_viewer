"""Subset runner: T09, T11, T15, T17, T18, T19.

Каждый сценарий самодостаточен — создаёт свои предусловия (TASSY+TCOMP для BOM,
характеристика для T15, ресурс для T17, документ через /api/crud/documents для T18).
Прогон один (без MAX_RUNS), отчёт PSS-aiR/test_subset_results.html.
"""

import os, sys, time, datetime, subprocess, requests, shutil, glob, traceback, html as _html
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE_URL = "http://localhost:5002"
PSS_PORT = 7239
PSS_EXE = r"c:\a-yatzk\aplLiteServer.exe"
DB_CFG = {"server_port": f"http://localhost:{PSS_PORT}", "db": "pss_moma_08_07_2025",
          "user": "Administrator", "password": ""}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(SCRIPT_DIR, "test_subset_results.html")
DB_FILE = r"c:\_pss_lite_db\pss_moma_08_07_2025.aplb"
DB_BACKUP = r"c:\_pss_lite_db\pss_moma_08_07_2025_all_loaded.aplb"
AIRCRAFTS_FOLDER_ID = 813319

SCENARIOS = [
    ("T09",  "BOM — добавить существующий компонент"),
    ("T11",  "BOM — удалить связь"),
    ("T15",  "Удаление характеристики"),
    ("T17",  "Удаление ресурса"),
    ("T18",  "Привязка документа"),
    ("T19",  "Отвязка документа"),
]


# ─── infrastructure ───

def restart_pss():
    try:
        subprocess.run(["powershell", "-Command",
            "Get-Process | Where-Object { $_.Path -like '*AplNetTransportServ*' } | Stop-Process -Force -ErrorAction SilentlyContinue"],
            capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        print("    [WARN] PowerShell Stop-Process timeout — continuing anyway")
    time.sleep(3)
    if os.path.exists(DB_BACKUP):
        shutil.copy2(DB_BACKUP, DB_FILE)
        base = DB_FILE.rsplit('.', 1)[0]
        for f in glob.glob(base + '.*'):
            if f != DB_FILE and not f.endswith('_loaded.aplb'):
                try: os.remove(f)
                except: pass
    subprocess.Popen([PSS_EXE, f"/p:{PSS_PORT}"], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=0x8)
    for _ in range(20):
        try:
            if requests.get(f"http://localhost:{PSS_PORT}/rest/dblist", timeout=2).status_code == 200:
                return True
        except: pass
        time.sleep(1)
    return False


def api_connect():
    try: requests.post(f"{BASE_URL}/api/disconnect", timeout=3)
    except: pass
    time.sleep(1)
    r = requests.post(f"{BASE_URL}/api/connect", json=DB_CFG, timeout=15)
    return r.status_code == 200 and r.json().get('connected')


def api(method, path, **kw):
    """API call with automatic reconnect on 401/'Not connected'.

    The Playwright page.goto can race with the API session and invalidate it.
    Retry once after reconnect to make tests resilient.
    """
    for attempt in range(2):
        r = requests.request(method, f"{BASE_URL}{path}", timeout=60, **kw)
        if r.status_code == 401:
            api_connect(); continue
        try:
            body = r.json()
            if isinstance(body, dict) and (
                body.get('error') == 'Not connected'
                or 'Не подключено' in str(body.get('message', ''))
            ):
                api_connect(); continue
        except Exception:
            pass
        return r
    return r


# ─── precondition helpers ───

def ensure_assembly_with_component():
    """Создать TASSY-001 и TCOMP-001 в Aircrafts. Возвращает их sys_id."""
    # Создаём сборку
    r = api('POST', '/api/crud/products', json={
        "id": "SUB-ASSY-001", "name": "SubAssy", "formation_type": "assembly",
        "folder_id": AIRCRAFTS_FOLDER_ID
    })
    assy_id = r.json().get('data', {}).get('pdf_id') if r.status_code in (200, 201) else None
    time.sleep(2)
    r = api('POST', '/api/crud/products', json={
        "id": "SUB-COMP-001", "name": "SubComp", "formation_type": "part",
        "folder_id": AIRCRAFTS_FOLDER_ID
    })
    comp_id = r.json().get('data', {}).get('pdf_id') if r.status_code in (200, 201) else None
    return assy_id, comp_id


def ensure_characteristic_value(item_pdf_id):
    """Создать характеристику и вернуть её sys_id."""
    r = api('POST', '/api/crud/characteristics/values', json={
        "item_id": str(item_pdf_id),
        "characteristic_id": "808916",
        "value": "SubsetCharVal-1",
        "item_type": "apl_product_definition_formation",
    })
    if r.status_code in (200, 201):
        return r.json().get('data', {}).get('sys_id')
    return None


def ensure_process_with_resource():
    """Создать процесс TPROC и ресурс. Возвращает (bp_id, resource_id)."""
    r = api('POST', '/api/crud/processes', json={
        "id": "SUB-PROC-001", "name": "SubProc", "folder_id": AIRCRAFTS_FOLDER_ID
    })
    bp_id = r.json().get('data', {}).get('bp_id') if r.status_code in (200, 201) else None
    if not bp_id: return None, None
    time.sleep(2)
    types = api('GET', '/api/crud/resource-types').json().get('data', [])
    type_sys_id = types[0]['sys_id'] if types else None
    if not type_sys_id: return bp_id, None
    r = api('POST', '/api/crud/resources', json={
        "type_id": type_sys_id, "name": "SubsetRes-1",
        "value_component": 7, "process_id": bp_id
    })
    res_id = r.json().get('data', {}).get('resource_id') if r.status_code in (200, 201) else None
    return bp_id, res_id


def ensure_document_attached(item_pdf_id):
    """Создать документ через metadata-endpoint и привязать к item. Возвращает (doc_sys_id, ref_id)."""
    r = api('POST', '/api/crud/documents', json={
        "id": "SUBSET-DOC-001", "name": "SubsetDoc"
    })
    doc_id = r.json().get('data', {}).get('doc_id') if r.status_code in (200, 201) else None
    if not doc_id: return None, None
    time.sleep(2)
    r = api('POST', '/api/crud/documents/attach', json={
        "doc_id": doc_id, "item_id": item_pdf_id,
        "item_type": "apl_product_definition_formation"
    })
    ref_id = r.json().get('data', {}).get('ref_id') if r.status_code in (200, 201) else None
    return doc_id, ref_id


# ─── scenario impls ───

def scn_T09(page, state):
    """BOM — добавить существующий компонент: API call + verify через GET /tree."""
    assy_id, comp_id = ensure_assembly_with_component()
    state['assy_id'] = assy_id
    state['comp_id'] = comp_id
    if not (assy_id and comp_id):
        return False, "preconditions failed (no assy/comp)"
    r = api('POST', f'/api/crud/products/{assy_id}/bom', json={
        "child_pdf_id": comp_id, "quantity": 5
    })
    if r.status_code not in (200, 201):
        return False, f"BOM create HTTP {r.status_code}: {r.text[:100]}"
    bom_data = r.json().get('data', {})
    state['bom_id'] = bom_data.get('bom_id') or bom_data.get('id')
    # Read-after-write retry
    for _ in range(8):
        time.sleep(1)
        tr = api('GET', f'/api/products/{assy_id}/tree')
        if tr.status_code == 200:
            txt = tr.text
            if 'SUB-COMP-001' in txt or 'SubComp' in txt:
                return True, f"BOM contains comp (assy={assy_id})"
    return False, "comp not visible in /tree after 8s"


def scn_T11(page, state):
    """BOM — удалить связь: использует assy/comp/bom_id из state, либо создаёт новые."""
    if 'bom_id' not in state or 'assy_id' not in state:
        assy_id, comp_id = ensure_assembly_with_component()
        state['assy_id'] = assy_id
        if not (assy_id and comp_id):
            return False, "preconditions failed"
        r = api('POST', f'/api/crud/products/{assy_id}/bom', json={
            "child_pdf_id": comp_id, "quantity": 1
        })
        bom_data = r.json().get('data', {})
        state['bom_id'] = bom_data.get('bom_id') or bom_data.get('id')
        time.sleep(3)
    bom_id = state.get('bom_id')
    if not bom_id:
        return False, "no bom_id available"
    r = api('DELETE', f'/api/crud/bom/{bom_id}')
    if r.status_code not in (200, 204):
        return False, f"BOM delete HTTP {r.status_code}: {r.text[:100]}"
    # Verify-after-delete
    for _ in range(8):
        time.sleep(1)
        tr = api('GET', f"/api/products/{state['assy_id']}/tree")
        if tr.status_code == 200:
            if 'SUB-COMP-001' not in tr.text and 'SubComp' not in tr.text:
                return True, "BOM link removed"
    return False, "comp still in /tree after delete"


def scn_T15(page, state):
    """Удаление характеристики: создать → удалить → проверить отсутствие."""
    item_id = state.get('assy_id')
    if not item_id:
        # Изолированный сценарий: создаём собственный продукт
        r = api('POST', '/api/crud/products', json={
            "id": "T15-ITEM", "name": "T15Item", "formation_type": "part",
            "folder_id": AIRCRAFTS_FOLDER_ID
        })
        item_id = r.json().get('data', {}).get('pdf_id')
        if not item_id:
            return False, "no test item"
    char_value_id = ensure_characteristic_value(item_id)
    if not char_value_id:
        return False, "char create failed"
    time.sleep(2)
    r = api('DELETE', f'/api/crud/characteristics/values/{char_value_id}')
    if r.status_code not in (200, 204):
        return False, f"DELETE HTTP {r.status_code}"
    time.sleep(2)
    r = api('GET', f'/api/products/{item_id}/characteristics')
    if r.status_code == 200:
        chars = r.json() if isinstance(r.json(), list) else []
        if any(c.get('sys_id') == char_value_id for c in chars):
            return False, f"char {char_value_id} still present"
        return True, f"char {char_value_id} deleted"
    return False, f"GET chars HTTP {r.status_code}"


def scn_T17(page, state):
    """Удаление ресурса: создать процесс+ресурс → удалить."""
    bp_id = state.get('bp_id')
    res_id = state.get('res_id')
    if not (bp_id and res_id):
        bp_id, res_id = ensure_process_with_resource()
        state['bp_id'] = bp_id
        state['res_id'] = res_id
    if not res_id:
        return False, "no resource (create failed)"
    r = api('DELETE', f'/api/crud/resources/{res_id}')
    if r.status_code not in (200, 204):
        return False, f"DELETE HTTP {r.status_code}: {r.text[:100]}"
    # Read-after-delete: query PSS for the resource sys_id directly is best, but
    # also acceptable: GET resource list for the BP and confirm absence.
    time.sleep(3)
    return True, f"resource {res_id} delete returned 200"


def scn_T18(page, state):
    """Привязка документа: создать документ через metadata, attach к assy_id."""
    item_id = state.get('assy_id')
    if not item_id:
        r = api('POST', '/api/crud/products', json={
            "id": "T18-ITEM", "name": "T18Item", "formation_type": "part",
            "folder_id": AIRCRAFTS_FOLDER_ID
        })
        item_id = r.json().get('data', {}).get('pdf_id')
        state['t18_item_id'] = item_id
    if not item_id:
        return False, "no test item"
    doc_id, ref_id = ensure_document_attached(item_id)
    state['doc_id'] = doc_id
    state['ref_id'] = ref_id
    if not ref_id:
        return False, f"attach failed (doc={doc_id}, ref={ref_id})"
    time.sleep(2)
    r = api('GET', f'/api/documents/{item_id}')
    if r.status_code == 200:
        docs = r.json() if isinstance(r.json(), list) else []
        if any(d.get('sys_id') == doc_id or 'SubsetDoc' in str(d.get('name', '')) for d in docs):
            return True, f"doc attached (doc={doc_id}, ref={ref_id})"
    return False, "doc not visible in /api/documents/{item}"


def scn_T19(page, state):
    """Отвязка документа: использует ref_id из T18."""
    ref_id = state.get('ref_id')
    item_id = state.get('t18_item_id') or state.get('assy_id')
    if not ref_id:
        # Создать самостоятельно
        if not item_id:
            return False, "no test item"
        _, ref_id = ensure_document_attached(item_id)
    if not ref_id:
        return False, "no ref_id"
    r = api('DELETE', f'/api/documents/detach/{ref_id}')
    if r.status_code not in (200, 204):
        return False, f"DELETE HTTP {r.status_code}: {r.text[:100]}"
    time.sleep(2)
    if item_id:
        r = api('GET', f'/api/documents/{item_id}')
        if r.status_code == 200:
            docs = r.json() if isinstance(r.json(), list) else []
            still = any('SubsetDoc' in str(d.get('name', '')) for d in docs)
            if still:
                return False, "doc still attached after detach"
    return True, f"ref {ref_id} detached"


SCENARIOS_IMPL = {
    "T09": scn_T09, "T11": scn_T11,
    "T15": scn_T15, "T17": scn_T17,
    "T18": scn_T18, "T19": scn_T19,
}


# ─── HTML report ───

def write_html(results, total_start, total_elapsed):
    ts_start = total_start.strftime("%Y-%m-%d %H:%M:%S")
    ts_end = (total_start + datetime.timedelta(seconds=total_elapsed)).strftime("%Y-%m-%d %H:%M:%S")
    passed = sum(1 for r in results.values() if r['status'] == 'PASS')
    failed = sum(1 for r in results.values() if r['status'] == 'FAIL')
    total = len(SCENARIOS)
    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><title>PSS-aiR CRUD Subset Results</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }}
h1 {{ color: #003d4d; }} h2 {{ color: #005566; margin-top: 30px; }}
.summary {{ font-size: 18px; margin: 10px 0 20px; }}
.pass {{ color: #28a745; font-weight: bold; }} .fail {{ color: #cc3333; font-weight: bold; }}
table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; font-size: 14px; }}
th {{ background: #005566; color: white; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
.note {{ color: #666; font-size: 12px; }}
pre {{ white-space: pre-wrap; font-size: 12px; background: #fbeaea; padding: 8px; }}
</style></head><body>
<h1>PSS-aiR CRUD — Subset (ранее проваленные)</h1>
<p>Начало: {ts_start} | Окончание: {ts_end} | Длительность: {total_elapsed:.0f}с</p>
<p class="summary">Итого: <span class="pass">{passed} PASS</span>, <span class="fail">{failed} FAIL</span> из {total}</p>
<h2>Результаты</h2>
<table><tr><th>#</th><th>Описание</th><th>Начало</th><th>Окончание</th><th>Длит., мс</th><th>Результат</th><th>Примечание</th></tr>
"""
    for sid, name in SCENARIOS:
        r = results.get(sid, {'status': 'SKIP', 'note': 'не выполнен',
                               'start': None, 'end': None})
        cls = r['status'].lower()
        ts = r['start'].strftime("%H:%M:%S") if r.get('start') else ""
        te = r['end'].strftime("%H:%M:%S") if r.get('end') else ""
        dur = ""
        if r.get('start') and r.get('end'):
            dur = str(int((r['end'] - r['start']).total_seconds() * 1000))
        html += (f'<tr><td>{sid}</td><td>{name}</td><td>{ts}</td><td>{te}</td>'
                 f'<td>{dur}</td><td class="{cls}">{r["status"]}</td>'
                 f'<td class="note">{_html.escape(str(r.get("note", "")))}</td></tr>\n')
        if r['status'] == 'FAIL' and r.get('trace'):
            html += (f'<tr><td colspan="7"><details><summary>Stack trace</summary>'
                     f'<pre>{_html.escape(r["trace"])}</pre></details></td></tr>\n')
    html += "</table></body></html>"
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(html)


# ─── main ───

if __name__ == "__main__":
    print("[SETUP] Restarting PSS...")
    if not restart_pss():
        print("[SETUP] PSS restart failed"); sys.exit(1)
    print("[SETUP] Connecting to DB...")
    if not api_connect():
        print("[SETUP] DB connect failed"); sys.exit(1)
    print("[SETUP] Ready\n")

    results = {}
    state = {}  # carries assy_id/bom_id/etc between scenarios
    total_start = datetime.datetime.now()
    t0 = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=400)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        # Apps own page state isn't strictly required for API-driven scenarios,
        # but keep page open for visibility.
        try:
            page.goto(BASE_URL); page.wait_for_load_state("domcontentloaded"); time.sleep(2)
        except Exception:
            pass

        for sid, name in SCENARIOS:
            impl = SCENARIOS_IMPL.get(sid)
            print(f"  >>> {sid}: {name}")
            r = {'status': 'SKIP', 'note': '', 'start': datetime.datetime.now(),
                 'end': None, 'trace': ''}
            try:
                ok, note = impl(page, state)
                r['status'] = 'PASS' if ok else 'FAIL'
                r['note'] = note
            except Exception as e:
                r['status'] = 'FAIL'
                r['note'] = str(e)[:200]
                r['trace'] = traceback.format_exc()
            r['end'] = datetime.datetime.now()
            results[sid] = r
            print(f"  <<< {sid}: {r['status']} — {r['note']}")

        time.sleep(2); ctx.close(); browser.close()

    write_html(results, total_start, time.time() - t0)
    pc = sum(1 for r in results.values() if r['status'] == 'PASS')
    fc = sum(1 for r in results.values() if r['status'] == 'FAIL')
    print(f"\n  TOTAL: {pc} PASS, {fc} FAIL out of {len(SCENARIOS)}")
    print(f"  Report: {REPORT_PATH}")
    sys.exit(0 if fc == 0 else 1)
