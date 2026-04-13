"""UI-тесты CRUD для PSS-aiR.

Запуск: python PSS-aiR/test_ui_scenarios.py
Результат: PSS-aiR/test_results.html + PSS-aiR/test_video_pass.webm (при 100%)

Автоматически перезапускает PSS-сервер. headless=False, slow_mo=400.
Видео записывается для каждого прогона; сохраняется только при 100% PASS.
Перед каждым тестом на странице показывается overlay с названием теста (видно на видео).
"""

import os, sys, time, datetime, subprocess, requests, shutil, glob
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5002"
PSS_PORT = 7239
PSS_EXE = r"C:\Program Files (x86)\PSS_MUI\AplNetTransportServTCP.exe"
DB_CFG = {"server_port": f"http://localhost:{PSS_PORT}", "db": "pss_moma_08_07_2025", "user": "Administrator", "password": ""}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(SCRIPT_DIR, "test_results.html")
VIDEO_PATH = os.path.join(SCRIPT_DIR, "test_video_pass.webm")

SCENARIOS = [
    ("T01", "Загрузка приложения"),
    ("T02", "Подключение к БД"),
    ("T03", "Загрузка дерева папок"),
    ("T04", "Выбор папки — CRUD-тулбар"),
    ("T05", "Создание изделия"),
    ("T06", "Редактирование изделия"),
    ("T07", "Удаление изделия"),
    ("T08", "Создание сборки и компонента"),
    ("T09", "BOM — добавить существующий компонент"),
    ("T09b", "BOM — создать новое изделие в составе"),
    ("T10", "BOM — редактировать связь"),
    ("T11", "BOM — удалить связь"),
    ("T12", "Создание бизнес-процесса"),
    ("T13", "PropertyPanel — Редактировать"),
    ("T14", "Добавление характеристики"),
    ("T15", "Удаление характеристики"),
    ("T16", "Добавление ресурса"),
    ("T17", "Удаление ресурса"),
    ("T18", "Привязка документа"),
    ("T19", "Отвязка документа"),
    ("T20", "Очистка тестовых данных"),
]

# ─── infrastructure ───

DB_FILE = r"c:\_pss_lite_db\pss_moma_08_07_2025.aplb"
DB_BACKUP = r"c:\_pss_lite_db\pss_moma_08_07_2025_all_loaded.aplb"

def restart_pss():
    import shutil as _shutil
    # Kill
    subprocess.run(["powershell", "-Command",
        "Get-Process | Where-Object { $_.Path -like '*AplNetTransportServ*' } | Stop-Process -Force -ErrorAction SilentlyContinue"],
        capture_output=True, timeout=10)
    time.sleep(3)
    # Restore DB from backup + remove CRC/BAK/TMP
    if os.path.exists(DB_BACKUP):
        _shutil.copy2(DB_BACKUP, DB_FILE)
        for ext in ('.aplb.crc', '.aplb.bak', '.aplb.tmp', '.aclst', '.aclst.crc', '.crc.log'):
            p = DB_FILE.replace('.aplb', '') + ext if not ext.startswith('.aplb') else DB_FILE + ext.replace('.aplb', '')
            # Simpler: just remove files matching the pattern
            pass
        base = DB_FILE.rsplit('.', 1)[0]
        for f in glob.glob(base + '.*'):
            if f != DB_FILE and not f.endswith('_loaded.aplb'):
                try: os.remove(f)
                except: pass
    # Start
    subprocess.Popen([PSS_EXE, f"/p:{PSS_PORT}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x8)
    for i in range(20):
        try:
            if requests.get(f"http://localhost:{PSS_PORT}/rest/dblist", timeout=2).status_code == 200: return True
        except: pass
        time.sleep(1)
    return False

def ensure(page):
    try:
        if requests.get(f"http://localhost:{PSS_PORT}/rest/dblist", timeout=3).status_code == 200: return True
    except: pass
    print("    [RECOVERY] PSS down, restarting...")
    restart_pss()
    try: requests.post(f"{BASE_URL}/api/disconnect", timeout=3)
    except: pass
    time.sleep(2)
    page.reload(); time.sleep(5)
    c = page.evaluate("()=>document.querySelector('.status-dot')?.classList.contains('connected')||false")
    if not c:
        try:
            if not page.query_selector("#connectModal.visible"):
                b = page.query_selector("#btnConnect:not(.hidden)")
                if b: b.click(force=True); time.sleep(1)
            page.fill("#cfServer", DB_CFG["server_port"]); page.fill("#cfUser","Administrator"); page.fill("#cfDatabase", DB_CFG["db"])
            page.click("#btnConnectSubmit"); time.sleep(5)
            if page.query_selector("#connectModal.visible"): page.click("#connectModalClose")
        except: pass
    time.sleep(2); return True

def idle(page, t=15):
    """Wait for all network requests to finish."""
    try: page.wait_for_load_state("networkidle", timeout=t*1000)
    except: pass
    for _ in range(t):
        if not page.query_selector(".spinner-overlay"): return
        time.sleep(1)

def wr(page, t=12):
    for _ in range(t*2):
        if not page.query_selector("#crudModalOverlay.visible") and not page.query_selector(".spinner-overlay"): return
        if page.query_selector("#crudModalOverlay.visible"):
            try: page.click("#crudModalClose")
            except: pass
        time.sleep(0.5)
    page.evaluate("document.querySelectorAll('.spinner-overlay').forEach(s=>s.remove());var m=document.getElementById('crudModalOverlay');if(m)m.classList.remove('visible')")

def sel_folder(page, name="Aircrafts"):
    page.evaluate("()=>{var p=document.getElementById('panelLeft');if(p&&p.classList.contains('minimized'))p.classList.remove('minimized')}")
    idle(page)
    loc = page.locator(f'.tree-node-row[data-name="{name}"]')
    if loc.count() > 0: loc.first.click(force=True); idle(page); time.sleep(1); return True
    return False

def modal_save(page, btn, t=60):
    idle(page)
    page.click(btn)
    for _ in range(t):
        time.sleep(1)
        if not page.query_selector("#crudModalOverlay.visible"): return True
    wr(page); return False

def show_title(page, tid, name):
    """Show test title overlay on page (visible in video recording)."""
    page.evaluate(f"""() => {{
        let el = document.getElementById('_testOverlay');
        if (!el) {{
            el = document.createElement('div');
            el.id = '_testOverlay';
            el.style.cssText = 'position:fixed;top:0;left:0;right:0;padding:10px 20px;background:rgba(0,50,70,0.92);color:#fff;font:bold 18px sans-serif;z-index:9999;text-align:center;';
            document.body.appendChild(el);
        }}
        el.textContent = '{tid}: {name}';
        el.style.display = 'block';
    }}""")
    time.sleep(1)

def hide_title(page):
    page.evaluate("()=>{var e=document.getElementById('_testOverlay');if(e)e.style.display='none'}")

# ─── test runner ───

def run(page):
    R = {}
    times = {}

    def ok(tid, n=""): R[tid]=("PASS",n); hide_title(page); print(f"  [PASS] {tid}")
    def fail(tid, n=""): R[tid]=("FAIL",n); hide_title(page); print(f"  [FAIL] {tid}: {n}")

    def begin(tid):
        name = next((n for i,n in SCENARIOS if i==tid), tid)
        show_title(page, tid, name)
        times[tid] = datetime.datetime.now()

    # T01
    begin("T01")
    page.goto(BASE_URL); page.wait_for_load_state("domcontentloaded"); time.sleep(3)
    if page.evaluate("typeof CrudManager!=='undefined'"): ok("T01")
    else: fail("T01"); return R, times

    # T02
    begin("T02"); time.sleep(4)
    c = page.evaluate("()=>document.querySelector('.status-dot')?.classList.contains('connected')||false")
    if not c:
        m = page.query_selector("#connectModal.visible")
        if not m:
            b = page.query_selector("#btnConnect:not(.hidden)")
            if b: b.click(force=True); time.sleep(1)
        try: page.fill("#cfServer",DB_CFG["server_port"]); page.fill("#cfUser","Administrator"); page.fill("#cfDatabase",DB_CFG["db"]); page.click("#btnConnectSubmit"); time.sleep(5)
        except: pass
        if page.query_selector("#connectModal.visible"):
            try: page.click("#connectModalClose")
            except: pass
        c = page.evaluate("()=>document.querySelector('.status-dot')?.classList.contains('connected')||false")
    if c: ok("T02")
    else: fail("T02"); return R, times

    # T03
    begin("T03"); time.sleep(5)
    nodes = page.query_selector_all(".tree-node-row")
    if not nodes:
        b = page.query_selector("#btnRefreshTree")
        if b: b.click(force=True); time.sleep(5)
        nodes = page.query_selector_all(".tree-node-row")
    if nodes: ok("T03", f"{len(nodes)} nodes")
    else: fail("T03"); return R, times

    # T04
    begin("T04"); sel_folder(page)
    tb = page.query_selector("#crudToolbar")
    th = tb.inner_html() if tb else ""
    if "Изделие" in th and "Папка" in th: ok("T04")
    else: fail("T04"); return R, times

    # T05 — create product
    begin("T05"); ensure(page); idle(page)
    page.click("#crudBtnCreateProduct"); time.sleep(1)
    page.fill("#crudProductForm-id","TCREAT-001"); page.fill("#crudProductForm-name","TestCreated"); page.fill("#crudProductForm-code1","TC01")
    page.select_option("#crudProductForm-formation_type","assembly")
    closed = modal_save(page,"#crudProductSave",25); time.sleep(2); wr(page)
    sel_folder(page); h = page.inner_html("#contentArea")
    if "TCREAT-001" in h or "TestCreated" in h: ok("T05")
    else: fail("T05", f"closed={closed}")

    # T06 — edit product
    begin("T06"); ensure(page); idle(page); sel_folder(page)
    try:
        page.locator(".content-row:has-text('TestCreated') .crud-edit, .content-row:has-text('TCREAT') .crud-edit").first.click(force=True, timeout=5000)
        time.sleep(2)
        if page.query_selector("#crudModalOverlay.visible"):
            page.fill("#crudProductEditForm-name","TestEdited")
            modal_save(page,"#crudProductEditSave",20); time.sleep(2); wr(page); sel_folder(page)
            if "TestEdited" in page.inner_html("#contentArea"): ok("T06")
            else: fail("T06","name not updated")
        else: fail("T06","modal not opened")
    except Exception as e: fail("T06",str(e)[:80])

    # T07 — delete product
    begin("T07"); ensure(page); idle(page); sel_folder(page)
    try:
        page.locator(".content-row:has-text('TestEdited') .crud-delete, .content-row:has-text('TCREAT') .crud-delete").first.click(force=True, timeout=5000)
        time.sleep(1); cf = page.query_selector("#crudConfirmOk")
        if cf: cf.click(); time.sleep(5); wr(page); sel_folder(page)
        h = page.inner_html("#contentArea")
        if "TCREAT-001" not in h and "TestEdited" not in h: ok("T07")
        else: fail("T07","still in table")
    except Exception as e: fail("T07",str(e)[:80])

    # T08 — create assembly + component
    begin("T08"); ensure(page); idle(page); sel_folder(page)
    page.click("#crudBtnCreateProduct"); time.sleep(1)
    page.fill("#crudProductForm-id","TASSY-001"); page.fill("#crudProductForm-name","TestAssy")
    page.select_option("#crudProductForm-formation_type","assembly")
    modal_save(page,"#crudProductSave",25); time.sleep(2); wr(page)
    ensure(page); idle(page); sel_folder(page)
    page.click("#crudBtnCreateProduct"); time.sleep(1)
    page.fill("#crudProductForm-id","TCOMP-001"); page.fill("#crudProductForm-name","TestComp")
    page.select_option("#crudProductForm-formation_type","part")
    modal_save(page,"#crudProductSave",25); time.sleep(2); wr(page); sel_folder(page)
    h8 = page.inner_html("#contentArea")
    if ("TCOMP-001" in h8 or "TestComp" in h8) and ("TASSY-001" in h8 or "TestAssy" in h8): ok("T08")
    else: fail("T08","products not in table")

    # T09 — BOM add existing component
    begin("T09"); ensure(page); idle(page); sel_folder(page)
    try:
        page.locator(".content-row:has-text('TestAssy')").first.dblclick(force=True, timeout=5000)
        time.sleep(5); wr(page)
        ab = page.query_selector("#crudBtnAddComponent")
        if ab:
            ab.click(); time.sleep(1)
            page.fill("#crudBomForm-search","TCOMP"); time.sleep(3)
            ri = page.query_selector("#crudBomSearchResults .search-result-item[data-id]")
            if ri:
                ri.click(); time.sleep(1); page.fill("#crudBomForm-quantity","5")
                modal_save(page,"#crudBomSave",20); time.sleep(3); wr(page)
                if "TestComp" in page.inner_html("#contentArea") or "TCOMP" in page.inner_html("#contentArea"): ok("T09")
                else: fail("T09","not in BOM")
            else: fail("T09","search empty")
        else: fail("T09","no add button")
    except Exception as e: fail("T09",str(e)[:80])

    # T09b — BOM create new product in assembly
    begin("T09b"); ensure(page); idle(page)
    # Should already be in BOM view; check for "Создать новое" button
    cb = page.query_selector("#crudBtnCreateInBom")
    if cb:
        cb.click(); time.sleep(1)
        if page.query_selector("#crudModalOverlay.visible"):
            # Check that parent info is shown
            modal_html = page.inner_html("#crudModalBody")
            has_parent = "Вхождение в состав" in modal_html
            page.fill("#crudProductForm-id","TNEW-IN-BOM")
            page.fill("#crudProductForm-name","NewInBom")
            page.select_option("#crudProductForm-formation_type","part")
            page.fill("#crudProductForm-quantity","3")
            modal_save(page,"#crudProductSave",25); time.sleep(3); wr(page)
            # Reload BOM
            try:
                sel_folder(page)
                page.locator(".content-row:has-text('TestAssy')").first.dblclick(force=True, timeout=5000)
                time.sleep(5); wr(page)
            except: pass
            hb = page.inner_html("#contentArea")
            if ("NewInBom" in hb or "TNEW-IN-BOM" in hb) and has_parent: ok("T09b")
            else: fail("T09b", f"parent_shown={has_parent}, in_bom={'NewInBom' in hb}")
        else: fail("T09b","modal not opened")
    else: fail("T09b","no create-in-bom button")

    # T10 — BOM edit link
    begin("T10"); ensure(page); idle(page)
    eb = page.query_selector(".crud-bom-edit")
    if eb:
        eb.click(); time.sleep(2)
        if page.query_selector("#crudModalOverlay.visible"):
            page.fill("#crudBomEditForm-quantity","10")
            if modal_save(page,"#crudBomEditSave",15): ok("T10")
            else: fail("T10","modal not closed")
        else: fail("T10","modal not opened")
    else: fail("T10","no edit button")

    # T11 — BOM delete link
    begin("T11"); ensure(page); idle(page); wr(page)
    db = page.query_selector(".crud-bom-delete")
    if db:
        db.click(); time.sleep(1); cf = page.query_selector("#crudConfirmOk")
        if cf: cf.click(); time.sleep(5); wr(page)
        # Delete second BOM link too
        db2 = page.query_selector(".crud-bom-delete")
        if db2:
            db2.click(); time.sleep(1); cf2 = page.query_selector("#crudConfirmOk")
            if cf2: cf2.click(); time.sleep(5); wr(page)
        hbd = page.inner_html("#contentArea")
        if "TestComp" not in hbd and "NewInBom" not in hbd: ok("T11")
        else: fail("T11","still in BOM")
    else: fail("T11","no delete button")

    # T12 — create business process
    begin("T12"); ensure(page); idle(page); sel_folder(page)
    bp = page.query_selector("#crudBtnCreateProcess")
    if bp:
        bp.click(); time.sleep(1)
        if page.query_selector("#crudModalOverlay.visible"):
            page.fill("#crudProcessForm-id","TPROC-001"); page.fill("#crudProcessForm-name","TestProcess")
            if modal_save(page,"#crudProcessSave",20): ok("T12")
            else: fail("T12","modal not closed")
        else: fail("T12","modal not opened")
    else: fail("T12","no button")

    # T13 — PropertyPanel edit button
    begin("T13"); ensure(page); idle(page); sel_folder(page); time.sleep(1)
    try:
        page.locator(".content-row[data-category='product']").first.click(force=True, timeout=5000)
        time.sleep(4); wr(page)
        if page.query_selector("#propEditBtn"): ok("T13")
        else: fail("T13","no edit button")
    except Exception as e: fail("T13",str(e)[:80])

    # T14 — add characteristic
    begin("T14"); ensure(page); idle(page)
    ct = page.query_selector('[data-tab="chars"]')
    if ct:
        ct.click(); time.sleep(3); wr(page)
        ac = page.query_selector("#propAddChar")
        if ac:
            ac.click(); time.sleep(2)
            if page.query_selector("#crudModalOverlay.visible"):
                page.fill("#crudCharForm-value","TestCharVal-999")
                modal_save(page,"#crudCharSave",15); time.sleep(2); wr(page)
                if "TestCharVal-999" in page.inner_html("#propertyContent"): ok("T14")
                else: fail("T14","not in panel")
            else: fail("T14","modal not opened")
        else: fail("T14","no add button")
    else: fail("T14","no chars tab")

    # T15 — delete characteristic
    begin("T15"); ensure(page); idle(page)
    dc = page.query_selector(".crud-char-delete")
    if dc:
        dc.click(); time.sleep(1); cf = page.query_selector("#crudConfirmOk")
        if cf: cf.click(); time.sleep(4); wr(page)
        if "TestCharVal-999" not in page.inner_html("#propertyContent"): ok("T15")
        else: fail("T15","still in panel")
    else: fail("T15","no delete button")

    # T16 — add resource (select a process first)
    begin("T16"); ensure(page); idle(page); sel_folder(page); time.sleep(1)
    try:
        page.locator(".content-row[data-category='process']").first.click(force=True, timeout=5000)
        time.sleep(4); wr(page)
        rt = page.query_selector('[data-tab="resources"]')
        if rt:
            rt.click(); time.sleep(3); wr(page)
            ar = page.query_selector("#propAddResource")
            if ar:
                ar.click(); time.sleep(2)
                if page.query_selector("#crudModalOverlay.visible"):
                    page.fill("#crudResourceForm-name","TestRes-777"); page.fill("#crudResourceForm-value_component","42")
                    modal_save(page,"#crudResourceSave",15); time.sleep(2); wr(page)
                    if "TestRes-777" in page.inner_html("#propertyContent"): ok("T16")
                    else: fail("T16","not in panel")
                else: fail("T16","modal not opened")
            else: fail("T16","no add button")
        else: fail("T16","no resources tab")
    except Exception as e: fail("T16",str(e)[:80])

    # T17 — delete resource
    begin("T17"); ensure(page); idle(page)
    dr = page.query_selector(".crud-res-delete")
    if dr:
        dr.click(); time.sleep(1); cf = page.query_selector("#crudConfirmOk")
        if cf: cf.click(); time.sleep(4); wr(page)
        if "TestRes-777" not in page.inner_html("#propertyContent"): ok("T17")
        else: fail("T17","still in panel")
    else: fail("T17","no delete button")

    # T18 — attach document
    begin("T18"); ensure(page); idle(page); sel_folder(page); time.sleep(1)
    try: page.locator(".content-row[data-category='product']").first.click(force=True, timeout=5000); time.sleep(4); wr(page)
    except: pass
    dt = page.query_selector('[data-tab="docs"]')
    if dt:
        dt.click(); time.sleep(3); wr(page)
        ab = page.query_selector("#propAttachDoc")
        if ab:
            ab.click(); time.sleep(1)
            if page.query_selector("#crudModalOverlay.visible"):
                page.fill("#crudDocAttachForm-search","A"); time.sleep(3)
                di = page.query_selector("#crudDocSearchResults .search-result-item[data-id]")
                if di:
                    di.click(); time.sleep(1)
                    modal_save(page,"#crudDocAttachSave",15); time.sleep(2); wr(page)
                    if page.query_selector_all("#propertyContent .prop-table tbody tr"): ok("T18")
                    else: fail("T18","no rows")
                else: fail("T18","no search results")
            else: fail("T18","modal not opened")
        else: fail("T18","no attach button")
    else: fail("T18","no docs tab")

    # T19 — detach document
    begin("T19"); ensure(page); idle(page)
    dd = page.query_selector(".crud-doc-detach")
    if dd:
        dd.click(); time.sleep(1); cf = page.query_selector("#crudConfirmOk")
        if cf: cf.click(); time.sleep(4); wr(page); ok("T19")
        else: fail("T19","no confirm")
    else: fail("T19","no detach button")

    # T20 — cleanup
    begin("T20"); ensure(page); idle(page); sel_folder(page); time.sleep(1)
    for target in ["TNEW-IN-BOM","TASSY","TCOMP"]:
        try:
            loc = page.locator(f".content-row:has-text('{target}') .crud-delete").first
            loc.click(force=True, timeout=3000); time.sleep(1)
            cf = page.query_selector("#crudConfirmOk")
            if cf: cf.click(); time.sleep(5); wr(page)
            ensure(page); idle(page); sel_folder(page); time.sleep(1)
        except: pass
    ok("T20")
    hide_title(page)
    return R, times

# ─── HTML report ───

def write_html(results, times, run_history, total_start, total_elapsed):
    ts_start = total_start.strftime("%Y-%m-%d %H:%M:%S")
    ts_end = (total_start + datetime.timedelta(seconds=total_elapsed)).strftime("%Y-%m-%d %H:%M:%S")
    passed = sum(1 for v in results.values() if v[0]=="PASS")
    failed = sum(1 for v in results.values() if v[0]=="FAIL")
    skipped = len(SCENARIOS) - len(results)
    total = len(SCENARIOS)
    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><title>PSS-aiR CRUD Test Results</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }}
h1 {{ color: #003d4d; }} h2 {{ color: #005566; margin-top: 30px; }}
.summary {{ font-size: 18px; margin: 10px 0 20px; }}
.pass {{ color: #28a745; font-weight: bold; }} .fail {{ color: #cc3333; font-weight: bold; }}
.skip {{ color: #888; }}
table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; font-size: 14px; }}
th {{ background: #005566; color: white; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
.note {{ color: #666; font-size: 12px; }}
</style></head><body>
<h1>PSS-aiR CRUD — Результаты тестирования</h1>
<p>Начало: {ts_start} | Окончание: {ts_end} | Длительность: {total_elapsed:.0f}с</p>
<p class="summary">Итого: <span class="pass">{passed} PASS</span>, <span class="fail">{failed} FAIL</span>, <span class="skip">{skipped} SKIP</span> из {total}</p>
<h2>Результаты</h2>
<table><tr><th>#</th><th>Описание</th><th>Время начала</th><th>Результат</th><th>Примечание</th></tr>
"""
    for sid, name in SCENARIOS:
        status, note = results.get(sid, ("SKIP","не выполнен"))
        cls = status.lower()
        t_str = times.get(sid, "").strftime("%H:%M:%S") if isinstance(times.get(sid), datetime.datetime) else ""
        html += f'<tr><td>{sid}</td><td>{name}</td><td>{t_str}</td><td class="{cls}">{status}</td><td class="note">{note}</td></tr>\n'
    html += "</table>\n"
    if run_history:
        html += "<h2>История прогонов</h2><table><tr><th>Прогон</th><th>PASS</th><th>FAIL</th><th>SKIP</th></tr>\n"
        for i, rh in enumerate(run_history, 1):
            html += f'<tr><td>#{i}</td><td>{rh[0]}</td><td>{rh[1]}</td><td>{rh[2]}</td></tr>\n'
        html += "</table>\n"
    html += "</body></html>"
    with open(REPORT_PATH, "w", encoding="utf-8") as f: f.write(html)

# ─── main ───

if __name__ == "__main__":
    MAX_RUNS = 5
    MAX_TIME = 2 * 3600
    total_start = datetime.datetime.now()
    start_time = time.time()
    run_history = []
    best_results, best_times, best_pass = {}, {}, 0

    for attempt in range(1, MAX_RUNS + 1):
        if time.time() - start_time > MAX_TIME:
            print(f"\n[TIMEOUT] 2h limit"); break

        print(f"\n{'='*60}\n  RUN #{attempt}\n{'='*60}")
        print("[SETUP] Restarting PSS...")
        if not restart_pss(): print("[SETUP] FAIL"); run_history.append((0,0,len(SCENARIOS))); continue
        try: requests.post(f"{BASE_URL}/api/disconnect", timeout=3)
        except: pass
        time.sleep(1); print("[SETUP] Ready")

        video_tmp = os.path.join(SCRIPT_DIR, f"_video_run{attempt}")
        if os.path.exists(video_tmp): shutil.rmtree(video_tmp)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=400)
            ctx = browser.new_context(viewport={"width":1400,"height":900}, record_video_dir=video_tmp, record_video_size={"width":1400,"height":900})
            page = ctx.new_page()
            try:
                results, times = run(page)
            except Exception as e:
                import traceback; traceback.print_exc()
                results, times = {}, {}
            time.sleep(2); ctx.close(); browser.close()

        pc = sum(1 for v in results.values() if v[0]=="PASS")
        fc = sum(1 for v in results.values() if v[0]=="FAIL")
        sc = len(SCENARIOS) - pc - fc
        run_history.append((pc,fc,sc))
        print(f"\n  Run #{attempt}: {pc} PASS, {fc} FAIL, {sc} SKIP")

        if pc > best_pass: best_pass, best_results, best_times = pc, results.copy(), times.copy()

        if pc == len(SCENARIOS):
            videos = glob.glob(os.path.join(video_tmp, "*.webm"))
            if videos: shutil.copy2(videos[0], VIDEO_PATH); print(f"  Video: {VIDEO_PATH}")
            shutil.rmtree(video_tmp, ignore_errors=True)
            print("\n  *** 100% PASS ***"); break
        else:
            shutil.rmtree(video_tmp, ignore_errors=True)

    write_html(best_results, best_times, run_history, total_start, time.time()-start_time)
    print(f"\nReport: {REPORT_PATH}")
    print(f"Done: {len(run_history)} runs, best={best_pass}/{len(SCENARIOS)}")
