"""Build the self-contained notebook from the same trusted Python modules as the app."""
import ast
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = {}
for name in ['__init__.py', 'llm.py', 'authoring.py', 'config.py', 'learning.py',
             'cloud_protocol.py', 'cloud_worker.py', 'schema.json']:
    BUNDLE['webqa/' + name] = (ROOT / 'src/webqa' / name).read_text()
for name in ['runtime_setup.py', 'requirements-colab.lock', 'compatibility-manifest.json']:
    BUNDLE[name] = (ROOT / 'notebooks' / name).read_text()

cells = []


def markdown(text):
    cells.append({'cell_type': 'markdown', 'metadata': {}, 'source': text.splitlines(True)})


def code(text, title):
    ast.parse(text)
    cells.append({'cell_type': 'code', 'metadata': {'cellView': 'form'}, 'source':
                  ('#@title ' + title + '\n' + text).splitlines(True), 'execution_count': None, 'outputs': []})


markdown('''# WebQA Cloud LLM — version 0.4.0

Run the AI work here, then run website tests in your local WebQA dashboard. No API key is needed. This notebook uses an Ollama model on your Google Colab GPU.

**Before running:** select **Runtime → Change runtime type → T4 GPU** (or another NVIDIA GPU). Then run steps 1–5 using each ▶ button. You do not need to edit code.

1. In the local dashboard, choose **Google Colab (file exchange)**.
2. Export a test request, failure explanations, or learning guidance.
3. Upload that `.webqa-request.json` file in step 3 below.
4. Download the completed `.webqa-result.json` in step 5.
5. Copy it into the app folder’s **Cloud-Inbox**. Click **Scan inbox → Import and review**. For tests, choose **Use these tests → Run AI tests**.

**What goes to Colab:** your selected website settings, test expectations, bounded failure messages, and relevant history/review notes. Screenshots and browser execution stay on your computer. Review the exported request before uploading if notes contain private information.

GPU availability and session duration depend on Colab. This notebook does its work through notebook cells, with no tunnel or publicly exposed server. See [Colab’s FAQ](https://research.google.com/colaboratory/faq.html).

This release includes local protocol, dependency, and notebook-code tests. A real Colab GPU/model run is not claimed; step 2 performs that acceptance check on your assigned runtime.
''')

code('''import json
import os
import subprocess
import sys
import venv
from pathlib import Path

SAVE_CHECKPOINTS_TO_DRIVE = False #@param {type:"boolean"}
if not (3, 12) <= sys.version_info[:2] < (3, 14):
    raise RuntimeError("Use a Colab runtime with Python 3.12 or 3.13.")
ROOT = Path("/content/webqa-cloud")
ROOT.mkdir(parents=True, exist_ok=True)
BUNDLED_FILES = ''' + repr(BUNDLE) + '''
for relative, contents in BUNDLED_FILES.items():
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
VENV = ROOT / "venv"
if not (VENV / "bin/python").exists():
    venv.EnvBuilder(with_pip=False).create(VENV)
PYTHON = str(VENV / "bin/python")
ENV = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONUNBUFFERED": "1"}
# Install only when the exact isolated environment is missing or mismatched.
version_probe = "from importlib.metadata import version; from pathlib import Path; " + \\
    "pairs=[line.split('==') for line in Path('" + str(ROOT / 'requirements-colab.lock') + "').read_text().splitlines() if line]; " + \\
    "assert all(version(name)==expected for name,expected in pairs)"
ready = subprocess.run([PYTHON, "-c", version_probe], capture_output=True).returncode == 0
if not ready:
    command = [sys.executable, "-m", "pip", "--python", PYTHON, "install", "-r", str(ROOT / "requirements-colab.lock")]
    installed = subprocess.run(command, capture_output=True, text=True)
    (ROOT / "installer.log").write_text(installed.stdout + installed.stderr)
    if installed.returncode:
        print((installed.stdout + installed.stderr)[-6000:])
        raise RuntimeError("Dependency installation failed. See installer.log; do not continue.")
subprocess.run([PYTHON, "-m", "pip", "check"], check=True)
if SAVE_CHECKPOINTS_TO_DRIVE:
    from google.colab import drive
    drive.mount("/content/drive")
    OUTPUT = Path("/content/drive/MyDrive/WebQA-Cloud")
else:
    OUTPUT = ROOT / "outputs"
OUTPUT.mkdir(parents=True, exist_ok=True)
print("Setup complete. Colab's existing Python, Torch, and CUDA packages were not replaced.")
print("Output/checkpoint folder:", OUTPUT)
''', '1. Set up the notebook environment')

markdown('''Step 2 downloads the engine and selected model the first time. Allow several minutes and at least 15 GB of free runtime storage. The setup verifies the engine checksum, dependencies, structured model output, and actual GPU memory use. It stops with an explanation if any check fails. Choose the smaller model if GPU memory is limited.
''')
code('''MODEL = "qwen2.5-coder:7b" #@param ["qwen2.5-coder:7b", "qwen2.5-coder:3b"]
SECONDS_PER_JOB = 1200 #@param [600, 1200] {type:"raw"}
subprocess.run([PYTHON, str(ROOT / "runtime_setup.py"), str(ROOT), "--model", MODEL],
               env=ENV, check=True)
PREFLIGHT = json.loads((ROOT / "preflight.json").read_text())
for name in ["preflight.json", "environment-freeze.txt", "requirements-colab.lock", "compatibility-manifest.json", "pip-check.txt", "installer.log"]:
    (OUTPUT / name).write_bytes((ROOT / name).read_bytes())
print("Ready for a request from your local dashboard.")
''', '2. Prepare and verify the GPU model')

code('''from google.colab import files

uploads = files.upload()
if len(uploads) != 1:
    raise ValueError("Upload exactly one .webqa-request.json file exported by WebQA.")
filename, data = next(iter(uploads.items()))
if not filename.endswith(".webqa-request.json") or len(data) > 2_000_000:
    raise ValueError("Choose a WebQA request JSON file smaller than 2 MB.")
REQUEST_FILE = ROOT / "uploaded-request.json"
REQUEST_FILE.write_bytes(data)
subprocess.run([PYTHON, "-c", "from webqa.cloud_protocol import read_json,validate_request; import sys; validate_request(read_json(sys.argv[1])); print('Request validated.')", str(REQUEST_FILE)], env=ENV, check=True)
REQUEST = json.loads(REQUEST_FILE.read_text())
print("Website:", REQUEST["website"])
print("Task:", REQUEST["operation"], "| Jobs:", len(REQUEST["jobs"]))
print("No website tests will be executed in Colab.")
''', '3. Upload your exported request')

code('''PREFLIGHT = json.loads((ROOT / "preflight.json").read_text())
if PREFLIGHT.get("model") != MODEL or PREFLIGHT.get("gpu_probe") != "passed":
    raise RuntimeError("Run step 2 successfully for the selected model before continuing.")
subprocess.run([PYTHON, "-m", "webqa.cloud_worker", str(REQUEST_FILE), "--model", MODEL,
               "--out", str(OUTPUT), "--timeout", str(SECONDS_PER_JOB),
               "--provenance", str(ROOT / "preflight.json")], env=ENV, check=True)
RESULT_FILE = OUTPUT / REQUEST["id"] / (REQUEST["id"] + ".webqa-result.json")
if not RESULT_FILE.is_file():
    raise RuntimeError("No complete result file was produced. Review the error above.")
print("Your result is ready. Run step 5 to download it.")
''', '4. Process the request (rerun to resume completed jobs)')

code('''from google.colab import files

if "RESULT_FILE" not in globals() or not RESULT_FILE.is_file():
    raise RuntimeError("Complete step 4 before downloading a result.")
# Revalidate against the currently uploaded request; an old download cannot masquerade as new work.
subprocess.run([PYTHON, "-c", "from webqa.cloud_protocol import read_json,validate_result; import sys; validate_result(read_json(sys.argv[1]),read_json(sys.argv[2]))", str(RESULT_FILE), str(REQUEST_FILE)], env=ENV, check=True)
files.download(str(RESULT_FILE))
print("Copy the downloaded file into Cloud-Inbox in your local app folder.")
print("In WebQA: Scan inbox → Import and review. For tests: Use these tests → Run AI tests.")
''', '5. Download the result for your local dashboard')

markdown('''## Reuse and troubleshooting

- **Another request, same model:** repeat steps 3–5. You can reuse the notebook for all four tasks: create tests, revise tests, explain failures, and history-based guidance.
- **Interrupted job:** rerun step 4. Completed jobs are checkpointed and schema-validated before reuse. To survive a deleted Colab runtime, enable Drive checkpoints in step 1 before processing; reconnect, rerun steps 1–3 with the same request/model, then step 4.
- **GPU unavailable:** select a GPU runtime. Colab does not guarantee one; retry later or use local Ollama in the dashboard.
- **Model error or timeout:** completed jobs stay saved. Rerun step 4 or choose the smaller model and rerun step 2. A different model needs a new exported request so incompatible checkpoints are not reused.
- **Invalid output:** the notebook stops without producing a complete import file. A fresh attempt may work; if repeated, export a simpler request such as “Create two homepage accessibility checks.” Existing local tests remain unchanged.
- **Website settings or tests changed while Colab worked:** export a fresh request. The dashboard rejects stale results.
- **No files in the inbox:** copy the `.webqa-result.json`, not the request JSON, notebook, ZIP, or a Python file. The dashboard displays the exact inbox path and can open it for you.
- **Duplicate import:** the same result reopens the same proposal. It does not create duplicate tests.

Cloud explanations are advisory and do not change test outcomes. They are based on text evidence, not visual inspection of screenshots. Applying a test proposal does not run it; use **Run AI tests** afterward.

Reference implementation: [Ollama Linux setup](https://docs.ollama.com/linux), [pinned engine release](https://github.com/ollama/ollama/releases/tag/v0.34.1), [Colab FAQ](https://research.google.com/colaboratory/faq.html).
''')

notebook = {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {'colab': {'name': 'WebQA_Cloud_LLM.ipynb', 'provenance': []},
            'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
            'language_info': {'name': 'python', 'version': '3.12'}, 'accelerator': 'GPU'}, 'cells': cells}
for i, cell in enumerate(cells):
    cell['id'] = f'webqa-cell-{i:02}'
path = ROOT / 'notebooks/WebQA_Cloud_LLM.ipynb'
path.write_text(json.dumps(notebook, indent=2), encoding='utf-8')
assets = ROOT / 'src/webqa/assets'
assets.mkdir(exist_ok=True)
shutil.copyfile(path, assets / path.name)
print(path)
