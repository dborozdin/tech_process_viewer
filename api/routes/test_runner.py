"""Test runner — выполняет сценарии из openapi/test_API_settings.json по группам.

Endpoints (Smorest, /api/v1/test-runner):
- POST /run         body: {"group": "<group_key>"}    — запустить группу
- POST /run-all                                       — запустить все группы
- GET  /history?group=<key>                           — последний JSON-отчёт группы
- GET  /history                                       — все группы

Результаты сохраняются в openapi/test_API_results_<safe_group>.json
"""

import os
import re
import json
import time
import datetime
from urllib.parse import urlparse

import requests as _http
from flask import current_app
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from ..schemas.common_schemas import fields as _f
import marshmallow as _ma


blp = Blueprint(
    "test_runner",
    __name__,
    url_prefix="/api/v1/test-runner",
    description="Run grouped API smoke-tests defined in openapi/test_API_settings.json",
)


_TPV_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_PATH = os.path.join(_TPV_DIR, "openapi", "test_API_settings.json")
RESULTS_DIR = os.path.join(_TPV_DIR, "openapi")


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name)


def _load_settings():
    if not os.path.exists(SETTINGS_PATH):
        abort(500, message=f"Settings file not found: {SETTINGS_PATH}")
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_results(group: str, report: dict):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"test_API_results_{_safe(group)}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)


def _load_results(group: str):
    path = os.path.join(RESULTS_DIR, f"test_API_results_{_safe(group)}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _interp(template, state):
    """Replace {key} placeholders in str/dict/list with values from state."""
    if isinstance(template, str):
        def repl(m):
            k = m.group(1)
            return str(state.get(k, m.group(0)))
        return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", repl, template)
    if isinstance(template, dict):
        return {k: _interp(v, state) for k, v in template.items()}
    if isinstance(template, list):
        return [_interp(v, state) for v in template]
    return template


def _jsonpath_get(obj, path):
    """Tiny JSONPath-ish: '$.foo[0].bar' → obj['foo'][0]['bar']."""
    if not path or not path.startswith("$"):
        return None
    p = path[1:]
    if p.startswith("."):
        p = p[1:]
    cur = obj
    parts = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\[\d+\]", p)
    for part in parts:
        if part.startswith("["):
            try:
                cur = cur[int(part[1:-1])]
            except (KeyError, IndexError, TypeError):
                return None
        else:
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return None
        if cur is None:
            return None
    return cur


def _origin_from_request_url(req_url):
    p = urlparse(req_url)
    return f"{p.scheme}://{p.netloc}"


def _run_scenario(base_url, step, state, default_db):
    method = step["method"].upper()
    path = _interp(step["path"], state)
    body = step.get("body")
    if step.get("body_from") == "db":
        body = default_db
    elif body is not None:
        body = _interp(body, state)

    expect = step.get("expect_status", 200)
    if not isinstance(expect, list):
        expect = [expect]

    started = time.perf_counter()
    headers = {"Content-Type": "application/json"} if body is not None else {}
    try:
        resp = _http.request(method, base_url + path,
                             json=body if body is not None else None,
                             headers=headers, timeout=60)
        duration_ms = int((time.perf_counter() - started) * 1000)
        try:
            resp_body = resp.json()
        except Exception:
            resp_body = resp.text[:500]

        status = "PASS" if resp.status_code in expect else "FAIL"

        # Capture saved fields
        saved = {}
        if status == "PASS" and isinstance(step.get("save_as"), dict):
            for key, jp in step["save_as"].items():
                val = _jsonpath_get(resp_body, jp)
                if val is not None:
                    state[key] = val
                    saved[key] = val

        # Build preview / error
        preview = ""
        error = ""
        if status == "PASS":
            try:
                preview = json.dumps(resp_body, ensure_ascii=False)[:400]
            except Exception:
                preview = str(resp_body)[:400]
        else:
            error = f"HTTP {resp.status_code} (expected {expect}); body: {str(resp_body)[:300]}"

        return {
            "scenario": step["id"],
            "method": method,
            "path": path,
            "http_status": resp.status_code,
            "duration_ms": duration_ms,
            "status": status,
            "saved": saved,
            "response_preview": preview,
            "error": error,
        }
    except Exception as e:
        return {
            "scenario": step["id"],
            "method": method,
            "path": path,
            "http_status": 0,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "status": "FAIL",
            "saved": {},
            "response_preview": "",
            "error": f"Exception: {e!r}",
        }


def _run_group(base_url, group_key, group_def, default_db, do_connect=True):
    state = {}
    started_at = datetime.datetime.now()

    # Pre-step: ensure DB connect (kept session via shared cookies / server-side)
    if do_connect:
        _http.post(base_url + "/api/connect", json=default_db, timeout=10)

    results = []
    for step in group_def.get("scenarios", []):
        results.append(_run_scenario(base_url, step, state, default_db))

    finished_at = datetime.datetime.now()
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    return {
        "group": group_key,
        "title": group_def.get("title", group_key),
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_s": int((finished_at - started_at).total_seconds()),
        "summary": {"total": len(results), "passed": passed, "failed": failed},
        "results": results,
    }


# ─── Schemas ────────────────────────────────────────────────────────

class _RunRequestSchema(_ma.Schema):
    class Meta:
        unknown = _ma.EXCLUDE
    group = _f.Str(required=True, description="Group key from test_API_settings.json")


class _ScenarioResultSchema(_ma.Schema):
    class Meta:
        unknown = _ma.EXCLUDE
    scenario = _f.Str()
    method = _f.Str()
    path = _f.Str()
    http_status = _f.Int()
    duration_ms = _f.Int()
    status = _f.Str()
    saved = _f.Dict()
    response_preview = _f.Str()
    error = _f.Str()


class _RunResponseSchema(_ma.Schema):
    class Meta:
        unknown = _ma.EXCLUDE
    group = _f.Str()
    title = _f.Str()
    started_at = _f.Str()
    finished_at = _f.Str()
    duration_s = _f.Int()
    summary = _f.Dict()
    results = _f.List(_f.Nested(_ScenarioResultSchema))


class _AllRunResponseSchema(_ma.Schema):
    class Meta:
        unknown = _ma.EXCLUDE
    groups = _f.Dict()
    summary = _f.Dict()


class _HistoryAllResponseSchema(_ma.Schema):
    class Meta:
        unknown = _ma.EXCLUDE
    groups = _f.Dict()


# ─── Endpoints ──────────────────────────────────────────────────────

@blp.route("/run")
class TestRunnerRun(MethodView):
    @blp.arguments(_RunRequestSchema)
    @blp.response(200, _RunResponseSchema)
    @blp.doc(description=("Запустить все сценарии указанной группы. Возвращает JSON-отчёт "
                          "и сохраняет копию в openapi/test_API_results_<group>.json"))
    def post(self, data):
        settings = _load_settings()
        group = data["group"]
        if group not in settings.get("groups", {}):
            abort(404, message=f"Unknown group '{group}'. Known: {list(settings.get('groups', {}).keys())}")
        # base_url from current request (так test-runner работает на той же машине)
        from flask import request as _req
        base_url = _origin_from_request_url(_req.url_root + "_x")
        report = _run_group(base_url, group, settings["groups"][group], settings["db"])
        _save_results(group, report)
        return report


@blp.route("/run-all")
class TestRunnerRunAll(MethodView):
    @blp.response(200, _AllRunResponseSchema)
    @blp.doc(description="Запустить все группы по порядку. Каждая группа сохраняется отдельно.")
    def post(self):
        settings = _load_settings()
        from flask import request as _req
        base_url = _origin_from_request_url(_req.url_root + "_x")
        groups_out = {}
        total_pass = total_fail = 0
        for gk, gdef in settings.get("groups", {}).items():
            rep = _run_group(base_url, gk, gdef, settings["db"])
            _save_results(gk, rep)
            groups_out[gk] = rep
            total_pass += rep["summary"]["passed"]
            total_fail += rep["summary"]["failed"]
        return {"groups": groups_out,
                "summary": {"total_groups": len(groups_out),
                            "passed": total_pass, "failed": total_fail}}


@blp.route("/history")
class TestRunnerHistory(MethodView):
    @blp.response(200)
    @blp.doc(description=("Последний сохранённый JSON-отчёт. Если ?group= указан — для одной группы; "
                          "иначе — словарь по всем группам, у которых есть история."))
    def get(self):
        from flask import request as _req
        group = _req.args.get("group", "").strip()
        if group:
            data = _load_results(group)
            if data is None:
                return {"group": group, "results": None, "message": "no history yet"}
            return data
        # all
        out = {}
        for fn in os.listdir(RESULTS_DIR):
            m = re.match(r"^test_API_results_(.+)\.json$", fn)
            if not m: continue
            gk = m.group(1)
            data = _load_results(gk)
            if data: out[gk] = data
        return {"groups": out}


@blp.route("/groups")
class TestRunnerGroups(MethodView):
    @blp.response(200)
    @blp.doc(description="Метаданные групп из test_API_settings.json (без выполнения тестов).")
    def get(self):
        settings = _load_settings()
        return {
            "db_target": settings.get("db", {}),
            "groups": {k: {"title": v.get("title", k),
                            "scenarios": [s["id"] for s in v.get("scenarios", [])]}
                        for k, v in settings.get("groups", {}).items()}
        }
