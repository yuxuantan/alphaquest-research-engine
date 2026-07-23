# Installation

## Requirements

- Python 3.12 is the CI reference version; the package supports Python 3.10 or newer.
- Local market data is optional for unit tests and the synthetic tutorial.
- Real campaign execution requires the data paths declared by that campaign.
- Node.js is not a researcher or Studio runtime dependency. It is needed only by developers who rebuild the committed React assets.

## One-time administrator setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -c constraints/dev.txt -e ".[dev,studio]"
```

Verify the installation:

```bash
make smoke
alphaquest --help
alphaquest studio status
```

On macOS, the researcher can now double-click `AlphaQuest Studio.command`. The launcher binds only to the local workstation and opens the browser. The same lifecycle is available to an administrator as:

```bash
alphaquest studio start
alphaquest studio status
alphaquest studio stop
```

The default interface is the committed React bundle served by a local FastAPI/Uvicorn process. `alphaquest studio status` reports the UI runtime, HTTP health, worker health, URL, process IDs, and local log paths. The launcher opens the browser only after both the web application and durable worker are healthy. No Node.js process, development server, CDN, or hosted application is involved.

After Python packages have been installed, the normal workflow can run offline against local data. Optional AI drafting is the exception: it is disabled without a key and requires an outbound OpenAI API connection when explicitly used.

The OpenAI drafting adapter is optional. Studio works without a key. If enabled, the key is stored in the operating-system keychain; no credential is written to the workspace.

## Frontend developer setup

The editable React/TypeScript source lives under `studio-ui/`. A current Node.js LTS release and npm are required only when changing that source. Install its development dependencies once, then validate and rebuild:

```bash
npm --prefix studio-ui install
make studio-ui-check
make studio-ui-build
```

`make studio-ui-build` writes the production bundle to `src/alphaquest/studio/web_assets/`. Those generated assets are committed so administrator setup and researcher launch remain Python-only. Commit source and rebuilt assets together, and run the Python launcher tests before handing off a UI change.

## Legacy Streamlit fallback

The retired Streamlit Studio is not part of the novice workflow. During migration, an operator may install the separate dashboard dependencies and launch it explicitly:

```bash
python -m pip install -c constraints/dev.txt -e ".[dashboard]"
alphaquest studio start --legacy-streamlit
```

Starting the default interface while a legacy instance is managed by the launcher cleanly replaces the old UI/worker pair under the same lifecycle lock. The standalone Streamlit validation dashboard remains an expert evidence-inspection surface.
