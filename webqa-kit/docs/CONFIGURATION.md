# Configuration reference

Profiles use schema version 1. `webqa validate FILE` checks the complete profile before network access and lists all generated cases. `src/webqa/schema.json` is the machine-readable contract. Unsupported fields fail validation rather than being ignored.

## Target and bounds

`id` is a lowercase site identifier. `base_url` is an HTTPS origin without credentials, path, query, or fragment; loopback HTTP is allowed for fixture servers. Use the site's canonical origin because cross-origin top-level redirects are intentionally blocked. Only declared page paths may be top-level navigation destinations. Admin and login path segments, traversal, queries, and external navigation are rejected. This is not exhaustive detection of every possible authenticated route: keep profile review in the workflow.

At most 20 pages, 20 journeys, 3 viewports, 30 steps per journey, and 100 generated cases are allowed. Execution is serial with a 300 ms gap before each page navigation. Site scripts may make read-only subresource requests; this is not a hard total-request cap or a crawler. Do not use it for load testing.

## Page checks

| Check | Assertion | Important limit |
|---|---|---|
| content | HTTP 200, declared URL, configured title or H1 content | A status code alone cannot identify soft 404s; specify an expected title/H1 |
| structure | Configured language, one main landmark, one nonempty H1 | Optional structural convention, not a conformance certificate |
| axe | No violations from configured WCAG A/AA rule tags | Iframes excluded; incomplete checks saved for review |
| semantics | No common nested interactive-control patterns | Deliberately narrow DOM signal; not a full HTML validator |
| image-alt | No missing alt or known placeholders | Empty alt may be correct for decoration; human meaning still needs review |
| reflow | Document width fits viewport within one CSS pixel | Does not establish all 400% zoom or component-overlap behavior |

All selected checks run against each viewport listed on the page. Every case has an independent browser context. The ready-state anchor is its H1 expectation when available; otherwise the body must be visible. For asynchronous pages without an H1 anchor, add a journey with an explicit ready element before its axe step.

`priority` is P0/P1/P2. `why` records business rationale. `smoke` selects P0 functional cases; `accessibility` selects accessibility checks and journeys marked `accessibility: true`; `mobile` selects viewports narrower than 768 CSS px. `full` selects everything.

## Locators

Prefer `{"role":"link","name":"Contact"}` or `{"label":"Email Address"}`. Names are exact by default; `exact: false` supports controlled partial matching. `level` scopes heading roles. `scope` is an optional CSS ancestor such as `header`, `main`, `nav`, or `form`. `selector` is a CSS escape hatch for stable attributes, not generated framework class names. Multiple matches fail rather than silently choosing the first.

## Journey actions

| Action | Required fields | Effect |
|---|---|---|
| click | locator | Clicks a visible non-submit control |
| press | locator, value | Presses a permitted key on a visible control |
| fill | locator, value | Enters synthetic text and asserts the resulting value |
| expect | locator, assert | Asserts visible, hidden, focused, text, value, attribute, or count |
| expect-url | value | Waits for exact configured origin plus declared path |
| keyboard | value | Sends a permitted keyboard key to current focus |
| tab-to | locator | Tabs up to max_tabs (default 20, maximum 30) and asserts focus |
| axe | none | Scans current state and writes an artifact |
| links | locator, hosts | Checks HTTPS destinations, optional path_prefix, visible text, and min_count |

`text`, `value`, and `attribute` assertions require `value`; attribute assertions also require `attribute`. Count assertions require integer `count`. Permitted keys are Enter, Space, Escape, Tab, Shift+Tab, ArrowDown, ArrowUp, Home, and End.

The runner rejects submit-control activation and Enter inside forms. It prevents submit events and blocks non-read requests as additional safeguards. GET endpoints can still have site-specific side effects; declare only ordinary public content pages. Forms, CAPTCHAs, real personal data, and authentication are not supported workflows.

Changing a profile does not rewrite existing reports. Every run saves a snapshot and hash. History is scoped by ID and origin but currently aggregates across profile revisions; compare snapshots before interpreting a trend. Review notes refer to case IDs including the browser suffix found in results, for example `journey--keyboard-menu-chromium`.
