import pytest

from propstack.strategy_modules.entry import all_entry_module_metadata, entry_module_metadata


def test_entry_registry_exposes_metadata_for_every_registered_module():
    metadata = all_entry_module_metadata()

    assert "calendar_session_bias" in metadata
    assert all(item.name == name for name, item in metadata.items())
    assert all(item.module_type == "entry" for item in metadata.values())


def test_calendar_session_bias_declares_required_columns():
    metadata = entry_module_metadata("calendar_session_bias")

    assert metadata.required_columns == frozenset({"is_rth"})
    assert metadata.decision_timing == "bar_close"


def test_entry_module_metadata_rejects_unknown_module():
    with pytest.raises(ValueError, match="Unknown entry module"):
        entry_module_metadata("not_registered")
