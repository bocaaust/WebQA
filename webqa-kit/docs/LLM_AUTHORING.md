# LLM test development and revisions

The same local Ollama integration powers result guidance and on-demand pytest authoring. Use the local app for the normal workflow, or these CLI commands for development and GitHub review.

## Generate, review, apply, run

```bash
webqa develop --config profiles/ctg.json --model YOUR_INSTALLED_MODEL \
  --request "Check the contact page heading and mobile accessibility. Use the existing page facts." \
  --out proposals/contact

# Review proposals/contact/changes.diff and validation.json first.
webqa apply proposals/contact --config profiles/ctg.json --dest examples/test_my_contact.py
webqa run --config profiles/ctg.json --tests examples/test_my_contact.py --collect-only
webqa run --config profiles/ctg.json --tests examples/test_my_contact.py
```

Every generated module has a matching `.plan.json` sidecar. Keep both files under version control. The runner snapshots both files into the report directory and uses its existing browser fixtures, request guards, evidence, and learning pipeline. `--tests` selects managed modules instead of the baseline profile suite; repeat the flag for multiple modules. The usual suite/browser selectors still work.

## Revise existing pytests

```bash
webqa revise --config profiles/ctg.json --test examples/test_my_contact.py \
  --model YOUR_INSTALLED_MODEL \
  --request "Retain the existing checks and add a keyboard journey through the contact fields." \
  --out proposals/contact-v2

webqa apply proposals/contact-v2 --config profiles/ctg.json --dest examples/test_my_contact.py
webqa run --config profiles/ctg.json --tests examples/test_my_contact.py
```

A curated existing example, `examples/test_ctg_contact.py`, contains three cases you can inspect, collect, run, or revise immediately. It was compiled from inspected site facts; it is explicitly labeled as a curated example, not an actual model response.

Pass `--run reports/ctg/<run>` to either authoring command to include sanitized failure evidence. Site-scoped history and reviewed resolutions are retrieved automatically from `--db`, which defaults to `.webqa/history.sqlite3`. The local app uses its persistent workspace database instead.

## What the model produces

The model returns a schema-constrained plan containing a summary, assumptions, and up to ten tests. A test can reference a configured page and standard check, or describe a journey using the package's supported interactions and assertions. The model sees the current site profile, user request, existing managed code when revising, prior outcomes, and explicit reviews. It has no browser or filesystem tools and does not independently crawl the site.

The compiler emits real pytest functions with explicit case parameters. It does not execute free-form Python from the model. JSON schema validation, declared-page and viewport checks, bounded case/step counts, synthetic-data substitution, and syntax compilation happen before a candidate is written. An interactive journey must end with an observable assertion or scan. These checks establish structural validity; they cannot establish that a selector, business expectation, or proposed diagnosis is correct.

For form fills, the model chooses a `test_data` key such as `email`; the compiler supplies a fixed synthetic value like `webqa@example.invalid`. Runtime protections continue to reject submit actions and block non-read requests.

The compiler uses ordinary [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html). Local model requests use Ollama's [chat API](https://docs.ollama.com/api/chat) with a JSON schema in `format`, followed by independent response validation as described in [structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

## Proposal artifacts and integrity

Each new proposal directory contains:

- `prompt.json`: exact request and input context.
- `test_candidate.py` and `test_candidate.plan.json`: proposed code and reproducible plan/profile snapshot.
- `profile.json`: the intended target profile.
- `changes.diff`: readable changes against the existing module, or additions for a new one.
- `validation.json`: schema/syntax status, added/modified/removed cases, and assumptions. It explicitly says no browser execution occurred.
- `proposal.json`: content hashes and original-file hashes used to prevent stale overwrites.
- `error.txt` if generation failed; no candidate is applied on failure.

Applying is a separate deliberate command or button. It verifies candidate integrity and original-file hashes, saves backups of replaced files, and records `applied.json`. Before a managed module is executed, the runner regenerates its expected source from the plan and requires an exact match. This is a constrained authoring format, not a general Python sandbox or a cryptographic signature scheme. Local users still control their own files.

## Boundaries and future work

Revisions support WebQA-managed modules, including the shipped example. Handwritten arbitrary pytest suites are not automatically imported or rewritten. Translate those tests into plans, or add a separately reviewed developer extension. The 43 baseline CTG cases still derive from their profile and can be maintained there.

Do not remove assertions just to get a passing run. The proposal highlights removed and changed cases, but a person must review whether a revision weakens coverage. Source hashes detect stale edits; they do not prove semantic correctness.

The integration is implemented and exercised with deterministic stub responses and real pytest collection. Actual model inference, generated browser execution, and the hosted GitHub workflows were not run in this environment. The local app's HTTP routes are tested; the managed browser refused localhost access, so its rendered end-to-end UI workflow remains an installation acceptance check.

Next improvements would include a controlled browser fixture site, a labeled authoring evaluation set, measured selector accuracy, better novice explanations, undo inside the app, and persistent team review workflows. A hosted version also needs authentication, tenant isolation, target verification, network controls, and durable storage.


## Version 0.3.0 transport update

Model requests stream progress, default to ten minutes, and can be set to twenty minutes in the app or with `--ai-timeout 1200` on develop/revise/run. Duplicate generated Python and output schema copies have been removed from the authoring packet; the complete current managed plan remains the revision source of truth. New requests should contain 1–3 focused scenarios. Failed or truncated responses never create an applicable partial proposal. Reports can explain failures using sanitized assertion excerpts and rule metadata, alongside locally stored screenshots; the text model does not interpret image pixels. See the README for evidence limits and acceptance checks.
