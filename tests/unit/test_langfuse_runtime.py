"""Real SDK / in-memory exporter contracts; no network or model inference."""
import asyncio
import json
import threading
from types import SimpleNamespace as NS
import uuid

import pytest
from opentelemetry import trace

from apiserver import langfuse_integration as bridge
from apiserver import langfuse_runtime as runtime


@pytest.fixture
def sdk(monkeypatch):
    from langfuse import Langfuse
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    monkeypatch.setenv('OTEL_SDK_DISABLED', 'false')
    monkeypatch.setenv('LANGFUSE_TRACING_ENABLED', 'true')
    monkeypatch.delenv('LANGFUSE_CAPTURE_CONTENT', raising=False)
    exporter = InMemorySpanExporter()
    client = Langfuse(public_key='pk-lf-synthetic-' + uuid.uuid4().hex,
                      secret_key='sk-lf-synthetic-only', base_url='http://127.0.0.1:9',
                      tracer_provider=TracerProvider(), span_exporter=exporter,
                      mask=bridge.redact_langfuse_payload)
    monkeypatch.setattr(bridge, '_langfuse_client', client)
    monkeypatch.setattr(bridge, '_client_initialized', True)
    monkeypatch.setattr(bridge, '_dotenv_loaded', True)

    def spans():
        client.flush()
        return exporter.get_finished_spans()

    yield NS(client=client, spans=spans)
    if bridge._langfuse_client is client:
        client.shutdown()


def field(span, key):
    return span.attributes.get('langfuse.observation.' + key)


def chunk(content=None, usage=None):
    return NS(choices=[] if content is None else [NS(delta=NS(content=content, reasoning_content=None,
                                                            tool_calls=None), finish_reason=None)], usage=usage)


def response(content='synthetic-answer'):
    return NS(choices=[NS(message=NS(content=content, reasoning_content='synthetic-reasoning'))],
              usage=NS(prompt_tokens=11, completion_tokens=7, total_tokens=18))


@pytest.mark.asyncio
async def test_sdk_root_session_parentage_and_default_no_content(sdk):
    async def completion(**kwargs):
        return response()

    @runtime.trace_chat
    async def route(request):
        runtime.set_chat_session('synthetic-session')
        result = await runtime.traced_completion(completion, messages=[{'content': request.message}], model='synthetic')
        return NS(response=result.choices[0].message.content)

    for _ in range(2):
        assert (await route(NS(session_id=None, message='private-input'))).response == 'synthetic-answer'
    spans = sdk.spans()
    roots = [span for span in spans if span.name == 'chat.request']
    assert len(roots) == 2 and len(spans) == 4
    assert len({span.context.trace_id for span in roots}) == 2
    for root in roots:
        assert root.parent is None
        children = [span for span in spans if span.parent and span.parent.span_id == root.context.span_id]
        assert len(children) == 1 and children[0].name == 'llm.generation'
        assert json.loads(field(children[0], 'usage_details')) == {'input': 11, 'output': 7, 'total': 18}
    for span in spans:
        assert span.attributes['session.id'] == 'synthetic-session'
        assert field(span, 'input') is None and field(span, 'output') is None
    assert runtime._current.get() is None
    assert not trace.get_current_span().get_span_context().is_valid


@pytest.mark.asyncio
async def test_interleaved_streams_do_not_leak_context_at_yield(sdk, monkeypatch):
    monkeypatch.setenv('LANGFUSE_CAPTURE_CONTENT', 'true')

    async def source(text):
        yield 'data: ' + json.dumps({'type': 'content', 'text': text}) + '\n\n'
        yield 'data: {"type":"token_refreshed","text":"never-export-this-token"}\n\n'
        yield 'data: [DONE]\n\n'

    streams = [runtime.trace_chat_stream(source(text), NS(session_id=text, message='synthetic'))
               for text in ('session-a', 'session-b')]
    for stream in streams:
        await anext(stream)
        assert runtime._current.get() is None
        assert not trace.get_current_span().get_span_context().is_valid
    for stream in streams:
        async for _ in stream:
            pass
    spans = sdk.spans()
    assert len(spans) == 2
    for span in spans:
        assert span.parent is None
        assert json.loads(field(span, 'output'))['content'] == span.attributes['session.id']
        assert 'never-export' not in str(span.attributes)


@pytest.mark.asyncio
async def test_stream_usage_only_chunk_and_explicit_close(sdk, monkeypatch):
    monkeypatch.setenv('LANGFUSE_CAPTURE_CONTENT', 'true')
    closed = []

    async def source():
        try:
            yield chunk('safe')
            yield chunk(usage=NS(prompt_tokens=3, completion_tokens=2, total_tokens=5))
        finally:
            closed.append(True)

    async def completion(**kwargs):
        return source()

    stream = await runtime.traced_completion(completion, stream=True, model='synthetic')
    chunks = [item async for item in stream]
    await stream.aclose()
    await stream.aclose()
    span, = sdk.spans()
    assert len(chunks) == 2 and closed == [True]
    assert json.loads(field(span, 'usage_details'))['total'] == 5
    assert json.loads(field(span, 'output'))['content'] == 'safe'


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel', [False, True])
async def test_early_close_or_cancel_ends_generation_and_root(sdk, cancel):
    closed = []
    entered = asyncio.Event()

    async def provider():
        try:
            yield chunk('partial')
            entered.set()
            await asyncio.Event().wait()
        finally:
            closed.append(True)

    async def completion(**kwargs):
        return provider()

    async def route():
        stream = await runtime.traced_completion(completion, stream=True)
        try:
            async for item in stream:
                yield 'data: {"type":"content","text":"partial"}\n\n'
        finally:
            await stream.aclose()

    stream = runtime.trace_chat_stream(route(), NS(session_id='synthetic-cancel', message='synthetic'))
    await anext(stream)
    if cancel:
        task = asyncio.create_task(anext(stream))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        await stream.aclose()
    spans = sdk.spans()
    assert len(spans) == 2 and closed == [True]
    assert all(field(span, 'level') == 'WARNING' for span in spans)
    assert all(not span.events for span in spans)  # no raw exception/stack recording
    assert runtime._current.get() is None


@pytest.mark.asyncio
async def test_real_dispatch_keeps_parallel_tools_siblings_and_failures(sdk, monkeypatch):
    from apiserver import agentic_tool_loop as loop

    started = []
    both_started = asyncio.Event()

    async def executor(call, **kwargs):
        started.append(call['tool_name'])
        if len(started) == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), 1)
        if call['tool_name'] == 'bad':
            raise ValueError('synthetic-secret-error')
        return {'status': 'success', 'result': 'synthetic-result'}

    monkeypatch.setattr(loop, '_execute_mcp_call', executor)
    root = runtime.Operation('chat.stream', root=True, session_id='synthetic-tools')
    with root.activate():
        results = await loop.execute_tool_calls([
            {'agentType': 'mcp', 'service_name': 'synthetic', 'tool_name': name} for name in ('ok', 'bad')
        ], 'synthetic-tools')
    root.end()
    assert [result['status'] for result in results] == ['success', 'error']
    spans = sdk.spans()
    parent = next(span for span in spans if span.name == 'chat.stream')
    children = [span for span in spans if span.name.startswith('tool.')]
    assert len(children) == 2
    assert all(span.parent.span_id == parent.context.span_id for span in children)
    failed = next(span for span in children if span.name.endswith('.bad'))
    assert field(failed, 'level') == 'ERROR' and field(failed, 'status_message') == 'ValueError'
    assert 'synthetic-secret-error' not in str(failed.attributes) and not failed.events


@pytest.mark.asyncio
async def test_tracing_failures_preserve_values_and_original_exception(monkeypatch):
    class BrokenObservation:
        def update(self, **kwargs):
            raise RuntimeError('observer unavailable')

        def end(self):
            raise RuntimeError('observer unavailable')

    monkeypatch.setattr(bridge, 'get_langfuse_client', lambda: NS(start_observation=lambda **kw: BrokenObservation()))
    monkeypatch.setattr(bridge, 'propagate_langfuse_attributes', lambda **kw: bridge.nullcontext())

    async def good():
        return 'legacy-non-dict-result'

    assert await runtime.trace_tool(good(), {}, 'synthetic') == 'legacy-non-dict-result'
    original = ValueError('original-business-error')

    async def bad(**kwargs):
        raise original

    with pytest.raises(ValueError) as caught:
        await runtime.traced_completion(bad)
    assert caught.value is original
    assert runtime._current.get() is None


def test_payload_policy_redacts_before_bounding(monkeypatch):
    secret = 'long-synthetic-' + 'z' * 5000
    monkeypatch.setenv('SYNTHETIC_SECRET', secret)
    monkeypatch.setenv('LANGFUSE_CAPTURE_CONTENT', 'true')
    payload = bridge.observation_fields({'input': {'api_key': 'private', 'text': secret,
                                                  'other': 'Bearer fake-token mail@example.test'}})
    encoded = json.dumps(payload)
    assert 'private' not in encoded and 'long-synthetic-' not in encoded
    assert 'fake-token' not in encoded and 'mail@example.test' not in encoded
    assert len(json.dumps(bridge.redact_langfuse_payload(data=['x' * 3999] * 20)).encode()) < 16000
    assert runtime._bounded_text('start', 'z' * 5000) == '<truncated>'


@pytest.mark.asyncio
async def test_shutdown_wait_is_bounded_off_loop_and_once(monkeypatch):
    release = threading.Event()
    finished = threading.Event()
    calls = []

    def flush():
        calls.append(threading.current_thread().name)
        release.wait(1)

    def shutdown():
        calls.append('shutdown')
        finished.set()

    monkeypatch.setattr(bridge, '_langfuse_client', NS(flush=flush, shutdown=shutdown))
    try:
        started = asyncio.get_running_loop().time()
        assert await bridge.shutdown_langfuse_async(timeout=0.03) is False
        assert asyncio.get_running_loop().time() - started < 0.5
        assert await bridge.shutdown_langfuse_async(timeout=0.03) is True
    finally:
        release.set()
        await asyncio.to_thread(finished.wait, 1)
    assert calls == ['naga-langfuse-shutdown', 'shutdown']
