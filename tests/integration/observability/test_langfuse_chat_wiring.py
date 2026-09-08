"""Real route -> loop -> LLM service -> scripted provider, with a real SDK.

Default uses an in-memory exporter. LAN variant is explicitly opted in, permits
only the saved private Langfuse endpoint, and uploads synthetic data only.
"""
import json
import os
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace as NS
from urllib.parse import urlsplit

import pytest

from tests.integration.chat_stream.test_resilience import stream_env  # shared route isolation fixture
from tests.unit.test_langfuse_runtime import sdk, chunk, response  # real SDK offline contract fixture


@pytest.fixture
def scripted_provider(monkeypatch):
    from apiserver import llm_service as llm
    import apiserver.routes.chat as routes
    import apiserver.agentic_tool_loop as loop
    import apiserver.context_compressor as compressor

    calls = []
    tool_calls = []

    async def provider(**params):
        calls.append(params)
        if not params.get('stream'):
            return response()
        stream_call = sum(bool(item.get('stream')) for item in calls)

        async def chunks():
            # First actual invocation is empty: exercise the product's retry.
            if stream_call == 1:
                return
            if stream_call == 2:
                yield chunk('```tool\n' + json.dumps({'agentType': 'mcp', 'service_name': 'synthetic',
                                                     'tool_name': 'lookup', 'input': 'synthetic-only'}) + '\n```')
            else:
                yield chunk('synthetic-final-answer')
            yield chunk(usage=NS(prompt_tokens=11, completion_tokens=7, total_tokens=18))

        return chunks()

    async def execute(call, **kwargs):
        tool_calls.append(call)
        return {'status': 'success', 'result': 'synthetic-tool-result', 'service_name': 'synthetic', 'tool_name': 'lookup'}

    async def compress(messages):
        return NS(compressed=False, messages=messages, sse_events=[])

    service = llm.LLMService()
    monkeypatch.setattr(llm, 'acompletion', provider)
    monkeypatch.setattr(llm, 'get_llm_service', lambda: service)
    monkeypatch.setattr(routes, 'get_llm_service', lambda: service)
    monkeypatch.setattr(service, '_get_llm_params', lambda: {'api_key': 'synthetic-only'})
    monkeypatch.setattr(service, '_get_overridden_llm_params', lambda *a: {'api_key': 'synthetic-only'})
    monkeypatch.setattr(service, '_get_model_name', lambda *a, **kw: 'openai/synthetic')
    monkeypatch.setattr(loop, '_execute_mcp_call', execute)
    monkeypatch.setattr(compressor, 'compress_context', compress)
    return NS(calls=calls, tool_calls=tool_calls)


def exercise_routes(env, provider):
    payload = {'message': 'MIG-5 synthetic-only Langfuse verification', 'temporary': True, 'disable_tts': True}
    nonstream = env.client.post('/chat', json=payload)
    assert nonstream.status_code == 200
    assert nonstream.json()['response'] == 'synthetic-answer'
    stream = env.client.post('/chat/stream', json=payload)
    assert stream.status_code == 200 and 'synthetic-final-answer' in stream.text
    # Current upstream real LLM service ends by iterator exhaustion; unlike the
    # historical fake-loop profile it does not supply a [DONE] event. MIG-5 does
    # not rewrite that business protocol to make an observability probe pass.
    terminal = json.loads(stream.text.strip().split('\n\n')[-1].removeprefix('data: '))
    assert terminal == {'type': 'round_end', 'round': 2, 'has_more': False}
    assert len(provider.calls) == 4  # non-stream + empty retry + tool round + answer round
    assert len(provider.tool_calls) == 1 and len(env.save_calls) == 2
    return {'non_stream_session': nonstream.json()['session_id'],
            'stream_session': next(line.removeprefix('data: session_id:').strip()
                                   for line in stream.text.splitlines() if line.startswith('data: session_id:'))}


def test_routes_real_sdk_retry_tool_tree(sdk, stream_env, scripted_provider):
    sessions = exercise_routes(stream_env, scripted_provider)
    spans = sdk.spans()
    roots = [span for span in spans if span.parent is None]
    assert sorted(span.name for span in roots) == ['chat.request', 'chat.stream']
    root = next(span for span in roots if span.name == 'chat.stream')
    children = [span for span in spans if span.parent and span.parent.span_id == root.context.span_id]
    assert sorted(span.name for span in children) == ['llm.generation'] * 3 + ['tool.synthetic.lookup']
    assert len(spans) == 7
    assert all(span.attributes['session.id'] == sessions['stream_session'] for span in children + [root])
    generations = [span for span in children if span.name == 'llm.generation']
    assert sorted(span.attributes['langfuse.observation.metadata.attempt'] for span in generations) == [1, 1, 2]


@pytest.fixture
def lan_sdk(monkeypatch):
    if os.environ.get('NAGA_ENABLE_LANGFUSE_LAN_TESTS') != '1':
        pytest.skip('Synthetic LAN Langfuse upload/readback is opt-in')
    import httpx
    from dotenv import dotenv_values
    from apiserver import langfuse_integration as bridge
    from tests.conftest import _offline_bootstrap

    root = Path(__file__).resolve().parents[3]
    saved = dotenv_values(root / '.env')
    keys = ('LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY', 'LANGFUSE_BASE_URL')
    if not all(saved.get(key) for key in keys):
        pytest.fail('Saved .env lacks the three Langfuse settings', pytrace=False)
    base = saved['LANGFUSE_BASE_URL'].rstrip('/')
    parsed = urlsplit(base)
    assert parsed.scheme in ('http', 'https') and not any((parsed.username, parsed.password, parsed.query,
                                                         parsed.fragment, parsed.path))
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    monkeypatch.setenv('OTEL_SDK_DISABLED', 'false')
    monkeypatch.setenv('LANGFUSE_TRACING_ENABLED', 'true')
    monkeypatch.setenv('LANGFUSE_CAPTURE_CONTENT', 'true')  # only synthetic fixtures in this test
    monkeypatch.setenv('NO_PROXY', parsed.hostname)
    monkeypatch.setenv('no_proxy', parsed.hostname)
    for key in keys:
        monkeypatch.setenv(key, saved[key])
    monkeypatch.setattr(bridge, '_dotenv_loaded', True)
    monkeypatch.setattr(bridge, '_client_initialized', False)
    monkeypatch.setattr(bridge, '_langfuse_client', None)
    trace_ids = {}
    with _offline_bootstrap.allow_langfuse_lan(parsed.hostname, port):
        with httpx.Client(base_url=base, auth=(saved[keys[0]], saved[keys[1]]), trust_env=False,
                          timeout=5, follow_redirects=False) as api:
            health = api.get('/api/public/health')
            assert health.status_code == 200
            projects = api.get('/api/public/projects')
            assert projects.status_code == 200
            client = bridge.get_langfuse_client()
            assert client is not None
            original = client.start_observation

            def start(**kwargs):
                observation = original(**kwargs)
                if kwargs['name'] in ('chat.request', 'chat.stream'):
                    trace_ids[kwargs['name']] = observation.trace_id
                return observation

            monkeypatch.setattr(client, 'start_observation', start)
            try:
                yield NS(client=client, api=api, trace_ids=trace_ids, base=base, root=root,
                         version=health.json().get('version'), project_id=projects.json()['data'][0]['id'])
            finally:
                # The stream_env lifecycle normally owns shutdown, before this permit closes.
                bridge.shutdown_langfuse()


def test_lan_synthetic_upload_and_readback(lan_sdk, stream_env, scripted_provider):
    sessions = exercise_routes(stream_env, scripted_provider)
    lan_sdk.client.flush()
    traces = []
    for name, trace_id in lan_sdk.trace_ids.items():
        deadline = time.monotonic() + 45
        expected = 2 if name == 'chat.request' else 5
        while True:
            result = lan_sdk.api.get('/api/public/traces/' + trace_id)
            data = result.json() if result.status_code == 200 else {}
            observations = data.get('observations', [])
            if len(observations) == expected and all(item.get('endTime') for item in observations):
                break
            assert time.monotonic() < deadline, f'Synthetic trace {trace_id}: readback incomplete, HTTP {result.status_code}'
            time.sleep(2)
        assert data['sessionId'] == sessions['non_stream_session' if name == 'chat.request' else 'stream_session']
        root_observation = next(item for item in observations if item['name'] == name)
        children = [item for item in observations if item['id'] != root_observation['id']]
        assert all(item['parentObservationId'] == root_observation['id'] for item in children)
        assert len([item for item in children if item['type'] == 'GENERATION']) == (1 if expected == 2 else 3)
        assert 'synthetic' in json.dumps(data.get('output'))
        # Whitelisted proof, not a dump of authenticated response bodies or keys.
        traces.append({'trace_id': trace_id, 'name': name, 'session_id': data['sessionId'],
                       'observations': [{key: item.get(key) for key in
                                         ('id', 'name', 'type', 'parentObservationId', 'level', 'startTime', 'endTime')}
                                        for item in observations], 'synthetic_content_readback': True,
                       'parentage_verified': True})
    assert len(traces) == 2
    report = {'server_version': lan_sdk.version, 'base_url': lan_sdk.base, 'project_id': lan_sdk.project_id,
              'sdk_version': '4.15.1', 'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'worktree': 'MIG-5 implementation under verification', 'traces': traces,
              'real': ['FastAPI route', 'agentic loop', 'LLM service', 'tool dispatcher', 'Langfuse SDK', 'LAN server'],
              'synthetic': ['provider output', 'MCP result', 'prompt', 'user input'],
              'isolated': ['remote memory', 'persistence', 'other TCP destinations']}
    output = lan_sdk.root / 'tests/artifacts/upstream_migration/mig-5/lan-readback.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Synthetic LAN readback verified: ' + str(output))
