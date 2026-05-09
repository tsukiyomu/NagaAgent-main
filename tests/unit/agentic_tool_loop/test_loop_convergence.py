"""Unit convergence tests for `run_agentic_loop(...)`.

Scope of this file:
1. no actionable tool calls -> loop stops immediately
2. repeated all-failed tool rounds -> early summary round
3. max_rounds exhausted -> summary round with `tools=None`

These tests run purely in-process and patch all high-variance dependencies.
They validate internal workflow-state transitions, not HTTP/SSE route behavior.
"""

from __future__ import annotations

import copy
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
    extract_sse_json_events,
    native_tool_call_chunk as build_native_tool_call_chunk,
    sse,
    sse_done,
)


pytestmark = [pytest.mark.unit]


def _native_tool_call_chunk(call_id: str, query: str = "naga", extra_args: dict[str, Any] | None = None) -> str:
    """Build one `tool_calls_native` SSE chunk consumed by real loop parser."""
    return build_native_tool_call_chunk(call_id, query=query, extra_args=extra_args)


async def _collect_loop_chunks(
    messages: list[dict[str, Any]],
    *,
    max_rounds: int,
    tools: list[dict[str, Any]] | None,
) -> list[str]:
    """Run the real loop and collect all yielded SSE chunks."""
    output: list[str] = []
    async for chunk in loop_module.run_agentic_loop(
        messages,
        session_id="unit-session",
        max_rounds=max_rounds,
        tools=tools,
    ):
        output.append(chunk)
    return output


@pytest.fixture
def loop_test_env(monkeypatch):
    """Shared deterministic harness for loop unit tests."""

    async def _compress_passthrough(messages):
        # Keep compression path active but deterministic/no-op.
        return context_compressor.CompressResult(
            messages=messages,
            sse_events=[],
            compressed=False,
        )

    # Keep runtime config access deterministic in tests.
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
async def test_loop_stops_when_no_actionable_tool_calls(loop_test_env):
    """State: round_start + no actionable tool call -> stop_without_tool_dispatch.

    Test path:
    1. Fake LLM emits plain content and no tool call.
    2. Dispatch is patched but should never be used.
    3. The real loop should stop after the first round.
    4. No summary round should be entered.
    """
    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                sse({"type": "content", "text": "plain answer"}),
                sse_done(),
            ]
        ]
    )
    loop_test_env.monkeypatch.setattr(
        loop_test_env.llm_service_module,
        "get_llm_service",
        lambda: llm,
    )

    dispatch_call_count = 0

    async def _dispatch_unexpected(*_args, **_kwargs):
        nonlocal dispatch_call_count
        dispatch_call_count += 1
        return []

    loop_test_env.monkeypatch.setattr(loop_module, "execute_tool_calls", _dispatch_unexpected)

    chunks = await _collect_loop_chunks(
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hello"},
        ],
        max_rounds=3,
        tools=[{"type": "function", "function": {"name": "tool__web_search"}}],
    )
    events = extract_sse_json_events(chunks)
    round_end_events = [e for e in events if e.get("type") == "round_end"]
    summary_round_start = [e for e in events if e.get("type") == "round_start" and e.get("summary")]

    assert dispatch_call_count == 0
    assert len(llm.calls) == 1
    assert len(round_end_events) == 1
    assert round_end_events[0]["has_more"] is False
    assert summary_round_start == []


@pytest.mark.asyncio
async def test_loop_repeated_all_failed_rounds_trigger_early_summary(loop_test_env):
    """State: two full-failure rounds -> early summary (before max_rounds).

    Test path:
    1. Round 1 emits a native tool call and dispatcher returns error.
    2. Round 2 emits another native tool call and dispatcher returns error again.
    3. The loop should treat this as repeated full-round failure.
    4. Summary should start before exhausting `max_rounds`.
    5. Summary LLM call should run with `tools=None`.
    """
    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                sse({"type": "content", "text": "round-1"}),
                _native_tool_call_chunk("call-r1"),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "round-2"}),
                _native_tool_call_chunk("call-r2"),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "summary-after-failure"}),
                sse_done(),
            ],
        ]
    )
    loop_test_env.monkeypatch.setattr(
        loop_test_env.llm_service_module,
        "get_llm_service",
        lambda: llm,
    )

    dispatch_calls: list[list[dict[str, Any]]] = []

    async def _dispatch_all_error(calls, _session_id, source_agent_id=None):
        del source_agent_id
        dispatch_calls.append(copy.deepcopy(calls))
        return [
            {
                "service_name": "tool",
                "tool_name": c.get("tool_name", ""),
                "status": "error",
                "result": "failed",
            }
            for c in calls
        ]

    loop_test_env.monkeypatch.setattr(loop_module, "execute_tool_calls", _dispatch_all_error)

    chunks = await _collect_loop_chunks(
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "please use tools"},
        ],
        max_rounds=5,
        tools=[{"type": "function", "function": {"name": "tool__web_search"}}],
    )
    events = extract_sse_json_events(chunks)
    summary_starts = [e for e in events if e.get("type") == "round_start" and e.get("summary") is True]
    round_ends = [e for e in events if e.get("type") == "round_end"]
    final_round_end = round_ends[-1]

    assert len(dispatch_calls) == 2
    assert len(llm.calls) == 3
    assert llm.calls[-1]["tools"] is None
    assert summary_starts and summary_starts[0]["round"] == 6
    assert final_round_end["round"] == 6
    assert final_round_end["has_more"] is False


@pytest.mark.asyncio
async def test_loop_max_rounds_exhausted_enters_summary_with_tools_disabled(loop_test_env):
    """State: round==max_rounds and still tool calls -> summary round with tools=None.

    Test path:
    1. Round 1 emits a native tool call and dispatcher succeeds.
    2. Round 2 emits another native tool call and dispatcher succeeds again.
    3. `max_rounds=2` prevents a third normal tool round.
    4. The loop should enter summary instead of continuing tool use.
    5. Summary LLM call should run with `tools=None`.
    """
    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                sse({"type": "content", "text": "round-1"}),
                _native_tool_call_chunk("call-r1"),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "round-2"}),
                _native_tool_call_chunk("call-r2"),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "summary-after-max-rounds"}),
                sse_done(),
            ],
        ]
    )
    loop_test_env.monkeypatch.setattr(
        loop_test_env.llm_service_module,
        "get_llm_service",
        lambda: llm,
    )

    dispatch_call_count = 0

    async def _dispatch_success(calls, _session_id, source_agent_id=None):
        del source_agent_id
        nonlocal dispatch_call_count
        dispatch_call_count += 1
        return [
            {
                "service_name": "tool",
                "tool_name": c.get("tool_name", ""),
                "status": "success",
                "result": "ok",
            }
            for c in calls
        ]

    loop_test_env.monkeypatch.setattr(loop_module, "execute_tool_calls", _dispatch_success)

    chunks = await _collect_loop_chunks(
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "please keep calling tools"},
        ],
        max_rounds=2,
        tools=[{"type": "function", "function": {"name": "tool__web_search"}}],
    )
    events = extract_sse_json_events(chunks)
    summary_starts = [e for e in events if e.get("type") == "round_start" and e.get("summary") is True]
    round_ends = [e for e in events if e.get("type") == "round_end"]
    final_round_end = round_ends[-1]

    assert dispatch_call_count == 2
    assert len(llm.calls) == 3
    assert llm.calls[-1]["tools"] is None
    assert summary_starts and summary_starts[0]["round"] == 3
    assert final_round_end["round"] == 3
    assert final_round_end["has_more"] is False


@pytest.mark.asyncio
async def test_loop_tool_timeout_errors_still_converge_to_summary(loop_test_env):
    """Consecutive timeout failures should still converge into summary round.

    Test path:
    1. Round 1 emits a tool call that the executor reports as timeout-style error.
    2. Round 2 repeats the same timeout-style failure pattern.
    3. The real loop should standardize those failures as error results.
    4. Repeated timeout failures should force summary.
    5. Summary LLM call should run with `tools=None` and terminate cleanly.
    """
    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                sse({"type": "content", "text": "round-1"}),
                _native_tool_call_chunk("call-timeout-r1", extra_args={"timeout_seconds": 1}),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "round-2"}),
                _native_tool_call_chunk("call-timeout-r2", extra_args={"timeout_seconds": 1}),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "summary-after-timeout"}),
                sse_done(),
            ],
        ]
    )
    loop_test_env.monkeypatch.setattr(
        loop_test_env.llm_service_module,
        "get_llm_service",
        lambda: llm,
    )

    async def _timeout_tool(call, source_agent_id=None):
        del source_agent_id
        return {
            "tool_call": call,
            "service_name": "tool",
            "tool_name": call.get("tool_name", ""),
            "status": "error",
            "result": "tool timeout: 1s",
        }

    loop_test_env.monkeypatch.setattr(loop_module, "_execute_openclaw_tool_call", _timeout_tool)

    chunks = await _collect_loop_chunks(
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "please run tools with timeout"},
        ],
        max_rounds=5,
        tools=[{"type": "function", "function": {"name": "tool__web_search"}}],
    )
    events = extract_sse_json_events(chunks)
    summary_starts = [e for e in events if e.get("type") == "round_start" and e.get("summary") is True]
    round_ends = [e for e in events if e.get("type") == "round_end"]
    tool_results_events = [e for e in events if e.get("type") == "tool_results"]

    assert len(llm.calls) == 3
    assert llm.calls[-1]["tools"] is None
    assert summary_starts and summary_starts[0]["round"] == 6
    assert round_ends[-1]["round"] == 6
    assert round_ends[-1]["has_more"] is False
    assert tool_results_events
    assert any("timeout" in str(r.get("result", "")) for e in tool_results_events for r in e.get("results", []))
