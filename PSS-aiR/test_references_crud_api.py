"""API-тесты CRUD операций для справочников PSS-aiR (классификаторы).

Запуск: python PSS-aiR/test_references_crud_api.py
Предполагает, что PSS-aiR запущен на порту 5002 и подключён к БД pss_moma_08_07_2025.
Тесты создают временные системы классификаторов и уровни, затем удаляют их.
"""

import sys
import requests
import json
import time
import uuid

BASE_URL = "http://localhost:5002"

def test_endpoint(url, method='GET', data=None, expected_status=200, description=""):
    """Вспомогательная функция для проверки эндпоинта."""
    try:
        if method == 'GET':
            resp = requests.get(url, timeout=10)
        elif method == 'POST':
            resp = requests.post(url, json=data, timeout=10)
        elif method == 'PUT':
            resp = requests.put(url, json=data, timeout=10)
        elif method == 'DELETE':
            resp = requests.delete(url, timeout=10)
        else:
            raise ValueError(f"Unsupported method {method}")

        if resp.status_code != expected_status:
            print(f"  [FAIL] {description}: статус {resp.status_code}, ожидался {expected_status}")
            if resp.text:
                print(f"    Ответ: {resp.text[:200]}")
            return False, resp

        # Проверяем, что ответ JSON
        try:
            json_data = resp.json()
        except Exception:
            print(f"  [FAIL] {description}: ответ не JSON")
            print(f"    Ответ: {resp.text[:200]}")
            return False, resp

        print(f"  [OK] {description}")
        return True, resp

    except requests.exceptions.ConnectionError:
        print(f"  [SKIP] {description}: не удалось подключиться к {BASE_URL}. Убедитесь, что PSS-aiR запущен.")
        return None, None
    except Exception as e:
        print(f"  [ERROR] {description}: {e}")
        return False, None


def is_connected():
    """Проверить, подключено ли приложение к БД."""
    try:
        resp = requests.get(f"{BASE_URL}/api/status", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get('connected') is True
        return False
    except Exception:
        return False


def run_tests():
    print("=== API-тесты CRUD операций для классификаторов PSS-aiR ===")
    print(f"Базовый URL: {BASE_URL}")
    print(f"Время: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Проверяем, что приложение отвечает
    try:
        requests.get(BASE_URL, timeout=5)
    except requests.exceptions.ConnectionError:
        print("[SKIP] PSS-aiR не запущен. Пропускаем API-тесты.")
        return

    # Проверяем подключение к БД
    if not is_connected():
        print("[INFO] PSS-aiR не подключён к БД. Пытаемся подключиться автоматически...")
        # Попытка автоматического подключения
        connect_data = {
            "server_port": "http://localhost:7239",
            "db": "pss_moma_08_07_2025",
            "user": "Administrator",
            "password": ""
        }
        try:
            resp = requests.post(f"{BASE_URL}/api/connect", json=connect_data, timeout=10)
            if resp.status_code == 200 and resp.json().get('connected'):
                print("[OK] Успешно подключились к БД")
                # Даем время на инициализацию
                time.sleep(1)
                # Проверяем еще раз
                if not is_connected():
                    print("[SKIP] Подключение прошло, но статус не изменился.")
                    return
            else:
                print(f"[SKIP] Не удалось подключиться к БД автоматически. Статус: {resp.status_code}")
                print(f"   Ответ: {resp.text[:200]}")
                return
        except Exception as e:
            print(f"[SKIP] Ошибка при подключении: {e}")
            return

    results = []

    # Генерируем уникальные ID для тестовых данных
    test_system_id = f"TEST_CRUD_{uuid.uuid4().hex[:8].upper()}"
    test_level_id = f"TEST_LEVEL_{uuid.uuid4().hex[:8].upper()}"

    print(f"Используем тестовый ID системы: {test_system_id}")
    print(f"Используем тестовый ID уровня: {test_level_id}")
    print()

    # 1. Создание системы классификаторов
    print("1. Создание системы классификаторов (POST /api/references/classifiers)")
    system_data = {
        "id": test_system_id,
        "name": "Тестовая система классификаторов",
        "description": "Создана автоматическими тестами CRUD API",
        "parent_id": None,
        "default_level_id": None
    }
    ok, resp = test_endpoint(
        f"{BASE_URL}/api/references/classifiers",
        method='POST',
        data=system_data,
        expected_status=200,
        description="POST /api/references/classifiers (создание системы)"
    )
    system_sys_id = None  # Инициализация на случай неудачи
    level_sys_id = None
    if ok is False:
        print("   [WARN] Не удалось создать систему. Возможно, ID уже существует или нет прав записи.")
        print("   Пропускаем последующие тесты CRUD.")
        results.append(("Создание системы классификаторов", ok))
        # Продолжаем другие тесты чтения
    else:
        results.append(("Создание системы классификаторов", ok))
        # Извлекаем sys_id созданной системы
        created_system = resp.json().get('system', {})
        system_sys_id = created_system.get('sys_id')
        if not system_sys_id:
            print("   [WARN] В ответе нет sys_id созданной системы")
            system_sys_id = None
        else:
            print(f"   Создана система с sys_id: {system_sys_id}")

    # 2. Получение списка систем (проверяем, что система появилась)
    print("\n2. Получение списка систем классификаторов")
    ok, resp = test_endpoint(
        f"{BASE_URL}/api/references/classifiers",
        description="GET /api/references/classifiers"
    )
    if ok and system_sys_id:
        # Проверяем, что наша система есть в списке
        data = resp.json()
        systems = data.get('systems', [])
        found = any(s.get('id') == test_system_id for s in systems)
        if found:
            print(f"   [OK] Тестовая система {test_system_id} найдена в списке")
        else:
            print(f"   [WARN] Тестовая система {test_system_id} не найдена в списке")
    results.append(("Получение списка систем", ok))

    # 3. Создание уровня классификатора (если система создана)
    print("\n3. Создание уровня классификатора")
    level_sys_id = None
    if system_sys_id:
        level_data = {
            "system_id": system_sys_id,
            "id": test_level_id,
            "name": "Тестовый уровень классификатора",
            "code": "TEST_CODE",
            "description": "Создан автоматическими тестами",
            "parent_id": None,
            "related_product_id": None
        }
        ok, resp = test_endpoint(
            f"{BASE_URL}/api/references/classifiers/levels",
            method='POST',
            data=level_data,
            expected_status=200,
            description="POST /api/references/classifiers/levels (создание уровня)"
        )
        if ok:
            created_level = resp.json().get('level', {})
            level_sys_id = created_level.get('sys_id')
            if level_sys_id:
                print(f"   Создан уровень с sys_id: {level_sys_id}")
        results.append(("Создание уровня классификатора", ok))
    else:
        print("   [SKIP] Создание уровня: нет system_sys_id")
        results.append(("Создание уровня классификатора", None))

    # 4. Получение дерева классификатора
    print("\n4. Получение дерева классификатора")
    if system_sys_id:
        ok, resp = test_endpoint(
            f"{BASE_URL}/api/references/classifiers/{system_sys_id}/tree",
            description=f"GET /api/references/classifiers/{system_sys_id}/tree"
        )
        if ok:
            data = resp.json()
            tree_system = data.get('system', {})
            if tree_system:
                print(f"   Дерево для системы: {tree_system.get('name')}")
    else:
        ok = test_endpoint(
            f"{BASE_URL}/api/references/classifiers/1/tree",
            expected_status=404,
            description="GET /api/references/classifiers/1/tree (несуществующая система)"
        )[0]
    results.append(("Получение дерева классификатора", ok))

    # 5. Получение деталей уровня классификатора
    print("\n5. Получение деталей уровня классификатора")
    if level_sys_id:
        ok, resp = test_endpoint(
            f"{BASE_URL}/api/references/classifiers/levels/{level_sys_id}",
            description=f"GET /api/references/classifiers/levels/{level_sys_id}"
        )
        if ok:
            data = resp.json()
            level = data.get('level', {})
            if level:
                print(f"   Уровень: {level.get('name')} (код: {level.get('code')})")
    else:
        ok = test_endpoint(
            f"{BASE_URL}/api/references/classifiers/levels/999999",
            expected_status=404,
            description="GET /api/references/classifiers/levels/999999 (несуществующий уровень)"
        )[0]
    results.append(("Получение деталей уровня", ok))

    # 6. Обновление системы классификаторов
    print("\n6. Обновление системы классификаторов")
    if system_sys_id:
        update_data = {
            "name": "Обновленное название системы",
            "description": "Обновлено автоматическими тестами"
        }
        ok, resp = test_endpoint(
            f"{BASE_URL}/api/references/classifiers/{system_sys_id}",
            method='PUT',
            data=update_data,
            expected_status=200,
            description=f"PUT /api/references/classifiers/{system_sys_id} (обновление системы)"
        )
        if ok:
            updated = resp.json().get('system', {})
            if updated.get('name') == update_data['name']:
                print(f"   Система обновлена: {updated.get('name')}")
    else:
        ok = test_endpoint(
            f"{BASE_URL}/api/references/classifiers/999999",
            method='PUT',
            data={"name": "test"},
            expected_status=404,
            description="PUT /api/references/classifiers/999999 (несуществующая система)"
        )[0]
    results.append(("Обновление системы", ok))

    # 7. Обновление уровня классификатора
    print("\n7. Обновление уровня классификатора")
    if level_sys_id:
        update_data = {
            "name": "Обновленное название уровня",
            "code": "UPDATED_CODE"
        }
        ok, resp = test_endpoint(
            f"{BASE_URL}/api/references/classifiers/levels/{level_sys_id}",
            method='PUT',
            data=update_data,
            expected_status=200,
            description=f"PUT /api/references/classifiers/levels/{level_sys_id} (обновление уровня)"
        )
        if ok:
            updated = resp.json().get('level', {})
            if updated.get('code') == update_data['code']:
                print(f"   Уровень обновлен: {updated.get('name')} (код: {updated.get('code')})")
    else:
        ok = test_endpoint(
            f"{BASE_URL}/api/references/classifiers/levels/999999",
            method='PUT',
            data={"name": "test"},
            expected_status=404,
            description="PUT /api/references/classifiers/levels/999999 (несуществующий уровень)"
        )[0]
    results.append(("Обновление уровня", ok))

    # 8. Удаление уровня классификатора
    print("\n8. Удаление уровня классификатора")
    if level_sys_id:
        ok, resp = test_endpoint(
            f"{BASE_URL}/api/references/classifiers/levels/{level_sys_id}",
            method='DELETE',
            expected_status=200,
            description=f"DELETE /api/references/classifiers/levels/{level_sys_id}"
        )
        if ok:
            print(f"   Уровень {level_sys_id} удален")
    else:
        ok = test_endpoint(
            f"{BASE_URL}/api/references/classifiers/levels/999999",
            method='DELETE',
            expected_status=404,
            description="DELETE /api/references/classifiers/levels/999999 (несуществующий уровень)"
        )[0]
    results.append(("Удаление уровня", ok))

    # 9. Удаление системы классификаторов
    print("\n9. Удаление системы классификаторов")
    if system_sys_id:
        ok, resp = test_endpoint(
            f"{BASE_URL}/api/references/classifiers/{system_sys_id}",
            method='DELETE',
            expected_status=200,
            description=f"DELETE /api/references/classifiers/{system_sys_id}"
        )
        if ok:
            print(f"   Система {system_sys_id} удалена")
    else:
        ok = test_endpoint(
            f"{BASE_URL}/api/references/classifiers/999999",
            method='DELETE',
            expected_status=404,
            description="DELETE /api/references/classifiers/999999 (несуществующая система)"
        )[0]
    results.append(("Удаление системы", ok))

    # Подсчёт результатов
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ CRUD API:")

    passed = sum(1 for _, ok in results if ok is True)
    failed = sum(1 for _, ok in results if ok is False)
    skipped = sum(1 for _, ok in results if ok is None)

    for i, (name, ok) in enumerate(results, 1):
        status = "PASS" if ok is True else "FAIL" if ok is False else "SKIP"
        print(f"{i:2}. {name:40} {status}")

    print(f"\nИтого: {passed} PASS, {failed} FAIL, {skipped} SKIP")

    # Генерация HTML отчёта
    generate_html_report(results, passed, failed, skipped)

    if failed > 0:
        sys.exit(1)


def generate_html_report(results, passed, failed, skipped):
    """Генерация HTML отчёта о результатах тестирования."""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Отчёт тестирования CRUD API классификаторов</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .pass {{ color: green; }}
        .fail {{ color: red; }}
        .skip {{ color: orange; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>Отчёт тестирования CRUD API классификаторов PSS-aiR</h1>
    <div class="timestamp">Время тестирования: {timestamp}</div>

    <div class="summary">
        <h2>Сводка</h2>
        <p><strong class="pass">Пройдено: {passed}</strong> |
           <strong class="fail">Провалено: {failed}</strong> |
           <strong class="skip">Пропущено: {skipped}</strong></p>
    </div>

    <h2>Детальные результаты</h2>
    <table>
        <tr>
            <th>#</th>
            <th>Тест</th>
            <th>Статус</th>
            <th>Примечания</th>
        </tr>
"""

    for i, (name, ok) in enumerate(results, 1):
        if ok is True:
            status = "✅ PASS"
            cls = "pass"
            notes = "Успешно"
        elif ok is False:
            status = "❌ FAIL"
            cls = "fail"
            notes = "Тест не пройден"
        else:
            status = "⚠️ SKIP"
            cls = "skip"
            notes = "Тест пропущен (отсутствует подключение к БД или недостаточно данных)"

        html += f"""        <tr>
            <td>{i}</td>
            <td>{name}</td>
            <td class="{cls}">{status}</td>
            <td>{notes}</td>
        </tr>
"""

    html += """    </table>

    <h2>Информация о тестировании</h2>
    <ul>
        <li><strong>API:</strong> Справочники PSS-aiR (классификаторы)</li>
        <li><strong>Базовый URL:</strong> http://localhost:5002</li>
        <li><strong>Тестируемые операции:</strong> CRUD (создание, чтение, обновление, удаление) систем и уровней классификаторов</li>
        <li><strong>Тестовые данные:</strong> Создаются автоматически с уникальными ID, удаляются после тестирования</li>
    </ul>

    <footer>
        <p>Сгенерировано автоматически тестом <code>test_references_crud_api.py</code></p>
    </footer>
</body>
</html>"""

    report_path = "test_crud_report.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nHTML отчёт сохранён в файл: {report_path}")
    print(f"Откройте файл в браузере для просмотра.")


if __name__ == "__main__":
    run_tests()