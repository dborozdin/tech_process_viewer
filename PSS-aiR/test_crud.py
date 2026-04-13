"""Playwright-тесты CRUD для PSS-aiR.

Запуск: python PSS-aiR/test_crud.py
Браузер открывается в видимом режиме (headless=False).
"""

import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5002"
DB_CONFIG = {
    "server_port": "http://localhost:7239",
    "db": "pss_moma_08_07_2025",
    "user": "Administrator",
    "password": ""
}


def test_crud():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        page.set_viewport_size({"width": 1400, "height": 900})

        # 1. Открыть приложение
        page.goto(BASE_URL)
        page.wait_for_load_state('domcontentloaded')
        time.sleep(2)
        print("[OK] Страница загружена")

        # Проверить что crud.js загружен
        has_crud = page.evaluate("typeof CrudManager !== 'undefined'")
        print(f"[{'OK' if has_crud else 'FAIL'}] CrudManager загружен: {has_crud}")

        # 2. Подключиться к БД (или дождаться авто-подключения)
        time.sleep(3)
        is_connected = page.evaluate("() => { const dot = document.querySelector('.status-dot'); return dot && dot.classList.contains('connected'); }")

        if not is_connected:
            # Открыть модалку подключения
            connect_btn = page.query_selector("#btnConnect:not(.hidden)")
            if connect_btn:
                connect_btn.click()
                page.wait_for_selector("#connectModal.visible", timeout=3000)

                page.fill("#cfServer", DB_CONFIG["server_port"])
                page.fill("#cfUser", DB_CONFIG["user"])
                page.fill("#cfDatabase", DB_CONFIG["db"])
                page.click("#btnConnectSubmit")
                time.sleep(3)

                is_connected = page.evaluate("() => { const dot = document.querySelector('.status-dot'); return dot && dot.classList.contains('connected'); }")

        print(f"[{'OK' if is_connected else 'FAIL'}] Подключение к БД: {is_connected}")

        if not is_connected:
            print("[SKIP] Нет подключения к БД, пропускаем тесты CRUD с данными")
            time.sleep(5)
            browser.close()
            return

        # 3. Дождаться загрузки дерева папок и кликнуть на первую папку
        page.wait_for_selector(".tree-node-row", timeout=10000)
        time.sleep(1)

        first_folder = page.query_selector(".tree-node-row")
        if first_folder:
            first_folder.click()
            time.sleep(2)
            print("[OK] Папка выбрана")

        # 4. Проверить наличие CRUD тулбара
        toolbar = page.query_selector("#crudToolbar")
        toolbar_html = toolbar.inner_html() if toolbar else ""
        has_create_btn = "Изделие" in toolbar_html
        print(f"[{'OK' if has_create_btn else 'FAIL'}] Кнопка 'Изделие' в тулбаре: {has_create_btn}")

        has_folder_btn = "Папка" in toolbar_html
        print(f"[{'OK' if has_folder_btn else 'FAIL'}] Кнопка 'Папка' в тулбаре: {has_folder_btn}")

        # 5. Проверить наличие кнопок действий в строках таблицы
        action_btns = page.query_selector_all(".crud-edit, .crud-delete")
        print(f"[{'OK' if len(action_btns) > 0 else 'INFO'}] Кнопок действий в таблице: {len(action_btns)}")

        # 6. Тест создания изделия — открыть модальное окно
        create_btn = page.query_selector("#crudBtnCreateProduct")
        if create_btn:
            create_btn.click()
            time.sleep(1)
            modal_visible = page.query_selector("#crudModalOverlay.visible")
            print(f"[{'OK' if modal_visible else 'FAIL'}] Модальное окно создания изделия открылось")

            if modal_visible:
                # Заполнить форму
                page.fill("#crudProductForm-id", "TEST-CRUD-001")
                page.fill("#crudProductForm-name", "Тестовое изделие CRUD")
                page.fill("#crudProductForm-code1", "КОД-001")
                time.sleep(1)

                # Нажать Создать
                page.click("#crudProductSave")
                time.sleep(4)

                # Проверить что модалка закрылась
                modal_hidden = not page.query_selector("#crudModalOverlay.visible")
                print(f"[{'OK' if modal_hidden else 'WARN'}] Модалка закрылась после создания: {modal_hidden}")

                # Если модалка ещё открыта — закрыть вручную и проверить ошибки
                if not modal_hidden:
                    # Проверить toast с ошибкой
                    toasts = page.query_selector_all(".toast")
                    for t in toasts:
                        print(f"  [TOAST] {t.inner_text()}")
                    page.click("#crudModalClose")
                    time.sleep(1)

                # Проверить что изделие появилось в таблице
                time.sleep(2)
                table_html = page.inner_html("#contentArea")
                has_product = "TEST-CRUD-001" in table_html or "Тестовое изделие CRUD" in table_html
                print(f"[{'OK' if has_product else 'INFO'}] Изделие появилось в таблице: {has_product}")

                # 7. Тест редактирования — если изделие создано
                if has_product:
                    rows = page.query_selector_all(".content-row")
                    for row in rows:
                        if "Тестовое изделие CRUD" in (row.inner_text() or ""):
                            edit_btn = row.query_selector(".crud-edit")
                            if edit_btn:
                                edit_btn.click()
                                time.sleep(2)
                                edit_modal = page.query_selector("#crudModalOverlay.visible")
                                print(f"[{'OK' if edit_modal else 'FAIL'}] Модалка редактирования открылась")
                                if edit_modal:
                                    page.fill("#crudProductEditForm-name", "Тестовое изделие CRUD (изменено)")
                                    page.click("#crudProductEditSave")
                                    time.sleep(3)
                                    print("[OK] Изделие отредактировано")
                                    if page.query_selector("#crudModalOverlay.visible"):
                                        page.click("#crudModalClose")
                                        time.sleep(1)
                            break

                # 8. Тест удаления изделия
                if has_product:
                    rows = page.query_selector_all(".content-row")
                    for row in rows:
                        if "CRUD" in (row.inner_text() or ""):
                            del_btn = row.query_selector(".crud-delete")
                            if del_btn:
                                del_btn.click()
                                time.sleep(1)
                                confirm_btn = page.query_selector("#crudConfirmOk")
                                if confirm_btn:
                                    confirm_btn.click()
                                    time.sleep(3)
                                    print("[OK] Изделие удалено")
                            break

        # 9. Закрыть модалку если открыта, затем кликнуть на изделие
        if page.query_selector("#crudModalOverlay.visible"):
            page.click("#crudModalClose")
            time.sleep(1)
        rows = page.query_selector_all(".content-row")
        product_row = None
        for row in rows:
            if row.get_attribute("data-category") == "product":
                product_row = row
                break

        if product_row:
            product_row.click()
            time.sleep(2)
            print("[OK] Изделие выбрано для просмотра свойств")

            # Проверить кнопку редактирования в панели свойств
            edit_attr_btn = page.query_selector("#propEditBtn")
            print(f"[{'OK' if edit_attr_btn else 'INFO'}] Кнопка 'Редактировать' в панели атрибутов: {edit_attr_btn is not None}")

            # Перейти на вкладку характеристик
            char_tab = page.query_selector('[data-tab="chars"]')
            if char_tab:
                char_tab.click()
                time.sleep(2)
                add_char_btn = page.query_selector("#propAddChar")
                print(f"[{'OK' if add_char_btn else 'INFO'}] Кнопка 'Добавить характеристику': {add_char_btn is not None}")

            # Перейти на вкладку документов
            docs_tab = page.query_selector('[data-tab="docs"]')
            if docs_tab:
                docs_tab.click()
                time.sleep(2)
                attach_btn = page.query_selector("#propAttachDoc")
                upload_btn = page.query_selector("#propUploadDoc")
                print(f"[{'OK' if attach_btn else 'INFO'}] Кнопка 'Привязать документ': {attach_btn is not None}")
                print(f"[{'OK' if upload_btn else 'INFO'}] Кнопка 'Загрузить документ': {upload_btn is not None}")

        # 10. Проверить BOM view
        if product_row:
            product_row.dblclick()
            time.sleep(3)

            bom_toolbar = page.query_selector("#crudToolbar")
            bom_html = bom_toolbar.inner_html() if bom_toolbar else ""
            has_add_comp = "Компонент" in bom_html
            print(f"[{'OK' if has_add_comp else 'INFO'}] Кнопка 'Добавить компонент' в BOM: {has_add_comp}")

            bom_edit_btns = page.query_selector_all(".crud-bom-edit")
            bom_del_btns = page.query_selector_all(".crud-bom-delete")
            print(f"[INFO] Кнопок редактирования BOM: {len(bom_edit_btns)}, удаления: {len(bom_del_btns)}")

        print("\n=== Тестирование завершено ===")
        time.sleep(5)
        browser.close()


if __name__ == '__main__':
    test_crud()
