"""Real loopback HTTP transport tests; no downloaded model or browser is needed."""
import http.client
import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from webqa.llm import chat, model_request

SCHEMA = {"type": "object", "required": ["answer"], "properties": {"answer": {"type": "string"}}}


@contextmanager
def model_server(monkeypatch, responder):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert body['stream'] is True and body['think'] is False
            assert body['options']['num_predict'] == 4096
            assert self.path == '/api/chat'
            try:
                responder(self, body)
            except (BrokenPipeError, ConnectionResetError):
                pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
    thread.start()
    original = http.client.HTTPConnection
    def connection(host, port, timeout):
        assert host == '127.0.0.1' and port == 11434
        return original(host, server.server_port, timeout=timeout)
    monkeypatch.setattr('webqa.llm.http.client.HTTPConnection', connection)
    try:
        yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def send(handler, messages):
    handler.send_response(200)
    handler.end_headers()
    for message in messages:
        handler.wfile.write(json.dumps(message).encode() + b'\n')
        handler.wfile.flush()


def test_streaming_accumulates_content_and_reports_progress(monkeypatch):
    messages = []
    def responder(handler, body):
        assert body['options']['num_ctx'] == 8192
        send(handler, [{'message': {'content': '{"answer":'}},
                       {'message': {'content': '"Complete"}'}, 'done': True}])
    with model_server(monkeypatch, responder), model_request(600, messages.append):
        assert chat('local-model', 'Instructions', {}, SCHEMA) == {'answer': 'Complete'}
    assert any('responding' in message for message in messages)
    assert messages[-1].startswith('Checking')


@pytest.mark.parametrize('stage', ['before-headers', 'during-response', 'continuous-stream'])
def test_deadline_interrupts_loading_stalled_and_trickling_responses(monkeypatch, stage):
    def responder(handler, _):
        if stage == 'before-headers':
            time.sleep(.2)
        handler.send_response(200)
        handler.end_headers()
        if stage == 'continuous-stream':
            for _ in range(15):
                handler.wfile.write(b'{"message":{"content":" "}}\n')
                handler.wfile.flush()
                time.sleep(.02)
        else:
            time.sleep(.2)
    started = time.monotonic()
    with model_server(monkeypatch, responder):
        with pytest.raises(ValueError, match='longer AI wait time'):
            chat('local-model', '', {}, SCHEMA, timeout=.07)
    assert time.monotonic() - started < 1


@pytest.mark.parametrize('messages,match', [
    ([{'message': {'content': '{"answer":"partial"}'}}], 'ended before'),
    ([{'message': {'content': '{}'}, 'done': True, 'done_reason': 'length'}], 'fewer tests'),
    ([{'error': 'out of memory'}], 'out of memory'),
])
def test_incomplete_and_server_error_responses_are_not_accepted(monkeypatch, messages, match):
    with model_server(monkeypatch, lambda h, _: send(h, messages)):
        with pytest.raises(ValueError, match=match):
            chat('local-model', '', {}, SCHEMA)


def test_model_not_installed_is_actionable(monkeypatch):
    def responder(handler, _):
        handler.send_response(404)
        handler.end_headers()
        handler.wfile.write(b'{"error":"not found"}')
    with model_server(monkeypatch, responder):
        with pytest.raises(ValueError, match='not installed'):
            chat('missing-model', '', {}, SCHEMA)


def test_prompt_size_limit_is_explicit_not_silent_truncation():
    with pytest.raises(ValueError, match='too large'):
        chat('model', '', {'request': 'x' * 50000}, SCHEMA)
