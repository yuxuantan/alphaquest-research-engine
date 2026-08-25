import json

from alphaquest.studio.settings import StudioSettings, load_settings, save_settings, settings_path


def test_studio_settings_round_trip_under_runtime_root(tmp_path):
    settings = StudioSettings(
        reviewer_identity="Researcher One",
        openai_model="pinned-model",
        openai_retention_notice=(
            "Administrator verified the organization's endpoint retention configuration on 2026-07-15."
        ),
        openai_zero_data_retention_enabled=True,
    )
    path = save_settings(settings, project_root=tmp_path)

    assert "run-store/studio-runtime" in str(path)
    assert load_settings(project_root=tmp_path) == settings


def test_existing_settings_gain_safe_subscription_factory_defaults(tmp_path):
    path = settings_path(project_root=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "reviewer_identity": "Existing Researcher",
                "openai_model": "",
                "default_commission_per_contract": 2.5,
                "default_slippage_ticks": 1.0,
                "default_initial_balance": 150000.0,
                "default_flatten_time": "15:55:00",
                "privacy_notice_acknowledged": False,
                "openai_retention_notice": (
                    "Organization-specific OpenAI API retention controls have not been recorded. "
                    "Default endpoint retention policies may apply; ask your administrator."
                ),
                "openai_zero_data_retention_enabled": False,
            }
        ),
        encoding="utf-8",
    )

    loaded = load_settings(project_root=tmp_path)

    assert loaded.reviewer_identity == "Existing Researcher"
    assert loaded.assistant_mode == "codex_subscription"
    assert loaded.codex_timeout_seconds == 1800
    assert loaded.codex_max_runs_per_day == 12


def test_manual_and_legacy_assistant_modes_round_trip(tmp_path):
    manual = StudioSettings(assistant_mode="manual_only", codex_max_runs_per_day=3)
    save_settings(manual, project_root=tmp_path)
    assert load_settings(project_root=tmp_path) == manual

    legacy = StudioSettings(assistant_mode="legacy_openai_api", openai_model="pinned-model")
    save_settings(legacy, project_root=tmp_path)
    assert load_settings(project_root=tmp_path) == legacy


def test_corrupt_existing_settings_fail_closed_to_manual_mode(tmp_path):
    path = settings_path(project_root=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    assert load_settings(project_root=tmp_path).assistant_mode == "manual_only"
