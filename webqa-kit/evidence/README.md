# Execution evidence

The evidence types below are deliberately separate.

| Evidence | What was executed | Result | What it does not prove |
|---|---|---|---|
| unit-results.json and unit-results.xml | Python pytest checks of configuration, guardrails, history isolation, idempotency, reviews, CLI init, stubbed LLM guidance/authoring, managed pytest collection, revision integrity, and local app HTTP/workflow behavior | 75 passed | Browser behavior or real LLM inference |
| collection/ | Installed CLI invoking the packaged pytest suite with --collect-only | 43 CTG cases collected | No browser cases executed; zero live passes claimed |
| live-browser-checks.json | Ten desktop checks or observations through a connected Chrome browser | 8 successful, 2 findings | Not a run of the shipped Python suite or axe-core |
| wheel-collection/ | CLI loaded from an installed wheel outside the source folder | 43 cases collected; bundled assets present | Full browser execution |
| page-observations.json | DOM inspection of six representative public pages | Page identities and structural details recorded | Complete navigation, mobile behavior, or accessibility conformance |

The two recorded findings are three nested buttons inside homepage links and one image on the portfolio page with the placeholder alternative text `Alt text`. The packaged semantics and image-alt checks keep these conditions as strict failures. The observed issue does not establish the full impact on every browser or assistive technology.

The environment exposed a managed browser for direct inspection. Its available interface did not execute the packaged Python browser suite or permit the axe injection workflow used by that suite. Package execution was verified through offline tests, installed CLI collection, and distribution checks; live user flows were inspected separately. Mobile, axe, full Python browser execution, cross-browser runs, GitHub Actions, and actual local-model inference must still be exercised by the recipient.

Nothing in collection output should be presented as a green browser suite. Run the package locally before the interview and replace or supplement this evidence with its timestamped report. Future site changes can alter the observed results.

Version 0.2 adds collection-v02/ (43 baseline cases) and authored-collection/ (3 curated managed cases). These remain collection-only. The generated-test and local-app offline workflows use controlled model responses and do not establish real-model quality or live website behavior. The managed browser refused access to the local app, so visual and interactive UI acceptance checks remain unexecuted. Windows/macOS launchers are supplied but were not run on those platforms.

Version 0.3.0 adds actual loopback streaming/deadline tests and a real pytest hook lifecycle test using a controlled page fixture. Fixture PNGs are not website screenshots. No real model inference or live browser screenshot capture is claimed.
