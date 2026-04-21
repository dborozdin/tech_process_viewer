"""Сервис для работы со справочниками PSS.

Классификаторы: полная реализация (ленивая загрузка дерева).
Другие справочники (единицы, организации, характеристики и др.): заглушки.
"""

from tech_process_viewer.api.query_helpers import track_performance
from tech_process_viewer.globals import logger


class ReferenceService:
    """Сервис для работы со справочниками PSS."""

    def __init__(self, db_api):
        self.db_api = db_api

    def _api(self):
        if not self.db_api or not hasattr(self.db_api, 'classifiers_api'):
            return None
        return self.db_api.classifiers_api

    # ===== Классификаторы =====

    @track_performance("get_classifier_systems")
    def get_classifier_systems(self):
        api = self._api()
        if not api:
            return []
        try:
            return api.get_classifier_systems()
        except Exception as e:
            logger.error(f"Error getting classifier systems: {e}")
            return []

    @track_performance("get_classifier_tree")
    def get_classifier_tree(self, system_sys_id, max_depth=2):
        api = self._api()
        if not api:
            return {'system': None, 'levels': []}
        try:
            return api.get_classifier_tree(int(system_sys_id), max_depth)
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error getting classifier tree for {system_sys_id}: {e}")
            return {'system': None, 'levels': []}

    @track_performance("get_root_levels")
    def get_root_levels(self, system_sys_id):
        api = self._api()
        if not api:
            return []
        try:
            return api.get_root_levels(int(system_sys_id))
        except Exception as e:
            logger.error(f"Error getting root levels for system {system_sys_id}: {e}")
            return []

    @track_performance("get_child_levels")
    def get_child_levels(self, parent_level_sys_id):
        api = self._api()
        if not api:
            return []
        try:
            return api.get_child_levels(int(parent_level_sys_id))
        except Exception as e:
            logger.error(f"Error getting child levels for parent {parent_level_sys_id}: {e}")
            return []

    @track_performance("get_classifier_level_details")
    def get_classifier_level_details(self, level_sys_id):
        api = self._api()
        if not api:
            return {}
        try:
            return api.get_classifier_level_details(int(level_sys_id))
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error getting level details for {level_sys_id}: {e}")
            return {}

    @track_performance("search_classifiers")
    def search_classifiers(self, search_text, search_type="all"):
        api = self._api()
        if not api:
            return {'systems': [], 'levels': []}
        try:
            return api.search_classifiers(search_text, search_type)
        except Exception as e:
            logger.error(f"Error searching classifiers: {e}")
            return {'systems': [], 'levels': []}

    # ===== CRUD (проксируем на ClassifiersAPI) =====

    @track_performance("create_classifier_system")
    def create_classifier_system(self, system_data):
        api = self._api()
        if not api:
            return {}
        try:
            return api.create_classifier_system(system_data)
        except Exception as e:
            logger.error(f"Error creating classifier system: {e}")
            return {}

    @track_performance("update_classifier_system")
    def update_classifier_system(self, sys_id, updates):
        api = self._api()
        if not api:
            return {}
        try:
            return api.update_classifier_system(int(sys_id), updates)
        except Exception as e:
            logger.error(f"Error updating classifier system {sys_id}: {e}")
            return {}

    @track_performance("delete_classifier_system")
    def delete_classifier_system(self, sys_id):
        api = self._api()
        if not api:
            return False
        try:
            return api.delete_classifier_system(int(sys_id))
        except Exception as e:
            logger.error(f"Error deleting classifier system {sys_id}: {e}")
            return False

    @track_performance("create_classifier_level")
    def create_classifier_level(self, level_data):
        api = self._api()
        if not api:
            return {}
        try:
            return api.create_classifier_level(level_data)
        except Exception as e:
            logger.error(f"Error creating classifier level: {e}")
            return {}

    @track_performance("update_classifier_level")
    def update_classifier_level(self, sys_id, updates):
        api = self._api()
        if not api:
            return {}
        try:
            return api.update_classifier_level(int(sys_id), updates)
        except Exception as e:
            logger.error(f"Error updating classifier level {sys_id}: {e}")
            return {}

    @track_performance("delete_classifier_level")
    def delete_classifier_level(self, sys_id):
        api = self._api()
        if not api:
            return False
        try:
            return api.delete_classifier_level(int(sys_id))
        except Exception as e:
            logger.error(f"Error deleting classifier level {sys_id}: {e}")
            return False

    # ===== Список типов справочников / заглушки =====

    @track_performance("get_all_reference_types")
    def get_all_reference_types(self):
        count = len(self.get_classifier_systems()) if self._api() else 0
        return [
            {'id': 'classifiers', 'name': 'Классификаторы', 'icon': '📚',
             'description': 'Системы и уровни классификации объектов',
             'implemented': True, 'count': count},
            {'id': 'units', 'name': 'Единицы измерения', 'icon': '📏',
             'description': 'Базовые и производные единицы измерения',
             'implemented': False, 'count': 0},
            {'id': 'organizations', 'name': 'Организации', 'icon': '🏢',
             'description': 'Организации-исполнители и подрядчики',
             'implemented': False, 'count': 0},
            {'id': 'characteristics', 'name': 'Характеристики', 'icon': '📋',
             'description': 'Типы характеристик изделий',
             'implemented': False, 'count': 0},
            {'id': 'other', 'name': 'Другие справочники', 'icon': '📄',
             'description': 'Документы, ресурсы, статусы, категории',
             'implemented': False, 'count': 0},
        ]

    @track_performance("get_reference_list")
    def get_reference_list(self, ref_type):
        """Заглушка для неподдерживаемых типов справочников."""
        known = {
            'units': 'Единицы измерения',
            'organizations': 'Организации',
            'characteristics': 'Характеристики',
            'document-types': 'Типы документов',
            'resource-types': 'Типы ресурсов',
            'statuses': 'Статусы объектов',
            'categories': 'Категории',
            'other': 'Другие справочники',
        }
        name = known.get(ref_type, ref_type)
        return {
            'type': ref_type,
            'name': name,
            'placeholder': True,
            'message': 'Функционал находится в разработке',
            'items': [],
        }
