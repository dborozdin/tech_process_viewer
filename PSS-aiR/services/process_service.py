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

        res_type_id = self.db_api.resources_api.find_resource_type_by_name("Vreme rada")

        result = []
        for proc in proc_data.get("instances", []):
            attrs = proc.get("attributes", {})
            bp_id = proc.get("id")
            org_unit = resolve_org_unit(self.db_api, bp_id, res_type_id)

            result.append({
                "process_id": bp_id,
                "product_id": product_pdf_id,
                "name": attrs.get("name"),
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

        result = {
            'sys_id': tech_proc_id,
            'name': tp_attrs.get('name'),
            'org_unit': org_unit,
            'process_type': "Customized" if tp_attrs.get("customized", False) else "Typical",
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

            # Display name
            if element_type == 'tech_proc_id':
                display_name = f"{attrs.get('id', '')} : {attrs.get('name')}"
            elif element_type == 'operation_id':
                bp_id_attr = attrs.get("id", "")
                oper_id = bp_id_attr.split()[-1] if bp_id_attr else ""
                display_name = f"{oper_id} : {attrs.get('name')}"
            else:
                type_obj = attrs.get("type", {})
                type_id = type_obj.get("id") if isinstance(type_obj, dict) else None
                type_name = type_map.get(type_id, "") if type_id else ""
                display_name = f"{type_name} : {attrs.get('name')}" if type_name else attrs.get("name")

            org_unit = resolve_org_unit(self.db_api, bp_id, res_type_id)

            result.append({
                parent_element_type: process_id,
                element_type: bp_id,
                "name": display_name,
                "original_name": attrs.get("name"),
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
