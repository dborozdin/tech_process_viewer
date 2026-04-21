"""Перехватчик всех HTTP-запросов к PSS REST API.

Monkey-patches requests.Session.send() чтобы логировать каждый запрос
к PSS-серверу (порт 7239) с полными заголовками, телом и ответом.

Включение: import pss_request_logger; pss_request_logger.install()
Лог: PSS-aiR/pss_requests.log
"""

import os
import time
import json
import datetime
import threading
import requests
from requests import adapters

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pss_requests.log")
PSS_PORT = "7239"

_lock = threading.Lock()
_original_send = None
_counter = 0
_log_file = None


def _log(msg):
    global _log_file
    with _lock:
        if _log_file is None:
            _log_file = open(LOG_PATH, "w", encoding="utf-8", buffering=1)  # line-buffered
            _log_file.write(f"=== PSS Request Log started {datetime.datetime.now().isoformat()} ===\n\n")
        _log_file.write(msg + "\n")
        _log_file.flush()


def _patched_send(self, request, **kwargs):
    global _counter

    # Only log requests to PSS server
    url = request.url or ""
    if f":{PSS_PORT}/" not in url:
        return _original_send(self, request, **kwargs)

    with _lock:
        _counter += 1
        n = _counter

    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    method = request.method
    body = request.body
    headers = dict(request.headers)

    # Log request
    lines = []
    lines.append(f"─── #{n} [{ts}] {method} {url} ───")
    lines.append(f"  Headers:")
    for k, v in headers.items():
        val = v[:60] + "..." if len(v) > 60 else v
        lines.append(f"    {k}: {val}")

    if body:
        body_str = body if isinstance(body, str) else body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
        # Pretty-print JSON if possible
        try:
            parsed = json.loads(body_str)
            body_pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
            if len(body_pretty) > 1500:
                body_pretty = body_pretty[:1500] + "\n  ... (truncated)"
        except (json.JSONDecodeError, TypeError):
            body_pretty = body_str[:1500]
        lines.append(f"  Body:")
        for bl in body_pretty.split("\n"):
            lines.append(f"    {bl}")

    _log("\n".join(lines))

    # Execute request
    start = time.perf_counter()
    error = None
    response = None
    try:
        response = _original_send(self, request, **kwargs)
    except Exception as e:
        error = e
        elapsed = time.perf_counter() - start
        _log(f"  >>> EXCEPTION after {elapsed:.3f}s: {type(e).__name__}: {str(e)[:200]}")
        _log(f"  >>> SERVER MAY BE DOWN <<<")
        _log("")
        raise

    elapsed = time.perf_counter() - start

    # Log response
    rlines = []
    rlines.append(f"  Response: HTTP {response.status_code}  Time: {elapsed:.3f}s")
    rlines.append(f"  Response Headers:")
    for k, v in response.headers.items():
        rlines.append(f"    {k}: {v[:80]}")

    resp_text = response.text or ""
    if resp_text:
        try:
            parsed_resp = json.loads(resp_text)
            resp_pretty = json.dumps(parsed_resp, ensure_ascii=False, indent=2)
            if len(resp_pretty) > 1500:
                resp_pretty = resp_pretty[:1500] + "\n  ... (truncated)"
        except (json.JSONDecodeError, TypeError):
            resp_pretty = resp_text[:1500]
        rlines.append(f"  Response Body:")
        for rl in resp_pretty.split("\n"):
            rlines.append(f"    {rl}")

    status = "OK" if response.ok else f"ERROR (HTTP {response.status_code})"
    rlines.append(f"  >>> {status} <<<")
    rlines.append("")

    _log("\n".join(rlines))
    return response


def install():
    """Включить логирование всех requests к PSS."""
    global _original_send
    if _original_send is not None:
        return  # Already installed

    _original_send = requests.adapters.HTTPAdapter.send
    requests.adapters.HTTPAdapter.send = _patched_send

    # Clear old log
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)

    print(f"[PSS Logger] Installed. Log: {LOG_PATH}")


def uninstall():
    """Отключить логирование."""
    global _original_send, _log_file
    if _original_send is not None:
        requests.adapters.HTTPAdapter.send = _original_send
        _original_send = None
    if _log_file:
        _log_file.close()
        _log_file = None
