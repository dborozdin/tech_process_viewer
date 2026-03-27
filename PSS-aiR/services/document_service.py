"""Сервис для работы с документами.

Документы привязываются к любым объектам через apl_document_reference.
"""

from tech_process_viewer.api.query_helpers import (
    track_performance, query_apl, batch_query_by_ids
)
from tech_process_viewer.globals import logger


class DocumentService:
    def __init__(self, db_api):
        self.db_api = db_api

    @track_performance("get_documents_for_item")
    def get_documents_for_item(self, item_sys_id):
        """Получить документы, привязанные к объекту через apl_document_reference.

        Args:
            item_sys_id: sys_id любого объекта (изделие, техпроцесс, etc.)

        Returns:
            list: [{sys_id, name, code, type, ref_sys_id}]
        """
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_document_reference(.item = #{item_sys_id})}}
        END_SELECT"""
        refs_data = query_apl(self.db_api, query, "Document references")

        doc_ids = []
        ref_map = {}  # doc_id -> ref_sys_id
        for inst in refs_data.get('instances', []):
            ref_id = inst.get('id')
            assigned = inst.get('attributes', {}).get('assigned_document', {})
            if isinstance(assigned, dict) and 'id' in assigned:
                did = assigned['id']
                doc_ids.append(did)
                ref_map[did] = ref_id

        if not doc_ids:
            return []

        # Batch: load documents
        doc_instances = batch_query_by_ids(self.db_api, doc_ids, "Documents (batch)")

        # Collect doc type IDs for batch
        doc_type_ids = []
        for dinst in doc_instances:
            kind = dinst.get('attributes', {}).get('kind', {})
            if isinstance(kind, dict) and 'id' in kind:
                doc_type_ids.append(kind['id'])

        doc_type_map = {}
        if doc_type_ids:
            type_instances = batch_query_by_ids(self.db_api, doc_type_ids, "Doc types (batch)")
            for tinst in type_instances:
                doc_type_map[tinst.get('id')] = tinst.get('attributes', {}).get('product_data_type', '')

        result = []
        for dinst in doc_instances:
            dattrs = dinst.get('attributes', {})
            did = dinst.get('id')
            kind = dattrs.get('kind', {})
            type_id = kind.get('id') if isinstance(kind, dict) else None

            result.append({
                'sys_id': did,
                'ref_sys_id': ref_map.get(did),
                'name': dattrs.get('name', ''),
                'code': dattrs.get('id', ''),
                'type': doc_type_map.get(type_id, ''),
            })

        return result

    def attach_document(self, doc_sys_id, item_sys_id, item_type='apl_product_definition_formation'):
        """Привязать документ к объекту."""
        return self.db_api.docs_api.find_or_create_document_reference(
            doc=doc_sys_id,
            ref_object=item_sys_id,
            ref_object_type=item_type
        )

    def detach_document(self, doc_ref_sys_id):
        """Отвязать документ (удалить связку)."""
        return self.db_api.docs_api.delete_document_reference(doc_ref_sys_id)

    @track_performance("search_documents")
    def search_documents(self, query_text):
        """Поиск документов по имени или id."""
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_document(.id LIKE "*{query_text}*" OR .name LIKE "*{query_text}*")}}
        END_SELECT"""
        result = query_apl(self.db_api, query, "Search documents")
        docs = []
        for inst in result.get('instances', [])[:50]:
            attrs = inst.get('attributes', {})
            docs.append({
                'sys_id': inst.get('id'),
                'name': attrs.get('name', ''),
                'code': attrs.get('id', ''),
            })
        return docs
