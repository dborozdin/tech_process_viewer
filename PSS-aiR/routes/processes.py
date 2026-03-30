"""REST-маршруты для работы с техпроцессами."""

from flask import Blueprint, jsonify, request, current_app

bp = Blueprint('processes', __name__, url_prefix='/api/processes')


def _service():
    from services.process_service import ProcessService
    db_api = current_app.config.get('db_api')
    return ProcessService(db_api) if db_api else None


@bp.route('/<int:product_id>')
def processes_for_product(product_id):
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    return jsonify(svc.get_processes_for_product(product_id))


@bp.route('/<int:process_id>/hierarchy')
def process_hierarchy(process_id):
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    return jsonify(svc.get_process_hierarchy(process_id))


@bp.route('/<int:process_id>/details')
def process_details(process_id):
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    result = svc.get_process_details(process_id)
    if result is None:
        return jsonify({'error': 'Process not found'}), 404
    return jsonify(result)


@bp.route('/column-types')
def operation_column_types():
    """Доступные типы динамических колонок для таблицы операций."""
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    return jsonify(svc.get_operation_column_types())


@bp.route('/<int:process_id>/characteristics')
def process_characteristics(process_id):
    """Значения характеристик бизнес-процесса."""
    db_api = current_app.config.get('db_api')
    if not db_api:
        return jsonify({'error': 'Not connected'}), 400
    try:
        values = db_api.characteristic_api.get_values_for_item(process_id)
        result = []
        for inst in values:
            parsed = db_api.characteristic_api._extract_display_value(inst)
            attrs = inst.get('attributes', {})
            char_ref = attrs.get('characteristic', {})
            char_name = ''
            if isinstance(char_ref, dict) and char_ref.get('name'):
                char_name = char_ref['name']
            result.append({
                'name': char_name,
                'value': parsed['value'],
                'unit': parsed['unit'],
                'subtype': parsed['subtype'],
            })
        # Resolve reference values (batch)
        ref_ids = []
        for i, inst in enumerate(values):
            parsed = db_api.characteristic_api._extract_display_value(inst)
            if not parsed['value'] and '_ref_id' in parsed:
                ref_ids.append((i, parsed['_ref_id']))
        if ref_ids:
            ids_str = ", ".join(f"#{rid}" for _, rid in ref_ids)
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{{ids_str}}} END_SELECT"
            ref_data = db_api.query_apl(query)
            ref_map = {}
            if ref_data:
                for rinst in ref_data.get('instances', []):
                    rattrs = rinst.get('attributes', {})
                    ref_map[rinst['id']] = rattrs.get('name', rattrs.get('id', ''))
            for idx, ref_id in ref_ids:
                if ref_id in ref_map and idx < len(result):
                    result[idx]['value'] = ref_map[ref_id]
        # Resolve characteristic names that are missing
        char_ids_to_resolve = []
        for i, inst in enumerate(values):
            if not result[i]['name']:
                char_ref = inst.get('attributes', {}).get('characteristic', {})
                if isinstance(char_ref, dict) and 'id' in char_ref:
                    char_ids_to_resolve.append((i, char_ref['id']))
        if char_ids_to_resolve:
            ids_str = ", ".join(f"#{cid}" for _, cid in char_ids_to_resolve)
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{{ids_str}}} END_SELECT"
            char_data = db_api.query_apl(query)
            char_map = {}
            if char_data:
                for cinst in char_data.get('instances', []):
                    char_map[cinst['id']] = cinst.get('attributes', {}).get('name', '')
            for idx, cid in char_ids_to_resolve:
                if cid in char_map:
                    result[idx]['name'] = char_map[cid]
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:process_id>/resources')
def process_resources(process_id):
    """Все ресурсы бизнес-процесса."""
    db_api = current_app.config.get('db_api')
    if not db_api:
        return jsonify({'error': 'Not connected'}), 400
    try:
        query = (
            f"SELECT NO_CASE Ext_ FROM "
            f"Ext_{{apl_business_process_resource(.process = #{process_id})}}"
            f" END_SELECT"
        )
        data = db_api.query_apl(query)
        instances = data.get('instances', []) if data else []
        # Resolve type names and unit names
        type_ids = set()
        unit_ids = set()
        for inst in instances:
            attrs = inst.get('attributes', {})
            t = attrs.get('type', {})
            if isinstance(t, dict) and 'id' in t:
                type_ids.add(t['id'])
            u = attrs.get('unit_component', {})
            if isinstance(u, dict) and 'id' in u:
                unit_ids.add(u['id'])
        all_ids = list(type_ids | unit_ids)
        name_map = {}
        if all_ids:
            ids_str = ", ".join(f"#{rid}" for rid in all_ids)
            ref_query = f"SELECT NO_CASE Ext_ FROM Ext_{{{ids_str}}} END_SELECT"
            ref_data = db_api.query_apl(ref_query)
            if ref_data:
                for rinst in ref_data.get('instances', []):
                    name_map[rinst['id']] = rinst.get('attributes', {}).get('name', '')
        result = []
        for inst in instances:
            attrs = inst.get('attributes', {})
            t = attrs.get('type', {})
            u = attrs.get('unit_component', {})
            type_id = t.get('id') if isinstance(t, dict) else None
            unit_id = u.get('id') if isinstance(u, dict) else None
            result.append({
                'sys_id': inst.get('id'),
                'name': attrs.get('name', ''),
                'id': attrs.get('id', ''),
                'type': name_map.get(type_id, ''),
                'value': attrs.get('value_component', ''),
                'unit': name_map.get(unit_id, ''),
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:process_id>/operation-columns')
def operation_column_data(process_id):
    """Данные динамических колонок для операций техпроцесса."""
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    columns_param = request.args.get('columns', '')
    if not columns_param:
        return jsonify({})
    column_keys = [k.strip() for k in columns_param.split(',') if k.strip()]
    try:
        return jsonify(svc.get_operation_column_data(process_id, column_keys))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
