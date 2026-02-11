"""
Authentication routes for database connection.
Provides endpoints for connecting to PSS database and managing sessions.
"""
import requests
from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from marshmallow import Schema, fields

from tech_process_viewer.api.pss_api import DatabaseAPI


blp = Blueprint(
    'auth',
    __name__,
    url_prefix='/api',
    description='Database authentication and session management'
)


class ConnectRequestSchema(Schema):
    """Schema for database connection request"""
    server_port = fields.String(
        load_default='http://localhost:7239',
        metadata={'description': 'PSS server URL (e.g., http://localhost:7239)'}
    )
    db = fields.String(
        load_default='pss_moma_08_07_2025',
        metadata={'description': 'Database name to connect to'}
    )
    user = fields.String(
        load_default='Administrator',
        metadata={'description': 'Username for authentication'}
    )
    password = fields.String(
        load_default='',
        metadata={'description': 'Password (optional, not used in current implementation)'}
    )


class ConnectResponseSchema(Schema):
    """Schema for successful connection response"""
    connected = fields.Boolean(metadata={'description': 'Connection status'})
    session_key = fields.String(metadata={'description': 'Session key for X-APL-SessionKey header'})
    db = fields.String(metadata={'description': 'Connected database name'})
    user = fields.String(metadata={'description': 'Connected user'})


class ErrorResponseSchema(Schema):
    """Schema for error response"""
    connected = fields.Boolean(metadata={'description': 'Connection status (false)'})
    message = fields.String(metadata={'description': 'Error message'})


class DisconnectResponseSchema(Schema):
    """Schema for disconnect response"""
    disconnected = fields.Boolean(metadata={'description': 'Disconnection status'})
    message = fields.String(metadata={'description': 'Status message'})


class DatabaseListItemSchema(Schema):
    """Schema for a single database in the list"""
    name = fields.String(metadata={'description': 'Database name'})


def get_app_api():
    """Get the Flask app module"""
    from tech_process_viewer import app as flask_app
    return flask_app


@blp.route('/connect')
class Connect(MethodView):
    """Database connection endpoint"""

    @blp.arguments(ConnectRequestSchema)
    @blp.response(200, ConnectResponseSchema)
    @blp.alt_response(500, schema=ErrorResponseSchema, description="Connection failed")
    @blp.doc(
        security=[],  # No auth required for connect
        description="""Connect to PSS database and obtain a session key.

**Usage:**
1. Call this endpoint with connection parameters
2. Copy the `session_key` from the response
3. Click "Authorize" button in Swagger UI
4. Paste the session_key into the value field
5. All subsequent API calls will use this session key

**Default values** will connect to local development database."""
    )
    def post(self, args):
        """Connect to PSS database

        Returns a session_key to use in X-APL-SessionKey header for all subsequent requests.
        """
        flask_app = get_app_api()

        try:
            server_port = args.get('server_port', 'http://localhost:7239')
            db = args.get('db', 'pss_moma_08_07_2025')
            user = args.get('user', 'Administrator')

            # Build credentials and URL
            credentials = f'user={user}&db={db}'
            url_db_api = server_port + '/rest'

            # Create DatabaseAPI instance and connect
            api_instance = DatabaseAPI(url_db_api, credentials)
            session_key = api_instance.reconnect_db()

            if session_key:
                # Use the set_api function to store API in Flask app.extensions
                flask_app.set_api(api_instance)

            if session_key is None:
                return jsonify({
                    'connected': False,
                    'message': 'Failed to connect to DB. Check server address and credentials.'
                }), 500

            return jsonify({
                'connected': True,
                'session_key': session_key,
                'db': db,
                'user': user
            })

        except Exception as e:
            return jsonify({
                'connected': False,
                'message': str(e)
            }), 500


@blp.route('/disconnect')
class Disconnect(MethodView):
    """Database disconnection endpoint"""

    @blp.response(200, DisconnectResponseSchema)
    @blp.doc(description="Disconnect from PSS database and invalidate the session key.")
    def post(self):
        """Disconnect from PSS database"""
        flask_app = get_app_api()

        try:
            api_instance = flask_app.get_api()
            if api_instance is not None and api_instance.connect_data is not None:
                api_instance.disconnect_db()
                flask_app.set_api(None)
                return jsonify({
                    'disconnected': True,
                    'message': 'Successfully disconnected from database'
                })
            else:
                return jsonify({
                    'disconnected': True,
                    'message': 'No active connection to disconnect'
                })

        except Exception as e:
            return jsonify({
                'disconnected': False,
                'message': str(e)
            }), 500


@blp.route('/dblist')
class DatabaseList(MethodView):
    """Get list of available databases"""

    @blp.doc(
        security=[],  # No auth required
        description="Get list of available databases from PSS server. No authentication required."
    )
    def get(self):
        """Get list of available databases"""
        try:
            response = requests.get('http://localhost:7239/rest/dblist/')
            response.raise_for_status()
            return jsonify(response.json())
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@blp.route('/status')
class ConnectionStatus(MethodView):
    """Check current connection status"""

    @blp.doc(
        security=[],  # No auth required to check status
        description="Check if currently connected to a database."
    )
    def get(self):
        """Check connection status"""
        flask_app = get_app_api()
        api_instance = flask_app.get_api()

        if api_instance is not None and api_instance.connect_data is not None:
            return jsonify({
                'connected': True,
                'session_key': api_instance.connect_data.get('session_key', '')[:8] + '...',  # Partial key for security
                'message': 'Connected to database'
            })
        else:
            return jsonify({
                'connected': False,
                'message': 'Not connected to database. Use POST /api/connect to connect.'
            })
