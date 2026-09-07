import pytest


@pytest.mark.smoke
@pytest.mark.blocking
def test_health_smoke(client):
    """P2 基线健康检查: 服务可启动、路由可访问、基础状态可读。"""
    response = client.get("/health")
    assert response.status_code == 200, (
        f"status wrong: GET /health expected HTTP 200, got {response.status_code}: {response.text}"
    )

    body = response.json()
    assert body.get("status") == "healthy", (
        f"status wrong: expected health status 'healthy', got {body.get('status')!r}"
    )
    assert "agent_ready" in body, f"agent_ready missing: response body was {body!r}"


@pytest.mark.smoke
@pytest.mark.blocking
def test_chat_non_stream_smoke(client):
    """非流式最小闭环: 请求入站 -> 会话创建 -> LLM链路返回 -> 标准响应封装。"""
    response = client.post(
        "/chat",
        json={
            "message": "ping",
            "temporary": True,
            "disable_tts": True,
        },
    )
    assert response.status_code == 200, (
        f"status wrong: POST /chat expected HTTP 200, got {response.status_code}: {response.text}"
    )

    body = response.json()
    assert body.get("status") == "success", (
        f"status wrong: expected chat status 'success', got {body.get('status')!r}"
    )
    assert body.get("response") == "smoke-chat-ok", (
        f"response wrong: expected 'smoke-chat-ok', got {body.get('response')!r}"
    )
    assert body.get("session_id"), f"session_id missing: response body was {body!r}"


@pytest.mark.smoke
@pytest.mark.blocking
def test_chat_stream_smoke_has_terminal_event(client):
    """流式可收尾: 建立 SSE -> 产生首段事件 -> 存在终止事件 [DONE]。"""
    with client.stream(
        "POST",
        "/chat/stream",
        json={
            "message": "ping",
            "temporary": True,
            "disable_tts": True,
        },
    ) as response:
        assert response.status_code == 200, (
            f"status wrong: POST /chat/stream expected HTTP 200, got {response.status_code}"
        )
        content_type = response.headers.get("content-type", "")
        assert content_type.startswith("text/event-stream"), (
            f"content-type wrong: expected text/event-stream, got {content_type!r}"
        )
        stream_text = "".join(response.iter_text())

    assert "data: session_id:" in stream_text, (
        f"session_id missing: stream payload was {stream_text!r}"
    )
    assert "smoke-stream-ok" in stream_text, (
        f"stream content missing: expected 'smoke-stream-ok', payload was {stream_text!r}"
    )
    assert "data: [DONE]" in stream_text, (
        f"DONE missing: stream payload was {stream_text!r}"
    )
