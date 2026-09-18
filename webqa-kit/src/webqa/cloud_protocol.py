"""Portable data-only request/result protocol, shared with the Colab worker."""
import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator, validate

FORMAT_VERSION = 1
MAX_BYTES = 2_000_000


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Cloud file is too large (maximum 2 MB)")
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def check_schema_refs(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$ref", "$dynamicRef"} and (not isinstance(child, str) or not child.startswith("#/")):
                raise ValueError("Only local schema references are supported")
            check_schema_refs(child)
    elif isinstance(value, list):
        for child in value:
            check_schema_refs(child)


def validate_request(request):
    if not isinstance(request, dict) or request.get("format") != "webqa-cloud-request" or request.get("version") != FORMAT_VERSION:
        raise ValueError("Use a WebQA cloud request exported by version 0.4.0 or newer")
    if not re.fullmatch(r"[a-f0-9]{32}", str(request.get("id", ""))):
        raise ValueError("Invalid cloud request ID")
    if request.get("operation") not in {"develop", "revise", "explain", "advise"}:
        raise ValueError("Unsupported cloud operation")
    jobs = request.get("jobs")
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= 20:
        raise ValueError("A cloud request must contain 1–20 bounded jobs")
    seen = set()
    for job in jobs:
        if not isinstance(job, dict) or set(job) != {"id", "system", "input", "schema"}:
            raise ValueError("Invalid cloud job")
        if not re.fullmatch(r"job-[0-9]{3}", str(job["id"])) or job["id"] in seen:
            raise ValueError("Invalid or duplicate cloud job ID")
        seen.add(job["id"])
        if not isinstance(job["system"], str) or not isinstance(job["input"], dict):
            raise ValueError("Invalid cloud prompt")
        check_schema_refs(job["schema"])
        Draft202012Validator.check_schema(job["schema"])
        if len(canonical(job)) > 44000:
            raise ValueError("A cloud job is too large. Shorten the request or reduce the profile.")
    if len(canonical(request)) > MAX_BYTES:
        raise ValueError("Cloud request exceeds 2 MB")
    return request


def validate_result(result, request):
    validate_request(request)
    if not isinstance(result, dict) or result.get("format") != "webqa-cloud-result" or result.get("version") != FORMAT_VERSION:
        raise ValueError("This is not a supported Colab result file")
    if result.get("request_id") != request["id"] or result.get("request_sha256") != fingerprint(request):
        raise ValueError("This result does not match the exported request")
    if result.get("operation") != request["operation"]:
        raise ValueError("Cloud operation does not match")
    if not isinstance(result.get("model"), str) or not 1 <= len(result["model"]) <= 200:
        raise ValueError("Model provenance is missing")
    outputs = result.get("outputs")
    expected = {job["id"]: job for job in request["jobs"]}
    if not isinstance(outputs, dict) or set(outputs) != set(expected):
        raise ValueError("Cloud result is incomplete or contains unexpected jobs")
    for key, value in outputs.items():
        validate(value, expected[key]["schema"])
    if len(canonical(result)) > MAX_BYTES:
        raise ValueError("Cloud result exceeds 2 MB")
    return result
