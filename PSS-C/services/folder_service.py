"""Сервис для работы с папками PSS.

Обобщённая работа с папками: дерево, содержимое с типами, создание, перемещение.
"""

from tech_process_viewer.api.query_helpers import track_performance, query_apl, batch_query_by_ids
from tech_process_viewer.globals import logger


class FolderService:
    def __init__(self, db_api):
        self.db_api = db_api

    @track_performance("get_folder_tree")
    def get_folder_tree(self, root_name=None):
        """Построить дерево папок.

        Args:
            root_name: Имя корневой папки (None = все папки верхнего уровня)

        Returns:
            list: Дерево папок [{sys_id, name, children: [...]}]
        """
        all_folders = self.db_api.folders_api.get_all_folders()
        if not all_folders:
            return []

        # Build map: sys_id -> folder info
        folder_map = {}
        for f in all_folders:
            fid = f.get('id')
            attrs = f.get('attributes', {})
            content = attrs.get('content', [])
            parent = attrs.get('parent')
            # Identify child folder IDs
            child_folder_ids = set()
            for item in content:
                if item.get('type') == 'apl_folder':
                    child_folder_ids.add(item.get('id'))
            folder_map[fid] = {
                'sys_id': fid,
                'name': attrs.get('name', ''),
                'has_parent': bool(parent),
                'child_folder_ids': child_folder_ids,
                'content_count': len(content),
                'children': []
            }

        # Build tree: attach children
        for finfo in folder_map.values():
            for cfid in finfo['child_folder_ids']:
                if cfid in folder_map:
                    finfo['children'].append(folder_map[cfid])

        # Root folders = those with no parent attribute set
        if root_name:
            roots = [f for f in folder_map.values() if f['name'] == root_name]
        else:
            roots = [f for f in folder_map.values() if not f.get('has_parent')]

        def clean_tree(node):
            return {
                'sys_id': node['sys_id'],
                'name': node['name'],
                'content_count': node['content_count'],
                'children': [clean_tree(c) for c in node['children']]
            }

        return [clean_tree(r) for r in roots]

    @track_performance("get_folder_contents")
    def get_folder_contents(self, folder_sys_id):
        """Получить содержимое папки с разрешёнными типами.

        Returns:
            dict: {folder_id, folder_name, items: [{sys_id, type, category, name}]}
        """
        return self.db_api.folders_api.get_folder_with_content_types(folder_sys_id)

    @track_performance("create_folder")
    def create_folder(self, name, parent_id=None):
        """Создать папку и добавить в родительскую (если указана).

        Returns:
            dict: {sys_id, name} или None
        """
        result = self.db_api.folders_api.create_folder(name)
        if result is None:
            return None

        folder_id, status, _ = result

        if parent_id:
            self.db_api.folders_api.add_item_to_folder(
                item=folder_id,
                item_type='apl_folder',
                folder=parent_id
            )

        return {'sys_id': folder_id, 'name': name}

    def move_item(self, item_id, item_type, from_folder_id, to_folder_id):
        """Переместить элемент из одной папки в другую."""
        self.db_api.folders_api.remove_item_from_folder(from_folder_id, item_id)
        self.db_api.folders_api.add_item_to_folder(item_id, item_type, to_folder_id)
        return True
