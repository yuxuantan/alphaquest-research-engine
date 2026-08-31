from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import socket
from threading import Thread
import time

import pandas as pd
import pytest
import uvicorn

from alphaquest.studio.data_import import DataImportSpec, DatasetImporter
from alphaquest.studio.web import create_app


LONG_TEXT = (
    "This declaration is deliberately substantive and records a falsifiable completed-bar economic mechanism "
    "before any performance result is available to the researcher or the application."
)


def _dataset(root: Path) -> None:
    source = root / "administrator-bars.csv"
    # Full publication must have enough declared history for the frozen
    # 24-month selection plus terminal 6-month acceptance calendar.
    session_starts = pd.bdate_range("2023-01-02", "2026-01-16")
    timestamps = pd.DatetimeIndex(
        [
            timestamp
            for session_start in session_starts
            for timestamp in pd.date_range(
                f"{session_start.date()} 09:30:00", periods=60, freq="min"
            )
        ]
    )
    prices = [
        5000.0 + bar_index * 0.25
        for _session_start in session_starts
        for bar_index in range(60)
    ]
    pd.DataFrame(
        {
            "timestamp": timestamps.astype(str),
            "open": prices,
            "high": [item + 1 for item in prices],
            "low": [item - 1 for item in prices],
            "close": [item + 0.25 for item in prices],
            "volume": [1000 + index for index in range(len(timestamps))],
        }
    ).to_csv(source, index=False)
    DatasetImporter(root).import_file(
        source,
        DataImportSpec(
            dataset_id="governed_es_1m",
            symbol="ES",
            timeframe="1m",
            timezone="America/New_York",
            timestamp_semantics="bar_open",
            roll_policy="single_contract",
            timestamp_column="timestamp",
            open_column="open",
            high_column="high",
            low_column="low",
            close_column="close",
            volume_column="volume",
            single_contract_confirmed=True,
        ),
    )


@contextmanager
def _server(root: Path):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(2048)
    port = int(sock.getsockname()[1])
    server = uvicorn.Server(
        uvicorn.Config(create_app(project_root=root), log_level="error", lifespan="off")
    )
    thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("Studio test server did not start")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()


def _browser(playwright):
    default = Path(playwright.chromium.executable_path)
    system_chrome = Path(
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    executable = default if default.is_file() else system_chrome
    if not executable.is_file():
        pytest.skip("a Playwright Chromium or system Chrome executable is required")
    return playwright.chromium.launch(headless=True, executable_path=str(executable))


def test_fresh_researcher_completes_six_decisions_and_all_governance_gates_without_terminal_yaml_or_python(
    tmp_path: Path,
) -> None:
    playwright_module = pytest.importorskip("playwright.sync_api")
    _dataset(tmp_path)
    with _server(tmp_path) as base_url, playwright_module.sync_playwright() as playwright:
        browser = _browser(playwright)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.set_default_timeout(20_000)

        page.goto(f"{base_url}/research/new")
        page.get_by_label("Research title").fill("Automated no-code edge")
        page.get_by_role(
            "checkbox",
            name="I confirm this performance and risk objective before AI source research or PnL.",
        ).check()
        page.get_by_role("button", name="Create research draft").click()
        page.wait_for_url("**/design/1")

        page.get_by_label("Economic edge family").fill("automated_completed_bar_edge")
        page.get_by_label("Falsifiable hypothesis").fill(LONG_TEXT)
        page.get_by_label("Expected causal mechanism").fill(LONG_TEXT)
        page.get_by_label("Expected holding horizon").fill("Next bar open through same-session flatten")
        page.get_by_label("Known failure modes").fill(LONG_TEXT)
        page.get_by_label("Source title").fill("Completed-bar price discovery study")
        page.get_by_label("Authors").fill("A. Researcher")
        page.get_by_label("Source link (or provide a DOI above)").fill(
            "https://example.test/completed-bars"
        )
        page.get_by_label("Why this source may apply to ES").fill(LONG_TEXT)
        page.get_by_label("Market behavior").fill(
            "Completed auction imbalance persists into the following bar"
        )
        page.get_by_label("Signal inputs").fill("completed close, prior opening range")
        page.get_by_label("Market context").fill("ES regular trading session")
        page.get_by_role("button", name="Save and continue").click()
        page.wait_for_url("**/design/2")

        page.get_by_text("This idea is economically distinct", exact=True).click()
        page.get_by_label("Substantive economic distinction").fill(LONG_TEXT)
        page.get_by_role("button", name="Save and choose data").click()
        page.wait_for_url("**/design/3")

        page.locator(".dataset-choice").first.click()
        page.get_by_role("button", name="Save and continue").click()
        page.wait_for_url("**/design/4")

        page.get_by_text(
            "I reviewed the dataset’s contract roll policy", exact=True
        ).click()
        page.get_by_role("button", name="Save and continue").click()
        page.wait_for_url("**/design/5")

        page.get_by_text(
            "This recipe represents the frozen hypothesis", exact=True
        ).click()
        page.get_by_role("button", name="Save mechanics lane").click()
        page.wait_for_url("**/design/6")

        page.locator(".matrix-row").first.click()
        page.get_by_text(
            "I confirm this mechanic before performance testing", exact=True
        ).click()
        page.get_by_role("button", name="Save the confirmed initial variant").click()
        page.wait_for_url("**/design/7")

        page.get_by_text("Freeze this research protocol", exact=True).click()
        page.get_by_role(
            "button", name="Review and publish governed campaign"
        ).click()
        page.wait_for_url("**/automated_no_code_edge/overview", timeout=60_000)

        page.get_by_text("Sequential variant stage matrix", exact=True).wait_for()
        assert page.locator(".stage-row").count() == 2
        page.get_by_role("tab", name="History", exact=True).click()
        follow_up = page.get_by_role("button", name="Create explicit follow-up")
        assert follow_up.is_enabled()
        page.get_by_text("Recovery follow-ups remain available", exact=True).wait_for()
        assert not page_errors
        assert (tmp_path / "research/campaigns/active/automated_no_code_edge/campaign.yaml").is_file()
        browser.close()
