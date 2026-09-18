# WebQA Kit

On-demand public website testing with Python, pytest, Playwright, and axe-core. Configure a target in JSON, run a small serial suite locally or from GitHub Actions, inspect the report, and retain reviewed failure history for better guidance next time.

**Version 0.4.0 is a GitHub-ready local app and CLI product.** It is not a hosted multi-tenant service. No GitHub repository or PyPI release has been published by this delivery. The distribution name is a project name, not a claim of registry availability.

## Start with the local app

For everyday use, follow [Start here](docs/START_HERE.md). A helper runs the setup launcher once. Afterward, open **Start-WebQA.bat** on Windows or **Start-WebQA.command** on macOS. The app opens in your browser with buttons to save a website, run checks, prepare/revise AI tests, review changes, and record findings. No code or JSON editing is required for those workflows.

Technical entry point: `webqa ui`. It listens only on localhost and stores data in `~/WebQA`. The CLI remains available for CI and developers.

## LLM test authoring

Use the app's **Prepare tests** flow, or `webqa develop`, `webqa revise`, and `webqa apply`. The model proposes a structured plan; the compiler emits actual pytest modules. Revisions produce a diff, changed-coverage summary, and assumptions. Applying and running remain explicit actions. Site-specific test history and review notes inform both advice and future authoring. See [the full authoring workflow](docs/LLM_AUTHORING.md).

## Developer quick start

Requires Python 3.11+ and a supported Playwright operating system. Python 3.12 is used by CI. Node.js is not required by end users: axe-core 4.10.3 is bundled with its license.

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
python -m playwright install chromium
# On a fresh Linux machine: python -m playwright install --with-deps chromium

webqa validate profiles/ctg.json
webqa run --config profiles/ctg.json --suite smoke
webqa run --config profiles/ctg.json --suite accessibility
webqa run --config profiles/ctg.json --suite full --headed
```

`run` is the explicit on-demand action. It opens a browser and sends normal page and asset requests. There are no scheduled production runs, parallel workers, automatic retries, form submissions, load tests, or penetration tests. Configure only public pages you are authorized to test.

To install from the provided wheel instead, run `python -m pip install dist/webqa_kit-0.4.0-py3-none-any.whl`, then install Chromium. To create a CTG profile outside this repository, run `webqa init --preset ctg --out ctg.json`.

## Target another website

```bash
webqa init --url https://example.com --id example --out profiles/example.json
webqa validate profiles/example.json
webqa run --config profiles/example.json
```

Replace the example URL with the intended public origin. A generated profile covers homepage accessibility at desktop and mobile widths. Edit it to add the site's expected title/headings, approved page paths, priorities, and meaningful visitor journeys. It cannot infer business requirements from a URL. The `smoke` selector needs P0 content checks or P0 functional journeys; a new baseline intentionally has neither.

Minimal content test:

```json
{
  "id": "home",
  "path": "/",
  "title_contains": "Your organization",
  "h1_contains": "Your expected heading",
  "language": "en",
  "checks": ["content", "structure", "axe", "reflow"],
  "viewports": ["desktop", "mobile"],
  "priority": "P0",
  "why": "Visitors must understand the service and reach the primary action."
}
```

A journey can click a role-based locator, assert the destination, and confirm its content. Every possible top-level destination must already be declared in `pages`.

```json
{
  "id": "home-to-contact",
  "start": "/",
  "viewport": "desktop",
  "priority": "P0",
  "why": "Primary inquiry route",
  "steps": [
    {"action": "click", "locator": {"role": "link", "name": "Contact"}},
    {"action": "expect-url", "value": "/contact"},
    {"action": "expect", "locator": {"role": "heading", "level": 1}, "assert": "text", "value": "Contact"}
  ]
}
```

See [the configuration reference](docs/CONFIGURATION.md), [the CTG profile](profiles/ctg.json), and [the JSON schema](src/webqa/schema.json).

## Reports and exit codes

Each run gets its own `reports/<site>/<timestamp>-<id>/` directory containing:

- `report.html`, `junit.xml`, and `results.json`: human and machine-readable results.
- `profile.json` and `run.json`: target, exact expectations, selected browser, version, and execution metadata.
- `overview.html`: readable report with inline screenshots and optional LLM explanations.
- `failure-report.json`: structured failure cards and explanation source.
- `checks/*/failure-*.json` and `.png`: assertion evidence, viewport capture, and up to three element captures.
- `browser/`: original Playwright failure screenshots and traces.
- `checks/<case>/axe*.json`: full axe results, including violations and incomplete checks.
- `checks/<case>/blocked-requests.json`: blocked request metadata, without payloads or query strings.
- `guidance.json` and `guidance-prompt.txt`: deterministic triage and optional LLM context.

The CLI preserves pytest's exit code: `0` means selected tests passed, `1` means failures, `2–4` indicate interruption/configuration/internal problems, and `5` means no tests were selected. `--collect-only` is explicitly labeled collection-only and does not add passing results to learning history. A successful collection is not a successful browser run.

```bash
python -m playwright show-trace reports/<site>/<run>/browser/<failure-folder>/trace.zip
```

Reports and traces can contain public page content and synthetic inputs. Inspect artifacts before sharing. The live test environment blocks writes, so it does not reproduce contact submission, analytics, or other POST-dependent behavior.

## Accessibility coverage

The product runs axe rules tagged WCAG 2 A/AA, 2.1 A/AA, and 2.2 AA, along with optional language/landmark checks, nested-control checks, missing/placeholder image alternatives, keyboard journeys, and narrow-screen reflow checks. The CTG profile scans the mobile menu after opening it.

A clean scan is not WCAG conformance. Cross-origin iframe contents are excluded (`iframes: false`), and incomplete checks remain for review. Add screen-reader testing, actual browser zoom, focus visibility/obscuration review, useful alternative-text assessment, reduced-motion checks, and inclusive usability sessions. The one-main/one-h1 check is an optional project convention, not a universal WCAG rule. [Playwright accessibility guidance](https://playwright.dev/docs/accessibility-testing), [W3C WCAG reference](https://www.w3.org/WAI/WCAG22/quickref/).

## LLM guidance and learning over time

Ordinary runs need no model or API key. Results enter a local SQLite database scoped by profile ID and origin. Re-ingesting a run is idempotent. Skips are not passes, and failure rates are displayed as observations, not proof of flaky tests.

```bash
webqa history profiles/ctg.json
webqa review reports/ctg/<run> --case chromium-journey--keyboard-menu \
  --decision accepted --resolution "Confirmed focus does not return after Escape; issue QA-123."
webqa advise reports/ctg/<run>
# Optional: with Ollama running locally and a model already installed:
webqa advise reports/ctg/<run> --model YOUR_INSTALLED_MODEL
```

The optional model receives case outcomes, site-scoped history, axe rule IDs/counts, and explicit human reviews. Raw DOM, form contents, stack traces, screenshots, and request payloads are excluded from its prompt. Review notes are deliberately included; do not put private information in them. Guidance uses the loopback Ollama API and validates the response schema and case IDs. The LLM has no tools and cannot suppress failures or submit forms. Its separate authoring workflow proposes managed test changes; the application applies them only when explicitly requested.

This is learning through persistent reviewed context, not training model weights. Guidance accuracy has not been established by a benchmark. A rejected diagnosis is retained as a negative example. Full inference with an actual model was not run in this environment; transport and response validation were unit-tested using a stub. [Ollama chat API](https://docs.ollama.com/api/chat).

## GitHub on-demand use

Create a repository from this folder and push it to its default branch. In **Actions → On demand website QA → Run workflow**, select a saved profile, suite, and browser. An optional target URL creates a generic homepage baseline. A maintained profile gives stronger coverage.

The workflow uses read-only repository permissions, installs the selected browser, uploads reports even when tests fail, and carries SQLite history forward using Actions cache. Runs are serialized to reduce contention. Cache is best-effort storage, not a durable database; use a proper database for a hosted product. An optional managed_test input runs a checked-in module under examples/. No workflow starts a model or sends data to an external LLM. [GitHub manual workflow documentation](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

If you use GitHub CLI, after creating a private repository and pushing this code:

```bash
gh workflow run on-demand.yml -f profile=ctg -f suite=smoke -f browser=chromium
```

Ordinary push/PR CI runs offline unit checks, validates collection, and builds wheel/source distributions. It does not test the public website on every commit.

## Development and verification

```bash
python -m pip install -e '.[dev]'
python -m pytest tests/unit
ruff check src tests
webqa run --config profiles/ctg.json --collect-only
python -m build
```

The CTG profile expands into **43 cases**, including **12 journeys**. See [scenario-by-scenario rationale](docs/SCENARIOS.md), [assumptions and gaps](docs/ASSUMPTIONS.md), [interview preparation](docs/INTERVIEW_GUIDE.md), and [execution evidence](evidence/README.md).

**Delivery validation:** 90 offline tests passed; all 43 CTG cases collected; live connected-browser probes recorded 8 successful observations/checks and 2 accessibility findings. The packaged Python browser suite, mobile checks, axe scans, cross-browser matrix, GitHub workflow, and actual LLM inference have not been executed end to end here. Run the commands above before presenting a full-suite result. Known structural findings remain strict failures; no blanket baseline or xfail hides them.

## Scope and next versions

Version 0.1 supports public-page read-only testing, explicit profiles, sequential execution, reports, local history, and advisory local inference. It deliberately omits authenticated flows, form submission, crawling, visual baselines, performance thresholds, automatic locator repair, scheduling, a web dashboard, and hosted multi-tenancy.

Next: execute and stabilize the browser suite in CI, validate browser coverage against audience data, introduce reviewed issue-level accessibility exceptions with expiry, add a fixture-backed package integration suite, evaluate guidance on labeled historical failures, and add durable storage. A hosted product also requires tenant authentication, target authorization, network isolation and DNS/redirect SSRF defenses, quotas, encrypted artifact storage, and retention controls. Current origin/path checks are useful CLI guardrails, not a hosted-service security boundary.

Source code is MIT licensed. Bundled axe-core retains its MPL-2.0 license; see `THIRD_PARTY_NOTICES.md`.

## Usability update (0.3.0)

After one-time setup, use the desktop launcher and the local app. Page addresses and expected headings have separate labeled fields. The app remembers your selected website and model, restores each website’s latest completed result, explains result categories in plain language, and enables actions when their prerequisites are ready. Built-in help covers normal use and common setup problems. No terminal commands or code editing are needed for ordinary use.

This release adds offline regression coverage for persisted results and website isolation. The local UI has not been visually validated in this environment; the setup helper should complete the acceptance checks in Start Here.

## AI reliability and illustrated reports (0.3.0)

The v0.2.x non-streaming 180-second request could expire during model loading or generation. This release streams Ollama responses, displays progress and elapsed time, removes duplicated schema/generated-source context, defaults to a 600-second absolute deadline, and supports up to 1200 seconds. It caps generated output at 4096 tokens, disables optional thinking, retains model warmth for ten minutes, and asks for 1–3 tests on new requests. Small prompts use an 8192-token context; larger prompts use 16384. Oversized prompts and incomplete answers fail explicitly; there is no automatic unbounded retry or automatic application of partial code.

The app can automatically explain failures with the selected local model. Reports are saved before inference and stay usable if the model fails. Each card includes what happened, why it matters, and what to do. The model receives bounded assertion messages, rule metadata, and test context; basic redaction is applied to common secrets and email addresses. Screenshots, full HTML, and raw stack traces are not sent. Screenshots are evidence for the reader, not visual model analysis. AI covers the first twelve failed checks per request; additional failures retain rule-based explanations. All original outcomes remain unchanged.

Screenshot capture runs before page teardown. It records a viewport image and attempts up to three close-ups from axe targets, known semantic/image selectors, or a journey’s current locator. Form inputs are masked in these report images. A browser launch failure, detached element, off-screen target, or closed page can prevent a capture; the report states when an image is unavailable. Original Playwright artifacts may have different masking behavior and should be reviewed before sharing.

```bash
webqa run --config profiles/ctg.json --model YOUR_INSTALLED_MODEL --ai-timeout 1200
webqa develop --config profiles/ctg.json --request "Create 1–3 accessibility checks" --model YOUR_INSTALLED_MODEL --ai-timeout 1200 --out proposals/new-request
```

The same deadline setting appears as **How long may AI work?** in the local app. Upgrade instructions are in `docs/START_HERE.md`. UI version 0.3.0 confirms that the new package is running.

Validation includes real loopback HTTP tests for streaming, pre-response stalls, mid-stream stalls, a continuously responding server exceeding the deadline, missing models, truncated output, and report fallbacks. A real pytest subprocess verifies capture timing with a controlled page fixture. These tests do not claim successful inference on your installed model or live screenshot capture in this environment. The control-browser skill restricts browser execution to the managed browser, whose localhost access was blocked; rendered UI and full browser acceptance remain to be run on the installation computer.

API references: [Ollama chat](https://docs.ollama.com/api/chat), [streaming](https://docs.ollama.com/capabilities/streaming).

## Colab file exchange (0.4.0)

Choose Google Colab in the dashboard to export create, revise, explain, or history-guidance requests. The self-contained `notebooks/WebQA_Cloud_LLM.ipynb` processes them on a Colab GPU and downloads data-only result files. Copy those into `Cloud-Inbox` in the app folder, scan, and import. Imported plans are compiled locally using the same validation as local AI and require review/apply before running. Request snapshots, source hashes, exact job matching, and persisted receipts prevent stale overwrites and duplicate proposals. Cloud explanations retain local screenshots and original outcomes.

The CLI’s `webqa ui --inbox /path/to/Cloud-Inbox` can override the drop folder. The default is `Cloud-Inbox` under the launch directory; supplied launchers first enter the app folder. Pending requests remain under the chosen workspace (normally `~/WebQA/cloud/requests`). Keep that workspace across upgrades. There is no public API tunnel, cloud browser execution, or automatic execution of downloaded Python.

See `docs/CLOUD_COLAB.md` for the user workflow and limitations. The notebook is bundled in the wheel and downloadable from the dashboard. Rebuild it after changing shared modules with `python scripts/build_colab_notebook.py`; the notebook regression test rejects stale embedded code.

Developer UI test: `npm ci --prefix tests/ui`, then `npm test --prefix tests/ui`. These DOM tests simulate API responses and do not substitute for rendered browser testing. Colab dependency lock/audit/preflight evidence is in `notebooks/` and `evidence/colab-*`. The actual GPU/model and Google widgets require an acceptance run on Colab; no such run is claimed here.
