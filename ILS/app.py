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
LLM_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'data', 'llm_config.json')
TOOL_SUPPORT_CACHE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'tool_support_cache.json')
HISTORY_MAX = 100
schema = None
agent = None

# ---------------------------------------------------------------------------
# LLM provider presets and runtime config
# ---------------------------------------------------------------------------

LLM_PROVIDERS = {
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": Config.LLM_API_KEY,
        "model": Config.LLM_MODEL,
        "needs_api_key": True,
    },
    "ollama": {
        "label": "Ollama (bolt.cals.ru)",
        "base_url": "http://bolt.cals.ru:38386/v1",
        "api_key": "not-needed",
        "model": "qwen2.5:32b",
        "needs_api_key": False,
    },
}

def _load_llm_config() -> dict:
    """Load saved LLM config from file, falling back to Ollama defaults."""
    defaults = {
        "provider": "ollama",
        "base_url": LLM_PROVIDERS["ollama"]["base_url"],
        "api_key": LLM_PROVIDERS["ollama"]["api_key"],
        "model": LLM_PROVIDERS["ollama"]["model"],
        "temperature": Config.LLM_TEMPERATURE,
        "max_tokens": 8192,
    }
    if os.path.exists(LLM_CONFIG_PATH):
        try:
            with open(LLM_CONFIG_PATH, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            # Validate provider exists
            if saved.get("provider") in LLM_PROVIDERS:
                defaults.update(saved)
                logger.info(f"LLM config loaded: {saved.get('provider')}/{saved.get('model')}")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load LLM config: {e}")
    return defaults


def _save_llm_config():
    """Persist current LLM config to file."""
    try:
        os.makedirs(os.path.dirname(LLM_CONFIG_PATH), exist_ok=True)
        with open(LLM_CONFIG_PATH, 'w', encoding='utf-8') as f:
            # Don't persist API keys for security
            save_data = {k: v for k, v in llm_config.items() if k != "api_key"}
            json.dump(save_data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning(f"Failed to save LLM config: {e}")


llm_config = _load_llm_config()


def _load_tool_cache() -> dict:
    """Load cached tool-support check results."""
    if os.path.exists(TOOL_SUPPORT_CACHE_PATH):
        try:
            with open(TOOL_SUPPORT_CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_tool_cache(cache: dict):
    """Persist tool-support cache."""
    try:
        os.makedirs(os.path.dirname(TOOL_SUPPORT_CACHE_PATH), exist_ok=True)
        with open(TOOL_SUPPORT_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning(f"Failed to save tool cache: {e}")


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
        base_url=llm_config["base_url"],
        api_key=llm_config["api_key"],
        model=llm_config["model"],
        temperature=llm_config["temperature"],
        max_tokens=llm_config["max_tokens"],
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
        "llm_model": llm_config["model"],
        "llm_provider": llm_config["provider"],
        "llm_base_url": llm_config["base_url"],
        "llm_temperature": llm_config["temperature"],
        "llm_max_tokens": llm_config["max_tokens"],
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
    if not llm_config["api_key"] or llm_config["provider"] != "openrouter":
        return jsonify({"available": False})
    try:
        resp = req.get('https://openrouter.ai/api/v1/key',
                       headers={'Authorization': f'Bearer {llm_config["api_key"]}'},
                       timeout=5)
        resp.raise_for_status()
        data = resp.json().get('data', {})
        return jsonify({"available": True, **data})
    except Exception as e:
        return jsonify({"available": False, "error": str(e)})


@app.route('/api/llm/providers')
def llm_providers_info():
    """Get available LLM providers and current config."""
    # Mask API key in response
    safe_config = {**llm_config}
    if safe_config.get("api_key") and len(safe_config["api_key"]) > 8:
        safe_config["api_key"] = safe_config["api_key"][:4] + "..." + safe_config["api_key"][-4:]
    return jsonify({
        "current": safe_config,
        "providers": {
            name: {"label": p["label"], "base_url": p["base_url"],
                    "default_model": p["model"], "needs_api_key": p["needs_api_key"]}
            for name, p in LLM_PROVIDERS.items()
        },
    })


@app.route('/api/llm/switch', methods=['POST'])
def llm_switch():
    """Switch LLM provider/model at runtime."""
    global agent
    data = request.get_json() or {}

    provider = data.get("provider", llm_config["provider"])
    if provider not in LLM_PROVIDERS:
        return jsonify({"error": f"Unknown provider: {provider}"}), 400

    preset = LLM_PROVIDERS[provider]
    llm_config["provider"] = provider
    llm_config["base_url"] = data.get("base_url") or preset["base_url"]
    llm_config["model"] = data.get("model") or preset["model"]
    llm_config["temperature"] = float(data.get("temperature", llm_config["temperature"]))
    llm_config["max_tokens"] = int(data.get("max_tokens", llm_config["max_tokens"]))

    # Update API key: for openrouter allow override, for ollama use preset
    if provider == "openrouter" and data.get("api_key"):
        llm_config["api_key"] = data["api_key"]
    elif provider != "openrouter":
        llm_config["api_key"] = preset["api_key"]

    # Force agent re-creation
    agent = None
    _save_llm_config()

    logger.info(f"LLM switched to {provider}: model={llm_config['model']}, "
                f"base_url={llm_config['base_url']}")

    safe_config = {**llm_config}
    if safe_config.get("api_key") and len(safe_config["api_key"]) > 8:
        safe_config["api_key"] = safe_config["api_key"][:4] + "..." + safe_config["api_key"][-4:]
    return jsonify({"switched": True, "config": safe_config})


def _parse_param_size(s: str) -> float | None:
    """Parse parameter size string like '32.8B' or '137M' to float in billions."""
    if not s:
        return None
    s = s.strip().upper()
    try:
        if s.endswith('B'):
            return float(s[:-1])
        elif s.endswith('M'):
            return float(s[:-1]) / 1000
    except ValueError:
        pass
    return None


@app.route('/api/llm/models')
def llm_models_list():
    """Fetch available models for a provider."""
    import requests as req
    provider = request.args.get("provider", llm_config["provider"])

    # Models recommended for agent tool-use tasks
    OLLAMA_RECOMMENDED = {"qwen2.5:32b", "qwen2.5:14b", "mistral-small3.1:24b"}
    # Families/names to skip (embeddings, tiny helpers)
    OLLAMA_SKIP_FAMILIES = {"nomic-bert", "bert"}
    OLLAMA_MIN_PARAMS_B = 2.0  # skip models smaller than 2B

    if provider == "ollama":
        ollama_base = LLM_PROVIDERS["ollama"]["base_url"].replace("/v1", "")
        try:
            resp = req.get(f"{ollama_base}/api/tags", timeout=10)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            tool_cache = _load_tool_cache()
            result = []
            for m in models:
                details = m.get("details", {})
                family = details.get("family", "")
                # Skip embedding models
                if family in OLLAMA_SKIP_FAMILIES:
                    continue
                param_str = details.get("parameter_size", "")
                param_b = _parse_param_size(param_str)
                if param_b and param_b < OLLAMA_MIN_PARAMS_B:
                    continue

                info = {"name": m["name"]}
                if param_str:
                    info["params"] = param_str
                if details.get("quantization_level"):
                    info["quant"] = details["quantization_level"]
                if family:
                    info["family"] = family
                # Mark recommended models
                if m["name"] in OLLAMA_RECOMMENDED:
                    info["recommended"] = True
                # Add note for special model types
                if "coder" in m["name"].lower():
                    info["note"] = "code, tools?"
                elif "deepseek-r1" in m["name"].lower() or "qwq" in m["name"].lower():
                    info["note"] = "reasoning"
                if param_b:
                    info["_param_b"] = param_b
                # Merge cached tool-support info
                cached = tool_cache.get(m["name"])
                if cached:
                    info["tools"] = cached["tools"]
                    info["tools_checked"] = cached["checked"]
                result.append(info)

            # Sort: tools=false last, then recommended first, then by param size desc
            result.sort(key=lambda x: (x.get("tools") is False,
                                        not x.get("recommended", False),
                                        -(x.get("_param_b") or 0)))
            # Remove internal sort key
            for r in result:
                r.pop("_param_b", None)

            return jsonify({"models": result})
        except Exception as e:
            return jsonify({"models": [], "error": str(e)})

    elif provider == "openrouter":
        # Curated list of useful free/popular models
        return jsonify({"models": [
            {"name": "nvidia/nemotron-3-super-120b-a12b:free"},
            {"name": "google/gemma-3-27b-it:free"},
            {"name": "deepseek/deepseek-chat-v3-0324:free"},
            {"name": "qwen/qwen-2.5-72b-instruct:free"},
            {"name": "meta-llama/llama-4-maverick:free"},
            {"name": "google/gemini-2.5-pro-exp-03-25:free"},
        ]})

    return jsonify({"models": []})


@app.route('/api/llm/pull', methods=['POST'])
def llm_pull():
    """Pull (download) a model on the Ollama server. Returns SSE stream with progress."""
    import requests as req
    data = request.get_json() or {}
    model_name = data.get("model", "").strip()
    if not model_name:
        return jsonify({"error": "Missing 'model'"}), 400

    ollama_base = LLM_PROVIDERS["ollama"]["base_url"].replace("/v1", "")

    def generate():
        try:
            resp = req.post(f"{ollama_base}/api/pull",
                            json={"name": model_name, "stream": True},
                            stream=True, timeout=600)
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    yield f"data: {line.decode('utf-8')}\n\n"
            yield 'data: {"status":"done"}\n\n'
        except Exception as e:
            yield f'data: {{"status":"error","error":"{str(e)}"}}\n\n'

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@app.route('/api/llm/check-tools', methods=['POST'])
def llm_check_tools():
    """Check which Ollama models support tool use. Returns SSE stream with progress."""
    import requests as req
    ollama_base = LLM_PROVIDERS["ollama"]["base_url"].replace("/v1", "")

    # Minimal tool definition for testing
    test_tools = [{"type": "function", "function": {
        "name": "test_tool", "description": "test",
        "parameters": {"type": "object", "properties": {}}
    }}]

    def generate():
        # Get model list
        try:
            resp = req.get(f"{ollama_base}/api/tags", timeout=10)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
        except Exception as e:
            yield f'data: {json.dumps({"status": "error", "error": str(e)})}\n\n'
            return

        cache = _load_tool_cache()
        checked = 0
        with_tools = 0
        without_tools = 0

        for model_name in models:
            yield f'data: {json.dumps({"model": model_name, "status": "checking"}, ensure_ascii=False)}\n\n'
            try:
                r = req.post(
                    f"{ollama_base}/v1/chat/completions",
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": "hi"}],
                        "tools": test_tools,
                        "max_tokens": 1,
                    },
                    timeout=60,
                )
                tools_ok = r.status_code == 200
                if r.status_code == 400:
                    tools_ok = False
                elif r.status_code != 200:
                    # Unexpected error — skip, don't cache
                    yield f'data: {json.dumps({"model": model_name, "status": "skip", "error": f"HTTP {r.status_code}"}, ensure_ascii=False)}\n\n'
                    continue

                cache[model_name] = {
                    "tools": tools_ok,
                    "checked": time.strftime('%Y-%m-%dT%H:%M:%S'),
                }
                checked += 1
                if tools_ok:
                    with_tools += 1
                else:
                    without_tools += 1
                yield f'data: {json.dumps({"model": model_name, "status": "done", "tools": tools_ok}, ensure_ascii=False)}\n\n'
            except Exception as e:
                yield f'data: {json.dumps({"model": model_name, "status": "skip", "error": str(e)}, ensure_ascii=False)}\n\n'

        _save_tool_cache(cache)
        yield f'data: {json.dumps({"status": "complete", "checked": checked, "with_tools": with_tools, "without_tools": without_tools})}\n\n'

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


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
    entry = {
        "question": question,
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
        "auto": data.get('auto', True),
    }
    if data.get('tool_calls'):
        entry['tool_calls'] = data['tool_calls']
    if data.get('api_calls'):
        entry['api_calls'] = data['api_calls']
    entries.insert(0, entry)
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


@app.route('/api/clear-context', methods=['POST'])
def clear_context():
    """Clear agent conversation history (start fresh dialogue)."""
    if agent:
        agent.clear_history()
    return jsonify({"cleared": True, "history_count": 0})


@app.route('/api/context-status')
def context_status():
    """Get current conversation context status."""
    count = agent.history_count if agent else 0
    return jsonify({"history_count": count})


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
    print(f" * LLM: {llm_config['model']} via {llm_config['base_url']} ({llm_config['provider']})")
    print(f" * PSS: {Config.PSS_REST_URL}")
    print(f" * DB: {Config.PSS_DB_NAME}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
