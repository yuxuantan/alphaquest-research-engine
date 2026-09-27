from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphaquest.cli import main
from alphaquest.research.development_status import (
    MAX_DEPENDENCY_DEPTH,
    MAX_SKIP_CHAINS_PER_UNIT,
    MAX_UNITS,
    load_development_status,
    select_development_unit,
)


def _unit(
    unit_id: str,
    status: str,
    *,
    depends_on: list[str] | None = None,
    trigger: dict[str, str] | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "id": unit_id,
        "title": f"Development {unit_id}",
        "declared_status": status,
        "depends_on": depends_on or [],
        "repercussions": [f"Repercussion for {unit_id}."],
        "metadata": metadata or {},
    }
    if trigger is not None:
        value["trigger"] = trigger
    return value


def _roadmap(units: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": "alphaquest.development-roadmap/v1",
        "owner_instruction": {"text": "Continue independent work without consuming skipped artifacts."},
        "scope": {"objective": "Codex-driven research MVP development units."},
        "units": units,
    }


def _write_roadmap(root: Path, payload: dict[str, object], path: str = "config/development_roadmap.json") -> Path:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_resolves_transitive_multipath_skips_and_preserves_declared_history(tmp_path: Path) -> None:
    evidence = tmp_path / "must-not-be-opened"
    evidence.mkdir()
    payload = _roadmap(
        [
            _unit(
                "guard-a",
                "SKIPPED_SAFEGUARD",
                trigger={"reason": "Platform safeguard stopped review.", "evidence_ref": str(evidence)},
            ),
            _unit(
                "guard-b",
                "SKIPPED_SAFEGUARD",
                depends_on=["guard-a"],
                trigger={"reason": "A separate direct safeguard trigger.", "evidence_ref": "ledger:b"},
            ),
            _unit("middle", "VERIFIED", depends_on=["guard-b", "guard-a"]),
            _unit(
                "leaf",
                "IMPLEMENTED",
                depends_on=["middle", "guard-a"],
                metadata={
                    "nested_description": {"kept": True},
                },
            ),
        ]
    )
    payload["units"][-1].update(
        historical_status="Accepted before dependency reassessment.",
        evidence_refs=["commit:abc"],
        arbitrary_description={"also_kept": True},
    )
    _write_roadmap(tmp_path, payload)

    report = load_development_status(tmp_path)
    units = {unit["id"]: unit for unit in report["units"]}

    assert units["guard-b"]["effective_status"] == "SKIPPED_SAFEGUARD"
    assert units["guard-b"]["skip_root_ids"] == ["guard-a", "guard-b"]
    assert units["guard-b"]["skip_root_triggers"] == {
        "guard-a": {"reason": "Platform safeguard stopped review.", "evidence_ref": str(evidence)},
        "guard-b": {"reason": "A separate direct safeguard trigger.", "evidence_ref": "ledger:b"},
    }
    assert units["guard-b"]["skip_dependency_chains"] == [["guard-b"], ["guard-b", "guard-a"]]
    assert units["leaf"]["declared_status"] == "IMPLEMENTED"
    assert units["leaf"]["effective_status"] == "SKIPPED_DEPENDENCY"
    assert units["leaf"]["skip_root_ids"] == ["guard-a", "guard-b"]
    assert units["leaf"]["skip_dependency_chains"] == [
        ["leaf", "guard-a"],
        ["leaf", "middle", "guard-a"],
        ["leaf", "middle", "guard-b"],
        ["leaf", "middle", "guard-b", "guard-a"],
    ]
    assert units["leaf"]["evidence"]["historical_status"].startswith("Accepted")
    assert units["leaf"]["metadata"]["metadata"] == {"nested_description": {"kept": True}}
    assert units["leaf"]["metadata"]["arbitrary_description"] == {"also_kept": True}
    assert evidence.is_dir()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload.update(scope=["not", "an", "object"]), "scope must be a nonempty object"),
        (lambda payload: payload["units"][0].update(depends_on="root"), "depends_on must be an array"),
        (lambda payload: payload["units"][0].update(repercussions=[]), "must contain at least one"),
        (lambda payload: payload["units"][0].update(depends_on=["missing"]), "unknown dependency"),
        (lambda payload: payload["units"][0].update(depends_on=["root", "root"]), "duplicate dependency"),
        (lambda payload: payload["units"][0].update(depends_on=["root"]), "dependency cycle"),
    ],
)
def test_validation_rejects_invalid_types_references_duplicates_and_cycles(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    payload = _roadmap([_unit("root", "PLANNED")])
    mutation(payload)
    _write_roadmap(tmp_path, payload)

    with pytest.raises(ValueError, match=message):
        load_development_status(tmp_path)


def test_direct_safeguard_skip_requires_nonblank_trigger_fields(tmp_path: Path) -> None:
    payload = _roadmap([_unit("blocked", "SKIPPED_SAFEGUARD")])
    _write_roadmap(tmp_path, payload)
    with pytest.raises(ValueError, match="requires a trigger"):
        load_development_status(tmp_path)

    payload["units"][0]["trigger"] = {"reason": " ", "evidence_ref": "ledger:a"}
    _write_roadmap(tmp_path, payload)
    with pytest.raises(ValueError, match="reason must be a nonblank string"):
        load_development_status(tmp_path)


@pytest.mark.parametrize(
    "status",
    ["PLANNED", "IMPLEMENTED", "VERIFIED", "DEFERRED", "SKIPPED_SAFEGUARD"],
)
def test_explicit_null_trigger_is_rejected_for_every_declared_state(
    tmp_path: Path,
    status: str,
) -> None:
    unit = _unit("null-trigger", status)
    unit["trigger"] = None
    _write_roadmap(tmp_path, _roadmap([unit]))

    with pytest.raises(ValueError, match="trigger must be an object"):
        load_development_status(tmp_path)


def test_explicit_null_trigger_returns_cli_schema_error(tmp_path: Path, capsys) -> None:
    unit = _unit("contradiction", "PLANNED")
    unit["trigger"] = None
    _write_roadmap(tmp_path, _roadmap([unit]))

    assert main(["factory", "development-status", "--project-root", str(tmp_path), "--json"]) == 2
    assert "trigger must be an object" in capsys.readouterr().err


def test_trigger_is_exclusive_to_direct_safeguard_skip(tmp_path: Path, capsys) -> None:
    payload = _roadmap(
        [
            _unit(
                "contradiction",
                "PLANNED",
                trigger={"reason": "This contradicts planned state.", "evidence_ref": "opaque:evidence"},
            )
        ]
    )
    _write_roadmap(tmp_path, payload)

    assert main(["factory", "development-status", "--project-root", str(tmp_path), "--json"]) == 2
    assert "trigger is allowed only for SKIPPED_SAFEGUARD" in capsys.readouterr().err


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["owner_instruction"].update(text=" "),
        lambda payload: payload["scope"].update(nested={"description": ""}),
        lambda payload: payload["scope"].update(sequence=["valid", "\t"]),
        lambda payload: payload["scope"].update({" ": "value"}),
    ],
)
def test_governed_descriptive_objects_recursively_reject_blank_strings_and_keys(
    tmp_path: Path,
    mutate,
) -> None:
    payload = _roadmap([_unit("planned", "PLANNED")])
    mutate(payload)
    _write_roadmap(tmp_path, payload)

    with pytest.raises(ValueError, match="blank strings|keys must be nonblank"):
        load_development_status(tmp_path)


def test_governed_descriptive_objects_preserve_non_string_primitives(tmp_path: Path) -> None:
    payload = _roadmap([_unit("planned", "PLANNED")])
    payload["scope"].update(
        enabled=False,
        limit=0,
        ratio=1.5,
        optional=None,
        nested={"values": [True, 2, None]},
    )
    _write_roadmap(tmp_path, payload)

    report = load_development_status(tmp_path)

    assert report["scope"] == payload["scope"]


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e9999", "-1e9999"])
def test_non_json_or_nonfinite_numbers_are_rejected_anywhere_in_payload(
    tmp_path: Path,
    token: str,
) -> None:
    payload = _roadmap([_unit("planned", "PLANNED")])
    payload["units"][0]["arbitrary_metadata"] = {"numeric": "NUMERIC_MARKER"}
    roadmap_path = _write_roadmap(tmp_path, payload)
    raw = roadmap_path.read_text(encoding="utf-8").replace('"NUMERIC_MARKER"', token)
    roadmap_path.write_text(raw, encoding="utf-8")

    with pytest.raises(ValueError, match="non-JSON numeric constant|non-finite JSON number"):
        load_development_status(tmp_path)


def test_finite_numbers_large_integers_bool_and_null_are_preserved_in_metadata(tmp_path: Path) -> None:
    payload = _roadmap([_unit("planned", "PLANNED")])
    metadata = {
        "finite": [-1.25, 0.0, 2.5],
        "large_integer": 10**200,
        "flag": False,
        "optional": None,
    }
    payload["units"][0]["arbitrary_metadata"] = metadata
    _write_roadmap(tmp_path, payload)

    report = load_development_status(tmp_path)

    assert report["units"][0]["metadata"]["arbitrary_metadata"] == metadata


def test_known_optional_unit_descriptions_must_be_nonblank(tmp_path: Path) -> None:
    for key in ("scope", "dependency_note"):
        unit = _unit("planned", "PLANNED")
        unit[key] = " "
        _write_roadmap(tmp_path, _roadmap([unit]))
        with pytest.raises(ValueError, match=rf"{key} must be a nonblank string"):
            load_development_status(tmp_path)


def test_schema_v1_unit_and_dependency_depth_bounds(tmp_path: Path) -> None:
    at_unit_limit = [_unit(f"unit-{index:03d}", "PLANNED") for index in range(MAX_UNITS)]
    _write_roadmap(tmp_path, _roadmap(at_unit_limit))
    assert len(load_development_status(tmp_path)["units"]) == MAX_UNITS

    _write_roadmap(tmp_path, _roadmap([*at_unit_limit, _unit("overflow", "PLANNED")]))
    with pytest.raises(ValueError, match=rf"at most {MAX_UNITS}"):
        load_development_status(tmp_path)

    at_depth_limit = [_unit("depth-001", "PLANNED")]
    for index in range(2, MAX_DEPENDENCY_DEPTH + 1):
        at_depth_limit.append(_unit(f"depth-{index:03d}", "PLANNED", depends_on=[f"depth-{index - 1:03d}"]))
    _write_roadmap(tmp_path, _roadmap(at_depth_limit))
    assert len(load_development_status(tmp_path)["units"]) == MAX_DEPENDENCY_DEPTH

    beyond_depth_limit = [
        *at_depth_limit,
        _unit(
            f"depth-{MAX_DEPENDENCY_DEPTH + 1:03d}",
            "PLANNED",
            depends_on=[f"depth-{MAX_DEPENDENCY_DEPTH:03d}"],
        ),
    ]
    _write_roadmap(tmp_path, _roadmap(beyond_depth_limit))
    with pytest.raises(ValueError, match=rf"maximum dependency depth {MAX_DEPENDENCY_DEPTH}"):
        load_development_status(tmp_path)


def test_schema_v1_skip_chain_bound(tmp_path: Path) -> None:
    root = _unit(
        "root",
        "SKIPPED_SAFEGUARD",
        trigger={"reason": "Bounded root.", "evidence_ref": "opaque:root"},
    )
    units = [root]
    predecessor = "root"
    for level in range(1, 13):
        left = f"left-{level:02d}"
        right = f"right-{level:02d}"
        merge = f"merge-{level:02d}"
        units.extend(
            [
                _unit(left, "PLANNED", depends_on=[predecessor]),
                _unit(right, "PLANNED", depends_on=[predecessor]),
                _unit(merge, "PLANNED", depends_on=[left, right]),
            ]
        )
        predecessor = merge

    _write_roadmap(tmp_path, _roadmap(units))
    report = load_development_status(tmp_path)
    by_id = {unit["id"]: unit for unit in report["units"]}
    assert len(by_id[predecessor]["skip_dependency_chains"]) == MAX_SKIP_CHAINS_PER_UNIT

    units.append(_unit("too-many", "PLANNED", depends_on=[predecessor, "root"]))
    _write_roadmap(tmp_path, _roadmap(units))
    with pytest.raises(ValueError, match=rf"maximum safeguard skip chains {MAX_SKIP_CHAINS_PER_UNIT}"):
        load_development_status(tmp_path)


def test_check_unit_is_scope_eligibility_not_prerequisite_readiness(tmp_path: Path, capsys) -> None:
    payload = _roadmap(
        [
            _unit("deferred-prerequisite", "DEFERRED"),
            _unit("planned", "PLANNED", depends_on=["deferred-prerequisite"]),
            _unit(
                "skipped",
                "SKIPPED_SAFEGUARD",
                trigger={"reason": "Stopped by safeguard.", "evidence_ref": "ledger:skip"},
            ),
        ]
    )
    roadmap_path = _write_roadmap(tmp_path, payload, "custom/roadmap.json")
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    assert (
        main(
            [
                "factory",
                "development-status",
                "--project-root",
                str(tmp_path),
                "--roadmap",
                "custom/roadmap.json",
                "--check-unit",
                "planned",
                "--json",
            ]
        )
        == 0
    )
    planned = json.loads(capsys.readouterr().out)
    assert planned["scope_eligible"] is True
    assert planned["unit"]["effective_status"] == "PLANNED"
    assert (
        main(
            [
                "factory",
                "development-status",
                "--project-root",
                str(tmp_path),
                "--roadmap",
                str(roadmap_path),
                "--check-unit",
                "deferred-prerequisite",
                "--json",
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["scope_eligible"] is False
    assert (
        main(
            [
                "factory",
                "development-status",
                "--project-root",
                str(tmp_path),
                "--roadmap",
                str(roadmap_path),
                "--check-unit",
                "skipped",
                "--json",
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["unit"]["skip_root_ids"] == ["skipped"]
    assert (
        main(
            [
                "factory",
                "development-status",
                "--project-root",
                str(tmp_path),
                "--roadmap",
                str(roadmap_path),
                "--check-unit",
                "unknown",
                "--json",
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["unit"] is None

    after = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before


def test_text_report_includes_dependency_chains_and_root_evidence(tmp_path: Path, capsys) -> None:
    payload = _roadmap(
        [
            _unit(
                "root",
                "SKIPPED_SAFEGUARD",
                trigger={"reason": "Stopped by safeguard.", "evidence_ref": "opaque:root-evidence"},
            ),
            _unit("dependent", "VERIFIED", depends_on=["root"]),
        ]
    )
    _write_roadmap(tmp_path, payload)

    assert main(["factory", "development-status", "--project-root", str(tmp_path)]) == 0
    default_output = capsys.readouterr().out
    assert "skip-chain: dependent -> root" in default_output
    assert "blocking-root evidence root: opaque:root-evidence" in default_output

    assert (
        main(
            [
                "factory",
                "development-status",
                "--project-root",
                str(tmp_path),
                "--check-unit",
                "dependent",
            ]
        )
        == 1
    )
    selected_output = capsys.readouterr().out
    assert "skip-chain: dependent -> root" in selected_output
    assert "blocking-root evidence root: opaque:root-evidence" in selected_output


def test_explicit_blank_check_unit_never_falls_through_to_full_report(tmp_path: Path, capsys) -> None:
    _write_roadmap(tmp_path, _roadmap([_unit("planned", "PLANNED")]))

    assert (
        main(
            [
                "factory",
                "development-status",
                "--project-root",
                str(tmp_path),
                "--check-unit",
                "",
                "--json",
            ]
        )
        == 1
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["requested_unit_id"] == ""
    assert payload["unit"] is None
    assert payload["scope_eligible"] is False
    assert "units" not in payload

    assert (
        main(
            [
                "factory",
                "development-status",
                "--project-root",
                str(tmp_path),
                "--check-unit",
                "   ",
            ]
        )
        == 1
    )
    output = capsys.readouterr().out
    assert "UNKNOWN '   ': outside the declared development scope" in output
    assert "Development scope:" not in output


def test_invalid_roadmap_returns_cli_error_without_writes(tmp_path: Path, capsys) -> None:
    roadmap_path = _write_roadmap(tmp_path, _roadmap([_unit("bad", "PLANNED")]))
    roadmap_path.write_text("{invalid", encoding="utf-8")
    before = roadmap_path.read_bytes()

    assert main(["factory", "development-status", "--project-root", str(tmp_path), "--json"]) == 2
    assert "invalid development roadmap JSON" in capsys.readouterr().err
    assert roadmap_path.read_bytes() == before


def test_select_development_unit_does_not_mutate_report(tmp_path: Path) -> None:
    _write_roadmap(tmp_path, _roadmap([_unit("verified", "VERIFIED")]))
    report = load_development_status(tmp_path)

    selected = select_development_unit(report, "verified")

    assert selected is not None and selected["scope_eligible"] is True
    assert "scope_eligible" not in report["units"][0]


def test_repository_roadmap_has_expected_bounded_skip_partition() -> None:
    project_root = Path(__file__).resolve().parents[1]

    report = load_development_status(project_root)
    units = {unit["id"]: unit for unit in report["units"]}

    assert report["counts_by_effective_status"]["SKIPPED_SAFEGUARD"] == 1
    assert report["counts_by_effective_status"]["SKIPPED_DEPENDENCY"] == 19
    assert units["legacy_p16_qualification"]["effective_status"] == "PLANNED"
    assert units["mvp_skip_policy"]["effective_status"] == "IMPLEMENTED"
