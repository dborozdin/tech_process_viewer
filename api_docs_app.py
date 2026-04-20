"""API Docs — Swagger/OpenAPI документация для REST API платформы PSS.

Порт: 5004
Функции: Swagger UI, ReDoc, OpenAPI spec export.

Запуск: python api_docs_app.py
Swagger UI: http://localhost:5004/api/docs
ReDoc: http://localhost:5004/api/redoc
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask_smorest import Api

from tech_process_viewer.api.app_helpers import create_pss_app
from tech_process_viewer.globals import logger

app = create_pss_app(
    __name__,
    static_folder='static',
    template_folder='static/templates',
    port=5004
)

# Flask-Smorest — auto-generates Swagger/OpenAPI
api = Api(app)

# Register all REST blueprints
from tech_process_viewer.api.routes.auth import blp as auth_blp
from tech_process_viewer.api.routes.business_processes import blp as business_processes_blp
from tech_process_viewer.api.routes.entity_viewer import blp as entity_viewer_blp
from tech_process_viewer.api.routes.products import blp as products_blp
from tech_process_viewer.api.routes.documents import blp as documents_blp
from tech_process_viewer.api.routes.resources import blp as resources_blp
from tech_process_viewer.api.routes.organizations import blp as organizations_blp
from tech_process_viewer.api.routes.characteristics import blp as characteristics_blp
from tech_process_viewer.api.routes.test_runner import blp as test_runner_blp

api.register_blueprint(auth_blp)
api.register_blueprint(business_processes_blp)
api.register_blueprint(entity_viewer_blp)
api.register_blueprint(products_blp)
api.register_blueprint(documents_blp)
api.register_blueprint(resources_blp)
api.register_blueprint(organizations_blp)
api.register_blueprint(characteristics_blp)
api.register_blueprint(test_runner_blp)


# ── Override /api/docs Swagger UI to inject our test-runner plugin ──────
from flask import send_from_directory, Response, request, stream_with_context


@app.route("/static/<path:filename>")
def _api_docs_static(filename):
    return send_from_directory(os.path.join(BASE_DIR, "static"), filename)


@app.route("/openapi/<path:filename>")
def _api_docs_openapi_file(filename):
    """Serve files from openapi/ (settings.json, test_API_results_*.json, etc.)."""
    return send_from_directory(os.path.join(BASE_DIR, "openapi"), filename)


# Streaming endpoint for live test-runner updates (NDJSON, не Smorest).
@app.route("/api/v1/test-runner/run-stream", methods=["POST"])
def _test_runner_run_stream():
    from tech_process_viewer.api.routes.test_runner import (
        _load_settings, run_group_stream, _origin_from_request_url,
    )
    data = request.get_json(silent=True) or {}
    group = data.get("group")
    settings = _load_settings()
    if group not in settings.get("groups", {}):
        return Response(
            json.dumps({"error": f"Unknown group '{group}'"}, ensure_ascii=False),
            mimetype="application/json", status=404,
        )
    base_url = _origin_from_request_url(request.url_root + "_x")
    return Response(
        stream_with_context(
            run_group_stream(base_url, group, settings["groups"][group], settings["db"])
        ),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


_SWAGGER_UI_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>PSS API — Swagger + Test Runner</title>
  <link href="https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui.css" rel="stylesheet" type="text/css"/>
  <style>
    .test-runner-row table tr:nth-child(even){background:#f9f9f9}
    .test-runner-row .test-runner-output{max-height:520px;overflow:auto}
  </style>
</head>
<body>
  <div id="swagger-ui-container"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui-standalone-preset.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui-bundle.js"></script>
  <script src="/static/test_runner_plugin.js"></script>
  <script>
    window.onload = function() {
      window.ui = SwaggerUIBundle({
        url: "/api/openapi.json",
        dom_id: '#swagger-ui-container',
        presets: [SwaggerUIBundle.presets.apis],
        plugins: [window.TestRunnerPlugin],
        layout: 'BaseLayout',
        docExpansion: 'list'
      });
    };
  </script>
</body>
</html>
"""


def _override_swagger_ui():
    """Replace Smorest's openapi_swagger_ui view with our enhanced HTML."""
    def _ui():
        return Response(_SWAGGER_UI_HTML, mimetype="text/html")
    # Smorest registers endpoint name 'api-docs.openapi_swagger_ui'
    for endpoint in list(app.view_functions.keys()):
        if "openapi_swagger_ui" in endpoint:
            app.view_functions[endpoint] = _ui
            print(f" * Overridden Swagger UI endpoint: {endpoint}")
            break


_override_swagger_ui()

BASE_DIR = os.path.dirname(__file__)


@app.after_request
def export_openapi_spec(response):
    """Export OpenAPI spec to files in development mode."""
    if app.config.get('DEBUG') and hasattr(api, 'spec'):
        try:
            spec_dict = api.spec.to_dict()
            openapi_dir = os.path.join(BASE_DIR, 'openapi')
            os.makedirs(openapi_dir, exist_ok=True)

            json_path = os.path.join(openapi_dir, 'openapi.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(spec_dict, f, indent=2, ensure_ascii=False)

            try:
                import yaml
                yaml_path = os.path.join(openapi_dir, 'openapi.yaml')
                with open(yaml_path, 'w', encoding='utf-8') as f:
                    yaml.dump(spec_dict, f, default_flow_style=False, allow_unicode=True)
            except ImportError:
                pass
        except Exception as e:
            logger.error(f"Error exporting OpenAPI spec: {e}")

    return response


# ========== Startup ==========

with app.app_context():
    print(" * API Docs (Swagger): http://localhost:5004/api/docs")
    print(" * API Docs (ReDoc):   http://localhost:5004/api/redoc")

if __name__ == '__main__':
    app.run(debug=True, port=5004)
