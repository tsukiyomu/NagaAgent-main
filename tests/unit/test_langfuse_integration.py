from __future__ import annotations

"""Unit tests for the Langfuse adapter boundary.

These tests stay intentionally local:
- no real Langfuse client
- no real network calls
- assertions target the helper contract that call sites rely on
"""

from types import SimpleNamespace
from typing import Any
import asyncio
import importlib.util
from pathlib import Path
import socket
import sys

import pytest

pytestmark = [pytest.mark.unit]

# apiserver/__init__.py eagerly imports api_server (config, routes and services).
# Exercise the real, standalone adapter source without bootstrapping the API.
_adapter_path = Path(__file__).resolve().parents[2] / "apiserver" / "langfuse_integration.py"
_adapter_spec = importlib.util.spec_from_file_location("langfuse_adapter_under_test", _adapter_path)
assert _adapter_spec is not None and _adapter_spec.loader is not None
langfuse_integration = importlib.util.module_from_spec(_adapter_spec)
_adapter_spec.loader.exec_module(langfuse_integration)


@pytest.fixture(autouse=True)
def isolated_adapter(monkeypatch, tmp_path):
    """Never read project credentials or instantiate a real SDK, even on a dev PC."""
    monkeypatch.setattr(langfuse_integration, "_dotenv_loaded", True)
    monkeypatch.setattr(langfuse_integration, "_ENV_PATH", tmp_path / "absent.env")
    monkeypatch.setattr(langfuse_integration, "_client_initialized", False)
    monkeypatch.setattr(langfuse_integration, "_langfuse_client", None)
    monkeypatch.setitem(sys.modules, "langfuse", None)
    # Legacy helper payload contracts explicitly opt into synthetic content.
    monkeypatch.setenv("LANGFUSE_CAPTURE_CONTENT", "true")
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "true")
    for key in langfuse_integration._LANGFUSE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    connections = []

    def block_network(*args, **kwargs):
        connections.append(True)
        raise AssertionError("Network is forbidden in adapter unit tests")

    monkeypatch.setattr(socket.socket, "connect", block_network)
    monkeypatch.setattr(socket.socket, "connect_ex", block_network)
    monkeypatch.setattr(socket, "create_connection", block_network)
    yield
    assert connections == [], "Adapter attempted a network connection"


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


class _SDKContext:
    def __init__(self, events, observation, failure=None, suppress=False):
        self.events = events
        self.observation = observation
        self.failure = failure
        self.suppress = suppress

    def __enter__(self):
        self.events.append("enter")
        if self.failure == "enter":
            raise RuntimeError("telemetry enter failed")
        return self.observation

    def __exit__(self, exc_type, exc, tb):
        self.events.append(("exit", exc))
        if self.failure == "exit":
            raise RuntimeError("telemetry exit failed")
        return self.suppress


def _install_context(monkeypatch, boundary, events, failure=None, suppress=False):
    observation = object()

    def factory(**kwargs):
        events.append(("create", kwargs))
        if failure == "create":
            raise RuntimeError("telemetry creation failed")
        return _SDKContext(events, observation, failure, suppress)

    client = SimpleNamespace(start_as_current_observation=factory)
    monkeypatch.setattr(langfuse_integration, "get_langfuse_client", lambda: client)
    monkeypatch.setitem(sys.modules, "langfuse", SimpleNamespace(propagate_attributes=factory))
    if boundary == "observation":
        context = langfuse_integration.start_observation(name="synthetic.request")
    else:
        context = langfuse_integration.propagate_langfuse_attributes(session_id="synthetic-session")
    return context, observation


@pytest.mark.parametrize("boundary", ["observation", "attributes"])
@pytest.mark.parametrize("failure", [None, "create", "enter", "exit"])
def test_telemetry_context_failures_do_not_change_body_result(monkeypatch, boundary, failure):
    events = []
    context, observation = _install_context(monkeypatch, boundary, events, failure)
    body_results = []
    with context as current:
        assert current is (None if failure in ("create", "enter") else observation)
        body_results.append("business success")
    assert body_results == ["business success"]  # execute exactly once, including failed __enter__
    exits = [event for event in events if isinstance(event, tuple) and event[0] == "exit"]
    assert exits == ([] if failure in ("create", "enter") else [("exit", None)])


@pytest.mark.parametrize("boundary", ["observation", "attributes"])
@pytest.mark.parametrize("failure,suppress", [(None, False), (None, True), ("exit", False), ("enter", False)])
@pytest.mark.parametrize("error_type", [ValueError, asyncio.CancelledError, GeneratorExit])
def test_original_body_exception_survives_sdk_cleanup(monkeypatch, boundary, failure, suppress, error_type):
    events = []
    context, _ = _install_context(monkeypatch, boundary, events, failure, suppress)
    error = error_type("business failure")
    with pytest.raises(error_type) as caught:
        with context:
            raise error
    assert caught.value is error
    exits = [event for event in events if isinstance(event, tuple) and event[0] == "exit"]
    assert exits == ([] if failure == "enter" else [("exit", error)])


def _set_credentials(monkeypatch):
    for key in langfuse_integration._LANGFUSE_ENV_KEYS:
        monkeypatch.setenv(key, "synthetic-test-only")


@pytest.mark.parametrize("missing_key", langfuse_integration._LANGFUSE_ENV_KEYS)
def test_incomplete_configuration_is_disabled(monkeypatch, missing_key):
    _set_credentials(monkeypatch)
    monkeypatch.setenv(missing_key, "  ")
    calls = []
    monkeypatch.setitem(sys.modules, "langfuse", SimpleNamespace(Langfuse=lambda **kwargs: calls.append(True)))
    assert langfuse_integration.get_langfuse_client() is None
    assert not langfuse_integration.is_langfuse_enabled()
    assert calls == []


@pytest.mark.parametrize("failure", [False, True])
def test_client_initialization_is_cached_on_success_and_failure(monkeypatch, failure):
    _set_credentials(monkeypatch)
    calls = []
    client = object()

    def get_client(**kwargs):
        calls.append(True)
        if failure:
            raise RuntimeError("synthetic init failure")
        return client

    monkeypatch.setitem(sys.modules, "langfuse", SimpleNamespace(Langfuse=get_client))
    assert langfuse_integration.get_langfuse_client() is (None if failure else client)
    assert langfuse_integration.get_langfuse_client() is (None if failure else client)
    assert calls == [True]


def test_missing_sdk_is_optional(monkeypatch):
    _set_credentials(monkeypatch)
    assert langfuse_integration.get_langfuse_client() is None
    with langfuse_integration.start_observation(name="disabled") as observation:
        assert observation is None
    with langfuse_integration.propagate_langfuse_attributes(session_id="synthetic") as attributes:
        assert attributes is None


def test_dotenv_is_loaded_once_without_overriding_process_env(monkeypatch):
    calls = []
    monkeypatch.setattr(langfuse_integration, "_dotenv_loaded", False)
    path = SimpleNamespace(exists=lambda: True)
    monkeypatch.setattr(langfuse_integration, "_ENV_PATH", path)
    monkeypatch.setitem(sys.modules, "dotenv", SimpleNamespace(
        load_dotenv=lambda *args, **kwargs: calls.append((args, kwargs)),
    ))
    langfuse_integration._load_project_dotenv()
    langfuse_integration._load_project_dotenv()
    assert calls == [((path,), {"override": False})]


def test_dotenv_loader_failure_is_optional(monkeypatch):
    monkeypatch.setattr(langfuse_integration, "_dotenv_loaded", False)
    monkeypatch.setitem(sys.modules, "dotenv", None)
    assert langfuse_integration.get_langfuse_client() is None


def test_attribute_whitelist_and_empty_noop(monkeypatch):
    captured = []
    monkeypatch.setattr(langfuse_integration, "get_langfuse_client", lambda: object())
    monkeypatch.setitem(sys.modules, "langfuse", SimpleNamespace(
        propagate_attributes=lambda **kwargs: captured.append(kwargs) or _ObservationContext(None),
    ))
    with langfuse_integration.propagate_langfuse_attributes():
        pass
    assert captured == []
    fields = dict(session_id="synthetic", user_id="fake-user", metadata={"revision": "test"},
                  version="test", tags=["unit"], trace_name="test-request")
    with langfuse_integration.propagate_langfuse_attributes(**fields):
        pass
    assert captured == [fields]


def test_payload_is_bounded_without_mutating_original():
    compact = langfuse_integration.compact_langfuse_payload
    original = {"text": "abcde", "nested": {"key": "value"}}
    assert compact(original, max_string=3) == {"text": "abc...<truncated>", "nested": {"key": "val...<truncated>"}}
    assert original == {"text": "abcde", "nested": {"key": "value"}}
    assert compact({"nested": {"key": "value"}}, max_depth=2) == {"nested": {"key": "<truncated>"}}
    assert compact(list(range(25))) == list(range(20)) + ["<truncated:5 more items>"]
    assert len(compact({str(i): i for i in range(45)})) == 41
    assert compact({str(i): i for i in range(45)})["__truncated__"] == "5 more keys"
    assert compact(b"synthetic") == "<bytes:9>"
    assert compact((None, True, 1, 1.5)) == [None, True, 1, 1.5]


def test_update_failure_does_not_escape():
    def fail(**kwargs):
        raise RuntimeError("synthetic update failure")

    langfuse_integration.update_observation(None, output="ok")
    langfuse_integration.update_observation(SimpleNamespace(update=fail), output="ok")


def test_error_recording_keeps_original_exception(monkeypatch):
    updates = []
    error = ValueError("x" * 600)
    observation = SimpleNamespace(update=lambda **kwargs: updates.append(kwargs))
    langfuse_integration.record_observation_error(observation, error)
    assert updates == [{"level": "ERROR", "status_message": "x" * 500}]
    assert str(error) == "x" * 600


@pytest.mark.parametrize("call,expected", [
    ({"service_name": "weather", "tool_name": "today"}, "tool.weather.today"),
    ({"agentType": "mcp", "tool_name": "today"}, "tool.mcp.today"),
    ({"agentType": "mcp"}, "tool.mcp"),
    ({}, "tool.tool"),
])
def test_tool_name_fallbacks(call, expected):
    assert langfuse_integration.get_langfuse_tool_observation_name(call) == expected


def test_tool_success_is_not_marked_error():
    updates = []
    observation = SimpleNamespace(update=lambda **kwargs: updates.append(kwargs))
    result = {"status": "success", "result": "ok"}
    langfuse_integration.complete_tool_observation(observation, result)
    assert updates == [{"output": result, "level": None, "status_message": None}]


def test_usage_absent_and_partial():
    assert langfuse_integration.extract_langfuse_usage_details(None) is None
    response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=0, completion_tokens=None, total_tokens="2"))
    assert langfuse_integration.extract_langfuse_usage_details(response) == {"input": 0}


def test_cleanup_does_not_initialize_an_unused_sdk(monkeypatch):
    calls = []
    monkeypatch.setattr(langfuse_integration, "get_langfuse_client", lambda: calls.append(True))
    langfuse_integration.flush_langfuse()
    langfuse_integration.shutdown_langfuse()
    assert calls == []


@pytest.mark.parametrize("failure", [None, "flush", "shutdown"])
def test_shutdown_cleans_up_once_even_when_flush_fails(monkeypatch, failure):
    calls = []

    def invoke(method):
        calls.append(method)
        if failure == method:
            raise RuntimeError("synthetic cleanup failure")

    client = SimpleNamespace(flush=lambda: invoke("flush"), shutdown=lambda: invoke("shutdown"))
    monkeypatch.setattr(langfuse_integration, "_client_initialized", True)
    monkeypatch.setattr(langfuse_integration, "_langfuse_client", client)
    langfuse_integration.shutdown_langfuse()
    langfuse_integration.shutdown_langfuse()
    assert calls == ["flush", "shutdown"]
    assert langfuse_integration.get_langfuse_client() is None


def test_flush_uses_existing_client_without_closing_it(monkeypatch):
    calls = []
    client = SimpleNamespace(flush=lambda: calls.append("flush"))
    monkeypatch.setattr(langfuse_integration, "_client_initialized", True)
    monkeypatch.setattr(langfuse_integration, "_langfuse_client", client)
    langfuse_integration.flush_langfuse()
    assert calls == ["flush"]
    assert langfuse_integration.get_langfuse_client() is client
