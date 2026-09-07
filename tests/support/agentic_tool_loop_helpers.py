"""Shared test helpers for `agentic_tool_loop` unit suites."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any


@dataclass
class EmptyQueueStub:
    """Queue stub whose `drain()` is always empty."""

    drain_calls: int = 0

    def drain(self):
        # Count how many times the loop tried to consume queued messages.
        self.drain_calls += 1
        return []


class OneShotQueuedMessageStub:
    """Queue stub that returns one queued message exactly once."""

    def __init__(self, *, source: str = "scheduler", content: str = "queue-msg-1"):
        self._returned = False
        self._message = SimpleNamespace(source=source, content=content)
        self.drain_calls = 0

    def drain(self):
        # Return the queued message on the first drain, then behave like an
        # empty queue afterwards.
        self.drain_calls += 1
        if self._returned:
            return []
        self._returned = True
        return [self._message]


class ScriptedStreamLLM:
    """Deterministic fake streaming LLM with per-round scripts."""

    def __init__(self, round_scripts: list[list[str]]):
        self._round_scripts = round_scripts
        self.calls: list[dict[str, Any]] = []

    async def stream_chat_with_context(
        self,
        messages,
        _temperature=0.7,
        model_override=None,
        tools=None,
        session_id=None,
    ):
        # This fake LLM ignores model_override because tests only care about
        # loop behavior, not model routing.
        del model_override

        # Use the number of previous calls to decide which scripted round
        # should be returned this time.
        call_index = len(self.calls)
        script_index = min(call_index, len(self._round_scripts) - 1)

        # Record the exact LLM input for later assertions.
        # deepcopy prevents later loop-side mutation from changing the capture.
        self.calls.append(
            {
                "messages": copy.deepcopy(messages),
                "tools": tools,
                "session_id": session_id,
            }
        )

        # Yield the preconfigured SSE chunks one by one to simulate streaming.
        for chunk in self._round_scripts[script_index]:
            yield chunk


def sse(payload: dict[str, Any]) -> str:
    """Encode one JSON payload as one SSE chunk."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def sse_done() -> str:
    """Encode the terminal SSE done chunk."""
    return "data: [DONE]\n\n"


def native_tool_call_chunk(
    call_id: str,
    *,
    tool_name: str = "tool__web_search",
    query: str = "naga",
    extra_args: dict[str, Any] | None = None,
) -> str:
    """Build one native `tool_calls_native` SSE chunk for the real parser."""
    # Start from the common query shape used across loop tests.
    args = {"query": query}

    # Allow tests to add extra function-call arguments without rebuilding the
    # whole native payload by hand.
    if extra_args:
        args.update(extra_args)

    # Match the loop's expected native tool-call event shape.
    native_calls = [
        {
            "id": call_id,
            "name": tool_name,
            "arguments": json.dumps(args, ensure_ascii=False),
        }
    ]
    return sse(
        {
            "type": "tool_calls_native",
            "text": json.dumps(native_calls, ensure_ascii=False),
        }
    )


def extract_sse_json_events(chunks: list[str]) -> list[dict[str, Any]]:
    """Parse loop SSE chunks into decoded JSON payloads when possible."""
    events: list[dict[str, Any]] = []
    for chunk in chunks:
        # Ignore anything that is not a normal SSE data line.
        if not chunk.startswith("data: "):
            continue
        payload = chunk[6:].strip()

        # Keep `[DONE]` as a synthetic event so tests can assert termination.
        if payload == "[DONE]":
            events.append({"type": "[DONE]"})
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            # Some tests may emit non-JSON text chunks; those are not part of
            # JSON event assertions.
            continue
    return events
