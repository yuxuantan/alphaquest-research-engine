# Applications

Interactive applications consume generated evidence but do not define strategy or engine semantics.

- `validation_dashboard.py`: Streamlit mechanics-review application backed by exported validation artifacts.

Reusable dashboard logic belongs under `src/alphaquest/dashboard/`. Application files should remain thin launch surfaces.
