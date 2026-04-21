"""REST-маршруты для работы со справочниками PSS.

Классификаторы — полная реализация с ленивой загрузкой дерева.
"""

from flask import Blueprint, jsonify, request, current_app

bp = Blueprint('references', __name__, url_prefix='/api/references')


def _service():
    from services.reference_service import ReferenceService
    db_api = current_app.config.get('db_api')
    return ReferenceService(db_api) if db_api else None


def _need_service():
    svc = _service()
    if not svc:
        return None, (jsonify({'error': 'Not connected'}), 400)
    return svc, None


# ===== Общие =====

@bp.route('/types')
def get_reference_types():
    svc, err = _need_service()
    if err:
        return err
    return jsonify({'types': svc.get_all_reference_types()})


@bp.route('/list/<ref_type>')
def get_reference_list(ref_type):
    svc, err = _need_service()
    if err:
        return err
    return jsonify(svc.get_reference_list(ref_type))


# ===== Классификаторы: чтение =====

@bp.route('/classifiers')
def list_classifier_systems():
    """Список систем классификаторов."""
    svc, err = _need_service()
    if err:
        return err
    return jsonify({'systems': svc.get_classifier_systems()})


@bp.route('/classifiers/<int:system_id>/tree')
def get_classifier_tree(system_id):
    """Неглубокое дерево классификатора (система + корневые уровни + 1 уровень потомков)."""
    svc, err = _need_service()
    if err:
        return err
    max_depth = request.args.get('max_depth', 2, type=int)
    try:
        return jsonify(svc.get_classifier_tree(system_id, max_depth))
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error getting classifier tree: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/classifiers/<int:system_id>/roots')
def get_classifier_roots(system_id):
    """Корневые уровни системы классификатора."""
    svc, err = _need_service()
    if err:
        return err
    return jsonify({'levels': svc.get_root_levels(system_id)})


@bp.route('/levels/<int:parent_id>/children')
def get_level_children(parent_id):
    """Прямые дочерние уровни для заданного родительского уровня."""
    svc, err = _need_service()
    if err:
        return err
    return jsonify({'levels': svc.get_child_levels(parent_id)})


@bp.route('/classifiers/levels/<int:level_id>')
def get_classifier_level_details(level_id):
    """Полная информация об уровне классификатора."""
    svc, err = _need_service()
    if err:
        return err
    try:
        details = svc.get_classifier_level_details(level_id)
        if not details:
            return jsonify({'error': 'Level not found'}), 404
        return jsonify({'level': details})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error getting level details: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/search')
def search():
    """Поиск по классификаторам (системы и уровни)."""
    svc, err = _need_service()
    if err:
        return err
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'error': 'q parameter required'}), 400
    search_type = request.args.get('type', 'all')
    return jsonify(svc.search_classifiers(q, search_type))


# ===== Классификаторы: CRUD систем =====

@bp.route('/classifiers', methods=['POST'])
def create_classifier_system():
    svc, err = _need_service()
    if err:
        return err
    data = request.get_json() or {}
    if not data.get('id') or not data.get('name'):
        return jsonify({'error': 'id and name required'}), 400
    try:
        result = svc.create_classifier_system(data)
        if not result:
            return jsonify({'error': 'Failed to create system'}), 500
        return jsonify({'system': result})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error creating classifier system: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/classifiers/<int:sys_id>', methods=['PUT'])
def update_classifier_system(sys_id):
    svc, err = _need_service()
    if err:
        return err
    data = request.get_json() or {}
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    try:
        result = svc.update_classifier_system(sys_id, data)
        if not result:
            return jsonify({'error': 'Failed to update system'}), 500
        return jsonify({'system': result})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error updating classifier system {sys_id}: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/classifiers/<int:sys_id>', methods=['DELETE'])
def delete_classifier_system(sys_id):
    svc, err = _need_service()
    if err:
        return err
    try:
        ok = svc.delete_classifier_system(sys_id)
        if not ok:
            return jsonify({'error': 'Failed to delete system'}), 500
        return jsonify({'message': 'System deleted successfully'})
    except Exception as e:
        current_app.logger.error(f"Error deleting classifier system {sys_id}: {e}")
        return jsonify({'error': str(e)}), 500


# ===== Классификаторы: CRUD уровней =====

@bp.route('/classifiers/levels', methods=['POST'])
def create_classifier_level():
    svc, err = _need_service()
    if err:
        return err
    data = request.get_json() or {}
    if not data.get('system_id') or not data.get('id') or not data.get('name'):
        return jsonify({'error': 'system_id, id and name required'}), 400
    try:
        result = svc.create_classifier_level(data)
        if not result:
            return jsonify({'error': 'Failed to create level'}), 500
        return jsonify({'level': result})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error creating classifier level: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/classifiers/levels/<int:sys_id>', methods=['PUT'])
def update_classifier_level(sys_id):
    svc, err = _need_service()
    if err:
        return err
    data = request.get_json() or {}
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    try:
        result = svc.update_classifier_level(sys_id, data)
        if not result:
            return jsonify({'error': 'Failed to update level'}), 500
        return jsonify({'level': result})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error updating classifier level {sys_id}: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/classifiers/levels/<int:sys_id>', methods=['DELETE'])
def delete_classifier_level(sys_id):
    svc, err = _need_service()
    if err:
        return err
    try:
        ok = svc.delete_classifier_level(sys_id)
        if not ok:
            return jsonify({'error': 'Failed to delete level'}), 500
        return jsonify({'message': 'Level deleted successfully'})
    except Exception as e:
        current_app.logger.error(f"Error deleting classifier level {sys_id}: {e}")
        return jsonify({'error': str(e)}), 500
