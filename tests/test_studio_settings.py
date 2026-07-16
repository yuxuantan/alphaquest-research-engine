from alphaquest.studio.settings import StudioSettings, load_settings, save_settings


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
