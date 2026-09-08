"""Runtime-only tracing boundaries. Never retain an active span across `yield`."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import json
from typing import Any

from . import langfuse_integration as bridge

_current: ContextVar[Any] = ContextVar("naga_langfuse_operation", default=None)


@contextmanager
def _new_request_context():
    """A root has no ambient parent or baggage from a previously handled request."""
    from opentelemetry.context import Context, attach, detach

    token = attach(Context())
    try:
        yield
    finally:
        detach(token)


def _bounded_text(previous: str, addition: str) -> str:
    # Discard an overflowing field instead of exporting a truncated secret prefix.
    if previous == "<truncated>" or len(previous) + len(addition) > 4000:
        return "<truncated>"
    return previous + addition


class Operation:
    def __init__(self, name: str, *, root=False, session_id=None, **fields):
        self.observation = None
        self.ended = False
        parent = None if root else _current.get()
        self.session_id = session_id or (parent.session_id if parent else None)
        self.root = self if root or parent is None else parent.root
        try:
            client = bridge.get_langfuse_client()
            if client is not None:
                with _new_request_context() if root else bridge.nullcontext():
                    with bridge.propagate_langfuse_attributes(session_id=self.session_id):
                        self.observation = client.start_observation(**bridge.observation_fields(dict(name=name, **fields)))
        except Exception:
            bridge.logger.debug("[Langfuse] Runtime observation unavailable")

    @contextmanager
    def activate(self):
        token = _current.set(self)
        try:
            def context():
                from opentelemetry.trace import use_span
                # SDK 4.15.1's span bridge is isolated here and covered by a real-SDK
                # contract test. Disable automatic exception/stack capture.
                return use_span(self.observation._otel_span, end_on_exit=False,
                                record_exception=False, set_status_on_exception=False)

            with bridge._safe_sdk_context(context) if self.observation is not None else bridge.nullcontext():
                with bridge.propagate_langfuse_attributes(session_id=self.session_id):
                    yield self
        finally:
            _current.reset(token)

    def update(self, **fields):
        bridge.update_observation(self.observation, **fields)

    def error(self, error: BaseException):
        # Exception text/stack may contain auth tokens or arbitrary customer data.
        self.update(level="WARNING" if isinstance(error, (asyncio.CancelledError, GeneratorExit)) else "ERROR",
                    status_message=type(error).__name__)

    def end(self):
        if not self.ended:
            self.ended = True
            try:
                if self.observation is not None:
                    self.observation.end()
            except Exception:
                bridge.logger.debug("[Langfuse] Runtime end failed")


def set_chat_session(session_id: str):
    """Use the product-created session id; tracing must not create product state."""
    operation = _current.get()
    if operation:
        operation.root.session_id = session_id
        operation.session_id = session_id
        # Apply to the already-started root, without leaking baggage to the caller.
        with bridge.propagate_langfuse_attributes(session_id=session_id):
            pass


def trace_chat(function):
    @wraps(function)
    async def wrapped(request, *args, **kwargs):
        operation = Operation("chat.request", root=True, session_id=request.session_id,
                              input={"message": request.message}, metadata={"mode": "non_stream"})
        try:
            with operation.activate():
                result = await function(request, *args, **kwargs)
                operation.update(output={"content": result.response}, metadata={"result": "completed"})
                return result
        except BaseException as error:
            operation.error(error)
            raise
        finally:
            operation.end()
    return wrapped


async def trace_chat_stream(iterator, request):
    operation = Operation("chat.stream", root=True, session_id=request.session_id,
                          input={"message": request.message}, metadata={"mode": "stream"})
    content = ""
    events = 0
    business_error = None
    try:
        while True:
            try:
                with operation.activate():
                    chunk = await anext(iterator)
            except StopAsyncIteration:
                break
            # Never copy raw SSE: auth-refresh messages contain credentials.
            events += 1
            try:
                payload = chunk.removeprefix('data:').strip()
                if payload.startswith('error:'):
                    operation.update(level="ERROR", status_message="stream_error")
                elif payload.startswith('{'):
                    event = json.loads(payload)
                    if event.get('type') in ('content', 'content_clean'):
                        previous = '' if event['type'] == 'content_clean' else content
                        content = _bounded_text(previous, str(event.get('text', '')))
                    elif event.get('type') in ('error', 'auth_expired'):
                        operation.update(level="ERROR", status_message="stream_error")
            except Exception:
                pass
            yield chunk  # no active tracing context is retained while suspended
        operation.update(output={"content": content}, metadata={"events": events})
    except BaseException as error:
        business_error = error
        operation.error(error)
        raise
    finally:
        try:
            with operation.activate():
                await iterator.aclose()
        except Exception:
            if business_error is None:
                raise
            bridge.logger.debug("[Langfuse] Stream cleanup failed during existing error")
        finally:
            operation.end()


class ObservedLLMStream:
    def __init__(self, response, operation):
        self.response = response
        self.iterator = response.__aiter__()
        self.operation = operation
        self.content = ""
        self.reasoning = ""
        self.calls: dict[int, dict] = {}
        self.usage = None
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            with self.operation.activate():
                chunk = await anext(self.iterator)
            try:
                usage = bridge.extract_langfuse_usage_details(chunk)
                if usage is not None:
                    self.usage = usage
                for choice in chunk.choices:
                    delta = choice.delta
                    self.content = _bounded_text(self.content, getattr(delta, 'content', None) or '')
                    self.reasoning = _bounded_text(self.reasoning, getattr(delta, 'reasoning_content', None) or '')
                    for call in getattr(delta, 'tool_calls', None) or []:
                        if len(self.calls) >= 20 and call.index not in self.calls:
                            continue
                        record = self.calls.setdefault(call.index, {'id': '', 'name': '', 'arguments': ''})
                        record['id'] = call.id or record['id']
                        if call.function:
                            record['name'] = call.function.name or record['name']
                            record['arguments'] = _bounded_text(record['arguments'], call.function.arguments or '')
            except Exception:
                pass  # malformed observability fields must not discard a business chunk
            return chunk
        except StopAsyncIteration:
            self.finish()
            raise
        except BaseException as error:
            self.operation.error(error)
            self.finish()
            raise

    def finish(self):
        if self.operation.ended:
            return
        self.operation.update(output={'content': self.content, 'reasoning_content': self.reasoning,
                                      'tool_calls': list(self.calls.values())}, usage_details=self.usage)
        self.operation.end()

    async def aclose(self):
        if self.closed:
            return
        self.closed = True
        if not self.operation.ended:
            self.operation.error(GeneratorExit())
            self.finish()
        close = getattr(self.response, 'aclose', None)
        if close:
            try:
                await close()
            except Exception:
                bridge.logger.debug("[Langfuse] Provider stream cleanup failed")


async def traced_completion(completion, *, observation_attempt=1, **params):
    """One observation per actual provider invocation, inside the existing retry loop."""
    operation = Operation("llm.generation", as_type="generation", input=params.get('messages'),
                          model=params.get('model'), metadata={'attempt': observation_attempt},
                          model_parameters=bridge.build_langfuse_model_parameters(
                              temperature=params.get('temperature'), max_tokens=params.get('max_tokens'),
                              stream=bool(params.get('stream')), tools=params.get('tools')))
    try:
        with operation.activate():
            response = await completion(**params)
        if params.get('stream'):
            return ObservedLLMStream(response, operation)
        try:
            message = response.choices[0].message
            operation.update(output={'content': message.content, 'reasoning_content': getattr(message, 'reasoning_content', None)},
                             usage_details=bridge.extract_langfuse_usage_details(response))
        except Exception:
            pass
        operation.end()
        return response
    except BaseException as error:
        operation.error(error)
        operation.end()
        raise


async def close_observed_stream(response):
    if isinstance(response, ObservedLLMStream):
        await response.aclose()


async def trace_tool(awaitable, call, session_id, source_agent_id=None):
    operation = Operation(bridge.get_langfuse_tool_observation_name(call), as_type="tool",
                          session_id=session_id, input=call,
                          metadata={'agent_type': call.get('agentType'), 'source_agent_id': source_agent_id})
    try:
        with operation.activate():
            result = await awaitable
        is_error = isinstance(result, dict) and result.get('status') == 'error'
        operation.update(output=result, level='ERROR' if is_error else 'DEFAULT',
                         status_message='tool_error' if is_error else None)
        return result
    except BaseException as error:
        operation.error(error)
        raise
    finally:
        operation.end()
