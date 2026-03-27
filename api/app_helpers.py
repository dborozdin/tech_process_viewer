"""Общие хелперы для всех приложений платформы PSS.

Используется в: tech_process_viewer_app, entity_viewer_app, api_docs_app, PSS-aiR.
"""

import os
from flask import Flask, current_app
from tech_process_viewer.config import config


def create_pss_app(name, static_folder='static', template_folder='static/templates', port=5000):
    """Создаёт Flask-приложение с общей конфигурацией PSS.

    Args:
        name: Имя приложения (для Flask)
        static_folder: Путь к статическим файлам
        template_folder: Путь к шаблонам
        port: Порт для запуска

    Returns:
        Flask: Настроенное Flask-приложение
    """
    app = Flask(name,
                static_folder=static_folder,
                static_url_path='',
                template_folder=template_folder)

    env = os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config[env])
    app.config['PORT'] = port

    if env == 'production':
        if not app.config.get('SECRET_KEY'):
            raise ValueError("SECRET_KEY environment variable must be set for production")
        if app.config.get('SECRET_KEY') == 'dev-secret-key-change-in-production':
            raise ValueError("Default SECRET_KEY cannot be used in production")

    # Хранилище для PSS API instance
    if 'pss_api' not in app.extensions:
        app.extensions['pss_api'] = None

    return app


def get_api():
    """Получить текущий экземпляр DatabaseAPI из контекста приложения."""
    return current_app.extensions.get('pss_api')


def set_api(api_instance):
    """Установить экземпляр DatabaseAPI в контексте приложения."""
    current_app.extensions['pss_api'] = api_instance
