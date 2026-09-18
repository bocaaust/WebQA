import copy
import json

import pytest

from webqa.cloud_protocol import atomic_json, read_json, validate_request
from webqa.cloud_worker import process_request
from webqa.learning import ingest, review
from webqa.ui import LocalApp


@pytest.fixture
def app(tmp_path):
    app = LocalApp(tmp_path / 'app-data', tmp_path / 'app-folder' / 'Cloud-Inbox')
    yield app
    app.pool.shutdown(wait=True)


@pytest.fixture
def site(app):
    return app.save_site('https://example.com')['id']


def plan(viewport='desktop'):
    return {'summary': 'Verify homepage accessibility', 'assumptions': ['Homepage is public'], 'tests': [
        {'id': 'home-a11y', 'kind': 'page', 'page': 'home', 'check': 'axe', 'viewport': viewport,
         'priority': 'P1', 'why': 'Find barriers for visitors using assistive technology'}]}


def deliver(app, request, tmp_path, answer):
    path = process_request(request, 'controlled-test-model', tmp_path / 'colab-output',
                           progress=lambda _: None, infer=lambda *_: copy.deepcopy(answer))
    downloaded = app.cloud.inbox / path.name
    downloaded.write_bytes(path.read_bytes())
    return downloaded


def fake_run(app, site, failures=1):
    target = app.site(site)
    root = target / 'reports' / ('b' * 32) / 'example' / 'run-one'
    root.mkdir(parents=True)
    from webqa.config import load_profile
    from webqa.learning import site_key
    config = load_profile(target / 'profile.json')
    atomic_json(root / 'run.json', {'run_id': 'run-one', 'site_key': site_key(config), 'created': '2026-09-17', 'suite': 'full'})
    atomic_json(root / 'results.json', {'summary': {'failed': failures}, 'tests': [
        {'nodeid': f'test[case-{i}]', 'outcome': 'failed'} for i in range(failures)]})
    atomic_json(target / 'latest-run.json', {'path': str(root)})
    atomic_json(target / 'latest-result.json', {'kind': 'run', 'counts': {'failed': failures}, 'exit_code': 1,
                                               'cases': [], 'log': ''})
    ingest(app.db, root)
    return root


def test_create_round_trip_compiles_reviewable_tests_and_is_idempotent(app, site, tmp_path):
    request = app.cloud.export(site, 'develop', 'Create a homepage accessibility test')
    assert request['profile']['base_url'] == 'https://example.com'
    path = deliver(app, request, tmp_path, plan())
    assert app.cloud.scan()['files'][0]['status'] == 'ready'
    result = app.import_cloud(path.name)
    assert result['kind'] == 'proposal' and result['validation']['schema_valid']
    target = app.site(site) / 'test_custom.py'
    assert not target.exists()
    assert app.import_cloud(path.name)['proposal'] == result['proposal']
    app.apply(site, result['proposal'])
    assert target.exists()
    assert 'page_check' in target.read_text()
    from webqa.cli import main
    assert main(['run', '--config', str(app.site(site) / 'profile.json'), '--tests', str(target),
                 '--collect-only', '--out', str(tmp_path / 'collected')]) == 0
    assert app.import_cloud(path.name)['applied'] is True
    assert app.cloud.scan()['files'][0]['status'] == 'imported'


def test_revision_round_trip_preserves_tests_until_apply(app, site, tmp_path):
    first = app.cloud.export(site, 'develop', 'Create tests')
    proposal = app.import_cloud(deliver(app, first, tmp_path, plan()).name)
    app.apply(site, proposal['proposal'])
    target = app.site(site) / 'test_custom.py'
    before = target.read_bytes()
    revision = app.cloud.export(site, 'revise', 'Use mobile width')
    assert revision['jobs'][0]['input']['current_plan'] == plan()
    result = app.import_cloud(deliver(app, revision, tmp_path, plan('mobile')).name)
    assert target.read_bytes() == before
    app.apply(site, result['proposal'])
    assert target.read_bytes() != before


@pytest.mark.parametrize('change', ['profile', 'tests', 'result-hash', 'extra-job', 'arbitrary-code'])
def test_import_rejects_stale_mismatched_or_unsafe_results(app, site, tmp_path, change):
    request = app.cloud.export(site, 'develop', 'Create tests')
    path = deliver(app, request, tmp_path, plan())
    if change == 'profile':
        app.save_site('https://example.com', '/about')
    elif change == 'tests':
        (app.site(site) / 'test_custom.py').write_text('# another change')
    else:
        data = read_json(path)
        if change == 'result-hash':
            data['request_sha256'] = '0' * 64
        elif change == 'extra-job':
            data['outputs']['unexpected'] = {}
        else:
            data['outputs']['job-000']['python'] = 'import os; os.system("unwanted")'
        atomic_json(path, data)
    with pytest.raises(Exception):
        app.import_cloud(path.name)
    assert not list((app.site(site) / 'proposals').glob('*/proposal.json'))


def test_explanations_return_to_original_local_screenshots_without_changing_outcomes(app, site, tmp_path):
    run = fake_run(app, site, failures=13)
    original = (run / 'results.json').read_bytes()
    capture = run / 'checks' / 'case-0'
    capture.mkdir(parents=True)
    (capture / 'failure-call.png').write_bytes(b'\x89PNG\r\n\x1a\n')
    atomic_json(capture / 'failure-call.json', {'nodeid': 'test[case-0]', 'message': 'button missing name',
        'phase': 'call', 'check': 'axe', 'screenshots': [{'file': 'failure-call.png', 'caption': 'Fixture screenshot'}]})
    request = app.cloud.export(site, 'explain')
    assert len(request['jobs']) == 3  # All failures, not just the previous first twelve.
    assert '"screenshots"' not in json.dumps(request) and 'data:image' not in json.dumps(request)
    def explain(_m, _s, packet, _schema):
        return {'explanations': [{'case_id': f['case_id'], 'what_happened': 'A check failed.',
                'why_it_matters': 'A visitor may be affected.', 'next_step': 'Review the evidence.'}
                for f in packet['failures']]}
    cloud = process_request(request, 'controlled-test-model', tmp_path / 'output', infer=explain, progress=lambda _: None)
    downloaded = app.cloud.inbox / cloud.name
    downloaded.write_bytes(cloud.read_bytes())
    result = app.import_cloud(downloaded.name)
    assert len(result['failures']) == 13 and result['failures'][0]['source'].startswith('Colab')
    assert result['failures'][0]['screenshots'][0]['url'].endswith('failure-call.png')
    assert 'data:image/png' in (run / 'overview.html').read_text()
    assert (run / 'results.json').read_bytes() == original


def test_historical_reviews_are_available_to_cloud_guidance(app, site, tmp_path):
    run = fake_run(app, site)
    key = read_json(run / 'run.json')['site_key']
    review(app.db, key, 'case-0', 'accepted', 'Verified missing button name')
    request = app.cloud.export(site, 'advise')
    assert request['jobs'][0]['input']['human_reviews'][0]['resolution'].startswith('Verified')
    guidance = {'summary': 'Review recurring failures', 'suggestions': [
        {'case_id': 'case-0', 'hypothesis': 'The same missing label may persist',
         'next_check': 'Check the accessible name', 'confidence': 'medium'}]}
    result = app.import_cloud(deliver(app, request, tmp_path, guidance).name)
    assert result['kind'] == 'advice' and result['guidance']['source'] == 'colab'


def test_explanation_rejects_a_different_latest_run(app, site, tmp_path):
    run = fake_run(app, site)
    request = app.cloud.export(site, 'advise')
    path = deliver(app, request, tmp_path, {'summary': 'Review', 'suggestions': []})
    atomic_json(run / 'results.json', {'summary': {'passed': 1}, 'tests': []})
    with pytest.raises(ValueError, match='run changed'):
        app.import_cloud(path.name)


def test_checkpoint_resume_does_not_repeat_completed_jobs(app, site, tmp_path):
    fake_run(app, site, failures=7)
    request = app.cloud.export(site, 'explain')
    count = 0
    def model(_m, _s, packet, _schema):
        nonlocal count
        count += 1
        if count == 2:
            raise TimeoutError('Controlled timeout')
        return {'explanations': [{'case_id': f['case_id'], 'what_happened': 'Issue',
                                 'why_it_matters': 'Impact', 'next_step': 'Review'} for f in packet['failures']]}
    with pytest.raises(ValueError, match='Completed jobs were saved'):
        process_request(request, 'test', tmp_path / 'output', infer=model, progress=lambda _: None)
    assert not list((tmp_path / 'output').rglob('*.webqa-result.json'))
    path = process_request(request, 'test', tmp_path / 'output', infer=model, progress=lambda _: None)
    assert count == 3 and path.exists()


def test_inbox_rejects_shortcuts_foreign_requests_and_path_traversal(app, site, tmp_path):
    outside = tmp_path / 'outside.webqa-result.json'
    outside.write_text('{}')
    (app.cloud.inbox / 'shortcut.webqa-result.json').symlink_to(outside)
    atomic_json(app.cloud.inbox / 'unknown.webqa-result.json', {'request_id': 'f' * 32})
    assert all(f['status'] == 'invalid' for f in app.cloud.scan()['files'])
    with pytest.raises(ValueError):
        app.import_cloud('../outside.webqa-result.json')
    with pytest.raises(ValueError):
        app.import_cloud('shortcut.webqa-result.json')


def test_external_schema_references_are_never_fetched(app, site):
    request = app.cloud.export(site, 'develop', 'Create tests')
    request['jobs'][0]['schema'] = {'$ref': 'https://example.com/schema.json'}
    with pytest.raises(ValueError, match='local schema'):
        validate_request(request)
