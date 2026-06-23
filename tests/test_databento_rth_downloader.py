from propstack.data.databento_rth_downloader import DownloadConfig
from propstack.data.databento_rth_downloader import build_download_plan
from propstack.data.databento_rth_downloader import filter_available_sessions
from propstack.data.databento_rth_downloader import iter_rth_sessions
from propstack.data.databento_rth_downloader import session_output_path
from propstack.data.databento_rth_downloader import write_manifest


def test_iter_rth_sessions_builds_weekday_timezone_aware_windows():
    sessions = iter_rth_sessions("2026-03-06", "2026-03-10")

    assert [session.session_date.isoformat() for session in sessions] == [
        "2026-03-06",
        "2026-03-09",
        "2026-03-10",
    ]
    assert sessions[0].start.isoformat() == "2026-03-06T09:30:00-05:00"
    assert sessions[-1].start.isoformat() == "2026-03-10T09:30:00-04:00"
    assert sessions[-1].end.isoformat() == "2026-03-10T16:00:00-04:00"


def test_iter_rth_sessions_can_include_weekends():
    sessions = iter_rth_sessions("2026-03-07", "2026-03-08", weekdays_only=False)

    assert [session.session_date.isoformat() for session in sessions] == [
        "2026-03-07",
        "2026-03-08",
    ]


def test_filter_available_sessions_keeps_available_and_degraded_dates():
    sessions = iter_rth_sessions("2026-06-01", "2026-06-05")
    filtered = filter_available_sessions(
        sessions,
        [
            {"date": "2026-06-01", "condition": "available"},
            {"date": "2026-06-02", "condition": "degraded"},
            {"date": "2026-06-03", "condition": "missing"},
            {"date": "2026-06-04", "condition": None},
        ],
    )

    assert [session.session_date.isoformat() for session in filtered] == [
        "2026-06-01",
        "2026-06-02",
    ]


def test_session_output_path_and_download_plan_skip_existing_file(tmp_path):
    config = DownloadConfig(output_dir=tmp_path)
    sessions = iter_rth_sessions("2026-06-01", "2026-06-02")
    existing = session_output_path(config, sessions[0])
    existing.write_bytes(b"already downloaded")

    assert existing.name == "glbx-mdp3-20260601.rth.trades.dbn.zst"
    plan = build_download_plan(sessions, config)

    assert [session.session_date.isoformat() for session in plan] == ["2026-06-02"]


def test_session_output_path_uses_schema_specific_suffix_for_tbbo(tmp_path):
    config = DownloadConfig(output_dir=tmp_path, schema="tbbo")
    session = iter_rth_sessions("2026-06-01", "2026-06-01")[0]

    path = session_output_path(config, session)

    assert path.name == "glbx-mdp3-20260601.rth.tbbo.dbn.zst"
    assert path.match("*.tbbo.dbn.zst")


def test_download_plan_force_keeps_existing_file(tmp_path):
    config = DownloadConfig(output_dir=tmp_path, force=True)
    sessions = iter_rth_sessions("2026-06-01", "2026-06-01")
    session_output_path(config, sessions[0]).write_bytes(b"already downloaded")

    assert build_download_plan(sessions, config) == sessions


def test_write_manifest_creates_json(tmp_path):
    config = DownloadConfig(output_dir=tmp_path / "raw")
    sessions = iter_rth_sessions("2026-06-01", "2026-06-01")
    manifest = tmp_path / "manifest.json"

    write_manifest(
        manifest,
        config=config,
        requested_sessions=sessions,
        planned_sessions=sessions,
        cost_estimate={"estimated_cost": 1.23},
    )

    text = manifest.read_text()
    assert '"symbols": "ES.FUT"' in text
    assert '"estimated_cost": 1.23' in text
