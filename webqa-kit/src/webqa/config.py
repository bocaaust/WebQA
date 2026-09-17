"""Validate declarative profiles before a browser or network connection exists."""
import ipaddress
import json
from importlib.resources import files
from pathlib import Path
from urllib.parse import unquote, urlsplit

from jsonschema import Draft202012Validator


def origin(value):
    p = urlsplit(value)
    if p.scheme not in {"https", "http"} or not p.hostname or p.username or p.password:
        raise ValueError("Expected an HTTP(S) origin without credentials")
    if p.path not in {"", "/"} or p.query or p.fragment:
        raise ValueError("base_url must contain only an origin")
    local = p.hostname in {"localhost", "127.0.0.1", "::1"}
    if p.scheme != "https" and not local:
        raise ValueError("Public targets require HTTPS; HTTP is for localhost fixtures")
    # Reject obvious private literal targets; this CLI is not a hosted SSRF defense.
    try:
        address = ipaddress.ip_address(p.hostname)
    except ValueError:
        address = None
    if address and not address.is_global and not local:
        raise ValueError("Private IP targets are not supported")
    _ = p.port  # Validate malformed port syntax.
    return value.rstrip("/")


def safe_path(value):
    decoded = unquote(value)
    p = urlsplit(value)
    if not value.startswith("/") or value.startswith("//") or p.query or p.fragment or p.netloc:
        raise ValueError(f"Use an explicit relative page path without query or fragment: {value}")
    if "\\" in decoded or ".." in decoded.split("/") or any(ord(c) < 32 for c in decoded):
        raise ValueError("Unsafe path")
    if any(part.lower() in {"admin", "login", "logout", "sign-in", "signin", "wp-admin"}
           for part in decoded.split("/")):
        raise ValueError("Authenticated and admin routes are outside this product's scope")
    return value


def validate_profile(data):
    schema = json.loads(files("webqa").joinpath("schema.json").read_text())
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: str(e.path))
    if errors:
        raise ValueError("; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5]))
    data["base_url"] = origin(data["base_url"])
    viewport_ids = [v["id"] for v in data["viewports"]]
    page_ids = [p["id"] for p in data["pages"]]
    journey_ids = [j["id"] for j in data["journeys"]]
    for names in [viewport_ids, page_ids, journey_ids]:
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ids are not allowed within a collection")
    paths = {safe_path(p["path"]) for p in data["pages"]}
    if len(paths) != len(data["pages"]):
        raise ValueError("Duplicate page paths are not allowed")
    for page in data["pages"]:
        if not set(page["viewports"]) <= set(viewport_ids):
            raise ValueError("Unknown page viewport")
        if "content" in page["checks"] and not (page.get("h1_contains") or page.get("title_contains")):
            raise ValueError("Content checks need an explicit title_contains or h1_contains oracle")
    for journey in data["journeys"]:
        if journey["start"] not in paths or journey["viewport"] not in viewport_ids:
            raise ValueError("Journey start and viewport must be declared")
        for step in journey["steps"]:
            action = step["action"]
            if action in {"click", "press", "fill", "expect", "tab-to", "links"} and "locator" not in step:
                raise ValueError(f"{action} requires a locator")
            if action in {"press", "fill", "keyboard", "expect-url"} and "value" not in step:
                raise ValueError(f"{action} requires a value")
            if action == "expect-url" and step["value"] not in paths:
                raise ValueError("Expected URL must be a declared public page path")
            if action in {"press", "keyboard"} and step["value"] not in {
                "Enter", "Space", "Escape", "Tab", "Shift+Tab", "ArrowDown", "ArrowUp", "Home", "End"
            }:
                raise ValueError("Unsupported key")
            if action == "expect":
                assertion = step.get("assert")
                if assertion is None:
                    raise ValueError("expect requires assert")
                if assertion in {"text", "value", "attribute"} and "value" not in step:
                    raise ValueError("Text, value and attribute assertions require value")
                if assertion == "attribute" and "attribute" not in step:
                    raise ValueError("Attribute name required")
                if assertion == "count" and "count" not in step:
                    raise ValueError("Count assertion requires count")
            if action == "links" and not step.get("hosts"):
                raise ValueError("Link destination checks require exact allowed hosts")
    if len(expand_cases(data)) > 100:
        raise ValueError("Maximum 100 cases per run; split large profiles")
    return data


def load_profile(path):
    return validate_profile(json.loads(Path(path).read_text(encoding="utf-8")))


def expand_cases(config):
    cases = []
    for page in config["pages"]:
        for viewport in page["viewports"]:
            for check in page["checks"]:
                cases.append({"id": f"page--{page['id']}--{viewport}--{check}",
                              "kind": "page", "check": check, "viewport": viewport,
                              "priority": page["priority"], "spec": page})
    for journey in config["journeys"]:
        cases.append({"id": "journey--" + journey["id"], "kind": "journey",
                      "viewport": journey["viewport"], "priority": journey["priority"], "spec": journey})
    return cases
