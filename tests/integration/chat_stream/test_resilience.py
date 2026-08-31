"""Integration resilience tests for `/chat/stream` SSE behavior.

Test scope:
1. Verify stream completion semantics in normal and failure paths.
2. Verify route-level finalization always clears queue active state.
3. Verify route-level cleanup still happens when side channels fail.

Design notes:
- These tests run in the `integration` layer (not pure unit).
- External/high-variance dependencies are patched for determinism.
- Assertions focus on stream protocol + lifecycle safety, not model quality.
- Scenarios are split into two groups:
  1) real route + fake loop
  2) real route + real loop + fake stream LLM
"""

import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from tests.support.failure_attribution import build_failure_attribution


pytestmark = [pytest.mark.integration]


async def _noop_async(*_args, **_kwargs):
    """Async no-op helper used to silence non-critical side effects."""
    return None


def _make_fake_loop(*chunks: str, error: Exception | None = None):
    """Create a deterministic fake `run_agentic_loop` implementation."""

    async def _loop(
        _messages,
        _session_id,
        max_rounds=5,
        model_override=None,
        tools=None,
        source_agent_id=None,
    ):
        del max_rounds, model_override, tools, source_agent_id
        for chunk in chunks:
            yield chunk
        if error is not None:
            raise error

    return _loop


def _make_slow_fake_loop(*chunks: str, delay_seconds: float = 0.25):
    """Create a fake loop that leaves time for an early client disconnect.

    Purpose:
    - simulate a user stop / client-side stream abort after the first chunk
    - keep later chunks pending long enough for the test to close the stream
    """

    async def _loop(
        _messages,
        _session_id,
        max_rounds=5,
        model_override=None,
        tools=None,
        source_agent_id=None,
    ):
        del max_rounds, model_override, tools, source_agent_id
        for index, chunk in enumerate(chunks):
            yield chunk
            if index == 0:
                await asyncio.sleep(delay_seconds)

    return _loop


class _ChunkedStreamLLM:
    """Simple fake streaming LLM used with the real agentic loop."""

    def __init__(self, *chunks: str):
        self._chunks = chunks

    async def stream_chat_with_context(
        self,
        _messages,
        _temperature=0.7,
        model_override=None,
        tools=None,
        session_id=None,
    ):
        del model_override, tools, session_id
        for chunk in self._chunks:
            yield chunk


def _drain_conversation_active_flag():
    """Best-effort cleanup for singleton queue state leakage across tests.

    `apiserver.message_queue` is process-global in tests. If a previous test
    leaves the conversation flag active, subsequent tests may fail for the
    wrong reason. This helper force-resets the flag before/after each case.
    """
    from apiserver.message_queue import get_message_queue

    mq = get_message_queue()
    # Defensive loop: tolerate internal retries or racey state transitions.
    for _ in range(16):
        if not mq.is_conversation_active():
            break
        mq.set_conversation_active(False)


def _assert_queue_inactive():
    """Common post-condition: stream finalization must release queue active flag."""
    from apiserver.message_queue import get_message_queue

    assert not get_message_queue().is_conversation_active()


def _request_payload():
    """Minimal stable request body for stream route integration tests."""
    return {
        "message": "ping",
        "temporary": True,
        "disable_tts": True,
    }


def _stream_run(client: TestClient, payload: dict | None = None):
    """Run `/chat/stream` once and collect a small deterministic report.

    This keeps the current resilience suite cheap while exposing the minimum
    stream-level metrics we care about in regression tests:
    - `ttfb_ms`
    - `total_latency_ms`
    - `event_count`
    - `done_seen`
    """
    started_at = time.monotonic()
    first_chunk_at = None
    chunks: list[str] = []

    with client.stream("POST", "/chat/stream", json=payload or _request_payload()) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        for text_chunk in response.iter_text():
            if text_chunk and first_chunk_at is None:
                first_chunk_at = time.monotonic()
            chunks.append(text_chunk)

    stream_text = "".join(chunks)
    sse_events = [event.strip() for event in stream_text.split("\n\n") if event.strip()]
    parsed_events = _parse_sse_events(stream_text)
    return SimpleNamespace(
        text=stream_text,
        sse_events=sse_events,
        parsed_events=parsed_events,
        ttfb_ms=None if first_chunk_at is None else int((first_chunk_at - started_at) * 1000),
        total_latency_ms=int((time.monotonic() - started_at) * 1000),
        event_count=len(parsed_events),
        done_seen=any(event["event_type"] == "done" for event in parsed_events),
    )


def _parse_sse_events(stream_text: str):
    """Parse route-level SSE data blocks without assuming HTTP chunk boundaries.

    `TestClient` may coalesce several network writes into one `iter_text()` value.
    The stable application contract is therefore the ordered sequence of SSE
    `data:` events, not the number of transport chunks observed in-process.
    """
    parsed_events = []
    for raw_block in stream_text.split("\n\n"):
        data_lines = [
            line.removeprefix("data: ")
            for line in raw_block.splitlines()
            if line.startswith("data: ")
        ]
        if not data_lines:
            continue

        raw_data = "\n".join(data_lines).strip()
        if raw_data == "[DONE]":
            parsed_events.append({"event_type": "done", "payload": None, "raw": raw_data})
            continue
        if raw_data.startswith("session_id:"):
            parsed_events.append(
                {
                    "event_type": "session_id",
                    "payload": raw_data.partition(":")[2].strip(),
                    "raw": raw_data,
                }
            )
            continue
        if raw_data.startswith("error:"):
            parsed_events.append(
                {
                    "event_type": "error",
                    "payload": raw_data.partition(":")[2].strip(),
                    "raw": raw_data,
                }
            )
            continue

        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError:
            parsed_events.append({"event_type": "unknown", "payload": raw_data, "raw": raw_data})
            continue

        parsed_events.append(
            {
                "event_type": payload.get("type", "unknown"),
                "payload": payload,
                "raw": raw_data,
            }
        )

    return parsed_events


def _assert_sse_terminal_contract(parsed_events, expected_terminal: str):
    """Assert exactly one normal/error terminal and no event after it."""
    assert expected_terminal in {"done", "error"}
    terminal_events = [
        (index, event)
        for index, event in enumerate(parsed_events)
        if event["event_type"] in {"done", "error"}
    ]
    assert len(terminal_events) == 1, terminal_events
    terminal_index, terminal_event = terminal_events[0]
    assert terminal_event["event_type"] == expected_terminal
    assert terminal_index == len(parsed_events) - 1


def _assert_stream_prefix_before_content(parsed_events):
    """Assert session metadata starts the stream and status precedes content."""
    event_types = [event["event_type"] for event in parsed_events]
    assert event_types[0] == "session_id"
    first_content_index = event_types.index("content")
    assert event_types[1:first_content_index]
    assert set(event_types[1:first_content_index]) == {"status"}
    return event_types, first_content_index


def _build_stream_report(stream_env, stream_run):
    """Return a minimal assertion/report payload for SSE resilience tests."""
    # Route emits notify calls via async tasks; wait briefly for event loop flush.
    time.sleep(0.05)
    from apiserver.message_queue import get_message_queue

    return {
        "ttfb_ms": stream_run.ttfb_ms,
        "total_latency_ms": stream_run.total_latency_ms,
        "event_count": stream_run.event_count,
        "done_seen": stream_run.done_seen,
        "finalize_called": stream_env.events.count("ended"),
        "save_call_count": len(stream_env.save_calls),
        "active_cleaned": not get_message_queue().is_conversation_active(),
    }


def _publish_quality_gate_case(
    request,
    *,
    case_id: str,
    blocking: bool,
    attribution: dict | None,
    report: dict,
    story: str = "correctness",
    non_blocking: bool = False,
    reason: str = "",
):
    final_status = "success"
    failure_stage = "none"
    tool_rounds = 0
    tool_count = 0
    if attribution is not None:
        final_status = attribution["final_status"]
        failure_stage = attribution["failure_stage"]
        tool_rounds = int(attribution.get("rounds", 0))
        tool_count = int(attribution.get("tool_call_count", 0))

    request.node.user_properties.append(
        (
            "quality_gate_case",
            {
                "case_id": case_id,
                "feature": "p2_api",
                "story": story,
                "blocking": blocking,
                "non_blocking": non_blocking,
                "final_status": final_status,
                "failure_stage": failure_stage,
                "reason": reason,
                "metrics": {
                    "ttfb_ms": report.get("ttfb_ms"),
                    "total_latency_ms": report.get("total_latency_ms"),
                    "event_count": report.get("event_count"),
                    "tool_rounds": tool_rounds,
                    "tool_count": tool_count,
                    "retry_count": 0,
                    "workflow_timeout_count": 0,
                },
            },
        )
    )


@pytest.fixture
def stream_env(monkeypatch):
    """Build a deterministic stream-test environment around real FastAPI app.

    What this fixture provides:
    - `client`: TestClient bound to the real app/router stack.
    - `events`: captures conversation lifecycle notifications.
    - module handles used by tests for selective monkeypatching.

    Why patch here:
    - Route-adjacent side effects (telemetry/persistence/etc.) are outside the
      resilience assertion scope and can make tests flaky.
    - We keep route control flow intact while stabilizing non-essential IO.
    """
    from apiserver.api_server import app
    import apiserver.routes.chat as chat_routes
    import apiserver.agentic_tool_loop as agentic_tool_loop
    import apiserver.context_compressor as context_compressor
    import apiserver.llm_service as llm_service
    import summer_memory.memory_client as memory_client

    _drain_conversation_active_flag()
    events = []
    save_calls = []

    async def _record_notify(event: str):
        # Keep a local event ledger to validate started/ended lifecycle emits.
        events.append(event)

    def _record_save(session_id, user_message, response_text):
        # Keep persistence observable without touching the real filesystem.
        save_calls.append((session_id, user_message, response_text))

    # Deterministic route setup: lock prompt/context generation to fixed values.
    monkeypatch.setattr(chat_routes, "_build_agent_prompt_context", lambda _agent_id: None)
    monkeypatch.setattr(chat_routes, "build_system_prompt", lambda *args, **kwargs: "INTEG_SYSTEM_PROMPT")
    monkeypatch.setattr(chat_routes, "build_context_supplement", lambda *args, **kwargs: "INTEG_SUPPLEMENT")
    monkeypatch.setattr(chat_routes, "_supports_function_calling", lambda _model_name: False)
    monkeypatch.setattr(memory_client, "get_remote_memory_client", lambda: None)

    # Silence side channels not relevant to protocol/lifecycle assertions.
    monkeypatch.setattr(chat_routes, "_update_proactive_activity_silent", _noop_async)
    monkeypatch.setattr(chat_routes, "_save_conversation_and_logs", _record_save)
    monkeypatch.setattr(chat_routes, "emit_telemetry", lambda *_args, **_kwargs: None)

    # Keep notifications observable for assertions instead of sending externally.
    monkeypatch.setattr(chat_routes, "_notify_conversation_event", _record_notify)

    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            events=events,
            save_calls=save_calls,
            monkeypatch=monkeypatch,
            chat_routes=chat_routes,
            agentic_tool_loop=agentic_tool_loop,
            context_compressor=context_compressor,
            llm_service=llm_service,
        )

    _drain_conversation_active_flag()


def _stream_text(client: TestClient):
    """Run `/chat/stream` once and return concatenated SSE response text.

    The helper enforces baseline transport assumptions for every test:
    - HTTP 200 status
    - `text/event-stream` content type
    """
    return _stream_run(client).text


def _assert_event_type_present(stream_text: str, event_type: str):
    """Assert an SSE payload contains an event type regardless of JSON spacing."""
    assert (
        f'"type":"{event_type}"' in stream_text
        or f'"type": "{event_type}"' in stream_text
    )


class TestChatStreamRouteWithFakeLoop:
    """Real `/chat/stream` route, fake loop: focus on finalize and protocol safety."""

    @pytest.mark.blocking
    def test_chat_stream_resilience_baseline_finishes_and_cleans_state(self, stream_env, request):
        """Happy path: ordered incremental content reaches one final [DONE]."""
        stream_env.monkeypatch.setattr(
            stream_env.agentic_tool_loop,
            "run_agentic_loop",
            _make_fake_loop(
                'data: {"type":"content","text":"baseline-"}\n\n',
                'data: {"type":"content","text":"stream-"}\n\n',
                'data: {"type":"content","text":"ok"}\n\n',
                'data: {"type":"round_end","round":1,"has_more":false}\n\n',
                "data: [DONE]\n\n",
            ),
        )
        stream_run = _stream_run(stream_env.client)
        stream_text = stream_run.text

        event_types, first_content_index = _assert_stream_prefix_before_content(stream_run.parsed_events)
        content_events = [
            event for event in stream_run.parsed_events if event["event_type"] == "content"
        ]
        assert [event["payload"]["text"] for event in content_events] == [
            "baseline-",
            "stream-",
            "ok",
        ]
        assert content_events[0]["payload"]["text"]
        assert event_types[first_content_index:] == [
            "content",
            "content",
            "content",
            "round_end",
            "done",
        ]
        assert event_types.count("round_end") == 1
        _assert_sse_terminal_contract(stream_run.parsed_events, "done")

        report = _build_stream_report(stream_env, stream_run)
        attribution = build_failure_attribution("stream_baseline", stream_run.text, report)
        _publish_quality_gate_case(
            request,
            case_id="stream_baseline",
            blocking=True,
            attribution=attribution,
            report=report,
            story="correctness",
        )
        assert stream_env.events.count("started") == 1
        assert report["finalize_called"] == 1
        assert report["save_call_count"] == 1
        assert stream_env.save_calls[0][2] == "baseline-stream-ok"
        assert report["done_seen"] is True
        assert attribution["final_status"] == "success"
        assert attribution["failure_stage"] == "none"
        assert attribution["unhandled_exception"] is False
        _assert_queue_inactive()

    @pytest.mark.blocking
    def test_chat_stream_resilience_midstream_exception_returns_error_and_cleans_state(self, stream_env, request):
        """Failure path: mid-stream exception must surface error and still finalize."""
        stream_env.monkeypatch.setattr(
            stream_env.agentic_tool_loop,
            "run_agentic_loop",
            _make_fake_loop(
                'data: {"type":"content","text":"partial-before-error"}\n\n',
                error=RuntimeError("midstream boom"),
            ),
        )
        stream_run = _stream_run(stream_env.client)
        stream_text = stream_run.text
        event_types, first_content_index = _assert_stream_prefix_before_content(stream_run.parsed_events)
        report = _build_stream_report(stream_env, stream_run)
        attribution = build_failure_attribution("stream_midstream_exception", stream_run.text, report)
        _publish_quality_gate_case(
            request,
            case_id="stream_midstream_exception",
            blocking=True,
            attribution=attribution,
            report=report,
            story="stability",
        )

        assert "partial-before-error" in stream_text
        assert "data: error:midstream boom" in stream_text
        assert event_types[first_content_index:] == ["content", "error"]
        _assert_sse_terminal_contract(stream_run.parsed_events, "error")
        assert "done" not in event_types
        assert len(stream_env.save_calls) == 0
        assert attribution["final_status"] == "degraded"
        assert attribution["failure_stage"] == "tool_dispatch"
        assert attribution["unhandled_exception"] is False
        _assert_queue_inactive()

    def test_chat_stream_resilience_tool_error_event_still_terminates(self, stream_env, request):
        """Tool error payload is tolerated; stream still reaches terminal [DONE]."""
        stream_env.monkeypatch.setattr(
            stream_env.agentic_tool_loop,
            "run_agentic_loop",
            _make_fake_loop(
                'data: {"type":"tool_calls","calls":[{"agentType":"mcp","service_name":"fake","tool_name":"x"}]}\n\n',
                (
                    'data: {"type":"tool_results","results":[{"service_name":"fake","tool_name":"x",'
                    '"status":"error","result":"failed"}]}\n\n'
                ),
                'data: {"type":"round_end","round":1,"has_more":false}\n\n',
                "data: [DONE]\n\n",
            ),
        )
        stream_run = _stream_run(stream_env.client)
        stream_text = stream_run.text
        report = _build_stream_report(stream_env, stream_run)
        attribution = build_failure_attribution("stream_tool_error_event", stream_text, report)
        _publish_quality_gate_case(
            request,
            case_id="stream_tool_error_event",
            blocking=True,
            attribution=attribution,
            report=report,
            story="stability",
        )

        assert '"type":"tool_results"' in stream_text
        assert '"status":"error"' in stream_text
        assert "data: [DONE]" in stream_text
        assert len(stream_env.save_calls) == 1
        _assert_queue_inactive()

    def test_chat_stream_resilience_notify_failure_does_not_block_finalization(self, stream_env, request):
        """Notification side-channel failure must not block stream finalization."""

        async def _notify_boom(_event):
            raise RuntimeError("notify failed")

        stream_env.monkeypatch.setattr(
            stream_env.agentic_tool_loop,
            "run_agentic_loop",
            _make_fake_loop(
                'data: {"type":"content","text":"notify-failure-safe"}\n\n',
                'data: {"type":"round_end","round":1,"has_more":false}\n\n',
                "data: [DONE]\n\n",
            ),
        )
        stream_env.monkeypatch.setattr(stream_env.chat_routes, "_notify_conversation_event", _notify_boom)
        stream_run = _stream_run(stream_env.client)
        stream_text = stream_run.text
        report = _build_stream_report(stream_env, stream_run)
        attribution = build_failure_attribution("stream_notify_failure", stream_text, report)
        _publish_quality_gate_case(
            request,
            case_id="stream_notify_failure",
            blocking=True,
            attribution=attribution,
            report=report,
            story="stability",
        )

        assert "notify-failure-safe" in stream_text
        assert "data: [DONE]" in stream_text
        assert len(stream_env.save_calls) == 1
        _assert_queue_inactive()

    def test_chat_stream_resilience_empty_output_still_finalizes(self, stream_env, request):
        """Gap case: even empty assistant output should still finalize coherently."""
        stream_env.monkeypatch.setattr(
            stream_env.agentic_tool_loop,
            "run_agentic_loop",
            _make_fake_loop(
                'data: {"type":"round_end","round":1,"has_more":false}\n\n',
                "data: [DONE]\n\n",
            ),
        )
        stream_run = _stream_run(stream_env.client)
        report = _build_stream_report(stream_env, stream_run)
        attribution = build_failure_attribution("stream_empty_output", stream_run.text, report)
        _publish_quality_gate_case(
            request,
            case_id="stream_empty_output",
            blocking=True,
            attribution=attribution,
            report=report,
            story="correctness",
        )

        assert "data: session_id:" in stream_run.text
        assert report["done_seen"] is True
        assert report["finalize_called"] == 1
        assert report["save_call_count"] == 1
        assert report["active_cleaned"] is True
        assert stream_env.save_calls[0][2] == ""
        _assert_queue_inactive()

    @pytest.mark.xfail(
        reason="runtime has no explicit user-stop contract yet; keep this as an executable gap",
        strict=False,
    )
    def test_chat_stream_user_stop_contract_gap(self, stream_env):
        """Executable gap for future user-stop semantics.

        Desired contract:
        1. early client disconnect is treated as a user stop / aborted stream
        2. route finalize still executes and releases active state
        3. the stream does not silently continue into a normal saved completion
        """
        stream_env.monkeypatch.setattr(
            stream_env.agentic_tool_loop,
            "run_agentic_loop",
            _make_slow_fake_loop(
                'data: {"type":"content","text":"before-user-stop"}\n\n',
                'data: {"type":"round_end","round":1,"has_more":false}\n\n',
                "data: [DONE]\n\n",
            ),
        )

        with stream_env.client.stream("POST", "/chat/stream", json=_request_payload()) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            first_piece = next(response.iter_text())
            assert first_piece
            assert "session_id" in first_piece or "status" in first_piece or "before-user-stop" in first_piece
            # Context exit closes the stream early and acts as the current best
            # approximation of "user stop" in in-process tests.

        time.sleep(0.35)
        report = _build_stream_report(stream_env, SimpleNamespace(
            text=first_piece,
            sse_events=[first_piece],
            ttfb_ms=None,
            total_latency_ms=0,
            event_count=1,
            done_seen=False,
        ))

        # Target contract we want after runtime support exists.
        assert report["done_seen"] is False
        assert report["finalize_called"] == 1
        assert report["save_call_count"] == 0
        assert report["active_cleaned"] is True


class TestChatStreamRouteWithRealLoopAndFakeLLM:
    """Real route + real loop, but fake LLM: focus on loop-adjacent fallback paths."""

    def test_chat_stream_real_loop_with_fake_llm_finishes_and_cleans_state(self, stream_env, request):
        """Keep the real loop and prove the happy-path protocol stays coherent."""
        stream_env.monkeypatch.setattr(
            stream_env.llm_service,
            "get_llm_service",
            lambda: _ChunkedStreamLLM(
                'data: {"type":"content","text":"real-loop-safe-ok"}\n\n',
                "data: [DONE]\n\n",
            ),
        )
        stream_run = _stream_run(stream_env.client)
        stream_text = stream_run.text
        report = _build_stream_report(stream_env, stream_run)
        attribution = build_failure_attribution("stream_real_loop_fake_llm", stream_text, report)
        _publish_quality_gate_case(
            request,
            case_id="stream_real_loop_fake_llm",
            blocking=False,
            attribution=attribution,
            report=report,
            story="correctness",
        )

        assert "real-loop-safe-ok" in stream_text
        _assert_event_type_present(stream_text, "round_end")
        assert "data: [DONE]" in stream_text
        assert len(stream_env.save_calls) == 1
        _assert_queue_inactive()

    def test_chat_stream_resilience_compress_failure_does_not_break_stream(self, stream_env, request):
        """Context compression failure should degrade gracefully, not break stream."""

        async def _compress_boom(_messages):
            raise RuntimeError("compress failed")

        stream_env.monkeypatch.setattr(
            stream_env.llm_service,
            "get_llm_service",
            lambda: _ChunkedStreamLLM(
                'data: {"type":"content","text":"compress-safe-ok"}\n\n',
                "data: [DONE]\n\n",
            ),
        )
        stream_env.monkeypatch.setattr(stream_env.context_compressor, "compress_context", _compress_boom)
        # Keep the real loop to exercise route -> loop -> compress fallback integration.
        stream_run = _stream_run(stream_env.client)
        stream_text = stream_run.text
        report = _build_stream_report(stream_env, stream_run)
        attribution = build_failure_attribution("stream_compress_failure", stream_text, report)
        _publish_quality_gate_case(
            request,
            case_id="stream_compress_failure",
            blocking=True,
            attribution=attribution,
            report=report,
            story="stability",
        )

        assert "compress-safe-ok" in stream_text
        _assert_event_type_present(stream_text, "round_end")
        assert "data: [DONE]" in stream_text
        assert len(stream_env.save_calls) == 1
        _assert_queue_inactive()
