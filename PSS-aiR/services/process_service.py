"""Сервис для работы с техпроцессами.

Перенос и оптимизация логики из tech_process_viewer app.py.
"""

from tech_process_viewer.api.query_helpers import (
    track_performance, query_apl, batch_query_by_ids, resolve_org_unit
)
from tech_process_viewer.globals import logger


class ProcessService:
    def __init__(self, db_api):
        self.db_api = db_api

    @track_performance("get_processes_for_product")
    def get_processes_for_product(self, product_pdf_id):
        """Получить техпроцессы, связанные с изделием.

        Args:
            product_pdf_id: sys_id версии изделия
        """
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_business_process_reference(.item=#{product_pdf_id})}}.assigned_process
        END_SELECT"""
        refs_data = query_apl(self.db_api, query, "BP refs for product")
        process_ids = [inst["id"] for inst in refs_data.get("instances", [])]

        if not process_ids:
            return []

        # Batch: processes
        ids_str = ", ".join(f"#{pid}" for pid in process_ids)
        query_bp = f"""SELECT NO_CASE
        Ext2
        FROM
        Ext_{{{ids_str}}}
        Ext2{{apl_business_process(.# in #Ext_)}}
        END_SELECT"""
        proc_data = query_apl(self.db_api, query_bp, "Business processes")

        # Batch: resolve type names
        type_ids = []
        for inst in proc_data.get("instances", []):
            type_obj = inst.get("attributes", {}).get("type", {})
            if isinstance(type_obj, dict) and "id" in type_obj:
                type_ids.append(type_obj["id"])
        type_map = {}
        if type_ids:
            for tinst in batch_query_by_ids(self.db_api, list(set(type_ids)), "BP types"):
                type_map[tinst.get("id")] = tinst.get("attributes", {}).get("name", "")

        res_type_id = self.db_api.resources_api.find_resource_type_by_name("Vreme rada")

        result = []
        for proc in proc_data.get("instances", []):
            attrs = proc.get("attributes", {})
            bp_id = proc.get("id")
            org_unit = resolve_org_unit(self.db_api, bp_id, res_type_id)

            type_obj = attrs.get("type", {})
            type_id = type_obj.get("id") if isinstance(type_obj, dict) else None
            resolved_type_name = type_map.get(type_id, "") if type_id else ""

            result.append({
                "process_id": bp_id,
                "product_id": product_pdf_id,
                "name": attrs.get("name"),
                "designation": attrs.get("id", ""),
                "type_name": resolved_type_name,
                "org_unit": org_unit,
                "process_type": "Customized" if attrs.get("customized", False) else "Typical",
            })

        return result

    @track_performance("get_process_hierarchy")
    def get_process_hierarchy(self, process_id):
        """Получить иерархию подпроцессов (фазы → техпроцессы → операции)."""
        return self._get_sub_processes(process_id, element_type='phase_id', parent_element_type='process_id')

    @track_performance("get_process_details")
    def get_process_details(self, tech_proc_id):
        """Получить детали техпроцесса с операциями, документами, материалами."""
        query_tp = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_business_process(.# = #{tech_proc_id})}}
        END_SELECT"""
        tp_data = query_apl(self.db_api, query_tp, "TP details")

        if not tp_data.get("instances"):
            return None

        tp_attrs = tp_data["instances"][0]["attributes"]
        res_type_id = self.db_api.resources_api.find_resource_type_by_name("Vreme rada")
        org_unit = resolve_org_unit(self.db_api, tech_proc_id, res_type_id)

        # Resolve type name
        type_name = ""
        type_obj = tp_attrs.get("type", {})
        if isinstance(type_obj, dict) and "id" in type_obj:
            type_instances = batch_query_by_ids(self.db_api, [type_obj["id"]], "BP type")
            if type_instances:
                type_name = type_instances[0].get("attributes", {}).get("name", "")

        # Resolve vreme rada for the process itself
        man_hours = ""
        if res_type_id:
            resource_id = self.db_api.resources_api.find_resource_by_bp_and_type(
                tech_proc_id, res_type_id
            )
            if resource_id:
                resource_data = self.db_api.resources_api.find_resource_data_by_id(resource_id)
                if resource_data and resource_data.get('instances'):
                    value = resource_data['instances'][0].get('attributes', {}).get("value_component", "")
                    man_hours = str(value) if value else ""

        result = {
            'sys_id': tech_proc_id,
            'id': tp_attrs.get('id', ''),
            'name': tp_attrs.get('name'),
            'description': tp_attrs.get('description', ''),
            'org_unit': org_unit,
            'type_name': type_name,
            'process_type': "Customized" if tp_attrs.get("customized", False) else "Typical",
            'man_hours': man_hours,
        }

        # Operations
        operations = self._get_sub_processes(
            tech_proc_id, element_type='operation_id', parent_element_type='tech_proc_id'
        )
        for op in operations:
            op['man_hours'] = ""
            if res_type_id:
                resource_id = self.db_api.resources_api.find_resource_by_bp_and_type(
                    op['operation_id'], res_type_id
                )
                if resource_id:
                    resource_data = self.db_api.resources_api.find_resource_data_by_id(resource_id)
                    if resource_data and 'instances' in resource_data and resource_data['instances']:
                        value = resource_data['instances'][0]['attributes'].get("value_component", "")
                        op['man_hours'] = str(value) if value else ""
        result['operations'] = operations

        # Documents (batch)
        result['documents'] = self._get_documents(tech_proc_id)

        # Materials
        result['materials'] = self._get_materials(tech_proc_id)

        return result

    def _get_sub_processes(self, process_id, element_type, parent_element_type):
        """Загрузить подпроцессы для бизнес-процесса."""
        query = f"""SELECT NO_CASE
        Ext2
        FROM
        Ext_{{#{process_id}}}
        Ext2{{apl_business_process(.# IN #Ext_)}}
        END_SELECT"""
        refs_data = query_apl(self.db_api, query, f"BP for {element_type}")

        phase_ids = []
        for inst in refs_data.get("instances", []):
            elements = inst.get("attributes", {}).get('elements')
            if elements:
                for elem in elements:
                    phase_ids.append(elem.get('id'))

        if not phase_ids:
            return []

        # Batch: sub-processes
        ids_str = ", ".join(f"#{pid}" for pid in phase_ids)
        query_bp = f"""SELECT NO_CASE
        Ext2
        FROM
        Ext_{{{ids_str}}}
        Ext2{{apl_business_process(.# in #Ext_)}}
        END_SELECT"""
        proc_data = query_apl(self.db_api, query_bp, f"Sub-processes ({element_type})")

        # Batch: types
        type_ids = []
        for inst in proc_data.get("instances", []):
            if inst.get("type") == "apl_business_process":
                type_obj = inst.get("attributes", {}).get("type", {})
                if isinstance(type_obj, dict) and "id" in type_obj:
                    type_ids.append(type_obj["id"])

        type_map = {}
        if type_ids:
            type_instances = batch_query_by_ids(self.db_api, type_ids, "BP types")
            for tinst in type_instances:
                type_map[tinst.get("id")] = tinst.get("attributes", {}).get("name", "")

        res_type_id = self.db_api.resources_api.find_resource_type_by_name("Vreme rada")

        result = []
        for proc in proc_data.get("instances", []):
            if proc.get("type") != "apl_business_process":
                continue
            attrs = proc.get("attributes", {})
            bp_id = proc.get("id")

            # Resolve type name
            type_obj = attrs.get("type", {})
            type_id = type_obj.get("id") if isinstance(type_obj, dict) else None
            resolved_type_name = type_map.get(type_id, "") if type_id else ""

            # Display name
            if element_type == 'tech_proc_id':
                display_name = f"{attrs.get('id', '')} : {attrs.get('name')}"
            elif element_type == 'operation_id':
                bp_id_attr = attrs.get("id", "")
                oper_id = bp_id_attr.split()[-1] if bp_id_attr else ""
                display_name = f"{oper_id} : {attrs.get('name')}"
            else:
                display_name = f"{resolved_type_name} : {attrs.get('name')}" if resolved_type_name else attrs.get("name")

            org_unit = resolve_org_unit(self.db_api, bp_id, res_type_id)

            result.append({
                parent_element_type: process_id,
                element_type: bp_id,
                "name": display_name,
                "original_name": attrs.get("name"),
                "designation": attrs.get("id", ""),
                "type_name": resolved_type_name,
                "description": attrs.get("description", ""),
                "org_unit": org_unit,
                "process_type": "Customized" if attrs.get("customized", False) else "Typical",
            })

        return result

    def _get_documents(self, item_sys_id):
        """Получить документы для объекта (batch)."""
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_document_reference(.item = #{item_sys_id})}}
        END_SELECT"""
        refs = query_apl(self.db_api, query, "Doc refs")

        doc_ids = []
        for inst in refs.get('instances', []):
            assigned = inst.get('attributes', {}).get('assigned_document', {})
            if isinstance(assigned, dict) and 'id' in assigned:
                doc_ids.append(assigned['id'])

        if not doc_ids:
            return []

        doc_instances = batch_query_by_ids(self.db_api, doc_ids, "Docs (batch)")
        return [{
            'name': d.get('attributes', {}).get('name', ''),
            'code': d.get('attributes', {}).get('id', ''),
        } for d in doc_instances]

    def _get_materials(self, tech_proc_id):
        """Получить материалы для техпроцесса (batch)."""
        mat_type_id = self.db_api.resources_api.find_resource_type_by_name("Potrošni materijal")
        if not mat_type_id:
            return []

        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_business_process_resource(.process = #{tech_proc_id} AND .type = #{mat_type_id})}}
        END_SELECT"""
        mats_data = query_apl(self.db_api, query, "Material resources")

        materials = []
        for inst in mats_data.get("instances", []):
            obj = inst.get("attributes", {}).get("object", {})
            if not isinstance(obj, dict) or 'id' not in obj:
                continue

            assembly_pdf_id = obj['id']
            query_asm = f"""SELECT NO_CASE
            Ext_
            FROM
            Ext_{{apl_quantified_assembly_component_usage+next_assembly_usage_occurrence(.relating_product_definition = #{assembly_pdf_id})}}
            END_SELECT"""
            asm_data = query_apl(self.db_api, query_asm, "Assemblies")

            # Batch: related PDFs, products, units
            related_ids = []
            unit_ids = []
            asm_map = {}
            for ainst in asm_data.get("instances", []):
                aattrs = ainst.get("attributes", {})
                related = aattrs.get("related_product_definition", {})
                if isinstance(related, dict) and 'id' in related:
                    rid = related['id']
                    related_ids.append(rid)
                    asm_map[rid] = aattrs
                    unit = aattrs.get("unit_component", {})
                    if isinstance(unit, dict) and 'id' in unit:
                        unit_ids.append(unit['id'])

            if not related_ids:
                continue

            related_insts = batch_query_by_ids(self.db_api, related_ids, "Related PDFs")
            product_ids = []
            pdf_map = {}
            for rinst in related_insts:
                of_product = rinst.get("attributes", {}).get("of_product", {})
                if isinstance(of_product, dict) and 'id' in of_product:
                    product_ids.append(of_product['id'])
                    pdf_map[rinst.get("id")] = {
                        'product_id': of_product['id'],
                        'code1': rinst.get("attributes", {}).get('code1', '')
                    }

            prod_map = {}
            if product_ids:
                for pinst in batch_query_by_ids(self.db_api, product_ids, "Products"):
                    prod_map[pinst.get("id")] = pinst.get("attributes", {})

            unit_map = {}
            if unit_ids:
                for uinst in batch_query_by_ids(self.db_api, unit_ids, "Units"):
                    unit_map[uinst.get("id")] = uinst.get("attributes", {}).get("name", "")

            for rid, aattrs in asm_map.items():
                pinfo = pdf_map.get(rid, {})
                pattrs = prod_map.get(pinfo.get('product_id'), {})
                unit = aattrs.get("unit_component", {})
                uid = unit.get('id') if isinstance(unit, dict) else None
                materials.append({
                    'name': pattrs.get('name', ''),
                    'code': pinfo.get('code1', ''),
                    'id': pattrs.get('id', ''),
                    'quantity': aattrs.get('value_component', ''),
                    'uom': unit_map.get(uid, '')
                })

        return materials

    @track_performance("get_operation_column_types")
    def get_operation_column_types(self):
        """Получить доступные типы динамических колонок для таблицы операций.

        Returns:
            list: [{category, key, label, sys_id?}]
        """
        result = []

        # Resource types from DB
        res_types = self.db_api.resources_api.list_resource_types(limit=200)
        if res_types and 'instances' in res_types:
            for inst in res_types['instances']:
                attrs = inst.get('attributes', {})
                result.append({
                    'category': 'resource',
                    'key': f"res_{inst['id']}",
                    'label': attrs.get('name', f"Ресурс #{inst['id']}"),
                    'sys_id': inst['id']
                })

        # Documents — fixed synthetic entry
        result.append({
            'category': 'document',
            'key': 'documents',
            'label': 'Документы'
        })

        return result

    @track_performance("get_operation_column_data")
    def get_operation_column_data(self, tech_proc_id, column_keys):
        """Получить данные динамических колонок для операций техпроцесса.

        Args:
            tech_proc_id: sys_id техпроцесса
            column_keys: list строк вида ["res_815000", "documents"]

        Returns:
            dict: {column_key: {operation_id_str: [{value, unit?} or {name, code}]}}
        """
        # Get operation IDs first
        operations = self._get_sub_processes(
            tech_proc_id, element_type='operation_id', parent_element_type='tech_proc_id'
        )
        op_ids = [op['operation_id'] for op in operations]
        if not op_ids:
            return {}

        result = {}
        for col_key in column_keys:
            if col_key.startswith('res_'):
                result[col_key] = self._get_resource_column(op_ids, col_key)
            elif col_key == 'documents':
                result[col_key] = self._get_document_column(op_ids)

        return result

    def _get_resource_column(self, op_ids, col_key):
        """Batch-запрос ресурсов одного типа для всех операций."""
        res_type_id = int(col_key.replace('res_', ''))
        ids_str = ", ".join(f"#{oid}" for oid in op_ids)

        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_business_process_resource(.process IN ({ids_str}) AND .type = #{res_type_id})}}
        END_SELECT"""
        data = query_apl(self.db_api, query, f"Resources col {col_key}")

        # Collect unit IDs for batch resolution
        unit_ids = []
        for inst in data.get('instances', []):
            unit_obj = inst.get('attributes', {}).get('unit_component', {})
            if isinstance(unit_obj, dict) and 'id' in unit_obj:
                unit_ids.append(unit_obj['id'])

        unit_map = {}
        if unit_ids:
            for uinst in batch_query_by_ids(self.db_api, list(set(unit_ids)), "Units"):
                unit_map[uinst.get('id')] = uinst.get('attributes', {}).get('name', '')

        # Group by process (operation) ID
        grouped = {}
        for inst in data.get('instances', []):
            attrs = inst.get('attributes', {})
            proc_ref = attrs.get('process', {})
            proc_id = proc_ref.get('id') if isinstance(proc_ref, dict) else None
            if proc_id is None:
                continue

            unit_obj = attrs.get('unit_component', {})
            unit_id = unit_obj.get('id') if isinstance(unit_obj, dict) else None

            value = attrs.get('value_component', '')
            entry = {
                'value': str(value) if value else '',
                'unit': unit_map.get(unit_id, '')
            }
            grouped.setdefault(str(proc_id), []).append(entry)

        return grouped

    def _get_document_column(self, op_ids):
        """Batch-запрос документов для всех операций."""
        ids_str = ", ".join(f"#{oid}" for oid in op_ids)

        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_document_reference(.item IN ({ids_str}))}}
        END_SELECT"""
        refs = query_apl(self.db_api, query, "Doc refs for operations")

        # Collect doc IDs and map ref → operation
        doc_ids = []
        ref_to_op = {}  # doc_id → op_id
        for inst in refs.get('instances', []):
            attrs = inst.get('attributes', {})
            item_ref = attrs.get('item', {})
            op_id = item_ref.get('id') if isinstance(item_ref, dict) else None
            assigned = attrs.get('assigned_document', {})
            doc_id = assigned.get('id') if isinstance(assigned, dict) else None
            if op_id and doc_id:
                doc_ids.append(doc_id)
                ref_to_op.setdefault(doc_id, []).append(op_id)

        if not doc_ids:
            return {}

        # Batch resolve document names
        doc_map = {}
        for dinst in batch_query_by_ids(self.db_api, list(set(doc_ids)), "Docs batch"):
            dattrs = dinst.get('attributes', {})
            doc_map[dinst.get('id')] = {
                'name': dattrs.get('name', ''),
                'code': dattrs.get('id', '')
            }

        # Group by operation ID
        grouped = {}
        for doc_id, op_ids_list in ref_to_op.items():
            doc_info = doc_map.get(doc_id, {'name': '', 'code': ''})
            for op_id in op_ids_list:
                grouped.setdefault(str(op_id), []).append(doc_info)

        return grouped
