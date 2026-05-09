"""Unit tests for loop-level failure-attribution contract.

These tests keep the real `run_agentic_loop(...)` orchestration path and assert
that loop output can be projected into a stable attribution payload.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import apiserver.agentic_tool_loop as loop_module
import apiserver.context_compressor as context_compressor
import apiserver.llm_service as llm_service
import apiserver.message_queue as message_queue
from tests.support.agentic_tool_loop_helpers import (
    EmptyQueueStub,
    ScriptedStreamLLM,
    native_tool_call_chunk,
    sse,
    sse_done,
)
from tests.support.failure_attribution import (
    assert_failure_attribution_shape,
    build_failure_attribution,
)


pytestmark = [pytest.mark.unit]


async def _collect_loop_text(
    messages: list[dict[str, Any]],
    *,
    max_rounds: int,
    tools: list[dict[str, Any]] | None,
) -> str:
    chunks: list[str] = []
    async for chunk in loop_module.run_agentic_loop(
        messages,
        session_id="loop-attr-unit",
        max_rounds=max_rounds,
        tools=tools,
    ):
        chunks.append(chunk)
    return "".join(chunks)


def _report_for_loop_text(stream_text: str) -> dict[str, Any]:
    """Build route-like minimal report fields from loop output text."""
    sse_events = [event.strip() for event in stream_text.split("\n\n") if event.strip()]
    return {
        "ttfb_ms": 0,
        "total_latency_ms": 0,
        "event_count": len(sse_events),
        "done_seen": "data: [DONE]" in stream_text,
        "finalize_called": 1,
        "save_call_count": 0,
        "active_cleaned": True,
    }


def _publish_quality_gate_case(request, *, case_id: str, payload: dict[str, Any], report: dict[str, Any]):
    request.node.user_properties.append(
        (
            "quality_gate_case",
            {
                "case_id": case_id,
                "feature": "agentic_tool_loop",
                "story": "correctness",
                "blocking": True,
                "final_status": payload["final_status"],
                "failure_stage": payload["failure_stage"],
                "metrics": {
                    "ttfb_ms": report["ttfb_ms"],
                    "total_latency_ms": report["total_latency_ms"],
                    "event_count": report["event_count"],
                    "tool_rounds": payload["rounds"],
                    "tool_count": payload["tool_call_count"],
                    "retry_count": 0,
                    "workflow_timeout_count": 0,
                },
            },
        )
    )


@pytest.fixture
def loop_attr_env(monkeypatch):
    """Deterministic loop harness shared by failure-attribution tests."""

    async def _compress_passthrough(messages):
        return context_compressor.CompressResult(
            messages=messages,
            sse_events=[],
            compressed=False,
        )

    monkeypatch.setattr(
        loop_module,
        "get_config",
        lambda: SimpleNamespace(api=SimpleNamespace(temperature=0.0)),
    )
    monkeypatch.setattr(context_compressor, "compress_context", _compress_passthrough)
    monkeypatch.setattr(message_queue, "get_message_queue", lambda: EmptyQueueStub())

    return SimpleNamespace(
        monkeypatch=monkeypatch,
        llm_service_module=llm_service,
    )


@pytest.mark.asyncio
async def test_loop_failure_attribution_success_contract(loop_attr_env, request):
    """Happy path should map to `final_status=success` + `failure_stage=none`.

    Test path:
    1. Fake LLM emits one normal content round and `[DONE]`.
    2. The real loop produces a normal terminal stream.
    3. The stream text is projected into a route-like report.
    4. `build_failure_attribution(...)` should classify the run as success.
    """
    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                sse({"type": "content", "text": "plain answer"}),
                sse_done(),
            ]
        ]
    )
    loop_attr_env.monkeypatch.setattr(loop_attr_env.llm_service_module, "get_llm_service", lambda: llm)

    stream_text = await _collect_loop_text(
        messages=[{"role": "user", "content": "hello"}],
        max_rounds=3,
        tools=[{"type": "function", "function": {"name": "tool__web_search"}}],
    )
    report = _report_for_loop_text(stream_text)
    payload = build_failure_attribution(
        "loop_attr_success",
        stream_text,
        report,
    )
    _publish_quality_gate_case(
        request,
        case_id="loop_attr_success",
        payload=payload,
        report=report,
    )

    assert payload["final_status"] == "success"
    assert payload["failure_stage"] == "none"
    assert payload["rounds"] == 1
    assert payload["unhandled_exception"] is False
    assert_failure_attribution_shape(payload)


@pytest.mark.asyncio
async def test_loop_failure_attribution_dispatch_error_contract(loop_attr_env, request):
    """Error-event stream should map to degraded + `tool_dispatch` stage.

    Test path:
    1. Fake LLM emits a non-JSON `error:` SSE line.
    2. The real loop passes that stream through.
    3. The attribution helper reads the final stream text.
    4. The run should be classified as degraded at `tool_dispatch`.
    """
    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                "data: error:dispatch boom\n\n",
            ]
        ]
    )
    loop_attr_env.monkeypatch.setattr(loop_attr_env.llm_service_module, "get_llm_service", lambda: llm)

    stream_text = await _collect_loop_text(
        messages=[{"role": "user", "content": "trigger error event"}],
        max_rounds=3,
        tools=None,
    )
    report = _report_for_loop_text(stream_text)
    payload = build_failure_attribution(
        "loop_attr_dispatch_error",
        stream_text,
        report,
    )
    _publish_quality_gate_case(
        request,
        case_id="loop_attr_dispatch_error",
        payload=payload,
        report=report,
    )

    assert "data: error:dispatch boom" in stream_text
    assert payload["final_status"] == "degraded"
    assert payload["failure_stage"] == "tool_dispatch"
    assert payload["unhandled_exception"] is False
    assert_failure_attribution_shape(payload)


@pytest.mark.asyncio
async def test_loop_failure_attribution_summary_round_contract(loop_attr_env, request):
    """Repeated failures triggering summary should be expressible as `summary_round`.

    Test path:
    1. Round 1 emits a native tool call and dispatcher returns error.
    2. Round 2 repeats the same failure pattern.
    3. The real loop enters summary and emits a summary round.
    4. Attribution is built from the final stream text with `summary_round` override.
    5. The payload should mark `summary_triggered=true`.
    """
    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                sse({"type": "content", "text": "round-1"}),
                native_tool_call_chunk("call-r1"),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "round-2"}),
                native_tool_call_chunk("call-r2"),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "summary output"}),
                sse_done(),
            ],
        ]
    )
    loop_attr_env.monkeypatch.setattr(loop_attr_env.llm_service_module, "get_llm_service", lambda: llm)

    async def _dispatch_all_error(calls, _session_id, source_agent_id=None):
        del source_agent_id
        return [
            {
                "service_name": "tool",
                "tool_name": c.get("tool_name", ""),
                "status": "error",
                "result": "failed",
            }
            for c in calls
        ]

    loop_attr_env.monkeypatch.setattr(loop_module, "execute_tool_calls", _dispatch_all_error)

    stream_text = await _collect_loop_text(
        messages=[{"role": "user", "content": "keep trying tools"}],
        max_rounds=5,
        tools=[{"type": "function", "function": {"name": "tool__web_search"}}],
    )
    report = _report_for_loop_text(stream_text)
    payload = build_failure_attribution(
        "loop_attr_summary_round",
        stream_text,
        report,
        failure_stage="summary_round",
    )
    _publish_quality_gate_case(
        request,
        case_id="loop_attr_summary_round",
        payload=payload,
        report=report,
    )

    assert '"summary":true' in stream_text or '"summary": true' in stream_text
    assert payload["summary_triggered"] is True
    assert payload["failure_stage"] == "summary_round"
    assert_failure_attribution_shape(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure_stage",
    [
        "tool_call_normalize",
        "tool_result_injection",
    ],
)
async def test_loop_failure_attribution_accepts_loop_stage_overrides(loop_attr_env, request, failure_stage: str):
    """Loop-level attribution should accept deterministic stage overrides for gate reporting.

    Test path:
    1. Fake LLM emits a deterministic error-style stream.
    2. The loop output is converted into route-like report fields.
    3. `build_failure_attribution(...)` is called with an explicit stage override.
    4. The payload should preserve that override exactly.
    """
    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                "data: error:loop stage mismatch\n\n",
            ]
        ]
    )
    loop_attr_env.monkeypatch.setattr(loop_attr_env.llm_service_module, "get_llm_service", lambda: llm)

    stream_text = await _collect_loop_text(
        messages=[{"role": "user", "content": "trigger stage override"}],
        max_rounds=3,
        tools=None,
    )
    report = _report_for_loop_text(stream_text)
    payload = build_failure_attribution(
        f"loop_attr_{failure_stage}",
        stream_text,
        report,
        failure_stage=failure_stage,
    )
    _publish_quality_gate_case(
        request,
        case_id=f"loop_attr_{failure_stage}",
        payload=payload,
        report=report,
    )

    assert payload["final_status"] == "degraded"
    assert payload["failure_stage"] == failure_stage
    assert payload["unhandled_exception"] is False
    assert_failure_attribution_shape(payload)
