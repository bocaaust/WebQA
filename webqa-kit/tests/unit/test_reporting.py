import base64
import json
from pathlib import Path

import pytest

from webqa.reporting import build_report, capture_failure, image_bytes

# A tiny fixture PNG, not an actual website screenshot.
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


class Page:
    first = property(lambda self: self)

    def locator(self, _):
        return self

    def count(self):
        return 1

    def is_visible(self):
        return True

    def screenshot(self, *, path, mask, **kwargs):
        assert mask
        Path(path).write_bytes(PNG)


@pytest.fixture
def failed_run(tmp_path):
    case = {'id': 'page--home--desktop--axe', 'viewport': 'desktop', 'check': 'axe',
            'spec': {'path': '/', 'why': 'Check accessibility'}}
    node = 'test_site.py::test[chromium-page--home--desktop--axe]'
    folder = tmp_path / 'checks' / case['id']
    folder.mkdir(parents=True)
    (folder / 'axe.json').write_text(json.dumps({'violations': [{'id': 'button-name', 'impact': 'critical',
        'help': 'Buttons must have discernible text', 'nodes': [{'target': ['button']}]}]}))
    capture_failure(Page(), case, folder, node, 'call', '<script>unsafe()</script> email=x@example.com')
    (tmp_path / 'results.json').write_text(json.dumps({'summary': {'failed': 1}, 'tests': [
        {'nodeid': node, 'outcome': 'failed'}]}))
    return tmp_path


def test_report_embeds_failure_and_element_images_and_escapes_evidence(failed_run):
    result = build_report(failed_run)
    failure = result['failures'][0]
    assert len(failure['screenshots']) == 2
    assert failure['rules'][0]['nodes'] == 1
    assert 'x@example.com' not in failure['message']
    document = (failed_run / 'overview.html').read_text()
    assert document.count('data:image/png;base64,') == 2
    assert '<script>unsafe()' not in document and '&lt;script&gt;' in document
    assert 'What happened:' in document and 'Rule-based' in document


def test_model_explanations_are_bound_to_evidence_and_leave_outcomes_unchanged(failed_run, monkeypatch):
    original = (failed_run / 'results.json').read_bytes()
    def model(_name, _system, packet, _schema):
        assert 'screenshots' not in str(packet) and 'data:image' not in str(packet)
        failure = packet['failures'][0]
        assert failure['rules'][0]['id'] == 'button-name'
        return {'explanations': [{'case_id': failure['case_id'], 'what_happened': 'A button has no accessible name.',
                'why_it_matters': 'A screen reader may not explain its purpose.',
                'next_step': 'Ask the website team to label the button and check it with a screen reader.'}]}
    monkeypatch.setattr('webqa.reporting.chat', model)
    result = build_report(failed_run, 'test-model')
    assert result['failures'][0]['source'].startswith('AI explanation')
    assert 'accessible name' in (failed_run / 'overview.html').read_text()
    assert (failed_run / 'results.json').read_bytes() == original


@pytest.mark.parametrize('reason', ['timeout', 'unknown-case'])
def test_report_survives_model_timeout_or_invented_case(failed_run, monkeypatch, reason):
    def model(*_):
        assert (failed_run / 'overview.html').exists()  # Report was saved before inference.
        if reason == 'timeout':
            raise TimeoutError('Model timed out')
        return {'explanations': [{'case_id': 'invented', 'what_happened': 'Fake',
                'why_it_matters': 'Fake', 'next_step': 'Fake'}]}
    monkeypatch.setattr('webqa.reporting.chat', model)
    result = build_report(failed_run, 'broken-model')
    assert result['ai_status'].startswith('AI explanation unavailable')
    assert result['failures'][0]['source'] == 'Rule-based explanation'
    assert 'data:image/png' in (failed_run / 'overview.html').read_text()


def test_screenshot_failure_does_not_discard_test_evidence(tmp_path):
    class ClosedPage(Page):
        def screenshot(self, **kwargs):
            raise ValueError('Page closed')
    record = capture_failure(ClosedPage(), {'id': 'home', 'viewport': 'desktop', 'spec': {'path': '/'}},
                             tmp_path, 'test[home]', 'setup', 'Page failed to load')
    assert record['screenshots'] == [] and 'unavailable' in record['screenshot_note']
    assert (tmp_path / 'failure-setup.json').is_file()


def test_missing_browser_has_specific_non_defect_explanation(tmp_path):
    (tmp_path / 'results.json').write_text(json.dumps({'summary': {'error': 1}, 'tests': [
        {'nodeid': 'test[home]', 'outcome': 'error', 'setup': {'outcome': 'failed',
            'crash': {'message': "Executable doesn't exist at /browser"}}}]}))
    result = build_report(tmp_path)
    assert 'not installed' in result['failures'][0]['what_happened']
    assert 'does not establish' in result['failures'][0]['why_it_matters']


def test_images_cannot_escape_run_directory(tmp_path):
    outside = tmp_path / 'outside.png'
    outside.write_bytes(PNG)
    root = tmp_path / 'run'
    root.mkdir()
    assert image_bytes(root, '../outside.png') is None
    (root / 'checks').mkdir()
    (root / 'checks' / 'link.png').symlink_to(outside)
    assert image_bytes(root, 'checks/link.png') is None


def test_real_pytest_hook_captures_before_fixture_teardown(tmp_path):
    import subprocess
    import sys
    from webqa.cli import new_profile
    case = {'id': 'home', 'viewport': 'desktop', 'spec': {'path': '/'}, 'priority': 'P1', 'kind': 'page'}
    config = tmp_path / 'profile.json'
    config.write_text(json.dumps(new_profile('fixture', 'https://example.com')))
    test = tmp_path / 'test_capture.py'
    test.write_text('''import pytest
from pathlib import Path
@pytest.fixture(autouse=True)
def bounded_browser():
    yield
@pytest.fixture
def page():
    class Page:
        alive = True
        def locator(self, selector): return self
        def screenshot(self, *, path, **kwargs):
            assert self.alive, "Screenshot attempted after teardown"
            Path(path).write_bytes(b"\\x89PNG\\r\\n\\x1a\\n")
    p = Page()
    yield p
    p.alive = False
@pytest.fixture
def broken(page):
    raise AssertionError("Setup failed intentionally")
''' + f'@pytest.mark.parametrize("case", [{case!r}], ids=["home"])\n'
        + 'def test_failure(page, case_output, case):\n    assert False, "Intentional test failure"\n'
        + f'@pytest.mark.parametrize("case", [{dict(case, id="setup-home")!r}], ids=["setup-home"])\n'
        + 'def test_setup_failure(page, case_output, case, broken):\n    pass\n')
    result = subprocess.run([sys.executable, '-m', 'pytest', str(test), '-p', 'webqa.pytest_plugin',
                             '--run-config', str(config), '--run-directory', str(tmp_path),
                             '--json-report', '--json-report-file', str(tmp_path / 'results.json'), '-q'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (tmp_path / 'checks/home/failure-call.png').exists()
    assert (tmp_path / 'checks/setup-home/failure-setup.png').exists()
    report = build_report(tmp_path)
    assert len(report['failures']) == 2
    assert all(len(f['screenshots']) == 1 for f in report['failures'])
