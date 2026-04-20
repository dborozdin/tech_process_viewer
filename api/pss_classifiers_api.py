"""API для работы с классификаторами PSS (apl_classifier_system, apl_classifier_level).

Реализует ленивую загрузку: уровни иерархии загружаются по запросу (parent → children).
Используется в PSS-aiR и MCP сервере.
"""

import json
import requests
from typing import List, Dict, Any, Optional

from .query_helpers import query_apl


def _ref_id(attr_value: Any) -> Optional[int]:
    """Извлечь sys_id из ссылочного атрибута PSS ({"id": N, "type": "..."})."""
    if isinstance(attr_value, dict):
        return attr_value.get('id')
    return None


def _map_system(inst: Dict[str, Any]) -> Dict[str, Any]:
    """Преобразовать raw-instance apl_classifier_system → dict для API."""
    attrs = inst.get('attributes', {})
    return {
        'sys_id': inst.get('id'),
        'id': attrs.get('id'),
        'name': attrs.get('name'),
        'description': attrs.get('description') or '',
        'parent_id': _ref_id(attrs.get('parent')),
        'default_level_id': _ref_id(attrs.get('default_level')),
        'can_store_object': attrs.get('can_store_object', False),
        'stored_entity': attrs.get('stored_entity') or '',
        'is_multi_object': attrs.get('is_multi_object', False),
        'inner_label': attrs.get('inner_label') or '',
    }


def _map_level(inst: Dict[str, Any]) -> Dict[str, Any]:
    """Преобразовать raw-instance apl_classifier_level → dict для API."""
    attrs = inst.get('attributes', {})
    return {
        'sys_id': inst.get('id'),
        'id': attrs.get('id'),
        'name': attrs.get('name'),
        'code': attrs.get('code') or '',
        'description': attrs.get('description') or '',
        'system_id': _ref_id(attrs.get('system')),
        'parent_id': _ref_id(attrs.get('parent')),
        'related_product_id': _ref_id(attrs.get('related_pdf')),
        'section_type': attrs.get('section_type') or '',
        'name_eng': attrs.get('name_eng') or '',
        'okpd_code': attrs.get('okpd_code') or '',
        'is_system_level': attrs.get('is_system_level', False),
        'only_construction': attrs.get('only_construction', False),
        'wiring': attrs.get('wiring', False),
        'wiring_near_controls': attrs.get('wiring_near_controls', False),
        'combustible_materials': attrs.get('combustible_materials', False),
        'required_characts': attrs.get('required_characts') or '',
    }


class ClassifiersAPI:
    """API для работы с системами классификаторов и их уровнями (ленивая загрузка)."""

    def __init__(self, db_api):
        self.db_api = db_api

    # ===== Системы классификаторов =====

    def get_classifier_systems(self) -> List[Dict[str, Any]]:
        """Получить все системы классификаторов (без подсчёта потомков — экономим запросы)."""
        query = "SELECT NO_CASE Ext_ FROM Ext_{apl_classifier_system} END_SELECT"
        result = query_apl(self.db_api, query, "get_classifier_systems")
        return [_map_system(inst) for inst in result.get('instances', [])]

    def get_classifier_system(self, sys_id: int) -> Optional[Dict[str, Any]]:
        """Получить одну систему классификаторов по sys_id."""
        query = f"SELECT NO_CASE Ext_ FROM Ext_{{apl_classifier_system(.# = #{sys_id})}} END_SELECT"
        result = query_apl(self.db_api, query, f"get_classifier_system {sys_id}")
        instances = result.get('instances', [])
        return _map_system(instances[0]) if instances else None

    # ===== Уровни классификаторов =====

    def get_root_levels(self, system_sys_id: int) -> List[Dict[str, Any]]:
        """Получить корневые уровни системы (уровни без родителя)."""
        # Все уровни системы, затем фильтруем по отсутствию parent.
        # В PSS APL нельзя напрямую фильтровать по "parent отсутствует".
        query = (
            f"SELECT NO_CASE Ext_ FROM Ext_{{apl_classifier_level"
            f"(.system->apl_classifier_system.# = #{system_sys_id})}} END_SELECT"
        )
        result = query_apl(self.db_api, query, f"get_root_levels system={system_sys_id}")
        levels = [_map_level(inst) for inst in result.get('instances', [])]
        # Корневые — это уровни без parent_id
        roots = [lv for lv in levels if not lv.get('parent_id')]
        return roots

    def get_child_levels(self, parent_level_sys_id: int) -> List[Dict[str, Any]]:
        """Получить прямые дочерние уровни для заданного родительского уровня."""
        query = (
            f"SELECT NO_CASE Ext_ FROM Ext_{{apl_classifier_level"
            f"(.parent->apl_classifier_level.# = #{parent_level_sys_id})}} END_SELECT"
        )
        result = query_apl(self.db_api, query, f"get_child_levels parent={parent_level_sys_id}")
        return [_map_level(inst) for inst in result.get('instances', [])]

    def get_classifier_level_details(self, level_sys_id: int) -> Dict[str, Any]:
        """Получить полную информацию об уровне классификатора.

        Включает: атрибуты, имя системы и родителя, количество прямых потомков.
        """
        query = f"SELECT NO_CASE Ext_ FROM Ext_{{apl_classifier_level(.# = #{level_sys_id})}} END_SELECT"
        result = query_apl(self.db_api, query, f"get_classifier_level_details {level_sys_id}")
        instances = result.get('instances', [])
        if not instances:
            raise ValueError(f"Уровень классификатора с sys_id={level_sys_id} не найден")

        level = _map_level(instances[0])

        # Имя системы
        if level.get('system_id'):
            sys_info = self.get_classifier_system(level['system_id'])
            if sys_info:
                level['system_name'] = sys_info.get('name')

        # Имя родителя
        if level.get('parent_id'):
            parent_query = (
                f"SELECT NO_CASE Ext_ FROM Ext_{{apl_classifier_level(.# = #{level['parent_id']})}} END_SELECT"
            )
            parent_res = query_apl(self.db_api, parent_query, f"parent of level {level_sys_id}")
            p_instances = parent_res.get('instances', [])
            if p_instances:
                p_attrs = p_instances[0].get('attributes', {})
                level['parent_name'] = p_attrs.get('name')

        # Количество прямых потомков
        level['child_count'] = len(self.get_child_levels(level_sys_id))

        return level

    def get_classifier_tree(self, system_sys_id: int, max_depth: int = 2) -> Dict[str, Any]:
        """Получить неглубокое дерево: система + корневые уровни.

        Для полноценной навигации используйте get_child_levels при раскрытии узла.
        max_depth=1 — только корневые; max_depth=2 — корневые + их прямые потомки.
        """
        system = self.get_classifier_system(system_sys_id)
        if not system:
            raise ValueError(f"Система классификатора с sys_id={system_sys_id} не найдена")

        roots = self.get_root_levels(system_sys_id)

        # Для каждого корневого узла подгружаем потомков на глубину max_depth-1
        def _expand(node: Dict[str, Any], depth: int) -> Dict[str, Any]:
            if depth >= max_depth:
                node['children'] = []
                node['has_children'] = None  # неизвестно, загружать лениво
                return node
            children = self.get_child_levels(node['sys_id'])
            node['children'] = [_expand(c, depth + 1) for c in children]
            node['has_children'] = len(children) > 0
            return node

        levels = [_expand(r, 1) for r in roots]

        return {
            'system': system,
            'levels': levels,
        }

    # ===== Поиск =====

    def search_classifiers(self, search_text: str, search_type: str = "all") -> Dict[str, Any]:
        """Поиск по классификаторам.

        LIKE в APL не работает с кириллицей, поэтому фильтруем на стороне Python.
        """
        text = (search_text or '').lower()
        results = {'systems': [], 'levels': []}

        if search_type in ('all', 'systems'):
            for sys in self.get_classifier_systems():
                if text in (sys.get('id') or '').lower() \
                   or text in (sys.get('name') or '').lower() \
                   or text in (sys.get('description') or '').lower():
                    results['systems'].append(sys)

        if search_type in ('all', 'levels'):
            query = "SELECT NO_CASE Ext_ FROM Ext_{apl_classifier_level} END_SELECT"
            result = query_apl(self.db_api, query, "search_classifiers levels")
            for inst in result.get('instances', []):
                lv = _map_level(inst)
                if text in (lv.get('id') or '').lower() \
                   or text in (lv.get('name') or '').lower() \
                   or text in (lv.get('code') or '').lower():
                    results['levels'].append(lv)

        return results

    # ===== CRUD: системы =====

    def create_classifier_system(self, system_data: Dict[str, Any]) -> Dict[str, Any]:
        """Создать новую систему классификаторов."""
        attributes: Dict[str, Any] = {
            "id": system_data.get("id"),
            "name": system_data.get("name"),
            "description": system_data.get("description", ""),
            "is_concept_level_control": system_data.get("is_concept_level_control", False),
            "is_concept_last_level": system_data.get("is_concept_last_level", False),
            "is_object_level_control": system_data.get("is_object_level_control", False),
            "is_object_last_level": system_data.get("is_object_last_level", False),
            "object_minlevel": system_data.get("object_minlevel", 1),
            "object_maxlevel": system_data.get("object_maxlevel", 1),
            "is_type_control": system_data.get("is_type_control", False),
            "can_store_object": system_data.get("can_store_object", False),
            "stored_entity": system_data.get("stored_entity", ""),
            "item_id_template": system_data.get("item_id_template", ""),
            "esquisse": system_data.get("esquisse", ""),
            "esquisse_name": system_data.get("esquisse_name", ""),
            "guid": system_data.get("guid", ""),
            "struct_changed_date": system_data.get("struct_changed_date", ""),
            "only_construction": system_data.get("only_construction", False),
            "wiring": system_data.get("wiring", False),
            "wiring_near_controls": system_data.get("wiring_near_controls", False),
            "combustible_materials": system_data.get("combustible_materials", False),
            "is_multi_object": system_data.get("is_multi_object", False),
        }
        if system_data.get("parent_id"):
            attributes["parent"] = {"id": system_data["parent_id"]}
        if system_data.get("default_level_id"):
            attributes["default_level"] = {"id": system_data["default_level_id"]}

        payload = {
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [{
                "id": 0,
                "index": 0,
                "type": "apl_classifier_system",
                "attributes": attributes,
            }],
        }

        headers = self.db_api.get_headers()
        response = requests.post(self.db_api.URL_QUERY_SAVE, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        if result.get('count_all', 0) > 0 and result.get('instances'):
            new_sys_id = result['instances'][0]['id']
            created = self.get_classifier_system(new_sys_id)
            return created or {}
        return {}

    def update_classifier_system(self, sys_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Обновить систему классификаторов."""
        attributes: Dict[str, Any] = {}
        for key, value in updates.items():
            if key == 'parent_id':
                if value:
                    attributes['parent'] = {"id": value}
            elif key == 'default_level_id':
                if value:
                    attributes['default_level'] = {"id": value}
            else:
                attributes[key] = value

        payload = {
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [{
                "id": int(sys_id),
                "type": "apl_classifier_system",
                "attributes": attributes,
            }],
        }

        headers = self.db_api.get_headers()
        response = requests.post(self.db_api.URL_QUERY_SAVE, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        return self.get_classifier_system(int(sys_id)) or {}

    def delete_classifier_system(self, sys_id: int) -> bool:
        """Удалить систему классификаторов."""
        return self.db_api.delete_instance(int(sys_id), 'apl_classifier_system')

    # ===== CRUD: уровни =====

    def create_classifier_level(self, level_data: Dict[str, Any]) -> Dict[str, Any]:
        """Создать новый уровень классификатора."""
        if not level_data.get("system_id"):
            raise ValueError("system_id обязателен")

        attributes: Dict[str, Any] = {
            "system": {"id": level_data["system_id"]},
            "id": level_data.get("id"),
            "name": level_data.get("name"),
            "code": level_data.get("code", ""),
            "description": level_data.get("description", ""),
            "esquisse": level_data.get("esquisse", ""),
            "esquisse_name": level_data.get("esquisse_name", ""),
            "guid": level_data.get("guid", ""),
            "struct_changed_date": level_data.get("struct_changed_date", ""),
            "content_changed_data": level_data.get("content_changed_data", ""),
            "only_construction": level_data.get("only_construction", False),
            "wiring": level_data.get("wiring", False),
            "wiring_near_controls": level_data.get("wiring_near_controls", False),
            "combustible_materials": level_data.get("combustible_materials", False),
            "section_type": level_data.get("section_type", ""),
            "required_characts": level_data.get("required_characts", ""),
            "name_eng": level_data.get("name_eng", ""),
            "is_system_level": level_data.get("is_system_level", False),
        }
        if level_data.get("parent_id"):
            attributes["parent"] = {"id": level_data["parent_id"]}
        if level_data.get("related_product_id"):
            attributes["related_pdf"] = {"id": level_data["related_product_id"]}

        payload = {
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [{
                "id": 0,
                "index": 0,
                "type": "apl_classifier_level",
                "attributes": attributes,
            }],
        }

        headers = self.db_api.get_headers()
        response = requests.post(self.db_api.URL_QUERY_SAVE, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        if result.get('count_all', 0) > 0 and result.get('instances'):
            new_sys_id = result['instances'][0]['id']
            # Достать заново, чтобы получить нормализованный dict
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{apl_classifier_level(.# = #{new_sys_id})}} END_SELECT"
            created = query_apl(self.db_api, query, f"read created level {new_sys_id}")
            if created.get('instances'):
                return _map_level(created['instances'][0])
        return {}

    def update_classifier_level(self, sys_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Обновить уровень классификатора."""
        attributes: Dict[str, Any] = {}
        for key, value in updates.items():
            if key == 'system_id':
                if value:
                    attributes['system'] = {"id": value}
            elif key == 'parent_id':
                if value:
                    attributes['parent'] = {"id": value}
            elif key == 'related_product_id':
                if value:
                    attributes['related_pdf'] = {"id": value}
            else:
                attributes[key] = value

        payload = {
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [{
                "id": int(sys_id),
                "type": "apl_classifier_level",
                "attributes": attributes,
            }],
        }

        headers = self.db_api.get_headers()
        response = requests.post(self.db_api.URL_QUERY_SAVE, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        query = f"SELECT NO_CASE Ext_ FROM Ext_{{apl_classifier_level(.# = #{sys_id})}} END_SELECT"
        re_read = query_apl(self.db_api, query, f"read updated level {sys_id}")
        if re_read.get('instances'):
            return _map_level(re_read['instances'][0])
        return {}

    def delete_classifier_level(self, sys_id: int) -> bool:
        """Удалить уровень классификатора."""
        return self.db_api.delete_instance(int(sys_id), 'apl_classifier_level')
