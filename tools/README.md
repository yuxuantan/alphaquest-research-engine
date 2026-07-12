# Compatibility Tools

Prefer the supported `propstack` CLI and `make help` for routine workflows. Files in this directory remain at stable paths because historical audits and campaign documentation reference them directly.

Run `propstack workspace build`, then use the generated `views/code/tools/` index to browse by purpose. New reusable business logic belongs under `src/propstack/`; a tool script should be a thin compatibility entry point.
