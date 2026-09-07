"""Opt-in real-LLM smoke for the `/chat/stream` happy path.

Why this file exists:
- keep one thin end-to-end-ish check on the real model path
- do not make it part of the blocking PR gate
- keep side effects isolated while preserving the real route + real loop + real LLM path
"""

import os
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


pytestmark = [pytest.mark.integration, pytest.mark.real_llm]


async def _noop_async(*_args, **_kwargs):
    return None


def _request_payload():
    return {
        "message": "Please reply with one short plain sentence.",
        "temporary": True,
        "disable_tts": True,
    }


def _stream_run(client: TestClient, payload: dict | None = None):
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
    return SimpleNamespace(
        text=stream_text,
        sse_events=sse_events,
        ttfb_ms=None if first_chunk_at is None else int((first_chunk_at - started_at) * 1000),
        total_latency_ms=int((time.monotonic() - started_at) * 1000),
        event_count=len(sse_events),
        done_seen="data: [DONE]" in stream_text,
    )


def _publish_quality_gate_case(request, stream_run):
    request.node.user_properties.append(
        (
            "quality_gate_case",
            {
                "case_id": "real_llm_stream_smoke",
                "feature": "real_llm",
                "story": "performance",
                "blocking": False,
                "non_blocking": True,
                "final_status": "success",
                "failure_stage": "none",
                "metrics": {
                    "ttfb_ms": stream_run.ttfb_ms,
                    "total_latency_ms": stream_run.total_latency_ms,
                    "event_count": stream_run.event_count,
                    "tool_rounds": stream_run.text.count('"type":"round_end"')
                    + stream_run.text.count('"type": "round_end"'),
                    "tool_count": stream_run.text.count('"type":"tool_calls"')
                    + stream_run.text.count('"type": "tool_calls"'),
                    "retry_count": 0,
                    "workflow_timeout_count": 0,
                },
            },
        )
    )


@pytest.fixture
def real_llm_stream_env(monkeypatch):
    from apiserver.api_server import app
    import apiserver.routes.chat as chat_routes

    events = []
    save_calls = []

    async def _record_notify(event: str):
        events.append(event)

    def _record_save(session_id, user_message, response_text):
        save_calls.append((session_id, user_message, response_text))

    # Keep prompt/context deterministic, but preserve the real llm + real loop path.
    monkeypatch.setattr(chat_routes, "_build_agent_prompt_context", lambda _agent_id: None)
    monkeypatch.setattr(chat_routes, "build_system_prompt", lambda *args, **kwargs: "REAL_LLM_SMOKE_PROMPT")
    monkeypatch.setattr(chat_routes, "build_context_supplement", lambda *args, **kwargs: "REAL_LLM_SMOKE_SUPPLEMENT")
    monkeypatch.setattr(chat_routes, "_update_proactive_activity_silent", _noop_async)
    monkeypatch.setattr(chat_routes, "_notify_conversation_event", _record_notify)
    monkeypatch.setattr(chat_routes, "_save_conversation_and_logs", _record_save)
    monkeypatch.setattr(chat_routes, "emit_telemetry", lambda *_a, **_k: None)

    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            events=events,
            save_calls=save_calls,
        )


@pytest.mark.skipif(
    os.getenv("NAGA_ENABLE_REAL_LLM_TESTS") != "1",
    reason="requires opt-in and working real LLM credentials/config",
)
def test_chat_stream_real_llm_normal_smoke(real_llm_stream_env, request):
    """Non-blocking smoke for the real model path.

    This test intentionally stays thin:
    - real FastAPI route
    - real `run_agentic_loop(...)`
    - real `get_llm_service()`
    - deterministic prompt scaffolding
    - side effects converted to local ledgers/spies
    """
    stream_run = _stream_run(real_llm_stream_env.client)
    time.sleep(0.05)
    _publish_quality_gate_case(request, stream_run)

    from apiserver.message_queue import get_message_queue

    assert "data: session_id:" in stream_run.text
    assert (
        '"type":"round_end"' in stream_run.text
        or '"type": "round_end"' in stream_run.text
    )
    assert "auth_expired" not in stream_run.text
    assert "data: error:" not in stream_run.text
    assert "LLM服务不可用" not in stream_run.text
    assert "流式调用出错" not in stream_run.text
    assert stream_run.event_count >= 3
    assert real_llm_stream_env.events.count("ended") == 1
    assert len(real_llm_stream_env.save_calls) == 1
    assert not get_message_queue().is_conversation_active()
