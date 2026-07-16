"""Local, non-authoritative Research Studio preferences."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from alphaquest.research.storage import load_storage_layout


class StudioSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, strict=True)

    reviewer_identity: str = ""
    openai_model: str = ""
    default_commission_per_contract: float = Field(default=2.5, ge=0)
    default_slippage_ticks: float = Field(default=1.0, ge=0)
    default_initial_balance: float = Field(default=150_000.0, gt=0)
    default_flatten_time: str = "15:55:00"
    privacy_notice_acknowledged: bool = False
    openai_retention_notice: str = Field(
        default=(
            "Organization-specific OpenAI API retention controls have not been recorded. "
            "Default endpoint retention policies may apply; ask your administrator."
        ),
        min_length=20,
    )
    openai_zero_data_retention_enabled: bool = False


def load_settings(*, project_root: str | Path = ".") -> StudioSettings:
    path = settings_path(project_root=project_root)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return StudioSettings()
    try:
        return StudioSettings.model_validate(value)
    except ValueError:
        return StudioSettings()


def save_settings(settings: StudioSettings | dict[str, Any], *, project_root: str | Path = ".") -> Path:
    value = settings if isinstance(settings, StudioSettings) else StudioSettings.model_validate(settings)
    path = settings_path(project_root=project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def settings_path(*, project_root: str | Path = ".") -> Path:
    layout = load_storage_layout(project_root)
    runtime = getattr(layout, "studio_runtime_root", layout.run_store_root / "studio-runtime")
    return Path(runtime) / "settings.json"
