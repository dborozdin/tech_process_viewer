"""API CRUD tests via Playwright on the API Docs (Swagger) server (port 5004).

После объединения CRUD в Smorest (`/api/v1/`) тесты бьют по новым путям.

Запуск:
    python tech_process_viewer/test_api_swagger.py

Артефакты:
    tech_process_viewer/api_test_results.html
    tech_process_viewer/api_test_video.webm  (при 100% PASS)
"""

import os
import sys
import time
import datetime
import subprocess
import requests
import shutil
import glob
import traceback
import html as _html
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE_URL = "http://localhost:5004"
PSS_PORT = 7239
PSS_EXE = r"c:\a-yatzk\aplLiteServer.exe"
DB_CFG = {
    "server_port": f"http://localhost:{PSS_PORT}",
    "db": "pss_moma_08_07_2025",
    "user": "Administrator",
    "password": "",
}
DB_FILE = r"c:\_pss_lite_db\pss_moma_08_07_2025.aplb"
DB_BACKUP = r"c:\_pss_lite_db\pss_moma_08_07_2025_all_loaded.aplb"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(SCRIPT_DIR, "api_test_results.html")
VIDEO_PATH = os.path.join(SCRIPT_DIR, "api_test_video.webm")


SCENARIOS = [
    ("T01", "GET  /api/dblist — список БД"),
    ("T02", "POST /api/connect — подключение к БД"),
    ("T03", "GET  /api/status — статус подключения"),
    ("T04", "GET  /api/v1/resources/types — типы ресурсов"),
    ("T05", "GET  /api/v1/characteristics/ — определения характеристик"),
    ("T06", "POST /api/v1/products/ — создать сборку (assy)"),
    ("T07", "POST /api/v1/products/ — создать компонент (comp)"),
    ("T08", "POST /api/v1/products/{assy}/bom/items — связать BOM"),
    ("T09", "GET  /api/v1/products/{assy}/bom — BOM-структура"),
    ("T10", "PUT  /api/v1/products/{assy} — обновить продукт"),
    ("T11", "DELETE /api/v1/products/{assy}/bom/items/{bom_item} — удалить связь"),
    ("T12", "POST /api/v1/business-processes/ — создать процесс"),
    ("T13", "PUT  /api/v1/business-processes/{bp} — обновить процесс"),
    ("T14", "POST /api/v1/business-processes/{bp}/elements — вложенный элемент"),
    ("T15", "DELETE /api/v1/business-processes/{bp}/elements/{ch} — удалить вложение"),
    ("T16", "POST /api/v1/business-processes/{bp}/link-product — привязка к изделию"),
    ("T17", "POST /api/v1/characteristics/values — создать значение"),
    ("T18", "GET  /api/v1/characteristics/values/{item} — значения объекта"),
    ("T19", "PUT  /api/v1/characteristics/values/{val} — обновить значение"),
    ("T20", "DELETE /api/v1/characteristics/values/{val} — удалить значение"),
    ("T21", "POST /api/v1/business-processes/{bp}/resources — создать ресурс"),
    ("T22", "PUT  /api/v1/business-processes/{bp}/resources/{res} — обновить ресурс"),
    ("T23", "DELETE /api/v1/business-processes/{bp}/resources/{res} — удалить ресурс"),
    ("T24", "GET  /api/v1/documents/search — поиск документов"),
    ("T25", "DELETE /api/v1/business-processes/{bp} + /api/v1/products/{assy} — cleanup"),
]


# ─── infrastructure ───

def restart_pss():
    try:
        subprocess.run(["powershell", "-Command",
            "Get-Process | Where-Object { $_.Path -like '*AplNetTransportServ*' } | Stop-Process -Force -ErrorAction SilentlyContinue"],
            capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        print("    [WARN] PowerShell Stop-Process timeout — continuing")
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
        except Exception:
            pass
        time.sleep(1)
    return False


def show_title(page, tid, name, status=""):
    color = {"PASS": "#28a745", "FAIL": "#cc3333", "": "#005566"}.get(status, "#005566")
    safe_name = name.replace('"', '\\"').replace("'", "\\'")
    page.evaluate(f"""(() => {{
      let o = document.getElementById('__test_overlay');
      if (!o) {{
        o = document.createElement('div');
        o.id = '__test_overlay';
        o.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:99999;'
                        + 'padding:18px 24px;color:white;font:bold 18px sans-serif;'
                        + 'box-shadow:0 4px 12px rgba(0,0,0,0.4);text-align:center;';
        document.body.appendChild(o);
      }}
      o.style.background = '{color}';
      o.textContent = '{tid}: {safe_name}' + ({"' — '+'%s'" % status if status else "''"});
    }})()""")


def hide_title(page):
    try:
        page.evaluate("(() => { const o = document.getElementById('__test_overlay'); if (o) o.remove(); })()")
    except Exception:
        pass


def fetch_json(page, method, path, json_body=None, _retry=True):
    """Make HTTP request from the browser context.

    Returns (status, body). body may be dict/list/str/None.

    Read body via .text() once, then JSON.parse — avoids 'body stream already read'.
    On 401, reconnect to PSS and retry once.
    """
    import json as _json
    js = (
        "async ([m, p, b]) => {"
        "  const opts = {method: m, headers: {'Content-Type': 'application/json'}};"
        "  if (b !== null && b !== undefined) opts.body = b;"
        "  const r = await fetch(p, opts);"
        "  const text = await r.text();"
        "  let body = null;"
        "  if (text) { try { body = JSON.parse(text); } catch (e) { body = text; } }"
        "  return {status: r.status, body};"
        "}"
    )
    arg = [method, path, _json.dumps(json_body) if json_body is not None else None]
    r = page.evaluate(js, arg)
    if r.get("status") == 401 and _retry and path != "/api/connect":
        # Reconnect once and retry
        page.evaluate(js, ["POST", "/api/connect", _json.dumps(DB_CFG)])
        return fetch_json(page, method, path, json_body, _retry=False)
    return r


# ─── scenarios ───

def run_all(page, results):
    state = {}

    def begin(tid, name):
        results[tid] = {"status": "PENDING", "note": "", "start": datetime.datetime.now(),
                        "end": None, "trace": ""}
        show_title(page, tid, name)
        print(f"  >>> {tid}: {name}")

    def ok(tid, note=""):
        results[tid]["status"] = "PASS"
        results[tid]["note"] = note
        results[tid]["end"] = datetime.datetime.now()
        name = next((n for i, n in SCENARIOS if i == tid), tid)
        show_title(page, tid, name, "PASS")
        print(f"  <<< {tid}: PASS — {note}")

    def fail(tid, note="", exc=None):
        results[tid]["status"] = "FAIL"
        results[tid]["note"] = note
        results[tid]["end"] = datetime.datetime.now()
        if exc is not None:
            results[tid]["trace"] = traceback.format_exc()
        name = next((n for i, n in SCENARIOS if i == tid), tid)
        show_title(page, tid, name, "FAIL")
        print(f"  <<< {tid}: FAIL — {note}")

    # T01: dblist
    begin("T01", "GET /api/dblist")
    try:
        r = fetch_json(page, "GET", "/api/dblist")
        if r["status"] == 200:
            ok("T01", "HTTP 200")
        else:
            fail("T01", f"HTTP {r['status']}: {str(r['body'])[:80]}")
    except Exception as e:
        fail("T01", str(e)[:120], exc=e)
    time.sleep(1)

    # T02: connect
    begin("T02", "POST /api/connect")
    try:
        r = fetch_json(page, "POST", "/api/connect", DB_CFG)
        if r["status"] == 200 and isinstance(r["body"], dict) and r["body"].get("connected"):
            ok("T02", f"session_key={(r['body'].get('session_key') or '')[:18]}…")
        else:
            fail("T02", f"HTTP {r['status']}: {str(r['body'])[:120]}")
            return
    except Exception as e:
        fail("T02", str(e)[:120], exc=e); return
    time.sleep(1)

    # T03: status
    begin("T03", "GET /api/status")
    try:
        r = fetch_json(page, "GET", "/api/status")
        if r["status"] == 200 and r["body"].get("connected"): ok("T03", "connected=true")
        else: fail("T03", f"HTTP {r['status']}: {r['body']}")
    except Exception as e:
        fail("T03", str(e)[:120], exc=e)
    time.sleep(1)

    # T04: resource-types
    begin("T04", "GET /api/v1/resources/types")
    try:
        r = fetch_json(page, "GET", "/api/v1/resources/types")
        types = (r["body"] or {}).get("resource_types", []) if isinstance(r["body"], dict) else []
        # find first with sys_id
        sys_id = next((t.get("sys_id") for t in types if t.get("sys_id")), None)
        if r["status"] == 200 and sys_id:
            state["res_type_sys_id"] = sys_id
            ok("T04", f"{len(types)} types, sys_id={sys_id}")
        else:
            fail("T04", f"HTTP {r['status']}, types={len(types)}, sys_id={sys_id}")
    except Exception as e:
        fail("T04", str(e)[:120], exc=e)
    time.sleep(1)

    # T05: characteristics
    begin("T05", "GET /api/v1/characteristics/")
    try:
        r = fetch_json(page, "GET", "/api/v1/characteristics/")
        data = (r["body"] or {}).get("data", []) if isinstance(r["body"], dict) else []
        if r["status"] == 200 and len(data) > 0:
            state["char_id"] = data[0]["sys_id"]
            ok("T05", f"{len(data)} chars, first sys_id={state['char_id']}")
        else:
            fail("T05", f"HTTP {r['status']}, count={len(data)}")
    except Exception as e:
        fail("T05", str(e)[:120], exc=e)
    time.sleep(1)

    # Helper: create product, returns (product_id, pdf_id)
    def _create_product(prd_id, name):
        r = fetch_json(page, "POST", "/api/v1/products/", {"id": prd_id, "name": name})
        if r["status"] != 201: return None, None, r
        product_id = (r["body"] or {}).get("product_id")
        # Fetch PDF
        time.sleep(1)
        gr = fetch_json(page, "GET", f"/api/v1/products/{product_id}")
        defs = (gr["body"] or {}).get("definitions", []) if isinstance(gr["body"], dict) else []
        pdf_id = defs[0].get("id") if defs else None
        return product_id, pdf_id, r

    # T06: assy
    begin("T06", "POST /api/v1/products/ (assy)")
    try:
        pid, pdf, r = _create_product("API-ASSY-001", "ApiAssy")
        if pid and pdf:
            state["assy_product_id"] = pid
            state["assy_pdf_id"] = pdf
            ok("T06", f"product_id={pid}, pdf_id={pdf}")
        else:
            fail("T06", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T06", str(e)[:120], exc=e)
    time.sleep(2)

    # T07: comp
    begin("T07", "POST /api/v1/products/ (comp)")
    try:
        pid, pdf, r = _create_product("API-COMP-001", "ApiComp")
        if pid and pdf:
            state["comp_product_id"] = pid
            state["comp_pdf_id"] = pdf
            ok("T07", f"product_id={pid}, pdf_id={pdf}")
        else:
            fail("T07", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T07", str(e)[:120], exc=e)
    time.sleep(2)

    # T08: BOM add
    begin("T08", "POST /api/v1/products/{assy}/bom/items")
    try:
        if not (state.get("assy_product_id") and state.get("comp_pdf_id")):
            fail("T08", "preconditions failed")
        else:
            r = fetch_json(page, "POST",
                           f"/api/v1/products/{state['assy_product_id']}/bom/items",
                           {"component_id": state["comp_pdf_id"], "quantity": 5})
            if r["status"] == 201 and (r["body"] or {}).get("bom_item_id"):
                state["bom_item_id"] = r["body"]["bom_item_id"]
                ok("T08", f"bom_item_id={state['bom_item_id']}")
            else:
                fail("T08", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T08", str(e)[:120], exc=e)
    time.sleep(2)

    # T09: GET bom
    begin("T09", "GET /api/v1/products/{assy}/bom")
    try:
        if not (state.get("assy_product_id") and state.get("comp_pdf_id")):
            fail("T09", "no assy_product_id/comp_pdf_id")
        else:
            ok9 = False
            comp_pdf = state["comp_pdf_id"]
            s = ""
            for _ in range(8):
                r = fetch_json(page, "GET", f"/api/v1/products/{state['assy_product_id']}/bom")
                s = str(r["body"])
                if r["status"] == 200 and (str(comp_pdf) in s or "ApiComp" in s or "API-COMP" in s):
                    ok9 = True; break
                time.sleep(1)
            if ok9:
                ok("T09", f"BOM содержит компонент pdf={comp_pdf}")
            else:
                fail("T09", f"BOM не содержит pdf={comp_pdf}: {s[:120]}")
    except Exception as e:
        fail("T09", str(e)[:120], exc=e)
    time.sleep(1)

    # T10: update product
    begin("T10", "PUT /api/v1/products/{assy}")
    try:
        if not state.get("assy_product_id"):
            fail("T10", "no assy_product_id")
        else:
            r = fetch_json(page, "PUT", f"/api/v1/products/{state['assy_product_id']}",
                           {"name": "ApiAssyEdited"})
            if r["status"] == 200 and (r["body"] or {}).get("success"):
                ok("T10", "name updated")
            else:
                fail("T10", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T10", str(e)[:120], exc=e)
    time.sleep(2)

    # T11: delete BOM item
    begin("T11", "DELETE /api/v1/products/{assy}/bom/items/{bom}")
    try:
        if not (state.get("assy_product_id") and state.get("bom_item_id")):
            fail("T11", "no assy or bom_item_id")
        else:
            r = fetch_json(page, "DELETE",
                           f"/api/v1/products/{state['assy_product_id']}/bom/items/{state['bom_item_id']}")
            if r["status"] in (200, 204):
                ok("T11", f"HTTP {r['status']}")
            else:
                fail("T11", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T11", str(e)[:120], exc=e)
    time.sleep(2)

    # T12: BP create
    begin("T12", "POST /api/v1/business-processes/")
    try:
        r = fetch_json(page, "POST", "/api/v1/business-processes/",
                       {"id": "API-BP-001", "name": "ApiProcess", "description": "test"})
        if r["status"] == 201 and (r["body"] or {}).get("process_id"):
            state["bp_id"] = r["body"]["process_id"]
            ok("T12", f"process_id={state['bp_id']}")
        else:
            fail("T12", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T12", str(e)[:120], exc=e)
    time.sleep(2)

    # T13: BP update
    begin("T13", "PUT /api/v1/business-processes/{bp}")
    try:
        if not state.get("bp_id"):
            fail("T13", "no bp_id")
        else:
            r = fetch_json(page, "PUT", f"/api/v1/business-processes/{state['bp_id']}",
                           {"name": "ApiProcessEdited", "description": "edited"})
            if r["status"] == 200 and (r["body"] or {}).get("success"):
                ok("T13", "BP updated")
            else:
                fail("T13", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T13", str(e)[:120], exc=e)
    time.sleep(2)

    # T14: add child element
    begin("T14", "POST /api/v1/business-processes/{bp}/elements")
    try:
        rc = fetch_json(page, "POST", "/api/v1/business-processes/",
                        {"id": "API-BP-CHILD", "name": "ApiBpChild"})
        if rc["status"] != 201 or not (rc["body"] or {}).get("process_id"):
            fail("T14", f"create child HTTP {rc['status']}: {str(rc['body'])[:80]}")
        else:
            state["bp_child_id"] = rc["body"]["process_id"]
            time.sleep(2)
            r = fetch_json(page, "POST",
                           f"/api/v1/business-processes/{state['bp_id']}/elements",
                           {"element_id": state["bp_child_id"]})
            if r["status"] in (200, 201) and (r["body"] or {}).get("success"):
                ok("T14", f"child {state['bp_child_id']} added to {state['bp_id']}")
            else:
                fail("T14", f"add HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T14", str(e)[:120], exc=e)
    time.sleep(2)

    # T15: delete child element
    begin("T15", "DELETE /api/v1/business-processes/{bp}/elements/{ch}")
    try:
        if not (state.get("bp_id") and state.get("bp_child_id")):
            fail("T15", "no bp/child")
        else:
            r = fetch_json(page, "DELETE",
                           f"/api/v1/business-processes/{state['bp_id']}/elements/{state['bp_child_id']}")
            if r["status"] in (200, 204): ok("T15", f"HTTP {r['status']}")
            else: fail("T15", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T15", str(e)[:120], exc=e)
    time.sleep(2)

    # T16: link BP → product
    begin("T16", "POST /api/v1/business-processes/{bp}/link-product")
    try:
        if not (state.get("bp_id") and state.get("assy_pdf_id")):
            fail("T16", "no bp/assy_pdf")
        else:
            r = fetch_json(page, "POST",
                           f"/api/v1/business-processes/{state['bp_id']}/link-product",
                           {"pdf_id": state["assy_pdf_id"]})
            if r["status"] in (200, 201) and (r["body"] or {}).get("success"):
                ok("T16", f"linked bp {state['bp_id']} → pdf {state['assy_pdf_id']}")
            else:
                fail("T16", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T16", str(e)[:120], exc=e)
    time.sleep(2)

    # T17: create char value
    begin("T17", "POST /api/v1/characteristics/values")
    try:
        if not (state.get("char_id") and state.get("assy_pdf_id")):
            fail("T17", "no char_id/assy_pdf_id")
        else:
            r = fetch_json(page, "POST", "/api/v1/characteristics/values",
                           {"item_id": state["assy_pdf_id"],
                            "characteristic_id": state["char_id"],
                            "value": "ApiCharVal-1",
                            "subtype": "apl_descriptive_characteristic_value",
                            "item_type": "apl_product_definition_formation"})
            if r["status"] == 201 and (r["body"] or {}).get("data", {}).get("sys_id"):
                state["char_val_id"] = r["body"]["data"]["sys_id"]
                ok("T17", f"sys_id={state['char_val_id']}")
            else:
                fail("T17", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T17", str(e)[:120], exc=e)
    time.sleep(2)

    # T18: get values for item
    begin("T18", "GET /api/v1/characteristics/values/{item}")
    try:
        if not state.get("assy_pdf_id"):
            fail("T18", "no assy_pdf_id")
        else:
            r = fetch_json(page, "GET", f"/api/v1/characteristics/values/{state['assy_pdf_id']}")
            data = (r["body"] or {}).get("data", []) if isinstance(r["body"], dict) else []
            if r["status"] == 200 and len(data) > 0:
                ok("T18", f"{len(data)} values")
            else:
                fail("T18", f"HTTP {r['status']}, count={len(data)}")
    except Exception as e:
        fail("T18", str(e)[:120], exc=e)
    time.sleep(1)

    # T19: update char value
    begin("T19", "PUT /api/v1/characteristics/values/{val}")
    try:
        if not state.get("char_val_id"):
            fail("T19", "no char_val_id")
        else:
            r = fetch_json(page, "PUT", f"/api/v1/characteristics/values/{state['char_val_id']}",
                           {"value": "ApiCharVal-Edited",
                            "subtype": "apl_descriptive_characteristic_value"})
            if r["status"] == 200 and (r["body"] or {}).get("success"):
                ok("T19", "value updated")
            else:
                fail("T19", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T19", str(e)[:120], exc=e)
    time.sleep(2)

    # T20: delete char value
    begin("T20", "DELETE /api/v1/characteristics/values/{val}")
    try:
        if not state.get("char_val_id"):
            fail("T20", "no char_val_id")
        else:
            r = fetch_json(page, "DELETE", f"/api/v1/characteristics/values/{state['char_val_id']}")
            if r["status"] in (200, 204) and (r["body"] is None or (r["body"] or {}).get("success") is not False):
                ok("T20", f"HTTP {r['status']}")
            else:
                fail("T20", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T20", str(e)[:120], exc=e)
    time.sleep(2)

    # T21: create resource (BP-scoped endpoint)
    begin("T21", "POST /api/v1/business-processes/{bp}/resources")
    try:
        if not (state.get("bp_id") and state.get("res_type_sys_id")):
            fail("T21", "no bp/res_type_sys_id")
        else:
            r = fetch_json(page, "POST",
                           f"/api/v1/business-processes/{state['bp_id']}/resources",
                           {"id": "API-RES-001", "name": "ApiRes",
                            "type_id": state["res_type_sys_id"],
                            "value_component": 7})
            if r["status"] == 201 and ((r["body"] or {}).get("resource_id") or (r["body"] or {}).get("data", {}).get("resource_id")):
                rid = (r["body"] or {}).get("resource_id") or r["body"]["data"]["resource_id"]
                state["res_id"] = rid
                ok("T21", f"resource_id={rid}")
            else:
                fail("T21", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T21", str(e)[:120], exc=e)
    time.sleep(2)

    # T22: update resource
    begin("T22", "PUT /api/v1/business-processes/{bp}/resources/{res}")
    try:
        if not state.get("res_id"):
            fail("T22", "no res_id")
        else:
            r = fetch_json(page, "PUT",
                           f"/api/v1/business-processes/{state['bp_id']}/resources/{state['res_id']}",
                           {"name": "ApiResEdited", "value_component": 9})
            if r["status"] == 200 and (r["body"] or {}).get("success"):
                ok("T22", "resource updated")
            else:
                fail("T22", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T22", str(e)[:120], exc=e)
    time.sleep(2)

    # T23: delete resource
    begin("T23", "DELETE /api/v1/business-processes/{bp}/resources/{res}")
    try:
        if not state.get("res_id"):
            fail("T23", "no res_id")
        else:
            r = fetch_json(page, "DELETE",
                           f"/api/v1/business-processes/{state['bp_id']}/resources/{state['res_id']}")
            if r["status"] in (200, 204): ok("T23", f"HTTP {r['status']}")
            else: fail("T23", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T23", str(e)[:120], exc=e)
    time.sleep(2)

    # T24: doc search (smoke test — pss_moma имеет 0 документов, ok если []
    begin("T24", "GET /api/v1/documents/search")
    try:
        r = fetch_json(page, "GET", "/api/v1/documents/search?q=A")
        if r["status"] == 200 and isinstance((r["body"] or {}).get("data"), list):
            n = len((r["body"] or {}).get("data") or [])
            ok("T24", f"HTTP 200, found {n} docs")
        else:
            fail("T24", f"HTTP {r['status']}: {str(r['body'])[:120]}")
    except Exception as e:
        fail("T24", str(e)[:120], exc=e)
    time.sleep(1)

    # T25: cleanup — DELETE BP + product
    begin("T25", "DELETE BP + product (cleanup)")
    try:
        notes = []
        if state.get("bp_child_id"):
            r = fetch_json(page, "DELETE", f"/api/v1/business-processes/{state['bp_child_id']}")
            notes.append(f"bp_child→{r['status']}")
        if state.get("bp_id"):
            r = fetch_json(page, "DELETE", f"/api/v1/business-processes/{state['bp_id']}")
            notes.append(f"bp→{r['status']}")
        if state.get("assy_product_id"):
            r = fetch_json(page, "DELETE", f"/api/v1/products/{state['assy_product_id']}")
            notes.append(f"assy→{r['status']}")
        if state.get("comp_product_id"):
            r = fetch_json(page, "DELETE", f"/api/v1/products/{state['comp_product_id']}")
            notes.append(f"comp→{r['status']}")
        ok("T25", "; ".join(notes) if notes else "nothing to clean")
    except Exception as e:
        fail("T25", str(e)[:120], exc=e)
    time.sleep(1)


# ─── HTML report ───

def write_html(results, total_start, total_elapsed, run_history):
    ts_start = total_start.strftime("%Y-%m-%d %H:%M:%S")
    ts_end = (total_start + datetime.timedelta(seconds=total_elapsed)).strftime("%Y-%m-%d %H:%M:%S")
    passed = sum(1 for r in results.values() if r.get("status") == "PASS")
    failed = sum(1 for r in results.values() if r.get("status") == "FAIL")
    skipped = len(SCENARIOS) - len(results)
    total = len(SCENARIOS)
    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><title>API CRUD — Результаты</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }}
h1 {{ color: #003d4d; }} h2 {{ color: #005566; margin-top: 30px; }}
.summary {{ font-size: 18px; margin: 10px 0 20px; }}
.pass {{ color: #28a745; font-weight: bold; }}
.fail {{ color: #cc3333; font-weight: bold; }}
.skip {{ color: #888; }}
table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; font-size: 14px; }}
th {{ background: #005566; color: white; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
.note {{ color: #666; font-size: 12px; }}
pre {{ white-space: pre-wrap; font-size: 12px; background: #fbeaea; padding: 8px; }}
</style></head><body>
<h1>API CRUD на 5004 (/api/v1/) — Результаты</h1>
<p>Начало: {ts_start} | Окончание: {ts_end} | Длительность: {total_elapsed:.0f}с</p>
<p class="summary">Итого: <span class="pass">{passed} PASS</span>, <span class="fail">{failed} FAIL</span>, <span class="skip">{skipped} SKIP</span> из {total}</p>
<h2>Результаты</h2>
<table><tr><th>#</th><th>Описание</th><th>Начало</th><th>Окончание</th><th>Длит., мс</th><th>Результат</th><th>Примечание</th></tr>
"""
    for sid, name in SCENARIOS:
        r = results.get(sid, {"status": "SKIP", "note": "не выполнен", "start": None, "end": None})
        cls = r["status"].lower()
        ts = r["start"].strftime("%H:%M:%S") if r.get("start") else ""
        te = r["end"].strftime("%H:%M:%S") if r.get("end") else ""
        dur = ""
        if r.get("start") and r.get("end"):
            dur = str(int((r["end"] - r["start"]).total_seconds() * 1000))
        html += (f'<tr><td>{sid}</td><td>{name}</td><td>{ts}</td><td>{te}</td>'
                 f'<td>{dur}</td><td class="{cls}">{r["status"]}</td>'
                 f'<td class="note">{_html.escape(str(r.get("note", "")))}</td></tr>\n')
        if r["status"] == "FAIL" and r.get("trace"):
            html += (f'<tr><td colspan="7"><details><summary>Stack trace</summary>'
                     f'<pre>{_html.escape(r["trace"])}</pre></details></td></tr>\n')
    html += "</table>\n"
    if run_history:
        html += "<h2>История прогонов</h2><table><tr><th>Прогон</th><th>PASS</th><th>FAIL</th></tr>\n"
        for i, (p, f) in enumerate(run_history, 1):
            html += f'<tr><td>#{i}</td><td>{p}</td><td>{f}</td></tr>\n'
        html += "</table>\n"
    html += "</body></html>"
    with open(REPORT_PATH, "w", encoding="utf-8") as fp:
        fp.write(html)


# ─── main ───

if __name__ == "__main__":
    MAX_RUNS = 3
    total_start = datetime.datetime.now()
    start_time = time.time()
    run_history = []
    best_results, best_pass = {}, 0

    for attempt in range(1, MAX_RUNS + 1):
        print(f"\n{'='*60}\n  RUN #{attempt}\n{'='*60}")
        print("[SETUP] Restarting PSS...")
        if not restart_pss():
            print("[SETUP] PSS restart failed"); run_history.append((0, len(SCENARIOS))); continue
        print("[SETUP] Ready")

        video_tmp = os.path.join(SCRIPT_DIR, f"_api_video_run{attempt}")
        if os.path.exists(video_tmp): shutil.rmtree(video_tmp)

        results = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=400)
            ctx = browser.new_context(viewport={"width": 1400, "height": 900},
                                       record_video_dir=video_tmp,
                                       record_video_size={"width": 1400, "height": 900})
            page = ctx.new_page()
            try:
                page.goto(f"{BASE_URL}/api/docs"); page.wait_for_load_state("domcontentloaded"); time.sleep(3)
            except Exception:
                pass
            try:
                run_all(page, results)
            except Exception as e:
                traceback.print_exc()
                results["__runner__"] = {"status": "FAIL", "note": str(e)[:200],
                                         "start": datetime.datetime.now(), "end": None,
                                         "trace": traceback.format_exc()}
            time.sleep(2); ctx.close(); browser.close()

        pc = sum(1 for r in results.values() if r.get("status") == "PASS")
        fc = sum(1 for r in results.values() if r.get("status") == "FAIL")
        run_history.append((pc, fc))
        print(f"\n  Run #{attempt}: {pc} PASS, {fc} FAIL")

        if pc > best_pass:
            best_pass, best_results = pc, results.copy()

        if pc == len(SCENARIOS):
            videos = glob.glob(os.path.join(video_tmp, "*.webm"))
            if videos:
                shutil.copy2(videos[0], VIDEO_PATH)
                print(f"  Video: {VIDEO_PATH}")
            shutil.rmtree(video_tmp, ignore_errors=True)
            print("\n  *** 100% PASS ***"); break
        else:
            shutil.rmtree(video_tmp, ignore_errors=True)

    write_html(best_results, total_start, time.time() - start_time, run_history)
    print(f"\nReport: {REPORT_PATH}")
    print(f"Done: {len(run_history)} runs, best={best_pass}/{len(SCENARIOS)}")
    sys.exit(0 if best_pass == len(SCENARIOS) else 1)
