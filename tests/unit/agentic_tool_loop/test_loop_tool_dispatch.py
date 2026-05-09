"""Unit tests for tool-dispatch contracts in `agentic_tool_loop`.

Focus:
1. `execute_tool_calls(...)` branch routing and error normalization behavior
2. parity between text-parsed and native function-call dispatch contracts
"""

from __future__ import annotations

import json
from typing import Any

import pytest

import apiserver.agentic_tool_loop as loop_module


pytestmark = [pytest.mark.unit]


def _project_dispatch_shape(call: dict[str, Any]) -> dict[str, Any]:
    """Project one dispatch call into a comparable stable shape."""
    projected: dict[str, Any] = {
        "agentType": call.get("agentType"),
        "service_name": call.get("service_name"),
        "tool_name": call.get("tool_name"),
    }
    if "args" in call:
        projected["args"] = call["args"]
    return projected


@pytest.mark.asyncio
async def test_execute_tool_calls_empty_list_returns_empty():
    """No executable tasks should return an empty result list.

    Test path:
    1. Call the real dispatch entry with an empty list.
    2. No executor branch should run.
    3. The result should be exactly `[]`.
    """
    result = await loop_module.execute_tool_calls([], session_id="unit-session")
    assert result == []


@pytest.mark.asyncio
async def test_execute_tool_calls_normalizes_raised_exceptions(monkeypatch):
    """Raised task exceptions should be normalized into generic error records.

    Test path:
    1. MCP executor branch returns one normal success result.
    2. Tool executor branch raises an exception.
    3. The real dispatch entry should keep the success record intact.
    4. The raised exception should be normalized into a stable error result.
    """
    tool_calls = [
        {"agentType": "mcp", "service_name": "svc", "tool_name": "ok"},
        {"agentType": "tool", "tool_name": "boom", "args": {"x": 1}},
    ]

    async def _mcp_ok(call, source_agent_id=None):
        del source_agent_id
        return {
            "tool_call": call,
            "result": "ok-result",
            "status": "success",
            "service_name": call.get("service_name", "mcp"),
            "tool_name": call.get("tool_name", ""),
        }

    async def _tool_boom(_call, source_agent_id=None):
        del source_agent_id
        raise RuntimeError("tool exploded")

    monkeypatch.setattr(loop_module, "_execute_mcp_call", _mcp_ok)
    monkeypatch.setattr(loop_module, "_execute_openclaw_tool_call", _tool_boom)

    results = await loop_module.execute_tool_calls(tool_calls, session_id="unit-session")

    assert len(results) == 2
    assert results[0]["status"] == "success"
    assert results[0]["service_name"] == "svc"
    assert results[0]["tool_name"] == "ok"

    error_result = results[1]
    assert error_result["status"] == "error"
    assert error_result["service_name"] == "unknown"
    assert error_result["tool_name"] == "unknown"
    assert "tool exploded" in error_result["result"]


@pytest.mark.asyncio
async def test_execute_tool_calls_preserves_executor_returned_timeout_error(monkeypatch):
    """Executor-level timeout result should pass through unchanged.

    Test path:
    1. Tool executor branch returns a pre-normalized timeout-style error record.
    2. The real dispatch entry should not rewrite that record into another shape.
    3. Timeout semantics should remain visible in the final result.
    """
    tool_calls = [
        {
            "agentType": "tool",
            "tool_name": "slow_tool",
            "args": {"timeout_seconds": 1},
        }
    ]

    async def _tool_timeout(_call, source_agent_id=None):
        del source_agent_id
        return {
            "tool_call": _call,
            "result": "tool timeout: 1s",
            "status": "error",
            "service_name": "tool",
            "tool_name": "slow_tool",
        }

    monkeypatch.setattr(loop_module, "_execute_openclaw_tool_call", _tool_timeout)

    results = await loop_module.execute_tool_calls(tool_calls, session_id="unit-session")

    assert len(results) == 1
    timeout_result = results[0]
    assert timeout_result["status"] == "error"
    assert timeout_result["service_name"] == "tool"
    assert timeout_result["tool_name"] == "slow_tool"
    assert "timeout" in timeout_result["result"]


def test_native_and_text_paths_share_dispatch_contract():
    """Text parse and native conversion should feed one stable dispatch contract.

    Test path:
    1. Build one tool call through the text parser path.
    2. Build the same logical tool call through the native conversion path.
    3. Project both into a comparable dispatch shape.
    4. The two shapes should match exactly.
    """
    text_payload = (
        "before\n"
        "```tool\n"
        '{"agentType":"tool","tool_name":"web_search","args":{"query":"naga"}}\n'
        "```\n"
        "after"
    )
    clean_text, text_calls = loop_module.parse_tool_calls_from_text(text_payload)

    native_calls = [
        {
            "id": "call-1",
            "name": "tool__web_search",
            "arguments": json.dumps({"query": "naga"}, ensure_ascii=False),
        }
    ]
    native_dispatch = loop_module._convert_native_to_dispatch(native_calls)

    assert "```tool" not in clean_text
    assert "before" in clean_text
    assert "after" in clean_text
    assert len(text_calls) == 1
    assert len(native_dispatch) == 1
    assert _project_dispatch_shape(text_calls[0]) == _project_dispatch_shape(native_dispatch[0])


@pytest.mark.asyncio
async def test_execute_tool_calls_dispatches_all_supported_agent_types(monkeypatch):
    """Each supported agent type should route to its dedicated executor branch.

    Test path:
    1. Provide one call for each supported agent type.
    2. Patch each executor branch with a distinct fake.
    3. Run the real dispatch entry on the mixed input.
    4. Verify that each call reached the expected executor and result shape.
    """
    calls_seen: list[tuple[str, str]] = []

    async def _mcp(call, source_agent_id=None):
        calls_seen.append(("mcp", source_agent_id or ""))
        return {
            "tool_call": call,
            "result": "mcp-ok",
            "status": "success",
            "service_name": call.get("service_name", "mcp"),
            "tool_name": call.get("tool_name", ""),
        }

    async def _openclaw(call, session_id):
        calls_seen.append(("openclaw", session_id))
        return {
            "tool_call": call,
            "result": "openclaw-ok",
            "status": "success",
            "service_name": "openclaw",
            "tool_name": call.get("task_type", "message"),
        }

    async def _tool(call, source_agent_id=None):
        calls_seen.append(("tool", source_agent_id or ""))
        return {
            "tool_call": call,
            "result": "tool-ok",
            "status": "success",
            "service_name": "tool",
            "tool_name": call.get("tool_name", ""),
        }

    async def _naga_control(call):
        calls_seen.append(("naga_control", call.get("command", "")))
        return {
            "tool_call": call,
            "result": "control-ok",
            "status": "success",
            "service_name": "naga_control",
            "tool_name": call.get("command", ""),
        }

    monkeypatch.setattr(loop_module, "_execute_mcp_call", _mcp)
    monkeypatch.setattr(loop_module, "_execute_openclaw_call", _openclaw)
    monkeypatch.setattr(loop_module, "_execute_openclaw_tool_call", _tool)
    monkeypatch.setattr(loop_module, "_execute_naga_control", _naga_control)

    results = await loop_module.execute_tool_calls(
        [
            {"agentType": "mcp", "service_name": "weather", "tool_name": "today"},
            {"agentType": "openclaw", "task_type": "message", "message": "hello"},
            {"agentType": "tool", "tool_name": "web_search", "args": {"query": "naga"}},
            {"agentType": "naga_control", "command": "focus"},
        ],
        session_id="unit-session",
        source_agent_id="agent-42",
    )

    assert calls_seen == [
        ("mcp", "agent-42"),
        ("openclaw", "unit-session"),
        ("tool", "agent-42"),
        ("naga_control", "focus"),
    ]
    assert [r["service_name"] for r in results] == ["weather", "openclaw", "tool", "naga_control"]
    assert [r["status"] for r in results] == ["success", "success", "success", "success"]
