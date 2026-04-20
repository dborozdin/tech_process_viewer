"""API-тесты для справочников PSS-aiR.

Запуск: python PSS-aiR/test_references_api.py
Предполагает, что PSS-aiR запущен на порту 5002 и подключён к БД.
"""

import sys
import requests
import json

BASE_URL = "http://localhost:5002"

def test_endpoint(url, method='GET', data=None, expected_status=200, description=""):
    """Вспомогательная функция для проверки эндпоинта."""
    try:
        if method == 'GET':
            resp = requests.get(url, timeout=10)
        elif method == 'POST':
            resp = requests.post(url, json=data, timeout=10)
        else:
            raise ValueError(f"Unsupported method {method}")

        if resp.status_code != expected_status:
            print(f"  [FAIL] {description}: статус {resp.status_code}, ожидался {expected_status}")
            if resp.text:
                print(f"    Ответ: {resp.text[:200]}")
            return False

        # Проверяем, что ответ JSON
        try:
            resp.json()
        except Exception:
            print(f"  [FAIL] {description}: ответ не JSON")
            print(f"    Ответ: {resp.text[:200]}")
            return False

        print(f"  [OK] {description}")
        return True

    except requests.exceptions.ConnectionError:
        print(f"  [SKIP] {description}: не удалось подключиться к {BASE_URL}. Убедитесь, что PSS-aiR запущен.")
        return None
    except Exception as e:
        print(f"  [ERROR] {description}: {e}")
        return False

def run_tests():
    print("=== API-тесты справочников PSS-aiR ===")
    print(f"Базовый URL: {BASE_URL}")

    # Проверяем, что приложение отвечает
    try:
        requests.get(BASE_URL, timeout=5)
    except requests.exceptions.ConnectionError:
        print("[SKIP] PSS-aiR не запущен. Пропускаем API-тесты.")
        return

    results = []

    # 1. Список систем классификаторов
    ok = test_endpoint(
        f"{BASE_URL}/api/references/classifiers",
        description="GET /api/references/classifiers"
    )
    results.append(("Классификаторы", ok))

    # 2. Список типов справочников
    ok = test_endpoint(
        f"{BASE_URL}/api/references/types",
        description="GET /api/references/types"
    )
    results.append(("Типы справочников", ok))

    # 3. Получение справочника по типу (заглушка)
    ok = test_endpoint(
        f"{BASE_URL}/api/references/list/units",
        description="GET /api/references/list/units (заглушка)"
    )
    results.append(("Справочник единиц измерения", ok))

    # 4. Поиск классификаторов (требует параметр q)
    ok = test_endpoint(
        f"{BASE_URL}/api/references/search?q=test",
        description="GET /api/references/search?q=test"
    )
    results.append(("Поиск классификаторов", ok))

    # 5. Дерево классификатора (требует существующий system_id)
    # Пропускаем, так как нужен реальный ID
    print("  [SKIP] GET /api/references/classifiers/{id}/tree — требуется реальный system_id")

    # 6. Детали уровня классификатора (требует level_id)
    print("  [SKIP] GET /api/references/classifiers/levels/{id} — требуется реальный level_id")

    # Подсчёт результатов
    passed = sum(1 for _, ok in results if ok is True)
    failed = sum(1 for _, ok in results if ok is False)
    skipped = len(results) - passed - failed

    print(f"\nИтого: {passed} PASS, {failed} FAIL, {skipped} SKIP")

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()