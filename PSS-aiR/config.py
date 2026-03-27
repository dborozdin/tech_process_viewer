"""Configuration for PSS-aiR application."""

import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'pss-c-dev-secret')
    DEBUG = True
    PORT = 5002

    # PSS REST API
    DEFAULT_DB_SERVER = os.environ.get('PSS_SERVER', 'http://localhost:7239')
    DEFAULT_DB_NAME = os.environ.get('PSS_DB_NAME', 'pss_moma_08_07_2025')
    DEFAULT_DB_USER = os.environ.get('PSS_DB_USER', 'Administrator')
    DEFAULT_DB_PASSWORD = os.environ.get('PSS_DB_PASSWORD', '')
