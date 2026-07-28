from __future__ import annotations

"""Unit tests for the Langfuse adapter boundary.

These tests stay intentionally local:
- no real Langfuse client
- no real network calls
- assertions target the helper contract that call sites rely on
"""

from types import SimpleNamespace
from typing import Any

import pytest

import apiserver.langfuse_integration as langfuse_integration


pytestmark = [pytest.mark.unit]


class _ObservationContext:
    """Tiny context wrapper so tests can mimic `with observation as current:`."""

    def __init__(self, observation: Any):
        self._observation = observation

    def __enter__(self):
        return self._observation

    def __exit__(self, exc_type, exc, tb):
        return False


def test_llm_generation_helpers_record_output_usage_and_metadata(monkeypatch):
    """Non-streaming adapter helpers should preserve metadata, output, and usage."""

    captured_starts: list[dict[str, Any]] = []
    observation = SimpleNamespace(updates=[])

    def _start_observation(**kwargs):
        captured_starts.append(kwargs)
        return _ObservationContext(observation)

    def _update_observation(obs, **kwargs):
        obs.updates.append(kwargs)

    monkeypatch.setattr(langfuse_integration, "start_observation", _start_observation)
    monkeypatch.setattr(langfuse_integration, "update_observation", _update_observation)

    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=7, total_tokens=19),
    )
    with langfuse_integration.start_llm_generation_observation(
        name="llm.chat_with_context",
        messages=[{"role": "user", "content": "hello"}],
        model="openai/test-model",
        metadata={"session_id": "session-llm-1"},
        temperature=0.2,
        max_tokens=256,
        stream=False,
    ) as current_observation:
        assert current_observation is observation

    langfuse_integration.complete_llm_generation_observation(
        observation,
        content="hello from llm",
        reasoning_content="reasoned",
        response=response,
    )

    assert captured_starts[0]["name"] == "llm.chat_with_context"
    assert captured_starts[0]["model"] == "openai/test-model"
    assert captured_starts[0]["metadata"]["session_id"] == "session-llm-1"
    assert captured_starts[0]["as_type"] == "generation"
    assert captured_starts[0]["input"] == [{"role": "user", "content": "hello"}]
    assert captured_starts[0]["model_parameters"] == {
        "temperature": 0.2,
        "max_tokens": 256,
        "stream": False,
    }
    assert observation.updates == [
        {
            "output": {
                "content": "hello from llm",
                "reasoning_content": "reasoned",
            },
            "usage_details": {"input": 12, "output": 7, "total": 19},
        }
    ]


def test_stream_generation_helpers_record_tools_and_output(monkeypatch):
    """Streaming adapter helpers should record tool count and normalized output."""

    captured_starts: list[dict[str, Any]] = []
    observation = SimpleNamespace(updates=[])

    def _start_observation(**kwargs):
        captured_starts.append(kwargs)
        return _ObservationContext(observation)

    def _update_observation(obs, **kwargs):
        obs.updates.append(kwargs)

    monkeypatch.setattr(langfuse_integration, "start_observation", _start_observation)
    monkeypatch.setattr(langfuse_integration, "update_observation", _update_observation)

    tools = [{"type": "function", "function": {"name": "tool__web_search"}}]
    tool_calls = [
        {
            "id": "call-1",
            "name": "tool__web_search",
            "arguments": '{"query":"naga"}',
        }
    ]
    with langfuse_integration.start_llm_generation_observation(
        name="llm.stream_chat_with_context",
        messages=[{"role": "user", "content": "hello"}],
        model="openai/test-model",
        metadata={"session_id": "session-stream-1"},
        temperature=0.4,
        max_tokens=256,
        stream=True,
        tools=tools,
    ) as current_observation:
        assert current_observation is observation

    langfuse_integration.complete_llm_generation_observation(
        observation,
        content="hello world",
        reasoning_content="think ",
        tool_calls=tool_calls,
    )

    assert captured_starts[0]["name"] == "llm.stream_chat_with_context"
    assert captured_starts[0]["metadata"]["session_id"] == "session-stream-1"
    assert captured_starts[0]["model_parameters"] == {
        "temperature": 0.4,
        "max_tokens": 256,
        "stream": True,
        "tool_count": 1,
    }
    assert observation.updates == [
        {
            "output": {
                "content": "hello world",
                "reasoning_content": "think ",
                "tool_calls": tool_calls,
            }
        }
    ]


def test_tool_observation_helpers_build_expected_name_and_status(monkeypatch):
    """Tool helper should propagate session_id and flag errors."""

    captured_starts: list[dict[str, Any]] = []
    captured_propagation: list[dict[str, Any]] = []
    observation = SimpleNamespace(updates=[])

    def _start_observation(**kwargs):
        captured_starts.append(kwargs)
        return _ObservationContext(observation)

    def _update_observation(obs, **kwargs):
        obs.updates.append(kwargs)

    def _propagate_attributes(**kwargs):
        captured_propagation.append(kwargs)
        return _ObservationContext(None)

    monkeypatch.setattr(langfuse_integration, "start_observation", _start_observation)
    monkeypatch.setattr(langfuse_integration, "update_observation", _update_observation)
    monkeypatch.setattr(langfuse_integration, "propagate_langfuse_attributes", _propagate_attributes)

    call = {
        "agentType": "mcp",
        "service_name": "weather_time",
        "tool_name": "today_weather",
    }
    with langfuse_integration.start_tool_observation(
        call,
        session_id="session-1",
        source_agent_id="agent-1",
    ) as current_observation:
        assert current_observation is observation

    langfuse_integration.complete_tool_observation(
        observation,
        {
            "status": "error",
            "result": "tool failed",
            "service_name": "weather_time",
            "tool_name": "today_weather",
        },
    )

    assert captured_starts == [
        {
            "name": "tool.weather_time.today_weather",
            "as_type": "tool",
            "input": call,
            "metadata": {
                "session_id": "session-1",
                "source_agent_id": "agent-1",
                "agent_type": "mcp",
            },
        }
    ]
    assert captured_propagation == [{"session_id": "session-1"}]
    assert observation.updates == [
        {
            "output": {
                "status": "error",
                "result": "tool failed",
                "service_name": "weather_time",
                "tool_name": "today_weather",
            },
            "level": "ERROR",
            "status_message": "tool failed",
        }
    ]
