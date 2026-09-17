import copy
import json
from importlib.resources import files

import pytest

from webqa.cli import main, new_profile
from webqa.config import expand_cases, origin, validate_profile
from webqa.policy import allow_request


@pytest.fixture
def profile():
    return json.loads(files("webqa").joinpath("profiles/ctg.json").read_text())


def test_ctg_profile_has_unique_focused_cases(profile):
    validated = validate_profile(profile)
    cases = expand_cases(validated)
    assert len(cases) == 43
    assert len({c["id"] for c in cases}) == len(cases)
    assert any(c["check"] == "axe" for c in cases if c["kind"] == "page")


@pytest.mark.parametrize("url", ["https://example.com", "http://localhost:8000", "https://example.com/"])
def test_allowed_origins(url):
    assert origin(url) == url.rstrip("/")


@pytest.mark.parametrize("url", ["http://example.com", "https://user:secret@example.com", "file:///etc/passwd",
                                 "https://example.com/admin", "https://example.com?q=secret", "https://10.0.0.1"])
def test_reject_out_of_scope_origins(url):
    with pytest.raises(ValueError):
        origin(url)


@pytest.mark.parametrize("path", ["//external.example", "/admin", "/%61dmin", "/a/../logout", "/?email=qa", "/%5csecret"])
def test_reject_unsafe_or_unscoped_page_paths(profile, path):
    profile["pages"][0]["path"] = path
    with pytest.raises(ValueError):
        validate_profile(profile)


def test_reject_unknown_viewport_and_missing_assertion_value(profile):
    wrong = copy.deepcopy(profile)
    wrong["pages"][0]["viewports"] = ["unknown"]
    with pytest.raises(ValueError, match="viewport"):
        validate_profile(wrong)
    profile["journeys"][0]["steps"] = [{"action": "expect", "locator": {"role": "link"}, "assert": "attribute"}]
    with pytest.raises(ValueError, match="value"):
        validate_profile(profile)


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_writes_blocked_even_for_same_origin(profile, method):
    assert not allow_request(method, "https://www.capitaltg.com/contact-us", False, profile)


def test_navigation_boundaries_and_read_assets(profile):
    assert allow_request("GET", "https://www.capitaltg.com/careers", True, profile)
    assert allow_request("GET", "https://fonts.example/font.woff2", False, profile)
    assert not allow_request("GET", "https://boards.greenhouse.io/capitaltg/jobs/1", True, profile)
    assert not allow_request("GET", "https://www.capitaltg.com/contact-us?message=qa", True, profile)
    assert not allow_request("GET", "https://www.capitaltg.com/admin", True, profile)


def test_new_site_requires_no_ctg_specific_code():
    data = validate_profile(new_profile("second-site", "https://example.com"))
    assert len(expand_cases(data)) == 10
    assert "capitaltg" not in json.dumps(data)


def test_cli_init_preserves_existing_config(tmp_path):
    target = tmp_path / "site.json"
    assert main(["init", "--url", "https://example.com", "--out", str(target)]) == 0
    previous = target.read_bytes()
    assert main(["init", "--preset", "ctg", "--out", str(target)]) == 2
    assert target.read_bytes() == previous
