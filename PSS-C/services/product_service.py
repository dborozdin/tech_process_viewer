"""Сервис для работы с изделиями и структурой BOM.

Рекурсивное дерево BOM читается по уровням (batch-запросами).
"""

from tech_process_viewer.api.query_helpers import (
    track_performance, query_apl, batch_query_by_ids
)
from tech_process_viewer.globals import logger


class ProductService:
    def __init__(self, db_api):
        self.db_api = db_api

    @track_performance("get_product_tree")
    def get_product_tree(self, pdf_sys_id, max_depth=10):
        """Построить дерево BOM по уровням.

        Количество запросов к БД ~ max_depth (не N).

        Args:
            pdf_sys_id: sys_id версии изделия (apl_product_definition_formation)
            max_depth: Максимальная глубина

        Returns:
            dict: {root: {...}, children: [...], total_nodes, depth}
        """
        # Get root product info
        root_info = self._get_pdf_info(pdf_sys_id)
        if not root_info:
            return None

        tree = {
            'root': root_info,
            'children': [],
            'total_nodes': 1,
            'depth': 0
        }

        # BFS by levels
        current_level = [pdf_sys_id]
        parent_children_map = {pdf_sys_id: tree['children']}

        for depth in range(max_depth):
            if not current_level:
                break

            tree['depth'] = depth + 1

            # One query per level: all children of current level
            if len(current_level) == 1:
                filter_expr = f".relating_product_definition = #{current_level[0]}"
            else:
                ids_str = ", ".join(f"#{pid}" for pid in current_level)
                filter_expr = f".relating_product_definition IN ({ids_str})"
            query = (
                "SELECT NO_CASE Ext_ FROM "
                f"Ext_{{apl_quantified_assembly_component_usage+next_assembly_usage_occurrence({filter_expr})}}"
                " END_SELECT"
            )
            try:
                bom_data = query_apl(self.db_api, query, f"BOM level {depth+1}")
            except Exception:
                break

            if not bom_data.get('instances'):
                break

            # Collect related PDF IDs for batch resolution
            related_ids = set()
            unit_ids_to_resolve = set()
            bom_items_by_parent = {}
            for inst in bom_data.get('instances', []):
                attrs = inst.get('attributes', {})
                relating = attrs.get('relating_product_definition', {})
                related = attrs.get('related_product_definition', {})
                parent_id = relating.get('id') if isinstance(relating, dict) else None
                child_id = related.get('id') if isinstance(related, dict) else None

                if parent_id and child_id:
                    related_ids.add(child_id)
                    unit_ref = attrs.get('unit_component', {})
                    unit_id = unit_ref.get('id') if isinstance(unit_ref, dict) else unit_ref
                    if unit_id:
                        unit_ids_to_resolve.add(unit_id)
                    if parent_id not in bom_items_by_parent:
                        bom_items_by_parent[parent_id] = []
                    bom_items_by_parent[parent_id].append({
                        'bom_sys_id': inst.get('id'),
                        'child_pdf_id': child_id,
                        'quantity': attrs.get('value_component', ''),
                        'unit_id': unit_id,
                        'reference_designator': attrs.get('reference_designator', ''),
                    })

            # Batch: resolve units
            unit_map = {}
            if unit_ids_to_resolve:
                unit_instances = batch_query_by_ids(
                    self.db_api, list(unit_ids_to_resolve), f"Units level {depth+1}"
                )
                for uinst in unit_instances:
                    unit_map[uinst.get('id')] = uinst.get('attributes', {}).get('id', '')

            # Batch: resolve child product info
            child_info_map = {}
            if related_ids:
                child_instances = batch_query_by_ids(
                    self.db_api, list(related_ids), f"Child PDFs level {depth+1}"
                )
                # Get product IDs for names
                product_ids = []
                pdf_product_map = {}
                for cinst in child_instances:
                    of_product = cinst.get('attributes', {}).get('of_product', {})
                    if isinstance(of_product, dict) and 'id' in of_product:
                        product_ids.append(of_product['id'])
                        pdf_product_map[cinst.get('id')] = of_product['id']

                product_map = {}
                if product_ids:
                    prod_instances = batch_query_by_ids(
                        self.db_api, product_ids, f"Products level {depth+1}"
                    )
                    for pinst in prod_instances:
                        product_map[pinst.get('id')] = pinst.get('attributes', {})

                for cinst in child_instances:
                    cid = cinst.get('id')
                    pid = pdf_product_map.get(cid)
                    pattrs = product_map.get(pid, {})
                    cinst_attrs = cinst.get('attributes', {})
                    child_info_map[cid] = {
                        'sys_id': cid,
                        'product_id': pattrs.get('id', ''),
                        'name': pattrs.get('name', ''),
                        'product_code': pattrs.get('code', ''),
                        'code1': cinst_attrs.get('code1', ''),
                        'code2': cinst_attrs.get('code2', ''),
                        'formation_type': cinst_attrs.get('formation_type', ''),
                        'make_or_buy': cinst_attrs.get('make_or_buy', ''),
                    }

            # Build tree nodes for this level
            next_level = []
            new_parent_map = {}
            for parent_id, items in bom_items_by_parent.items():
                parent_list = parent_children_map.get(parent_id, [])
                for item in items:
                    child_id = item['child_pdf_id']
                    info = child_info_map.get(child_id, {})
                    node = {
                        'sys_id': child_id,
                        'bom_sys_id': item['bom_sys_id'],
                        'product_id': info.get('product_id', ''),
                        'name': info.get('name', ''),
                        'product_code': info.get('product_code', ''),
                        'code1': info.get('code1', ''),
                        'code2': info.get('code2', ''),
                        'formation_type': info.get('formation_type', ''),
                        'make_or_buy': info.get('make_or_buy', ''),
                        'quantity': item['quantity'],
                        'unit_name': unit_map.get(item.get('unit_id'), ''),
                        'reference_designator': item.get('reference_designator', ''),
                        'children': []
                    }
                    parent_list.append(node)
                    tree['total_nodes'] += 1
                    next_level.append(child_id)
                    new_parent_map[child_id] = node['children']

            current_level = next_level
            parent_children_map = new_parent_map

        return tree

    @track_performance("get_product_details")
    def get_product_details(self, pdf_sys_id):
        """Получить полные данные об изделии.

        Returns:
            dict: {sys_id, product_id, name, attributes, characteristics, documents}
        """
        info = self._get_pdf_info(pdf_sys_id)
        if not info:
            return None

        # Characteristics (may fail if entity type doesn't exist in this DB)
        try:
            chars = self.db_api.products_api.get_product_characteristics(pdf_sys_id)
            info['characteristics'] = [{
                'sys_id': c.get('id'),
                'name': c.get('attributes', {}).get('name', ''),
                'value': c.get('attributes', {}).get('value', ''),
            } for c in chars]
        except Exception:
            info['characteristics'] = []

        # Documents (may fail if entity type doesn't exist in this DB)
        try:
            doc_query = f"""SELECT NO_CASE
            Ext_
            FROM
            Ext_{{apl_document_reference(.item = #{pdf_sys_id})}}
            END_SELECT"""
            doc_refs = query_apl(self.db_api, doc_query, "Document refs for product")
            doc_ids = []
            for inst in doc_refs.get('instances', []):
                assigned = inst.get('attributes', {}).get('assigned_document', {})
                if isinstance(assigned, dict) and 'id' in assigned:
                    doc_ids.append(assigned['id'])

            docs = []
            if doc_ids:
                doc_instances = batch_query_by_ids(self.db_api, doc_ids, "Documents for product")
                for dinst in doc_instances:
                    dattrs = dinst.get('attributes', {})
                    docs.append({
                        'sys_id': dinst.get('id'),
                        'name': dattrs.get('name', ''),
                        'code': dattrs.get('id', ''),
                    })
            info['documents'] = docs
        except Exception:
            info['documents'] = []

        return info

    @track_performance("search_products")
    def search_products(self, query_text):
        """Поиск изделий по id или name."""
        results = self.db_api.products_api.search_products(query_text)
        return [{
            'sys_id': inst.get('id'),
            'product_id': inst.get('attributes', {}).get('id', ''),
            'name': inst.get('attributes', {}).get('name', ''),
        } for inst in results]

    def export_bom_flat(self, pdf_sys_id, max_depth=10):
        """Плоский список BOM для отчётов."""
        tree = self.get_product_tree(pdf_sys_id, max_depth)
        if not tree:
            return []

        flat = []

        def flatten(children, depth=1):
            for node in children:
                flat.append({
                    'depth': depth,
                    'product_id': node.get('product_id', ''),
                    'name': node.get('name', ''),
                    'code1': node.get('code1', ''),
                    'quantity': node.get('quantity', ''),
                    'unit_name': node.get('unit_name', ''),
                    'formation_type': node.get('formation_type', ''),
                })
                flatten(node.get('children', []), depth + 1)

        flatten(tree.get('children', []))
        return flat

    @track_performance("get_product_full_info")
    def get_product_full_info(self, pdf_sys_id):
        """Получить полные атрибуты изделия и его версии."""
        return self.db_api.products_api.get_product_full_info(pdf_sys_id)

    def _get_pdf_info(self, pdf_sys_id):
        """Получить базовую информацию о версии изделия."""
        pdf_instances = batch_query_by_ids(self.db_api, [pdf_sys_id], "PDF info")
        if not pdf_instances:
            return None

        pdf_inst = pdf_instances[0]
        pdf_attrs = pdf_inst.get('attributes', {})
        of_product = pdf_attrs.get('of_product', {})

        # Get product name
        product_name = ''
        product_id = ''
        if isinstance(of_product, dict) and 'id' in of_product:
            prod_instances = batch_query_by_ids(
                self.db_api, [of_product['id']], "Product for PDF"
            )
            if prod_instances:
                pattrs = prod_instances[0].get('attributes', {})
                product_name = pattrs.get('name', '')
                product_id = pattrs.get('id', '')

        return {
            'sys_id': pdf_sys_id,
            'product_id': product_id,
            'name': product_name,
            'code1': pdf_attrs.get('code1', ''),
            'code2': pdf_attrs.get('code2', ''),
            'formation_type': pdf_attrs.get('formation_type', ''),
            'make_or_buy': pdf_attrs.get('make_or_buy', ''),
            'attributes': pdf_attrs,
        }
