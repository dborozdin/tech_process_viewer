"""REST-маршруты для генерации отчётов."""

from flask import Blueprint, jsonify, request, current_app, Response

bp = Blueprint('reports', __name__, url_prefix='/api/reports')


def _service():
    from services.report_service import ReportService
    db_api = current_app.config.get('db_api')
    return ReportService(db_api) if db_api else None


@bp.route('')
def list_reports():
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    return jsonify(svc.list_reports())


@bp.route('/<report_name>')
def render_report(report_name):
    svc = _service()
    if not svc:
        return jsonify({'error': 'Not connected'}), 400
    params = dict(request.args)
    html = svc.render_report(report_name, params)
    if html is None:
        return jsonify({'error': 'Report not found'}), 404
    return Response(html, mimetype='text/html')
