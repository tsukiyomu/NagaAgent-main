"""Unit tests for reusable stream failure-attribution helpers."""

from __future__ import annotations

import pytest

from tests.support.failure_attribution import (
    assert_failure_attribution_shape,
    build_failure_attribution,
)


pytestmark = [pytest.mark.unit]


def _base_report(*, done_seen: bool, finalize_called: int, active_cleaned: bool) -> dict:
    return {
        "ttfb_ms": 5,
        "total_latency_ms": 25,
        "event_count": 4,
        "done_seen": done_seen,
        "finalize_called": finalize_called,
        "save_call_count": 1,
        "active_cleaned": active_cleaned,
    }


def test_failure_attribution_success_shape_and_defaults():
    """Success stream should map to default success attribution fields.

    Test path:
    1. Build one minimal successful stream with `round_end` and `[DONE]`.
    2. Pair it with a clean finalize report.
    3. The attribution helper should infer success defaults without overrides.
    """
    text = (
        'data: {"type":"content","text":"ok"}\n\n'
        'data: {"type":"round_end","round":1,"has_more":false}\n\n'
        "data: [DONE]\n\n"
    )
    payload = build_failure_attribution(
        "attr_success",
        text,
        _base_report(done_seen=True, finalize_called=1, active_cleaned=True),
    )

    assert payload["final_status"] == "success"
    assert payload["failure_stage"] == "none"
    assert payload["rounds"] == 1
    assert payload["tool_call_count"] == 0
    assert payload["summary_triggered"] is False
    assert payload["unhandled_exception"] is False


def test_failure_attribution_degraded_from_error_event():
    """Error-event stream should degrade to default `tool_dispatch` attribution.

    Test path:
    1. Build a partial stream followed by an `error:` event.
    2. Pair it with a report that finalized but did not see `[DONE]`.
    3. The attribution helper should classify the run as degraded.
    """
    text = (
        'data: {"type":"content","text":"partial"}\n\n'
        "data: error:midstream boom\n\n"
    )
    payload = build_failure_attribution(
        "attr_degraded",
        text,
        _base_report(done_seen=False, finalize_called=1, active_cleaned=True),
    )

    assert payload["final_status"] == "degraded"
    assert payload["failure_stage"] == "tool_dispatch"
    assert payload["unhandled_exception"] is False
    assert_failure_attribution_shape(payload)


def test_failure_attribution_failed_when_finalize_not_cleaned():
    """Unclean finalize should be classified as failed at `finalize`.

    Test path:
    1. Build a non-terminal stream with no `[DONE]`.
    2. Pair it with a report showing finalize was not called and active was not cleaned.
    3. The attribution helper should treat this as a hard failure.
    """
    text = 'data: {"type":"content","text":"stuck"}\n\n'
    payload = build_failure_attribution(
        "attr_failed_finalize",
        text,
        _base_report(done_seen=False, finalize_called=0, active_cleaned=False),
    )

    assert payload["final_status"] == "failed"
    assert payload["failure_stage"] == "finalize"
    assert payload["unhandled_exception"] is True


@pytest.mark.parametrize(
    "failure_stage",
    [
        "llm_output_parse",
        "tool_result_injection",
        "context_assembly",
        "summary_round",
    ],
)
def test_failure_attribution_accepts_explicit_stage_overrides(failure_stage: str):
    """Explicit stage override should win over default stage inference.

    Test path:
    1. Build one degraded-looking partial stream.
    2. Pass an explicit `failure_stage` override into the attribution helper.
    3. The helper should preserve that override while keeping schema validity.
    """
    text = 'data: {"type":"content","text":"partial"}\n\n'
    payload = build_failure_attribution(
        f"attr_{failure_stage}",
        text,
        _base_report(done_seen=False, finalize_called=1, active_cleaned=True),
        failure_stage=failure_stage,
    )

    assert payload["final_status"] == "degraded"
    assert payload["failure_stage"] == failure_stage
    assert_failure_attribution_shape(payload)
