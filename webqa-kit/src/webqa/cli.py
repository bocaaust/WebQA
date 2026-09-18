"""Installable CLI; no GitHub, hosting service, or LLM account required."""
import argparse
import hashlib
import json
import subprocess
import shutil
import sys
import uuid
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from jsonschema import ValidationError

from webqa import __version__
from webqa.config import expand_cases, load_profile, validate_profile
from webqa.learning import advise, history, ingest, review, site_key
from webqa.authoring import apply_proposal, load_managed, propose, sidecar


def new_profile(site_id, url):
    return {"schema_version": 1, "id": site_id, "base_url": url,
            "viewports": [{"id": "desktop", "width": 1440, "height": 1000},
                          {"id": "mobile", "width": 390, "height": 844}],
            "pages": [{"id": "home", "path": "/", "checks": ["structure", "axe", "semantics", "image-alt", "reflow"],
                       "viewports": ["desktop", "mobile"], "priority": "P1", "language": "en",
                       "why": "Baseline public homepage accessibility; add explicit content and journey oracles."}],
            "journeys": []}


def parser():
    p = argparse.ArgumentParser(prog="webqa", description="On-demand public website QA")
    p.add_argument("--version", action="version", version=__version__)
    commands = p.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a site profile without making network requests")
    init.add_argument("--preset", choices=["ctg"])
    init.add_argument("--url")
    init.add_argument("--id", default="my-site")
    init.add_argument("--out", type=Path, required=True)
    validate_cmd = commands.add_parser("validate", help="Validate and list planned cases")
    validate_cmd.add_argument("config", type=Path)
    run = commands.add_parser("run", help="Run serial read-only browser checks now")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--suite", choices=["full", "smoke", "accessibility", "mobile"], default="full")
    run.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")
    run.add_argument("--model", help="Optional local model for plain-language failure reports")
    run.add_argument("--ai-timeout", type=int, default=600, help="AI deadline in seconds (1–1200)")
    run.add_argument("--headed", action="store_true")
    run.add_argument("--collect-only", action="store_true", help="Validate pytest collection without opening a browser")
    run.add_argument("--out", type=Path, default=Path("reports"))
    run.add_argument("--db", type=Path, default=Path(".webqa/history.sqlite3"))
    run.add_argument("--tests", type=Path, action="append", default=[],
                     help="Run a managed pytest module instead of the profile suite; repeat for multiple modules")
    for name in ["develop", "revise"]:
        cmd = commands.add_parser(name, help="Ask the local LLM to propose a managed pytest module")
        cmd.add_argument("--config", type=Path, required=True)
        cmd.add_argument("--ai-timeout", type=int, default=600, help="AI deadline in seconds (1–1200)")
        cmd.add_argument("--request", required=True, help="Describe the desired behavior in plain language")
        cmd.add_argument("--model", required=True, help="Installed local Ollama model")
        cmd.add_argument("--out", type=Path, required=True, help="New proposal directory")
        cmd.add_argument("--db", type=Path, default=Path(".webqa/history.sqlite3"))
        cmd.add_argument("--run", type=Path, help="Optional failure evidence from this website")
        if name == "revise":
            cmd.add_argument("--test", type=Path, required=True, help="Existing managed pytest module")
    apply_cmd = commands.add_parser("apply", help="Apply a reviewed proposal; never runs it automatically")
    apply_cmd.add_argument("proposal", type=Path)
    apply_cmd.add_argument("--config", type=Path, required=True)
    apply_cmd.add_argument("--dest", type=Path, required=True)
    ui = commands.add_parser("ui", help="Open the local app for people who prefer buttons to commands")
    ui.add_argument("--port", type=int, default=8765)
    ui.add_argument("--workspace", type=Path, default=Path.home() / "WebQA")
    ui.add_argument("--inbox", type=Path, default=Path.cwd() / "Cloud-Inbox", help="Folder for Colab result files")
    ui.add_argument("--no-open", action="store_true", help="Do not open the browser automatically")
    for name in ["advise", "review"]:
        cmd = commands.add_parser(name)
        cmd.add_argument("run_dir", type=Path)
        cmd.add_argument("--db", type=Path, default=Path(".webqa/history.sqlite3"))
        if name == "advise":
            cmd.add_argument("--model", help="Optional installed local Ollama model name")
        else:
            cmd.add_argument("--case", required=True)
            cmd.add_argument("--decision", choices=["accepted", "rejected"], required=True)
            cmd.add_argument("--resolution", required=True, help="Reviewed diagnosis; do not put secrets here")
    hist = commands.add_parser("history")
    hist.add_argument("config", type=Path)
    hist.add_argument("--db", type=Path, default=Path(".webqa/history.sqlite3"))
    return p


def run_suite(args):
    config = load_profile(args.config)
    managed = []
    for path in args.tests:
        record, source = load_managed(path, config)
        managed.append((path, record, source))
    names = [path.name for path, _, _ in managed]
    if len(names) != len(set(names)):
        raise ValueError("Managed module filenames must be unique")
    timestamp = datetime.now(timezone.utc)
    run_id = timestamp.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    out = (args.out / config["id"] / run_id).resolve()
    out.mkdir(parents=True)
    snapshot = out / "profile.json"
    snapshot.write_text(json.dumps(config, indent=2), encoding="utf-8")
    meta = {"run_id": run_id, "created": timestamp.isoformat(), "site_key": site_key(config),
            "site_id": config["id"], "base_url": config["base_url"], "suite": args.suite,
            "browser": args.browser, "package_version": __version__,
            "profile_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
            "execution": "collection-only" if args.collect_only else "live-browser"}
    (out / "run.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    suite = Path(str(files("webqa").joinpath("suite")))
    test_paths = [str(suite / "test_site.py")]
    if managed:
        authored = out / "authored"
        authored.mkdir()
        test_paths = []
        for path, record, source in managed:
            target = authored / path.name
            target.write_text(source, encoding="utf-8")
            shutil.copyfile(sidecar(path), sidecar(target))
            test_paths.append(str(target))
        meta["managed_modules"] = names
    command = [sys.executable, "-m", "pytest", *test_paths, "-p", "webqa.pytest_plugin",
               "-c", str(suite / "pytest.ini"), "--run-config", str(snapshot),
               "--run-directory", str(out), "--browser", args.browser, "-v",
               "--json-report", "--json-report-file", str(out / "results.json"),
               "--junitxml", str(out / "junit.xml"), "--html", str(out / "report.html"), "--self-contained-html",
               "--output", str(out / "browser"), "--tracing", "retain-on-failure",
               "--screenshot", "only-on-failure"]
    if args.suite != "full":
        command.extend(["-m", args.suite])
    if args.headed:
        command.append("--headed")
    if args.collect_only:
        command.append("--collect-only")
    completed = subprocess.run(command, check=False)  # argv list; no shell interpolation.
    meta["exit_code"] = completed.returncode
    (out / "run.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if not args.collect_only and (out / "results.json").exists():
        ingest(args.db, out)
        advise(args.db, out)
        from webqa.reporting import build_report
        from webqa.llm import model_request
        with model_request(args.ai_timeout):
            build_report(out, args.model)
    print(f"Report directory: {out}")
    return completed.returncode


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    try:
        if args.command == "init":
            if args.out.exists():
                raise ValueError("Output exists; choose a new filename to preserve the current profile")
            if args.preset:
                if args.url:
                    raise ValueError("Choose --preset or --url, not both")
                data = json.loads(files("webqa").joinpath("profiles/ctg.json").read_text())
            elif args.url:
                data = new_profile(args.id, args.url)
            else:
                raise ValueError("Provide --preset ctg or --url https://your-site.example")
            validate_profile(data)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(f"Created {args.out}. Review the profile before running it.")
        elif args.command == "validate":
            config = load_profile(args.config)
            cases = expand_cases(config)
            for case in cases:
                print(f"{case['priority']} {case['id']}")
            print(f"Valid profile: {len(cases)} cases; target {config['base_url']}")
        elif args.command == "run":
            return run_suite(args)
        elif args.command in {"develop", "revise"}:
            from webqa.llm import model_request
            with model_request(args.ai_timeout, lambda message: print(message, flush=True)):
                result = propose(args.config, args.request, args.model, args.out, args.db,
                                 getattr(args, "test", None), args.run)
            print(json.dumps(result, indent=2))
            print(f"Proposal: {args.out}. Review changes.diff and validation.json before applying.")
        elif args.command == "apply":
            print(f"Applied {apply_proposal(args.proposal, args.config, args.dest)}. Run it with webqa run --tests.")
        elif args.command == "ui":
            from webqa.ui import serve
            serve(args.workspace, args.port, not args.no_open, args.inbox)
        elif args.command == "advise":
            print(json.dumps(advise(args.db, args.run_dir, args.model), indent=2))
        elif args.command == "review":
            meta = json.loads((args.run_dir / "run.json").read_text())
            review(args.db, meta["site_key"], args.case, args.decision, args.resolution)
            print("Human review saved. Subsequent advice will retrieve it for this site.")
        elif args.command == "history":
            print(json.dumps(history(args.db, site_key(load_profile(args.config))), indent=2))
        return 0
    except (ValueError, OSError, KeyError, ValidationError) as exc:
        print(f"webqa: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
