"""Unit tests for message-injection behavior in `run_agentic_loop(...)`."""

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
    OneShotQueuedMessageStub,
    ScriptedStreamLLM,
    extract_sse_json_events,
    native_tool_call_chunk,
    sse,
    sse_done,
)


pytestmark = [pytest.mark.unit]


@pytest.fixture
def loop_env(monkeypatch):
    """Deterministic harness with no-op compression and empty queue injection."""

    async def _compress_passthrough(messages):
        return context_compressor.CompressResult(
            messages=messages,
            sse_events=[],
            compressed=False,
        )

    queue = EmptyQueueStub()
    monkeypatch.setattr(
        loop_module,
        "get_config",
        lambda: SimpleNamespace(api=SimpleNamespace(temperature=0.0)),
    )
    monkeypatch.setattr(context_compressor, "compress_context", _compress_passthrough)
    monkeypatch.setattr(message_queue, "get_message_queue", lambda: queue)
    return SimpleNamespace(
        monkeypatch=monkeypatch,
        queue=queue,
        llm_service_module=llm_service,
    )


@pytest.mark.asyncio
async def test_native_result_injection_is_single_and_stable(loop_env):
    """One native tool round should inject one assistant+tool pair exactly once.

    Test path:
    1. Round 1 emits one native tool call.
    2. Fake dispatcher returns one successful tool result.
    3. Round 2 should receive history augmented with one assistant tool-call message
       and one matching tool result message.
    4. The same tool result must not be injected twice.
    """
    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                sse({"type": "content", "text": "round-1"}),
                native_tool_call_chunk("call-r1", query="naga"),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "final answer"}),
                sse_done(),
            ],
        ]
    )
    loop_env.monkeypatch.setattr(
        loop_env.llm_service_module,
        "get_llm_service",
        lambda: llm,
    )

    async def _dispatch_success(calls, _session_id, source_agent_id=None):
        del source_agent_id
        return [
            {
                "service_name": "tool",
                "tool_name": c.get("tool_name", ""),
                "status": "success",
                "result": f"ok-{c.get('tool_name', '')}",
            }
            for c in calls
        ]

    loop_env.monkeypatch.setattr(loop_module, "execute_tool_calls", _dispatch_success)

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "please search"},
    ]
    output_chunks: list[str] = []
    async for chunk in loop_module.run_agentic_loop(
        messages,
        session_id="unit-session",
        max_rounds=3,
        tools=[{"type": "function", "function": {"name": "tool__web_search"}}],
    ):
        output_chunks.append(chunk)

    # Exactly two LLM calls:
    # - round 1 with tool call
    # - round 2 after result injection (no further tools -> stop)
    assert len(llm.calls) == 2

    second_round_messages = llm.calls[1]["messages"]
    assistant_with_tool_calls = [
        m for m in second_round_messages if m.get("role") == "assistant" and m.get("tool_calls")
    ]
    tool_messages = [m for m in second_round_messages if m.get("role") == "tool"]

    assert len(assistant_with_tool_calls) == 1
    assert len(tool_messages) == 1
    assert tool_messages[0]["tool_call_id"] == "call-r1"
    assert tool_messages[0]["content"] == "ok-web_search"

    # No duplicate injection of the same tool result.
    assert sum(1 for m in tool_messages if m.get("tool_call_id") == "call-r1") == 1

    events = extract_sse_json_events(output_chunks)
    round_ends = [e for e in events if e.get("type") == "round_end"]
    assert round_ends[-1]["has_more"] is False


@pytest.mark.asyncio
async def test_queue_injection_happens_before_next_round_and_once(monkeypatch):
    """Queued messages should be injected once before the next LLM round.

    Test path:
    1. Round 1 emits a text-parsed tool call.
    2. Fake dispatcher returns one successful tool result.
    3. Queue stub returns one side-channel message on its first drain.
    4. Round 2 should see the tool result plus queued text merged into the
       last user-semantic message.
    5. The same queued message must not be injected twice.
    """

    async def _compress_passthrough(messages):
        return context_compressor.CompressResult(
            messages=messages,
            sse_events=[],
            compressed=False,
        )

    queue = OneShotQueuedMessageStub(source="scheduler", content="queue-msg-1")
    monkeypatch.setattr(
        loop_module,
        "get_config",
        lambda: SimpleNamespace(api=SimpleNamespace(temperature=0.0)),
    )
    monkeypatch.setattr(context_compressor, "compress_context", _compress_passthrough)
    monkeypatch.setattr(message_queue, "get_message_queue", lambda: queue)

    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                sse(
                    {
                        "type": "content",
                        "text": (
                            "let me use a tool\n"
                            "```tool\n"
                            '{"agentType":"tool","tool_name":"web_search","args":{"query":"naga"}}\n'
                            "```"
                        ),
                    }
                ),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "final answer after queue inject"}),
                sse_done(),
            ],
        ]
    )
    monkeypatch.setattr(llm_service, "get_llm_service", lambda: llm)

    async def _dispatch_success(calls, _session_id, source_agent_id=None):
        del source_agent_id
        return [
            {
                "service_name": "tool",
                "tool_name": c.get("tool_name", ""),
                "status": "success",
                "result": f"ok-{c.get('tool_name', '')}",
            }
            for c in calls
        ]

    monkeypatch.setattr(loop_module, "execute_tool_calls", _dispatch_success)

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "please search and include queued context"},
    ]
    output_chunks: list[str] = []
    async for chunk in loop_module.run_agentic_loop(
        messages,
        session_id="unit-session",
        max_rounds=3,
        tools=[{"type": "function", "function": {"name": "tool__web_search"}}],
    ):
        output_chunks.append(chunk)

    # Two rounds only: one tool round + one final round.
    assert len(llm.calls) == 2
    assert queue.drain_calls >= 1

    second_round_messages = llm.calls[1]["messages"]
    user_messages = [m for m in second_round_messages if m.get("role") == "user"]
    assert user_messages
    last_user_content = user_messages[-1]["content"]

    # Queue context is merged into last user-semantic message exactly once.
    assert "queue-msg-1" in last_user_content
    assert last_user_content.count("queue-msg-1") == 1
    assert "ok-web_search" in last_user_content

    events = extract_sse_json_events(output_chunks)
    queued_events = [e for e in events if e.get("type") == "queued_messages"]
    assert len(queued_events) == 1
    assert queued_events[0]["count"] == 1
    assert queued_events[0]["sources"] == ["scheduler"]


@pytest.mark.asyncio
async def test_multi_round_native_result_injection_stays_idempotent(loop_env):
    """Across multiple rounds, each tool result should be injected once.

    Test path:
    1. Round 1 emits tool call `call-r1` and dispatcher returns success.
    2. Round 2 emits tool call `call-r2` and dispatcher returns success.
    3. Round 3 should see both historical tool results in messages.
    4. Each `tool_call_id` should appear exactly once in injected history.
    """
    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                sse({"type": "content", "text": "round-1"}),
                native_tool_call_chunk("call-r1", query="alpha"),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "round-2"}),
                native_tool_call_chunk("call-r2", query="beta"),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "final answer"}),
                sse_done(),
            ],
        ]
    )
    loop_env.monkeypatch.setattr(loop_env.llm_service_module, "get_llm_service", lambda: llm)

    async def _dispatch_success(calls, _session_id, source_agent_id=None):
        del source_agent_id
        return [
            {
                "service_name": "tool",
                "tool_name": c.get("tool_name", ""),
                "status": "success",
                "result": f"ok-{c.get('_tool_call_id')}",
            }
            for c in calls
        ]

    loop_env.monkeypatch.setattr(loop_module, "execute_tool_calls", _dispatch_success)

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "please do two searches"},
    ]
    output_chunks: list[str] = []
    async for chunk in loop_module.run_agentic_loop(
        messages,
        session_id="unit-session",
        max_rounds=4,
        tools=[{"type": "function", "function": {"name": "tool__web_search"}}],
    ):
        output_chunks.append(chunk)

    # Round 1 -> Round 2 -> Final round
    assert len(llm.calls) == 3

    round2_messages = llm.calls[1]["messages"]
    round2_tools = [m for m in round2_messages if m.get("role") == "tool"]
    assert len(round2_tools) == 1
    assert round2_tools[0]["tool_call_id"] == "call-r1"
    assert round2_tools[0]["content"] == "ok-call-r1"

    round3_messages = llm.calls[2]["messages"]
    round3_tools = [m for m in round3_messages if m.get("role") == "tool"]
    round3_tool_ids = [m.get("tool_call_id") for m in round3_tools]

    # Two rounds of tool results should exist exactly once each.
    assert len(round3_tools) == 2
    assert round3_tool_ids.count("call-r1") == 1
    assert round3_tool_ids.count("call-r2") == 1

    round3_tool_contents = [m.get("content") for m in round3_tools]
    assert "ok-call-r1" in round3_tool_contents
    assert "ok-call-r2" in round3_tool_contents

    # Assistant function-call messages should also match the two rounds exactly.
    round3_assistant_with_calls = [
        m for m in round3_messages if m.get("role") == "assistant" and m.get("tool_calls")
    ]
    assert len(round3_assistant_with_calls) == 2
    assert sum(
        1 for m in round3_assistant_with_calls for c in m.get("tool_calls", []) if c.get("id") == "call-r1"
    ) == 1
    assert sum(
        1 for m in round3_assistant_with_calls for c in m.get("tool_calls", []) if c.get("id") == "call-r2"
    ) == 1

    events = extract_sse_json_events(output_chunks)
    round_ends = [e for e in events if e.get("type") == "round_end"]
    assert round_ends[-1]["has_more"] is False


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="runtime does not deduplicate duplicate tool_call_id injections across rounds yet",
    strict=False,
)
async def test_duplicate_tool_call_id_is_deduplicated_across_rounds(loop_env):
    """Duplicate `tool_call_id` should not be reinjected into loop history.

    Test path:
    1. Round 1 emits tool call `dup-id`.
    2. Round 2 emits another tool call using the same id.
    3. Dispatcher returns success both times.
    4. Target contract: later history should keep only one injected copy of that id.
    5. Current runtime does not satisfy this yet, so the test is `xfail`.
    """
    llm = ScriptedStreamLLM(
        round_scripts=[
            [
                sse({"type": "content", "text": "round-1"}),
                native_tool_call_chunk("dup-id", query="alpha"),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "round-2"}),
                native_tool_call_chunk("dup-id", query="beta"),
                sse_done(),
            ],
            [
                sse({"type": "content", "text": "final answer"}),
                sse_done(),
            ],
        ]
    )
    loop_env.monkeypatch.setattr(loop_env.llm_service_module, "get_llm_service", lambda: llm)

    async def _dispatch_success(calls, _session_id, source_agent_id=None):
        del source_agent_id
        return [
            {
                "service_name": "tool",
                "tool_name": c.get("tool_name", ""),
                "status": "success",
                "result": f"ok-{c.get('_tool_call_id')}",
            }
            for c in calls
        ]

    loop_env.monkeypatch.setattr(loop_module, "execute_tool_calls", _dispatch_success)

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "please run two tools"},
    ]
    async for _chunk in loop_module.run_agentic_loop(
        messages,
        session_id="unit-session",
        max_rounds=4,
        tools=[{"type": "function", "function": {"name": "tool__web_search"}}],
    ):
        pass

    assert len(llm.calls) == 3
    round3_messages = llm.calls[2]["messages"]

    # Target contract: only one injected tool message per tool_call_id.
    round3_tools = [m for m in round3_messages if m.get("role") == "tool"]
    dup_tool_messages = [m for m in round3_tools if m.get("tool_call_id") == "dup-id"]
    assert len(dup_tool_messages) == 1

    round3_assistant_with_calls = [
        m for m in round3_messages if m.get("role") == "assistant" and m.get("tool_calls")
    ]
    dup_assistant_call_refs = sum(
        1
        for m in round3_assistant_with_calls
        for c in m.get("tool_calls", [])
        if c.get("id") == "dup-id"
    )
    assert dup_assistant_call_refs == 1
