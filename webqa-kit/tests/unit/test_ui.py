import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from webqa.ui import LocalApp, handler


@pytest.fixture
def app(tmp_path):
    instance = LocalApp(tmp_path)
    yield instance
    instance.pool.shutdown(wait=True)


def test_nontechnical_target_setup_supports_pages_and_heading(app):
    saved = app.save_site('example.com', '/contact | Contact us\n/about')
    profile = json.loads((app.site(saved['id']) / 'profile.json').read_text())
    assert saved['pages'] == 3
    assert profile['pages'][1]['h1_contains'] == 'Contact us'
    assert app.state()['websites'][0]['url'] == 'https://example.com'
    ctg = app.save_site('https://www.capitaltg.com')
    assert len(json.loads((app.site(ctg['id']) / 'profile.json').read_text())['journeys']) == 12


@pytest.mark.parametrize('url,pages', [('https://example.com/path', ''), ('https://example.com', '/admin'),
    ('https://example.com', 'https://elsewhere.example/page'), ('https://example.com', '/?secret=x')])
def test_target_editor_rejects_invalid_scopes(app, url, pages):
    with pytest.raises(ValueError):
        app.save_site(url, pages)


def test_jobs_serialize_and_return_human_readable_errors(app):
    gate = threading.Event()
    started = app.enqueue(lambda: gate.wait(2))
    with pytest.raises(ValueError, match='already running'):
        app.enqueue(lambda: None)
    gate.set()
    app.pool.shutdown(wait=True)
    assert app.jobs[started['job']]['status'] == 'done'


def test_http_app_has_accessible_labels_and_requires_session_token(app):
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler(app, 'test-session'))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urllib.request.urlopen(base) as response:
            html = response.read().decode()
        assert 'for="url"' in html and 'aria-live="polite"' in html and "const token='test-session'" in html
        body = json.dumps({'url': 'https://example.com'}).encode()
        request = urllib.request.Request(base + '/api/site', data=body, headers={'Content-Type': 'application/json'})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        assert error.value.code == 403
        request.add_header('X-WebQA-Token', 'test-session')
        with urllib.request.urlopen(request) as response:
            assert json.load(response)['pages'] == 1
        request = urllib.request.Request(base + '/report/../../secret/report.html')
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_ui_run_dispatch_uses_arguments_and_shows_failures(app, monkeypatch):
    saved = app.save_site('https://example.com')
    def fake_run(command, **kwargs):
        assert kwargs['check'] is False
        out = Path(command[command.index('--out') + 1]) / 'example' / 'one'
        out.mkdir(parents=True)
        (out / 'run.json').write_text('{}')
        (out / 'results.json').write_text(json.dumps({'summary': {'passed': 1, 'failed': 1}}))
        (out / 'report.html').write_text('<h1>Report</h1>')
        from subprocess import CompletedProcess
        return CompletedProcess(command, 1, 'one failure', '')
    monkeypatch.setattr('webqa.ui.subprocess.run', fake_run)
    queued = app.run(saved['id'])
    app.pool.shutdown(wait=True)
    result = app.jobs[queued['job']]['result']
    assert result['counts']['failed'] == 1 and result['exit_code'] == 1
    assert result['report'].startswith('/report/sites/')
    assert app.state()['websites'][0]['latest_result'] == result


def test_app_generate_review_apply_revise_workflow(app, monkeypatch):
    saved = app.save_site('https://example.com')
    plan = {'summary': 'Check accessibility', 'assumptions': ['Homepage is public'], 'tests': [
        {'id': 'home-a11y', 'kind': 'page', 'page': 'home', 'check': 'axe', 'viewport': 'desktop',
         'priority': 'P1', 'why': 'Find accessibility rule violations'}]}
    monkeypatch.setattr('webqa.authoring.chat', lambda *_: plan)
    job = app.author(saved['id'], 'Check accessibility', 'stub-model')
    app.pool.submit(lambda: None).result(timeout=10)
    proposed = app.jobs[job['job']]['result']
    assert proposed['validation']['live_browser_run'] is False
    target = app.site(saved['id']) / 'test_custom.py'
    assert not target.exists()
    app.apply(saved['id'], proposed['proposal'])
    assert target.exists() and app.state()['websites'][0]['has_tests']
    original = target.read_text()
    plan['tests'][0]['viewport'] = 'mobile'
    job = app.author(saved['id'], 'Check mobile width instead', 'stub-model', revise=True)
    app.pool.submit(lambda: None).result(timeout=10)
    proposed = app.jobs[job['job']]['result']
    assert target.read_text() == original
    app.apply(saved['id'], proposed['proposal'])
    assert target.read_text() != original


def test_latest_result_survives_reopening_and_stays_with_website(app, monkeypatch):
    first = app.save_site('https://example.com')
    second = app.save_site('https://www.capitaltg.com')
    result = {'kind': 'run', 'exit_code': 1, 'counts': {'failed': 2}, 'cases': [], 'report': None}
    (app.site(first['id']) / 'latest-result.json').write_text(json.dumps(result))
    reopened = LocalApp(app.workspace)
    try:
        sites = {s['id']: s for s in reopened.state()['websites']}
        assert sites[first['id']]['latest_result'] == result
        assert sites[second['id']]['latest_result'] is None
        (app.site(first['id']) / 'latest-result.json').write_text('interrupted write')
        assert reopened.latest_result(app.site(first['id'])) is None
    finally:
        reopened.pool.shutdown(wait=True)


def test_run_saves_report_before_slow_ai_and_retains_it_on_model_failure(app, monkeypatch):
    saved = app.save_site('https://example.com')
    def fake_run(command, **kwargs):
        out = Path(command[command.index('--out') + 1]) / 'example' / 'one'
        out.mkdir(parents=True)
        (out / 'run.json').write_text('{}')
        (out / 'results.json').write_text(json.dumps({'summary': {'failed': 1}, 'tests': [
            {'nodeid': 'test[home]', 'outcome': 'failed'}]}))
        from subprocess import CompletedProcess
        return CompletedProcess(command, 1, 'one failure', '')
    def unavailable(*_):
        preview = app.latest_result(app.site(saved['id']))
        assert preview['counts']['failed'] == 1
        assert preview['report'].endswith('/overview.html')
        raise ValueError('Model unavailable')
    monkeypatch.setattr('webqa.ui.subprocess.run', fake_run)
    monkeypatch.setattr('webqa.reporting.chat', unavailable)
    job = app.run(saved['id'], model='offline')
    app.pool.submit(lambda: None).result(timeout=5)
    result = app.jobs[job['job']]
    assert result['status'] == 'done'
    assert 'unavailable' in result['result']['ai_status']
    assert result['result']['exit_code'] == 1
    assert app.latest_result(app.site(saved['id']))['failures'][0]['case_id'] == 'home'


def test_ai_wait_settings_and_progress_reach_worker(app, monkeypatch):
    from webqa.llm import _OPTIONS, progress
    gate = threading.Event()
    entered = threading.Event()
    def work():
        assert _OPTIONS.get()['timeout'] == 1200
        progress('Model is responding')
        entered.set()
        gate.wait(2)
        return 'done'
    job = app.enqueue(work, ai_timeout=1200)
    assert entered.wait(1)
    assert app.jobs[job['job']]['message'] == 'Model is responding'
    gate.set()
    app.pool.submit(lambda: None).result(timeout=5)
    with pytest.raises(ValueError, match='wait time'):
        app.enqueue(lambda: None, ai_timeout=3600)


def test_report_http_serves_inline_report_and_png_but_not_arbitrary_files(app):
    saved = app.save_site('https://example.com')
    run = app.site(saved['id']) / 'reports' / ('a' * 32) / 'example' / 'run-1'
    shot = run / 'checks' / 'home' / 'failure-call.png'
    shot.parent.mkdir(parents=True)
    shot.write_bytes(b'\x89PNG\r\n\x1a\n')
    (run / 'overview.html').write_text('<h1>Readable report</h1>')
    (run / 'secret.json').write_text('not served')
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler(app, 'test-session'))
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}/report/' + run.relative_to(app.workspace).as_posix() + '/'
    try:
        with urllib.request.urlopen(base + 'overview.html') as response:
            assert b'Readable report' in response.read()
        with urllib.request.urlopen(base + 'checks/home/failure-call.png') as response:
            assert response.headers['Content-Type'] == 'image/png'
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + 'secret.json')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_reopening_ui_discovers_active_job(app):
    gate = threading.Event()
    job = app.enqueue(lambda: gate.wait(2))
    try:
        state = app.state()
        assert state['active_job']['id'] == job['job']
        assert state['active_job']['status'] == 'running'
    finally:
        gate.set()
        app.pool.submit(lambda: None).result(timeout=5)
    assert app.state()['active_job'] is None
