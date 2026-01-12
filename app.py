from flask import Flask, render_template, jsonify, request
import os
import json
import requests
from api.pss_api import DatabaseAPI
from globals import logger, resource_path
import logging

app = Flask(__name__, static_folder='static', static_url_path='', template_folder='static/templates')

BASE_DIR = os.path.dirname(__file__)
API= None

# Helper functions to load data from JSON files
def load_json(file_name):
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            print(f'Loading data from file: {file_name}')
            return json.load(f)
    except FileNotFoundError:
        return []

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

def query_apl(query: str, description: str=None) -> dict:
    global API
    """Выполняет запрос к APL и возвращает JSON."""
    print(f'----------------------- query_apl ({description}) ------------------------')
    print(f'Executing DB query: {query}')
    HEADERS = {
        "X-APL-SessionKey": API.connect_data['session_key'],
        "Content-Type": "application/json",
        "Cookie": f"X-Apl-SessionKey={API.connect_data['session_key']}"
    }
    BASE_URL = API.URL_QUERY
    response = requests.post(BASE_URL, headers=HEADERS, data=query.encode("utf-8"))
    response.raise_for_status()
    result = response.json()
    print(f'DB query result: {result}')
    return result


def fetch_aircrafts():
    global API
    # 1) Получаем версии aircrafts
    query_versions = """SELECT NO_CASE
    Ext2
    FROM
    Ext_{apl_folder(.name LIKE 'Aircrafts')}.content
    Ext2{apl_product_definition_formation(.# IN #Ext_)}
    END_SELECT"""
    versions_data = query_apl(query_versions)

    print(f'versions_data={versions_data}')

    # собираем ID версий
    version_ids = [inst["id"] for inst in versions_data.get("instances", [])]
    if not version_ids:
        return []

    # 2) Получаем данные для типа изделий по этим версиям
    ids_str = ", ".join(f"#{vid}" for vid in version_ids)
    query_products = f"""SELECT NO_CASE
    Ext2
    FROM
    Ext_{{{ids_str}}}
    Ext2{{apl_product_definition_formation(.# in #Ext_)}}.of_product
    END_SELECT"""
    products_data = query_apl(query_products)
    print(f'products_data={products_data}')

    # маппинг id -> продукт
    products_map = {
        inst["id"]: inst for inst in products_data.get("instances", [])
    }
    print(f'products_map={products_map}')

    # 3) Формируем целевой JSON
    result = []
    for inst in versions_data.get("instances", []):
        attrs = inst.get("attributes", {})
        print(f'attrs={attrs}')
        aircraft_id = inst.get("id")
        print(f'aircraft_id={aircraft_id}')
        product_id = attrs.get("of_product").get("id")
        print(f'product_id={product_id}')

        # пробуем найти продукт по id (через of_product)
        product = products_map.get(product_id, {})
        print(f'product={product}')
        product_attrs = product.get("attributes", {}) if product else {}
        print(f'product_attrs={product_attrs}')

        item = {
            "aircraft_id": aircraft_id,
            "code": product_attrs.get("id"),              # id из attributes версии
            "name": product_attrs.get("name"),            # name из attributes версии
            "data_type": "Typical",  # тип берем из продукта (пример)
            "serial_number": None,
            "release_date": None,                 # нет в JSON, ставим None
            "repair_date": None,
            "user_id": 1
        }
        result.append(item)

    return result

@app.route('/api/dblist')
def get_db_list():
    try:
        response = requests.get('http://localhost:7239/rest/dblist/')
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def fetch_aircrafts_from_folder():
    global API
    print(f'----------------------- fetch_aircrafts_from_folder ------------------------')
    # Find the "Aircrafts" folder
    folder_data = API.folders_api.find_folder("Aircrafts")
    if not folder_data:
        print("Aircrafts folder not found")
        return []

    folder_id, status, content_ids = folder_data
    if not content_ids:
        print("No content in Aircrafts folder")
        return []

    # content_ids are apl_product_definition_formation ids
    # Query to get the of_product ids
    ids_str = ", ".join(f"#{cid}" for cid in content_ids)
    query_pdf = f"""SELECT NO_CASE
    Ext_
    FROM
    Ext_{{{ids_str}}}
    END_SELECT"""
    pdf_data = query_apl(query= query_pdf, description="Get apl_product_definition_formation instances from Aircrafts folder")
    print(f'PDF query data: {pdf_data}')

    product_ids = []
    pdf_map = {}
    for inst in pdf_data.get("instances", []):
        attrs = inst.get("attributes", {})
        of_product = attrs.get("of_product", {})
        if isinstance(of_product, dict) and 'id' in of_product:
            product_ids.append(of_product['id'])
            pdf_map[of_product['id']] = inst.get("id")  # product_id -> pdf_id

    print(f'Product IDs: {product_ids}')

    if not product_ids:
        print("No product IDs found")
        return []

    # Query for the products
    prod_ids_str = ", ".join(f"#{pid}" for pid in product_ids)
    query_products = f"""SELECT NO_CASE
    Ext_
    FROM
    Ext_{{{prod_ids_str}}}
    END_SELECT"""
    products_data = query_apl(query_products, description="Get products by IDs from apl_product_definition_formation")
    print(f'Products query data: {products_data}')

    result = []
    for inst in products_data.get("instances", []):
        attrs = inst.get("attributes", {})
        prod_id = attrs.get("id")
        prod_name = attrs.get("name")
        aircraft_id = pdf_map.get(inst.get("id"))
        item = {
            "aircraft_id": aircraft_id,
            "code": prod_id,
            "name": prod_name,
            "data_type": "Typical",
            "serial_number": None,
            "release_date": None,
            "repair_date": None,
            "user_id": 1
        }
        result.append(item)

    return result

@app.route('/api/connect', methods=['POST'])
def connect_db():
    global API
    try:
        data = request.get_json()
        server_port = data.get('server_port', 'http://localhost:7239')
        db = data.get('db', 'pss_moma_08_07_2025')
        user = data.get('user', 'Administrator')
        password = data.get('password', '')

        # Assuming password is not used in credentials, as per original
        credentials = f'user={user}&db={db}'
        URL_DB_API = server_port + '/rest'
        API = DatabaseAPI(URL_DB_API, credentials)

        session_key = API.reconnect_db()
        if session_key is None:
            return jsonify({'connected': False, 'message': 'Failed to connect to DB'}), 500

        return jsonify({'connected': True, 'session_key': session_key, 'db': db, 'user': user})
    except Exception as e:
        return jsonify({'connected': False, 'message': str(e)}), 500

@app.route('/api/aircraft')
def get_aircraft():
    global API
    if API is None or API.connect_data is None:
        return jsonify({'error': 'Not connected to DB'}), 400

    # Get products from "Aircrafts" folder
    data = fetch_aircrafts_from_folder()
    print(f'get_aircraft result={data}')
    return jsonify(data)


def fetch_processes(aircraft_id: int):
    global API
    # 1) Получаем id процессов, связанных с aircraft
    query_refs = f"""SELECT NO_CASE
    Ext_
    FROM
    Ext_{{apl_business_process_reference(.item=#{aircraft_id})}}.assigned_process
    END_SELECT"""
    refs_data = query_apl(query_refs, description="Get business process references for aircraft")
    process_ids = [inst["id"] for inst in refs_data.get("instances", [])]

    if not process_ids:
        return []

    # 2) Получаем данные процессов
    ids_str = ", ".join(f"#{pid}" for pid in process_ids)
    query_processes = f"""SELECT NO_CASE
    Ext2
    FROM
    Ext_{{{ids_str}}}
    Ext2{{apl_business_process(.# in #Ext_)}}
    END_SELECT"""
    proc_data = query_apl(query_processes, description="Get business processes by IDs")

    # Get resource type for "Vreme rada"
    res_type_id = API.resources_api.find_resource_type_by_name("Vreme rada")

    result = []
    for proc in proc_data.get("instances", []):
        attrs = proc.get("attributes", {})
        customized = attrs.get("customized", False)
        process_type = "Customized" if customized else "Typical"
        bp_id = proc.get("id")
        org_unit = ""
        if res_type_id:
            resource_id = API.resources_api.find_resource_by_bp_and_type(bp_id, res_type_id)
            if resource_id:
                resource_data = API.resources_api.find_resource_data_by_id(resource_id)
                if resource_data and 'instances' in resource_data and resource_data['instances']:
                    res_attrs = resource_data['instances'][0]['attributes']
                    org_obj = res_attrs.get("object")
                    if isinstance(org_obj, dict) and 'id' in org_obj:
                        org_sys_id = org_obj['id']
                        org_data = API.org_api.find_organization_data_by_sys_id(org_sys_id)
                        if org_data and 'instances' in org_data and org_data['instances']:
                            org_attrs = org_data['instances'][0]['attributes']
                            org_unit = org_attrs.get("id", "")
        item = {
            "process_id": bp_id,
            "aircraft_id": aircraft_id,
            "name": attrs.get("name"),
            "org_unit": org_unit,
            "process_type": process_type,
        }
        result.append(item)

    return result

@app.route('/api/processes/<aircraft_id>')
def get_processes(aircraft_id):
    global API
    if API is None or API.connect_data is None:
        return jsonify({'error': 'Not connected to DB'}), 400

    processes = fetch_processes(aircraft_id)
    print(json.dumps(processes, indent=2, ensure_ascii=False))
    return jsonify(processes)

    #filepath = os.path.join(BASE_DIR, 'processes.json')
    #with open(filepath, 'r') as f:
        #data = json.load(f)
        #print(f'Opened file {filepath}')
        #print(f'data={data}')
        #print(f'aircraft_id={aircraft_id}')
        #result_data = [item for item in data if str(item.get('aircraft_id')) == aircraft_id]
        #print(f'get_processes result={result_data}')
        #return jsonify(result_data)

def fetch_phases_or_tp(process_id: int, element_type='phase_id', parent_element_type='process_id'):
    global API
    # 1) Получаем id процессов, связанных с вышестоящим
    query_refs = f"""SELECT NO_CASE
    Ext2
    FROM
    Ext_{{#{process_id}}}
    Ext2{{apl_business_process(.# IN #Ext_)}}
    END_SELECT"""
    print(f'fetch_phases query: {query_refs}')
    refs_data = query_apl(query_refs, description="Get business process details by process ID")
    insts = refs_data.get("instances", [])
    print(f'inst_ids: {insts}')
    phases_ids=[]
    for inst in insts:
        elements= inst.get("attributes", []).get('elements')
        if elements is not None:
            for elem in elements:
                phases_ids.append(elem.get('id'))

    if not phases_ids:
        return []

    # 2) Получаем данные процессов
    ids_str = ", ".join(f"#{pid}" for pid in phases_ids)
    query_processes = f"""SELECT NO_CASE
    Ext2
    FROM
    Ext_{{{ids_str}}}
    Ext2{{apl_business_process(.# in #Ext_)}}
    END_SELECT"""
    proc_data = query_apl(query_processes, description="Get subprocesses (phases/technical processes) by IDs")

    # Собираем type_ids
    type_ids = []
    for inst in proc_data.get("instances", []):
        if inst.get("type") == "apl_business_process":
            type_obj = inst.get("attributes", {}).get("type", {})
            if isinstance(type_obj, dict) and "id" in type_obj:
                type_ids.append(type_obj["id"])

    # Получаем type_names
    type_map = {}
    if type_ids:
        type_ids_str = ", ".join(f"#{tid}" for tid in type_ids)
        query_types = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{{type_ids_str}}}
        END_SELECT"""
        types_data = query_apl(query_types, description="Get business process types by IDs")
        for inst in types_data.get("instances", []):
            type_id = inst.get("id")
            type_name = inst.get("attributes", {}).get("name", "")
            type_map[type_id] = type_name

    # Get resource type for "Vreme rada"
    res_type_id = API.resources_api.find_resource_type_by_name("Vreme rada")

    result = []
    for proc in proc_data.get("instances", []):
        if proc.get("type") != "apl_business_process":
            continue
        attrs = proc.get("attributes", {})
        customized = attrs.get("customized", False)
        process_type = "Customized" if customized else "Typical"
        bp_id = proc.get("id")
        # Получаем display_name
        if element_type == 'tech_proc_id':
            # Для техпроцессов: id : name
            bp_id_attr = attrs.get("id", "")
            display_name = f"{bp_id_attr} : {attrs.get('name')}"
        else:
            # Для фаз: type_name : name
            type_obj = attrs.get("type", {})
            type_id = type_obj.get("id") if isinstance(type_obj, dict) else None
            type_name = type_map.get(type_id, "") if type_id else ""
            display_name = f"{type_name} : {attrs.get('name')}" if type_name else attrs.get("name")
        org_unit = ""
        if res_type_id:
            resource_id = API.resources_api.find_resource_by_bp_and_type(bp_id, res_type_id)
            if resource_id:
                resource_data = API.resources_api.find_resource_data_by_id(resource_id)
                if resource_data and 'instances' in resource_data and resource_data['instances']:
                    res_attrs = resource_data['instances'][0]['attributes']
                    org_obj = res_attrs.get("object")
                    if isinstance(org_obj, dict) and 'id' in org_obj:
                        org_sys_id = org_obj['id']
                        org_data = API.org_api.find_organization_data_by_sys_id(org_sys_id)
                        if org_data and 'instances' in org_data and org_data['instances']:
                            org_attrs = org_data['instances'][0]['attributes']
                            org_unit = org_attrs.get("id", "")
        item = {
            parent_element_type: process_id,
            element_type: bp_id,
            "name": display_name,
            "original_name": attrs.get("name"),
            "description": attrs.get("name"),  # Use name as description for now
            "org_unit": org_unit,
            "process_type": process_type,
        }
        result.append(item)

    return result

@app.route('/api/phases/<process_id>')
def get_phases(process_id):
    global API
    if API is None or API.connect_data is None:
        return jsonify({'error': 'Not connected to DB'}), 400

    phases = fetch_phases_or_tp(process_id, element_type='phase_id', parent_element_type='process_id')
    print(json.dumps(phases, indent=2, ensure_ascii=False))
    return jsonify(phases)

    #filepath = os.path.join(BASE_DIR, 'phases.json')
    #with open(filepath, 'r') as f:
        #data = json.load(f)
        #print(f'Opened file {filepath}')
        #result_data= [item for item in data if str(item.get('process_id')) == process_id]
        #print(f'get_phases result={result_data}')
        #return jsonify(result_data)

@app.route('/api/technical_processes/<phase_id>')
def get_technical_processes(phase_id):
    global API
    if API is None or API.connect_data is None:
        return jsonify({'error': 'Not connected to DB'}), 400

    technical_processes = fetch_phases_or_tp(phase_id, element_type='tech_proc_id', parent_element_type='phase_id')
    print(json.dumps(technical_processes, indent=2, ensure_ascii=False))
    return jsonify(technical_processes)

    #filepath = os.path.join(BASE_DIR, 'technical_processes.json')
    #with open(filepath, 'r') as f:
        #data = json.load(f)
        #print(f'Opened file {filepath}')
        #result_data = [item for item in data if str(item.get('phase_id')) == phase_id]
        #print(f'get_technical_processes result={result_data}')
        #return jsonify(result_data)

@app.route('/api/technical_process_details/<tech_proc_id>', methods=['GET'])
def get_technical_process_details(tech_proc_id):
    global API
    if API is None or API.connect_data is None:
        return jsonify({'error': 'Not connected to DB'}), 400

    print(f'get_technical_process_details')
    print(f'tech_proc_id: {tech_proc_id}')

    # Query for the technical process details from database
    query_tp = f"""SELECT NO_CASE
    Ext_
    FROM
    Ext_{{apl_business_process(.# = #{tech_proc_id})}}
    END_SELECT"""
    tp_data = query_apl(query_tp, description="Get technical process details by ID")

    if not tp_data.get("instances"):
        return jsonify({'error': 'Technical process not found'}), 404

    tp_attrs = tp_data["instances"][0]["attributes"]
    customized = tp_attrs.get("customized", False)
    process_type = "Customized" if customized else "Typical"

    # Get org_unit from resource
    org_unit = ""
    res_type_id = API.resources_api.find_resource_type_by_name("Vreme rada")
    if res_type_id:
        resource_id = API.resources_api.find_resource_by_bp_and_type(tech_proc_id, res_type_id)
        if resource_id:
            resource_data = API.resources_api.find_resource_data_by_id(resource_id)
            if resource_data and 'instances' in resource_data and resource_data['instances']:
                res_attrs = resource_data['instances'][0]['attributes']
                org_obj = res_attrs.get("object")
                if isinstance(org_obj, dict) and 'id' in org_obj:
                    org_sys_id = org_obj['id']
                    org_data = API.org_api.find_organization_data_by_sys_id(org_sys_id)
                    if org_data and 'instances' in org_data and org_data['instances']:
                        org_attrs = org_data['instances'][0]['attributes']
                        org_unit = org_attrs.get("id", "")

    tech_proc = {
        'name': tp_attrs.get('name'),
        'org_unit': org_unit,
        'process_type': process_type
    }

    # Fetch operations from DB (sub-business processes)
    operations = fetch_phases_or_tp(tech_proc_id, element_type='operation_id', parent_element_type='tech_proc_id')
    # For each operation, get man_hours from resource "Vreme rada"
    for op in operations:
        op['man_hours'] = ""
        if res_type_id:
            resource_id = API.resources_api.find_resource_by_bp_and_type(op['operation_id'], res_type_id)
            if resource_id:
                resource_data = API.resources_api.find_resource_data_by_id(resource_id)
                if resource_data and 'instances' in resource_data and resource_data['instances']:
                    res_attrs = resource_data['instances'][0]['attributes']
                    value = res_attrs.get("value_component", "")
                    op['man_hours'] = str(value) if value else ""
        # For steps, load from JSON for now (assuming steps are not in DB)
        op['steps'] = []  # TODO: implement steps from DB if needed
    tech_proc['operations'] = operations

    # Fetch documents from document references
    tech_proc['documents'] = []
    query_docs = f"""SELECT NO_CASE
    Ext_
    FROM
    Ext_{{apl_document_reference(.item = #{tech_proc_id})}}
    END_SELECT"""
    docs_data = query_apl(query_docs, description="Get document references for technical process")
    for inst in docs_data.get("instances", []):
        attrs = inst.get("attributes", {})
        assigned_doc = attrs.get("assigned_document", {})
        if isinstance(assigned_doc, dict) and 'id' in assigned_doc:
            doc_id = assigned_doc['id']
            # Get document details
            query_doc = f"""SELECT NO_CASE
            Ext_
            FROM
            Ext_{{#{doc_id}}}
            END_SELECT"""
            doc_data = query_apl(query_doc, description="Get document details")
            if doc_data.get("instances"):
                doc_attrs = doc_data["instances"][0]["attributes"]
                doc_item = {
                    'name': doc_attrs.get('name', ''),
                    'code': doc_attrs.get('id', ''),
                    'type': ''  # TODO: get type if needed
                }
                tech_proc['documents'].append(doc_item)

    # Fetch materials from resources
    tech_proc['materials'] = []
    # Assume material resource type is "Materijal" or find all resources
    mat_type_id = API.resources_api.find_resource_type_by_name("Materijal")
    if mat_type_id:
        query_mats = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_business_process_resource(.process = #{tech_proc_id} AND .type = #{mat_type_id})}}
        END_SELECT"""
        mats_data = query_apl(query_mats, description="Get material resources for technical process")
        for inst in mats_data.get("instances", []):
            attrs = inst.get("attributes", {})
            obj = attrs.get("object", {})
            if isinstance(obj, dict) and 'id' in obj:
                mat_id = obj['id']
                # Assume the object is a product or material entity
                query_mat = f"""SELECT NO_CASE
                Ext_
                FROM
                Ext_{{#{mat_id}}}
                END_SELECT"""
                mat_data = query_apl(query_mat, description="Get material details")
                if mat_data.get("instances"):
                    mat_attrs = mat_data["instances"][0]["attributes"]
                    unit_obj = attrs.get("unit_component", {})
                    unit_name = ""
                    if isinstance(unit_obj, dict) and 'id' in unit_obj:
                        unit_id = unit_obj['id']
                        query_unit = f"""SELECT NO_CASE
                        Ext_
                        FROM
                        Ext_{{#{unit_id}}}
                        END_SELECT"""
                        unit_data = query_apl(query_unit, description="Get unit details")
                        if unit_data.get("instances"):
                            unit_attrs = unit_data["instances"][0]["attributes"]
                            unit_name = unit_attrs.get("name", "")
                    mat_item = {
                        'name': mat_attrs.get('name', ''),
                        'code': mat_attrs.get('id', ''),
                        'id': mat_attrs.get('id', ''),
                        'standart': '',  # TODO: if applicable
                        'uom': unit_name
                    }
                    tech_proc['materials'].append(mat_item)

    print(f'Technical process data={tech_proc}')
    return jsonify(tech_proc)

if __name__ == '__main__':
    app.run(debug=True)
