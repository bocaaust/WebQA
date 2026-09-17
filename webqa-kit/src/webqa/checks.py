"""Small deterministic check functions. Profiles contain no executable Python or JS."""
import json
from importlib.resources import files
from urllib.parse import urlsplit

from playwright.sync_api import expect


def locate(page, spec):
    root = page.locator(spec["scope"]) if spec.get("scope") else page
    if "selector" in spec:
        return root.locator(spec["selector"])
    if "label" in spec:
        return root.get_by_label(spec["label"], exact=spec.get("exact", True))
    options = {"exact": spec.get("exact", True)}
    if "name" in spec:
        options["name"] = spec["name"]
    if "level" in spec:
        options["level"] = spec["level"]
    return root.get_by_role(spec["role"], **options)


def prevent_submit_action(locator, action, value=None):
    # A plain button within a form defaults to submit. Inspect DOM properties,
    # rather than assuming an absent type attribute makes it safe.
    unsafe = locator.evaluate("""el => Boolean(el.closest('form')) && (
      (el.tagName === 'BUTTON' && el.type === 'submit') ||
      (el.tagName === 'INPUT' && ['submit','image'].includes(el.type)))""")
    in_form = locator.evaluate("el => Boolean(el.closest('form'))")
    activates = action == "click" or (action == "press" and value in {"Enter", "Space"})
    if (unsafe and activates) or (in_form and action == "press" and value == "Enter"):
        raise AssertionError("Form submission actions are intentionally unsupported")


def scan_axe(page, destination):
    page.evaluate("document.fonts.ready")
    source = files("webqa").joinpath("vendor/axe.min.js")
    page.add_script_tag(content=source.read_text(encoding="utf-8"))
    result = page.evaluate("""async () => await axe.run(document, {
        runOnly: {type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']},
        iframes:false
    })""")
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    findings = [{"rule": v["id"], "impact": v["impact"],
                 "targets": [n["target"] for n in v["nodes"]]} for v in result["violations"]]
    assert not findings, json.dumps(findings, indent=2)
    # 'incomplete' results remain in the artifact for manual assessment.


def page_check(page, spec, check, output):
    if check == "content":
        if spec.get("title_contains"):
            import re
            expect(page).to_have_title(re.compile(re.escape(spec["title_contains"]), re.I))
        if spec.get("h1_contains"):
            expect(page.get_by_role("heading", level=1)).to_contain_text(spec["h1_contains"])
    elif check == "structure":
        expect(page.locator("html")).to_have_attribute("lang", spec.get("language", "en"))
        expect(page.get_by_role("main")).to_have_count(1)
        expect(page.get_by_role("heading", level=1)).to_have_count(1)
        expect(page.get_by_role("heading", level=1)).not_to_be_empty()
    elif check == "axe":
        scan_axe(page, output / "axe.json")
    elif check == "semantics":
        expect(page.locator("a button, button a, button input, a input")).to_have_count(0)
    elif check == "image-alt":
        expect(page.locator('img:not([alt]), img[alt="Alt text"], img[alt="TODO"]')).to_have_count(0)
    elif check == "reflow":
        # A 320px viewport approximates one reflow condition; not a zoom audit.
        page.wait_for_function("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1",
                               timeout=10_000)
    else:
        raise ValueError(f"Unknown check: {check}")


def journey_check(page, journey, config, output):
    for number, step in enumerate(journey["steps"], start=1):
        (output / "active-step.json").write_text(json.dumps({"number": number, "step": step}), encoding="utf-8")
        action = step["action"]
        locator = locate(page, step["locator"]) if "locator" in step else None
        if action in {"click", "press"}:
            expect(locator).to_be_visible()
            prevent_submit_action(locator, action, step.get("value"))
            if action == "click":
                locator.click()
            else:
                locator.press(step["value"])
        elif action == "fill":
            expect(locator).to_be_editable()
            locator.fill(step["value"])
            expect(locator).to_have_value(step["value"])
        elif action == "keyboard":
            # Block Enter while focus is inside a form, including submit buttons.
            active = page.locator(":focus")
            if active.count():
                prevent_submit_action(active, "press", step["value"])
            page.keyboard.press(step["value"])
        elif action == "tab-to":
            for _ in range(step.get("max_tabs", 20)):
                if locator.evaluate("el => el === document.activeElement"):
                    break
                page.keyboard.press("Tab")
            expect(locator).to_be_focused()
        elif action == "expect-url":
            expect(page).to_have_url(config["base_url"] + step["value"])
        elif action == "expect":
            assertion = step["assert"]
            target = expect(locator)
            if assertion == "visible":
                target.to_be_visible()
            elif assertion == "hidden":
                target.to_be_hidden()
            elif assertion == "focused":
                target.to_be_focused()
            elif assertion == "text":
                target.to_contain_text(step["value"])
            elif assertion == "value":
                target.to_have_value(step["value"])
            elif assertion == "attribute":
                target.to_have_attribute(step["attribute"], step["value"])
            elif assertion == "count":
                target.to_have_count(step["count"])
        elif action == "axe":
            scan_axe(page, output / f"axe-step-{number}.json")
        elif action == "links":
            minimum = step.get("min_count", 1)
            if minimum:
                expect(locator.nth(minimum - 1)).to_be_visible()
            assert locator.count() >= minimum, "Link list smaller than its configured minimum"
            for link in locator.all():
                href = urlsplit(link.get_attribute("href") or "")
                assert href.scheme == "https" and href.hostname in step["hosts"], "Unexpected link destination"
                assert href.path.startswith(step.get("path_prefix", "/")), "Unexpected destination path"
                assert link.inner_text().strip(), "Destination link has no visible text"
