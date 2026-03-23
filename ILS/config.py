"""Configuration for ILS Report Agent."""

import os


class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'ils-dev-secret-key')
    DEBUG = True
    PORT = 5001

    # PSS REST API
    PSS_SERVER = os.environ.get('PSS_SERVER', 'http://localhost:7239')
    PSS_REST_URL = f"{PSS_SERVER}/rest"
    PSS_DB_NAME = os.environ.get('PSS_DB_NAME', 'ils_lessons12')
    PSS_DB_USER = os.environ.get('PSS_DB_USER', 'Administrator')
    PSS_DB_PASSWORD = os.environ.get('PSS_DB_PASSWORD', '')

    # LLM Configuration (OpenAI-compatible API)
    # Supported providers:
    #   OpenRouter: base_url="https://openrouter.ai/api/v1", model="qwen/qwen-2.5-72b-instruct"
    #   Groq:       base_url="https://api.groq.com/openai/v1", model="llama-3.1-70b-versatile"
    #   Ollama:     base_url="http://localhost:11434/v1", model="qwen2.5:32b"
    #   OpenAI:     base_url="https://api.openai.com/v1", model="gpt-4o"
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://openrouter.ai/api/v1')
    LLM_API_KEY = os.environ.get('LLM_API_KEY', '').strip()
    LLM_MODEL = os.environ.get('LLM_MODEL', 'nvidia/nemotron-3-super-120b-a12b:free')
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.1'))
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '8192'))

    # Agent settings
    AGENT_MAX_ITERATIONS = int(os.environ.get('AGENT_MAX_ITERATIONS', '15'))

    # Data paths
    # ILS/ is inside tech_process_viewer/, which is inside express_api/
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # express_api/
    _VIEWER_ROOT = os.path.dirname(os.path.dirname(__file__))  # tech_process_viewer/

    DICT_FILE_PATH = os.path.join(_PROJECT_ROOT, 'doc', 'apl_pss_a.dict')
    HTML_SCHEMA_PATH = os.path.join(_VIEWER_ROOT, 'db_schema_doc', 'apl_pss_a_1419_data.htm')
