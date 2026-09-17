import json
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from webqa.config import expand_cases, load_profile
from webqa.policy import allow_request


def pytest_addoption(parser):
    parser.addoption("--run-config", required=True)
    parser.addoption("--run-directory", required=True)


def pytest_generate_tests(metafunc):
    if "case" not in metafunc.fixturenames:
        return
    for marker in metafunc.definition.iter_markers("parametrize"):
        if "case" in [n.strip() for n in marker.args[0].split(",")]:
            return  # Managed modules carry their own explicit case parameters.
    profile = load_profile(metafunc.config.getoption("run_config"))
    widths = {v["id"]: v["width"] for v in profile["viewports"]}
    cases = []
    for case in expand_cases(profile):
        a11y = case.get("check") in {"axe", "structure", "semantics", "image-alt", "reflow"} or case["spec"].get("accessibility")
        marks = [pytest.mark.accessibility if a11y else pytest.mark.functional]
        if case["priority"] == "P0" and not a11y:
            marks.append(pytest.mark.smoke)
        if widths[case["viewport"]] < 768:
            marks.append(pytest.mark.mobile)
        cases.append(pytest.param(case, id=case["id"], marks=marks))
    metafunc.parametrize("case", cases)


@pytest.fixture(scope="session")
def site_config(pytestconfig):
    return load_profile(pytestconfig.getoption("run_config"))


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, site_config):
    return {**browser_context_args, "base_url": site_config["base_url"],
            "locale": "en-US", "service_workers": "block"}


@pytest.fixture
def case_output(case, pytestconfig):
    out = Path(pytestconfig.getoption("run_directory")) / "checks" / case["id"]
    out.mkdir(parents=True, exist_ok=True)
    return out


@pytest.fixture(autouse=True)
def bounded_browser(context, case, site_config, case_output):
    rejected = []
    context.add_init_script("""document.addEventListener('submit', event => {
        event.preventDefault(); event.stopImmediatePropagation();
    }, true);""")

    def guard(route):
        req = route.request
        top = req.is_navigation_request() and req.frame.parent_frame is None
        if allow_request(req.method, req.url, top, site_config):
            route.continue_()
        else:
            p = urlsplit(req.url)
            rejected.append({"method": req.method, "host": p.hostname,
                             "path": p.path, "top_navigation": top})
            route.abort("blockedbyclient")

    context.route("**/*", guard)
    yield
    (case_output / "blocked-requests.json").write_text(json.dumps(rejected, indent=2), encoding="utf-8")
    assert not any(r["top_navigation"] for r in rejected), "Out-of-scope navigation attempted; see blocked-requests.json"


@pytest.fixture
def loaded_page(page, case, site_config):
    viewport = next(v for v in site_config["viewports"] if v["id"] == case["viewport"])
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
    page.set_default_timeout(10_000)
    page.set_default_navigation_timeout(30_000)
    expect.set_options(timeout=10_000)
    path = case["spec"]["path"] if case["kind"] == "page" else case["spec"]["start"]
    time.sleep(0.3)  # Request pacing only. Readiness uses locators and assertions.
    response = page.goto(site_config["base_url"] + path, wait_until="domcontentloaded")
    assert response is not None and response.status == 200, "Expected a successful document response"
    expect(page).to_have_url(site_config["base_url"] + path)
    anchor = next(p for p in site_config["pages"] if p["path"] == path)
    if anchor.get("h1_contains"):
        expect(page.get_by_role("heading", level=1)).to_contain_text(anchor["h1_contains"])
    else:
        expect(page.locator("body")).to_be_visible()
    return page


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if not report.failed:
        return
    from webqa.reporting import capture_failure
    case = item.funcargs.get("case")
    output = item.funcargs.get("case_output")
    if case is None or output is None:
        return
    try:
        capture_failure(item.funcargs.get("page"), case, output, item.nodeid, report.when,
                        str(call.excinfo.value) if call.excinfo else report.longreprtext)
    except Exception as exc:
        # Evidence capture must never change a real test outcome.
        (output / "capture-error.txt").write_text(str(exc)[:1000], encoding="utf-8")
