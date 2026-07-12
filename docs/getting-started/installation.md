# Installation

## Requirements

- Python 3.12 is the CI reference version; the package supports Python 3.10 or newer.
- Local market data is optional for unit tests and the synthetic tutorial.
- Real campaign execution requires the data paths declared by that campaign.

## Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -c constraints/dev.txt -e ".[dev]"
```

Verify the installation:

```bash
make smoke
propstack --help
```

Install dashboard dependencies only when needed:

```bash
python -m pip install -e ".[dev,dashboard]"
```
