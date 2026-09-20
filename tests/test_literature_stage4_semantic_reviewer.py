from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path

import pytest

from alphaquest.research.literature import stage3_claim_extractor as stage3
from alphaquest.research.literature import stage4_semantic_model as model
from alphaquest.research.literature import stage4_semantic_reviewer as reviewer
from alphaquest.research.literature.contracts import (
    ClaimExtractionRevisionV1,
    CodexTaskAttemptRevisionV1,
    LiteratureAuthorityError,
    LiteratureIntegrityError,
    canonical_json_bytes,
)
from alphaquest.research.literature.stage2_runner import PilotManualReconciliation
from alphaquest.research.literature.store import LiteratureStore
from tests.test_literature_stage1 import (
    NOW,
    _actor,
    _protocol_payload,
    _rewrite_valid_hash_chains,
)
from tests.test_literature_stage3_claim_extractor import (
    _MANAGED,
    _acquire,
    _envelope as extraction_envelope,
    _output as extraction_output,
)


def _semantic_envelope(output=None, **changes):
    result = {
        "model": model.MODEL_CONTRACT,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": canonical_json_bytes(output or _direct_output()).decode(),
                    }
                ],
            }
        ],
    }
    if "response_output" in changes:
        result["output"] = changes.pop("response_output")
    result.update(changes)
    return canonical_json_bytes(result)


def _direct_output(*, scope="DIRECTLY_RELEVANT", support="EXACTLY_SUPPORTED", epistemic="CONSISTENT"):
    return {
        "support_assessment": support,
        "scope_assessment": scope,
        "epistemic_form_assessment": epistemic,
        "basis_spans": [
            {"byte_start": 0, "byte_end": 11, "quote": "Hello world"}
        ],
        "methodology_descriptors": [],
    }


def _stage3_store(root: Path, *, claims=None):
    store, protocol = _acquire(root)
    stage3.run_claim_extraction_pilot(
        root,
        protocol.record_sha256,
        _client=lambda _: extraction_envelope(
            extraction_output(claims=claims) if claims is not None else None
        ),
    )
    return store, protocol


def _requests(root: Path, protocol):
    return reviewer.prepare_semantic_review_requests(root, protocol.record_sha256)


def _supported_fixture(request: bytes) -> bytes:
    envelope = model.parse_json(request)
    logical = model.parse_json(
        envelope["input"][0]["content"][0]["text"].encode("utf-8")
    )
    claim = logical["claim"]
    return _semantic_envelope(
        {
            "support_assessment": "EXACTLY_SUPPORTED",
            "scope_assessment": "DIRECTLY_RELEVANT",
            "epistemic_form_assessment": "CONSISTENT",
            "basis_spans": [
                {
                    "byte_start": claim["byte_start"],
                    "byte_end": claim["byte_end"],
                    "quote": claim["quote"],
                }
            ],
            "methodology_descriptors": [],
        }
    )


def _run(root: Path, protocol, response, *, mapping=None):
    requests = _requests(root, protocol)
    fixtures = (
        {key: response for key in requests}
        if mapping is None
        else mapping
    )
    return reviewer.run_semantic_review_synthetic(
        root,
        protocol.record_sha256,
        response_by_request_sha256=fixtures,
        qualification_class="SYNTHETIC_FIXTURE_ONLY",
    )


def _attempts(store):
    return [
        item for item in store.records()
        if isinstance(item, CodexTaskAttemptRevisionV1)
        and item.attempt_id.startswith(model.ATTEMPT_PREFIX)
    ]


def _two_context_receipt(root: Path, *, first_response: bytes | None = None):
    claims = [
        {"byte_start": 0, "byte_end": 5, "quote": "Hello", "source_epistemic_form": "OTHER"},
        {"byte_start": 6, "byte_end": 11, "quote": "world", "source_epistemic_form": "OTHER"},
    ]
    store, protocol = _stage3_store(root, claims=claims)
    records = store.records()
    planned = reviewer._prepare_plan(protocol, records, store.verify_artifact)
    responses = [_supported_fixture(item.request) for item in planned]
    if first_response is not None:
        responses[0] = first_response
    fresh = [
        {
            "review_context_sha256": item.review_context_sha256,
            "request_sha256": item.request_sha256,
            "fixture_response_sha256": model.sha(response),
            "fixture_response_byte_count": len(response),
        }
        for item, response in zip(planned, responses, strict=True)
    ]
    receipt_bytes = reviewer._receipt_material(protocol, planned, records, [], fresh)
    receipt_sha = model.sha(receipt_bytes)
    for response in responses:
        store.put_artifact(response, kind="codex-io")
    assert store.put_artifact(receipt_bytes, kind="codex-io") == receipt_sha
    for item in planned:
        for artifact in (
            model.settings_bytes(),
            model.PROMPT.encode("utf-8"),
            item.request,
            reviewer._input_manifest(item, receipt_sha),
            reviewer._boundary_manifest(item, receipt_sha),
        ):
            store.put_artifact(artifact, kind="codex-io")
    return store, protocol, planned, responses, receipt_sha


def _append_started(store, prepared, receipt_sha):
    return store.append_codex_attempt(
        reviewer._fresh_started_payload(prepared, receipt_sha),
        actor=reviewer.CONTROLLER,
        idempotency_key=prepared.attempt_id + ".start",
    )


def _codex_artifacts(root: Path) -> set[Path]:
    artifact_root = root / "run-store/literature/codex-io"
    return {path for path in artifact_root.rglob("*") if path.is_file()}


class _ObservedMapping(Mapping):
    def __init__(self, keys, values, *, declared_length=None):
        self.keys = list(keys)
        self.values = values
        self.declared_length = (
            len(self.keys) if declared_length is None else declared_length
        )
        self.iterations = 0
        self.length_reads = 0
        self.lookups: list[str] = []

    def __iter__(self):
        self.iterations += 1
        return iter(self.keys)

    def __len__(self):
        self.length_reads += 1
        return self.declared_length

    def __getitem__(self, key):
        self.lookups.append(key)
        return self.values[key]


def test_zero_claim_lineage_completes_without_artifacts_or_attempts(tmp_path):
    store, protocol = _stage3_store(tmp_path, claims=[])
    before = set((tmp_path / "run-store/literature/codex-io").rglob("*"))
    result = _run(tmp_path, protocol, b"unused", mapping={})
    after = set((tmp_path / "run-store/literature/codex-io").rglob("*"))
    assert result["complete"] and result["receipt_refs"] == []
    assert not _attempts(store) and before == after


def test_exact_supported_direct_claim_is_advisory_direct_only(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    before = {family: 0 for family in {item.family for item in store.records()}}
    for item in store.records():
        before[item.family] += 1
    result = _run(tmp_path, protocol, _semantic_envelope())
    assert result["complete"] and result["eligible_direct_count"] == 1
    assert result["attempts"][0]["p3_advisory_use"] == "ELIGIBLE_DIRECT"
    after = {family: 0 for family in before}
    for item in store.records():
        after[item.family] += 1
    assert {family for family in before if before[family] != after[family]} == {
        "codex-attempts"
    }


def test_supported_background_methodology_is_context_only(tmp_path):
    _, protocol = _stage3_store(tmp_path)
    result = _run(
        tmp_path,
        protocol,
        _semantic_envelope(_direct_output(scope="BACKGROUND_RELEVANT")),
    )
    assert result["attempts"][0]["p3_advisory_use"] == "ELIGIBLE_CONTEXT_ONLY"


@pytest.mark.parametrize("support", ["OVERSTATED", "NOT_SUPPORTED"])
def test_overstated_or_not_supported_claim_is_successful_exclusion(tmp_path, support):
    _, protocol = _stage3_store(tmp_path)
    result = _run(
        tmp_path, protocol, _semantic_envelope(_direct_output(support=support))
    )
    assert result["complete"] and result["excluded_count"] == 1
    assert result["attempts"][0]["p3_advisory_use"] == "INELIGIBLE_EXCLUDED"


@pytest.mark.parametrize(
    "output",
    [
        _direct_output(support="AMBIGUOUS"),
        _direct_output(scope="INSUFFICIENT_CONTEXT"),
        _direct_output(epistemic="AMBIGUOUS"),
    ],
)
def test_ambiguous_and_insufficient_context_are_successful_exclusions_without_human_gate(tmp_path, output):
    _, protocol = _stage3_store(tmp_path)
    result = _run(tmp_path, protocol, _semantic_envelope(output))
    assert result["complete"] and result["excluded_count"] == 1
    assert result["attempts"][0]["p3_advisory_use"] == "AMBIGUOUS_EXCLUDED"


def test_zero_eligible_batch_completes_and_cannot_retry_for_support(tmp_path):
    _, protocol = _stage3_store(tmp_path)
    first = _run(
        tmp_path,
        protocol,
        _semantic_envelope(_direct_output(support="NOT_SUPPORTED")),
    )
    assert first["complete"] and first["eligible_direct_count"] == 0
    request = next(iter(_requests(tmp_path, protocol)))
    with pytest.raises(ValueError, match="empty fixture"):
        _run(tmp_path, protocol, b"", mapping={request: _semantic_envelope()})


def test_exact_utf8_basis_spans_and_descriptor_rules():
    abstract = "雪 evidence".encode()
    output = {
        "support_assessment": "EXACTLY_SUPPORTED",
        "scope_assessment": "DIRECTLY_RELEVANT",
        "epistemic_form_assessment": "CONSISTENT",
        "basis_spans": [{"byte_start": 0, "byte_end": 3, "quote": "雪"}],
        "methodology_descriptors": [
            {"descriptor": "SAMPLE_PERIOD", "assessment": "NOT_STATED", "basis_spans": []}
        ],
    }
    parsed = model.validate_response(
        _semantic_envelope(output),
        abstract,
        claim_byte_start=0,
        claim_byte_end=3,
        claim_quote="雪",
    )
    assert parsed.methodology_descriptors[0].assessment == "NOT_STATED"


@pytest.mark.parametrize(
    "response",
    [
        b'{"status":[],"status":"completed"}',
        b'{"status":NaN}',
        b'{"status":[]}',
        b'{"status":{}}',
    ],
)
def test_duplicate_keys_extra_fields_nonfinite_bool_float_and_bad_spans_fail_whole_output(response):
    with pytest.raises(model.InvalidSemanticReviewOutput):
        model.validate_response(
            response, b"x", claim_byte_start=0, claim_byte_end=1, claim_quote="x"
        )
    bad = _direct_output()
    bad["basis_spans"][0]["byte_start"] = False
    with pytest.raises(model.InvalidSemanticReviewOutput):
        model.validate_response(
            _semantic_envelope(bad),
            b"Hello world",
            claim_byte_start=0,
            claim_byte_end=11,
            claim_quote="Hello world",
        )


@pytest.mark.parametrize(
    "response,status",
    [
        (b"{", "INVALID_OUTPUT"),
        (b'{"status":[]}', "INVALID_OUTPUT"),
        (_semantic_envelope(status="incomplete"), "FAILED"),
        (
            _semantic_envelope(
                response_output=[{
                    "type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "refusal", "refusal": "no"}],
                }]
            ),
            "FAILED",
        ),
    ],
)
def test_refusal_incomplete_and_invalid_outputs_have_exact_terminal_categories(tmp_path, response, status):
    store, protocol = _stage3_store(tmp_path)
    result = _run(tmp_path, protocol, response)
    assert result["attempts"][0]["status"] == status
    expected_reason = (
        "INVALID_SEMANTIC_REVIEW_OUTPUT"
        if status == "INVALID_OUTPUT"
        else "REFUSAL_OR_INCOMPLETE_RESPONSE"
    )
    assert _attempts(store)[-1].failure_reason == expected_reason


def test_missing_or_extra_fixture_keys_fail_before_any_write(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    before = len(store.records())
    key = next(iter(_requests(tmp_path, protocol)))
    with pytest.raises(ValueError, match="exactly match"):
        _run(tmp_path, protocol, b"", mapping={})
    with pytest.raises(ValueError, match="exactly match"):
        _run(tmp_path, protocol, b"", mapping={key: _semantic_envelope(), "0" * 64: b"x"})
    assert len(store.records()) == before


def test_terminal_publication_failure_leaves_orphan_and_never_rereads_fixture(tmp_path, monkeypatch):
    store, protocol = _stage3_store(tmp_path)
    original = LiteratureStore.append_codex_attempt

    def fail_terminal(self, payload, **kwargs):
        if payload["attempt_id"].startswith(model.ATTEMPT_PREFIX) and payload["status"] != "STARTED":
            raise OSError("terminal publication crash")
        return original(self, payload, **kwargs)

    monkeypatch.setattr(LiteratureStore, "append_codex_attempt", fail_terminal)
    with pytest.raises(OSError):
        _run(tmp_path, protocol, _semantic_envelope())
    monkeypatch.setattr(LiteratureStore, "append_codex_attempt", original)
    assert _attempts(store)[-1].status == "STARTED"
    with pytest.raises(PilotManualReconciliation, match="abandoned"):
        _run(tmp_path, protocol, b"", mapping={})
    assert _attempts(store)[-1].status == "ABANDONED_AFTER_CRASH"


def test_crash_reentry_abandons_without_fixture_call(tmp_path, monkeypatch):
    test_terminal_publication_failure_leaves_orphan_and_never_rereads_fixture(
        tmp_path, monkeypatch
    )


def test_terminal_failure_consumes_context_and_blocks_later_batch_progress(tmp_path):
    claims = [
        {"byte_start": 0, "byte_end": 5, "quote": "Hello", "source_epistemic_form": "OTHER"},
        {"byte_start": 6, "byte_end": 11, "quote": "world", "source_epistemic_form": "OTHER"},
    ]
    store, protocol = _stage3_store(tmp_path, claims=claims)
    requests = _requests(tmp_path, protocol)
    result = reviewer.run_semantic_review_synthetic(
        tmp_path,
        protocol.record_sha256,
        response_by_request_sha256={key: b"{" for key in requests},
        qualification_class="SYNTHETIC_FIXTURE_ONLY",
    )
    assert not result["complete"] and result["attempts"][0]["status"] == "INVALID_OUTPUT"
    assert len(_attempts(store)) == 2
    again = _run(tmp_path, protocol, b"", mapping={})
    assert len(again["attempts"]) == 1 and len(_attempts(store)) == 2


def test_exact_success_reentry_reuses_and_recomputes_currentness(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    first = _run(tmp_path, protocol, _semantic_envelope())
    before = len(store.records())
    second = _run(tmp_path, protocol, b"", mapping={})
    assert second["attempts"][0]["reused"] and second["attempts"][0]["current"]
    assert second["receipt_refs"] == first["receipt_refs"] and len(store.records()) == before


def test_administrative_protocol_revision_or_renamed_lineage_cannot_redispatch(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    _run(tmp_path, protocol, _semantic_envelope())
    payload = protocol.model_dump(mode="json", exclude=_MANAGED)
    payload.update(administrative_annotations=["rename"], change_reason="Administrative")
    revised = store.append_protocol(payload, actor=_actor(), idempotency_key="admin")
    result = _run(tmp_path, revised, b"", mapping={})
    assert result["complete"] and result["attempts"] == []


def test_renamed_claim_id_same_subject_cannot_redispatch(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    claim = next(item for item in store.records() if isinstance(item, ClaimExtractionRevisionV1))
    renamed = claim.model_copy(update={"claim_id": "claim.stage3." + "f" * 64})
    assert reviewer._semantic_subject_sha256(renamed) == reviewer._semantic_subject_sha256(claim)
    prepared = reviewer._prepare_plan(protocol, store.records(), store.verify_artifact)[0]
    assert prepared.attempt_id == model.ATTEMPT_PREFIX + reviewer._review_context_sha256(
        reviewer._semantic_subject_sha256(renamed), prepared.research_context_sha256
    )


def test_model_prompt_backend_or_controller_rename_cannot_reset_base_context(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    prepared = reviewer._prepare_plan(protocol, store.records(), store.verify_artifact)[0]
    assert prepared.review_context_sha256 == reviewer._review_context_sha256(
        prepared.semantic_subject_sha256, prepared.research_context_sha256
    )
    assert all(
        marker.encode() not in canonical_json_bytes(
            [prepared.semantic_subject_sha256, prepared.research_context_sha256]
        )
        for marker in (
            model.MODEL_CONTRACT, model.PROMPT_VERSION, model.BACKEND,
            model.CONTROLLER_VERSION,
        )
    )


def test_material_research_context_change_has_distinct_hash_but_requires_exact_upstream_binding(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    claim = next(item for item in store.records() if isinstance(item, ClaimExtractionRevisionV1))
    revised = protocol.model_copy(
        update={"research_question": "Materially different question", "record_sha256": "0" * 64}
    )
    assert model.sha(canonical_json_bytes(reviewer._research_context(revised))) != model.sha(
        canonical_json_bytes(reviewer._research_context(protocol))
    )
    with pytest.raises(LiteratureAuthorityError, match="exact Stage 3 extraction protocol"):
        reviewer._prepare_claim(revised, claim, store.records(), store.verify_artifact)


def test_stale_corrected_withdrawn_or_retracted_claim_rejected_before_artifact_read(tmp_path, monkeypatch):
    store, protocol = _stage3_store(tmp_path)
    claim = next(item for item in store.records() if isinstance(item, ClaimExtractionRevisionV1))
    withdrawn = claim.model_copy(
        update={"revision": 2, "reliability": "WITHDRAWN_INVALID", "correction_reason": "invalid"}
    )
    records = [item for item in store.records() if item.record_sha256 != claim.record_sha256]
    records.append(withdrawn)
    forbidden = lambda *args, **kwargs: pytest.fail("artifact read")
    with pytest.raises(LiteratureAuthorityError, match="not currently eligible"):
        reviewer._prepare_claim(protocol, withdrawn, records, forbidden)


def test_substituted_claim_capture_protocol_or_extraction_attempt_rejected_on_append_and_reload(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    _run(tmp_path, protocol, _semantic_envelope())

    def mutate(record):
        if record.get("attempt_id", "").startswith(model.ATTEMPT_PREFIX):
            record["task_type"] = "DOSSIER_SYNTHESIZER"

    _rewrite_valid_hash_chains(tmp_path, mutate)
    with pytest.raises(LiteratureIntegrityError):
        LiteratureStore(tmp_path).validate()


def test_rehashed_response_status_contradiction_rejected_on_reload(tmp_path):
    _, protocol = _stage3_store(tmp_path)
    _run(tmp_path, protocol, _semantic_envelope())

    def mutate(record):
        if (
            record.get("attempt_id", "").startswith(model.ATTEMPT_PREFIX)
            and record["status"] != "STARTED"
        ):
            record.update(status="INVALID_OUTPUT", failure_reason="INVALID_SEMANTIC_REVIEW_OUTPUT")

    _rewrite_valid_hash_chains(tmp_path, mutate)
    with pytest.raises(LiteratureIntegrityError, match="contradicts retained response"):
        LiteratureStore(tmp_path).validate()


def test_reserved_task_backend_prefix_mismatches_fail_closed(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    requests = _requests(tmp_path, protocol)
    assert requests
    stage3_started = next(
        item for item in store.records()
        if isinstance(item, CodexTaskAttemptRevisionV1) and item.status == "STARTED"
    )
    payload = stage3_started.model_dump(mode="json", include={
        "task_type", "model", "settings_sha256", "prompt_sha256", "input_manifest_sha256",
        "workspace_manifest_sha256", "referenced_records", "isolation_backend",
    })
    payload.update(
        attempt_id=model.ATTEMPT_PREFIX + "0" * 64,
        status="STARTED", output_sha256=None, failure_reason=None,
    )
    with pytest.raises(LiteratureIntegrityError):
        store.append_codex_attempt(
            payload, actor=reviewer.CONTROLLER, idempotency_key="reserved-mismatch"
        )


def test_existing_stage3_attempts_and_claims_reload_unchanged(tmp_path):
    store, _ = _stage3_store(tmp_path)
    before = [(item.record_id, item.record_sha256) for item in store.records()]
    assert store.validate()["status"] == "PASS"
    assert before == [(item.record_id, item.record_sha256) for item in store.records()]


def test_pnl_result_trade_campaign_holdout_p2_and_git_noise_do_not_change_request_or_decision(tmp_path):
    _, protocol = _stage3_store(tmp_path)
    first = _requests(tmp_path, protocol)
    for name in ("pnl.json", "trades.csv", "campaign.yaml", "holdout.json", ".git-noise"):
        (tmp_path / name).write_text("SECRET_PNL_999")
    assert _requests(tmp_path, protocol) == first


def test_no_network_env_or_credential_access_and_no_downstream_family_writes(tmp_path, monkeypatch):
    store, protocol = _stage3_store(tmp_path)
    before = {item.family: 0 for item in store.records()}
    for item in store.records():
        before[item.family] += 1
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-read")
    result = _run(tmp_path, protocol, _semantic_envelope())
    assert result["complete"]
    after = {family: 0 for family in before}
    for item in store.records():
        after[item.family] += 1
    changed = {family for family in before if before[family] != after[family]}
    assert changed == {"codex-attempts"}


def test_synthetic_receipt_binds_initial_prefix_claims_and_exact_fixture_set(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    result = _run(tmp_path, protocol, _semantic_envelope())
    receipt = reviewer._parse_receipt(
        result["receipt_refs"][0], store.records(), store.verify_artifact
    )
    assert receipt.qualification_class == "SYNTHETIC_FIXTURE_ONLY"
    assert len(receipt.claim_refs) == len(receipt.fresh_fixture_bindings) == 1
    assert receipt.fresh_fixture_bindings[0].fixture_response_byte_count > 0


@pytest.mark.parametrize("anchor_kind", ["null", "early_protocol"])
def test_rehashed_receipt_rebound_attempt_cannot_forge_initial_prefix(
    tmp_path, anchor_kind
):
    store, protocol = _stage3_store(tmp_path)
    result = _run(tmp_path, protocol, _semantic_envelope())
    original_sha = result["receipt_refs"][0]
    receipt = reviewer._parse_receipt(
        original_sha, store.records(), store.verify_artifact
    )
    material = receipt.model_dump(mode="json", by_alias=True)
    material.pop("receipt_sha256")
    material["initial_store_head_record_sha256"] = (
        None if anchor_kind == "null" else protocol.record_sha256
    )
    material["receipt_sha256"] = model.sha(
        canonical_json_bytes(material, trailing_lf=False)
    )
    forged = reviewer.SyntheticSemanticQualificationReceiptV1.model_validate(material)
    forged_bytes = canonical_json_bytes(forged)
    forged_sha = store.put_artifact(forged_bytes, kind="codex-io")

    records = store.records()
    prepared = reviewer._prepare_plan(protocol, records, store.verify_artifact)[0]
    input_manifest = reviewer._input_manifest(prepared, forged_sha)
    boundary_manifest = reviewer._boundary_manifest(prepared, forged_sha)
    input_sha = store.put_artifact(input_manifest, kind="codex-io")
    boundary_sha = store.put_artifact(boundary_manifest, kind="codex-io")

    def mutate(record):
        if record.get("attempt_id", "").startswith(model.ATTEMPT_PREFIX):
            record["input_manifest_sha256"] = input_sha
            record["workspace_manifest_sha256"] = boundary_sha

    _rewrite_valid_hash_chains(tmp_path, mutate)
    with pytest.raises(LiteratureIntegrityError, match="initial|frozen-prefix"):
        LiteratureStore(tmp_path).validate()


def test_synthetic_backend_cannot_be_consumed_as_real_semantic_eligibility(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    result = _run(tmp_path, protocol, _semantic_envelope())
    evidence = reviewer.load_synthetic_semantic_review_evidence(
        store,
        result["attempts"][0]["attempt_id"],
        required_receipt_sha256=result["receipt_refs"][0],
    )
    with pytest.raises(LiteratureAuthorityError, match="not production eligibility"):
        reviewer.require_production_semantic_review(evidence)


def test_report_and_return_cannot_omit_or_relabel_synthetic_qualification_class(tmp_path):
    _, protocol = _stage3_store(tmp_path)
    result = _run(tmp_path, protocol, _semantic_envelope())
    assert result["qualification_class"] == "SYNTHETIC_FIXTURE_ONLY"
    assert result["synthetic_fixture_only"] is True
    with pytest.raises(LiteratureAuthorityError):
        reviewer.run_semantic_review_synthetic(
            tmp_path,
            protocol.record_sha256,
            response_by_request_sha256={},
            qualification_class=True,
        )


def test_all_success_reentry_empty_mapping_writes_nothing(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    _run(tmp_path, protocol, _semantic_envelope())
    before = [(item.record_id, item.record_sha256) for item in store.records()]
    result = _run(tmp_path, protocol, b"", mapping={})
    assert result["complete"] and result["attempts"][0]["reused"]
    assert before == [(item.record_id, item.record_sha256) for item in store.records()]


def _exercise_partial_success_reentry(tmp_path, monkeypatch):
    claims = [
        {"byte_start": 0, "byte_end": 5, "quote": "Hello", "source_epistemic_form": "OTHER"},
        {"byte_start": 6, "byte_end": 11, "quote": "world", "source_epistemic_form": "OTHER"},
    ]
    store, protocol = _stage3_store(tmp_path, claims=claims)
    requests = _requests(tmp_path, protocol)
    fixtures = {key: _supported_fixture(request) for key, request in requests.items()}
    original = LiteratureStore.append_codex_attempt
    starts = 0

    def crash_before_second(self, payload, **kwargs):
        nonlocal starts
        if payload["attempt_id"].startswith(model.ATTEMPT_PREFIX) and payload["status"] == "STARTED":
            starts += 1
            if starts == 2:
                raise KeyboardInterrupt
        return original(self, payload, **kwargs)

    monkeypatch.setattr(LiteratureStore, "append_codex_attempt", crash_before_second)
    with pytest.raises(KeyboardInterrupt):
        reviewer.run_semantic_review_synthetic(
            tmp_path,
            protocol.record_sha256,
            response_by_request_sha256=fixtures,
            qualification_class="SYNTHETIC_FIXTURE_ONLY",
        )
    monkeypatch.setattr(LiteratureStore, "append_codex_attempt", original)
    first_terminal = _attempts(store)[-1]
    manifest = reviewer._parse_input_manifest(first_terminal, store.verify_artifact)
    receipt_sha = manifest["synthetic_qualification_receipt_sha256"]
    receipt = reviewer._parse_receipt(receipt_sha, store.records(), store.verify_artifact)
    assert len(receipt.fresh_fixture_bindings) == 2

    # Advance the canonical head without altering semantic inputs.
    store.append_codex_attempt(
        {
            "attempt_id": "attempt.generic.head-noise",
            "task_type": "METHODOLOGY_DESCRIPTOR",
            "status": "REJECTED_PROCESSING_PERMISSION",
            "model": None,
            "settings_sha256": "0" * 64,
            "prompt_sha256": "1" * 64,
            "input_manifest_sha256": "2" * 64,
            "workspace_manifest_sha256": None,
            "output_sha256": None,
            "referenced_records": [],
            "isolation_backend": "NOT_INVOKED_PROCESSING_PERMISSION",
            "failure_reason": "fixture head advance",
        },
        actor=_actor(),
        idempotency_key="generic-head-noise",
    )
    assert store.records()[-1].record_sha256 != receipt.initial_store_head_record_sha256
    resumed = _run(tmp_path, protocol, b"", mapping={})
    assert resumed["complete"] and resumed["receipt_refs"] == [receipt_sha]
    assert [item["reused"] for item in resumed["attempts"]] == [True, False]
    return resumed


def test_partial_success_reentry_selects_original_receipt_despite_new_head(tmp_path, monkeypatch):
    _exercise_partial_success_reentry(tmp_path, monkeypatch)


def test_crash_before_next_started_uses_retained_future_fixture_without_new_receipt(tmp_path, monkeypatch):
    resumed = _exercise_partial_success_reentry(tmp_path, monkeypatch)
    assert all(item["status"] == "SUCCEEDED" for item in resumed["attempts"])


def test_orphan_abandonment_stops_later_receipt_contexts(tmp_path, monkeypatch):
    claims = [
        {"byte_start": 0, "byte_end": 5, "quote": "Hello", "source_epistemic_form": "OTHER"},
        {"byte_start": 6, "byte_end": 11, "quote": "world", "source_epistemic_form": "OTHER"},
    ]
    store, protocol = _stage3_store(tmp_path, claims=claims)
    requests = _requests(tmp_path, protocol)
    fixtures = {key: _supported_fixture(request) for key, request in requests.items()}
    original = LiteratureStore.append_codex_attempt

    def fail_first_terminal(self, payload, **kwargs):
        if payload["attempt_id"].startswith(model.ATTEMPT_PREFIX) and payload["status"] != "STARTED":
            raise OSError("terminal crash")
        return original(self, payload, **kwargs)

    monkeypatch.setattr(LiteratureStore, "append_codex_attempt", fail_first_terminal)
    with pytest.raises(OSError):
        reviewer.run_semantic_review_synthetic(
            tmp_path, protocol.record_sha256,
            response_by_request_sha256=fixtures,
            qualification_class="SYNTHETIC_FIXTURE_ONLY",
        )
    monkeypatch.setattr(LiteratureStore, "append_codex_attempt", original)
    with pytest.raises(PilotManualReconciliation, match="abandoned"):
        _run(tmp_path, protocol, b"", mapping={})
    assert [item.status for item in _attempts(store)] == [
        "STARTED", "ABANDONED_AFTER_CRASH"
    ]


def test_terminal_failure_blocks_later_context_and_rejects_alternative_fixture(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    _run(tmp_path, protocol, b"{")
    key = next(iter(_requests(tmp_path, protocol)))
    with pytest.raises(PilotManualReconciliation, match="alternative fixture"):
        _run(tmp_path, protocol, b"", mapping={key: _semantic_envelope()})
    assert len(_attempts(store)) == 2


def test_mixed_reused_fresh_batch_preserves_per_attempt_receipt_ownership(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    result = _run(tmp_path, protocol, _semantic_envelope())
    evidence = reviewer.load_synthetic_semantic_review_evidence(
        store, result["attempts"][0]["attempt_id"],
        required_receipt_sha256=result["attempts"][0]["owning_receipt_sha256"],
    )
    assert evidence.receipt_sha256 == result["attempts"][0]["owning_receipt_sha256"]


def test_unowned_receipt_artifact_is_never_selected(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    store.put_artifact(b'{"unowned":true}\n', kind="codex-io")
    result = _run(tmp_path, protocol, _semantic_envelope())
    assert result["complete"] and result["receipt_refs"]


def test_receipt_initial_head_is_ancestor_not_current_head_requirement(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    result = _run(tmp_path, protocol, _semantic_envelope())
    receipt = reviewer._parse_receipt(result["receipt_refs"][0], store.records(), store.verify_artifact)
    assert receipt.initial_store_head_record_sha256 != store.records()[-1].record_sha256
    assert _run(tmp_path, protocol, b"", mapping={})["complete"]


def test_synthetic_loader_preserves_literal_class_and_production_helper_rejects(tmp_path):
    test_synthetic_backend_cannot_be_consumed_as_real_semantic_eligibility(tmp_path)


def test_stage3_reserved_or_routing_preserves_all_mismatch_and_permission_sentinel_results(tmp_path):
    store, _ = _stage3_store(tmp_path)
    assert store.validate()["status"] == "PASS"


def test_receipt_rejects_later_context_started_before_first_at_append(tmp_path):
    store, _, planned, _, receipt_sha = _two_context_receipt(tmp_path)
    before = len(store.records())
    with pytest.raises(LiteratureIntegrityError, match="contiguous successful prefix"):
        _append_started(store, planned[1], receipt_sha)
    assert len(store.records()) == before
    assert not _attempts(store)


def test_receipt_rejects_later_context_after_terminal_failure(tmp_path):
    store, _, planned, responses, receipt_sha = _two_context_receipt(
        tmp_path, first_response=b"{"
    )
    first = _append_started(store, planned[0], receipt_sha)
    response_sha = model.sha(responses[0])
    reviewer._terminal(
        store,
        first,
        "INVALID_OUTPUT",
        output_sha=response_sha,
        reason="INVALID_SEMANTIC_REVIEW_OUTPUT",
    )
    before = len(store.records())
    with pytest.raises(LiteratureIntegrityError, match="contiguous successful prefix"):
        _append_started(store, planned[1], receipt_sha)
    assert len(store.records()) == before
    assert [item.status for item in _attempts(store)] == ["STARTED", "INVALID_OUTPUT"]


def test_receipt_rejects_later_context_after_orphan_started(tmp_path):
    store, _, planned, _, receipt_sha = _two_context_receipt(tmp_path)
    _append_started(store, planned[0], receipt_sha)
    before = len(store.records())
    with pytest.raises(LiteratureIntegrityError, match="contiguous successful prefix"):
        _append_started(store, planned[1], receipt_sha)
    assert len(store.records()) == before
    assert [item.status for item in _attempts(store)] == ["STARTED"]


def test_rehashed_noncontiguous_receipt_history_fails_reload_and_evidence_load(tmp_path):
    store, protocol = _stage3_store(
        tmp_path,
        claims=[
            {"byte_start": 0, "byte_end": 5, "quote": "Hello", "source_epistemic_form": "OTHER"},
            {"byte_start": 6, "byte_end": 11, "quote": "world", "source_epistemic_form": "OTHER"},
        ],
    )
    requests = _requests(tmp_path, protocol)
    result = reviewer.run_semantic_review_synthetic(
        tmp_path,
        protocol.record_sha256,
        response_by_request_sha256={
            key: _supported_fixture(request) for key, request in requests.items()
        },
        qualification_class="SYNTHETIC_FIXTURE_ONLY",
    )
    first_attempt_id = result["attempts"][0]["attempt_id"]
    later = result["attempts"][1]

    def remove_first_owner(record):
        if record.get("attempt_id") == first_attempt_id:
            record["attempt_id"] = "attempt.generic.removed-stage4-owner"
            record["record_id"] = (
                "attempt.generic.removed-stage4-owner"
                f".r{record['revision']:06d}"
            )
            record["task_type"] = "METHODOLOGY_DESCRIPTOR"
            record["isolation_backend"] = "GENERIC_OFFLINE_FIXTURE"

    _rewrite_valid_hash_chains(tmp_path, remove_first_owner)
    attempt_root = tmp_path / "research/literature/codex-attempts"
    (attempt_root / first_attempt_id).rename(
        attempt_root / "attempt.generic.removed-stage4-owner"
    )
    with pytest.raises(LiteratureIntegrityError, match="contiguous successful prefix"):
        LiteratureStore(tmp_path).validate()
    with pytest.raises(LiteratureIntegrityError, match="contiguous successful prefix"):
        reviewer.load_synthetic_semantic_review_evidence(
            store,
            later["attempt_id"],
            required_receipt_sha256=later["owning_receipt_sha256"],
        )


def test_duplicate_raw_mapping_key_fails_before_value_lookup_or_write(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    key = next(iter(_requests(tmp_path, protocol)))
    mapping = _ObservedMapping([key, key], {key: _semantic_envelope()})
    before_records = len(store.records())
    before_artifacts = _codex_artifacts(tmp_path)
    with pytest.raises(ValueError, match="invalid bounded synthetic fixture mapping"):
        _run(tmp_path, protocol, b"", mapping=mapping)
    assert mapping.lookups == []
    assert len(store.records()) == before_records
    assert _codex_artifacts(tmp_path) == before_artifacts
    assert not _attempts(store)


def test_equal_str_subclass_mapping_key_fails_before_write(tmp_path):
    class EqualString(str):
        pass

    store, protocol = _stage3_store(tmp_path)
    key = next(iter(_requests(tmp_path, protocol)))
    mapping = _ObservedMapping(
        [key, EqualString(key)], {key: _semantic_envelope()}
    )
    before_records = len(store.records())
    before_artifacts = _codex_artifacts(tmp_path)
    with pytest.raises(ValueError, match="invalid bounded synthetic fixture mapping"):
        _run(tmp_path, protocol, b"", mapping=mapping)
    assert mapping.lookups == []
    assert len(store.records()) == before_records
    assert _codex_artifacts(tmp_path) == before_artifacts


def test_valid_custom_mapping_is_snapshotted_once_and_never_accessed_again(tmp_path):
    _, protocol = _stage3_store(tmp_path)
    requests = _requests(tmp_path, protocol)
    mapping = _ObservedMapping(
        list(requests),
        {key: _supported_fixture(request) for key, request in requests.items()},
    )
    result = _run(tmp_path, protocol, b"", mapping=mapping)
    assert result["complete"]
    assert mapping.iterations == 1
    assert mapping.length_reads == 1
    assert mapping.lookups == list(requests)


def test_mapping_is_not_touched_until_store_wide_conflict_preflight_finishes(tmp_path):
    _, protocol = _stage3_store(tmp_path)
    _run(tmp_path, protocol, _semantic_envelope())

    def corrupt_owner(record):
        if record.get("attempt_id", "").startswith(model.ATTEMPT_PREFIX):
            record["task_type"] = "DOSSIER_SYNTHESIZER"

    _rewrite_valid_hash_chains(tmp_path, corrupt_owner)
    mapping = _ObservedMapping([], {})
    with pytest.raises(LiteratureIntegrityError):
        reviewer.run_semantic_review_synthetic(
            tmp_path,
            protocol.record_sha256,
            response_by_request_sha256=mapping,
            qualification_class="SYNTHETIC_FIXTURE_ONLY",
        )
    assert mapping.iterations == mapping.length_reads == 0
    assert mapping.lookups == []


def test_stage4_entrypoints_ignore_external_layout_environment_path(tmp_path, monkeypatch):
    _, protocol = _stage3_store(tmp_path)
    external = tmp_path.parent / f"{tmp_path.name}-external-layout.yaml"
    external.write_text("not: [valid")
    monkeypatch.setenv("ALPHAQUEST_STORAGE_LAYOUT", str(external))
    original = Path.read_text

    def guarded_read(path, *args, **kwargs):
        if path == external:
            pytest.fail("Stage 4 read the environment-selected layout")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read)
    requests = reviewer.prepare_semantic_review_requests(
        tmp_path, protocol.record_sha256
    )
    result = reviewer.run_semantic_review_synthetic(
        tmp_path,
        protocol.record_sha256,
        response_by_request_sha256={
            key: _supported_fixture(request) for key, request in requests.items()
        },
        qualification_class="SYNTHETIC_FIXTURE_ONLY",
    )
    assert result["complete"]


def test_stage4_entrypoints_do_not_follow_symlinked_fixed_layout_file(tmp_path, monkeypatch):
    _, protocol = _stage3_store(tmp_path)
    external = tmp_path.parent / f"{tmp_path.name}-symlink-layout.yaml"
    external.write_text("not: [valid")
    config = tmp_path / "config"
    config.mkdir(exist_ok=True)
    layout_path = config / "storage_layout.yaml"
    if layout_path.exists() or layout_path.is_symlink():
        layout_path.unlink()
    layout_path.symlink_to(external)
    original = Path.read_text

    def guarded_read(path, *args, **kwargs):
        if path in {layout_path, external}:
            pytest.fail("Stage 4 followed the storage-layout symlink")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read)
    requests = reviewer.prepare_semantic_review_requests(
        tmp_path, protocol.record_sha256
    )
    result = reviewer.run_semantic_review_synthetic(
        tmp_path,
        protocol.record_sha256,
        response_by_request_sha256={
            key: _supported_fixture(request) for key, request in requests.items()
        },
        qualification_class="SYNTHETIC_FIXTURE_ONLY",
    )
    assert result["complete"]


def test_fixture_set_digest_matches_independent_ordered_request_response_formula(tmp_path):
    store, protocol = _stage3_store(
        tmp_path,
        claims=[
            {"byte_start": 0, "byte_end": 5, "quote": "Hello", "source_epistemic_form": "OTHER"},
            {"byte_start": 6, "byte_end": 11, "quote": "world", "source_epistemic_form": "OTHER"},
        ],
    )
    requests = _requests(tmp_path, protocol)
    result = reviewer.run_semantic_review_synthetic(
        tmp_path,
        protocol.record_sha256,
        response_by_request_sha256={
            key: _supported_fixture(request) for key, request in requests.items()
        },
        qualification_class="SYNTHETIC_FIXTURE_ONLY",
    )
    receipt = reviewer._parse_receipt(
        result["receipt_refs"][0], store.records(), store.verify_artifact
    )
    projection = [
        {
            "request_sha256": item.request_sha256,
            "fixture_response_sha256": item.fixture_response_sha256,
        }
        for item in receipt.fresh_fixture_bindings
    ]
    persisted_projection = [
        item.model_dump(mode="json") for item in receipt.request_response_bindings
    ]
    assert projection == persisted_projection
    assert receipt.fixture_set_sha256 == model.sha(canonical_json_bytes(projection))
    for binding in receipt.fresh_fixture_bindings:
        response = store.verify_artifact(
            binding.fixture_response_sha256, kind="codex-io"
        )
        assert len(response) == binding.fixture_response_byte_count
        assert model.sha(response) == binding.fixture_response_sha256


def test_rehashed_receipt_with_fresh_binding_digest_formula_is_rejected(tmp_path):
    store, protocol = _stage3_store(tmp_path)
    result = _run(tmp_path, protocol, _semantic_envelope())
    original_sha = result["receipt_refs"][0]
    receipt = reviewer._parse_receipt(
        original_sha, store.records(), store.verify_artifact
    )
    material = receipt.model_dump(mode="json", by_alias=True)
    material.pop("receipt_sha256")
    material["fixture_set_sha256"] = model.sha(
        canonical_json_bytes(
            [item.model_dump(mode="json") for item in receipt.fresh_fixture_bindings]
        )
    )
    material["receipt_sha256"] = model.sha(
        canonical_json_bytes(material, trailing_lf=False)
    )
    forged = reviewer.SyntheticSemanticQualificationReceiptV1.model_validate(material)
    forged_sha = store.put_artifact(canonical_json_bytes(forged), kind="codex-io")
    records = store.records()
    prepared = reviewer._prepare_plan(protocol, records, store.verify_artifact)[0]
    input_sha = store.put_artifact(
        reviewer._input_manifest(prepared, forged_sha), kind="codex-io"
    )
    boundary_sha = store.put_artifact(
        reviewer._boundary_manifest(prepared, forged_sha), kind="codex-io"
    )

    def rebind_forged_receipt(record):
        if record.get("attempt_id", "").startswith(model.ATTEMPT_PREFIX):
            record["input_manifest_sha256"] = input_sha
            record["workspace_manifest_sha256"] = boundary_sha

    _rewrite_valid_hash_chains(tmp_path, rebind_forged_receipt)
    with pytest.raises(LiteratureIntegrityError, match="fixture-set hash mismatch"):
        LiteratureStore(tmp_path).validate()
