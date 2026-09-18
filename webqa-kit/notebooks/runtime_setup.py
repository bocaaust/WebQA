"""Notebook-owned Ollama setup and GPU preflight; not imported by the dashboard."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

import zstandard
from jsonschema import validate

from webqa.llm import chat, model_request

OLLAMA_VERSION = "0.34.1"
ARCHIVE_URL = "https://github.com/ollama/ollama/releases/download/v0.34.1/ollama-linux-amd64.tar.zst"
ARCHIVE_SHA256 = "f361dc3992ec07e4ad429f4bb2d10d4663ba2c295f9a9a688c7d52f4ba650034"


def get_json(route):
    with urllib.request.urlopen("http://127.0.0.1:11434" + route, timeout=5) as response:
        return json.load(response)


def dependency_preflight(root):
    if not (3, 12) <= sys.version_info[:2] < (3, 14):
        raise RuntimeError("This notebook supports Python 3.12 or 3.13. Choose a compatible Colab runtime.")
    versions = {}
    for line in (root / "requirements-colab.lock").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        name, expected = line.split("==")
        installed = importlib.metadata.version(name)
        if installed != expected:
            raise RuntimeError(f"Dependency mismatch: {name}. Rerun step 1.")
        versions[name] = installed
    checked = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True)
    (root / "pip-check.txt").write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    frozen = subprocess.check_output([sys.executable, "-m", "pip", "freeze", "--all"], text=True)
    (root / "environment-freeze.txt").write_text(frozen)
    validate({"ready": True}, {"type": "object", "required": ["ready"], "properties": {"ready": {"const": True}}})
    assert zstandard.ZstdDecompressor().decompress(zstandard.ZstdCompressor().compress(b"probe")) == b"probe"
    return {"python": sys.version, "platform": platform.platform(), "versions": versions,
            "pip_check": "passed", "schema_and_zstd_probes": "passed"}


def setup(root, model):
    root = Path(root)
    report = dependency_preflight(root)
    if sys.platform != "linux" or platform.machine() != "x86_64":
        raise RuntimeError("Select a Linux x86_64 Colab GPU runtime.")
    if not shutil.which("nvidia-smi"):
        raise RuntimeError("No NVIDIA GPU was found. Choose Runtime > Change runtime type > T4 GPU, then rerun.")
    report["gpu"] = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                                             "--format=csv,noheader"], text=True).strip()
    binary = root / "ollama" / "bin" / "ollama"
    marker = root / "ollama" / "verified-release.txt"
    if not binary.is_file() or not marker.exists() or marker.read_text() != ARCHIVE_SHA256:
        if shutil.disk_usage(root).free < 15 * 1024**3:
            raise RuntimeError("At least 15 GB of free runtime storage is needed for the engine and model.")
        archive = root / "ollama.tar.zst"
        print("Downloading the pinned Ollama engine (about 1.43 GB)…", flush=True)
        hasher = hashlib.sha256()
        with urllib.request.urlopen(ARCHIVE_URL, timeout=120) as source, archive.open("wb") as target:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                target.write(chunk)
                hasher.update(chunk)
        if hasher.hexdigest() != ARCHIVE_SHA256:
            raise RuntimeError("Engine download checksum mismatch. Rerun setup; do not use this download.")
        install = root / "ollama"
        install.mkdir(exist_ok=True)
        with archive.open("rb") as source, zstandard.ZstdDecompressor().stream_reader(source) as reader:
            with tarfile.open(fileobj=reader, mode="r|") as tar:
                tar.extractall(install, filter="data")
        if not binary.is_file():
            raise RuntimeError("Engine archive layout changed; setup cannot continue.")
        marker.write_text(ARCHIVE_SHA256)
        archive.unlink()
    try:
        active = get_json("/api/version")
    except OSError:
        env = {**os.environ, "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_MODELS": str(root / "models"),
               "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_MAX_LOADED_MODELS": "1"}
        with (root / "ollama.log").open("ab") as log:
            process = subprocess.Popen([str(binary), "serve"], env=env, stdout=log, stderr=subprocess.STDOUT)
        (root / "ollama.pid").write_text(str(process.pid))
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError("Ollama could not start. See ollama.log in the notebook files.")
            try:
                active = get_json("/api/version")
                break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError("Ollama startup timed out. See ollama.log.")
    if active.get("version") != OLLAMA_VERSION:
        raise RuntimeError("A different Ollama version is running. Use a fresh Colab runtime and rerun setup.")
    print(f"Preparing {model}. Its first download may take several minutes…", flush=True)
    subprocess.run([str(binary), "pull", model], check=True, timeout=1800,
                   env={**os.environ, "OLLAMA_HOST": "127.0.0.1:11434"})
    with model_request(600, lambda msg: print(msg, flush=True)):
        reply = chat(model, 'Return {"ready": true} as JSON.', {},
                     {"type": "object", "additionalProperties": False, "required": ["ready"],
                      "properties": {"ready": {"const": True}}})
    if reply != {"ready": True}:
        raise RuntimeError("Structured model response probe failed.")
    loaded = next((m for m in get_json("/api/ps").get("models", []) if m.get("name") == model), None)
    if not loaded or loaded.get("size_vram", 0) <= 0:
        raise RuntimeError("The model did not use GPU memory. Choose a GPU runtime or a smaller model before continuing.")
    model_info = next(m for m in get_json("/api/tags")["models"] if m["name"] == model)
    report.update(ollama_version=active["version"], engine_sha256=ARCHIVE_SHA256, model=model,
                  model_digest=model_info["digest"], gpu_bytes=loaded["size_vram"],
                  model_schema_probe="passed", gpu_probe="passed")
    (root / "preflight.json").write_text(json.dumps(report, indent=2))
    print("Preflight passed: GPU model, structured output, and dependencies are ready.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    setup(args.root, args.model)
