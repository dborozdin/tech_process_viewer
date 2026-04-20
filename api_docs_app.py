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

api.register_blueprint(auth_blp)
api.register_blueprint(business_processes_blp)
api.register_blueprint(entity_viewer_blp)
api.register_blueprint(products_blp)
api.register_blueprint(documents_blp)
api.register_blueprint(resources_blp)
api.register_blueprint(organizations_blp)
api.register_blueprint(characteristics_blp)

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
