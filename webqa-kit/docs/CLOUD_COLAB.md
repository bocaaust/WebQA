# Use Colab for WebQA’s AI tasks

Version 0.4.0 lets you do AI work on a Google Colab GPU and bring the results back to the local dashboard. You do not need Ollama installed on your own computer for this workflow. Your computer still runs the website tests and captures screenshots.

## Upgrade once

1. Stop the old app with Control+C in its launch window.
2. Extract the new WebQA ZIP into a new folder.
3. Run that folder’s Setup-WebQA launcher, then its Start-WebQA launcher. On Mac, you can run `bash Setup-WebQA.command` and `bash Start-WebQA.command` from Terminal in that folder.
4. Confirm the app header says **0.4.0**. Keep the **WebQA** data folder in your home folder; it contains saved websites, tests, reports, and the request records needed to import results.

## A. Export work from the dashboard

1. Save or choose a website.
2. Under **Where should AI work?**, choose **Google Colab (file exchange)**.
3. Choose your task:

| Task | What to click |
|---|---|
| Create tests | Choose Create new tests, describe the desired behavior, then Export test request. |
| Change existing tests | Choose Improve existing AI tests, describe the change, then Export test request. |
| Explain test failures | Run a website check locally, then select Export failure explanations. |
| Get guidance from history and review notes | After a local run, select Export learning guidance. |

Your browser downloads a file ending in `.webqa-request.json`. Exporting the file does not upload anything. The request contains your site settings, test expectations, bounded failure text, and relevant history/review notes. Screenshots and full browser traces are excluded. Review the JSON before uploading if your notes contain private information.

## B. Process the request in Colab

1. Download **WebQA_Cloud_LLM.ipynb** using the dashboard’s **Download Colab notebook** button or the separate supplied notebook.
2. Open [Google Colab](https://colab.research.google.com/). Choose **File → Upload notebook** and select that notebook.
3. Choose **Runtime → Change runtime type → T4 GPU**, or another available NVIDIA GPU, and save.
4. Run the five numbered cells using their ▶ buttons:
   - **1 — Set up:** creates an isolated environment. Optional Drive checkpoints let you resume after a Colab runtime is deleted.
   - **2 — Prepare model:** downloads the model and verifies GPU use. Leave the default `qwen2.5-coder:7b`, or select the smaller `qwen2.5-coder:3b` if GPU memory is limited. The first setup downloads the engine and model and can take several minutes.
   - **3 — Upload:** choose the `.webqa-request.json` from your dashboard.
   - **4 — Process:** wait for completion. Completed batches are checkpointed; rerun this cell to resume after an interruption.
   - **5 — Download:** saves a file ending in `.webqa-result.json` to your computer.

No API key is needed. GPU availability and runtime lifetime depend on your Colab allocation. The notebook checks them and stops with instructions if it cannot run. It does not promise unlimited free GPU time. [Colab FAQ](https://research.google.com/colaboratory/faq.html)

## C. Bring the result back

1. Return to WebQA and click **Open inbox folder**. With the supplied launchers, this is **Cloud-Inbox** inside your extracted **webqa-kit** app folder. The dashboard also shows the exact path.
2. Copy the downloaded `.webqa-result.json` into that folder. Do not unzip it or edit it. Do not copy the request file or notebook there.
3. Click **Scan inbox**, then **Import and review** next to your file.
4. For new or revised tests: read the proposal and assumptions, click **Use these tests**, then **Run AI tests**.
5. For failure explanations: the app updates the matching local report and keeps its existing screenshots. For historical guidance: the app displays the imported suggestions.

Importing tests does not apply or run them automatically. Reimporting the same file reopens the same proposal. The original pytest outcomes are not changed by cloud explanations.

## Everyday reuse

You can process another request by repeating notebook steps 3–5 while the same model is ready. You can close the local dashboard while Colab works; reopen it using the same WebQA data folder to import the result. Cloud processing does not require a connection back to your computer.

Keep request/result files until you have confirmed the imported work. Screenshots cannot be added retroactively to an old run that did not capture them. Run a new local check when needed.

## Common messages

| Situation | What to do |
|---|---|
| No GPU available | Select a GPU runtime, try again later, or use local Ollama. |
| Model/GPU preflight fails | Follow the printed message. Try the smaller model or a fresh GPU runtime. Do not skip the preflight. |
| Processing timed out | Rerun cell 4. Completed batches are reused. Start with 1–3 tests for generation. |
| Checkpoint belongs to another model | Export a new request before changing models. |
| No result files in the inbox | Copy the downloaded `.webqa-result.json` into the displayed folder, then Scan inbox again. |
| No matching request on this computer | Use the WebQA data folder that exported the request. Export a fresh request if its records were deleted. |
| Website settings or tests changed after export | Export and process a fresh request; the stale file cannot overwrite newer work. |
| Latest run changed after export | Export explanations for the current run. |
| Invalid generated plan | The app did not apply it. Try a fresh, narrower request describing the intended result. |

## Implementation and validation limits

The exchange uses versioned JSON, request fingerprints, complete-result checks, bounded files, and the same plan compiler used by local AI. Fingerprints associate files with local requests; they are not digital signatures proving model authorship. Imported data is treated as untrusted and cannot supply executable Python. Scope checks, stale-edit checks, and explicit review still apply.

Cloud explanations are batched six failed checks at a time, up to twenty jobs per request. All failed checks within that limit are covered. Historical context is bounded to the fifty cases with the most failures and fifteen recent review notes, with shortened note excerpts. Current managed plans remain complete. Large requests fail with a size message instead of being silently truncated.

The notebook pins Python dependencies in an isolated environment and verifies a pinned Ollama engine download. It leaves Colab’s existing Torch/CUDA Python stack untouched. Setup also saves dependency versions, the engine and model identifiers, and preflight results beside outputs. No tunnel or public inference endpoint is created.

Local tests cover export/import for all four task types, stale results, tampering, duplicate imports, checkpoint recovery, report preservation, actual pytest collection of imported tests, and dashboard DOM behavior. The notebook setup cell and dependency/API probes were executed locally under Python 3.12. A real Colab GPU run, Google upload/download widgets, and real model inference have not been executed in this delivery. Step 2’s strict preflight and one small request provide the installation acceptance check.
