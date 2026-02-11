from flask import Flask, render_template, jsonify
import os
import json
import requests
from flask_smorest import Api
from tech_process_viewer.globals import logger, resource_path
from tech_process_viewer.config import config
import logging

# Initialize Flask app
app = Flask(__name__, static_folder='static', static_url_path='', template_folder='static/templates')

# Load configuration
env = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[env])

# Validate production requirements
if env == 'production':
    if not app.config.get('SECRET_KEY'):
        raise ValueError("SECRET_KEY environment variable must be set for production")
    if app.config.get('SECRET_KEY') == 'dev-secret-key-change-in-production':
        raise ValueError("Default SECRET_KEY cannot be used in production")

# Initialize Flask-Smorest for OpenAPI documentation
api = Api(app)

# Register blueprints
from tech_process_viewer.api.routes.auth import blp as auth_blp
from tech_process_viewer.api.routes.business_processes import blp as business_processes_blp
from tech_process_viewer.api.routes.entity_viewer import blp as entity_viewer_blp
from tech_process_viewer.api.routes.products import blp as products_blp
from tech_process_viewer.api.routes.documents import blp as documents_blp
from tech_process_viewer.api.routes.resources import blp as resources_blp
from tech_process_viewer.api.routes.organizations import blp as organizations_blp

api.register_blueprint(auth_blp)  # Auth endpoints first
api.register_blueprint(business_processes_blp)
api.register_blueprint(entity_viewer_blp)
api.register_blueprint(products_blp)
api.register_blueprint(documents_blp)
api.register_blueprint(resources_blp)
api.register_blueprint(organizations_blp)

BASE_DIR = os.path.dirname(__file__)

# Store API instance in app.extensions to ensure it persists across imports
# This is the Flask-recommended way to store global state
if 'pss_api' not in app.extensions:
    app.extensions['pss_api'] = None

def get_api():
    """Get the current API instance"""
    return app.extensions.get('pss_api')

def set_api(api_instance):
    """Set the API instance"""
    app.extensions['pss_api'] = api_instance

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

# Entity Viewer UI routes
@app.route('/entity-viewer')
@app.route('/entity-viewer/')
def entity_viewer_ui():
    """Main entity viewer UI"""
    return render_template('entity_viewer/index.html')

@app.route('/entity-viewer/entity/<entity_name>')
def entity_instances_ui(entity_name):
    """Entity instances list UI"""
    from tech_process_viewer.dict_parser import get_dict_parser
    parser = get_dict_parser()
    entity = parser.get_entity_by_name(entity_name)

    if not entity:
        return "Entity type not found", 404

    return render_template('entity_viewer/instances.html', entity_name=entity_name, entity=entity)

@app.route('/entity-viewer/instance/<int:instance_id>')
def instance_detail_ui(instance_id):
    """Instance detail and edit UI"""
    return render_template('entity_viewer/instance_detail.html', instance_id=instance_id)

def query_apl(query: str, description: str=None) -> dict:
    """Выполняет запрос к APL и возвращает JSON."""
    API = get_api()
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
    API = get_api()
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

def fetch_aircrafts_from_folder():
    API = get_api()
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

@app.route('/api/aircraft')
def get_aircraft():
    API = get_api()
    if API is None or API.connect_data is None:
        return jsonify({'error': 'Not connected to DB'}), 400

    # Get products from "Aircrafts" folder
    data = fetch_aircrafts_from_folder()
    print(f'get_aircraft result={data}')
    return jsonify(data)


def fetch_processes(aircraft_id: int):
    API = get_api()
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
    API = get_api()
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
    API = get_api()
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
        elif element_type == 'operation_id':
            # Для операций: oper_id : name, где oper_id - правая часть id до пробела
            bp_id_attr = attrs.get("id", "")
            oper_id = bp_id_attr.split()[-1] if bp_id_attr else ""
            display_name = f"{oper_id} : {attrs.get('name')}"
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
            "description": attrs.get("description", ""),  # Use description attribute
            "org_unit": org_unit,
            "process_type": process_type,
        }
        result.append(item)

    return result

@app.route('/api/phases/<process_id>')
def get_phases(process_id):
    API = get_api()
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
    API = get_api()
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
    API = get_api()
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
                type_value = ''
                kind = doc_attrs.get('kind', {})
                if isinstance(kind, dict) and 'id' in kind:
                    doc_type_id = kind['id']
                    query_doc_type = f"""SELECT NO_CASE
                    Ext_
                    FROM
                    Ext_{{#{doc_type_id}}}
                    END_SELECT"""
                    doc_type_data = query_apl(query_doc_type, description="Get document type details")
                    if doc_type_data.get("instances"):
                        doc_type_attrs = doc_type_data["instances"][0]["attributes"]
                        type_value = doc_type_attrs.get('product_data_type', '')
                doc_item = {
                    'name': doc_attrs.get('name', ''),
                    'code': doc_attrs.get('id', ''),
                    'type': type_value
                }
                tech_proc['documents'].append(doc_item)

    # Fetch materials from resources
    tech_proc['materials'] = []
    # Assume material resource type is "Potrošni materijal" or find all resources
    mat_type_id = API.resources_api.find_resource_type_by_name("Potrošni materijal")
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
                assembly_pdf_id = obj['id']  # This is the relating_product_definition (assembly)
                # Find incoming assemblies for this pdf
                query_assemblies = f"""SELECT NO_CASE
                Ext_
                FROM
                Ext_{{apl_quantified_assembly_component_usage+next_assembly_usage_occurrence(.relating_product_definition = #{assembly_pdf_id})}}
                END_SELECT"""
                assemblies_data = query_apl(query_assemblies, description="Get assemblies for material resource")
                for assembly_inst in assemblies_data.get("instances", []):
                    assembly_attrs = assembly_inst.get("attributes", {})
                    related_pdf = assembly_attrs.get("related_product_definition", {})
                    if isinstance(related_pdf, dict) and 'id' in related_pdf:
                        related_pdf_id = related_pdf['id']
                        # Get the product from this pdf
                        query_related_pdf = f"""SELECT NO_CASE
                        Ext_
                        FROM
                        Ext_{{#{related_pdf_id}}}
                        END_SELECT"""
                        related_data = query_apl(query_related_pdf, description="Get related product details")
                        if related_data.get("instances"):
                            related_attrs = related_data["instances"][0]["attributes"]
                            of_product = related_attrs.get("of_product", {})
                            if isinstance(of_product, dict) and 'id' in of_product:
                                product_id = of_product['id']
                                # Query the product details
                                query_product = f"""SELECT NO_CASE
                                Ext_
                                FROM
                                Ext_{{#{product_id}}}
                                END_SELECT"""
                                product_data = query_apl(query_product, description="Get product details for material")
                                if product_data.get("instances"):
                                    product_attrs = product_data["instances"][0]["attributes"]
                                    unit_obj = assembly_attrs.get("unit_component", {})
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
                                        'name': product_attrs.get('name', ''),
                                        'code': related_attrs.get('code1', ''),
                                        'id': product_attrs.get('id', ''),
                                        'quantity': assembly_attrs.get('value_component', ''),
                                        'uom': unit_name
                                    }
                                    tech_proc['materials'].append(mat_item)

    print(f'Technical process data={tech_proc}')
    return jsonify(tech_proc)

@app.after_request
def after_request(response):
    """Add OpenAPI spec export after each request in development mode"""
    if app.config.get('DEBUG') and hasattr(api, 'spec'):
        try:
            # Export OpenAPI spec to YAML and JSON
            spec_dict = api.spec.to_dict()

            openapi_dir = os.path.join(os.path.dirname(BASE_DIR), 'openapi')
            os.makedirs(openapi_dir, exist_ok=True)

            # Export to JSON
            json_path = os.path.join(openapi_dir, 'openapi.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(spec_dict, f, indent=2, ensure_ascii=False)

            # Export to YAML (requires PyYAML)
            try:
                import yaml
                yaml_path = os.path.join(openapi_dir, 'openapi.yaml')
                with open(yaml_path, 'w', encoding='utf-8') as f:
                    yaml.dump(spec_dict, f, default_flow_style=False, allow_unicode=True)
            except ImportError:
                pass  # PyYAML not installed, skip YAML export
        except Exception as e:
            logger.error(f"Error exporting OpenAPI spec: {e}")

    return response


if __name__ == '__main__':
    app.run(debug=True)
