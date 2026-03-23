"""
ILS Report Agent — Flask application.
Run: python -m ILS.app
"""

import json
import logging
import os
import sys
import time

from flask import Flask, request, jsonify, Response, send_from_directory

from ILS.config import Config
from ILS.pss.api_client import PSSClient
from ILS.pss.schema import get_schema
from ILS.agent.llm_client import LLMClient
from ILS.agent.tool_executor import ToolExecutor
from ILS.agent.knowledge import KnowledgeStore
from ILS.agent.orchestrator import Agent
from ILS.agent.prompts import SYSTEM_PROMPT

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/ils_agent.log", encoding="utf-8", mode="w"),
    ],
)
logger = logging.getLogger("ils")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config.from_object(Config)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

pss_client = PSSClient(Config.PSS_REST_URL)
knowledge_store = KnowledgeStore(
    os.path.join(os.path.dirname(__file__), 'data', 'knowledge.json')
)
CUSTOM_INSTRUCTIONS_PATH = os.path.join(os.path.dirname(__file__), 'data', 'custom_instructions.txt')
QUERY_HISTORY_PATH = os.path.join(os.path.dirname(__file__), 'data', 'query_history.json')
HISTORY_MAX = 100
schema = None
agent = None


def _init_schema():
    global schema
    if schema is None:
        schema = get_schema(Config.DICT_FILE_PATH, Config.HTML_SCHEMA_PATH)
    return schema


def _init_agent():
    global agent
    if agent is not None:
        return agent

    _init_schema()

    llm = LLMClient(
        base_url=Config.LLM_BASE_URL,
        api_key=Config.LLM_API_KEY,
        model=Config.LLM_MODEL,
        temperature=Config.LLM_TEMPERATURE,
        max_tokens=Config.LLM_MAX_TOKENS,
    )
    executor = ToolExecutor(pss_client, schema, knowledge=knowledge_store)
    agent = Agent(llm, executor, schema, knowledge=knowledge_store,
                  max_iterations=Config.AGENT_MAX_ITERATIONS,
                  custom_instructions_path=CUSTOM_INSTRUCTIONS_PATH)
    return agent


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/connect', methods=['POST'])
def connect():
    """Connect to PSS database."""
    data = request.get_json() or {}
    db_name = data.get('db', Config.PSS_DB_NAME)
    user = data.get('user', Config.PSS_DB_USER)
    password = data.get('password', Config.PSS_DB_PASSWORD)

    # Support changing server at runtime
    server_port = data.get('server_port', '').strip()
    if server_port:
        pss_client.rest_url = server_port.rstrip('/') + '/rest'
        logger.info(f"PSS server changed to: {pss_client.rest_url}")

    try:
        session_key = pss_client.connect(db_name, user, password)
        _init_agent()
        return jsonify({
            "connected": True,
            "db": db_name,
            "user": user,
            "session_key": session_key[:8] + "...",
        })
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return jsonify({"connected": False, "error": str(e)}), 500


@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    """Disconnect from PSS database."""
    pss_client.disconnect()
    return jsonify({"disconnected": True})


@app.route('/api/status')
def status():
    """Check connection status."""
    return jsonify({
        "connected": pss_client.connected,
        "llm_model": Config.LLM_MODEL,
        "llm_provider": Config.LLM_BASE_URL,
        "defaults": {
            "server": Config.PSS_SERVER,
            "db": Config.PSS_DB_NAME,
            "user": Config.PSS_DB_USER,
        },
    })


@app.route('/api/llm-limits')
def llm_limits():
    """Get LLM API key usage/limits from OpenRouter."""
    import requests as req
    if not Config.LLM_API_KEY or 'openrouter' not in Config.LLM_BASE_URL:
        return jsonify({"available": False})
    try:
        resp = req.get('https://openrouter.ai/api/v1/key',
                       headers={'Authorization': f'Bearer {Config.LLM_API_KEY}'},
                       timeout=5)
        resp.raise_for_status()
        data = resp.json().get('data', {})
        return jsonify({"available": True, **data})
    except Exception as e:
        return jsonify({"available": False, "error": str(e)})


@app.route('/api/dblist')
def dblist():
    """Get list of available databases from PSS server."""
    import requests as req
    server = pss_client.rest_url.rsplit('/rest', 1)[0]
    try:
        resp = req.get(f"{server}/rest/dblist/", timeout=5)
        resp.raise_for_status()
        return jsonify(resp.json())
    except Exception as e:
        logger.warning(f"Failed to fetch dblist: {e}")
        # Fallback: return default db
        return jsonify([Config.PSS_DB_NAME])


@app.route('/api/settings/prompt', methods=['GET'])
def get_custom_prompt():
    """Get custom instructions text."""
    text = ""
    if os.path.exists(CUSTOM_INSTRUCTIONS_PATH):
        with open(CUSTOM_INSTRUCTIONS_PATH, 'r', encoding='utf-8') as f:
            text = f.read()
    return jsonify({"custom_instructions": text, "base_prompt": SYSTEM_PROMPT})


@app.route('/api/settings/prompt', methods=['POST'])
def save_custom_prompt():
    """Save custom instructions text."""
    data = request.get_json()
    text = data.get('custom_instructions', '')
    os.makedirs(os.path.dirname(CUSTOM_INSTRUCTIONS_PATH), exist_ok=True)
    with open(CUSTOM_INSTRUCTIONS_PATH, 'w', encoding='utf-8') as f:
        f.write(text)
    # Reset agent so system prompt is rebuilt on next ask()
    global agent
    agent = None
    logger.info(f"Custom instructions saved ({len(text)} chars)")
    return jsonify({"saved": True})


def _load_history():
    if os.path.exists(QUERY_HISTORY_PATH):
        with open(QUERY_HISTORY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def _save_history(entries):
    os.makedirs(os.path.dirname(QUERY_HISTORY_PATH), exist_ok=True)
    with open(QUERY_HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


@app.route('/api/history', methods=['GET'])
def get_history():
    """Get query history."""
    return jsonify({"entries": _load_history()})


@app.route('/api/history', methods=['POST'])
def add_history():
    """Add entry to query history."""
    data = request.get_json()
    question = data.get('question', '').strip()
    if not question:
        return jsonify({"error": "Missing 'question'"}), 400

    entries = _load_history()
    # Avoid duplicates of the same question (keep most recent)
    entries = [e for e in entries if e.get('question') != question]
    entries.insert(0, {
        "question": question,
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
        "auto": data.get('auto', True),
    })
    entries = entries[:HISTORY_MAX]
    _save_history(entries)
    return jsonify({"saved": True, "count": len(entries)})


@app.route('/api/history/<int:idx>', methods=['DELETE'])
def delete_history(idx):
    """Delete a history entry by index."""
    entries = _load_history()
    if 0 <= idx < len(entries):
        entries.pop(idx)
        _save_history(entries)
    return jsonify({"deleted": True, "count": len(entries)})


@app.route('/api/history', methods=['DELETE'])
def clear_history():
    """Clear all history."""
    _save_history([])
    return jsonify({"cleared": True})


@app.route('/api/ask', methods=['POST'])
def ask():
    """Ask the agent a question. Returns SSE stream of agent steps."""
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({"error": "Missing 'question' field"}), 400

    if not pss_client.connected:
        return jsonify({"error": "Not connected to database. Use POST /api/connect first."}), 400

    question = data['question']
    logger.info(f"User question: {question}")

    _init_agent()

    def generate():
        for step in agent.ask(question):
            event_data = json.dumps(step.to_dict(), ensure_ascii=False)
            yield f"data: {event_data}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


@app.route('/api/answer', methods=['POST'])
def answer_clarification():
    """Send user's answer to a pending clarification question. Returns SSE stream."""
    data = request.get_json()
    if not data or 'answer' not in data:
        return jsonify({"error": "Missing 'answer' field"}), 400

    if not pss_client.connected:
        return jsonify({"error": "Not connected to database."}), 400

    if agent is None:
        return jsonify({"error": "Agent not initialized."}), 400

    user_answer = data['answer']
    logger.info(f"User clarification answer: {user_answer}")

    def generate():
        for step in agent.continue_with_answer(user_answer):
            event_data = json.dumps(step.to_dict(), ensure_ascii=False)
            yield f"data: {event_data}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


@app.route('/api/ask_sync', methods=['POST'])
def ask_sync():
    """Ask the agent a question. Returns complete result (non-streaming)."""
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({"error": "Missing 'question' field"}), 400

    if not pss_client.connected:
        return jsonify({"error": "Not connected to database. Use POST /api/connect first."}), 400

    question = data['question']
    logger.info(f"User question (sync): {question}")

    _init_agent()
    result = agent.ask_sync(question)
    return jsonify(result)


@app.route('/api/schema/categories')
def schema_categories():
    """List entity categories from schema."""
    _init_schema()
    return jsonify(schema.get_categories())


@app.route('/api/schema/search')
def schema_search():
    """Search entities by keyword."""
    keyword = request.args.get('q', '')
    if not keyword:
        return jsonify({"error": "Missing 'q' parameter"}), 400
    _init_schema()
    return jsonify(schema.search_entities(keyword))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    os.makedirs("logs", exist_ok=True)
    print(f" * ILS Report Agent: http://localhost:{Config.PORT}/")
    print(f" * LLM: {Config.LLM_MODEL} via {Config.LLM_BASE_URL}")
    print(f" * PSS: {Config.PSS_REST_URL}")
    print(f" * DB: {Config.PSS_DB_NAME}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
