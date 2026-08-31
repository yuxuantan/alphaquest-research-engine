from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from alphaquest.accounts.models import AccountRuleProfileV1


@dataclass(frozen=True)
class ResolvedAccountProfile:
    profile: AccountRuleProfileV1
    path: Path
    sha256: str

    def snapshot(self) -> dict[str, Any]:
        payload = self.profile.model_dump(mode="json", by_alias=True)
        payload["profile_sha256"] = self.sha256
        payload["profile_source_path"] = str(self.path)
        return payload


def _canonical_sha256(profile: AccountRuleProfileV1) -> str:
    encoded = json.dumps(
        profile.model_dump(mode="json", by_alias=True),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AccountProfileCatalog:
    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.root = self.project_root / "config" / "account_profiles"

    def entries(self) -> list[ResolvedAccountProfile]:
        entries: list[ResolvedAccountProfile] = []
        seen: set[tuple[str, str]] = set()
        for path in sorted(self.root.rglob("*.yaml")) if self.root.is_dir() else []:
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                # YAML transports dates and timestamps as either native values or
                # strings depending on quoting.  Coerce only at this file boundary;
                # the resulting model remains strict everywhere else.
                profile = AccountRuleProfileV1.model_validate(raw, strict=False)
            except Exception as exc:
                raise ValueError(f"invalid account profile {path}: {exc}") from exc
            key = (profile.profile_id, profile.version)
            if key in seen:
                raise ValueError(f"duplicate account profile identity: {profile.profile_id}@{profile.version}")
            seen.add(key)
            entries.append(ResolvedAccountProfile(profile, path.resolve(), _canonical_sha256(profile)))
        return entries

    def resolve(self, profile_id: str, version: str | None = None) -> ResolvedAccountProfile:
        matches = [
            item
            for item in self.entries()
            if item.profile.profile_id == profile_id and (version is None or item.profile.version == version)
        ]
        if not matches:
            suffix = f"@{version}" if version else ""
            raise ValueError(f"unknown governed account profile: {profile_id}{suffix}")
        if version is None:
            matches.sort(key=lambda item: (item.profile.effective_from, item.profile.version), reverse=True)
        if len(matches) > 1 and version is not None:
            raise ValueError(f"ambiguous governed account profile: {profile_id}@{version}")
        selected = matches[0]
        if selected.profile.provenance.verification_status in {"stale", "needs_manual_review"}:
            raise ValueError(f"account profile is not eligible for new assessments: {profile_id}@{selected.profile.version}")
        return selected

    def list(self, *, novice_only: bool = True) -> list[dict[str, Any]]:
        rows = []
        for item in self.entries():
            profile = item.profile
            if novice_only and not profile.novice_visible:
                continue
            rows.append(
                {
                    "profile_id": profile.profile_id,
                    "version": profile.version,
                    "name": profile.name,
                    "description": profile.description,
                    "account_kind": profile.identity.account_kind,
                    "provider": profile.identity.provider,
                    "program": profile.identity.program,
                    "nominal_balance": profile.identity.nominal_balance,
                    "effective_from": profile.effective_from.isoformat(),
                    "effective_until": profile.effective_until.isoformat() if profile.effective_until else None,
                    "verification_status": profile.provenance.verification_status,
                    "promotable": profile.promotable,
                    "profile_sha256": item.sha256,
                    "cost_input_required": profile.rules.acquisition.evaluation_price_mode
                    == "assessment_input_required"
                    or profile.rules.acquisition.activation_fee_mode == "assessment_input_required",
                    "evaluation_price_input_required": profile.rules.acquisition.evaluation_price_mode
                    == "assessment_input_required",
                    "activation_fee_input_required": profile.rules.acquisition.activation_fee_mode
                    == "assessment_input_required",
                    "recommended_tests": profile.evaluation_policy.recommended_tests,
                    # Studio receives the complete validated rule contract so a
                    # researcher can inspect the destination-specific gates
                    # without opening repository YAML.  The source path stays
                    # server-side; the canonical profile hash is the browser's
                    # immutable identity.
                    "identity": profile.identity.model_dump(mode="json"),
                    "provenance": profile.provenance.model_dump(mode="json"),
                    "rules": profile.rules.model_dump(mode="json"),
                    "evaluation_policy": profile.evaluation_policy.model_dump(mode="json"),
                }
            )
        return rows


def resolve_account_profile(
    profile_id: str,
    *,
    project_root: str | Path = ".",
    version: str | None = None,
) -> ResolvedAccountProfile:
    return AccountProfileCatalog(project_root).resolve(profile_id, version)


def list_account_profiles(
    project_root: str | Path = ".",
    *,
    novice_only: bool = True,
) -> list[dict[str, Any]]:
    return AccountProfileCatalog(project_root).list(novice_only=novice_only)


__all__ = [
    "AccountProfileCatalog",
    "ResolvedAccountProfile",
    "list_account_profiles",
    "resolve_account_profile",
]
