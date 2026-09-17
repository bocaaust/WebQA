# WebQA Kit interview preparation

Prepared for Austin Lubetkin

This guide supports a ten-minute presentation of the Capital Technology Group QA exercise and the reusable product built from it. WebQA Kit is an installable Python package with a local app for everyday users and a CLI for developers. It runs configured public-website checks locally or through an on-demand GitHub Actions workflow. CTG is the first site profile. Business expectations stay explicit, accessibility receives dedicated coverage, and LLM guidance remains advisory.

The package contains 43 CTG browser cases, including 12 visitor or keyboard journeys, plus an offline test suite for the product itself. During preparation, 53 offline tests passed and all 43 browser cases collected successfully. Ten connected-browser probes recorded eight successful checks or observations and two accessibility findings. The packaged Python browser suite and axe scans have not been executed end to end in this environment. Present those categories separately; do not describe collection as a live pass.

## The first ten minutes

### Minutes 0 to 1 State the problem and the scope

“My starting point was the visitor's goal. For this public site, I identified three important outcomes: understand what CTG can do, find evidence of delivered work, and reach the right next step through contact or careers. I used those outcomes to choose coverage, rather than starting with an exhaustive list of links.

“The implementation uses Python and pytest, with Playwright for browser interaction and axe-core for automated accessibility checks. Python fits my recent technical work. I chose Playwright for isolated browser contexts, semantic locators, automatic waiting, and useful failure traces. I would not present Playwright as a framework I had used previously unless that is true.

“I then separated the reusable runner from the site's expectations. CTG is a JSON profile. Another website can use the same package with its own pages, viewports, and journeys.”

Open the local app and show the website selector, Check website button, and AI request box. Keep the high-level explanation under one minute. README.md and the package entry point are useful if the interviewer asks about implementation.

### Minutes 1 to 3 Explain the scenario selection

“I treated homepage-to-work, capability-to-contact, and navigation-to-careers as high-value flows. Each test checks a user-visible outcome. A URL change alone is insufficient for a client-rendered site, so I also wait for the expected heading or field.

“The contact test fills only clearly synthetic values, including an example.invalid email address. It stops before submission. The careers test checks the destination of application links without opening an application. Those boundaries keep the exercise useful without creating messages or applicant records.

“I sampled distinct templates: the homepage, a capability page, a case-study listing and detail, careers, contact, about, and labs. Direct-entry checks also cover visitors arriving from search or a shared link. I avoided asserting exact job counts because content changes independently of the application.”

Open profiles/ctg.json. Show one P0 journey and its why field. Explain that P0 is an execution priority; a serious defect found by any test can still block a release.

### Minutes 3 to 5 Demonstrate a run and a failure

Use a run completed before the interview, or start a smoke run only after verifying your local setup:

```bash
webqa validate profiles/ctg.json
webqa run --config profiles/ctg.json --suite smoke --headed
```

“The report directory contains a human-readable report, JUnit and JSON results, the exact profile used, and traces or screenshots for failures. Tests run serially and have fresh browser contexts. There are no automatic retries to turn a transient failure into a misleading green result.

“One structural issue I observed on the homepage is three buttons nested inside links. The portfolio also contains an image with the alternative text ‘Alt text’. I retained strict checks for both. A QA suite is valuable when it reports actionable failures; making every test green is not the objective.”

If using only the supplied evidence, open evidence/live-browser-checks.json and explain that it was captured through a connected browser, separately from the Python suite. If a new run fails, identify whether the evidence indicates a product defect, a test assumption, or an environment problem before proposing a change.

### Minutes 5 to 7 Explain accessibility and limitations

“Automated accessibility coverage combines axe scans with explicit checks for page structure, keyboard menus, a careers accordion, form tab order, nested controls, image alternatives, and narrow-screen overflow. I also scan the mobile menu after opening it, because a scan of the default page cannot cover hidden interaction states.

“I would never interpret a clean axe result as full accessibility compliance. Screen-reader behavior, meaningful alternative text, focus visibility, actual zoom, text spacing, reduced motion, and usability still need manual evaluation. Cross-origin iframe contents are excluded from the scanner and are an explicit coverage gap.

“The contact page has reCAPTCHA. I did not submit it or try to bypass that boundary. To test success, validation errors, network failures, and duplicate submissions, I would request staging with a test CAPTCHA configuration and a message sink.”

Show the axe helper and one keyboard journey. Explain that one main landmark and one H1 are selected conventions, not a claim that every extra heading violates WCAG.

### Minutes 7 to 9 Explain the reusable product and learning

“The package has a validated site profile, a deterministic execution engine, reporting, and a separate guidance layer. A new URL can generate a baseline accessibility profile, but meaningful business coverage still needs explicit expected behavior.

“Every run can enter a local SQLite history scoped to the site ID and origin. Duplicate ingestion does not inflate the counts, and skipped checks do not count as passes. A reviewer can record an accepted or rejected diagnosis. Later guidance retrieves that history and those reviews.

“An optional local LLM explains outcomes and proposes test changes. For authoring, it also receives the site profile, user request, and existing managed tests. The model returns a structured plan that the package compiles into pytest functions. The app shows a diff and requires an explicit apply action. The runner verifies the generated source before importing it. Persistent outcomes and reviewed resolutions inform later proposals; model weights do not change.”

Show webqa history and tests/unit/test_learning.py. If no local model is installed, demonstrate deterministic guidance and the saved prompt instead of claiming inference occurred.

### Minutes 9 to 10 Surface the next decisions

“My next step is to run and stabilize the packaged suite in the intended environment, then agree with the team on the most valuable flows, accessibility target, supported browsers, and failure ownership. I would add safe submission flows in staging and evaluate the guidance layer against labeled past failures.

“For a hosted product, the next work is larger than adding a dashboard: tenant isolation, target authorization, network restrictions, durable storage, and retention controls become necessary. The delivered version has a local app and CLI, with GitHub Actions for on-demand execution. A hosted multi-tenant service remains a separate stage.

“The main trade-off was choosing a bounded set of meaningful tests and keeping the evidence honest. The implementation can grow without making an LLM the judge of whether the website works.”

Stop at ten minutes and invite questions about a specific test or design decision.

## Demo preparation

Before the interview, install the package and Chromium, run the smoke and accessibility suites, and open the generated HTML report. Keep a failure trace ready. Use an ordinary browser separately to verify a disputed finding. Rehearse the ten-minute walkthrough with the exact files you will open.

The live site can change or become unavailable during the interview. Retain a timestamped report and profile snapshot. Explain the recorded environment and distinguish known findings from new failures. Do not silently remove a failing test or change its assertion while presenting.

Useful commands:

```bash
python -m pip install -e '.[dev]'
python -m playwright install chromium
python -m pytest tests/unit
webqa run --config profiles/ctg.json --suite smoke
webqa run --config profiles/ctg.json --suite accessibility
webqa history profiles/ctg.json
python -m build
```

## Likely interview questions and prepared answers

These are practice questions and answer models, not a prediction of the interviewer's exact questions. Adjust the first-person wording to what you can personally demonstrate.

### 1 Why did you choose these scenarios

I started with customer discovery, credibility, contact, and recruiting. The selected flows connect a visible action to an observable result. I sampled distinct page templates and added accessibility checks to important interaction states. This gives useful coverage without a large, noisy crawl.

### 2 How did you prioritize the tests

P0 protects the main visitor paths and contact entry. P1 covers supporting behavior and accessibility signals. P2 covers lower-frequency informational pages. These are provisional scheduling priorities based on the visible site. I would refine them with analytics, incidents, and stakeholders. Defect severity is a separate decision.

### 3 Why Python and pytest

Python fits my recent research and analysis workflows. Pytest makes parametrization and fixtures readable, and it integrates with JUnit, HTML, and JSON reports. Playwright adds browser capabilities without requiring the rest of the product to be written in JavaScript. The bundled axe engine is the small JavaScript component.

### 4 Why Playwright instead of Selenium or Cypress

Playwright offers isolated contexts, semantic locators, automatic actionability checks, several browser engines, and traces. Those capabilities fit this exercise. Selenium might fit an existing grid, and Cypress might fit a team's established frontend tooling. I would consider team ownership and infrastructure before prescribing a replacement framework.

### 5 What makes these end to end tests

The journey cases interact with the rendered public website and assert the destination and visible content. They exercise the browser-facing integration. They do not cover downstream contact delivery or the external applicant system, so I describe those boundaries explicitly rather than claiming complete business-process coverage.

### 6 Why use a configuration file instead of hardcoded tests

Profiles let another site reuse the same runner while keeping its expectations reviewable. The schema catches invalid inputs before browser access. I kept the action vocabulary small to avoid building a general programming language. Complex future workflows should use a clear extension point rather than an ever-growing configuration language.

### 7 Can someone supply only a URL

Yes, init creates a baseline homepage profile at desktop and mobile widths, and the GitHub workflow accepts an optional URL. It can run generic accessibility checks. It cannot know whether a business flow is correct. Strong functional tests need expected content, declared destinations, and a site's actual visitor goals.

### 8 How do you choose selectors

I prefer roles, accessible names, and form labels because they describe the user-facing interface. I scope ambiguous navigation to header or nav. A stable href selector is a reasonable fallback for a card with a long accessible name. I avoid generated class names, positional selectors, and silent first-match behavior.

### 9 How do you handle asynchronous rendering

I use Playwright's locator assertions and wait for the expected heading or field after navigation. A client-side URL may update before the new content is ready. I do not use network idle as a universal readiness signal. The 300 ms delay is only request pacing, not a substitute for a readiness condition.

### 10 How do you prevent tests from influencing one another

Each case receives a fresh browser context with its own storage and page state. Reports are separated by site and run. Tests do not depend on execution order. Shared history is outside the pass/fail path and cannot change what a test asserts.

### 11 What are the production safety boundaries

The suite visits only declared public routes, runs serially, blocks non-read requests, prevents form submit events, and rejects direct submit-control activation. It does not enter real personal data or open application forms. These are practical guardrails, not a guarantee against every site-specific GET side effect.

### 12 Why not test the successful contact submission

There is no approved test sink or staging configuration. Even a fake message could create work for the real team. I cover reachability, labels, synthetic input, and keyboard order now. With staging, I would verify validation, success feedback, delivery, duplicate protection, and recoverable errors.

### 13 How would you test email validation

First I would confirm the intended validation contract. In staging I would test empty, malformed, and valid addresses; verify visible and programmatically associated errors; and check keyboard focus and announcements. A native input type alone is not proof of complete client and server validation.

### 14 Why not follow the Greenhouse links

The public website owns exposing a readable, correct application destination. Greenhouse owns the application experience. Following every external link expands dependency and side-effect risk. I would add a small separately owned external smoke check only after agreeing on its scope and failure policy.

### 15 What happens when there are no open jobs

The current profile requires at least one matching destination because roles were present during inspection. That is a documented assumption. I would ask for the intended empty-state content and then support either a nonempty list or that explicit state. I would not treat an empty or broken feed as an automatic pass.

### 16 What accessibility issues can the suite detect

It can detect rule-based issues through axe and selected structural issues through focused checks. It also verifies some keyboard interactions and a reflow proxy. The observations include nested buttons in links and placeholder alternative text. An automated signal still needs a reproducible issue report and an assessment of user impact.

### 17 Does a passing axe scan mean the site is accessible

No. It means no violations were detected by the configured rules in the scanned state. It does not prove meaningful text alternatives, sensible focus order, usable screen-reader announcements, accessible error recovery, or conformance across the whole site. Manual assessment and inclusive user testing remain necessary.

### 18 Why scan the opened mobile menu

Automated scanners inspect the current rendered state. A hidden menu can contain issues that a default page scan misses. Opening the control, waiting for its links, and then scanning gives coverage of the state visitors actually use. Other dynamic states should be treated similarly.

### 19 How would you test keyboard accessibility manually

I would navigate without a mouse, follow the main visitor journeys, inspect visible focus, check logical order and skip mechanisms, enter and exit menus, and verify focus after errors and navigation. I would also test with a screen reader. A focused-element assertion cannot establish the quality of the entire experience.

### 20 Why are some accessibility tests expected to fail

The site already has observable structural issues. Suppressing those failures would reduce the suite's value. I would document the finding and triage it with the team. If temporary acceptance is necessary, I would prefer a narrowly scoped issue reference, owner, and expiry over disabling a whole rule.

### 21 How do you distinguish a defect from a bad test

I inspect the trace and actual page state, reproduce the behavior manually, and compare it with the agreed requirement. Then I classify it as a product issue, test assumption, test implementation problem, or environment failure. I preserve the original evidence and change an assertion only when the contract warrants it.

### 22 What would you do about flaky tests

I would collect repeated outcomes under controlled conditions and identify the cause. Common causes include race conditions, external dependencies, unstable data, and overbroad locators. I would improve readiness and isolation before adding retries. A failure-rate trend is a useful signal, not proof that a test is flaky.

### 23 Why no automatic retries

Retries can hide instability and make a live demonstration look healthier than it is. This initial suite favors clear evidence. If retries are later justified for a specific transient environment risk, I would retain and report the first failure and measure retry frequency instead of treating eventual success as ordinary success.

### 24 What is captured when a test fails

Pytest records the assertion and status. The run stores the profile, browser choice, version, and timestamp. Playwright retains a screenshot and trace for a failed browser test, and axe writes its full results before asserting. Blocked navigation attempts also produce metadata so an out-of-scope step is diagnosable.

### 25 How does the learning system improve over time

It persists site-scoped outcomes and human-reviewed resolutions. Future guidance retrieves previous diagnoses and failures so the reviewer has useful context. Duplicate runs do not inflate statistics, and skips are excluded from pass/fail rates. This improves available evidence; it does not establish that the advice itself has become more accurate.

### 26 Is the system training an AI model

No. It uses retrieval from persistent history and reviews. Model weights do not change. That was a proportionate choice for a small QA product. If there were enough well-labeled examples to justify training, I would first establish a baseline, a held-out evaluation set, and measurable criteria for useful guidance.

### 27 Why keep the LLM outside test pass and fail

A regression gate needs repeatable, auditable decisions. A model can offer a useful hypothesis but may be inconsistent or wrong. The deterministic suite reports what happened; the model suggests what to investigate. A human approves fixes and any changes to expected behavior.

### 28 How do you reduce hallucinations and prompt injection

The prompt receives a small allowlist of outcomes, rule summaries, and explicit reviews rather than arbitrary page text. The model has no tools. Its output must match a schema and reference a case in the current run. Those controls reduce scope; they do not prove the diagnosis is correct, so review remains necessary.

### 29 What information reaches the model

Guidance requests contain case IDs, outcomes, historical rates, axe rule summaries, and human review notes. Authoring additionally receives the site profile, user request, existing managed plan, and generated pytest code. Raw DOM, screenshots, network payloads, and raw failure logs are excluded. Requests and review notes must stay free of private data; the profile can contain the approved synthetic values.

### 30 How would you measure the value of LLM advice

I would use a labeled set of past failures, compare the advice with a deterministic triage baseline, and measure correct diagnosis rate, harmful recommendations, reviewer acceptance, and time to resolution. I would assess performance on new failures rather than the same examples used to develop the prompt.

### 31 What happens if the LLM is unavailable

Tests still run, report, and update history. Deterministic guidance and a prompt file remain available. Model invocation is a separate optional command, so a provider outage cannot change a test result or block ordinary QA. The current integration uses an explicitly named locally installed model.

### 32 How does this run on GitHub

A workflow_dispatch workflow accepts a saved profile or a new target URL, suite, browser, and an optional checked-in managed test module. It installs dependencies, runs checks serially, and uploads reports even after failures. Ordinary pull-request CI runs offline checks and builds distributions. The delivered workflows need to be pushed and exercised in a real repository before I claim they are validated.

### 33 How would you scale to more sites

I would keep profiles version controlled, assign owners and per-site budgets, and use durable storage for results and reviews. I would parallelize across approved staging targets only after agreeing on traffic limits. Shared runner improvements should be tested against representative fixture sites before affecting every customer profile.

### 34 What changes for a hosted product

A hosted service needs authenticated tenants, verified authority to test targets, isolated workers, DNS and redirect controls, network egress restrictions, quotas, encrypted artifacts, and retention rules. The current CLI's origin validation is not a sufficient SSRF defense. Hosting is a separate product stage, not something a dashboard alone completes.

### 35 How would you manage browser coverage

I would choose the initial browser from audience data, add a smaller high-value matrix for other engines, and test real devices where emulation is inadequate. The CLI supports Chromium, Firefox, and WebKit. Support in configuration is not evidence that all three have been executed successfully.

### 36 Why not add visual regression or performance testing now

Both can be valuable, but they need agreed baselines and environments. Pixel differences from dynamic content and timing changes from shared networks can create noise. I would add targeted component or page baselines and explicit performance budgets after establishing repeatable fixtures and ownership.

### 37 How do you maintain the suite when content changes

Content expectations live in the profile with a rationale. Every run saves the exact version used. I would review changes alongside the site release, preserving user-goal assertions where possible. Stable identity checks are stronger than copying every sentence, but removing all content assertions would make soft errors invisible.

### 38 What did you deliberately leave out

Production submissions, applications, authentication, broad crawling, visual comparisons, performance thresholds, full screen-reader assessment, autonomous repairs, and hosted multi-tenancy. I documented why each is omitted and what environment or agreement would make it appropriate. The timebox favors meaningful coverage and honest evidence.

### 39 What has actually been verified in this delivery

Fifty-three offline tests passed, the package's CTG profile collected 43 cases, and ten live connected-browser probes recorded eight successful checks or observations and two findings. The packaged Python browser suite, mobile and axe checks, GitHub execution, real-model inference, and rendered local-app workflow remain unexecuted integrations here. The new authoring/app flows have offline tests, including actual generated pytest collection and HTTP route checks. I would show a fresh local report before claiming a full end-to-end run.

### 40 What would you do with another day

I would execute the suite in the intended environment, resolve real implementation problems, verify the observed findings with assistive technology, add a controlled local fixture site for integration tests, and confirm product requirements with the team. Then I would add staging submission scenarios and evaluate guidance on a small labeled incident set.

### 41 How did you use LLM assistance in building this

I used it to help structure the implementation and documentation. The standard for accepting code is whether I understand it and can verify its behavior. I would be transparent about what was generated, what was reviewed, and what was executed. The presence of assistance does not substitute for test evidence or my ability to explain the design.

### 42 How does your accessibility interest affect your approach

Accessibility is part of whether a user can complete the task. I would ground findings in observable behavior and user impact, and include disabled users in evaluation. Automated rules provide useful evidence, while usability and assistive-technology testing reveal barriers the rules may miss.

### 43 How would you report the nested-control issue

I would include the affected page and control, exact reproduction, observed markup, expected single interaction target, likely keyboard or assistive-technology impact, and evidence. I would suggest styling the link as a button if it navigates, or using a button alone if it performs an action. I would confirm severity through actual interaction testing.

### 44 How would you report the placeholder alternative text

On the Our Work page, the Application Modernization card image has alt equal to ‘Alt text’. I would ask whether the image adds information beyond the adjacent linked heading. If it does, provide an accurate alternative; if it is decorative or redundant, an empty alternative may be appropriate. Nonempty text alone is not the goal.

### 45 What does a valuable test suite look like to you

It checks important behavior, fails for understandable reasons, produces useful evidence, and is maintainable by the team. It has a clear owner and a known scope. More tests, more elaborate models, or an always-green report are not sufficient measures of value.

### 46 How does the LLM develop executable pytests

The model returns a structured plan with test IDs, priorities, rationale, assumptions, and supported checks or journey steps. A deterministic compiler writes real pytest functions and a JSON sidecar. I chose this boundary so generated tests inherit the existing fixtures and public-site protections. Free-form model Python is never executed.

### 47 How do on-demand revisions work

The model receives the existing managed plan and source, the current profile, the requested change, and reviewed evidence. It proposes a full replacement plan. The product shows a diff and highlights added, changed, and removed scenarios. Applying checks content hashes, refuses stale overwrites, and saves the previous files. Running is a separate action.

### 48 Can the assistant rewrite any existing pytest file

The first version supports WebQA-managed modules, including the shipped three-case contact example. It does not rewrite arbitrary Python projects. A developer can translate an existing test into the supported plan or add a reviewed extension. This boundary keeps the product understandable and makes the generated code reproducible.

### 49 What is validated before applying generated tests

The plan must match a schema, use declared pages and viewports, stay within case and step budgets, and end each interactive journey with an observable assertion or scan. Form fills use fixed synthetic data. Python syntax is compiled without execution. These checks do not prove the selector or business expectation is correct; review and a real browser run are still required.

### 50 How do you prevent AI changes from hiding regressions

The prompt forbids weakening assertions merely to get a pass, but a prompt alone is insufficient. The product makes removals and modifications visible, preserves the original files, and separates proposing, applying, and running. A reviewer must verify changed expectations against the intended behavior. There is no automatic suppression or self-healing loop.

### 51 What happens if a model is unavailable or returns invalid output

Ordinary checks remain available without a model. Authoring records the request and error but does not apply a candidate. Malformed, out-of-scope, or unsupported plans fail validation. The app explains the problem and leaves existing tests intact. Model inference needs an installed local model; it was not exercised with a real model in this delivery.

### 52 How can someone with limited technical knowledge use the product

A helper installs the package, browser, and optional local model once. The user then opens a launcher, saves a website, chooses a check type, and selects Check website. They describe new behavior in plain language, review the proposal, and select Use these tests followed by Run AI tests. Technical logs and code diffs are available without being required for ordinary navigation.

### 53 What does one-time setup need to verify

The helper should verify Python compatibility, browser installation, local app startup, one public-site run, and one model proposal if AI is enabled. Windows and macOS launchers are included; Linux has explicit setup commands. The model must fit the computer's resources. I would not claim the launchers were tested on operating systems unavailable in this environment.

### 54 What checks cover the local app

Offline checks exercise website configuration, HTTP routes, session-token requirements, serial job execution, result summaries, and the generation/apply/revision flow with controlled model responses. Browser access to the local app was blocked by the managed browser environment. Visual, keyboard, and full interactive acceptance checks therefore remain a required local validation step.

### 55 Why use a local model

It provides a single optional integration without requiring users to create paid API credentials, and keeps the configured prompt on their computer. That choice has trade-offs: model installation, memory needs, speed, and output quality depend on the machine and model. A cloud provider could be added behind the same interface after agreeing on data handling and evaluation criteria.

### 56 How can a nontechnical user improve future guidance

After investigating a result, the user selects a check in Teach the assistant what you confirmed and records a verified conclusion. Those accepted or rejected reviews are retrieved for later advice and authoring for the same website. This improves available context; it does not prove that future suggestions are more accurate. I would measure that with a labeled evaluation set.

### 57 What would make this a production-ready product for a team

I would first execute the full suite and local app acceptance checks, test the launchers on supported systems, and measure generated-test quality. Then I would add a fixture site, clearer failure classification, an in-app undo flow, reliable upgrades, shared review ownership, and durable team storage. Hosting would additionally require authentication, tenant isolation, target authorization, and controlled network access.

## Questions to ask the interviewers

Ask the most relevant three or four during the discussion, then keep the others for follow-up.

1. Which customer or candidate journey would you most want protected first, and what incidents have affected it?
2. What staging infrastructure exists for contact forms, CAPTCHA, external job feeds, and synthetic data?
3. How does the team define and verify its accessibility target, and who owns remediation?
4. How are test failures triaged, and what evidence makes a report immediately useful to the team?
5. Which browsers and assistive technologies matter most for your audience?
6. How do developers and QA collaborate on acceptance criteria and reliable test selectors?
7. Where do you see the greatest opportunity for useful LLM assistance, and where should human approval remain mandatory?
8. Would a reusable testing product primarily serve internal teams, individual clients, or a hosted multi-tenant offering?
9. How would success in this role be measured during the first ninety days?

## Execution facts and remaining work

Inspection occurred on September 16, 2026. The website is mutable. The supplied browser evidence is a dated observation, not a guarantee about its current state. No messages or applications were submitted, no authenticated areas were accessed, and no load or penetration tests were performed.

The full scenario catalog follows in the document appendix and is also available as docs/SCENARIOS.md in the code package. The assumptions, exclusions, and production questions are captured in docs/ASSUMPTIONS.md. Keep these close to the report during the interview so the reasoning remains as reviewable as the code.

## Reference sources

Capital Technology Group public website: https://www.capitaltg.com/

Playwright Python pytest reference: https://playwright.dev/python/docs/test-runners

Playwright accessibility testing guidance: https://playwright.dev/docs/accessibility-testing

W3C WCAG quick reference: https://www.w3.org/WAI/WCAG22/quickref/

Deque axe-core source and documentation: https://github.com/dequelabs/axe-core

Ollama chat API: https://docs.ollama.com/api/chat

GitHub manual workflow execution: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow

Python packaging guidance: https://packaging.python.org/en/latest/tutorials/packaging-projects/
