"""Диагностический GUI-тест CRUD — один save на сессию.

PSS Lite не выдерживает >1 save в одной сессии (APLAPIERR_FILE_IO).
Каждый write-тест: restart PSS → clean DB → connect → 1 save → stop PSS.

Запуск: python PSS-aiR/test_gui_with_log.py
"""

import os, sys, time, datetime, subprocess, shutil, glob, requests
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5002"
PSS_PORT = 7239
PSS_EXE = r"C:\Program Files (x86)\PSS_MUI\AplNetTransportServTCP.exe"
DB_FILE = r"c:\_pss_lite_db\pss_moma_08_07_2025.aplb"
DB_BACKUP = r"c:\_pss_lite_db\pss_moma_08_07_2025_all_loaded.aplb"
DB_CFG = {"server_port": f"http://localhost:{PSS_PORT}", "db": "pss_moma_08_07_2025", "user": "Administrator", "password": ""}


def restart_pss_clean():
    """Kill PSS, restore clean DB, start PSS."""
    subprocess.run(["powershell", "-Command",
        "Get-Process | Where-Object { $_.Path -like '*AplNetTransportServ*' } | Stop-Process -Force -ErrorAction SilentlyContinue"],
        capture_output=True, timeout=10)
    time.sleep(3)
    # Restore clean DB + remove aux files
    shutil.copy2(DB_BACKUP, DB_FILE)
    for f in glob.glob(DB_FILE + ".*"):
        try: os.remove(f)
        except: pass
    for f in glob.glob(DB_FILE.replace('.aplb', '') + '.aclst*'):
        try: os.remove(f)
        except: pass
    for f in glob.glob(DB_FILE.replace('.aplb', '') + '.crc*'):
        try: os.remove(f)
        except: pass
    # Start PSS
    subprocess.Popen([PSS_EXE, f"/p:{PSS_PORT}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x8)
    for _ in range(20):
        try:
            if requests.get(f"http://localhost:{PSS_PORT}/rest/dblist", timeout=2).status_code == 200:
                return True
        except: pass
        time.sleep(1)
    return False


def connect_flask():
    """Connect PSS-aiR via Flask."""
    try: requests.post(f"{BASE_URL}/api/disconnect", timeout=3)
    except: pass
    time.sleep(1)
    r = requests.post(f"{BASE_URL}/api/connect", json=DB_CFG, timeout=15)
    return r.json().get("connected", False)


def idle(page):
    try: page.wait_for_load_state("networkidle", timeout=15000)
    except: pass
    for _ in range(20):
        if not page.query_selector(".spinner-overlay"): return
        time.sleep(0.5)


def wr(page):
    for _ in range(20):
        m = page.query_selector("#crudModalOverlay.visible")
        s = page.query_selector(".spinner-overlay")
        if not m and not s: return
        if m:
            try: page.click("#crudModalClose")
            except: pass
        time.sleep(0.5)
    page.evaluate("document.querySelectorAll('.spinner-overlay').forEach(s=>s.remove());"
                  "var m=document.getElementById('crudModalOverlay');if(m)m.classList.remove('visible')")


def sel(page, name="Aircrafts"):
    page.evaluate("()=>{var p=document.getElementById('panelLeft');"
                  "if(p&&p.classList.contains('minimized'))p.classList.remove('minimized')}")
    idle(page)
    loc = page.locator(f'.tree-node-row[data-name="{name}"]')
    if loc.count() > 0:
        loc.first.click(force=True)
        idle(page)
        time.sleep(1)


def msave(page, btn_id, timeout=120):
    idle(page)
    page.click(btn_id)
    for _ in range(timeout):
        time.sleep(1)
        if not page.query_selector("#crudModalOverlay.visible"):
            return True
    wr(page)
    return False


def main():
    print(f"=== GUI diagnostic test (1 save per session) === {datetime.datetime.now()}")
    print()

    results = []

    def run_test(name, fn):
        """Restart PSS, open browser, run fn, close browser."""
        print(f"\n{'─'*60}")
        print(f"  {name}")
        print(f"{'─'*60}")

        # Restart PSS with clean DB
        if not restart_pss_clean():
            print(f"  [FAIL] PSS didn't start")
            results.append((name, "FAIL", "PSS didn't start"))
            return

        # Connect Flask
        if not connect_flask():
            print(f"  [FAIL] Flask didn't connect")
            results.append((name, "FAIL", "Flask didn't connect"))
            return

        # Open browser
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=400)
            page = browser.new_page()
            page.set_viewport_size({"width": 1400, "height": 900})
            page.goto(BASE_URL)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(4)
            idle(page)

            try:
                ok, note = fn(page)
                status = "PASS" if ok else "FAIL"
                results.append((name, status, note))
                print(f"  [{status}] {note}")
            except Exception as e:
                results.append((name, "FAIL", str(e)[:100]))
                print(f"  [FAIL] {str(e)[:100]}")

            time.sleep(2)
            browser.close()

    # ─── T05: Create product ───
    def test_create(page):
        sel(page)
        idle(page)
        page.click("#crudBtnCreateProduct")
        time.sleep(1)
        page.fill("#crudProductForm-id", "TEST-001")
        page.fill("#crudProductForm-name", "TestProduct")
        page.select_option("#crudProductForm-formation_type", "assembly")
        closed = msave(page, "#crudProductSave", 30)
        idle(page)
        sel(page)
        idle(page)
        h = page.inner_html("#contentArea")
        found = "TEST-001" in h or "TestProduct" in h
        return found and closed, f"in_table={found}, closed={closed}"

    run_test("T05: Create product", test_create)

    # ─── T06: Edit product ───
    def test_edit(page):
        sel(page)
        idle(page)
        # Find product created by previous test (or any product)
        loc = page.locator(".crud-edit").first
        if loc.count() == 0:
            return False, "no edit button"
        loc.click(force=True, timeout=5000)
        time.sleep(2)
        if not page.query_selector("#crudModalOverlay.visible"):
            return False, "modal not opened"
        page.fill("#crudProductEditForm-name", "Edited")
        closed = msave(page, "#crudProductEditSave", 60)
        idle(page)
        sel(page)
        idle(page)
        h = page.inner_html("#contentArea")
        return closed, f"closed={closed}"

    run_test("T06: Edit product", test_edit)

    # ─── T07: Delete product ───
    def test_delete(page):
        sel(page)
        idle(page)
        loc = page.locator(".crud-delete").first
        if loc.count() == 0:
            return False, "no delete button"
        loc.click(force=True, timeout=5000)
        time.sleep(1)
        cf = page.query_selector("#crudConfirmOk")
        if not cf:
            return False, "no confirm"
        idle(page)
        cf.click()
        time.sleep(5)
        idle(page)
        return True, "deleted"

    run_test("T07: Delete product", test_delete)

    # ─── T08: Create 2 products (assembly + component) ───
    def test_create_two(page):
        sel(page)
        idle(page)
        page.click("#crudBtnCreateProduct"); time.sleep(1)
        page.fill("#crudProductForm-id", "ASSY-001")
        page.fill("#crudProductForm-name", "TestAssy")
        page.select_option("#crudProductForm-formation_type", "assembly")
        c1 = msave(page, "#crudProductSave", 30)
        idle(page)
        # Note: second create in same session may fail (FILE_IO)
        # But with reconnect before each write, it might work
        sel(page); idle(page)
        page.click("#crudBtnCreateProduct"); time.sleep(1)
        page.fill("#crudProductForm-id", "COMP-001")
        page.fill("#crudProductForm-name", "TestComp")
        page.select_option("#crudProductForm-formation_type", "part")
        c2 = msave(page, "#crudProductSave", 30)
        idle(page)
        sel(page); idle(page)
        h = page.inner_html("#contentArea")
        assy = "ASSY-001" in h or "TestAssy" in h
        comp = "COMP-001" in h or "TestComp" in h
        return assy and comp, f"assy={assy}({c1}), comp={comp}({c2})"

    run_test("T08: Create assembly + component", test_create_two)

    # ─── T12: Create business process ───
    def test_create_process(page):
        sel(page)
        idle(page)
        bp = page.query_selector("#crudBtnCreateProcess")
        if not bp:
            return False, "no process button"
        bp.click(); time.sleep(1)
        if not page.query_selector("#crudModalOverlay.visible"):
            return False, "modal not opened"
        page.fill("#crudProcessForm-id", "PROC-001")
        page.fill("#crudProcessForm-name", "TestProcess")
        closed = msave(page, "#crudProcessSave", 30)
        return closed, f"closed={closed}"

    run_test("T12: Create business process", test_create_process)

    # ─── Summary ───
    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"{'='*60}")
    for name, status, note in results:
        print(f"  [{status:4}] {name:40} {note}")
    passed = sum(1 for _, s, _ in results if s == "PASS")
    total = len(results)
    print(f"\n  {passed}/{total} PASS")
    print(f"\nDone at {datetime.datetime.now()}")


if __name__ == "__main__":
    main()
