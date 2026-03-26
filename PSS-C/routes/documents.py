"""REST-маршруты для работы с документами."""

from flask import Blueprint, jsonify, request, current_app

bp = Blueprint('documents', __name__, url_prefix='/api/documents')


def _service():
    from services.document_service import DocumentService
    db_api = current_app.config.get('db_api')
    return DocumentService(db_api) if db_api else None


@bp.route('/<int:item_id>')
def documents_for_item(item_id):
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    return jsonify(svc.get_documents_for_item(item_id))


@bp.route('/attach', methods=['POST'])
def attach_document():
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    data = request.get_json()
    if not data or not data.get('doc_id') or not data.get('item_id'):
        return jsonify({'error': 'doc_id and item_id required'}), 400
    result = svc.attach_document(
        data['doc_id'], data['item_id'],
        data.get('item_type', 'apl_product_definition_formation')
    )
    return jsonify({'result': result})


@bp.route('/detach/<int:ref_id>', methods=['DELETE'])
def detach_document(ref_id):
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    svc.detach_document(ref_id)
    return jsonify({'deleted': True})


@bp.route('/search')
def search_documents():
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    q = request.args.get('q', '')
    if not q:
        return jsonify({'error': 'q parameter required'}), 400
    return jsonify(svc.search_documents(q))
