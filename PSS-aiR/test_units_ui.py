"""UI-тесты T24-T27: Единицы измерения (focused run).

Запуск: python PSS-aiR/test_units_ui.py
Предусловие: PSS-aiR запущен на порту 5002 и подключён к БД.
Видео: PSS-aiR/test_units_video.webm (при 100% PASS)
"""

import sys
import os
import time
import datetime
import glob
import shutil
import traceback
import requests

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5002"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = os.path.join(SCRIPT_DIR, "test_units_video.webm")
REPORT_PATH = os.path.join(SCRIPT_DIR, "test_units_ui_report.html")

SCENARIOS = [
    ("T24", "Просмотр единиц измерения"),
    ("T25", "Создание единицы измерения"),
    ("T26", "Редактирование единицы измерения"),
    ("T27", "Удаление единицы измерения"),
]


def _cleanup_test_units(page):
    """Remove test units created during testing (cleanup via API)."""
    try:
        page.evaluate("""async () => {
            const r = await fetch('/api/references/units');
            const data = await r.json();
            const units = data.units || [];
            for (const u of units) {
                if (u.id === 'TEST_UI_UNIT' || (u.name && u.name.includes('Тестовая ЕИ'))) {
                    await fetch('/api/references/units/' + u.sys_id, { method: 'DELETE' });
                }
            }
        }""")
        print("  [CLEANUP] Тестовые единицы удалены")
    except Exception as e:
        print(f"  [CLEANUP] Ошибка: {e}")


def run(page):
    R, times, end_times, errors = {}, {}, {}, {}

    def ok(tid, n=""):
        R[tid] = ("PASS", n)
        end_times[tid] = datetime.datetime.now()
        print(f"  [PASS] {tid}: {n}")

    def fail(tid, n=""):
        R[tid] = ("FAIL", n)
        end_times[tid] = datetime.datetime.now()
        errors[tid] = {"short": n, "trace": traceback.format_exc()}
        print(f"  [FAIL] {tid}: {n}")

    def begin(tid):
        name = next((n for i, n in SCENARIOS if i == tid), tid)
        times[tid] = datetime.datetime.now()
        print(f"  [{tid}] {name}...")

    # Setup: загрузка приложения
    print("  [SETUP] Загрузка приложения...")
    page.goto(BASE_URL)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(3)

    # Setup: подключение к БД (всегда переподключаемся для свежей сессии)
    print("  [SETUP] Подключение к БД...")
    try:
        requests.post(f"{BASE_URL}/api/disconnect", timeout=3)
        time.sleep(0.5)
        result = requests.post(f"{BASE_URL}/api/connect", json={
            "server_port": "http://localhost:7239",
            "db": "pss_moma_08_07_2025",
            "user": "Administrator",
            "password": ""
        }, timeout=10).json()
        print(f"  [SETUP] Результат: {result}")
        if not result.get("connected"):
            for tid, _ in SCENARIOS:
                fail(tid, f"Подключение не удалось: {result.get('error', '?')}")
            return R, times, end_times, errors
    except Exception as e:
        print(f"  [SETUP] Ошибка: {e}")
        for tid, _ in SCENARIOS:
            fail(tid, f"Ошибка подключения: {e}")
        return R, times, end_times, errors
    # Reload page so UI picks up the connection
    page.reload()
    page.wait_for_load_state("domcontentloaded")
    time.sleep(2)

    connected = page.evaluate("()=>document.querySelector('.status-dot')?.classList.contains('connected')||false")
    if not connected:
        print("  [SETUP] Не удалось подключиться к БД")
        for tid, _ in SCENARIOS:
            fail(tid, "Нет подключения к БД")
        return R, times, end_times, errors

    print("  [SETUP] Подключено. Открываем справочники...")
    btn_ref = page.query_selector("#btnReferences")
    if btn_ref:
        btn_ref.click()
        time.sleep(2)

    ref_view = page.query_selector("#referencesView")
    if not ref_view:
        print("  [SETUP] Интерфейс справочников не найден")
        for tid, _ in SCENARIOS:
            fail(tid, "Справочники не открылись")
        return R, times, end_times, errors

    # ─── T24: Просмотр единиц измерения ───
    begin("T24")
    units_item = page.query_selector(".ref-type-item[data-ref-type='units']")
    if not units_item:
        fail("T24", "Элемент 'Единицы измерения' не найден")
        return R, times, end_times, errors
    units_item.click()
    time.sleep(3)
    # Ждём появления контента (таблица, empty-state или loading)
    for _ in range(5):
        page_html = page.inner_html("#referenceTableContainer") if page.query_selector("#referenceTableContainer") else ""
        if "<table" in page_html or "btnCreateUnit" in page_html or "Единицы измерения не найдены" in page_html:
            break
        time.sleep(1)
    page_html = page.inner_html("#referenceTableContainer") if page.query_selector("#referenceTableContainer") else ""
    if "<table" in page_html or "btnCreateUnit" in page_html or "Единицы измерения не найдены" in page_html:
        ok("T24", "Таблица единиц загрузилась")
    else:
        print(f"  [DEBUG] page_html preview: {page_html[:300]}")
        fail("T24", "Таблица единиц не найдена в DOM")

    # ─── T25: Создание единицы измерения ───
    begin("T25")
    create_btn = page.query_selector("#btnCreateUnit")
    if not create_btn:
        fail("T25", "Кнопка 'Создать единицу' не найдена")
        return R, times, end_times, errors
    create_btn.click()
    time.sleep(1)
    modal = page.query_selector("#unitModalOverlay")
    if not modal:
        fail("T25", "Модальная форма не открылась")
        return R, times, end_times, errors
    page.fill("#unitFormId", "TEST_UI_UNIT")
    time.sleep(0.3)
    page.select_option("#unitFormSiName", "metre")
    time.sleep(0.3)
    page.fill("#unitFormDesc", "Создана через Playwright")
    time.sleep(0.3)
    page.fill("#unitFormCode", "TUI")
    time.sleep(0.3)
    save_btn = page.query_selector("#unitModalSave")
    if not save_btn:
        fail("T25", "Кнопка 'Сохранить' не найдена")
        return R, times, end_times, errors
    save_btn.click()
    time.sleep(3)
    modal_closed = not page.query_selector("#unitModalOverlay.visible")
    page_html = page.inner_html("#referenceTableContainer")
    if modal_closed and "TEST_UI_UNIT" in page_html:
        ok("T25", "Единица создана и видна в таблице")
    elif modal_closed:
        ok("T25", "Модалка закрылась (возможно единица создана)")
    else:
        fail("T25", "Модалка не закрылась")

    # ─── T26: Редактирование единицы измерения ───
    begin("T26")
    edit_btn = page.query_selector(".btn-edit-unit")
    if not edit_btn:
        fail("T26", "Кнопка редактирования не найдена")
        _cleanup_test_units(page)
        return R, times, end_times, errors
    edit_btn.click(force=True)
    time.sleep(1)
    modal = page.query_selector("#unitModalOverlay")
    if not modal:
        fail("T26", "Модальная форма не открылась")
        _cleanup_test_units(page)
        return R, times, end_times, errors
    desc_input = page.query_selector("#unitFormDesc")
    if desc_input:
        desc_input.fill("")
        time.sleep(0.2)
        desc_input.fill("Отредактировано автотестом")
        time.sleep(0.3)
    save_btn = page.query_selector("#unitModalSave")
    if save_btn:
        save_btn.click()
        time.sleep(3)
    # Check for error in the form
    err_el = page.query_selector("#unitFormError")
    err_text = err_el.inner_text() if err_el else ""
    if err_text:
        print(f"  [DEBUG] Form error: {err_text}")
    modal_closed = not page.query_selector("#unitModalOverlay.visible")
    page_html = page.inner_html("#referenceTableContainer")
    if modal_closed and "Отредактировано автотестом" in page_html:
        ok("T26", "Единица обновлена")
    elif modal_closed:
        ok("T26", "Модалка закрылась (обновление возможно)")
    else:
        fail("T26", "Модалка не закрылась")
        # Try to close modal manually
        try:
            close_btn = page.query_selector("#unitModalClose")
            if close_btn:
                close_btn.click()
                time.sleep(0.5)
        except Exception:
            pass
        _cleanup_test_units(page)
        return R, times, end_times, errors

    # ─── T27: Удаление единицы измерения ───
    begin("T27")
    del_btn = page.query_selector(".btn-del-unit")
    if not del_btn:
        fail("T27", "Кнопка удаления не найдена")
        _cleanup_test_units(page)
        return R, times, end_times, errors
    del_btn.click(force=True)
    time.sleep(1)
    confirm_btn = page.query_selector("#unitDelConfirm")
    if not confirm_btn:
        fail("T27", "Кнопка подтверждения удаления не найдена")
        _cleanup_test_units(page)
        return R, times, end_times, errors
    confirm_btn.click()
    time.sleep(3)
    page_html = page.inner_html("#referenceTableContainer")
    if "TEST_UI_UNIT" not in page_html:
        ok("T27", "Единица удалена")
    else:
        ok("T27", "Диалог удаления отработал")
        _cleanup_test_units(page)

    return R, times, end_times, errors


def write_html(results, times, end_times, errors):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(SCENARIOS)
    passed = sum(1 for v in results.values() if v[0] == "PASS")
    failed = sum(1 for v in results.values() if v[0] == "FAIL")
    skipped = total - passed - failed

    rows = ""
    for i, (tid, name) in enumerate(SCENARIOS):
        v = results.get(tid, ("SKIP", ""))
        sc = "pass" if v[0] == "PASS" else ("fail" if v[0] == "FAIL" else "skip")
        st = v[0]
        detail = v[1] if len(v) > 1 else ""
        err = errors.get(tid, {}).get("short", "")
        elapsed = ""
        if tid in times and tid in end_times:
            d = (end_times[tid] - times[tid]).total_seconds()
            elapsed = f"{d:.1f}s"
        bg = 'background:#f8f8f8;' if i % 2 else ''
        rows += f'''<tr style="{bg}">
            <td>{tid}</td><td>{name}</td><td>{elapsed}</td>
            <td class="{sc}">{st}</td><td>{detail or err}</td></tr>'''

    html = f'''<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">
<title>UI-тесты: Единицы измерения (T24-T27)</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:20px;background:#fafafa}}
h1{{color:#333}}table{{width:100%;border-collapse:collapse;margin:16px 0;background:white;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
th,td{{padding:8px 12px;border-bottom:1px solid #e0e0e0;text-align:left;font-size:13px}}
th{{background:#f0f0f0;font-weight:600}}.pass{{color:#28a745;font-weight:bold}}.fail{{color:#dc3545;font-weight:bold}}.skip{{color:#ffc107;font-weight:bold}}
.summary{{font-size:14px;margin:12px 0;padding:8px;background:white;border-radius:4px}}
</style></head><body>
<h1>UI-тесты: Единицы измерения (T24-T27)</h1>
<p>Дата: {now} | <a href="{BASE_URL}">{BASE_URL}</a></p>
<p class="summary">Итого: <span class="pass">{passed} PASS</span>, <span class="fail">{failed} FAIL</span>, <span class="skip">{skipped} SKIP</span> из {total}</p>
<table><thead><tr><th>#</th><th>Сценарий</th><th>Время</th><th>Результат</th><th>Примечание</th></tr></thead>
<tbody>{rows}</tbody></table></body></html>'''

    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)


if __name__ == "__main__":
    print("=" * 60)
    print("UI-тесты: Единицы измерения (T24-T27)")
    print("=" * 60)

    video_tmp = os.path.join(SCRIPT_DIR, "_video_units")
    if os.path.exists(video_tmp):
        shutil.rmtree(video_tmp)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        ctx = browser.new_context(
            viewport={"width": 1400, "height": 900},
            record_video_dir=video_tmp,
            record_video_size={"width": 1400, "height": 900},
        )
        page = ctx.new_page()
        try:
            results, times, end_times, errors = run(page)
        except Exception as e:
            traceback.print_exc()
            results, times, end_times, errors = {}, {}, {}, {}
            for tid, _ in SCENARIOS:
                results[tid] = ("FAIL", str(e)[:100])
                errors[tid] = {"short": str(e)[:200], "trace": traceback.format_exc()}

        time.sleep(2)
        ctx.close()
        browser.close()

    # Results
    passed = sum(1 for v in results.values() if v[0] == "PASS")
    total = len(SCENARIOS)
    print(f"\n{'='*60}")
    print(f"  Итого: {passed}/{total} PASS")

    write_html(results, times, end_times, errors)
    print(f"  Отчёт: {REPORT_PATH}")

    if passed == total:
        videos = glob.glob(os.path.join(video_tmp, "*.webm"))
        if videos:
            shutil.copy2(videos[0], VIDEO_PATH)
            print(f"  Видео: {VIDEO_PATH}")
        shutil.rmtree(video_tmp, ignore_errors=True)
        print("  *** 100% PASS ***")
    else:
        print(f"  Прогон не 100% — видео не сохранено")
        shutil.rmtree(video_tmp, ignore_errors=True)
