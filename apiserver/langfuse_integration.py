from __future__ import annotations

import logging
import os
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any, Dict, List, Optional

# Best-effort Langfuse bridge for LLM and tool-call observability.
#
# This module stays intentionally thin and defensive:
# - call sites should not care whether Langfuse is configured or not
# - observability failures must never change chat/tool runtime behavior
# - large prompt/output payloads must be compacted before leaving the process

logger = logging.getLogger(__name__)

# Keep credential lookup anchored to the repo root so CLI, API server and other
# entrypoints do not need separate Langfuse bootstrap logic.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
_LANGFUSE_ENV_KEYS = (
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
)

_dotenv_loaded = False
_client_initialized = False
_langfuse_client: Any | None = None


def _load_project_dotenv() -> None:
    """Load `.env` once so every later credential check sees the same process state."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return

    _dotenv_loaded = True
    try:
        from dotenv import load_dotenv

        if _ENV_PATH.exists():
            load_dotenv(_ENV_PATH, override=False)
    except Exception as exc:
        logger.debug("[Langfuse] Failed to load .env: %s", exc)


def _has_langfuse_credentials() -> bool:
    """Treat Langfuse as enabled only when the full credential set is present."""
    _load_project_dotenv()
    return all((os.getenv(key) or "").strip() for key in _LANGFUSE_ENV_KEYS)


def is_langfuse_enabled() -> bool:
    """Cheap public check used by startup/logging code."""
    return get_langfuse_client() is not None


def get_langfuse_client() -> Any | None:
    """Return the shared Langfuse client, or None when observability is unavailable.

    The important contract here is not "always initialize Langfuse", but
    "never let observability bootstrap break the main runtime". Missing config
    and SDK init failures therefore collapse to `None` instead of raising.
    """
    global _client_initialized, _langfuse_client
    if _client_initialized:
        return _langfuse_client

    _client_initialized = True

    # Running without Langfuse is a valid deployment mode, so this stays INFO/no-op.
    if not _has_langfuse_credentials():
        logger.info("[Langfuse] Missing credentials, observability disabled")
        return None

    try:
        from langfuse import get_client

        _langfuse_client = get_client()
        logger.info("[Langfuse] Client initialized")
    except Exception as exc:
        logger.warning("[Langfuse] Initialization failed: %s", exc)
        _langfuse_client = None

    return _langfuse_client


def compact_langfuse_payload(value: Any, *, max_depth: int = 4, max_string: int = 4000) -> Any:
    """Shrink large/nested payloads into something trace-safe and readable.

    Trace payloads are useful only if they remain bounded and reviewable.
    We keep enough structure for debugging while deliberately losing detail once
    the payload becomes too deep, too wide, or too large.
    """
    if max_depth <= 0:
        return "<truncated>"

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, str):
        if len(value) <= max_string:
            return value
        return value[:max_string] + "...<truncated>"

    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"

    if isinstance(value, dict):
        items = list(value.items())[:40]
        compacted = {
            str(key)[:128]: compact_langfuse_payload(item, max_depth=max_depth - 1, max_string=max_string)
            for key, item in items
        }
        if len(value) > len(items):
            compacted["__truncated__"] = f"{len(value) - len(items)} more keys"
        return compacted

    # Collections are sampled rather than dumped in full to avoid trace blow-up.
    if isinstance(value, (list, tuple, set)):
        items = list(value)[:20]
        compacted = [
            compact_langfuse_payload(item, max_depth=max_depth - 1, max_string=max_string)
            for item in items
        ]
        if len(value) > len(items):
            compacted.append(f"<truncated:{len(value) - len(items)} more items>")
        return compacted

    return compact_langfuse_payload(str(value), max_depth=max_depth - 1, max_string=max_string)


def start_observation(*, name: str, as_type: str = "span", **kwargs: Any):
    """Start an observation while preserving a uniform call shape for callers.

    Call sites use `with ... as observation:` unconditionally. Returning
    `nullcontext(None)` keeps that shape intact even when Langfuse is disabled
    or the SDK rejects the observation start.
    """
    client = get_langfuse_client()
    if client is None:
        return nullcontext(None)

    try:
        return client.start_as_current_observation(name=name, as_type=as_type, **kwargs)
    except Exception as exc:
        logger.debug("[Langfuse] Failed to start observation %s: %s", name, exc)
        return nullcontext(None)


def update_observation(observation: Any | None, **kwargs: Any) -> None:
    """Best-effort update that never leaks telemetry failure back to business code."""
    if observation is None:
        return

    try:
        observation.update(**kwargs)
    except Exception as exc:
        logger.debug("[Langfuse] Failed to update observation: %s", exc)


def propagate_langfuse_attributes(
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    metadata: Dict[str, str] | None = None,
    version: str | None = None,
    tags: List[str] | None = None,
    trace_name: str | None = None,
):
    """Propagate supported trace-level attributes to child observations.

    Langfuse sessions are implemented via attribute propagation rather than
    observation constructor kwargs in the Python SDK.
    """
    client = get_langfuse_client()
    if client is None:
        return nullcontext(None)

    propagate_kwargs: Dict[str, Any] = {}
    if session_id:
        propagate_kwargs["session_id"] = session_id
    if user_id:
        propagate_kwargs["user_id"] = user_id
    if metadata:
        propagate_kwargs["metadata"] = metadata
    if version:
        propagate_kwargs["version"] = version
    if tags:
        propagate_kwargs["tags"] = tags
    if trace_name:
        propagate_kwargs["trace_name"] = trace_name

    if not propagate_kwargs:
        return nullcontext(None)

    try:
        from langfuse import propagate_attributes

        return propagate_attributes(**propagate_kwargs)
    except Exception as exc:
        logger.debug("[Langfuse] Failed to propagate attributes: %s", exc)
        return nullcontext(None)


def build_langfuse_model_parameters(
    *,
    temperature: Optional[float],
    max_tokens: Optional[int],
    stream: bool,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Record only the model-call knobs that help explain behavior later."""
    params: Dict[str, Any] = {
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    # The full tool schema already exists elsewhere in the call path; storing only
    # the count keeps traces smaller while still telling us whether tools mattered.
    if tools is not None:
        params["tool_count"] = len(tools)
    return params


def extract_langfuse_usage_details(response: Any) -> Dict[str, int] | None:
    """Normalize provider usage fields into one stable shape for downstream analysis."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None

    usage_details: Dict[str, int] = {}
    for source_key, target_key in (
        ("prompt_tokens", "input"),
        ("completion_tokens", "output"),
        ("total_tokens", "total"),
    ):
        value = getattr(usage, source_key, None)
        if isinstance(value, int):
            usage_details[target_key] = value

    return usage_details or None


def start_llm_generation_observation(
    *,
    name: str,
    messages: Any,
    model: str,
    metadata: Dict[str, Any] | None = None,
    temperature: Optional[float],
    max_tokens: Optional[int],
    stream: bool,
    tools: Optional[List[Dict[str, Any]]] = None,
):
    """Wrap one LLM call in a generation observation with compacted input metadata."""
    return start_observation(
        name=name,
        as_type="generation",
        input=compact_langfuse_payload(messages),
        model=model,
        metadata=metadata,
        model_parameters=build_langfuse_model_parameters(
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            tools=tools,
        ),
    )


def complete_llm_generation_observation(
    observation: Any | None,
    *,
    content: str,
    reasoning_content: Any = None,
    tool_calls: Any = None,
    response: Any | None = None,
) -> None:
    """Finalize a generation observation with the pieces most useful for replay/debug."""
    output: Dict[str, Any] = {
        "content": content,
        "reasoning_content": reasoning_content,
    }
    if tool_calls:
        output["tool_calls"] = tool_calls

    update_kwargs: Dict[str, Any] = {
        "output": compact_langfuse_payload(output),
    }
    usage_details = extract_langfuse_usage_details(response)
    if usage_details is not None:
        update_kwargs["usage_details"] = usage_details

    update_observation(observation, **update_kwargs)


def record_observation_error(observation: Any | None, error: Exception) -> None:
    """Mark the trace as failed without changing the original exception flow."""
    update_observation(
        observation,
        level="ERROR",
        status_message=str(error)[:500],
    )


def get_langfuse_tool_observation_name(call: Dict[str, Any]) -> str:
    """Build a stable tool span name from the normalized dispatch contract."""
    service_name = str(call.get("service_name") or "").strip()
    tool_name = str(call.get("tool_name") or "").strip()
    agent_type = str(call.get("agentType") or "tool").strip()

    if service_name and tool_name:
        return f"tool.{service_name}.{tool_name}"
    if tool_name:
        return f"tool.{agent_type}.{tool_name}"
    return f"tool.{agent_type}"


@contextmanager
def start_tool_observation(
    call: Dict[str, Any],
    *,
    session_id: str,
    source_agent_id: str | None = None,
):
    """Create one tool observation around a normalized dispatch item.

    We record the normalized contract rather than raw model text so traces align
    with the dispatcher/executor boundary that the runtime actually uses.
    """
    agent_type = str(call.get("agentType") or "").strip()
    with propagate_langfuse_attributes(session_id=session_id):
        with start_observation(
            name=get_langfuse_tool_observation_name(call),
            as_type="tool",
            input=compact_langfuse_payload(call),
            metadata={
                "session_id": session_id,
                "source_agent_id": source_agent_id,
                "agent_type": agent_type,
            },
        ) as observation:
            yield observation


def complete_tool_observation(observation: Any | None, result: Dict[str, Any]) -> None:
    """Finalize one tool observation with the normalized execution result."""
    is_error = result.get("status") == "error"
    update_observation(
        observation,
        output=compact_langfuse_payload(result),
        level="ERROR" if is_error else None,
        status_message=str(result.get("result", ""))[:500] if is_error else None,
    )


def shutdown_langfuse() -> None:
    """Flush and close the shared client during shutdown.

    Cleanup is best-effort only. Losing some telemetry on shutdown is acceptable;
    blocking process exit because Langfuse is slow or unavailable is not.
    """
    client = get_langfuse_client()
    if client is None:
        return

    try:
        if hasattr(client, "flush"):
            client.flush()
    except Exception as exc:
        logger.debug("[Langfuse] Flush failed: %s", exc)

    try:
        if hasattr(client, "shutdown"):
            client.shutdown()
    except Exception as exc:
        logger.debug("[Langfuse] Shutdown failed: %s", exc)


def flush_langfuse() -> None:
    """Best-effort flush for request-end visibility in interactive flows."""
    client = get_langfuse_client()
    if client is None:
        return

    try:
        if hasattr(client, "flush"):
            client.flush()
    except Exception as exc:
        logger.debug("[Langfuse] Flush failed: %s", exc)
