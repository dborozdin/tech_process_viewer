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
            parent_ref = attrs.get('parent')
            # parent is a reference like {"id": N} or just an int
            parent_id = None
            if isinstance(parent_ref, dict):
                parent_id = parent_ref.get('id')
            elif isinstance(parent_ref, (int, float)):
                parent_id = int(parent_ref)
            folder_map[fid] = {
                'sys_id': fid,
                'name': attrs.get('name', ''),
                'parent_id': parent_id,
                'content_count': len(content),
                'children': []
            }

        # Build tree: attach children via parent reference
        for finfo in folder_map.values():
            pid = finfo['parent_id']
            if pid and pid in folder_map:
                folder_map[pid]['children'].append(finfo)

        # Root folders = those with no parent (or parent not in folder_map)
        if root_name:
            roots = [f for f in folder_map.values() if f['name'] == root_name]
        else:
            roots = [f for f in folder_map.values()
                     if not f['parent_id'] or f['parent_id'] not in folder_map]

        def clean_tree(node):
            return {
                'sys_id': node['sys_id'],
                'name': node['name'],
                'content_count': node['content_count'],
                'children': sorted(
                    [clean_tree(c) for c in node['children']],
                    key=lambda x: x['name']
                )
            }

        return sorted([clean_tree(r) for r in roots], key=lambda x: x['name'])

    @track_performance("get_folder_contents")
    def get_folder_contents(self, folder_sys_id):
        """Получить содержимое папки с разрешёнными типами.

        Для изделий дополнительно считает количество входящих компонентов (BOM children).

        Returns:
            dict: {folder_id, folder_name, items: [{sys_id, type, category, name, children_count?}]}
        """
        result = self.db_api.folders_api.get_folder_with_content_types(folder_sys_id)
        if not result or not result.get('items'):
            return result

        # Collect product PDF IDs to count BOM children
        pdf_ids = [item['sys_id'] for item in result['items']
                   if item.get('category') == 'product' and item.get('sys_id')]

        if pdf_ids:
            children_counts = self._count_bom_children(pdf_ids)
            for item in result['items']:
                if item.get('category') == 'product':
                    item['children_count'] = children_counts.get(item['sys_id'], 0)

        return result

    def _count_bom_children(self, pdf_ids):
        """Count BOM children for a list of PDF sys_ids in one query.

        Returns:
            dict: {pdf_sys_id: count}
        """
        if len(pdf_ids) == 1:
            filter_expr = f".relating_product_definition = #{pdf_ids[0]}"
        else:
            ids_str = ", ".join(f"#{pid}" for pid in pdf_ids)
            filter_expr = f".relating_product_definition IN ({ids_str})"

        query = (
            "SELECT NO_CASE Ext_ FROM "
            f"Ext_{{apl_quantified_assembly_component_usage+next_assembly_usage_occurrence({filter_expr})}}"
            " END_SELECT"
        )
        try:
            bom_data = query_apl(self.db_api, query, "BOM children count")
        except Exception:
            return {}

        counts = {}
        for inst in bom_data.get('instances', []):
            relating = inst.get('attributes', {}).get('relating_product_definition', {})
            parent_id = relating.get('id') if isinstance(relating, dict) else None
            if parent_id:
                counts[parent_id] = counts.get(parent_id, 0) + 1
        return counts

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
