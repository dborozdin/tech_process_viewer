"""API-тесты для единиц измерения PSS-aiR.

Запуск: python PSS-aiR/test_units_api.py
Результат: PSS-aiR/test_units_report.html

Предполагает, что PSS-aiR запущен на порту 5002 и подключён к БД.
"""

import sys
import os
import time
import datetime
import requests
import json
import traceback

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE_URL = "http://localhost:5002"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(SCRIPT_DIR, "test_units_report.html")


def test_endpoint(url, method='GET', data=None, expected_status=200, description=""):
    start = time.perf_counter()
    try:
        if method == 'GET':
            resp = requests.get(url, timeout=15)
        elif method == 'POST':
            resp = requests.post(url, json=data, timeout=15)
        elif method == 'PUT':
            resp = requests.put(url, json=data, timeout=15)
        elif method == 'DELETE':
            resp = requests.delete(url, timeout=15)
        else:
            raise ValueError(f"Unsupported method {method}")

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        if resp.status_code != expected_status:
            detail = resp.text[:300] if resp.text else ''
            return {
                'passed': False, 'status': resp.status_code,
                'detail': f"Ожидался {expected_status}, получен {resp.status_code}. {detail}",
                'elapsed_ms': elapsed_ms,
            }

        try:
            body = resp.json()
        except Exception:
            return {
                'passed': False, 'status': resp.status_code,
                'detail': "Ответ не JSON",
                'elapsed_ms': elapsed_ms,
            }

        return {
            'passed': True, 'status': resp.status_code,
            'body': body, 'elapsed_ms': elapsed_ms,
        }

    except requests.exceptions.ConnectionError:
        return {
            'passed': None, 'status': 0,
            'detail': f"Не удалось подключиться к {BASE_URL}",
            'elapsed_ms': 0,
        }
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            'passed': False, 'status': 0,
            'detail': str(e), 'elapsed_ms': elapsed_ms,
        }


def run_tests():
    print("=" * 60)
    print("API-тесты: Единицы измерения")
    print("=" * 60)

    # Проверяем доступность
    try:
        requests.get(BASE_URL, timeout=5)
    except requests.exceptions.ConnectionError:
        print("[SKIP] PSS-aiR не запущен. Запустите: python PSS-aiR/app.py")
        return

    results = []
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ─── T1: Список единиц ───
    r = test_endpoint(
        f"{BASE_URL}/api/references/units",
        description="GET /api/references/units"
    )
    results.append(("T1", "Список единиц измерения", ts, r))
    print(f"  T1 Список единиц: {'PASS' if r['passed'] else 'FAIL'} ({r.get('elapsed_ms', 0)} мс)")

    initial_count = 0
    if r['passed']:
        initial_count = len(r.get('body', {}).get('units', []))
        print(f"    Найдено единиц: {initial_count}")

    # ─── T2: Создание единицы ───
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    test_id = f"TEST_UNIT_{int(time.time())}"
    create_data = {
        "id": test_id,
        "name": "Тестовая единица",
        "description": "Создана автотестом",
        "code": "TST",
        "subtype": "si_unit",
    }
    r = test_endpoint(
        f"{BASE_URL}/api/references/units",
        method='POST', data=create_data,
        description="POST /api/references/units"
    )
    results.append(("T2", "Создание единицы", ts, r))
    print(f"  T2 Создание: {'PASS' if r['passed'] else 'FAIL'} ({r.get('elapsed_ms', 0)} мс)")

    created_sys_id = None
    if r['passed']:
        unit = r.get('body', {}).get('unit', {})
        created_sys_id = unit.get('sys_id')
        print(f"    Создана единица sys_id={created_sys_id}")

    # ─── T3: Получение единицы ───
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if created_sys_id:
        r = test_endpoint(
            f"{BASE_URL}/api/references/units/{created_sys_id}",
            description=f"GET /api/references/units/{created_sys_id}"
        )
        results.append(("T3", "Получение созданной единицы", ts, r))
        print(f"  T3 Получение: {'PASS' if r['passed'] else 'FAIL'} ({r.get('elapsed_ms', 0)} мс)")
    else:
        results.append(("T3", "Получение созданной единицы", ts,
                        {'passed': False, 'status': 0, 'detail': 'Нет sys_id для проверки', 'elapsed_ms': 0}))
        print("  T3 Получение: SKIP (нет sys_id)")

    # ─── T4: Обновление единицы ───
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if created_sys_id:
        r = test_endpoint(
            f"{BASE_URL}/api/references/units/{created_sys_id}",
            method='PUT', data={"name": "Тестовая единица (обновлено)", "description": "Обновлено автотестом"},
            description=f"PUT /api/references/units/{created_sys_id}"
        )
        results.append(("T4", "Обновление единицы", ts, r))
        print(f"  T4 Обновление: {'PASS' if r['passed'] else 'FAIL'} ({r.get('elapsed_ms', 0)} мс)")
    else:
        results.append(("T4", "Обновление единицы", ts,
                        {'passed': False, 'status': 0, 'detail': 'Нет sys_id', 'elapsed_ms': 0}))
        print("  T4 Обновление: SKIP")

    # ─── T5: Проверка списка после создания ───
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    r = test_endpoint(
        f"{BASE_URL}/api/references/units",
        description="GET /api/references/units (после создания)"
    )
    if r['passed']:
        new_count = len(r.get('body', {}).get('units', []))
        detail = f"Было: {initial_count}, стало: {new_count}"
        ok = new_count > initial_count
        r['passed'] = ok
        r['detail'] = detail if not ok else ''
    results.append(("T5", "Список после создания", ts, r))
    print(f"  T5 Список после создания: {'PASS' if r['passed'] else 'FAIL'} ({r.get('elapsed_ms', 0)} мс)")

    # ─── T6: Удаление единицы ───
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if created_sys_id:
        r = test_endpoint(
            f"{BASE_URL}/api/references/units/{created_sys_id}",
            method='DELETE',
            description=f"DELETE /api/references/units/{created_sys_id}"
        )
        results.append(("T6", "Удаление единицы", ts, r))
        print(f"  T6 Удаление: {'PASS' if r['passed'] else 'FAIL'} ({r.get('elapsed_ms', 0)} мс)")
    else:
        results.append(("T6", "Удаление единицы", ts,
                        {'passed': False, 'status': 0, 'detail': 'Нет sys_id', 'elapsed_ms': 0}))
        print("  T6 Удаление: SKIP")

    # ─── Итоги ───
    passed = sum(1 for _, _, _, r in results if r['passed'] is True)
    failed = sum(1 for _, _, _, r in results if r['passed'] is False)
    skipped = sum(1 for _, _, _, r in results if r['passed'] is None)
    total = len(results)

    print(f"\nИтого: {passed} PASS, {failed} FAIL, {skipped} SKIP из {total}")

    # Генерация HTML
    generate_html_report(results, passed, failed, skipped, total)
    print(f"Отчёт: {REPORT_PATH}")


def generate_html_report(results, passed, failed, skipped, total):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    status_class = lambda p: 'pass' if p is True else ('fail' if p is False else 'skip')
    status_text = lambda p: 'PASS' if p is True else ('FAIL' if p is False else 'SKIP')

    rows = ''
    for tid, desc, ts, r in results:
        sc = status_class(r['passed'])
        st = status_text(r['passed'])
        detail = r.get('detail', '')
        row_bg = 'background:#f8f8f8;' if results.index((tid, desc, ts, r)) % 2 else ''
        rows += f'''
        <tr style="{row_bg}">
            <td>{tid}</td>
            <td>{desc}</td>
            <td>{r.get('status', '-')}</td>
            <td>{r.get('elapsed_ms', 0)}</td>
            <td class="{sc}">{st}</td>
            <td>{detail}</td>
        </tr>'''

    html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>API-тесты: Единицы измерения</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 20px; background: #fafafa; }}
h1 {{ color: #333; }}
table {{ width: 100%; border-collapse: collapse; margin: 16px 0; background: white; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
th, td {{ padding: 8px 12px; border-bottom: 1px solid #e0e0e0; text-align: left; font-size: 13px; }}
th {{ background: #f0f0f0; font-weight: 600; }}
.pass {{ color: #28a745; font-weight: bold; }}
.fail {{ color: #dc3545; font-weight: bold; }}
.skip {{ color: #ffc107; font-weight: bold; }}
.summary {{ font-size: 14px; margin: 12px 0; padding: 8px; background: white; border-radius: 4px; }}
</style>
</head>
<body>
<h1>API-тесты: Единицы измерения</h1>
<p>Дата: {now} | Базовый URL: {BASE_URL}</p>
<p class="summary">Итого: <span class="pass">{passed} PASS</span>, <span class="fail">{failed} FAIL</span>, <span class="skip">{skipped} SKIP</span> из {total}</p>
<table>
<thead><tr><th>#</th><th>Описание</th><th>HTTP</th><th>мс</th><th>Результат</th><th>Примечание</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</body></html>'''

    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)


if __name__ == '__main__':
    run_tests()
