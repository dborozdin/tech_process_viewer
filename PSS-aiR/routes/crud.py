"""CRUD-маршруты для PSS-aiR.

Blueprint с эндпоинтами создания, редактирования и удаления
объектов PDM: папки, изделия, BOM, бизнес-процессы, ресурсы,
характеристики, документы.
"""

import os
import time
import json
import datetime
import tempfile
from flask import Blueprint, jsonify, request, current_app, g
from tech_process_viewer.globals import logger

bp = Blueprint('crud', __name__, url_prefix='/api/crud')

# PSS creates .bak/.tmp files on save that block subsequent saves
_DB_FILE = r"c:\_pss_lite_db\pss_moma_08_07_2025.aplb"

def _clean_pss_aux():
    """Remove .bak/.tmp files that PSS leaves after save."""
    import glob as _glob
    for f in _glob.glob(_DB_FILE + ".*"):
        if f.endswith(('.bak', '.tmp')):
            try:
                os.remove(f)
            except:
                pass

# ── Request logging ──
_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pss_crud.log")

def _crud_log(msg):
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


@bp.before_request
def _reconnect_for_writes():
    """Reconnect PSS session before every write operation to avoid FILE_IO."""
    if request.method in ('POST', 'PUT', 'DELETE'):
        db_api = current_app.config.get('db_api')
        if db_api and db_api.connect_data:
            try:
                db_api.reconnect_db()
            except Exception as e:
                logger.warning(f"Pre-write reconnect failed: {e}")


@bp.before_request
def _log_before():
    g.crud_start = time.perf_counter()
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    body = request.get_data(as_text=True)[:2000] if request.data else ""
    _crud_log(f"\n─── [{ts}] {request.method} {request.path} ───")
    if body:
        try:
            pretty = json.dumps(json.loads(body), ensure_ascii=False, indent=2)[:1500]
        except:
            pretty = body[:1500]
        _crud_log(f"  Request body:\n    {pretty.replace(chr(10), chr(10)+'    ')}")


@bp.after_request
def _log_after(response):
    elapsed = time.perf_counter() - getattr(g, 'crud_start', time.perf_counter())
    resp_data = response.get_data(as_text=True)[:1500]
    try:
        pretty = json.dumps(json.loads(resp_data), ensure_ascii=False, indent=2)[:1000]
    except:
        pretty = resp_data[:1000]
    _crud_log(f"  Response: HTTP {response.status_code}  Time: {elapsed:.3f}s")
    _crud_log(f"  Response body:\n    {pretty.replace(chr(10), chr(10)+'    ')}")
    return response


def _db(reconnect=False):
    """Получить db_api или вернуть ошибку. reconnect=True пересоздаёт сессию PSS."""
    db_api = current_app.config.get('db_api')
    if not db_api or not db_api.connect_data:
        return None, (jsonify({'success': False, 'message': 'Не подключено к БД'}), 401)
    if reconnect:
        try:
            db_api.reconnect_db()
            logger.info("_db: reconnected PSS session")
        except Exception as e:
            logger.warning(f"_db: reconnect failed: {e}")
    return db_api, None


# ========== Папки ==========

@bp.route('/folders/<int:folder_id>', methods=['PUT'])
def rename_folder(folder_id):
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Наименование обязательно'}), 400
    try:
        db_api.folders_api.rename_folder(folder_id, name)
        return jsonify({'success': True, 'message': 'Папка переименована'})
    except Exception as e:
        logger.error(f"rename_folder error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/folders/<int:folder_id>', methods=['DELETE'])
def delete_folder(folder_id):
    db_api, err = _db()
    if err:
        return err
    try:
        db_api.folders_api.delete_folder(folder_id)
        return jsonify({'success': True, 'message': 'Папка удалена'})
    except Exception as e:
        logger.error(f"delete_folder error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/folders/<int:folder_id>/items', methods=['POST'])
def add_item_to_folder(folder_id):
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    item_id = data.get('item_id')
    item_type = data.get('item_type', 'apl_product_definition_formation')
    if not item_id:
        return jsonify({'success': False, 'message': 'item_id обязателен'}), 400
    try:
        db_api.folders_api.add_item_to_folder(item_id, item_type, folder_id)
        return jsonify({'success': True, 'message': 'Элемент добавлен в папку'}), 201
    except Exception as e:
        logger.error(f"add_item_to_folder error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/folders/<int:folder_id>/items/<int:item_id>', methods=['DELETE'])
def remove_item_from_folder(folder_id, item_id):
    db_api, err = _db()
    if err:
        return err
    try:
        db_api.folders_api.remove_item_from_folder(folder_id, item_id)
        return jsonify({'success': True, 'message': 'Элемент удалён из папки'})
    except Exception as e:
        logger.error(f"remove_item_from_folder error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== Изделия ==========

@bp.route('/products', methods=['POST'])
def create_product():
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    prd_id = data.get('id', '').strip()
    prd_name = data.get('name', '').strip()
    if not prd_id or not prd_name:
        return jsonify({'success': False, 'message': 'Обозначение и наименование обязательны'}), 400

    formation_type = data.get('formation_type', 'part')
    make_or_buy = data.get('make_or_buy', 'make')

    try:
        # Собрать ВСЕ в один bulk-save (PSS не выдерживает consecutive saves)
        import requests as http_requests

        pdf_attrs = {
            "formation_type": formation_type,
            "make_or_buy": make_or_buy,
            "of_product": {
                "id": 0, "index": 1, "type": "product",
                "attributes": {"id": prd_id, "name": prd_name}
            }
        }
        # Добавить code1/code2 сразу в PDF (без второго save)
        if data.get('code1'):
            pdf_attrs["code1"] = data["code1"]
        if data.get('code2'):
            pdf_attrs["code2"] = data["code2"]

        instances = [{
            "id": 0, "index": 0,
            "type": "apl_product_definition_formation",
            "attributes": pdf_attrs
        }]

        payload = {"format": "apl_json_1", "dictionary": "apl_pss_a", "instances": instances}
        headers = db_api.get_headers()
        resp = http_requests.post(db_api.URL_QUERY_SAVE, json=payload, headers=headers, timeout=120)
        logger.info(f"create_product: HTTP {resp.status_code}, time={resp.elapsed.total_seconds():.1f}s")
        logger.info(f"create_product: body={resp.text[:300]}")

        resp_data = resp.json()
        pdf_id = None
        if resp_data.get('instances'):
            for inst in resp_data['instances']:
                if inst.get('type') == 'apl_product_definition_formation':
                    pdf_id = inst.get('id')
                    break

        if pdf_id is None:
            logger.error(f"create_product failed: {resp_data}")
            return jsonify({'success': False, 'message': 'Не удалось создать изделие'}), 500

        # Добавить в папку (отдельный save — неизбежен, но можно попробовать)
        folder_id = data.get('folder_id')
        if folder_id:
            try:
                db_api.folders_api.add_item_to_folder(pdf_id, 'apl_product_definition_formation', folder_id)
            except Exception as e:
                logger.warning(f"add_to_folder failed (non-critical): {e}")

        # Включить в состав (BOM)
        parent_pdf_id = data.get('parent_pdf_id')
        bom_id = None
        if parent_pdf_id:
            try:
                quantity = data.get('quantity', 1)
                unit_id = db_api.units_api.find_unit_by_id("шт") or db_api.units_api.find_unit_by_id("EA") or 0
                bom_result = db_api.products_api.create_product_assembly(
                    pdf_related=pdf_id, pdf_relating=parent_pdf_id,
                    quantity=quantity, UOM=unit_id
                )
                if bom_result:
                    bom_id = bom_result[0] if isinstance(bom_result, tuple) else bom_result
            except Exception as e:
                logger.warning(f"create_bom failed (non-critical): {e}")

        _clean_pss_aux()
        return jsonify({'success': True, 'message': 'Изделие создано', 'data': {'pdf_id': pdf_id, 'bom_id': bom_id}}), 201
    except Exception as e:
        logger.error(f"create_product error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/products/<int:pdf_id>', methods=['PUT'])
def update_product(pdf_id):
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    try:
        # Получить product sys_id из PDF
        import time as _time
        _t0 = _time.perf_counter()
        pdf_inst = db_api.products_api.get_product_definition(pdf_id)
        _t1 = _time.perf_counter()
        logger.info(f"update_product: get_product_definition took {_t1-_t0:.2f}s")
        if not pdf_inst:
            return jsonify({'success': False, 'message': 'Изделие не найдено'}), 404

        of_product = pdf_inst.get('attributes', {}).get('of_product', {})
        product_sys_id = of_product.get('id') if isinstance(of_product, dict) else None

        # Собрать ВСЕ обновления в один bulk-save (минимизация запросов к PSS)
        import requests as http_requests
        instances = []

        # Product attributes (name, id, description)
        if product_sys_id:
            product_updates = {}
            if 'name' in data:
                product_updates['name'] = data['name']
            if 'id' in data:
                product_updates['id'] = data['id']
            if data.get('description'):
                product_updates['description'] = data['description']
            if product_updates:
                instances.append({
                    "id": product_sys_id,
                    "type": "product",
                    "attributes": product_updates
                })

        # PDF attributes (code1, code2, formation_type, make_or_buy)
        pdf_updates = {}
        for key in ('code1', 'code2', 'formation_type', 'make_or_buy'):
            if data.get(key):
                pdf_updates[key] = data[key]
        if pdf_updates:
            instances.append({
                "id": pdf_id,
                "type": "apl_product_definition_formation",
                "attributes": pdf_updates
            })

        if instances:
            payload = {
                "format": "apl_json_1",
                "dictionary": "apl_pss_a",
                "instances": instances
            }
            headers = db_api.get_headers()
            _t2 = _time.perf_counter()
            resp = http_requests.post(db_api.URL_QUERY_SAVE, json=payload, headers=headers, timeout=120)
            _t3 = _time.perf_counter()
            logger.info(f"update_product: bulk save took {_t3-_t2:.2f}s, HTTP {resp.status_code}")
            logger.info(f"update_product: PSS response: {resp.text[:300]}")
            if not resp.ok:
                logger.error(f"update_product bulk save error: HTTP {resp.status_code}, {resp.text[:300]}")

        _clean_pss_aux()
        return jsonify({'success': True, 'message': 'Изделие обновлено'})
    except Exception as e:
        logger.error(f"update_product error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/products/<int:pdf_id>', methods=['DELETE'])
def delete_product(pdf_id):
    db_api, err = _db()
    if err:
        return err
    folder_id = request.args.get('folder_id', type=int)
    try:
        # Убрать из папки если указана
        if folder_id:
            try:
                db_api.folders_api.remove_item_from_folder(folder_id, pdf_id)
            except Exception:
                pass

        db_api.products_api.delete_product_definition(pdf_id)
        return jsonify({'success': True, 'message': 'Изделие удалено'})
    except Exception as e:
        logger.error(f"delete_product error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== Состав изделия (BOM) ==========

@bp.route('/products/<int:pdf_id>/bom', methods=['POST'])
def create_bom_link(pdf_id):
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    child_pdf_id = data.get('child_pdf_id')
    quantity = data.get('quantity', 1)
    unit_id = data.get('unit_id')
    if not child_pdf_id:
        return jsonify({'success': False, 'message': 'child_pdf_id обязателен'}), 400
    try:
        if not unit_id:
            unit_id = db_api.units_api.find_unit_by_id("шт")
            if not unit_id:
                unit_id = db_api.units_api.find_unit_by_id("EA")

        result = db_api.products_api.create_product_assembly(
            pdf_related=child_pdf_id,
            pdf_relating=pdf_id,
            quantity=quantity,
            UOM=unit_id or 0
        )
        if result:
            bom_id = result[0] if isinstance(result, tuple) else result
            return jsonify({'success': True, 'message': 'Компонент добавлен', 'data': {'bom_id': bom_id}}), 201
        return jsonify({'success': False, 'message': 'Не удалось добавить компонент'}), 500
    except Exception as e:
        logger.error(f"create_bom_link error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/bom/<int:bom_id>', methods=['PUT'])
def update_bom_link(bom_id):
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    updates = {}
    if 'quantity' in data:
        updates['value_component'] = data['quantity']
    if 'unit_id' in data:
        updates['unit_component'] = {'id': data['unit_id'], 'type': 'apl_unit'}
    if 'reference_designator' in data:
        updates['reference_designator'] = data['reference_designator']
    try:
        db_api.products_api.update_bom_item(bom_id, updates)
        return jsonify({'success': True, 'message': 'Связь обновлена'})
    except Exception as e:
        logger.error(f"update_bom_link error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/bom/<int:bom_id>', methods=['DELETE'])
def delete_bom_link(bom_id):
    db_api, err = _db()
    if err:
        return err
    try:
        db_api.products_api.delete_bom_item(bom_id)
        return jsonify({'success': True, 'message': 'Компонент удалён из состава'})
    except Exception as e:
        logger.error(f"delete_bom_link error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== Бизнес-процессы ==========

@bp.route('/processes', methods=['POST'])
def create_process():
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    bp_name = data.get('name', '').strip()
    bp_id = data.get('id', bp_name)
    if not bp_name:
        return jsonify({'success': False, 'message': 'Наименование обязательно'}), 400
    try:
        type_name = data.get('type_name', 'Default')
        type_id = db_api.bp_api.find_or_create_bp_type(type_name)

        result = db_api.bp_api.create_business_process(bp_id, bp_name, type_id)
        if not result:
            return jsonify({'success': False, 'message': 'Не удалось создать процесс'}), 500

        bp_sys_id = result[0] if isinstance(result, tuple) else result
        bp_version_id = result[1] if isinstance(result, tuple) and len(result) > 1 else None

        if data.get('description'):
            db_api.bp_api.update_business_process(bp_sys_id, {'description': data['description']})

        # Привязать к изделию если указан pdf_id
        if data.get('pdf_id'):
            db_api.bp_api.find_or_create_bp_reference(bp=bp_sys_id, pdf=data['pdf_id'])

        return jsonify({
            'success': True, 'message': 'Процесс создан',
            'data': {'bp_id': bp_sys_id, 'version_id': bp_version_id}
        }), 201
    except Exception as e:
        logger.error(f"create_process error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/processes/<int:bp_id>', methods=['PUT'])
def update_process(bp_id):
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    updates = {}
    for key in ('name', 'description'):
        if key in data:
            updates[key] = data[key]
    try:
        db_api.bp_api.update_business_process(bp_id, updates)
        return jsonify({'success': True, 'message': 'Процесс обновлён'})
    except Exception as e:
        logger.error(f"update_process error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/processes/<int:bp_id>', methods=['DELETE'])
def delete_process(bp_id):
    db_api, err = _db()
    if err:
        return err
    try:
        db_api.bp_api.delete_business_process(bp_id)
        return jsonify({'success': True, 'message': 'Процесс удалён'})
    except Exception as e:
        logger.error(f"delete_process error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/processes/<int:bp_id>/elements', methods=['POST'])
def add_process_element(bp_id):
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    child_id = data.get('element_id')
    if not child_id:
        return jsonify({'success': False, 'message': 'element_id обязателен'}), 400
    try:
        db_api.bp_api.add_element_to_process(bp_id, child_id)
        return jsonify({'success': True, 'message': 'Элемент добавлен'}), 201
    except Exception as e:
        logger.error(f"add_process_element error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/processes/<int:bp_id>/elements/<int:child_id>', methods=['DELETE'])
def remove_process_element(bp_id, child_id):
    db_api, err = _db()
    if err:
        return err
    try:
        db_api.bp_api.remove_element_from_process(bp_id, child_id)
        return jsonify({'success': True, 'message': 'Элемент удалён'})
    except Exception as e:
        logger.error(f"remove_process_element error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/processes/<int:bp_id>/link-product', methods=['POST'])
def link_process_to_product(bp_id):
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    pdf_id = data.get('pdf_id')
    if not pdf_id:
        return jsonify({'success': False, 'message': 'pdf_id обязателен'}), 400
    try:
        ref_id = db_api.bp_api.find_or_create_bp_reference(bp=bp_id, pdf=pdf_id)
        return jsonify({'success': True, 'message': 'Процесс привязан к изделию', 'data': {'ref_id': ref_id}}), 201
    except Exception as e:
        logger.error(f"link_process_to_product error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== Ресурсы ==========

@bp.route('/resources', methods=['POST'])
def create_resource():
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    process_id = data.get('process_id')
    type_id = data.get('type_id')
    if not process_id or not type_id:
        return jsonify({'success': False, 'message': 'process_id и type_id обязательны'}), 400
    try:
        resource_id = db_api.resources_api.create_resource(
            res_id=data.get('id', ''),
            res_name=data.get('name', ''),
            res_type=type_id,
            bp=process_id,
            item=data.get('object_id', 0),
            item_type=data.get('object_type', 'organization'),
            value=data.get('value_component', 0),
            unit=data.get('unit_id', 0)
        )
        if resource_id:
            return jsonify({'success': True, 'message': 'Ресурс создан', 'data': {'resource_id': resource_id}}), 201
        return jsonify({'success': False, 'message': 'Не удалось создать ресурс'}), 500
    except Exception as e:
        logger.error(f"create_resource error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/resources/<int:resource_id>', methods=['PUT'])
def update_resource(resource_id):
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    try:
        db_api.resources_api.update_resource(resource_id, data)
        return jsonify({'success': True, 'message': 'Ресурс обновлён'})
    except Exception as e:
        logger.error(f"update_resource error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/resources/<int:resource_id>', methods=['DELETE'])
def delete_resource(resource_id):
    db_api, err = _db()
    if err:
        return err
    try:
        db_api.resources_api.delete_resource(resource_id)
        return jsonify({'success': True, 'message': 'Ресурс удалён'})
    except Exception as e:
        logger.error(f"delete_resource error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/resource-types', methods=['GET'])
def list_resource_types():
    db_api, err = _db()
    if err:
        return err
    try:
        types = db_api.resources_api.list_resource_types()
        result = []
        for t in types:
            attrs = t.get('attributes', {})
            result.append({
                'sys_id': t.get('id'),
                'name': attrs.get('name', ''),
                'id': attrs.get('id', '')
            })
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"list_resource_types error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== Характеристики ==========

@bp.route('/characteristics', methods=['GET'])
def list_characteristics():
    db_api, err = _db()
    if err:
        return err
    try:
        chars = db_api.characteristic_api.list_characteristics()
        result = []
        for ch in chars:
            attrs = ch.get('attributes', {})
            result.append({
                'sys_id': ch.get('id'),
                'name': attrs.get('name', ''),
                'description': attrs.get('description', ''),
                'id': attrs.get('id', '')
            })
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"list_characteristics error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/characteristics/values', methods=['POST'])
def create_characteristic_value():
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    item_id = data.get('item_id')
    char_id = data.get('characteristic_id')
    value = data.get('value', '')
    subtype = data.get('subtype', 'apl_descriptive_characteristic_value')
    if not item_id or not char_id:
        return jsonify({'success': False, 'message': 'item_id и characteristic_id обязательны'}), 400
    try:
        result = db_api.characteristic_api.create_characteristic_value(item_id, char_id, value, subtype)
        if result:
            sid = result.get('id') if isinstance(result, dict) else result
            return jsonify({'success': True, 'message': 'Характеристика создана', 'data': {'sys_id': sid}}), 201
        return jsonify({'success': False, 'message': 'Не удалось создать характеристику'}), 500
    except Exception as e:
        logger.error(f"create_characteristic_value error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/characteristics/values/<int:value_id>', methods=['PUT'])
def update_characteristic_value(value_id):
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    try:
        db_api.characteristic_api.update_characteristic_value(
            value_id,
            data.get('value', ''),
            data.get('subtype', 'apl_descriptive_characteristic_value')
        )
        return jsonify({'success': True, 'message': 'Характеристика обновлена'})
    except Exception as e:
        logger.error(f"update_characteristic_value error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/characteristics/values/<int:value_id>', methods=['DELETE'])
def delete_characteristic_value(value_id):
    db_api, err = _db()
    if err:
        return err
    try:
        db_api.characteristic_api.delete_characteristic_value(value_id)
        return jsonify({'success': True, 'message': 'Характеристика удалена'})
    except Exception as e:
        logger.error(f"delete_characteristic_value error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== Документы ==========

@bp.route('/documents/upload', methods=['POST'])
def upload_document():
    db_api, err = _db()
    if err:
        return err
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Файл не предоставлен'}), 400

    file = request.files['file']
    doc_id = request.form.get('doc_id', file.filename)
    doc_name = request.form.get('doc_name', file.filename)
    doc_type_id = request.form.get('doc_type_id')
    item_id = request.form.get('item_id')
    item_type = request.form.get('item_type', 'apl_product_definition_formation')

    try:
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)
        try:
            if not doc_type_id:
                doc_type_id = db_api.docs_api.find_or_create_doc_type("DEFAULT", "Default")

            result = db_api.docs_api.create_document(
                doc_id=doc_id, doc_name=doc_name, doc_type=doc_type_id,
                crc=None, src_date=None, stored_doc_id=None, file_path=temp_path
            )
            if result is None:
                return jsonify({'success': False, 'message': 'Не удалось создать документ'}), 500

            doc_sys_id = result[0] if isinstance(result, tuple) else result
            ref_id = None
            if item_id:
                ref_result = db_api.docs_api.create_document_reference(
                    doc=doc_sys_id, ref_object=int(item_id), ref_object_type=item_type
                )
                if ref_result:
                    ref_id = ref_result[0] if isinstance(ref_result, tuple) else ref_result

            return jsonify({
                'success': True, 'message': 'Документ загружен',
                'data': {'doc_id': doc_sys_id, 'ref_id': ref_id}
            }), 201
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
    except Exception as e:
        logger.error(f"upload_document error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/documents/attach', methods=['POST'])
def attach_document():
    db_api, err = _db()
    if err:
        return err
    data = request.get_json()
    doc_id = data.get('doc_id')
    item_id = data.get('item_id')
    item_type = data.get('item_type', 'apl_product_definition_formation')
    if not doc_id or not item_id:
        return jsonify({'success': False, 'message': 'doc_id и item_id обязательны'}), 400
    try:
        result = db_api.docs_api.create_document_reference(
            doc=doc_id, ref_object=item_id, ref_object_type=item_type
        )
        if result:
            ref_id = result[0] if isinstance(result, tuple) else result
            return jsonify({'success': True, 'message': 'Документ привязан', 'data': {'ref_id': ref_id}}), 201
        return jsonify({'success': False, 'message': 'Не удалось привязать документ'}), 500
    except Exception as e:
        logger.error(f"attach_document error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/documents/detach/<int:ref_id>', methods=['DELETE'])
def detach_document(ref_id):
    db_api, err = _db()
    if err:
        return err
    try:
        db_api.docs_api.delete_document_reference(ref_id)
        return jsonify({'success': True, 'message': 'Документ отвязан'})
    except Exception as e:
        logger.error(f"detach_document error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/documents/search', methods=['GET'])
def search_documents():
    db_api, err = _db()
    if err:
        return err
    q = request.args.get('q', '')
    if not q:
        return jsonify({'success': True, 'data': []})
    try:
        query = f'SELECT NO_CASE Ext_ FROM Ext_{{apl_document(.id LIKE "{q}")}} END_SELECT'
        data = db_api.query_apl(query)
        results = []
        if data and 'instances' in data:
            for inst in data['instances'][:20]:
                attrs = inst.get('attributes', {})
                results.append({
                    'sys_id': inst.get('id'),
                    'doc_id': attrs.get('id', ''),
                    'name': attrs.get('name', ''),
                    'type': inst.get('type', '')
                })
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        logger.error(f"search_documents error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== Справочники ==========

@bp.route('/units/search', methods=['GET'])
def search_units():
    db_api, err = _db()
    if err:
        return err
    q = request.args.get('q', '')
    try:
        if q:
            query = f'SELECT NO_CASE Ext_ FROM Ext_{{apl_unit(.id LIKE "{q}")}} END_SELECT'
        else:
            query = 'SELECT NO_CASE Ext_ FROM Ext_{apl_unit} END_SELECT'
        data = db_api.query_apl(query)
        results = []
        if data and 'instances' in data:
            for inst in data['instances'][:50]:
                attrs = inst.get('attributes', {})
                results.append({
                    'sys_id': inst.get('id'),
                    'name': attrs.get('name', ''),
                    'id': attrs.get('id', '')
                })
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        logger.error(f"search_units error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
