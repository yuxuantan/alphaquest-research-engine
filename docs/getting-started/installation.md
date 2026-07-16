# Installation

## Requirements

- Python 3.12 is the CI reference version; the package supports Python 3.10 or newer.
- Local market data is optional for unit tests and the synthetic tutorial.
- Real campaign execution requires the data paths declared by that campaign.

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

The OpenAI drafting adapter is optional. Studio works without a key. If enabled, the key is stored in the operating-system keychain; no credential is written to the workspace.
