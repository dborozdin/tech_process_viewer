"""REST-маршруты для работы с изделиями и BOM."""

from flask import Blueprint, jsonify, request, current_app

bp = Blueprint('products', __name__, url_prefix='/api/products')


def _service():
    from services.product_service import ProductService
    db_api = current_app.config.get('db_api')
    return ProductService(db_api) if db_api else None


@bp.route('/<int:product_id>')
def product_details(product_id):
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    result = svc.get_product_details(product_id)
    if result is None:
        return jsonify({'error': 'Product not found'}), 404
    return jsonify(result)


@bp.route('/<int:product_id>/tree')
def product_tree(product_id):
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    max_depth = request.args.get('max_depth', 10, type=int)
    result = svc.get_product_tree(product_id, max_depth)
    if result is None:
        return jsonify({'error': 'Product not found'}), 404
    return jsonify(result)


@bp.route('/<int:product_id>/characteristics')
def product_characteristics(product_id):
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    result = svc.get_product_details(product_id)
    if result is None:
        return jsonify({'error': 'Product not found'}), 404
    return jsonify(result.get('characteristics', []))


@bp.route('/search')
def search_products():
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    q = request.args.get('q', '')
    if not q:
        return jsonify({'error': 'q parameter required'}), 400
    return jsonify(svc.search_products(q))
