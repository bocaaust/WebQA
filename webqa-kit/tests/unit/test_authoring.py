import copy
import json
import subprocess
import sys

import pytest
from jsonschema import ValidationError

from webqa import authoring
from webqa.cli import main, new_profile
from webqa.learning import ingest, review, site_key


@pytest.fixture
def setup(tmp_path):
    config = new_profile('example', 'https://example.com')
    config['pages'][0].update(h1_contains='Example', title_contains='Example')
    path = tmp_path / 'profile.json'
    path.write_text(json.dumps(config))
    plan = {'summary': 'Verify the homepage and its accessibility', 'assumptions': ['Heading confirmed by owner'],
            'tests': [{'id': 'home-heading', 'kind': 'page', 'page': 'home', 'check': 'content',
                       'viewport': 'desktop', 'priority': 'P0', 'why': 'Verify visitor entry'},
                      {'id': 'home-accessibility', 'kind': 'page', 'page': 'home', 'check': 'axe',
                       'viewport': 'mobile', 'priority': 'P1', 'why': 'Detect rule violations'}]}
    return path, config, plan


def fake_model(monkeypatch, plan):
    monkeypatch.setattr(authoring, 'chat', lambda *args, **kwargs: copy.deepcopy(plan))


def make_proposal(setup, tmp_path, monkeypatch):
    path, config, plan = setup
    fake_model(monkeypatch, plan)
    proposal = tmp_path / 'proposal'
    result = authoring.propose(path, 'Check homepage entry and accessibility', 'test-model', proposal,
                               tmp_path / 'history.db')
    return proposal, result


def test_develop_apply_and_collect_real_generated_pytest(setup, tmp_path, monkeypatch):
    path, _, _ = setup
    proposal, result = make_proposal(setup, tmp_path, monkeypatch)
    assert result['test_count'] == 2 and result['live_browser_run'] is False
    target = tmp_path / 'test_example.py'
    assert not target.exists()
    assert '+def test_home_heading' in (proposal / 'changes.diff').read_text()
    authoring.apply_proposal(proposal, path, target)
    assert main(['run', '--config', str(path), '--tests', str(target), '--collect-only',
                 '--out', str(tmp_path / 'reports')]) == 0
    records = list((tmp_path / 'reports').glob('*/*/results.json'))
    report = json.loads(records[0].read_text())
    assert report['summary']['collected'] == 2


def test_revision_preserves_original_until_apply_and_refuses_stale_overwrite(setup, tmp_path, monkeypatch):
    path, _, plan = setup
    proposal, _ = make_proposal(setup, tmp_path, monkeypatch)
    target = tmp_path / 'test_example.py'
    authoring.apply_proposal(proposal, path, target)
    before = target.read_bytes()
    plan['tests'][1]['viewport'] = 'desktop'
    fake_model(monkeypatch, plan)
    revision = tmp_path / 'revision'
    authoring.propose(path, 'Use desktop for the scan', 'test-model', revision, tmp_path / 'history.db', target)
    assert target.read_bytes() == before
    assert json.loads((revision / 'validation.json').read_text())['changes']['modified'] == ['home-accessibility']
    target.write_text(target.read_text() + '# concurrent edit\n')
    with pytest.raises(ValueError, match='stale'):
        authoring.apply_proposal(revision, path, target)
    target.write_bytes(before)
    authoring.apply_proposal(revision, path, target)
    assert (revision / 'previous.py').read_bytes() == before
    assert target.read_bytes() != before


def test_arbitrary_python_and_tampered_proposals_are_rejected(setup, tmp_path, monkeypatch):
    path, config, _ = setup
    proposal, _ = make_proposal(setup, tmp_path, monkeypatch)
    candidate = proposal / 'test_candidate.py'
    candidate.write_text(candidate.read_text() + '\nimport os\nos.system("echo unwanted")\n')
    with pytest.raises(ValueError, match='arbitrary Python'):
        authoring.load_managed(candidate, config)
    with pytest.raises(ValueError):
        authoring.apply_proposal(proposal, path, tmp_path / 'test_target.py')


def test_model_failure_leaves_only_error_evidence(setup, tmp_path, monkeypatch):
    path, _, _ = setup
    def unavailable(*_):
        raise OSError('Ollama unavailable')
    monkeypatch.setattr(authoring, 'chat', unavailable)
    with pytest.raises(OSError):
        authoring.propose(path, 'Create tests', 'missing', tmp_path / 'draft', tmp_path / 'history.db')
    assert (tmp_path / 'draft' / 'error.txt').is_file()
    assert not (tmp_path / 'draft' / 'test_candidate.py').exists()


@pytest.mark.parametrize('mutation', ['extra-code', 'unknown-page', 'unknown-viewport', 'duplicate-id', 'empty'])
def test_reject_invalid_model_plans(setup, mutation):
    _, config, plan = setup
    if mutation == 'extra-code':
        plan['python'] = 'import os'
    elif mutation == 'unknown-page':
        plan['tests'][0]['page'] = 'invented'
    elif mutation == 'unknown-viewport':
        plan['tests'][0]['viewport'] = 'invented'
    elif mutation == 'duplicate-id':
        plan['tests'][1]['id'] = plan['tests'][0]['id']
    else:
        plan['tests'] = []
    with pytest.raises((ValueError, ValidationError)):
        authoring.compile_module(plan, config)


def journey_plan(steps):
    return {'summary': 'Check a form safely', 'assumptions': [], 'tests': [
        {'id': 'contact', 'kind': 'journey', 'start': '/', 'viewport': 'desktop',
         'priority': 'P0', 'why': 'Verify synthetic input', 'steps': steps}]}


def test_synthetic_data_is_compiled_and_raw_form_values_rejected(setup):
    _, config, _ = setup
    steps = [{'action': 'fill', 'locator': {'label': 'Email'}, 'test_data': 'email'},
             {'action': 'expect', 'locator': {'label': 'Email'}, 'assert': 'visible'}]
    source = authoring.compile_module(journey_plan(steps), config)
    assert 'webqa@example.invalid' in source
    steps[0] = {'action': 'fill', 'locator': {'label': 'Email'}, 'value': 'someone@real.example'}
    with pytest.raises(ValueError, match='synthetic'):
        authoring.compile_module(journey_plan(steps), config)


def test_no_assertion_or_out_of_scope_destination_rejected(setup):
    _, config, _ = setup
    with pytest.raises(ValueError, match='assertion'):
        authoring.compile_module(journey_plan([{'action': 'click', 'locator': {'role': 'link'}}]), config)
    with pytest.raises(ValueError, match='declared'):
        authoring.compile_module(journey_plan([
            {'action': 'expect-url', 'value': '/admin'},
            {'action': 'expect', 'locator': {'role': 'heading'}, 'assert': 'visible'}]), config)


def test_history_and_reviews_enter_authoring_but_other_site_evidence_rejected(setup, tmp_path, monkeypatch):
    path, config, plan = setup
    db = tmp_path / 'history.db'
    run = tmp_path / 'run'
    run.mkdir()
    meta = {'run_id': 'one', 'site_key': site_key(config), 'created': '2026-09-16', 'suite': 'full'}
    (run / 'run.json').write_text(json.dumps(meta))
    (run / 'results.json').write_text(json.dumps({'tests': [
        {'nodeid': 'test.py::test[home]', 'outcome': 'failed', 'call': {'longrepr': 'PRIVATE RAW LOG'}}]}))
    ingest(db, run)
    review(db, site_key(config), 'home', 'accepted', 'Confirmed heading changed with approval')
    def model(_model, _system, packet, _schema):
        assert packet['human_reviews'][0]['resolution'].startswith('Confirmed')
        assert packet['history'][0]['failures'] == 1
        assert 'PRIVATE RAW LOG' not in json.dumps(packet)
        return plan
    monkeypatch.setattr(authoring, 'chat', model)
    authoring.propose(path, 'Check heading', 'test-model', tmp_path / 'draft', db, run_dir=run)
    meta['site_key'] = 'other'
    (run / 'run.json').write_text(json.dumps(meta))
    with pytest.raises(ValueError, match='another site'):
        authoring.propose(path, 'Check heading', 'test-model', tmp_path / 'other', db, run_dir=run)


def test_profile_edits_require_revision_but_revision_is_possible(setup, tmp_path, monkeypatch):
    path, config, plan = setup
    proposal, _ = make_proposal(setup, tmp_path, monkeypatch)
    target = tmp_path / 'test_example.py'
    authoring.apply_proposal(proposal, path, target)
    config['pages'][0]['h1_contains'] = 'Updated heading'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='profile changed'):
        authoring.load_managed(target, config)
    fake_model(monkeypatch, plan)
    authoring.propose(path, 'Update expected heading', 'test-model', tmp_path / 'revision', tmp_path / 'db', target)
    authoring.apply_proposal(tmp_path / 'revision', path, target)
    assert 'Updated heading' in target.read_text()


def test_package_cli_exposes_simple_app_and_authoring_commands():
    completed = subprocess.run([sys.executable, '-m', 'webqa', '--help'], capture_output=True, text=True)
    assert completed.returncode == 0
    for command in ['ui', 'develop', 'revise', 'apply']:
        assert command in completed.stdout
