# Applications

Interactive applications call reusable engine services; they do not replace the authoritative YAML, simulator, staged runner, or immutable evidence contracts.

- `research_studio.py`: primary local no-code workflow for research intake, governed authoring, review, execution, and results.
- `validation_dashboard.py`: Streamlit mechanics-review application backed by exported validation artifacts.

Reusable dashboard logic belongs under `src/alphaquest/dashboard/`. Application files should remain thin launch surfaces.
