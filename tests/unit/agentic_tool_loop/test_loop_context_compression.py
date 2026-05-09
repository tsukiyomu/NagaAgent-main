"""Unit tests for loop-level context compression behavior.

Focus:
1. compression SSE events are forwarded through the real loop
2. compressed messages become the actual next-round LLM input
3. summary round also executes its own compression pass
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


def _native_tool_call_chunk(call_id: str, query: str = "naga") -> str:
    """Build one native tool-call chunk consumed by real loop parser."""
    # Reuse the shared native tool-call builder so this file stays focused on
    # compression timing, not tool-call payload formatting.
    return build_native_tool_call_chunk(call_id, query=query)


async def _collect_loop_chunks(
    messages: list[dict[str, Any]],
    *,
    max_rounds: int,
    tools: list[dict[str, Any]] | None,
) -> list[str]:
    """Run the real loop and collect all yielded SSE chunks."""
    # Store the raw SSE chunks exactly as yielded by `run_agentic_loop(...)`.
    # Tests decode them later with `extract_sse_json_events(...)` when they want
    # to assert event-level behavior such as `compress_info` or `round_end`.
    output: list[str] = []

    # Keep the real loop in the middle of the test.
    # We fake compression / LLM / tool execution around it, but still let the
    # actual orchestration code decide when to yield events and when to stop.
    async for chunk in loop_module.run_agentic_loop(
        messages,
        session_id="compression-unit-session",
        max_rounds=max_rounds,
        tools=tools,
    ):
        # Preserve chunk order because summary / compression assertions depend
        # on the real streaming sequence.
        output.append(chunk)
    return output


@pytest.fixture
def compression_env(monkeypatch):
    """Shared deterministic harness for compression-path unit tests."""
    # Keep runtime config deterministic so tests only exercise loop behavior.
    monkeypatch.setattr(
        loop_module,
        "get_config",
        lambda: SimpleNamespace(api=SimpleNamespace(temperature=0.0)),
    )
    # Use an always-empty queue so queue injection does not affect compression tests.
    monkeypatch.setattr(message_queue, "get_message_queue", lambda: EmptyQueueStub())

    return SimpleNamespace(
        monkeypatch=monkeypatch,
        llm_service_module=llm_service,
    )


@pytest.mark.asyncio
async def test_loop_forwards_compress_events_and_uses_compressed_messages(compression_env):
    """Compression events should be forwarded and compressed messages should be used.

    Test path:
    1. Stub compression replaces the original messages with a compressed view.
    2. Fake LLM emits one final content round with no tool call.
    3. The real loop should forward the compressor SSE event.
    4. The real loop should call LLM with the compressed messages.
    5. The loop should stop after this single round.
    """
    compressed_messages = [
        {"role": "system", "content": "compressed-sys"},
        {"role": "user", "content": "compressed-user"},
    ]
    compress_inputs: list[list[dict[str, Any]]] = []

    async def _compress_replace(messages):
        # Capture the pre-compression input the loop passed to the compressor.
        compress_inputs.append(copy.deepcopy(messages))
        return context_compressor.CompressResult(
            # Pretend compression replaced the whole context with a shorter view.
            messages=copy.deepcopy(compressed_messages),
            sse_events=[sse({"type": "compress_info", "phase": "round"})],
            compressed=True,
        )

    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                sse({"type": "content", "text": "compressed-ok"}),
                sse_done(),
            ]
        ]
    )
    compression_env.monkeypatch.setattr(context_compressor, "compress_context", _compress_replace)
    compression_env.monkeypatch.setattr(
        compression_env.llm_service_module,
        "get_llm_service",
        lambda: llm,
    )

    chunks = await _collect_loop_chunks(
        messages=[
            {"role": "system", "content": "original-sys"},
            {"role": "user", "content": "original-user"},
        ],
        max_rounds=3,
        tools=[{"type": "function", "function": {"name": "tool__web_search"}}],
    )
    events = extract_sse_json_events(chunks)
    compress_events = [e for e in events if e.get("type") == "compress_info"]
    round_ends = [e for e in events if e.get("type") == "round_end"]

    # Compression should run once before the only LLM round.
    assert len(compress_inputs) == 1
    # The LLM should see the compressed messages, not the original input.
    assert llm.calls[0]["messages"] == compressed_messages
    # The loop should forward compressor-produced SSE events unchanged.
    assert compress_events == [{"type": "compress_info", "phase": "round"}]
    assert round_ends[-1]["has_more"] is False


@pytest.mark.asyncio
async def test_loop_summary_round_runs_its_own_compression_pass(compression_env):
    """Summary round should trigger a second compression pass before final answer.

    Test path:
    1. First compression runs before the normal tool round.
    2. Fake LLM emits one native tool call.
    3. Fake dispatcher returns one successful tool result.
    4. `max_rounds=1` forces the loop to stop normal tool rounds and enter summary.
    5. Summary round runs its own compression pass and calls LLM with `tools=None`.
    """
    compress_inputs: list[list[dict[str, Any]]] = []

    async def _compress_track(messages):
        # Record each compressor input so the test can prove two passes happened:
        # one before the normal round and one before summary round.
        compress_inputs.append(copy.deepcopy(messages))
        phase = "initial" if len(compress_inputs) == 1 else "summary"
        return context_compressor.CompressResult(
            # Keep messages unchanged; this test cares about call timing, not replacement.
            messages=messages,
            sse_events=[sse({"type": "compress_info", "phase": phase})],
            compressed=False,
        )

    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                sse({"type": "content", "text": "round-1"}),
                _native_tool_call_chunk("call-r1"),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "summary-answer"}),
                sse_done(),
            ],
        ]
    )
    compression_env.monkeypatch.setattr(context_compressor, "compress_context", _compress_track)
    compression_env.monkeypatch.setattr(
        compression_env.llm_service_module,
        "get_llm_service",
        lambda: llm,
    )

    async def _dispatch_success(calls, _session_id, source_agent_id=None):
        del source_agent_id
        # Return one normalized success result per tool call so the loop can
        # continue into its summary-path decision logic.
        return [
            {
                "service_name": "tool",
                "tool_name": c.get("tool_name", ""),
                "status": "success",
                "result": "ok",
            }
            for c in calls
        ]

    compression_env.monkeypatch.setattr(loop_module, "execute_tool_calls", _dispatch_success)

    chunks = await _collect_loop_chunks(
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "please force summary"},
        ],
        # One normal round plus one forced summary round is the shortest path
        # to prove summary owns its own compression pass.
        max_rounds=1,
        tools=[{"type": "function", "function": {"name": "tool__web_search"}}],
    )
    events = extract_sse_json_events(chunks)
    compress_events = [e for e in events if e.get("type") == "compress_info"]
    summary_round_starts = [e for e in events if e.get("type") == "round_start" and e.get("summary") is True]
    round_ends = [e for e in events if e.get("type") == "round_end"]

    # Compression should run once before the tool round and once before summary.
    assert len(compress_inputs) == 2
    assert [e["phase"] for e in compress_events] == ["initial", "summary"]
    # Summary should be exposed as round 2 and must disable tools.
    assert summary_round_starts and summary_round_starts[0]["round"] == 2
    assert llm.calls[-1]["tools"] is None
    assert round_ends[-1]["round"] == 2
    assert round_ends[-1]["has_more"] is False
