import pytest


@pytest.mark.smoke
@pytest.mark.blocking
def test_health_smoke(client):
    """P2 基线健康检查: 服务可启动、路由可访问、基础状态可读。"""
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "healthy"
    assert "agent_ready" in body


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
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "success"
    assert body["response"] == "smoke-chat-ok"
    assert body.get("session_id")


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
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        stream_text = "".join(response.iter_text())

    assert "data: session_id:" in stream_text
    assert "smoke-stream-ok" in stream_text
    assert "data: [DONE]" in stream_text
