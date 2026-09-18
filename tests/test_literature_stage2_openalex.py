from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from alphaquest.research.literature import stage2_policy as policy
from alphaquest.research.literature import stage2_runner as runner
from alphaquest.research.literature.contracts import SearchRunRevisionV1, SourceCaptureRevisionV1
from alphaquest.research.literature.providers import openalex as oa
from alphaquest.research.literature.store import LiteratureStore
from tests.test_literature_stage1 import _actor, _project, _protocol_payload, NOW


def _work(n=1, *, abstract=True, doi=True):
    return dict(
        id=f"https://openalex.org/W{n}",
        doi=f"https://doi.org/10.1234/example.{n}" if doi else None,
        display_name=f"Example {n}",
        publication_date="2020-02-29",
        authorships=[{"author": {"display_name": "Test Author"}}],
        abstract_inverted_index={"world": [1], "Hello": [0]} if abstract else None,
    )


def _body(*works):
    return json.dumps({"results": list(works)}).encode()


def _response(body, status=200, **headers):
    return httpx.Response(
        status, headers={"content-type": "application/json", **headers}, stream=httpx.ByteStream(body)
    )


def _protocol(store, **changes):
    payload = _protocol_payload()
    for lane in payload["lanes"]:
        lane.update(
            provider_order=["openalex"],
            maximum_queries=1,
            adaptive_max_depth=0,
            saturation=None,
            maximum_bytes=2 * oa.MAX_BODY_BYTES,
            maximum_elapsed_seconds=60,
        )
    payload["lanes"][0].update(changes)
    return store.append_protocol(payload, actor=_actor(), idempotency_key="pilot.protocol", recorded_at=NOW)


@pytest.fixture
def store(tmp_path):
    return LiteratureStore(_project(tmp_path))


@pytest.mark.parametrize(
    "changes",
    [
        dict(provider_order=["openalex", "other"]),
        dict(provider_order=["other"]),
        dict(adaptive_max_depth=1),
        dict(required_initial_queries=["a", "b"], maximum_queries=2),
        dict(minimum_results_inspected_per_query=11, maximum_results=20),
        dict(minimum_distinct_results_inspected=11, maximum_results=20),
        dict(minimum_capture_attempts=11, maximum_captures=11, maximum_results=20),
        dict(minimum_provider_attempts=2),
    ],
)
def test_unsupported_protocol_never_dispatches(store, changes):
    protocol = _protocol(store, **changes)

    def forbidden(request):
        pytest.fail("unsupported protocol dispatched")

    with pytest.raises(policy.Stage2UnsupportedProfile):
        runner.run_openalex_pilot(store.project_root, protocol.record_sha256, _transport=httpx.MockTransport(forbidden))
    assert len(store.records()) == 1


def test_fixed_request_transport_and_body_limit(monkeypatch):
    captured = {}
    original = httpx.Client

    def client(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(httpx, "Client", client)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("SSL_CERT_FILE", "/not/a/certificate")
    calls = []
    body = b" " * oa.MAX_BODY_BYTES

    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        assert request.url.scheme == "https" and request.url.host == "api.openalex.org"
        assert request.url.path == "/works"
        assert request.url.params["search"] == "a & b/雪"
        assert request.url.params["per_page"] == "3"
        assert set(request.headers) == {"host", "accept", "accept-encoding"}
        return _response(body)

    assert (
        oa.fetch("a & b/雪", 3, byte_limit=oa.MAX_BODY_BYTES, elapsed_limit=60, transport=httpx.MockTransport(handler))
        == body
    )
    assert len(calls) == 1
    assert captured["trust_env"] is False and captured["verify"] is True and captured["follow_redirects"] is False
    assert captured["timeout"].connect == 5 and captured["timeout"].read == 10
    assert captured["limits"].max_connections == 1
    assert str(calls[0].url) == oa.request_url("a & b/雪", 3)


@pytest.mark.parametrize("status", [301, 302, 307, 429, 500, 503])
def test_http_errors_redirects_never_retry(status):
    calls = []

    def handler(request):
        calls.append(request)
        return _response(b"", status, location="http://127.0.0.1/private")

    with pytest.raises(oa.OpenAlexError, match=f"HTTP {status}"):
        oa.fetch("query", 1, byte_limit=1024, elapsed_limit=60, transport=httpx.MockTransport(handler))
    assert len(calls) == 1


@pytest.mark.parametrize(
    "headers,body",
    [({}, b"x" * 1025), ({"content-encoding": "gzip"}, b"fake"), ({"content-type": "text/html"}, b"<html>")],
)
def test_response_bounds(headers, body):
    with pytest.raises(oa.OpenAlexError):
        oa.fetch(
            "query",
            1,
            byte_limit=1024,
            elapsed_limit=60,
            transport=httpx.MockTransport(lambda _: _response(body, **headers)),
        )


@pytest.mark.parametrize(
    "body",
    [
        b"{",
        b"[]",
        b'{"results":{}}',
        b'{"results":[1]}',
        b'{"results":[],"results":[]}',
        b'{"results":[],"meta":NaN}',
        _body(_work(), _work(2)),
    ],
)
def test_malformed_or_oversized_results(body):
    with pytest.raises(oa.OpenAlexError):
        oa.normalize(body, 1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "http://127.0.0.1/W1"),
        ("id", "../../file"),
        ("display_name", 3),
        ("display_name", "\ud800"),
        ("doi", "https://evil.test/10.1234/x"),
        ("authorships", "author"),
        ("publication_date", "2020-99-99"),
    ],
)
def test_untrusted_result_fields(field, value):
    work = _work()
    work[field] = value
    with pytest.raises(oa.OpenAlexError):
        oa.normalize(_body(work), 1)


def test_deterministic_normalization_doi_and_no_doi():
    body = _body(_work(), _work(2, doi=False, abstract=False))
    first, second = oa.normalize(body, 2)
    assert oa.normalize(body, 2) == (first, second)
    assert first.abstract == b"Hello world"
    assert second.abstract is None and not second.abstract_error
    assert first.inspection.canonical_locator == "https://doi.org/10.1234/example.1"
    assert second.inspection.canonical_locator == "https://openalex.org/W2"
    assert [first.inspection.result_rank, second.inspection.result_rank] == [1, 2]
    assert first.inspection.provider_rank == second.inspection.provider_rank == 1
    with pytest.raises(oa.OpenAlexError, match="duplicate"):
        oa.normalize(_body(_work(), _work()), 2)


@pytest.mark.parametrize(
    "index", [{}, {"a": [1]}, {"a": [0], "b": [0]}, {"a": [True]}, {"a": [-1]}, {"a": [0, 16384]}, {"a": "0"}, ["x"]]
)
def test_malformed_abstract_fails_only_that_capture(index):
    work = _work()
    work["abstract_inverted_index"] = index
    (result,) = oa.normalize(_body(work), 1)
    assert result.abstract is None and result.abstract_error
    assert result.inspection.result_rank == 1


def test_full_seven_lane_workflow_real_store_and_no_redispatch(store, monkeypatch):
    protocol = _protocol(store)
    calls = []
    plans = []
    real_plan = policy.plan_publication
    real_capture = LiteratureStore.append_capture

    def observe_plan(*args, **kwargs):
        plan = real_plan(*args, **kwargs)
        plans.append(plan)
        return plan

    def require_current_plan(self, payload, **kwargs):
        head = self.records()[-1]
        plan = plans[-1]
        assert (head.append_sequence, head.record_sha256) == (
            plan.snapshot_append_sequence,
            plan.snapshot_head_record_sha256,
        )
        assert payload["capture_id"] in {a.capture_attempt_id for a in plan.next_capture_attempts}
        return real_capture(self, payload, **kwargs)

    monkeypatch.setattr(policy, "plan_publication", observe_plan)
    monkeypatch.setattr(LiteratureStore, "append_capture", require_current_plan)

    def handler(request):
        records = store.records()
        active = [r for r in records if isinstance(r, SearchRunRevisionV1)][-1]
        assert active.status == "STARTED"
        assert request.url.params["search"] == active.query
        calls.append(request)
        return _response(_body(_work(), _work(2, abstract=False)))

    result = runner.run_openalex_pilot(
        store.project_root, protocol.record_sha256, _transport=httpx.MockTransport(handler)
    )
    assert result["complete"] and len(calls) == 7
    assert store.validate()["status"] == "PASS"
    captures = [r for r in store.records() if isinstance(r, SourceCaptureRevisionV1)]
    assert len(captures) == 14
    assert {r.status for r in captures} == {"GENUINE_ABSTRACT_CAPTURED", "LOCATOR_METADATA_ONLY"}
    assert all(r.external_model_processing_permission == "LOCAL_ONLY" for r in captures)
    for capture in captures:
        if capture.status == "GENUINE_ABSTRACT_CAPTURED":
            assert store.verify_artifact(capture.extracted_representation_sha256, kind="extracted") == b"Hello world"
    with pytest.raises(runner.PilotManualReconciliation, match="no redispatch"):
        runner.run_openalex_pilot(store.project_root, protocol.record_sha256, _transport=httpx.MockTransport(handler))
    assert len(calls) == 7


@pytest.mark.parametrize("failure", ["timeout", 429, 500])
def test_failed_dispatch_terminalizes_once_and_does_not_retry(store, failure):
    protocol = _protocol(store)
    calls = []

    def handler(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("test", request=request)
        return _response(b"", failure)

    result = runner.run_openalex_pilot(
        store.project_root, protocol.record_sha256, _transport=httpx.MockTransport(handler)
    )
    assert not result["complete"] and len(calls) == 1
    assert result["searches"][0]["status"] == "FAILED"
    assert store.validate()["status"] == "PASS"
    with pytest.raises(runner.PilotManualReconciliation):
        runner.run_openalex_pilot(store.project_root, protocol.record_sha256, _transport=httpx.MockTransport(handler))
    assert len(calls) == 1


def test_crash_leaves_started_and_restart_never_redispatches(store):
    protocol = _protocol(store)
    calls = []

    def crash(request):
        calls.append(request)
        raise RuntimeError("simulated controller crash")

    with pytest.raises(RuntimeError, match="controller crash"):
        runner.run_openalex_pilot(store.project_root, protocol.record_sha256, _transport=httpx.MockTransport(crash))
    assert store.records()[-1].status == "STARTED"
    with pytest.raises(runner.PilotManualReconciliation):
        runner.run_openalex_pilot(store.project_root, protocol.record_sha256, _transport=httpx.MockTransport(crash))
    assert len(calls) == 1


def test_f4_rejects_before_network_and_before_capture(store, monkeypatch):
    protocol = _protocol(store)
    original = policy.plan_publication
    calls = []

    def reject(store, sha, proposals):
        plan = original(store, sha, proposals)
        return replace(
            plan, status="UNSUPPORTED_PUBLICATION_SCHEDULE", steps=(), next_capture_attempts=(), reason="test"
        )

    monkeypatch.setattr(policy, "plan_publication", reject)
    with pytest.raises(runner.PilotManualReconciliation, match="F4 rejected"):
        runner.run_openalex_pilot(
            store.project_root,
            protocol.record_sha256,
            _transport=httpx.MockTransport(lambda request: calls.append(request)),
        )
    assert not calls
    assert not any(isinstance(r, SourceCaptureRevisionV1) for r in store.records())


def test_f4_post_response_rejection_retains_no_capture(store, monkeypatch):
    protocol = _protocol(store)
    original = policy.plan_publication

    def reject_actual(store, sha, proposals):
        plan = original(store, sha, proposals)
        if proposals[0].terminal.inspected_results:
            return replace(
                plan, status="UNSUPPORTED_PUBLICATION_SCHEDULE", steps=(), next_capture_attempts=(), reason="test"
            )
        return plan

    monkeypatch.setattr(policy, "plan_publication", reject_actual)
    with pytest.raises(runner.PilotManualReconciliation):
        runner.run_openalex_pilot(
            store.project_root,
            protocol.record_sha256,
            _transport=httpx.MockTransport(lambda _: _response(_body(_work()))),
        )
    assert store.records()[-1].status == "STARTED"
    assert not (store.layout.literature_runtime_root / "artifacts").exists()


def test_frozen_prefix_does_not_skip_missing_abstract(store):
    protocol = _protocol(store, maximum_captures=1)
    runner.run_openalex_pilot(
        store.project_root,
        protocol.record_sha256,
        _transport=httpx.MockTransport(lambda _: _response(_body(_work(abstract=False), _work(2)))),
    )
    first_search = next(r for r in store.records() if isinstance(r, SearchRunRevisionV1) and r.status == "SUCCEEDED")
    assert len(first_search.capture_attempt_records) == 1
    capture = store.latest(SourceCaptureRevisionV1, first_search.capture_attempt_records[0].capture_attempt_id)
    assert capture.status == "LOCATOR_METADATA_ONLY"


def test_unmet_result_minimum_is_a_declared_gap(store):
    protocol = _protocol(store)
    result = runner.run_openalex_pilot(
        store.project_root, protocol.record_sha256, _transport=httpx.MockTransport(lambda _: _response(_body()))
    )
    assert not result["complete"]
    assert all(x["gap_reason"] == "FROZEN_MINIMUM_NOT_MET" for x in result["lane_completions"])


def test_pnl_noninterference_request_and_decision(tmp_path, monkeypatch):
    from alphaquest.research.edge_backlog import EdgeBacklogStore

    def forbidden(*args, **kwargs):
        pytest.fail("pilot reached P2 historical authority")

    monkeypatch.setattr(EdgeBacklogStore, "__init__", forbidden)
    requests, decisions, snapshots = [], [], []
    for index in range(2):
        root = tmp_path / str(index)
        root.mkdir()
        store = LiteratureStore(_project(root))
        protocol = _protocol(store)
        snapshots.append(protocol.model_dump_json())
        for relative in [
            "research/results/output.json",
            "research/evidence/trades.csv",
            "research_artifacts/reset.json",
            "backtest-campaigns/example/research_ledger.csv",
        ]:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"unrelated pnl {index}")
        calls = []

        def handler(request):
            calls.append(str(request.url))
            return _response(_body(_work()))

        result = runner.run_openalex_pilot(root, protocol.record_sha256, _transport=httpx.MockTransport(handler))
        requests.append(calls)
        assert result["complete"]
        decisions.append(
            [
                (r.status, r.inspected_results, r.capture_attempt_records)
                for r in store.records()
                if isinstance(r, SearchRunRevisionV1) and r.status != "STARTED"
            ]
        )
    assert snapshots[0] == snapshots[1]
    assert requests[0] == requests[1] and decisions[0] == decisions[1]


def test_real_f4_rejects_reordered_result_prefix(store, monkeypatch):
    protocol = _protocol(store)
    normalize = oa.normalize
    monkeypatch.setattr(oa, "normalize", lambda body, limit: tuple(reversed(normalize(body, limit))))
    with pytest.raises(runner.PilotManualReconciliation, match="F4 rejected"):
        runner.run_openalex_pilot(
            store.project_root,
            protocol.record_sha256,
            _transport=httpx.MockTransport(lambda _: _response(_body(_work(), _work(2)))),
        )
    assert store.records()[-1].status == "STARTED"
    assert not (store.layout.literature_runtime_root / "artifacts").exists()


def test_canonical_append_during_request_stales_authority(store):
    protocol = _protocol(store)

    def handler(request):
        store.append_work(
            dict(
                work_id="unrelated.work",
                source_category="OTHER",
                title="unrelated",
                authors=[],
                locators=["https://example.test/work"],
                identity_status="PROVISIONAL",
                change_reason="concurrent write",
            ),
            actor=_actor(),
            idempotency_key="unrelated.work",
        )
        return _response(_body(_work()))

    with pytest.raises(runner.PilotManualReconciliation, match="state changed"):
        runner.run_openalex_pilot(store.project_root, protocol.record_sha256, _transport=httpx.MockTransport(handler))
    assert not (store.layout.literature_runtime_root / "artifacts").exists()


def test_existing_emission_rejected_before_external_authority(store, monkeypatch):
    from alphaquest.research.edge_backlog import EdgeBacklogStore
    from tests.test_literature_stage1 import _initial_slice

    _initial_slice(store.project_root)
    protocol = _protocol(store)

    def forbidden(*args, **kwargs):
        pytest.fail("pilot reached external P2 authority or transport")

    monkeypatch.setattr(EdgeBacklogStore, "__init__", forbidden)
    with pytest.raises(policy.Stage2UnsupportedProfile, match="without P2 emissions"):
        runner.run_openalex_pilot(store.project_root, protocol.record_sha256, _transport=httpx.MockTransport(forbidden))


def test_concurrent_pilot_invocations_cannot_double_dispatch(store):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    protocol = _protocol(store)
    entered, release = Event(), Event()
    calls = []

    def handler(request):
        calls.append(request)
        entered.set()
        assert release.wait(5)
        return _response(b"", 500)

    def run():
        return runner.run_openalex_pilot(
            store.project_root, protocol.record_sha256, _transport=httpx.MockTransport(handler)
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(run)
        assert entered.wait(5)
        second = executor.submit(run)
        release.set()
        assert not first.result(timeout=10)["complete"]
        with pytest.raises(runner.PilotManualReconciliation):
            second.result(timeout=10)
    assert len(calls) == 1


def test_malformed_abstract_is_failed_capture_not_genuine_evidence(store):
    protocol = _protocol(store)
    work = _work()
    work["abstract_inverted_index"] = {"gap": [3]}
    runner.run_openalex_pilot(
        store.project_root, protocol.record_sha256, _transport=httpx.MockTransport(lambda _: _response(_body(work)))
    )
    captures = [r for r in store.records() if isinstance(r, SourceCaptureRevisionV1)]
    assert len(captures) == 7 and all(r.status == "FAILED" for r in captures)
    assert all(r.content_sha256 is None for r in captures)
    assert not (store.layout.literature_runtime_root / "artifacts").exists()


def test_oversized_json_integer_is_a_provider_failure():
    body = b'{"results":[],"meta":' + b"9" * 5000 + b"}"
    with pytest.raises(oa.OpenAlexError, match="malformed OpenAlex JSON"):
        oa.normalize(body, 1)


class _FragmentStream(httpx.SyncByteStream):
    """Expose actual delivery boundaries, including errors after partial bodies."""

    def __init__(self, fragments, *, error=None, on_fragment=None):
        self.fragments = fragments
        self.error = error
        self.on_fragment = on_fragment
        self.delivered_bytes = 0
        self.fragments_delivered = 0
        self.error_reached = False
        self.closed = False

    def __iter__(self):
        for fragment in self.fragments:
            if self.on_fragment is not None:
                self.on_fragment()
            self.delivered_bytes += len(fragment)
            self.fragments_delivered += 1
            yield fragment
        if self.error is not None:
            self.error_reached = True
            raise self.error

    def close(self):
        self.closed = True


def _fetch_stream(stream, *, byte_limit=50, elapsed_limit=60):
    return oa.fetch(
        "frozen query",
        1,
        byte_limit=byte_limit,
        elapsed_limit=elapsed_limit,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, headers={"content-type": "application/json"}, stream=stream)
        ),
    )


@pytest.mark.parametrize("budget,fragment_size", [(50, 1), (50, 7), (oa.MAX_BODY_BYTES, 8192)])
def test_oa1_fragmented_valid_body_at_exact_frozen_limit(budget, fragment_size):
    body = b'{"results":[]}'.ljust(budget)
    stream = _FragmentStream([body[i : i + fragment_size] for i in range(0, len(body), fragment_size)])
    received = _fetch_stream(stream, byte_limit=budget)
    assert received == body and oa.normalize(received, 1) == ()
    assert stream.delivered_bytes == budget and stream.closed


@pytest.mark.parametrize(
    "budget,fragments,expected",
    [
        (50, [b"x" * 50, b"x"], 51),
        (50, [b"x"] * 51, 51),
        (50, [b"x" * 100], 100),
        (oa.MAX_BODY_BYTES, [b"x" * 8192] * 128 + [b"x"], oa.MAX_BODY_BYTES + 1),
    ],
    ids=["limit-plus-one", "one-byte-fragments", "audit-100-with-budget-50", "one-mib-plus-one"],
)
def test_oa1_overrun_stops_at_first_excess_fragment_before_later_timeout(budget, fragments, expected):
    stream = _FragmentStream(fragments, error=httpx.ReadTimeout("must not reach next read"))
    with pytest.raises(oa.OpenAlexError, match="exceeds byte bound") as caught:
        _fetch_stream(stream, byte_limit=budget)
    assert caught.value.bytes_received == stream.delivered_bytes == expected
    assert stream.fragments_delivered == len(fragments)
    assert not stream.error_reached and stream.closed


@pytest.mark.parametrize(
    "error_type", [httpx.ReadTimeout, httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError, httpx.StreamError]
)
def test_oa1_fragmented_transport_error_preserves_twenty_delivered_bytes(error_type):
    stream = _FragmentStream([b"x" * 3, b"x" * 7, b"x" * 10], error=error_type("partial response"))
    with pytest.raises(oa.OpenAlexError, match="transport failed; no retry") as caught:
        _fetch_stream(stream)
    assert caught.value.bytes_received == stream.delivered_bytes == 20
    assert isinstance(caught.value.__cause__, error_type)
    assert stream.error_reached and stream.closed


def test_oa1_fragmented_slow_stream_checks_total_deadline_after_each_delivery(monkeypatch):
    clock = [0.0]

    def advance():
        clock[0] += 0.6  # Every fragment arrives within the one-second read timeout.

    monkeypatch.setattr(oa, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    stream = _FragmentStream([b"x"] * 20, on_fragment=advance)
    with pytest.raises(oa.OpenAlexError, match="elapsed budget exceeded") as caught:
        _fetch_stream(stream, elapsed_limit=1)
    assert clock[0] == pytest.approx(1.2)
    assert caught.value.bytes_received == stream.delivered_bytes == 2
    assert stream.fragments_delivered == 2 and stream.closed


@pytest.mark.parametrize("budget,fragment_size", [(50, 100), (oa.MAX_BODY_BYTES, 8192)])
def test_oa1_runner_overrun_keeps_started_without_false_terminal_or_redispatch(store, budget, fragment_size):
    protocol = _protocol(store, maximum_bytes=budget)
    fragments = [b"x" * 100] if budget == 50 else [b"x" * fragment_size] * (budget // fragment_size) + [b"x"]
    stream = _FragmentStream(fragments, error=httpx.ReadTimeout("after overrun"))
    calls = []

    def handler(request):
        assert store.records()[-1].status == "STARTED"
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "application/json"}, stream=stream)

    transport = httpx.MockTransport(handler)
    with pytest.raises(runner.PilotManualReconciliation, match="exceeded frozen budget"):
        runner.run_openalex_pilot(store.project_root, protocol.record_sha256, _transport=transport)
    searches = [record for record in store.records() if isinstance(record, SearchRunRevisionV1)]
    assert len(searches) == 1 and searches[0].status == "STARTED"
    assert stream.delivered_bytes == (100 if budget == 50 else budget + 1)
    assert not stream.error_reached and stream.closed
    assert store.validate()["status"] == "PASS"
    assert not any(isinstance(record, SourceCaptureRevisionV1) for record in store.records())
    with pytest.raises(runner.PilotManualReconciliation, match="no redispatch"):
        runner.run_openalex_pilot(store.project_root, protocol.record_sha256, _transport=transport)
    assert len(calls) == 1


@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ReadError, httpx.StreamError])
def test_oa1_runner_within_budget_failure_publishes_actual_bytes_once(store, error_type):
    protocol = _protocol(store, maximum_bytes=50)
    stream = _FragmentStream([b"x" * 3, b"x" * 7, b"x" * 10], error=error_type("partial response"))
    calls = []

    def handler(request):
        assert store.records()[-1].status == "STARTED"
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "application/json"}, stream=stream)

    transport = httpx.MockTransport(handler)
    result = runner.run_openalex_pilot(store.project_root, protocol.record_sha256, _transport=transport)
    searches = [record for record in store.records() if isinstance(record, SearchRunRevisionV1)]
    assert [record.status for record in searches] == ["STARTED", "FAILED"]
    assert searches[-1].bytes_retrieved == stream.delivered_bytes == 20
    assert stream.error_reached and stream.closed
    assert not result["complete"] and store.validate()["status"] == "PASS"
    with pytest.raises(runner.PilotManualReconciliation, match="no redispatch"):
        runner.run_openalex_pilot(store.project_root, protocol.record_sha256, _transport=transport)
    assert len(calls) == 1


@pytest.mark.parametrize("token", ["1e999", "-1e999", "NaN", "Infinity", "-Infinity"])
def test_oa2_nonfinite_json_numbers_fail_even_in_ignored_metadata(token):
    body = ('{"results":[],"meta":{"x":' + token + "}}").encode()
    with pytest.raises(oa.OpenAlexError, match="malformed OpenAlex JSON"):
        oa.normalize(body, 1)


@pytest.mark.parametrize("token", ["0", "1.5", "-2.5", "1e100", "-1e100", "1e-100"])
def test_oa2_finite_json_numbers_preserve_normalization(token):
    body = ('{"results":[],"meta":{"x":' + token + "}}").encode()
    assert oa.normalize(body, 1) == ()
