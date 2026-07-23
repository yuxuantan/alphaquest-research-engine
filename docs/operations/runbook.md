# Operations Runbook

## Daily Research

The novice workflow runs entirely in Research Studio. Operators can inspect the durable local processes and queue with:

```bash
alphaquest studio status
```

The default `ui_runtime` is `react-fastapi`. A healthy Studio has both `ui_healthy: true` and `worker_running: true`; operational process health remains separate from every scientific verdict. The service binds only to `127.0.0.1` or `localhost`, serves committed assets, and does not require Node.js or an external web host.

Lifecycle commands are:

```bash
make studio
make studio-status
make studio-stop
```

The launcher opens a browser only after `/healthz` verifies the React bundle and the durable worker is alive. Closing the browser does not stop the pair. Use the reported `log_path` and `worker_log_path` when startup or a queued operation fails.

Expert registry commands remain:

```bash
make research-workspace
alphaquest research status
alphaquest research search --verdict NEEDS_MANUAL_REVIEW
```

## Before A Run

```bash
alphaquest campaign validate <campaign_id>
make smoke
```

Complete the deterministic mechanics export and hash-bound `approved_for_testing` decision before invoking the staged performance command.

## After A Run

```bash
make research-workspace
alphaquest campaign show <campaign_id>
alphaquest campaign show <campaign_id> --explain --run <run_uid> --write-card
make qualify
```

## Failure Handling

- Preserve the failed run and its effective config.
- Diagnose the first failed stage.
- Do not use later stale folders as evidence.
- Do not retune on acceptance data.
- Record an explicitly authorized rescue as a new attempt and run ID.

## Studio Process Recovery

If status reports `stale_state: true`, inspect the two reported logs, then use the managed lifecycle rather than killing an unverified PID:

```bash
alphaquest studio stop
alphaquest studio start --background --no-browser
alphaquest studio status
```

A missing or invalid committed web bundle makes `/healthz` fail and prevents the launcher from claiming Studio is healthy. Reinstall the workspace or have a frontend developer rebuild and commit the assets; do not run a Vite development server as a researcher workaround.

The retired Streamlit Studio is available only for a time-bounded migration diagnosis:

```bash
alphaquest studio start --legacy-streamlit
```

It requires the optional `dashboard` dependencies. Switching back to the default launcher cleanly replaces the managed legacy UI/worker pair. The `validation-dashboard` and `validation-dashboard-sample` Make targets remain expert Streamlit/Plotly inspection tools and do not change the novice Studio runtime.

## Rebuilding The Studio Interface

Only frontend developers need Node.js. From a checkout with `studio-ui` dependencies installed:

```bash
make studio-ui-check
make studio-ui-build
python -m pytest -q tests/test_studio_web.py tests/test_studio_web_api.py tests/test_studio_launcher.py
```

The build target writes runtime assets to `src/alphaquest/studio/web_assets/`. Review and commit those files with the corresponding TypeScript source. Administrator installation and production launch never run npm.
