# Assumptions and open questions

## CTG assumptions

The homepage supports customer discovery; contact is a primary conversion flow; careers supports recruiting; public case studies build trust. These priorities are inferred from visible navigation, not analytics or a stakeholder interview. English is the observed language. Current headings and canonical routes are provisional content contracts.

Careers had open Greenhouse roles on inspection. The destination check intentionally fails if all roles disappear; the correct empty state is unknown. Confirm whether an empty list is valid before changing this expectation. We do not assert a fixed role count or specific job names.

The contact page exposes Name, Organization, Email Address, Phone Number, and Message. Labels were present. Required fields, email validation, message delivery, consent, CAPTCHA behavior, success feedback, and error behavior have not been established. No submit occurred. The form's native input markup does not itself prove whether client or server validation works.

The production site can change independently of the code. A failed title or route assertion may be an approved update. Page checks use explicit expectations so such changes become reviewable. No product defect should be declared solely from a cloud-browser timeout or an inaccessible external dependency.

## Questions before production use

1. Which visitor journeys have the highest value or traffic, and who owns their acceptance criteria?
2. Is there an approved staging site, contact email sink, CAPTCHA test configuration, and synthetic applicant workflow?
3. What should users see when Greenhouse is unavailable or no roles are open?
4. Which browsers, mobile devices, languages, and assistive technologies represent the actual audience?
5. Which accessibility target has the team committed to, and who owns manual validation and remediation?
6. Are there existing accessibility findings, owners, target dates, and a process for expiring exceptions?
7. How do consent banners, geography, analytics, or content experiments alter rendered pages?
8. Which contact fields are required, how are errors announced, and how is successful delivery confirmed?
9. Which routes and copy are intended to be stable, and can the team expose stable test attributes where semantics are ambiguous?
10. What are acceptable run frequency, browser concurrency, and external-dependency boundaries?
11. Who triages failures, what blocks a release, and how quickly must P0 failures be investigated?
12. Where may screenshots, traces, and reviewed incident notes be stored, and for how long?
13. May an external model receive sanitized test evidence, or must all guidance remain local?
14. Which past failures could form a labeled evaluation set for measuring advice quality?
15. Would this tool remain an internal CLI, or become a hosted service requiring target verification and tenant isolation?

## Deliberate gaps and trade-offs

No submissions or applications: production side effects outweigh the value within this exercise. Add them only in an approved test environment with a verifiable sink.

No authenticated/admin access, penetration tests, load tests, or CAPTCHA bypass. They are outside the assignment and package scope.

No broad crawl: a bounded profile exercises meaningful paths with predictable traffic. Add a reviewed, rate-limited link inventory later.

No full external-provider testing: destination contracts are owned by this suite; Greenhouse application functionality is not.

No screenshot-diff or performance gate: stable fixtures, approved visual baselines, and representative performance budgets are prerequisites. Network variability alone should not block a release.

No automatic test repair: a renamed locator may reflect a legitimate change, a regression, or missing accessibility semantics. Require review and preserve the failing evidence.

No complete accessibility claim: manually test keyboard reachability, focus order and visibility, screen-reader announcements, 200% text resize, 400% zoom, text spacing, reduced motion, contrast over images, touch target usability, error recovery, and alternative text meaning. Include disabled users in usability evaluation.

No claim that all shipped cases passed: see evidence/README.md for the exact distinction between offline tests, collection, browser probes, and unexecuted integrations.

## App and authoring assumptions

A technical helper can perform initial Python, browser, and optional Ollama setup. Ordinary use happens through the local app. AI generation uses only declared page scope and supplied expectations; it does not independently discover a site's requirements. Generated tests use the managed plan format, and arbitrary existing Python modules require developer translation. A person reviews changed expectations before applying them.

The local app is single-user and runs on loopback. Its files and SQLite history persist in the user's WebQA folder. Model size, installation, inference quality, and speed are environment-specific. Offline tests cover the authoring and HTTP workflows with controlled responses; actual model inference and full browser/UI execution remain installation acceptance checks.
