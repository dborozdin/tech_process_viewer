"""PSS-aiR — Product Data Management web application.

Порт: 5002
Функции: папки, структура изделий (BOM), документы, техпроцессы, отчёты.

Запуск: python PSS-aiR/app.py
"""

import os
import sys

from flask import Flask, jsonify, request, send_from_directory

# Add PSS-aiR/ to path so 'services' and 'routes' are importable
_PSS_C_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PSS_C_DIR)
# Add grandparent directory (express_api/) to path so 'tech_process_viewer' package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(_PSS_C_DIR)))

from tech_process_viewer.api.pss_api import DatabaseAPI
from tech_process_viewer.globals import logger

app = Flask(__name__, static_folder='static', static_url_path='')
app.config['SECRET_KEY'] = 'pss-c-dev-secret'

# PSS API instance
_db_api = None


def get_db_api():
    return _db_api


# ========== Connection Management ==========

@app.route('/api/connect', methods=['POST'])
def connect():
    global _db_api
    data = request.get_json() or {}
    server = data.get('server_port', 'http://localhost:7239')
    db = data.get('db', 'pss_moma_08_07_2025')
    user = data.get('user', 'Administrator')
    password = data.get('password', '')

    rest_url = f"{server}/rest"
    credentials = f"user={user}&db={db}"
    if password:
        credentials += f"&password={password}"

    try:
        _db_api = DatabaseAPI(rest_url, credentials)
        _db_api.reconnect_db()
        app.config['db_api'] = _db_api
        logger.info(f"PSS-aiR connected to {db} as {user}")
        return jsonify({
            'connected': True,
            'session_key': _db_api.connect_data['session_key'],
            'db': db,
            'user': user
        })
    except Exception as e:
        logger.error(f"PSS-aiR connection error: {e}")
        _db_api = None
        return jsonify({'error': str(e)}), 500


@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    global _db_api
    if _db_api:
        try:
            _db_api.disconnect_db()
        except Exception:
            pass
        _db_api = None
    app.config['db_api'] = None
    return jsonify({'connected': False})


@app.route('/api/status')
def status():
    connected = _db_api is not None and _db_api.connect_data is not None
    return jsonify({'connected': connected})


@app.route('/api/dblist')
def dblist():
    server = request.args.get('server', 'http://localhost:7239')
    import requests as req
    try:
        resp = req.get(f"{server}/rest/dblist", timeout=5)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== Register Route Blueprints ==========

# PSS-aiR contains a hyphen which is invalid for Python imports,
# so we use relative imports from within the package
from routes.folders import bp as folders_bp
from routes.products import bp as products_bp
from routes.documents import bp as documents_bp
from routes.processes import bp as processes_bp
from routes.reports import bp as reports_bp

app.register_blueprint(folders_bp)
app.register_blueprint(products_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(processes_bp)
app.register_blueprint(reports_bp)


# ========== Static Files ==========

# Serve shared static files (db-connection.js, styles.css) from parent static/
_SHARED_STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')


@app.route('/shared/<path:filename>')
def shared_static(filename):
    return send_from_directory(_SHARED_STATIC, filename)


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


# ========== Startup ==========

if __name__ == '__main__':
    print(f" * PSS-aiR: http://localhost:5002/")
    app.run(debug=True, port=5002)
