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
