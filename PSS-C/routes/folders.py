"""REST-маршруты для работы с папками."""

from flask import Blueprint, jsonify, request, current_app

bp = Blueprint('folders', __name__, url_prefix='/api/folders')


def _service():
    """Создаёт FolderService из текущего db_api."""
    from services.folder_service import FolderService
    db_api = current_app.config.get('db_api')
    if not db_api:
        return None
    return FolderService(db_api)


@bp.route('/tree')
def folder_tree():
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    root = request.args.get('root')
    return jsonify(svc.get_folder_tree(root_name=root))


@bp.route('/<int:folder_id>/contents')
def folder_contents(folder_id):
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    result = svc.get_folder_contents(folder_id)
    if result is None:
        return jsonify({'error': 'Folder not found'}), 404
    return jsonify(result)


@bp.route('', methods=['POST'])
def create_folder():
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'name required'}), 400
    result = svc.create_folder(data['name'], data.get('parent_id'))
    if result is None:
        return jsonify({'error': 'Failed to create folder'}), 500
    return jsonify(result), 201
