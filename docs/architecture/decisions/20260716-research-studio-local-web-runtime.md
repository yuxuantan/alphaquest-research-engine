# Local React/FastAPI Research Studio Runtime

Date: 2026-07-16

## Context

The first no-code Studio proved the governed workflow through Streamlit, but its whole-script reruns, framework-shaped navigation, and large combined page module constrained the desktop-like experience needed by non-coding researchers. The underlying draft, publication, data, approval, job, result, and recovery services were already framework-neutral Python contracts.

The application remains a single-user, local-workstation tool. Adding a Node.js server, hosted service, Electron shell, or second research backend at runtime would increase installation and operational risk without improving scientific controls.

## Decision

Research Studio uses a React/TypeScript single-page application as the novice interface and a local FastAPI/Uvicorn process as its same-origin transport and static-file server. The React source lives under `studio-ui/`; its production output is committed under `src/alphaquest/studio/web_assets/` and included as Python package data.

`alphaquest studio` manages the web process and the existing durable Python worker as one local lifecycle. It binds only to loopback, verifies the committed bundle through `/healthz`, opens the browser only after web and worker health pass, and records `ui_runtime: react-fastapi`. Browser state is never authoritative research state.

Node.js and npm are developer build-time tools only. Administrator installation and researcher launch use the committed assets and Python dependencies. The retired Streamlit Studio remains an explicit `--legacy-streamlit` migration fallback; the standalone Streamlit validation dashboard remains an expert evidence-inspection surface.

## Alternatives Considered

- Continue styling Streamlit: lowest migration effort, but retains whole-script reruns and weak control over navigation and interaction design.
- NiceGUI or another Python-rendered web framework: avoids a frontend build tool but provides less control over a complex research workspace and couples view behavior to another server-driven component model.
- Electron or Tauri: provides a native shell but adds a second packaging/runtime system that is unnecessary for a loopback single-user application.
- Hosted React/API service: conflicts with the local-data, single-workstation, offline-first boundary and introduces authentication and data-egress requirements outside V1 scope.

## Consequences

- Researchers get routed, responsive, selectively updated pages while all scientific mutations still pass through governed Python services.
- The repository contains both TypeScript source and generated production assets; changes must update and review both.
- Frontend developers need Node.js, while researchers and operators do not.
- FastAPI/Uvicorn become optional `studio` runtime dependencies.
- HTTP host restrictions, local-only content security policy, no-store API responses, and bundle-aware health are part of the launcher contract.
- Streamlit is no longer the documented novice runtime.

## Migration And Verification

The launcher recognizes legacy process state and cleanly replaces a managed legacy UI/worker pair when the default runtime is requested. CLI names, port 8501, the macOS launcher, SQLite queue, worker, authored definitions, and immutable evidence paths remain unchanged.

Every UI change runs TypeScript checks and tests, rebuilds committed assets, and verifies the FastAPI API/static fallback plus real start/status/stop and orphan-recovery tests. Missing compiled assets fail health instead of silently presenting an incomplete interface.
