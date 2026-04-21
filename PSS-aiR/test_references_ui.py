"""UI-тестирование раздела 'Справочники' PSS-aiR (Playwright).

Запуск: python PSS-aiR/test_references_ui.py
Требования: PSS-aiR на порту 5002 + подключение к БД pss_moma_08_07_2025.

Тест проверяет:
1. Кнопка 'Справочники' в заголовке;
2. Открытие интерфейса справочников (#referencesView виден);
3. Загрузка левой панели типов справочников;
4. Загрузка дерева систем классификаторов;
5. Раскрытие системы (ленивая загрузка корневых уровней);
6. Раскрытие уровня (ленивая загрузка дочерних уровней);
7. Показ деталей при клике на уровень;
8. Переключение на справочник-заглушку.
"""

import sys
import time
import requests
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5002"


def ensure_connected():
    """Убеждаемся, что PSS-aiR подключён к БД."""
    try:
        r = requests.get(f"{BASE_URL}/api/status", timeout=5).json()
        if r.get("connected"):
            return True
    except Exception:
        return False
    # Подключаемся
    try:
        r = requests.post(
            f"{BASE_URL}/api/connect",
            json={
                "server_port": "http://localhost:7239",
                "db": "pss_moma_08_07_2025",
                "user": "Administrator",
                "password": "",
            },
            timeout=10,
        )
        return r.json().get("connected") is True
    except Exception:
        return False


def run():
    print("=== UI-тестирование раздела 'Справочники' ===")

    if not ensure_connected():
        print("[FAIL] Не удалось подключить PSS-aiR к БД. Проверьте PSS-сервер и PSS-aiR.")
        return False

    results = []

    def log(step, status, info=""):
        mark = {"PASS": "[OK]", "FAIL": "[FAIL]", "WARN": "[WARN]"}.get(status, "[--]")
        line = f"{mark} {step}" + (f" — {info}" if info else "")
        print(line)
        results.append((step, status, info))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=400)
        ctx = browser.new_context()
        page = ctx.new_page()

        # Логируем ошибки консоли и JS-exceptions
        def _on_console(msg):
            if msg.type in ("error", "warning"):
                print(f"[BROWSER {msg.type}]", msg.text)
        page.on("console", _on_console)
        page.on("pageerror", lambda err: print(f"[BROWSER PAGEERROR]", err))

        try:
            page.goto(BASE_URL, timeout=15000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

            # Закрываем модалку подключения, если она открыта (статус уже connected,
            # но модалка может появиться из-за автологина при reload)
            modal = page.query_selector("#connectModal.visible")
            if modal:
                close_btn = page.query_selector("#connectModalClose, #btnConnectCancel")
                if close_btn:
                    close_btn.click()
                    time.sleep(0.5)

            # 1) Кнопка 'Справочники'
            btn = page.query_selector("#btnReferences")
            if not btn:
                log("1. Кнопка 'Справочники'", "FAIL", "id=btnReferences не найден")
                return False
            log("1. Кнопка 'Справочники'", "PASS")

            btn.click()
            time.sleep(1)

            # 2) Интерфейс открыт
            view = page.query_selector("#referencesView")
            cls = view.get_attribute("class") or ""
            if "hidden" in cls:
                log("2. Открытие интерфейса", "FAIL", "referencesView остался hidden")
                return False
            log("2. Открытие интерфейса", "PASS")

            # 3) Типы справочников загружены (минимум 3)
            page.wait_for_selector(".ref-type-item", timeout=5000)
            items = page.query_selector_all(".ref-type-item")
            if len(items) < 3:
                log("3. Типы справочников", "FAIL", f"только {len(items)} элементов")
            else:
                log("3. Типы справочников", "PASS", f"{len(items)} элементов")

            # Активен classifiers
            active = page.query_selector(".ref-type-item.active[data-ref-type='classifiers']")
            if not active:
                log("3.1 Классификаторы активны", "FAIL")
            else:
                log("3.1 Классификаторы активны", "PASS")

            # 4) Дерево систем классификаторов загружено
            page.wait_for_selector(".ref-tree .tree-node-row[data-kind='system']", timeout=10000)
            systems = page.query_selector_all(".ref-tree .tree-node-row[data-kind='system']")
            if not systems:
                log("4. Дерево классификаторов", "FAIL", "нет систем")
                return False
            log("4. Дерево классификаторов", "PASS", f"{len(systems)} систем")

            # 5) Выбор системы MOMA (sys_id=4698) — клик по строке выбирает + авто-раскрывает
            moma = page.query_selector(".tree-node-row[data-kind='system'][data-sys-id='4698']")
            if not moma:
                moma = systems[0]
            sys_id = moma.get_attribute("data-sys-id")
            moma.click()
            time.sleep(1)
            details_title = page.query_selector("#referenceDetailsPanel .details-title")
            if details_title:
                log("5. Выбор системы (детали показаны)", "PASS")
            else:
                log("5. Выбор системы (детали показаны)", "WARN", "details не отрисованы")

            # 6) После клика должна быть ленивая загрузка корневых уровней
            root_levels = []
            # Дожидаемся появления узлов уровней в DOM (не обязательно visible)
            try:
                page.wait_for_function(
                    f"document.querySelectorAll(\"[data-children-of='{sys_id}'] .tree-node[data-kind='level']\").length > 0",
                    timeout=20000,
                )
                root_levels = page.query_selector_all(
                    f"[data-children-of='{sys_id}'] > .tree-node[data-kind='level']"
                )
                log("6. Раскрытие системы (lazy load)", "PASS", f"{len(root_levels)} корневых уровней")
            except Exception as e:
                log("6. Раскрытие системы (lazy load)", "FAIL", str(e)[:80])

            # 7) Раскрытие первого корневого уровня через locator (стабильнее)
            if root_levels:
                selector = (
                    f"[data-children-of='{sys_id}'] > .tree-node[data-kind='level']:first-child > .tree-node-row"
                )
                first_level_row_loc = page.locator(selector)
                # Клик — выбор уровня + авто-раскрытие
                first_level_row_loc.click()
                level_id = first_level_row_loc.get_attribute("data-level-id")
                try:
                    page.wait_for_function(
                        f"document.querySelectorAll(\"[data-children-of='{level_id}'] .tree-node[data-kind='level'], "
                        f"[data-children-of='{level_id}'] .tree-empty-child\").length > 0",
                        timeout=20000,
                    )
                    log("7. Раскрытие уровня (lazy load)", "PASS")
                except Exception as e:
                    log("7. Раскрытие уровня (lazy load)", "FAIL", str(e)[:80])

                # 8) Детали уровня показаны после клика
                time.sleep(1)
                details_table = page.query_selector("#referenceDetailsPanel .details-table")
                if details_table:
                    log("8. Детали уровня показаны", "PASS")
                else:
                    log("8. Детали уровня показаны", "FAIL")
            else:
                log("7-8. Тесты уровня", "WARN", "нет уровней для теста")

            # 9) Переключение на заглушку 'Единицы измерения'
            units = page.query_selector(".ref-type-item[data-ref-type='units']")
            if units:
                units.click()
                time.sleep(1)
                table = page.query_selector("#referenceTableContainer")
                tcls = (table.get_attribute("class") or "") if table else "hidden"
                if "hidden" not in tcls:
                    placeholder = page.query_selector("#referenceTableContainer .empty-state-text")
                    ptext = placeholder.inner_text() if placeholder else ""
                    if "разработке" in ptext.lower():
                        log("9. Заглушка для 'Единицы измерения'", "PASS")
                    else:
                        log("9. Заглушка для 'Единицы измерения'", "WARN", "текст без слова 'разработке'")
                else:
                    log("9. Заглушка для 'Единицы измерения'", "FAIL", "табличный контейнер скрыт")
            else:
                log("9. Заглушка для 'Единицы измерения'", "FAIL", "элемент не найден")

            # 10) Возврат к основной панели
            page.query_selector("#btnBackToMain").click()
            time.sleep(1)
            view_cls = page.query_selector("#referencesView").get_attribute("class") or ""
            if "hidden" in view_cls:
                log("10. Возврат в основной интерфейс", "PASS")
            else:
                log("10. Возврат в основной интерфейс", "FAIL")

            print("\n=== Итоги ===")
            passed = sum(1 for _, s, _ in results if s == "PASS")
            failed = sum(1 for _, s, _ in results if s == "FAIL")
            warned = sum(1 for _, s, _ in results if s == "WARN")
            print(f"PASS: {passed}, FAIL: {failed}, WARN: {warned}")
            return failed == 0
        finally:
            # Оставляем браузер открытым на короткое время для визуальной проверки
            time.sleep(3)
            browser.close()


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
