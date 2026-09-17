# Start here — using WebQA

WebQA checks public websites and explains what needs attention. After setup, you can use its local app without editing code, JSON, or test files.

## Upgrade from v0.2.x

1. Stop the old app by pressing Control+C in its launch window.
2. Extract the new ZIP into a new folder. Keep the old folder until you confirm the update works.
3. Run the new folder’s Setup-WebQA launcher once. On Mac, open Terminal, type `cd ` (including the space), drag the new `webqa-kit` folder into Terminal, press Return, then run `bash Setup-WebQA.command`.
4. Launch the new folder’s Start-WebQA launcher (`bash Start-WebQA.command` on Mac). The header should say **0.3.0**.
5. Saved websites and tests in your home folder’s **WebQA** folder remain available. Do not delete that folder. Ollama and downloaded models do not need reinstalling.
6. Select your existing model, choose a ten- or twenty-minute AI wait, and first request 1–3 tests. Run a new website check to capture screenshots; old runs cannot gain screenshots retroactively.

## One-time setup

A technical helper should do this once on the computer you will use:

1. Install Python 3.11 or later and extract the complete WebQA folder.
2. On Windows, double-click **Setup-WebQA.bat**. On macOS, run **Setup-WebQA.command**. If macOS does not recognize the executable flag after extracting, your helper can run `bash Setup-WebQA.command` from the folder. Both install the package and its Chromium browser.
3. For Linux, use the README's virtual environment setup and `python -m playwright install --with-deps chromium`.
4. AI features are optional. Install and start [Ollama](https://ollama.com/download), then install a local model that supports structured JSON output. The helper should choose a model that fits the computer and verify it can answer a request before handing over the app. WebQA discovers installed models automatically; it does not download models or create paid accounts.
5. Open WebQA and verify a normal website check, then one AI proposal if AI is enabled. This delivery includes offline validation; it does not replace this installation acceptance check.

For a technical helper, the equivalent setup is:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install .
python -m playwright install chromium
webqa ui
```

On Windows, activation is `.venv\Scripts\Activate.ps1`. Model installation is a separate one-time step using Ollama's interface or `ollama pull MODEL_NAME`. Choose an installed model in WebQA; no model name must be typed during ordinary use. Local inference speed and memory requirements depend on that model and the computer. The default AI wait time is ten minutes. Choose five, ten, or twenty minutes in the app. Loading a model for the first time may be slow. Requests stream progress. Refreshing the browser reconnects to a running task as long as the launch window stays open. Requests have a bounded output size; start by asking for 1–3 tests.

## Open the app

On Windows, double-click **Start-WebQA.bat**. On macOS, open **Start-WebQA.command**. Your browser opens the app. Keep its launch window open while working. Closing it stops the app. The app only listens on this computer at `http://127.0.0.1:8765`.

Your saved websites, tests, reports, and learning history live in the **WebQA** folder inside your user/home folder. They remain available when you reopen the app. Select a saved website to reopen its latest completed result. Your last selected website and model are remembered in this browser.

## Check a website

1. Enter its main address, such as `https://www.capitaltg.com`, and select **Save website**.
2. CTG has a prepared set of 43 checks. A new website starts with homepage accessibility checks. To include another page, select **Add a page**, enter its address (for example `/contact`), and optionally enter its expected heading in the separate field. Use **Remove this page** to undo an addition. No special formatting is needed.
3. Choose **Accessibility**, **All configured checks**, or **Small-screen checks**. **Essential visitor journeys** needs a prepared profile with business expectations.
4. Select **Check website** and wait for the result. Only one task runs at a time.
5. When a model is selected, **Explain failures automatically after a check** adds plain-language explanations to failed checks. The app saves results first and shows progress while AI works. You can switch this option off.
6. Read the result: **passed**, **needs attention**, **could not run**, or **not checked**. Select **Open full report** for details. Each failed check includes **What happened**, **Why it matters**, and **What to do**. A failing check can indicate a website defect, an outdated expectation, or a setup problem; investigate before changing the test. Screenshots show the page and up to three affected elements where available. **Download report with screenshots** saves a portable HTML report that you can share with your website team.

Checks visit only included public pages and use ordinary browser requests. They do not submit contact forms or applications. A clean result does not establish full accessibility conformance.

## Ask AI to create tests

1. Select your website and an installed model.
2. Select **Create new tests**.
3. Describe what visitors should be able to do and the expected result. Include visible button or field names if you know them. Add any destination pages to the website first.
4. Select **Prepare tests**. Review the proposed scenarios and their assumptions. The code changes are available in an expandable section.
5. Select **Use these tests** to save the proposal, or **Keep current tests** to discard it.
6. Select **Run AI tests** to check their behavior on the real site. Preparing and applying tests do not execute them automatically.

Example request: “Check that a visitor can open Contact from the main menu, reach the contact page, and find the Email Address and Message fields. Do not send the form.” The assistant needs actual labels or reviewed assumptions; it does not independently discover every page.

## Improve existing tests

Choose **Improve existing AI tests**, describe the intended change, and select **Prepare tests**. The assistant receives the existing test plan, a compact site profile, previous outcomes, and review notes. Review added, changed, and removed scenarios before selecting **Use these tests**. Previous files are backed up with the proposal. A stale proposal cannot overwrite a more recent edit.

This workflow supports tests managed by WebQA. Arbitrary third-party Python test files need a developer to translate them into the supported plan format.

## Help the assistant learn

After a run, use **Explain latest result** to add or retry AI explanations in the illustrated report. The text model receives bounded failure evidence; it does not visually analyze the screenshots. If it cannot complete, rule-based explanations and screenshots remain available. In **Teach the assistant what you confirmed**, select a check, record whether you confirmed or rejected the finding, and describe the verified reason. These notes inform future guidance and proposals for that website. They do not train model weights or change pass/fail decisions.

Use facts and keep private information out of requests and review notes. Test failures alone do not tell the assistant what the correct behavior should be.

The app includes **Help with your next step**, with expandable explanations and troubleshooting. Buttons become available as their prerequisites are ready: save a website first; AI requires a local model; running AI tests requires an applied proposal.

## If something needs attention

| Message or situation | What to do |
|---|---|
| No local model is ready | Start Ollama, then select Refresh models. Ask your setup helper to install a model if the list stays empty. Website checks still work. |
| AI request times out | Select a longer AI wait time, choose a smaller installed model, or ask for only 1–3 tests. If it still fails, share the exact message plus the model name and Mac memory with your setup helper. Existing tests stay unchanged; completed reports remain available. |
| No checks matched | Choose All configured checks or Accessibility. New website profiles have no business smoke tests yet. |
| Browser executable missing | Ask the helper to rerun browser installation from the setup instructions. |
| Managed pytest profile changed | Describe the intended change using Improve existing AI tests, review it, and apply the new proposal. |
| Website redirects outside its configured address | Use the site's final canonical address, including `www` if required, and include its public destination pages. |
| App address already in use | Use the existing WebQA window, or ask your helper to start `webqa ui --port 8766`. |

The package is ready to place in a GitHub repository. GitHub publishing, hosted accounts, unattended scheduling, and a cloud dashboard are separate deployment tasks.
