from pathlib import Path

from fastapi.testclient import TestClient

from alphaquest.studio.web import DEFAULT_ASSETS_DIR, UI_RUNTIME, create_app, main


def _assets(root: Path) -> Path:
    assets = root / "web-assets"
    compiled = assets / "assets"
    compiled.mkdir(parents=True)
    (assets / "index.html").write_text(
        "<!doctype html><html><body><div id='root'>studio shell</div></body></html>",
        encoding="utf-8",
    )
    (compiled / "app.js").write_text("window.alphaquest = true;", encoding="utf-8")
    return assets


def test_web_runtime_reports_health_and_serves_spa_history_fallback(tmp_path: Path) -> None:
    client = TestClient(create_app(project_root=tmp_path, assets_dir=_assets(tmp_path)))

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "ui_runtime": UI_RUNTIME,
        "assets_ready": True,
    }
    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["x-frame-options"] == "DENY"
    assert health.headers["referrer-policy"] == "no-referrer"
    assert "script-src 'self'" in health.headers["content-security-policy"]
    assert "connect-src 'self'" in health.headers["content-security-policy"]

    index = client.get("/campaigns/example/results")
    assert index.status_code == 200
    assert "studio shell" in index.text
    assert index.headers["cache-control"] == "no-cache, no-store, must-revalidate"

    script = client.get("/assets/app.js")
    assert script.status_code == 200
    assert script.text == "window.alphaquest = true;"


def test_unknown_api_path_is_not_masked_by_spa_fallback(tmp_path: Path) -> None:
    client = TestClient(create_app(project_root=tmp_path, assets_dir=_assets(tmp_path)))

    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown Research Studio API route"


def test_web_runtime_rejects_untrusted_host_with_security_headers(tmp_path: Path) -> None:
    client = TestClient(create_app(project_root=tmp_path, assets_dir=_assets(tmp_path)))

    rejected = client.get("/healthz", headers={"Host": "research-studio.example"})
    localhost = client.get("/healthz", headers={"Host": "localhost:8501"})

    assert rejected.status_code == 400
    assert rejected.headers["x-frame-options"] == "DENY"
    assert localhost.status_code == 200


def test_web_runtime_blocks_cross_origin_mutations_before_route_execution(tmp_path: Path) -> None:
    client = TestClient(create_app(project_root=tmp_path, assets_dir=_assets(tmp_path)))

    response = client.post(
        "/api/drafts/predictable_campaign/publish",
        headers={
            "Origin": "https://attacker.example",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        content=b"",
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "cross_origin_mutation_blocked"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_web_runtime_allows_loopback_origins_and_originless_local_clients(tmp_path: Path) -> None:
    client = TestClient(create_app(project_root=tmp_path, assets_dir=_assets(tmp_path)))

    originless = client.post(
        "/api/drafts",
        json={"campaign_id": "originless", "title": "Originless local client", "instrument": "ES"},
    )
    loopback = client.post(
        "/api/drafts",
        headers={"Origin": "http://127.0.0.1:8501"},
        json={"campaign_id": "loopback", "title": "Loopback browser", "instrument": "NQ"},
    )
    local_dev = client.post(
        "/api/drafts",
        headers={"Origin": "http://localhost:5173"},
        json={"campaign_id": "local_dev", "title": "Local development browser", "instrument": "ES"},
    )
    safe_read = client.get("/healthz", headers={"Origin": "https://attacker.example"})

    assert originless.status_code == 201
    assert loopback.status_code == 201
    assert local_dev.status_code == 201
    assert safe_read.status_code == 200


def test_missing_compiled_assets_fail_health_and_show_admin_action(tmp_path: Path) -> None:
    client = TestClient(create_app(project_root=tmp_path, assets_dir=tmp_path / "missing-assets"))

    health = client.get("/healthz")
    shell = client.get("/")

    assert health.status_code == 503
    assert health.json() == {
        "status": "not_ready",
        "ui_runtime": UI_RUNTIME,
        "assets_ready": False,
    }
    assert shell.status_code == 503
    assert "Ask the administrator to reinstall" in shell.text


def test_web_runtime_rejects_non_local_bind_address() -> None:
    try:
        main(["--host", "0.0.0.0"])
    except ValueError as exc:
        assert "local workstation" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("non-local Studio bind was accepted")


def test_committed_react_bundle_is_offline_responsive_and_accessible() -> None:
    index = (DEFAULT_ASSETS_DIR / "index.html").read_text(encoding="utf-8")
    scripts = sorted((DEFAULT_ASSETS_DIR / "assets").glob("*.js"))
    styles = sorted((DEFAULT_ASSETS_DIR / "assets").glob("*.css"))

    assert len(scripts) == 1
    assert len(styles) == 1
    assert "https://" not in index
    assert "http://" not in index
    assert "<html lang=\"en\">" in index
    assert "name=\"viewport\"" in index
    assert not list((DEFAULT_ASSETS_DIR / "assets").glob("*.map"))

    css = styles[0].read_text(encoding="utf-8")
    compact_css = css.replace(" ", "")
    assert ":focus-visible" in css
    assert "@media(max-width:900px)" in compact_css
    assert "@media(max-width:680px)" in compact_css
    assert "@media(prefers-reduced-motion:reduce)" in compact_css
    assert "font-size:16px" in compact_css

    javascript = scripts[0].read_text(encoding="utf-8")
    assert "Backtests are evidence" in javascript
    assert "NEEDS MANUAL REVIEW" in javascript
    assert "candidate strategy only" in javascript
