"""Entity Viewer — универсальный просмотрщик сущностей PSS.

Порт: 5003
Функции: просмотр/создание/редактирование/удаление любых сущностей в БД.

Запуск: python entity_viewer_app.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import render_template
from flask_smorest import Api

from tech_process_viewer.api.app_helpers import create_pss_app

app = create_pss_app(
    __name__,
    static_folder='static',
    template_folder='static/templates',
    port=5003
)

# Flask-Smorest for OpenAPI support in entity_viewer blueprint
api = Api(app)

# Register blueprints
from tech_process_viewer.api.routes.auth import blp as auth_blp
from tech_process_viewer.api.routes.entity_viewer import blp as entity_viewer_blp

api.register_blueprint(auth_blp)
api.register_blueprint(entity_viewer_blp)


# ========== HTML Routes ==========

@app.route('/')
@app.route('/entity-viewer')
@app.route('/entity-viewer/')
def entity_viewer_ui():
    """Main entity viewer UI"""
    return render_template('entity_viewer/index.html')

@app.route('/entity-viewer/entity/<entity_name>')
def entity_instances_ui(entity_name):
    """Entity instances list UI"""
    from tech_process_viewer.dict_parser import get_dict_parser
    parser = get_dict_parser()
    entity = parser.get_entity_by_name(entity_name)
    if not entity:
        return "Entity type not found", 404
    return render_template('entity_viewer/instances.html', entity_name=entity_name, entity=entity)

@app.route('/entity-viewer/instance/<int:instance_id>')
def instance_detail_ui(instance_id):
    """Instance detail and edit UI"""
    return render_template('entity_viewer/instance_detail.html', instance_id=instance_id)


# ========== Startup ==========

with app.app_context():
    print(" * Entity Viewer: http://localhost:5003/")

if __name__ == '__main__':
    app.run(debug=True, port=5003)
