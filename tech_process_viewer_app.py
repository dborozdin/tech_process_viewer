"""Tech Process Viewer — просмотр технологических процессов.

Порт: 5000
Функции: навигация по изделиям → процессам → фазам → техпроцессам → деталям.

Запуск: python tech_process_viewer_app.py
"""

import json
import os
import sys

# Add parent directory to path so 'tech_process_viewer' package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import jsonify, render_template

from tech_process_viewer.api.app_helpers import create_pss_app, get_api
from tech_process_viewer.api.query_helpers import (
    query_apl, resolve_org_unit, batch_query_by_ids, track_performance
)
from tech_process_viewer.globals import logger

app = create_pss_app(
    __name__,
    static_folder='static',
    template_folder='static/templates',
    port=5000
)

# Register auth blueprint (shared connection management)
from flask_smorest import Api
api = Api(app)
from tech_process_viewer.api.routes.auth import blp as auth_blp
api.register_blueprint(auth_blp)

# Register CRUD routes blueprint
from tech_process_viewer.api.routes.crud_routes import crud_blp
app.register_blueprint(crud_blp)

# ========== HTML Routes ==========

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/processes')
def processes():
    return render_template('processes.html')

@app.route('/phases')
def phases():
    return render_template('phases.html')

@app.route('/technical_processes')
def tech_processes():
    return render_template('tech-processes.html')

@app.route('/technical_process_details')
def details():
    return render_template('technical_process_details.html')



# ========== Business Logic ==========

@track_performance("fetch_aircrafts_from_folder")
def fetch_aircrafts_from_folder():
    """Загрузить список изделий из папки 'Aircrafts'."""
    API = get_api()
    folder_data = API.folders_api.find_folder("Aircrafts")
    if not folder_data:
        logger.debug("Aircrafts folder not found")
        return []

    folder_id, status, content_ids = folder_data
    if not content_ids:
        logger.debug("No content in Aircrafts folder")
        return []

    # Batch: получаем все PDF из папки одним запросом
    pdf_instances = batch_query_by_ids(API, content_ids, "PDFs from Aircrafts folder")

    product_ids = []
    pdf_map = {}
    for inst in pdf_instances:
        attrs = inst.get("attributes", {})
        of_product = attrs.get("of_product", {})
        if isinstance(of_product, dict) and 'id' in of_product:
            product_ids.append(of_product['id'])
            pdf_map[of_product['id']] = inst.get("id")

    if not product_ids:
        return []

    # Batch: получаем все products одним запросом
    product_instances = batch_query_by_ids(API, product_ids, "Products by IDs")

    result = []
    for inst in product_instances:
        attrs = inst.get("attributes", {})
        item = {
            "aircraft_id": pdf_map.get(inst.get("id")),
            "code": attrs.get("id"),
            "name": attrs.get("name"),
            "data_type": "Typical",
            "serial_number": None,
            "release_date": None,
            "repair_date": None,
        }
        result.append(item)

    return result


@track_performance("fetch_processes")
def fetch_processes(aircraft_id: int):
    """Загрузить бизнес-процессы, связанные с изделием."""
    API = get_api()

    query_refs = f"""SELECT NO_CASE
    Ext_
    FROM
    Ext_{{apl_business_process_reference(.item=#{aircraft_id})}}.assigned_process
    END_SELECT"""
    refs_data = query_apl(API, query_refs, "BP references for aircraft")
    process_ids = [inst["id"] for inst in refs_data.get("instances", [])]

    if not process_ids:
        return []

    # Batch: получаем процессы
    ids_str = ", ".join(f"#{pid}" for pid in process_ids)
    query_processes = f"""SELECT NO_CASE
    Ext2
    FROM
    Ext_{{{ids_str}}}
    Ext2{{apl_business_process(.# in #Ext_)}}
    END_SELECT"""
    proc_data = query_apl(API, query_processes, "Business processes by IDs")

    res_type_id = API.resources_api.find_resource_type_by_name("Vreme rada")

    result = []
    for proc in proc_data.get("instances", []):
        attrs = proc.get("attributes", {})
        customized = attrs.get("customized", False)
        bp_id = proc.get("id")
        org_unit = resolve_org_unit(API, bp_id, res_type_id)

        item = {
            "process_id": bp_id,
            "aircraft_id": aircraft_id,
            "name": attrs.get("name"),
            "org_unit": org_unit,
            "process_type": "Customized" if customized else "Typical",
        }
        result.append(item)

    return result


@track_performance("fetch_phases_or_tp")
def fetch_phases_or_tp(process_id: int, element_type='phase_id', parent_element_type='process_id'):
    """Загрузить подпроцессы (фазы, техпроцессы, операции) для бизнес-процесса."""
    API = get_api()

    query_refs = f"""SELECT NO_CASE
    Ext2
    FROM
    Ext_{{#{process_id}}}
    Ext2{{apl_business_process(.# IN #Ext_)}}
    END_SELECT"""
    refs_data = query_apl(API, query_refs, f"BP details for {element_type}")
    insts = refs_data.get("instances", [])

    phases_ids = []
    for inst in insts:
        elements = inst.get("attributes", {}).get('elements')
        if elements is not None:
            for elem in elements:
                phases_ids.append(elem.get('id'))

    if not phases_ids:
        return []

    # Batch: подпроцессы
    ids_str = ", ".join(f"#{pid}" for pid in phases_ids)
    query_processes = f"""SELECT NO_CASE
    Ext2
    FROM
    Ext_{{{ids_str}}}
    Ext2{{apl_business_process(.# in #Ext_)}}
    END_SELECT"""
    proc_data = query_apl(API, query_processes, f"Sub-processes ({element_type})")

    # Batch: типы процессов
    type_ids = []
    for inst in proc_data.get("instances", []):
        if inst.get("type") == "apl_business_process":
            type_obj = inst.get("attributes", {}).get("type", {})
            if isinstance(type_obj, dict) and "id" in type_obj:
                type_ids.append(type_obj["id"])

    type_map = {}
    if type_ids:
        type_instances = batch_query_by_ids(API, type_ids, "BP types")
        for inst in type_instances:
            type_map[inst.get("id")] = inst.get("attributes", {}).get("name", "")

    res_type_id = API.resources_api.find_resource_type_by_name("Vreme rada")

    result = []
    for proc in proc_data.get("instances", []):
        if proc.get("type") != "apl_business_process":
            continue
        attrs = proc.get("attributes", {})
        customized = attrs.get("customized", False)
        bp_id = proc.get("id")

        # Display name format depends on element type
        if element_type == 'tech_proc_id':
            bp_id_attr = attrs.get("id", "")
            display_name = f"{bp_id_attr} : {attrs.get('name')}"
        elif element_type == 'operation_id':
            bp_id_attr = attrs.get("id", "")
            oper_id = bp_id_attr.split()[-1] if bp_id_attr else ""
            display_name = f"{oper_id} : {attrs.get('name')}"
        else:
            type_obj = attrs.get("type", {})
            type_id = type_obj.get("id") if isinstance(type_obj, dict) else None
            type_name = type_map.get(type_id, "") if type_id else ""
            display_name = f"{type_name} : {attrs.get('name')}" if type_name else attrs.get("name")

        org_unit = resolve_org_unit(API, bp_id, res_type_id)

        item = {
            parent_element_type: process_id,
            element_type: bp_id,
            "name": display_name,
            "original_name": attrs.get("name"),
            "description": attrs.get("description", ""),
            "org_unit": org_unit,
            "process_type": "Customized" if customized else "Typical",
        }
        result.append(item)

    return result


@track_performance("get_technical_process_details")
def get_tp_details(tech_proc_id):
    """Загрузить полные детали технологического процесса."""
    API = get_api()

    query_tp = f"""SELECT NO_CASE
    Ext_
    FROM
    Ext_{{apl_business_process(.# = #{tech_proc_id})}}
    END_SELECT"""
    tp_data = query_apl(API, query_tp, "TP details")

    if not tp_data.get("instances"):
        return None

    tp_attrs = tp_data["instances"][0]["attributes"]
    res_type_id = API.resources_api.find_resource_type_by_name("Vreme rada")
    org_unit = resolve_org_unit(API, tech_proc_id, res_type_id)

    tech_proc = {
        'name': tp_attrs.get('name'),
        'org_unit': org_unit,
        'process_type': "Customized" if tp_attrs.get("customized", False) else "Typical"
    }

    # Operations
    operations = fetch_phases_or_tp(tech_proc_id, element_type='operation_id', parent_element_type='tech_proc_id')
    for op in operations:
        op['man_hours'] = ""
        if res_type_id:
            resource_id = API.resources_api.find_resource_by_bp_and_type(op['operation_id'], res_type_id)
            if resource_id:
                resource_data = API.resources_api.find_resource_data_by_id(resource_id)
                if resource_data and 'instances' in resource_data and resource_data['instances']:
                    value = resource_data['instances'][0]['attributes'].get("value_component", "")
                    op['man_hours'] = str(value) if value else ""
        op['steps'] = []
    tech_proc['operations'] = operations

    # Documents (batch) — include ref_id for detach support
    tech_proc['documents'] = []
    query_docs = f"""SELECT NO_CASE
    Ext_
    FROM
    Ext_{{apl_document_reference(.item = #{tech_proc_id})}}
    END_SELECT"""
    docs_data = query_apl(API, query_docs, "Document references for TP")

    doc_ids = []
    doc_ref_map = {}  # doc_sys_id -> ref_sys_id
    for inst in docs_data.get("instances", []):
        assigned_doc = inst.get("attributes", {}).get("assigned_document", {})
        if isinstance(assigned_doc, dict) and 'id' in assigned_doc:
            doc_ids.append(assigned_doc['id'])
            doc_ref_map[assigned_doc['id']] = inst.get('id')

    if doc_ids:
        doc_instances = batch_query_by_ids(API, doc_ids, "Document details (batch)")
        doc_type_ids = []
        for dinst in doc_instances:
            kind = dinst.get("attributes", {}).get('kind', {})
            if isinstance(kind, dict) and 'id' in kind:
                doc_type_ids.append(kind['id'])

        # Batch: типы документов
        doc_type_map = {}
        if doc_type_ids:
            type_instances = batch_query_by_ids(API, doc_type_ids, "Document types (batch)")
            for tinst in type_instances:
                doc_type_map[tinst.get("id")] = tinst.get("attributes", {}).get('product_data_type', '')

        for dinst in doc_instances:
            dattrs = dinst.get("attributes", {})
            kind = dattrs.get('kind', {})
            type_id = kind.get('id') if isinstance(kind, dict) else None
            doc_sys_id = dinst.get('id')
            tech_proc['documents'].append({
                'name': dattrs.get('name', ''),
                'code': dattrs.get('id', ''),
                'type': doc_type_map.get(type_id, ''),
                'doc_sys_id': doc_sys_id,
                'ref_id': doc_ref_map.get(doc_sys_id)
            })

    # Materials (batch where possible)
    tech_proc['materials'] = []
    mat_type_id = API.resources_api.find_resource_type_by_name("Potrošni materijal")
    if mat_type_id:
        query_mats = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_business_process_resource(.process = #{tech_proc_id} AND .type = #{mat_type_id})}}
        END_SELECT"""
        mats_data = query_apl(API, query_mats, "Material resources for TP")

        assembly_pdf_ids = []
        for inst in mats_data.get("instances", []):
            obj = inst.get("attributes", {}).get("object", {})
            if isinstance(obj, dict) and 'id' in obj:
                assembly_pdf_ids.append(obj['id'])

        # For each assembly PDF, find components
        for assembly_pdf_id in assembly_pdf_ids:
            query_assemblies = f"""SELECT NO_CASE
            Ext_
            FROM
            Ext_{{apl_quantified_assembly_component_usage+next_assembly_usage_occurrence(.relating_product_definition = #{assembly_pdf_id})}}
            END_SELECT"""
            assemblies_data = query_apl(API, query_assemblies, "Assemblies for material")

            # Collect related PDF IDs and unit IDs for batch
            related_pdf_ids = []
            unit_ids = []
            assembly_map = {}
            for ainst in assemblies_data.get("instances", []):
                aattrs = ainst.get("attributes", {})
                related_pdf = aattrs.get("related_product_definition", {})
                if isinstance(related_pdf, dict) and 'id' in related_pdf:
                    rpid = related_pdf['id']
                    related_pdf_ids.append(rpid)
                    assembly_map[rpid] = aattrs
                    unit_obj = aattrs.get("unit_component", {})
                    if isinstance(unit_obj, dict) and 'id' in unit_obj:
                        unit_ids.append(unit_obj['id'])

            if not related_pdf_ids:
                continue

            # Batch: related PDFs
            related_instances = batch_query_by_ids(API, related_pdf_ids, "Related PDFs (batch)")
            product_ids = []
            pdf_product_map = {}
            for rinst in related_instances:
                of_product = rinst.get("attributes", {}).get("of_product", {})
                if isinstance(of_product, dict) and 'id' in of_product:
                    product_ids.append(of_product['id'])
                    pdf_product_map[rinst.get("id")] = {
                        'product_id': of_product['id'],
                        'code1': rinst.get("attributes", {}).get('code1', '')
                    }

            # Batch: products
            product_map = {}
            if product_ids:
                prod_instances = batch_query_by_ids(API, product_ids, "Products for materials (batch)")
                for pinst in prod_instances:
                    product_map[pinst.get("id")] = pinst.get("attributes", {})

            # Batch: units
            unit_map = {}
            if unit_ids:
                unit_instances = batch_query_by_ids(API, unit_ids, "Units (batch)")
                for uinst in unit_instances:
                    unit_map[uinst.get("id")] = uinst.get("attributes", {}).get("name", "")

            # Assemble material items
            for rpid, aattrs in assembly_map.items():
                pdf_info = pdf_product_map.get(rpid, {})
                prod_attrs = product_map.get(pdf_info.get('product_id'), {})
                unit_obj = aattrs.get("unit_component", {})
                unit_id = unit_obj.get('id') if isinstance(unit_obj, dict) else None

                tech_proc['materials'].append({
                    'name': prod_attrs.get('name', ''),
                    'code': pdf_info.get('code1', ''),
                    'id': prod_attrs.get('id', ''),
                    'quantity': aattrs.get('value_component', ''),
                    'uom': unit_map.get(unit_id, '')
                })

    # Characteristics
    tech_proc['characteristics'] = []
    try:
        char_values = API.characteristic_api.get_values_for_item(tech_proc_id)
        char_ids_to_resolve = set()
        for val in char_values:
            char_ref = val.get('attributes', {}).get('characteristic', {})
            if isinstance(char_ref, dict) and 'id' in char_ref:
                char_ids_to_resolve.add(char_ref['id'])

        # Batch resolve characteristic names
        char_name_map = {}
        if char_ids_to_resolve:
            char_instances = batch_query_by_ids(API, list(char_ids_to_resolve), "Characteristic definitions (batch)")
            for cinst in char_instances:
                char_name_map[cinst.get('id')] = cinst.get('attributes', {}).get('name', '')

        for val in char_values:
            attrs = val.get('attributes', {})
            char_ref = attrs.get('characteristic', {})
            char_id = char_ref.get('id') if isinstance(char_ref, dict) else None
            parsed = API.characteristic_api._extract_display_value(val)
            tech_proc['characteristics'].append({
                'sys_id': val.get('id'),
                'characteristic_name': char_name_map.get(char_id, ''),
                'characteristic_id': char_id,
                'value': parsed.get('value', ''),
                'subtype': val.get('type', ''),
                'unit': parsed.get('unit', '')
            })
    except Exception as e:
        logger.error(f"Error loading characteristics: {e}")

    return tech_proc


# ========== API Routes ==========

@app.route('/api/aircraft')
def get_aircraft():
    API = get_api()
    if API is None or API.connect_data is None:
        return jsonify({'error': 'Not connected to DB'}), 400
    data = fetch_aircrafts_from_folder()
    return jsonify(data)

@app.route('/api/processes/<aircraft_id>')
def get_processes(aircraft_id):
    API = get_api()
    if API is None or API.connect_data is None:
        return jsonify({'error': 'Not connected to DB'}), 400
    return jsonify(fetch_processes(int(aircraft_id)))

@app.route('/api/phases/<process_id>')
def get_phases(process_id):
    API = get_api()
    if API is None or API.connect_data is None:
        return jsonify({'error': 'Not connected to DB'}), 400
    return jsonify(fetch_phases_or_tp(int(process_id), element_type='phase_id', parent_element_type='process_id'))

@app.route('/api/technical_processes/<phase_id>')
def get_technical_processes(phase_id):
    API = get_api()
    if API is None or API.connect_data is None:
        return jsonify({'error': 'Not connected to DB'}), 400
    return jsonify(fetch_phases_or_tp(int(phase_id), element_type='tech_proc_id', parent_element_type='phase_id'))

@app.route('/api/technical_process_details/<tech_proc_id>', methods=['GET'])
def get_technical_process_details(tech_proc_id):
    API = get_api()
    if API is None or API.connect_data is None:
        return jsonify({'error': 'Not connected to DB'}), 400

    result = get_tp_details(int(tech_proc_id))
    if result is None:
        return jsonify({'error': 'Technical process not found'}), 404
    return jsonify(result)


# ========== Startup ==========

with app.app_context():
    print(" * Tech Process Viewer: http://localhost:5000/")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
