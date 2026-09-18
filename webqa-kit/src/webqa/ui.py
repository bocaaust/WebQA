"""Local, single-user app. Standard library only; never listens on a public interface."""
import copy
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from jsonschema import ValidationError

from webqa.authoring import apply_proposal, propose
from webqa.cloud import CloudExchange
from webqa.cloud_protocol import read_json
from webqa.config import load_profile, origin, validate_profile
from webqa.learning import review
from webqa.llm import model_request, progress
from webqa.reporting import build_report


class LocalApp:
    def __init__(self, workspace, inbox=None):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.db = self.workspace / "history.sqlite3"
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.lock = threading.Lock()
        self.jobs = {}
        self.cloud = CloudExchange(self.workspace, inbox)

    def site(self, site_id):
        if not re.fullmatch(r"site-[a-f0-9]{12}", site_id):
            raise ValueError("Choose a saved website")
        target = self.workspace / "sites" / site_id
        if not (target / "profile.json").is_file():
            raise ValueError("Website has not been saved")
        return target

    def save_site(self, url, page_lines=""):
        from webqa.cli import new_profile
        url = url.strip()
        if not url.startswith(("https://", "http://")):
            url = "https://" + url
        parsed = urlsplit(url)
        base = origin(f"{parsed.scheme}://{parsed.netloc}")
        if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("Enter the main website address above. Put individual pages in Pages to include.")
        site_id = "site-" + hashlib.sha256(base.encode()).hexdigest()[:12]
        target = self.workspace / "sites" / site_id
        if base == "https://www.capitaltg.com" and not page_lines.strip():
            profile = json.loads(files("webqa").joinpath("profiles/ctg.json").read_text())
        else:
            profile = new_profile(site_id, base)
            lines = [line.strip() for line in page_lines.splitlines() if line.strip()]
            if len(lines) > 10:
                raise ValueError("Include at most ten additional pages for this small on-demand run")
            for number, line in enumerate(lines, 1):
                address, _, heading = line.partition(" | ")
                if address.startswith("/"):
                    path = address
                else:
                    p = urlsplit(address)
                    if f"{p.scheme}://{p.netloc}" != base or p.query or p.fragment:
                        raise ValueError("Every included page must belong to this website, without a query or fragment")
                    path = p.path or "/"
                page = {"id": f"page-{number}", "path": path, "checks": ["structure", "axe", "reflow"],
                        "viewports": ["desktop"], "priority": "P1", "language": "en",
                        "why": "Page explicitly selected in the local app"}
                if heading.strip():
                    page["h1_contains"] = heading.strip()
                    page["checks"].insert(0, "content")
                if path == "/":
                    page["id"] = "home"
                    profile["pages"][0] = page
                else:
                    profile["pages"].append(page)
        validate_profile(profile)
        target.mkdir(parents=True, exist_ok=True)
        (target / "profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
        return {"id": site_id, "url": base, "pages": len(profile["pages"])}

    def state(self):
        websites = []
        for path in sorted((self.workspace / "sites").glob("*/profile.json")):
            config = load_profile(path)
            websites.append({"id": path.parent.name, "url": config["base_url"],
                             "page_lines": "" if config["id"] == "ctg" else "\n".join(
                                 p["path"] + (" | " + p["h1_contains"] if p.get("h1_contains") else "")
                                 for p in config["pages"] if p["path"] != "/" or p.get("h1_contains")),
                             "has_tests": (path.parent / "test_custom.py").exists(),
                             "latest_result": self.latest_result(path.parent)})
        with self.lock:
            active = next(({"id": key, **copy.deepcopy(value)} for key, value in self.jobs.items()
                           if value["status"] == "running"), None)
        return {"websites": websites, "workspace": str(self.workspace), "active_job": active, "cloud_inbox": str(self.cloud.inbox)}

    def latest_result(self, target):
        saved = target / "latest-result.json"
        if not saved.is_file():
            return None
        try:
            return json.loads(saved.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def publish_result(self, target, result):
        (target / "latest-result.json").write_text(json.dumps(result), encoding="utf-8")
        with self.lock:
            self.jobs[self.active_job]["preview"] = copy.deepcopy(result)

    def attach_report(self, result, run, report):
        prefix = "/report/" + run.relative_to(self.workspace).as_posix() + "/"
        result["report"] = prefix + "overview.html"
        result["ai_status"] = report["ai_status"]
        result["failures"] = [{**f, "screenshots": [{**shot, "url": prefix + shot["file"]}
                                                  for shot in f.get("screenshots", [])]}
                              for f in report["failures"]]
        return result

    def enqueue(self, fn, ai_timeout=600, site_id=None):
        if not isinstance(ai_timeout, int) or not 1 <= ai_timeout <= 1200:
            raise ValueError("Choose an AI wait time between 1 and 1200 seconds")
        with self.lock:
            if any(job["status"] == "running" for job in self.jobs.values()):
                raise ValueError("A task is already running. Wait for its result before starting another.")
            job_id = uuid.uuid4().hex
            self.jobs[job_id] = {"status": "running", "message": "Working. You can leave this window open.", "started": time.time(), "site": site_id}
            if len(self.jobs) > 30:
                del self.jobs[next(iter(self.jobs))]

        def update(message):
            with self.lock:
                self.jobs[job_id]["message"] = message

        def work():
            self.active_job = job_id
            try:
                with model_request(ai_timeout, update):
                    result = {"status": "done", "result": fn()}
            except Exception as exc:
                result = {"status": "error", "message": f"{exc}. Your existing tests were not automatically changed."}
            with self.lock:
                self.jobs[job_id] = result
        self.pool.submit(work)
        return {"job": job_id}

    def run(self, site_id, suite="accessibility", custom=False, model=None, ai_timeout=600):
        target = self.site(site_id)
        if suite not in {"full", "smoke", "accessibility", "mobile"}:
            raise ValueError("Choose a valid check type")
        run_root = target / "reports" / uuid.uuid4().hex
        command = [sys.executable, "-m", "webqa", "run", "--config", str(target / "profile.json"),
                   "--suite", suite, "--out", str(run_root), "--db", str(self.db)]
        if custom:
            command += ["--tests", str(target / "test_custom.py")]

        def task():
            progress("Checking the website and capturing failure evidence…")
            completed = subprocess.run(command, capture_output=True, text=True, timeout=1200, check=False)
            runs = list(run_root.glob("*/*/run.json"))
            if not runs:
                raise ValueError((completed.stderr or completed.stdout)[-2000:] or "The test runner could not start")
            run = runs[0].parent
            results = json.loads((run / "results.json").read_text()) if (run / "results.json").exists() else {}
            counts = {k: results.get("summary", {}).get(k, 0) for k in ["passed", "failed", "error", "skipped"]}
            (target / "latest-run.json").write_text(json.dumps({"path": str(run)}))
            link = "/report/" + run.relative_to(self.workspace).as_posix() + "/report.html"
            result = {"kind": "run", "exit_code": completed.returncode, "counts": counts,
                    "report": link if (run / "report.html").exists() else None,
                    "cases": [{"id": t["nodeid"].split("[")[-1].rstrip("]"), "outcome": t["outcome"]}
                              for t in results.get("tests", [])],
                    "log": (completed.stdout + completed.stderr)[-14000:]}
            if (run / "results.json").exists():
                self.attach_report(result, run, build_report(run))
                self.publish_result(target, result)
                if model:
                    self.attach_report(result, run, build_report(run, model))
            self.publish_result(target, result)
            return result
        return self.enqueue(task, ai_timeout, site_id)

    def author(self, site_id, request_text, model, revise=False, ai_timeout=600):
        target = self.site(site_id)
        proposal_id = uuid.uuid4().hex
        out = target / "proposals" / proposal_id
        existing = target / "test_custom.py" if revise else None
        if not revise and (target / "test_custom.py").exists():
            raise ValueError("This website already has AI tests. Choose Improve existing tests.")
        latest = target / "latest-run.json"
        run_dir = Path(json.loads(latest.read_text())["path"]) if latest.exists() else None

        def task():
            propose(target / "profile.json", request_text, model, out, self.db, existing, run_dir)
            return self.proposal_details(site_id, proposal_id)
        return self.enqueue(task, ai_timeout, site_id)

    def proposal_details(self, site_id, proposal_id):
        if not re.fullmatch(r"[a-f0-9]{32}", proposal_id):
            raise ValueError("Invalid proposal")
        out = self.site(site_id) / "proposals" / proposal_id
        record = read_json(out / "test_candidate.plan.json")
        return {"kind": "proposal", "proposal": proposal_id, "site": site_id,
                "summary": record["plan"]["summary"], "validation": read_json(out / "validation.json"),
                "tests": [{"id": t["id"], "why": t["why"], "priority": t["priority"]} for t in record["plan"]["tests"]],
                "applied": (out / "applied.json").exists(), "diff": (out / "changes.diff").read_text()}

    def import_cloud(self, filename):
        imported = self.cloud.import_result(filename)
        if imported["kind"] == "proposal":
            return self.proposal_details(imported["site"], imported["proposal"])
        if imported["kind"] == "run":
            target = self.site(imported["site"])
            run = self.workspace / imported["run"]
            result = self.latest_result(target)
            self.attach_report(result, run, read_json(run / "failure-report.json"))
            (target / "latest-result.json").write_text(json.dumps(result), encoding="utf-8")
            return {**result, "site": imported["site"]}
        return imported

    def open_inbox(self):
        folder = str(self.cloud.inbox)
        if sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        elif sys.platform == "win32":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])
        return {"message": "Copy the downloaded .webqa-result.json file into this folder, then Scan inbox.", "folder": folder}

    def apply(self, site_id, proposal_id):
        target = self.site(site_id)
        if not re.fullmatch(r"[a-f0-9]{32}", proposal_id):
            raise ValueError("Choose a valid proposal")
        apply_proposal(target / "proposals" / proposal_id, target / "profile.json", target / "test_custom.py")
        return {"message": "Tests saved. Use Run AI tests when you are ready to check the website."}

    def explain(self, site_id, model, ai_timeout=600):
        target = self.site(site_id)
        latest = target / "latest-run.json"
        if not latest.exists():
            raise ValueError("Run a website check first")
        run_dir = Path(json.loads(latest.read_text())["path"])

        def task():
            result = self.latest_result(target)
            if not result:
                raise ValueError("Run a new check to prepare a report with screenshots")
            self.attach_report(result, run_dir, build_report(run_dir, model))
            self.publish_result(target, result)
            return result
        return self.enqueue(task, ai_timeout, site_id)

    def feedback(self, site_id, case_id, decision, resolution):
        target = self.site(site_id)
        run_dir = Path(json.loads((target / "latest-run.json").read_text())["path"])
        meta = json.loads((run_dir / "run.json").read_text())
        review(self.db, meta["site_key"], case_id, decision, resolution)
        return {"message": "Review saved. The assistant will consider it the next time you ask for help."}


def installed_models():
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as response:
            data = json.loads(response.read(200000))
        return {"models": [m["name"] for m in data.get("models", [])], "available": True}
    except (OSError, ValueError, KeyError):
        return {"models": [], "available": False}


def handler(app, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, content, mime="application/json"):
            body = content.encode() if isinstance(content, str) else content
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}",
                                                  f"localhost:{self.server.server_port}"}

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, b"Local access only", "text/plain")
            parsed = urlsplit(self.path)
            if parsed.path == "/":
                html = files("webqa").joinpath("app.html").read_text().replace("__TOKEN__", token)
                return self.send(200, html, "text/html; charset=utf-8")
            if parsed.path == "/cloud-notebook":
                notebook = files("webqa").joinpath("assets/WebQA_Cloud_LLM.ipynb").read_bytes()
                return self.send(200, notebook, "application/x-ipynb+json")
            if parsed.path.startswith("/report/"):
                path = (app.workspace / parsed.path[len("/report/"):]).resolve()
                allowed = path.name in {"report.html", "overview.html"} or (
                    path.suffix == ".png" and path.name.startswith("failure-") and path.parent.parent.name == "checks")
                relative = path.relative_to(app.workspace).parts if path.is_relative_to(app.workspace) else ()
                if not allowed or len(relative) < 7 or relative[0] != "sites" or relative[2] != "reports" or not path.is_file():
                    return self.send(404, b"Report unavailable", "text/plain")
                mime = "image/png" if path.suffix == ".png" else "text/html; charset=utf-8"
                return self.send(200, path.read_bytes(), mime)
            if self.headers.get("X-WebQA-Token") != token:
                return self.send(403, b'{"error":"Please reopen the app"}')
            if parsed.path == "/api/state":
                result = app.state()
            elif parsed.path == "/api/models":
                result = installed_models()
            elif parsed.path == "/api/job":
                job = parse_qs(parsed.query).get("id", [""])[0]
                with app.lock:
                    result = app.jobs.get(job, {"status": "error", "message": "Task not found"})
            else:
                return self.send(404, b'{"error":"Not found"}')
            return self.send(200, json.dumps(result))

        def do_POST(self):
            if not self.valid_host() or self.headers.get("X-WebQA-Token") != token:
                return self.send(403, b'{"error":"Please reopen the app"}')
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 20000:
                    raise ValueError("Request is empty or too large")
                data = json.loads(self.rfile.read(size))
                if self.path == "/api/site":
                    with app.lock:
                        if any(j["status"] == "running" for j in app.jobs.values()):
                            raise ValueError("Wait for the active task before changing a website")
                        result = app.save_site(data["url"], data.get("pages", ""))
                elif self.path.startswith("/api/cloud/"):
                    with app.lock:
                        if any(j["status"] == "running" for j in app.jobs.values()):
                            raise ValueError("Wait for the current task before importing or exporting cloud work")
                        if self.path == "/api/cloud/export":
                            request = app.cloud.export(data["site"], data["operation"], data.get("request", ""))
                            result = {"request": request, "filename": request["id"] + ".webqa-request.json"}
                        elif self.path == "/api/cloud/scan":
                            result = app.cloud.scan()
                        elif self.path == "/api/cloud/import":
                            result = app.import_cloud(data["file"])
                        elif self.path == "/api/cloud/open":
                            result = app.open_inbox()
                        else:
                            raise ValueError("Unknown cloud action")
                elif self.path == "/api/run":
                    result = app.run(data["site"], data.get("suite", "accessibility"), data.get("custom", False),
                                     data.get("model"), data.get("ai_timeout", 600))
                elif self.path == "/api/author":
                    result = app.author(data["site"], data["request"], data["model"], data.get("revise", False), data.get("ai_timeout", 600))
                elif self.path == "/api/apply":
                    with app.lock:
                        if any(j["status"] == "running" for j in app.jobs.values()):
                            raise ValueError("Wait for the active task before applying changes")
                        result = app.apply(data["site"], data["proposal"])
                elif self.path == "/api/explain":
                    result = app.explain(data["site"], data["model"], data.get("ai_timeout", 600))
                elif self.path == "/api/review":
                    result = app.feedback(data["site"], data["case"], data["decision"], data["resolution"])
                else:
                    return self.send(404, b'{"error":"Not found"}')
                return self.send(200, json.dumps(result))
            except (ValueError, OSError, KeyError, TypeError, ValidationError) as exc:
                message = exc.message if isinstance(exc, ValidationError) else str(exc)
                return self.send(400, json.dumps({"error": message[:1200]}))
    return Handler


def serve(workspace, port=8765, open_browser=True, inbox=None):
    app = LocalApp(workspace, inbox)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler(app, secrets.token_urlsafe(32)))
    address = f"http://127.0.0.1:{server.server_port}"
    print(f"WebQA is ready at {address}. Close this window or press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.pool.shutdown(wait=False, cancel_futures=True)
