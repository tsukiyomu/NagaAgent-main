"""Reusable failure-attribution helpers for stream/workflow tests."""

from __future__ import annotations

from typing import Any


_ALLOWED_FINAL_STATUS = {"success", "degraded", "failed"}
_ALLOWED_FAILURE_STAGE = {
    "none",
    "llm_output_parse",
    "tool_call_normalize",
    "tool_dispatch",
    "tool_result_injection",
    "context_assembly",
    "summary_round",
    "finalize",
}


def build_failure_attribution(
    case_id: str,
    stream_text: str,
    report: dict[str, Any],
    failure_stage: str | None = None,
) -> dict[str, Any]:
    """Build a minimal workflow failure-attribution record.

    This is test-harness level reporting:
    - deterministic fields for CI diffs and regression tracking
    - no dependency on external tracing systems
    """
    has_error_event = "data: error:" in stream_text
    round_count = stream_text.count('"type":"round_end"') + stream_text.count('"type": "round_end"')
    tool_call_count = stream_text.count('"type":"tool_calls"') + stream_text.count('"type": "tool_calls"')
    summary_triggered = '"summary":true' in stream_text or '"summary": true' in stream_text

    if report["active_cleaned"] and report["finalize_called"] >= 1:
        if has_error_event or not report["done_seen"]:
            final_status = "degraded"
        else:
            final_status = "success"
    else:
        final_status = "failed"

    if failure_stage is None:
        if not report["active_cleaned"] or report["finalize_called"] == 0:
            failure_stage = "finalize"
        elif has_error_event:
            failure_stage = "tool_dispatch"
        else:
            failure_stage = "none"

    payload = {
        "case_id": case_id,
        "final_status": final_status,
        "failure_stage": failure_stage,
        "rounds": round_count,
        "tool_call_count": tool_call_count,
        "summary_triggered": summary_triggered,
        "unhandled_exception": final_status == "failed",
    }
    assert_failure_attribution_shape(payload)
    return payload


def assert_failure_attribution_shape(payload: dict[str, Any]) -> None:
    """Hard-assert a stable minimal schema for attribution records."""
    required_keys = {
        "case_id",
        "final_status",
        "failure_stage",
        "rounds",
        "tool_call_count",
        "summary_triggered",
        "unhandled_exception",
    }
    assert set(payload.keys()) == required_keys
    assert isinstance(payload["case_id"], str) and payload["case_id"]
    assert payload["final_status"] in _ALLOWED_FINAL_STATUS
    assert payload["failure_stage"] in _ALLOWED_FAILURE_STAGE
    assert isinstance(payload["rounds"], int) and payload["rounds"] >= 0
    assert isinstance(payload["tool_call_count"], int) and payload["tool_call_count"] >= 0
    assert isinstance(payload["summary_triggered"], bool)
    assert isinstance(payload["unhandled_exception"], bool)
