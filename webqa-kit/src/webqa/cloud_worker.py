"""Notebook worker. Runs inference only; never imports or runs downloaded Python tests."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import ValidationError, validate

from webqa.authoring import plan_cases
from webqa.cloud_protocol import atomic_json, fingerprint, read_json, validate_request, validate_result
from webqa.llm import chat, model_request


def validate_output(request, job, output):
    validate(output, job["schema"])
    operation = request["operation"]
    if operation in {"develop", "revise"}:
        plan_cases(output, request["profile"])
    elif operation == "explain":
        expected = {f["case_id"] for f in job["input"]["failures"]}
        ids = [f["case_id"] for f in output["explanations"]]
        if len(ids) != len(set(ids)) or set(ids) != expected:
            raise ValueError("Explain exactly the requested case IDs, with no duplicates or omissions")
    else:
        known = {c["case_id"] for c in job["input"]["current"]}
        if any(s["case_id"] not in known for s in output["suggestions"]):
            raise ValueError("Guidance must reference only supplied case IDs")


def process_request(request, model, destination, timeout=1200, provenance=None, progress=print, infer=None):
    validate_request(request)
    destination = Path(destination)
    folder = destination / request["id"]
    checkpoint = folder / "checkpoint.json"
    provenance = provenance or {}
    signature = fingerprint({"request": request, "model": model, "model_digest": provenance.get("model_digest")})
    outputs = {}
    if checkpoint.exists():
        previous = read_json(checkpoint)
        if previous.get("signature") != signature:
            raise ValueError("Checkpoint belongs to another model or request. Choose a new output folder.")
        outputs = previous.get("outputs", {})
        allowed = {job["id"] for job in request["jobs"]}
        if not isinstance(outputs, dict) or set(outputs) - allowed:
            raise ValueError("Invalid checkpoint jobs")
    call = infer or chat
    for number, job in enumerate(request["jobs"], 1):
        if job["id"] in outputs:
            validate_output(request, job, outputs[job["id"]])
            progress(f"Job {number}/{len(request['jobs'])}: using completed checkpoint.")
            continue
        progress(f"Job {number}/{len(request['jobs'])}: processing {request['operation']}…")
        try:
            with model_request(timeout, progress):
                answer = call(model, job["system"], job["input"], job["schema"])
            validate_output(request, job, answer)
            outputs[job["id"]] = answer
            atomic_json(checkpoint, {"signature": signature, "outputs": outputs})
        except Exception as exc:
            message = exc.message if isinstance(exc, ValidationError) else str(exc)
            message = message[:1000]
            atomic_json(folder / "last-error.json", {"job": job["id"], "error": message,
                                                     "completed_jobs": list(outputs)})
            raise ValueError(f"Job {number} did not complete: {message}. Completed jobs were saved; "
                             "rerun this step to resume. No complete result file was produced.") from exc
    result = {"format": "webqa-cloud-result", "version": 1, "request_id": request["id"],
              "request_sha256": fingerprint(request), "operation": request["operation"], "model": model,
              "created": datetime.now(timezone.utc).isoformat(), "provenance": provenance, "outputs": outputs}
    validate_result(result, request)
    result_path = folder / (request["id"] + ".webqa-result.json")
    atomic_json(result_path, result)
    progress("Complete. Download the result file and copy it into your local Cloud-Inbox.")
    return result_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--provenance", type=Path)
    args = parser.parse_args()
    provenance = read_json(args.provenance) if args.provenance else {}
    path = process_request(read_json(args.request), args.model, args.out, args.timeout, provenance)
    print(json.dumps({"result_file": str(path)}), flush=True)


if __name__ == "__main__":
    main()
