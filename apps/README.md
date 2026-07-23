# Applications

Interactive applications call reusable engine services; they do not replace the authoritative YAML, simulator, staged runner, or immutable evidence contracts.

- The primary novice Research Studio is the committed React application served by `alphaquest studio` through `alphaquest.studio.web`. Its TypeScript source is under `studio-ui/`; its runtime bundle is under `src/alphaquest/studio/web_assets/`.
- `research_studio.py`: retired Streamlit Studio retained only as the explicit `alphaquest studio start --legacy-streamlit` migration fallback. It is not the documented researcher path.
- `validation_dashboard.py`: expert Streamlit/Plotly mechanics-review application backed by exported validation artifacts. It remains available through the `validation-dashboard` Make targets while its reusable evidence logic is shared with Studio.

Reusable workflow services belong under `src/alphaquest/studio/`; reusable expert dashboard logic belongs under `src/alphaquest/dashboard/`. Application files should remain thin launch surfaces.
