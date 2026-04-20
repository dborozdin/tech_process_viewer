"""Playwright runner: открывает Swagger UI на :5004, для каждой группы кликает
«▶ Run all», ждёт окончания, оставляет спойлер раскрытым (видно результаты).

Сценарий:
1. restart_pss → восстановление БД из бэкапа.
2. Получить список групп через GET /api/v1/test-runner/groups.
3. Запустить Chromium (headless=False, slow_mo=300, record_video).
4. Для каждой группы:
   - найти tag-section
   - раскрыть тег если свернут
   - открыть спойлер «📊 Результаты»
   - кликнуть «▶ Run all», дождаться «Готово:»
   - подождать 3 сек чтобы зритель увидел результат
5. Закрыть context — видео сохраняется. Скопировать в api_test_video_all_groups.webm.
6. Собрать общий HTML отчёт api_test_results_all_groups.html из истории всех групп.
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
DB_FILE = r"c:\_pss_lite_db\pss_moma_08_07_2025.aplb"
DB_BACKUP = r"c:\_pss_lite_db\pss_moma_08_07_2025_all_loaded.aplb"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(SCRIPT_DIR, "api_test_results_all_groups.html")
VIDEO_PATH = os.path.join(SCRIPT_DIR, "api_test_video_all_groups.webm")


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


def get_groups():
    r = requests.get(f"{BASE_URL}/api/v1/test-runner/groups", timeout=10)
    r.raise_for_status()
    return list(r.json().get("groups", {}).keys())


def get_history(group):
    try:
        r = requests.get(f"{BASE_URL}/api/v1/test-runner/history?group={group}", timeout=10)
        if r.status_code == 200:
            j = r.json()
            return j if j and j.get("results") else None
    except Exception:
        pass
    return None


def write_html(history_per_group, started, finished):
    passed = sum(h.get("summary", {}).get("passed", 0) for h in history_per_group.values() if h)
    failed = sum(h.get("summary", {}).get("failed", 0) for h in history_per_group.values() if h)
    total = sum(h.get("summary", {}).get("total", 0) for h in history_per_group.values() if h)
    duration = (finished - started).total_seconds()

    rows = []
    for group, h in history_per_group.items():
        if not h:
            rows.append(f'<tr><td>{_html.escape(group)}</td><td colspan="6" class="skip">no data</td></tr>')
            continue
        s = h.get("summary", {})
        cls = "pass" if s.get("failed", 0) == 0 else "fail"
        rows.append(
            f'<tr><td><b>{_html.escape(group)}</b></td>'
            f'<td>{_html.escape(h.get("title",""))}</td>'
            f'<td>{_html.escape(h.get("started_at",""))}</td>'
            f'<td>{_html.escape(h.get("finished_at",""))}</td>'
            f'<td>{h.get("duration_s","")}с</td>'
            f'<td class="{cls}">{s.get("passed",0)}/{s.get("total",0)} PASS '
            f'({s.get("failed",0)} FAIL)</td>'
            f'<td><details><summary>Сценарии</summary>'
            + "<table class=inner>"
            + "".join([
                f'<tr><td>{_html.escape(r["scenario"])}</td>'
                f'<td>{_html.escape(r["method"])} {_html.escape(r["path"])}</td>'
                f'<td>{r.get("duration_ms",0)}мс</td>'
                f'<td class="{"pass" if r["status"]=="PASS" else "fail"}">{r["status"]}</td>'
                f'<td>{_html.escape(((r.get("response_preview") or r.get("error") or "")[:200]))}</td></tr>'
                for r in h.get("results", [])])
            + "</table></details></td></tr>"
        )

    html_content = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><title>API Test Runner — Все группы</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }}
h1 {{ color: #003d4d; }}
.summary {{ font-size: 18px; margin: 10px 0 20px; }}
.pass {{ color: #28a745; font-weight: bold; }}
.fail {{ color: #cc3333; font-weight: bold; }}
.skip {{ color: #888; }}
table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; font-size: 13px; vertical-align: top; }}
th {{ background: #005566; color: white; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
table.inner {{ box-shadow: none; margin-top: 4px; }}
table.inner td {{ padding: 3px 6px; font-size: 12px; }}
</style></head><body>
<h1>API Test Runner — все группы (Swagger /api/docs)</h1>
<p>Начало: {started.strftime("%Y-%m-%d %H:%M:%S")} | Окончание: {finished.strftime("%Y-%m-%d %H:%M:%S")} |
   Длительность: {duration:.0f}с</p>
<p class="summary">Итого: <span class="pass">{passed} PASS</span>,
   <span class="fail">{failed} FAIL</span> из {total} (по {len(history_per_group)} группам)</p>
<table>
  <tr><th>Группа</th><th>Title</th><th>Начало</th><th>Конец</th><th>Длит.</th><th>Результат</th><th>Сценарии</th></tr>
  {''.join(rows)}
</table>
<p style="margin-top:20px;color:#666">Видео: <a href="api_test_video_all_groups.webm">api_test_video_all_groups.webm</a></p>
</body></html>"""
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)


def main():
    print("[SETUP] Restarting PSS...")
    if not restart_pss():
        print("[SETUP] PSS restart failed"); return 1

    print("[SETUP] Connecting to DB...")
    requests.post(f"{BASE_URL}/api/connect", json={
        "server_port": f"http://localhost:{PSS_PORT}",
        "db": "pss_moma_08_07_2025",
        "user": "Administrator", "password": "",
    }, timeout=15)

    groups = get_groups()
    print(f"[SETUP] Groups to run: {groups}")

    started = datetime.datetime.now()
    video_tmp = os.path.join(SCRIPT_DIR, "_video_all_groups")
    if os.path.exists(video_tmp): shutil.rmtree(video_tmp)

    history = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900},
                                  record_video_dir=video_tmp,
                                  record_video_size={"width": 1400, "height": 900})
        page = ctx.new_page()

        page.goto(f"{BASE_URL}/api/docs"); page.wait_for_load_state("domcontentloaded")
        time.sleep(6)  # wait for Swagger UI + plugin to render

        # Make sure all tag sections expanded so we can see them
        try:
            page.evaluate("""() => {
                document.querySelectorAll('.opblock-tag').forEach(t => {
                    if (t.classList.contains('opblock-tag-no-desc')) return;
                    if (!t.parentElement.classList.contains('is-open')) t.click();
                });
            }""")
            time.sleep(2)
        except Exception:
            pass

        for grp in groups:
            print(f"\n[RUN] group={grp}")
            try:
                # Find Run-all button for this group
                btn = page.locator(f".test-runner-row:has-text('Run all ({grp})') button.trp-btn-run").first
                btn.scroll_into_view_if_needed(timeout=5000)
                # Open results details for visibility
                page.evaluate(f"""(grpKey) => {{
                    document.querySelectorAll('.test-runner-row').forEach(row => {{
                        const b = row.querySelector('.trp-btn-run');
                        if (b && b.textContent.includes('('+grpKey+')')) {{
                            const det = row.querySelector('.trp-details-results');
                            if (det) det.open = true;
                        }}
                    }});
                }}""", grp)
                time.sleep(1)
                btn.click(force=True)
                # Wait for «Готово:» text in progress
                done_loc = page.locator(f".test-runner-row:has-text('Run all ({grp})') .trp-progress:has-text('Готово')").first
                done_loc.wait_for(timeout=600000)  # 10 min max per group
                time.sleep(3)  # let viewer see the result
                history[grp] = get_history(grp)
                s = (history[grp] or {}).get("summary", {})
                print(f"  → {s.get('passed',0)}/{s.get('total',0)} PASS, {s.get('failed',0)} FAIL")
            except Exception as e:
                print(f"  ! ERROR: {e}")
                traceback.print_exc()
                history[grp] = get_history(grp)

        time.sleep(3)
        ctx.close(); browser.close()

    # Save video
    videos = glob.glob(os.path.join(video_tmp, "*.webm"))
    if videos:
        shutil.copy2(videos[0], VIDEO_PATH)
        print(f"\n[VIDEO] {VIDEO_PATH} ({os.path.getsize(VIDEO_PATH)//1024} KB)")
    shutil.rmtree(video_tmp, ignore_errors=True)

    finished = datetime.datetime.now()
    write_html(history, started, finished)
    print(f"[REPORT] {REPORT_PATH}")

    total_p = sum((h or {}).get("summary", {}).get("passed", 0) for h in history.values())
    total_f = sum((h or {}).get("summary", {}).get("failed", 0) for h in history.values())
    total_t = sum((h or {}).get("summary", {}).get("total", 0) for h in history.values())
    print(f"\nTOTAL: {total_p}/{total_t} PASS, {total_f} FAIL")
    return 0 if total_f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
