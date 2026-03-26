"""Хелперы для APL-запросов и метрики производительности.

Используется в: tech_process_viewer_app, PSS-C services.
"""

import time
import threading
from functools import wraps
import requests
from tech_process_viewer.globals import logger


# === Метрики производительности ===

_query_counter = threading.local()


def reset_query_counter():
    """Сбросить счётчик запросов к БД (для текущего потока)."""
    _query_counter.count = 0


def increment_query_counter():
    """Увеличить счётчик запросов к БД на 1."""
    if not hasattr(_query_counter, 'count'):
        _query_counter.count = 0
    _query_counter.count += 1


def get_query_count():
    """Получить текущее значение счётчика запросов."""
    return getattr(_query_counter, 'count', 0)


def track_performance(operation_name):
    """Декоратор: логирует время выполнения и количество запросов к БД.

    Использование:
        @track_performance("get_product_tree")
        def get_product_tree(self, pdf_sys_id):
            ...

    В логе (при LOG_LEVEL=DEBUG):
        [PERF] get_product_tree: 1.234s, 5 DB queries
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            reset_query_counter()
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.perf_counter() - start
                queries = get_query_count()
                logger.debug(
                    f"[PERF] {operation_name}: {elapsed:.3f}s, "
                    f"{queries} DB queries"
                )
        return wrapper
    return decorator


# === APL-запросы ===

def query_apl(api_instance, query, description=None):
    """Выполняет APL-запрос через активное подключение к PSS.

    Args:
        api_instance: Экземпляр DatabaseAPI с активным подключением
        query: Текст APL-запроса (SELECT NO_CASE ...)
        description: Описание запроса для отладки

    Returns:
        dict: JSON-ответ с ключами instances, count_all и др.
    """
    increment_query_counter()

    logger.debug(f'[APL] {description or "query"}: {query[:200]}')

    headers = {
        "X-APL-SessionKey": api_instance.connect_data['session_key'],
        "Content-Type": "application/json",
        "Cookie": f"X-Apl-SessionKey={api_instance.connect_data['session_key']}"
    }
    response = requests.post(
        api_instance.URL_QUERY,
        headers=headers,
        data=query.encode("utf-8")
    )
    response.raise_for_status()
    result = response.json()
    logger.debug(f'[APL] result: count_all={result.get("count_all", "?")}')
    return result


def resolve_org_unit(api_instance, bp_id, res_type_id):
    """Извлекает организационную единицу из ресурса 'Vreme rada' для бизнес-процесса.

    Args:
        api_instance: Экземпляр DatabaseAPI
        bp_id: sys_id бизнес-процесса
        res_type_id: sys_id типа ресурса "Vreme rada"

    Returns:
        str: ID организационной единицы или пустая строка
    """
    if not res_type_id:
        return ""

    resource_id = api_instance.resources_api.find_resource_by_bp_and_type(bp_id, res_type_id)
    if not resource_id:
        return ""

    resource_data = api_instance.resources_api.find_resource_data_by_id(resource_id)
    if not resource_data or 'instances' not in resource_data or not resource_data['instances']:
        return ""

    res_attrs = resource_data['instances'][0]['attributes']
    org_obj = res_attrs.get("object")
    if not isinstance(org_obj, dict) or 'id' not in org_obj:
        return ""

    org_data = api_instance.org_api.find_organization_data_by_sys_id(org_obj['id'])
    if not org_data or 'instances' not in org_data or not org_data['instances']:
        return ""

    return org_data['instances'][0]['attributes'].get("id", "")


def batch_query_by_ids(api_instance, sys_ids, description=None):
    """Batch-запрос: получить экземпляры по списку sys_id одним запросом.

    Args:
        api_instance: Экземпляр DatabaseAPI
        sys_ids: Список sys_id для загрузки
        description: Описание для отладки

    Returns:
        list: Список instances из ответа
    """
    if not sys_ids:
        return []

    ids_str = ", ".join(f"#{sid}" for sid in sys_ids)
    query = f"""SELECT NO_CASE
    Ext_
    FROM
    Ext_{{{ids_str}}}
    END_SELECT"""
    result = query_apl(api_instance, query, description=description or f"batch query {len(sys_ids)} items")
    return result.get("instances", [])
