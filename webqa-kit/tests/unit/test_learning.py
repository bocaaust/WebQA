import json
from contextlib import contextmanager

import pytest

from webqa.learning import advise, evidence_packet, history, ingest, review


def write_run(root, run_id, site, outcomes):
    root.mkdir(parents=True)
    (root / "run.json").write_text(json.dumps({"run_id": run_id, "site_key": site,
                                              "created": "2026-09-16T20:00:00Z", "suite": "full"}))
    (root / "results.json").write_text(json.dumps({"tests": [
        {"nodeid": f"test_site.py::test_site_case[{case}]", "outcome": result,
         "call": {"longrepr": "Secret contact email should not be in guidance"}}
        for case, result in outcomes.items()]}))
    return root


def test_history_deduplicates_and_does_not_count_skips_as_passes(tmp_path):
    db = tmp_path / "history.sqlite3"
    one = write_run(tmp_path / "one", "r1", "site-a", {"home": "failed", "menu": "skipped"})
    two = write_run(tmp_path / "two", "r2", "site-a", {"home": "passed", "menu": "passed"})
    other = write_run(tmp_path / "other", "r3", "site-b", {"home": "passed"})
    for run in [one, one, two, other]:
        ingest(db, run)
    values = {r["case_id"]: r for r in history(db, "site-a")}
    assert values["home"]["executions"] == 2
    assert values["home"]["failure_rate"] == 0.5
    assert values["menu"]["executions"] == 1 and values["menu"]["skips"] == 1


def test_review_is_retrieved_for_same_site_only_and_raw_logs_excluded(tmp_path):
    db = tmp_path / "history.sqlite3"
    run = write_run(tmp_path / "run", "r1", "site-a", {"home": "failed"})
    ingest(db, run)
    review(db, "site-a", "home", "accepted", "Confirmed placeholder alternative text")
    packet = evidence_packet(db, run)
    assert packet["human_reviews"][0]["resolution"] == "Confirmed placeholder alternative text"
    assert "Secret contact" not in json.dumps(packet)
    with pytest.raises(ValueError, match="recorded"):
        review(db, "site-b", "home", "accepted", "Wrong site")
    advice = advise(db, run)
    assert advice["source"] == "deterministic"
    assert (run / "guidance-prompt.txt").is_file()


def test_optional_model_transport_and_unknown_case_rejection(tmp_path, monkeypatch):
    db = tmp_path / "history.sqlite3"
    run = write_run(tmp_path / "run", "r1", "site-a", {"home": "failed"})
    ingest(db, run)
    import io
    import webqa.llm as llm
    reply = {"summary": "Review evidence", "suggestions": [{"case_id": "home", "hypothesis": "Possible regression",
              "next_check": "Inspect the trace", "confidence": "low"}]}

    @contextmanager
    def fake_urlopen(request, timeout):
        assert request.full_url == "http://127.0.0.1:11434/api/chat"
        payload = json.loads(request.data)
        assert payload["stream"] is False and payload["model"] == "installed-model"
        yield io.StringIO(json.dumps({"message": {"content": json.dumps(reply)}}))

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    assert advise(db, run, "installed-model")["advisory_only"] is True
    reply["suggestions"][0]["case_id"] = "invented"
    with pytest.raises(ValueError, match="outside"):
        advise(db, run, "installed-model")


def test_axe_findings_match_actual_pytest_parameter_order(tmp_path):
    db = tmp_path / 'history.db'
    run = write_run(tmp_path / 'run', 'r1', 'site-a', {'chromium-page--home--desktop--axe': 'failed'})
    checks = run / 'checks' / 'page--home--desktop--axe'
    checks.mkdir(parents=True)
    (checks / 'axe.json').write_text(json.dumps({'violations': [
        {'id': 'button-name', 'impact': 'critical', 'nodes': [{'target': ['button']}]}]}))
    ingest(db, run)
    assert evidence_packet(db, run)['accessibility_rules'][0]['case_id'] == 'chromium-page--home--desktop--axe'
