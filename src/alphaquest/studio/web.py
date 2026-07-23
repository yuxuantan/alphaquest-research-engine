"""Local React/FastAPI runtime for AlphaQuest Research Studio.

The compiled web application is package data.  No Node.js process or frontend
build tool is required on a researcher's workstation at runtime.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlsplit


UI_RUNTIME = "react-fastapi"
DEFAULT_ASSETS_DIR = Path(__file__).with_name("web_assets")
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})


def create_app(
    *,
    project_root: str | Path = ".",
    assets_dir: str | Path | None = None,
) -> Any:
    """Create the local-only Studio application.

    Imports stay inside the factory so the core research CLI remains usable
    when the optional ``studio`` dependencies are not installed.
    """

    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    root = Path(project_root).resolve()
    configured_assets = assets_dir or os.environ.get("ALPHAQUEST_STUDIO_ASSETS_DIR") or DEFAULT_ASSETS_DIR
    assets = Path(configured_assets).resolve()
    index_path = assets / "index.html"

    app = FastAPI(
        title="AlphaQuest Research Studio",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.project_root = root
    app.state.web_assets_dir = assets
    app.state.ui_runtime = UI_RUNTIME
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        origin = request.headers.get("origin")
        if request.method.upper() in _UNSAFE_METHODS and not _allowed_mutation_origin(origin):
            response = JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "cross_origin_mutation_blocked",
                        "message": "Research Studio rejected a mutation from a non-local browser origin.",
                    }
                },
            )
        else:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "base-uri 'none'; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "frame-src 'none'; "
            "form-action 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "manifest-src 'self'; "
            "worker-src 'self' blob:"
        )
        if request.url.path == "/healthz" or request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/healthz", include_in_schema=False)
    def health():
        ready = index_path.is_file()
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ok" if ready else "not_ready",
                "ui_runtime": UI_RUNTIME,
                "assets_ready": ready,
            },
        )

    # Workflow routes are registered before the SPA catch-all so unknown API
    # paths fail explicitly instead of being disguised as an HTML response.
    from alphaquest.studio.api import register_api_routes

    register_api_routes(app, root)

    compiled_assets = assets / "assets"
    if compiled_assets.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=compiled_assets, check_dir=True),
            name="studio-assets",
        )

    @app.get("/{requested_path:path}", include_in_schema=False)
    def serve_spa(requested_path: str):
        if requested_path == "api" or requested_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Unknown Research Studio API route")

        if requested_path:
            candidate = (assets / requested_path).resolve()
            try:
                candidate.relative_to(assets)
            except ValueError:
                raise HTTPException(status_code=404, detail="Asset path is outside the Studio bundle") from None
            if candidate.is_file():
                return FileResponse(candidate)

        if not index_path.is_file():
            return HTMLResponse(
                """
                <!doctype html>
                <html lang="en"><head><meta charset="utf-8"><title>AlphaQuest Research Studio</title></head>
                <body><main><h1>Research Studio is not ready</h1>
                <p>The compiled interface is missing. Ask the administrator to reinstall the Studio workspace.</p>
                </main></body></html>
                """.strip(),
                status_code=503,
            )
        return FileResponse(
            index_path,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    return app


def _allowed_mutation_origin(origin: str | None) -> bool:
    """Allow local non-browser clients or an explicit loopback browser origin."""

    if origin is None:
        return True
    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError:
        return False
    return bool(
        parsed.scheme == "http"
        and parsed.hostname in _LOOPBACK_HOSTS
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
        and (port is None or 1 <= port <= 65535)
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local AlphaQuest Research Studio web application.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--log-level", default="warning")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Research Studio binds only to the local workstation")
    if not 1 <= int(args.port) <= 65535:
        raise ValueError("Studio port must be between 1 and 65535")

    import uvicorn

    uvicorn.run(
        create_app(project_root=args.project_root),
        host=args.host,
        port=int(args.port),
        log_level=args.log_level,
        access_log=False,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the launcher
    raise SystemExit(main())
