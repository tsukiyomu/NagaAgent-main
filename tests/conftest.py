import pytest
from fastapi.testclient import TestClient


async def _noop_async(*_args, **_kwargs):
    """Generic async no-op used to disable external side effects in smoke tests."""
    return None


class _DummyLLMService:
    """Deterministic LLM stub for /chat smoke assertions."""

    async def chat_with_context_and_reasoning(self, _messages, _temperature=0.7):
        # Keep response shape consistent with production code path.
        from apiserver.llm_service import LLMResponse

        # Fixed output makes smoke assertions stable and offline-runnable.
        return LLMResponse(content="smoke-chat-ok", reasoning_content="")


async def _fake_run_agentic_loop(
    _messages,
    _session_id,
    max_rounds=5,
    model_override=None,
    tools=None,
    source_agent_id=None,
):
    """Deterministic SSE stub for /chat/stream smoke assertions.

    Event contract (minimal):
    1) content event exists
    2) round_end exists
    3) terminal [DONE] exists
    """
    # Keep signature aligned with real implementation, but these are unused in stub mode.
    del max_rounds, model_override, tools, source_agent_id

    # Minimal stream content to prove the stream produced business payload.
    yield 'data: {"type":"content","text":"smoke-stream-ok"}\n\n'
    # End one round explicitly, mirroring real loop semantics.
    yield 'data: {"type":"round_end","round":1,"has_more":false}\n\n'
    # Terminal event required by stream smoke gate.
    yield "data: [DONE]\n\n"


@pytest.fixture
def client(monkeypatch):
    """Shared TestClient fixture for all smoke tests.

    Responsibilities:
    - start/stop FastAPI app lifecycle once per test via context manager
    - replace unstable dependencies with deterministic stubs
    - keep smoke tests offline and repeatable
    """
    from apiserver.api_server import app
    import apiserver.agentic_tool_loop as agentic_tool_loop
    import apiserver.routes.chat as chat_routes

    # ---- Context/prompt assembly stabilization ----
    # Disable agent-specific prompt context to avoid environment-dependent branches.
    monkeypatch.setattr(chat_routes, "_build_agent_prompt_context", lambda _agent_id: None)
    # Use fixed prompt text to avoid content drift between runs.
    monkeypatch.setattr(
        chat_routes, "build_system_prompt", lambda *args, **kwargs: "SMOKE_SYSTEM_PROMPT"
    )
    monkeypatch.setattr(
        chat_routes, "build_context_supplement", lambda *args, **kwargs: "SMOKE_SUPPLEMENT"
    )

    # ---- Model/tool path stabilization ----
    # Force non-native function-calling path for deterministic smoke behavior.
    monkeypatch.setattr(chat_routes, "_supports_function_calling", lambda _model_name: False)
    # Replace real LLM service with deterministic response stub.
    monkeypatch.setattr(chat_routes, "get_llm_service", lambda: _DummyLLMService())
    # Replace real agentic loop with deterministic SSE sequence.
    monkeypatch.setattr(agentic_tool_loop, "run_agentic_loop", _fake_run_agentic_loop)

    # ---- Side-effect isolation ----
    # Disable background activity update (could trigger external interactions).
    monkeypatch.setattr(chat_routes, "_update_proactive_activity_silent", _noop_async)
    # Disable remote conversation lifecycle notification.
    monkeypatch.setattr(chat_routes, "_notify_conversation_event", _noop_async)
    # Disable persistence writes for smoke scope.
    monkeypatch.setattr(chat_routes, "_save_conversation_and_logs", lambda *_args, **_kwargs: None)
    # Disable telemetry emission to keep tests pure/offline.
    monkeypatch.setattr(chat_routes, "emit_telemetry", lambda *_args, **_kwargs: None)

    # TestClient context ensures startup/shutdown events are handled correctly.
    # monkeypatch automatically restores originals after fixture teardown.
    with TestClient(app) as test_client:
        yield test_client
