"""Export LLM-only work; validate inbox results against local snapshots before use."""
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from webqa import authoring, learning, reporting
from webqa.cloud_protocol import atomic_json, fingerprint, read_json, validate_request, validate_result
from webqa.config import load_profile


def file_hash(path):
    return authoring.digest(Path(path).read_bytes()) if Path(path).is_file() else None


def run_fingerprint(run):
    paths = [run / "run.json", run / "results.json", *sorted((run / "checks").glob("*/failure-*.json"))]
    return fingerprint({p.relative_to(run).as_posix(): file_hash(p) for p in paths})


def compact_context(packet):
    """Bound historical text without altering a current plan or test expectations."""
    if "history" in packet:
        packet["history"] = sorted(packet["history"], key=lambda row: row.get("failures", 0), reverse=True)[:50]
    if "human_reviews" in packet:
        packet["human_reviews"] = [{**row, "resolution": reporting.clean(row["resolution"], 500)}
                                   for row in packet["human_reviews"][:15]]
    if "accessibility_rules" in packet:
        packet["accessibility_rules"] = packet["accessibility_rules"][:80]
    if "failure_evidence" in packet:
        compact_context(packet["failure_evidence"])
    packet["context_note"] = "History and review notes are bounded excerpts; current test plans remain complete."
    return packet


class CloudExchange:
    def __init__(self, workspace, inbox=None):
        self.workspace = Path(workspace).resolve()
        self.requests = self.workspace / "cloud" / "requests"
        self.inbox = Path(inbox or self.workspace / "Cloud-Inbox").resolve()
        self.inbox.mkdir(parents=True, exist_ok=True)

    def site(self, site_id):
        if not re.fullmatch(r"site-[a-f0-9]{12}", str(site_id)):
            raise ValueError("Choose a saved website")
        path = self.workspace / "sites" / site_id
        if not (path / "profile.json").is_file():
            raise ValueError("Website has not been saved")
        return path

    def request_dir(self, request_id):
        if not re.fullmatch(r"[a-f0-9]{32}", str(request_id)):
            raise ValueError("Invalid request ID")
        return self.requests / request_id

    def latest_run(self, target):
        pointer = target / "latest-run.json"
        if not pointer.exists():
            raise ValueError("Run a website check before exporting explanations or guidance")
        run = Path(read_json(pointer)["path"]).resolve()
        if not run.is_relative_to(target / "reports") or not (run / "results.json").is_file():
            raise ValueError("The saved run is unavailable; run a new check")
        return run

    def export(self, site_id, operation, request_text=""):
        target = self.site(site_id)
        config_path = target / "profile.json"
        config = load_profile(config_path)
        existing = target / "test_custom.py"
        context = {"site": site_id, "profile_sha256": authoring.profile_digest(config),
                   "source_sha256": file_hash(existing), "sidecar_sha256": file_hash(authoring.sidecar(existing))}
        prompts = []
        if operation in {"develop", "revise"}:
            if operation == "develop" and (existing.exists() or authoring.sidecar(existing).exists()):
                raise ValueError("This website already has AI tests. Choose Improve existing tests.")
            if operation == "revise" and not existing.exists():
                raise ValueError("Create and apply tests before requesting a revision")
            run = self.latest_run(target) if (target / "latest-run.json").exists() else None
            _, packet = authoring.prepare_request(config_path, request_text, self.workspace / "history.sqlite3",
                                                   existing if operation == "revise" else None, run)
            prompts.append((authoring.SYSTEM, compact_context(packet), authoring.plan_schema()))
        elif operation in {"explain", "advise"}:
            run = self.latest_run(target)
            context.update(run=str(run.relative_to(self.workspace)), run_sha256=run_fingerprint(run))
            if operation == "explain":
                _, failures = reporting.read_failures(run)
                if not failures:
                    raise ValueError("No failed checks need an explanation in the latest run")
                # Cover the complete failed run in small batches, with per-job Colab checkpoints.
                keys = {"case_id", "phase", "path", "viewport", "check", "message", "rules", "purpose", "outcome", "active_step"}
                for offset in range(0, len(failures), 6):
                    packet = {"failures": [{k: v for k, v in f.items() if k in keys} for f in failures[offset:offset + 6]]}
                    for failure in packet["failures"]:
                        failure["message"] = reporting.clean(failure.get("message", ""), 1200)
                        failure["purpose"] = reporting.clean(failure.get("purpose", ""), 500)
                        if "rules" in failure:
                            failure["rules_total"] = len(failure["rules"])
                            failure["rules"] = failure["rules"][:10]
                    prompts.append((reporting.SYSTEM, packet, reporting.SCHEMA))
            else:
                packet = learning.evidence_packet(self.workspace / "history.sqlite3", run)
                prompts.append((learning.SYSTEM, compact_context(packet), learning.GUIDANCE_SCHEMA))
        else:
            raise ValueError("Choose a supported cloud task")
        request_id = uuid.uuid4().hex
        request = {"format": "webqa-cloud-request", "version": 1, "id": request_id,
                   "created": datetime.now(timezone.utc).isoformat(), "operation": operation,
                   "website": config["base_url"], "profile": config, "jobs": [{"id": f"job-{i:03}", "system": system,
                       "input": packet, "schema": schema} for i, (system, packet, schema) in enumerate(prompts)]}
        validate_request(request)
        folder = self.request_dir(request_id)
        atomic_json(folder / "request.json", request)
        atomic_json(folder / "context.json", context)
        return request

    def scan(self):
        items = []
        paths = sorted(self.inbox.glob("*.webqa-result.json"))
        for path in paths[:100]:
            try:
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Copy the downloaded file itself, not a shortcut")
                data = read_json(path)
                folder = self.request_dir(data.get("request_id", ""))
                if not (folder / "request.json").exists():
                    raise ValueError("No matching request on this computer")
                request = read_json(folder / "request.json")
                validate_result(data, request)
                receipt = folder / "receipt.json"
                items.append({"file": path.name, "site": read_json(folder / "context.json")["site"],
                              "operation": request["operation"], "status": "imported" if receipt.exists() else "ready"})
            except Exception as exc:
                items.append({"file": path.name, "status": "invalid", "message": str(exc)[:300]})
        return {"folder": str(self.inbox), "files": items, "more": len(paths) > 100}

    def import_result(self, filename):
        if not isinstance(filename, str) or Path(filename).name != filename or not filename.endswith(".webqa-result.json"):
            raise ValueError("Choose a Colab result file from Cloud-Inbox")
        path = self.inbox / filename
        if path.is_symlink() or not path.resolve().is_relative_to(self.inbox):
            raise ValueError("Cloud result must be a regular file in the inbox")
        result = read_json(path)
        folder = self.request_dir(result.get("request_id", ""))
        request = read_json(folder / "request.json")
        validate_result(result, request)
        context = read_json(folder / "context.json")
        target = self.site(context["site"])
        config = load_profile(target / "profile.json")
        if authoring.profile_digest(config) != context["profile_sha256"]:
            raise ValueError("Website settings changed after export. Export a fresh cloud request.")
        if request["operation"] in {"explain", "advise"}:
            run = (self.workspace / context["run"]).resolve()
            if self.latest_run(target) != run or run_fingerprint(run) != context["run_sha256"]:
                raise ValueError("The latest run changed after export. Export a fresh explanation request.")
        receipt_path = folder / "receipt.json"
        result_hash = fingerprint(result)
        if receipt_path.exists():
            receipt = read_json(receipt_path)
            if receipt["result_sha256"] != result_hash:
                raise ValueError("A different result for this request was already imported. Export a new request.")
            return receipt["imported"]  # Idempotent: retain the same reviewed proposal and evidence.
        operation = request["operation"]
        imported = {"site": context["site"], "operation": operation, "request_id": request["id"]}
        if operation in {"develop", "revise"}:
            existing = target / "test_custom.py"
            if file_hash(existing) != context["source_sha256"] or file_hash(authoring.sidecar(existing)) != context["sidecar_sha256"]:
                raise ValueError("Tests changed after export. Export a fresh revision request.")
            proposal_id = uuid.uuid4().hex
            authoring.save_plan(config, request["jobs"][0]["input"], result["outputs"]["job-000"],
                                "colab:" + result["model"], target / "proposals" / proposal_id,
                                existing if operation == "revise" else None)
            imported.update(kind="proposal", proposal=proposal_id)
        else:
            run = (self.workspace / context["run"]).resolve()
            if self.latest_run(target) != run or run_fingerprint(run) != context["run_sha256"]:
                raise ValueError("The latest run changed after export. Export a fresh explanation request.")
            if operation == "explain":
                explanations = []
                for job in request["jobs"]:
                    answer = result["outputs"][job["id"]]["explanations"]
                    expected = {f["case_id"] for f in job["input"]["failures"]}
                    ids = [f["case_id"] for f in answer]
                    if len(ids) != len(set(ids)) or set(ids) != expected:
                        raise ValueError("Cloud explanation must match every requested failed check exactly")
                    explanations.extend(answer)
                counts, failures = reporting.read_failures(run)
                by_id = {f["case_id"]: f for f in explanations}
                for failure in failures:
                    failure.update(by_id[failure["case_id"]], source="Colab AI explanation — verify against evidence")
                report = {"counts": counts, "failures": failures,
                          "ai_status": f"Colab explained {len(failures)} failed checks using {result['model']}."}
                reporting.render_report(run, report)
                imported.update(kind="run", run=context["run"])
            else:
                guidance = result["outputs"]["job-000"]
                known = {c["case_id"] for c in request["jobs"][0]["input"]["current"]}
                if any(s["case_id"] not in known for s in guidance["suggestions"]):
                    raise ValueError("Cloud guidance referenced a check outside this run")
                guidance = {"source": "colab", "model": result["model"], "advisory_only": True, **guidance}
                atomic_json(run / "guidance.json", guidance)
                imported.update(kind="advice", guidance=guidance)
        atomic_json(folder / "result.json", result)
        atomic_json(receipt_path, {"result_sha256": result_hash, "imported": imported})
        return imported
