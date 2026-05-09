from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

import apiserver.langfuse_integration as langfuse_integration
import apiserver.llm_service as llm_service


pytestmark = [pytest.mark.unit]


class _ObservationContext:
    def __init__(self, observation: Any):
        self._observation = observation

    def __enter__(self):
        return self._observation

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamResponse:
    def __init__(self, chunks: list[Any]):
        self._chunks = chunks

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for chunk in self._chunks:
            yield chunk


def _build_chunk(
    *,
    content: str | None = None,
    reasoning: str | None = None,
    tool_calls: list[Any] | None = None,
):
    delta = SimpleNamespace(
        content=content,
        reasoning_content=reasoning,
        tool_calls=tool_calls,
    )
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


@pytest.fixture
def llm_env(monkeypatch):
    config = SimpleNamespace(
        api=SimpleNamespace(
            api_key="test-key",
            base_url="https://api.example.com/v1",
            model="test-model",
            api_format="openai",
            max_tokens=256,
        )
    )
    monkeypatch.setattr(llm_service, "get_config", lambda: config)
    monkeypatch.setattr(llm_service.naga_auth, "is_authenticated", lambda: False)
    monkeypatch.setattr(llm_service.naga_auth, "get_access_token", lambda: "")
    monkeypatch.setattr(llm_service.naga_auth, "has_refresh_token", lambda: False)
    return config


@pytest.mark.asyncio
async def test_chat_with_context_updates_langfuse_generation(llm_env, monkeypatch):
    captured_starts: list[dict[str, Any]] = []
    observation = SimpleNamespace(updates=[])

    def _start_observation(**kwargs):
        captured_starts.append(kwargs)
        return _ObservationContext(observation)

    def _update_observation(obs, **kwargs):
        obs.updates.append(kwargs)

    async def _fake_acompletion(**kwargs):
        del kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="hello from llm",
                        reasoning_content="reasoned",
                    )
                )
            ],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=7, total_tokens=19),
        )

    monkeypatch.setattr(llm_service, "start_llm_generation_observation", _start_observation)
    monkeypatch.setattr(langfuse_integration, "update_observation", _update_observation)
    monkeypatch.setattr(llm_service, "acompletion", _fake_acompletion)

    service = llm_service.LLMService()
    response = await service.chat_with_context_and_reasoning_with_overrides(
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.2,
    )

    assert response.content == "hello from llm"
    assert response.reasoning_content == "reasoned"
    assert captured_starts[0]["name"] == "llm.chat_with_context"
    assert captured_starts[0]["model"] == "openai/test-model"
    assert captured_starts[0]["stream"] is False
    assert observation.updates == [
        {
            "output": {
                "content": "hello from llm",
                "reasoning_content": "reasoned",
            },
            "usage_details": {"input": 12, "output": 7, "total": 19},
        }
    ]


@pytest.mark.asyncio
async def test_stream_chat_with_context_preserves_sse_and_records_output(llm_env, monkeypatch):
    captured_starts: list[dict[str, Any]] = []
    observation = SimpleNamespace(updates=[])

    def _start_observation(**kwargs):
        captured_starts.append(kwargs)
        return _ObservationContext(observation)

    def _update_observation(obs, **kwargs):
        obs.updates.append(kwargs)

    async def _fake_acompletion(**kwargs):
        del kwargs
        tool_call = SimpleNamespace(
            index=0,
            id="call-1",
            function=SimpleNamespace(name="tool__web_search", arguments='{"query":"naga"}'),
        )
        return _FakeStreamResponse(
            [
                _build_chunk(content="hello ", reasoning="think "),
                _build_chunk(content="world", tool_calls=[tool_call]),
            ]
        )

    monkeypatch.setattr(llm_service, "start_llm_generation_observation", _start_observation)
    monkeypatch.setattr(langfuse_integration, "update_observation", _update_observation)
    monkeypatch.setattr(llm_service, "acompletion", _fake_acompletion)

    service = llm_service.LLMService()
    chunks = [
        chunk
        async for chunk in service.stream_chat_with_context(
            messages=[{"role": "user", "content": "hello"}],
            temperature=0.4,
            tools=[{"type": "function", "function": {"name": "tool__web_search"}}],
        )
    ]

    payloads = [json.loads(chunk[6:].strip()) for chunk in chunks]
    assert [payload["type"] for payload in payloads] == ["reasoning", "content", "content", "tool_calls_native"]
    assert captured_starts[0]["name"] == "llm.stream_chat_with_context"
    assert captured_starts[0]["stream"] is True
    assert observation.updates == [
        {
            "output": {
                "content": "hello world",
                "reasoning_content": "think ",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "name": "tool__web_search",
                        "arguments": '{"query":"naga"}',
                    }
                ],
            }
        }
    ]


def test_tool_observation_helpers_build_expected_name_and_status(monkeypatch):
    captured_starts: list[dict[str, Any]] = []
    observation = SimpleNamespace(updates=[])

    def _start_observation(**kwargs):
        captured_starts.append(kwargs)
        return _ObservationContext(observation)

    def _update_observation(obs, **kwargs):
        obs.updates.append(kwargs)

    monkeypatch.setattr(langfuse_integration, "start_observation", _start_observation)
    monkeypatch.setattr(langfuse_integration, "update_observation", _update_observation)

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
