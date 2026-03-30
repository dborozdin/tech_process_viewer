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

        # Batch resolve organization names
        org_ids = []
        for inst in proc_data.get("instances", []):
            org_obj = inst.get("attributes", {}).get("organization", {})
            if isinstance(org_obj, dict) and "id" in org_obj:
                org_ids.append(org_obj["id"])
        org_map = {}
        if org_ids:
            for oinst in batch_query_by_ids(self.db_api, list(set(org_ids)), "Org units"):
                org_map[oinst["id"]] = oinst.get("attributes", {}).get("id", "")

        result = []
        for proc in proc_data.get("instances", []):
            attrs = proc.get("attributes", {})
            bp_id = proc.get("id")

            type_obj = attrs.get("type", {})
            type_id = type_obj.get("id") if isinstance(type_obj, dict) else None
            resolved_type_name = type_map.get(type_id, "") if type_id else ""

            org_obj = attrs.get("organization", {})
            org_id = org_obj.get("id") if isinstance(org_obj, dict) else None
            org_unit = org_map.get(org_id, "") if org_id else ""

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
        """Получить атрибуты процесса и список операций.

        Документы, материалы, man_hours НЕ загружаются — они доступны
        через отдельные эндпоинты (lazy-load при открытии вкладки).
        """
        query_tp = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_business_process(.# = #{tech_proc_id})}}
        END_SELECT"""
        tp_data = query_apl(self.db_api, query_tp, "TP details")

        if not tp_data.get("instances"):
            return None

        tp_attrs = tp_data["instances"][0]["attributes"]

        # Resolve type name (batch — 1 query)
        type_name = ""
        type_obj = tp_attrs.get("type", {})
        if isinstance(type_obj, dict) and "id" in type_obj:
            type_instances = batch_query_by_ids(self.db_api, [type_obj["id"]], "BP type")
            if type_instances:
                type_name = type_instances[0].get("attributes", {}).get("name", "")

        # Org unit from process attributes (no extra query if already in attrs)
        org_unit = ""
        org_obj = tp_attrs.get("organization", {})
        if isinstance(org_obj, dict) and "id" in org_obj:
            org_instances = batch_query_by_ids(self.db_api, [org_obj["id"]], "Org unit")
            if org_instances:
                org_unit = org_instances[0].get("attributes", {}).get("id", "")

        result = {
            'sys_id': tech_proc_id,
            'id': tp_attrs.get('id', ''),
            'name': tp_attrs.get('name'),
            'description': tp_attrs.get('description', ''),
            'org_unit': org_unit,
            'type_name': type_name,
            'process_type': "Customized" if tp_attrs.get("customized", False) else "Typical",
        }

        # Operations (sub-processes) — batch load
        operations = self._get_sub_processes(
            tech_proc_id, element_type='operation_id', parent_element_type='tech_proc_id'
        )
        result['operations'] = operations

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

        # Batch resolve organization names (from process 'organization' attr)
        org_ids = []
        for proc in proc_data.get("instances", []):
            if proc.get("type") != "apl_business_process":
                continue
            org_obj = proc.get("attributes", {}).get("organization", {})
            if isinstance(org_obj, dict) and "id" in org_obj:
                org_ids.append(org_obj["id"])
        org_map = {}
        if org_ids:
            for oinst in batch_query_by_ids(self.db_api, list(set(org_ids)), "Org units"):
                org_map[oinst["id"]] = oinst.get("attributes", {}).get("id", "")

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

            org_obj = attrs.get("organization", {})
            org_id = org_obj.get("id") if isinstance(org_obj, dict) else None
            org_unit = org_map.get(org_id, "") if org_id else ""

            av_obj = attrs.get("active_version", {})
            active_version_id = av_obj.get("id") if isinstance(av_obj, dict) else None

            # Extract resource IDs from aggregated list
            raw_resources = attrs.get("resources", [])
            resource_ids = []
            if isinstance(raw_resources, list):
                for r in raw_resources:
                    if isinstance(r, dict) and 'id' in r:
                        resource_ids.append(r['id'])
                    elif isinstance(r, (int, str)):
                        resource_ids.append(int(r))

            # Check if process has child elements
            raw_elements = attrs.get("elements", [])
            has_children = bool(raw_elements and isinstance(raw_elements, list) and len(raw_elements) > 0)

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
                "active_version_id": active_version_id,
                "resource_ids": resource_ids,
                "has_children": has_children,
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
        """Получить материалы для техпроцесса.

        Материал = ресурс процесса, у которого object — это
        apl_product_definition_formation с formation_type = "kit".
        Затем загружается состав этого kit (assembly components).
        """
        # 1) Все ресурсы процесса (1 запрос)
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_business_process_resource(.process = #{tech_proc_id})}}
        END_SELECT"""
        res_data = query_apl(self.db_api, query, "All resources for materials")

        # 2) Собрать object IDs, batch-загрузить, отфильтровать kit
        obj_ids = []
        res_by_obj = {}
        for inst in res_data.get("instances", []):
            obj = inst.get("attributes", {}).get("object", {})
            if isinstance(obj, dict) and 'id' in obj:
                obj_ids.append(obj['id'])
                res_by_obj[obj['id']] = inst

        if not obj_ids:
            return []

        obj_instances = batch_query_by_ids(self.db_api, list(set(obj_ids)), "Resource objects")
        kit_pdf_ids = []
        for oinst in obj_instances:
            if oinst.get('type') == 'apl_product_definition_formation':
                if oinst.get('attributes', {}).get('formation_type') == 'kit':
                    kit_pdf_ids.append(oinst['id'])

        if not kit_pdf_ids:
            return []

        # 3) Для каждого kit — загрузить состав (assembly components)
        materials = []
        for kit_id in kit_pdf_ids:
            query_asm = f"""SELECT NO_CASE
            Ext_
            FROM
            Ext_{{apl_quantified_assembly_component_usage+next_assembly_usage_occurrence(.relating_product_definition = #{kit_id})}}
            END_SELECT"""
            asm_data = query_apl(self.db_api, query_asm, "Kit components")

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

            # Batch: related PDFs → products → names
            related_insts = batch_query_by_ids(self.db_api, related_ids, "Related PDFs")
            product_ids = []
            pdf_map = {}
            for rinst in related_insts:
                of_product = rinst.get("attributes", {}).get("of_product", {})
                if isinstance(of_product, dict) and 'id' in of_product:
                    product_ids.append(of_product['id'])
                    pdf_map[rinst['id']] = {
                        'product_id': of_product['id'],
                        'code1': rinst.get("attributes", {}).get('code1', '')
                    }

            prod_map = {}
            if product_ids:
                for pinst in batch_query_by_ids(self.db_api, product_ids, "Products"):
                    prod_map[pinst['id']] = pinst.get("attributes", {})

            unit_map = {}
            if unit_ids:
                for uinst in batch_query_by_ids(self.db_api, unit_ids, "Units"):
                    unit_map[uinst['id']] = uinst.get("attributes", {}).get("name", "")

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

        # 1) Process attribute columns (static, no DB query needed for data)
        result.extend([
            {'category': 'attribute', 'key': 'attr_designation',   'label': 'Обозначение'},
            {'category': 'attribute', 'key': 'attr_original_name', 'label': 'Наименование'},
            {'category': 'attribute', 'key': 'attr_type',          'label': 'Тип процесса'},
            {'category': 'attribute', 'key': 'attr_customized',    'label': 'Типовой / Кастомизированный'},
            {'category': 'attribute', 'key': 'attr_version',       'label': 'Версия'},
        ])

        # 2) Resource types from DB
        # list_resource_types() returns a list (not dict with 'instances')
        res_types = self.db_api.resources_api.list_resource_types(limit=200)
        if res_types:
            for inst in res_types:
                attrs = inst.get('attributes', {})
                result.append({
                    'category': 'resource',
                    'key': f"res_{inst['id']}",
                    'label': attrs.get('name', f"Ресурс #{inst['id']}"),
                    'sys_id': inst['id']
                })

        # 3) Characteristics from DB (via CharacteristicAPI)
        char_instances = self.db_api.characteristic_api.list_characteristics()
        for inst in char_instances:
            attrs = inst.get('attributes', {})
            result.append({
                'category': 'characteristic',
                'key': f"char_{inst['id']}",
                'label': attrs.get('name', f"Характеристика #{inst['id']}"),
                'sys_id': inst['id']
            })

        return result

    @track_performance("get_operation_column_data")
    def get_operation_column_data(self, tech_proc_id, column_keys, self_mode=False):
        """Получить данные динамических колонок для операций техпроцесса.

        Args:
            self_mode: если True — данные для самого процесса (листовой узел без подпроцессов)

        Оптимизация: batch-загрузка ресурсов и характеристик.
        - Ресурсы: 1 batch-запрос по resource_ids из подпроцессов → фильтр по типу в Python
        - Характеристики: 1 batch по active_version → 1 batch char_value_versions → фильтр
        - Версии: 1 batch-запрос
        - Атрибуты: 0 запросов (из данных подпроцессов)
        """
        if self_mode:
            # Leaf process: load the process itself as a single "operation"
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{apl_business_process(.# = #{tech_proc_id})}} END_SELECT"
            data = query_apl(self.db_api, query, "Self process for columns")
            if not data or not data.get('instances'):
                return {}
            inst = data['instances'][0]
            attrs = inst.get('attributes', {})
            raw_resources = attrs.get('resources', [])
            resource_ids = []
            if isinstance(raw_resources, list):
                for r in raw_resources:
                    rid = r.get('id') if isinstance(r, dict) else r
                    if rid:
                        resource_ids.append(int(rid) if not isinstance(rid, int) else rid)
            av_obj = attrs.get('active_version', {})
            operations = [{
                'operation_id': tech_proc_id,
                'designation': attrs.get('id', ''),
                'original_name': attrs.get('name', ''),
                'type_name': '',
                'process_type': 'Customized' if attrs.get('customized', False) else 'Typical',
                'active_version_id': av_obj.get('id') if isinstance(av_obj, dict) else None,
                'resource_ids': resource_ids,
            }]
        else:
            operations = self._get_sub_processes(
                tech_proc_id, element_type='operation_id', parent_element_type='tech_proc_id'
            )
        op_ids = [op['operation_id'] for op in operations]
        if not op_ids:
            return {}

        # Determine what data we need to batch-load
        res_keys = [k for k in column_keys if k.startswith('res_')]
        char_keys = [k for k in column_keys if k.startswith('char_')]
        need_version = 'attr_version' in column_keys

        # --- Batch load resources (1 query for ALL resources of ALL operations) ---
        resource_cache = {}  # {op_id_str: [instance, ...]}
        if res_keys:
            all_res_ids = []
            op_by_res_id = {}  # resource_id -> op_id
            for op in operations:
                op_id = op['operation_id']
                for rid in op.get('resource_ids', []):
                    all_res_ids.append(rid)
                    op_by_res_id[rid] = op_id

            if all_res_ids:
                res_instances = batch_query_by_ids(
                    self.db_api, list(set(all_res_ids)), "All resources batch"
                )
                # Collect unit IDs
                unit_ids = set()
                for inst in res_instances:
                    u = inst.get('attributes', {}).get('unit_component', {})
                    if isinstance(u, dict) and 'id' in u:
                        unit_ids.add(u['id'])
                unit_map = {}
                if unit_ids:
                    for uinst in batch_query_by_ids(self.db_api, list(unit_ids), "Units"):
                        unit_map[uinst['id']] = uinst.get('attributes', {}).get('name', '')

                for inst in res_instances:
                    rid = inst.get('id')
                    op_id = op_by_res_id.get(rid)
                    if op_id is None:
                        continue
                    resource_cache.setdefault(str(op_id), []).append((inst, unit_map))

        # --- Batch load characteristic values via versions (2 queries total) ---
        char_cache = {}  # {op_id_str: [{characteristic_id, value}, ...]}
        if char_keys:
            # 1) Batch load active_versions → get characteristic_value_versions
            version_ids = [op['active_version_id'] for op in operations if op.get('active_version_id')]
            if version_ids:
                ver_instances = batch_query_by_ids(
                    self.db_api, list(set(version_ids)), "BP versions for chars"
                )
                ver_to_op = {}
                for op in operations:
                    if op.get('active_version_id'):
                        ver_to_op[op['active_version_id']] = op['operation_id']

                # Collect all characteristic_value_version IDs
                cvv_ids = []
                cvv_to_op = {}
                for vinst in ver_instances:
                    vid = vinst.get('id')
                    op_id = ver_to_op.get(vid)
                    cvv_list = vinst.get('attributes', {}).get('characteristic_value_versions', [])
                    if isinstance(cvv_list, list):
                        for cvv in cvv_list:
                            cvv_id = cvv.get('id') if isinstance(cvv, dict) else cvv
                            if cvv_id:
                                cvv_ids.append(int(cvv_id) if not isinstance(cvv_id, int) else cvv_id)
                                cvv_to_op[cvv_id] = op_id

                # 2) Batch load all characteristic_value_versions
                if cvv_ids:
                    cvv_instances = batch_query_by_ids(
                        self.db_api, list(set(cvv_ids)), "Char value versions batch"
                    )
                    # Collect ref IDs for apl_reference_value resolution
                    ref_ids_to_resolve = []
                    for inst in cvv_instances:
                        attrs = inst.get('attributes', {})
                        char_ref = attrs.get('characteristic', {})
                        char_id = char_ref.get('id') if isinstance(char_ref, dict) else None
                        cvv_id = inst.get('id')
                        op_id = cvv_to_op.get(cvv_id)
                        scope = attrs.get('scope', '')
                        # For reference values, scope may be empty
                        val_ref = attrs.get('val', {})
                        ref_id = None
                        if not scope and isinstance(val_ref, dict) and 'id' in val_ref:
                            ref_id = val_ref['id']
                            ref_ids_to_resolve.append(ref_id)
                        char_cache.setdefault(str(op_id), []).append({
                            'characteristic_id': char_id,
                            'value': str(scope) if scope else '',
                            '_ref_id': ref_id,
                        })

                    # Resolve reference values in one batch
                    if ref_ids_to_resolve:
                        ref_map = {}
                        for rinst in batch_query_by_ids(
                            self.db_api, list(set(ref_ids_to_resolve)), "Char ref values"
                        ):
                            rattrs = rinst.get('attributes', {})
                            ref_map[rinst['id']] = rattrs.get('name', rattrs.get('id', ''))
                        for op_values in char_cache.values():
                            for cv in op_values:
                                if not cv['value'] and cv.get('_ref_id') in ref_map:
                                    cv['value'] = ref_map[cv['_ref_id']]

        # --- Batch load version numbers (1 query) ---
        version_cache = {}  # {op_id_str: version_number}
        if need_version:
            ver_ids = []
            ver_to_op = {}
            for op in operations:
                av_id = op.get('active_version_id')
                if av_id:
                    ver_ids.append(av_id)
                    ver_to_op[av_id] = str(op['operation_id'])
            if ver_ids:
                for vinst in batch_query_by_ids(self.db_api, list(set(ver_ids)), "BP versions"):
                    vid = vinst.get('id')
                    op_id = ver_to_op.get(vid)
                    num = vinst.get('attributes', {}).get('number', '')
                    if op_id and num is not None and num != '':
                        version_cache[op_id] = str(num)

        # --- Build result from caches ---
        result = {}
        for col_key in column_keys:
            if col_key.startswith('attr_') and col_key != 'attr_version':
                # Attributes from already-loaded operations (0 queries)
                FIELD_MAP = {
                    'attr_designation': 'designation',
                    'attr_original_name': 'original_name',
                    'attr_type': 'type_name',
                    'attr_customized': 'process_type',
                }
                field = FIELD_MAP.get(col_key)
                grouped = {}
                if field:
                    for op in operations:
                        v = op.get(field, '')
                        if v:
                            grouped[str(op['operation_id'])] = [{'value': str(v)}]
                result[col_key] = grouped

            elif col_key == 'attr_version':
                result[col_key] = {
                    oid: [{'value': v}] for oid, v in version_cache.items()
                }

            elif col_key.startswith('res_'):
                res_type_id = int(col_key.replace('res_', ''))
                grouped = {}
                for op_id_str, res_list in resource_cache.items():
                    for inst, unit_map in res_list:
                        attrs = inst.get('attributes', {})
                        type_ref = attrs.get('type', {})
                        tid = type_ref.get('id') if isinstance(type_ref, dict) else None
                        if tid != res_type_id:
                            continue
                        u = attrs.get('unit_component', {})
                        uid = u.get('id') if isinstance(u, dict) else None
                        val = attrs.get('value_component', '')
                        grouped.setdefault(op_id_str, []).append({
                            'value': str(val) if val else '',
                            'unit': unit_map.get(uid, '')
                        })
                result[col_key] = grouped

            elif col_key.startswith('char_'):
                char_id = int(col_key.replace('char_', ''))
                grouped = {}
                for op_id_str, cv_list in char_cache.items():
                    for cv in cv_list:
                        if cv.get('characteristic_id') == char_id and cv.get('value'):
                            grouped.setdefault(op_id_str, []).append({
                                'value': cv['value']
                            })
                result[col_key] = grouped

        return result

