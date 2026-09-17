"""Bounded streaming local-model transport with progress and an absolute deadline."""
import http.client
import json
import socket
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar

from jsonschema import validate

_OPTIONS = ContextVar("model_request", default={})


@contextmanager
def model_request(timeout=600, progress=None):
    if not 1 <= timeout <= 1200:
        raise ValueError("Choose an AI wait time between 1 and 1200 seconds")
    token = _OPTIONS.set({"timeout": timeout, "progress": progress})
    try:
        yield
    finally:
        _OPTIONS.reset(token)


def progress(message):
    callback = _OPTIONS.get().get("progress")
    if callback:
        callback(message)


def chat(model, system, packet, schema, timeout=None):
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError("Provide an installed local Ollama model name")
    limit = timeout if timeout is not None else _OPTIONS.get().get("timeout", 600)
    # Compact JSON and one schema copy reduce prefill work; never silently truncate input.
    user = json.dumps(packet, separators=(",", ":"), ensure_ascii=False)
    prompt_bytes = len((system + user + json.dumps(schema)).encode())
    if prompt_bytes > 44000:
        raise ValueError("This request is too large. Use a shorter request or a smaller website profile.")
    context = 8192 if prompt_bytes <= 14000 else 16384
    payload = {"model": model, "stream": True, "format": schema, "think": False, "keep_alive": "10m",
               "options": {"temperature": 0, "num_ctx": context, "num_predict": 4096},
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    conn = http.client.HTTPConnection("127.0.0.1", 11434, timeout=min(10, limit))
    expired = threading.Event()
    timer = None
    started = time.monotonic()
    try:
        progress("Connecting to Ollama on this computer…")
        conn.connect()
        sock = conn.sock
        sock.settimeout(limit)

        def expire():
            expired.set()
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        timer = threading.Timer(max(0.001, limit - (time.monotonic() - started)), expire)
        timer.daemon = True
        timer.start()
        conn.request("POST", "/api/chat", body=json.dumps(payload).encode(),
                     headers={"Content-Type": "application/json"})
        progress("Loading the model and reading the request. The first request can take longer…")
        response = conn.getresponse()
        if response.status != 200:
            detail = response.read(4096).decode("utf-8", errors="replace")
            if response.status == 404:
                raise ValueError("That model is not installed. Refresh models and choose an installed model.")
            raise ValueError(f"Ollama could not start this request (HTTP {response.status}). "
                             f"Try a smaller model or restart Ollama. Details: {detail[:500]}")
        pieces, size, done, chunks = [], 0, False, 0
        while True:
            raw = response.readline(1_000_001)
            if expired.is_set() or time.monotonic() - started >= limit:
                raise TimeoutError()
            if not raw:
                break
            size += len(raw)
            if size > 1_000_000:
                raise ValueError("Model response exceeded 1 MB")
            envelope = json.loads(raw)
            if envelope.get("error"):
                raise ValueError("Ollama reported: " + str(envelope["error"])[:500])
            content = envelope.get("message", {}).get("content", "")
            if not isinstance(content, str):
                raise ValueError("Ollama returned an invalid response")
            pieces.append(content)
            chunks += 1
            if chunks == 1 or chunks % 25 == 0:
                progress(f"The model is responding ({sum(map(len, pieces)):,} characters received)…")
            if envelope.get("done"):
                if envelope.get("done_reason") == "length":
                    raise ValueError("The model ran out of output space. Ask for fewer tests, or a smaller change.")
                done = True
                break
        if not done:
            raise ValueError("The model connection ended before its answer was complete. Try again.")
        progress("Checking the model’s answer…")
        result = json.loads("".join(pieces))
        validate(result, schema)
        return result
    except (TimeoutError, OSError, http.client.HTTPException) as exc:
        if expired.is_set() or isinstance(exc, TimeoutError):
            raise ValueError(f"The model did not finish within {limit:g} seconds. "
                             "Select a longer AI wait time, choose a smaller model, or request 1–3 tests. "
                             "No incomplete test proposal was applied.") from exc
        raise ValueError("Could not connect to Ollama or its connection was interrupted. "
                         "Open Ollama, refresh models, and try again.") from exc
    finally:
        if timer:
            timer.cancel()
        conn.close()
