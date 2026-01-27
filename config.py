"""
Configuration for Flask-Smorest and OpenAPI documentation.
"""

import os


class Config:
    """Base configuration"""

    # Flask-Smorest configuration
    API_TITLE = "Tech Process Viewer API"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/api"
    OPENAPI_JSON_PATH = "openapi.json"
    OPENAPI_REDOC_PATH = "/redoc"
    OPENAPI_REDOC_URL = "https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"
    OPENAPI_SWAGGER_UI_PATH = "/docs"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    # API configuration
    API_SPEC_OPTIONS = {
        "info": {
            "description": "REST API for managing technical processes, products, documents, and resources in the PSS application",
            "contact": {
                "name": "API Support"
            },
            "license": {
                "name": "Proprietary"
            }
        },
        "servers": [
            {
                "url": "http://localhost:5000",
                "description": "Development server"
            },
            {
                "url": "http://localhost:7239",
                "description": "Backend PSS REST API server"
            }
        ],
        "components": {
            "securitySchemes": {
                "SessionKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-APL-SessionKey",
                    "description": "Session key obtained from /api/connect endpoint"
                }
            }
        },
        "security": [
            {
                "SessionKey": []
            }
        ]
    }

    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = True

    # File upload configuration
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size

    # CORS configuration (if needed)
    CORS_ENABLED = False

    # Database API configuration
    DEFAULT_DB_SERVER = "http://localhost:7239"
    DEFAULT_DB_NAME = "pss_moma_08_07_2025"
    DEFAULT_DB_USER = "Administrator"


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = False
    TESTING = True

    # Use test database
    DEFAULT_DB_NAME = "pss_test"


class ProductionConfig(Config):
    """Production configuration

    IMPORTANT: Set SECRET_KEY environment variable before deploying to production:
        export SECRET_KEY='your-secret-key-here'
    """
    DEBUG = False
    TESTING = False

    # Production operators MUST set SECRET_KEY environment variable
    SECRET_KEY = os.environ.get('SECRET_KEY')


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
