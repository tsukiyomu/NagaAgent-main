"""Quality gate aggregation helpers for pytest-level workflow reporting.

This module is intentionally test-harness scoped:
- consumes pytest reports + optional test-emitted case properties
- computes pass/warn/fail gate result with baseline comparison
- emits stable JSON + Markdown artifacts for local/CI consumption
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any


ALLOWED_GATE_RESULTS = {"pass", "warn", "fail"}
ALLOWED_FINAL_STATUS = {"success", "degraded", "failed"}
ALLOWED_FAILURE_STAGE = {
    "none",
    "llm_output_parse",
    "tool_call_normalize",
    "tool_dispatch",
    "tool_result_injection",
    "context_assembly",
    "summary_round",
    "finalize",
}
ALLURE_STORIES = ("correctness", "stability", "performance")


@dataclass
class QualityGateConfig:
    profile: str
    artifacts_dir: Path
    baseline_dir: Path
    suite_name: str = "agent_workflow_regression"


@dataclass
class QualityGateArtifacts:
    report_path: Path
    summary_path: Path
    baseline_path: Path
    report_payload: dict[str, Any]
    summary_markdown: str
    allure_attached: bool


def infer_feature(nodeid: str, marker_names: set[str]) -> str | None:
    """Map test node into the quality-gate scope feature buckets."""
    normalized = nodeid.replace("\\", "/")
    if "real_llm" in marker_names or "test_chat_stream_real_llm_smoke.py" in normalized:
        return "real_llm"
    if normalized.startswith("tests/smoke/"):
        return "p2_api"
    if normalized.startswith("tests/integration/p2_api/"):
        return "p2_api"
    if normalized.startswith("tests/unit/agentic_tool_loop/"):
        return "agentic_tool_loop"
    return None


def should_include_for_gate(nodeid: str, marker_names: set[str]) -> bool:
    return infer_feature(nodeid, marker_names) is not None


def _extract_quality_case_payload(user_properties: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in user_properties:
        if key == "quality_gate_case" and isinstance(value, dict):
            payload = value
    return payload


def apply_allure_case_labels(*, feature: str, story: str) -> bool:
    """Best-effort Allure hierarchy mapping for case-level visibility."""
    try:
        import allure  # type: ignore
    except Exception:
        return False
    try:
        allure.dynamic.epic("Agent Workflow Quality Gate")
        allure.dynamic.feature(feature)
        allure.dynamic.story(story)
        return True
    except Exception:
        return False


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return int(value)
    return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return float(value)
    return None


def _map_outcome_to_final_status(outcome: str) -> str:
    if outcome == "passed":
        return "success"
    if outcome == "failed":
        return "failed"
    return "degraded"


def _default_failure_stage(outcome: str) -> str:
    if outcome == "failed":
        return "finalize"
    return "none"


def _normalize_failure_stage(stage: str | None, outcome: str) -> str:
    if isinstance(stage, str) and stage in ALLOWED_FAILURE_STAGE:
        return stage
    return _default_failure_stage(outcome)


def _normalize_final_status(final_status: str | None, outcome: str) -> str:
    if isinstance(final_status, str) and final_status in ALLOWED_FINAL_STATUS:
        return final_status
    return _map_outcome_to_final_status(outcome)


def _parse_case_story(payload: dict[str, Any]) -> str:
    story = payload.get("story")
    if isinstance(story, str) and story in ALLURE_STORIES:
        return story
    return "correctness"


def _round_value(value: float | None, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _safe_delta(current: float | int | None, baseline: float | int | None) -> float | None:
    if current is None or baseline is None:
        return None
    return float(current) - float(baseline)


def _ratio_delta(current: float | int | None, baseline: float | int | None) -> float | None:
    if current is None or baseline in (None, 0):
        return None
    return (float(current) - float(baseline)) / float(baseline)


def _percentile(values: list[int | float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _bool_count(values: list[Any]) -> int:
    return sum(1 for v in values if bool(v))


def _collect_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    ttfb_values = [
        metric
        for metric in (_coerce_float(c["metrics"].get("ttfb_ms")) for c in cases)
        if metric is not None
    ]
    latency_values = [
        metric
        for metric in (_coerce_float(c["metrics"].get("total_latency_ms")) for c in cases)
        if metric is not None
    ]
    rounds_values = [
        metric
        for metric in (_coerce_float(c["metrics"].get("tool_rounds")) for c in cases)
        if metric is not None
    ]
    max_round_values = [
        metric
        for metric in (_coerce_float(c["metrics"].get("max_tool_rounds")) for c in cases)
        if metric is not None
    ]
    retry_values = [
        metric
        for metric in (_coerce_int(c["metrics"].get("retry_count")) for c in cases)
        if metric is not None
    ]
    timeout_values = [
        metric
        for metric in (_coerce_int(c["metrics"].get("workflow_timeout_count")) for c in cases)
        if metric is not None
    ]
    tool_count_values = [
        metric
        for metric in (_coerce_float(c["metrics"].get("tool_count")) for c in cases)
        if metric is not None
    ]

    metrics = {
        "ttfb_p95_ms": _round_value(_percentile(ttfb_values, 0.95), digits=2),
        "total_latency_p95_ms": _round_value(_percentile(latency_values, 0.95), digits=2),
        "avg_tool_rounds": _round_value(sum(rounds_values) / len(rounds_values), digits=3)
        if rounds_values
        else None,
        "max_tool_rounds": _round_value(max(max_round_values), digits=3)
        if max_round_values
        else (_round_value(max(rounds_values), digits=3) if rounds_values else None),
        "avg_tool_count": _round_value(sum(tool_count_values) / len(tool_count_values), digits=3)
        if tool_count_values
        else None,
        "retry_count": int(sum(retry_values)) if retry_values else 0,
        "workflow_timeout_count": int(sum(timeout_values)) if timeout_values else 0,
    }
    return metrics


def _build_case_record(record: dict[str, Any]) -> dict[str, Any]:
    nodeid = record["nodeid"]
    marker_names = set(record.get("marker_names", []))
    feature = infer_feature(nodeid, marker_names)
    assert feature is not None  # guarded by caller

    payload = _extract_quality_case_payload(record.get("user_properties", []))
    outcome = record["outcome"]

    raw_metrics = payload.get("metrics")
    metrics: dict[str, Any] = raw_metrics.copy() if isinstance(raw_metrics, dict) else {}
    if "tool_rounds" not in metrics and payload.get("rounds") is not None:
        metrics["tool_rounds"] = payload.get("rounds")
    if "tool_count" not in metrics and payload.get("tool_call_count") is not None:
        metrics["tool_count"] = payload.get("tool_call_count")

    case = {
        "nodeid": nodeid,
        "case_id": str(payload.get("case_id") or nodeid),
        "feature": str(payload.get("feature") or feature),
        "story": _parse_case_story(payload),
        "blocking": bool(payload.get("blocking", ("blocking" in marker_names and feature != "real_llm"))),
        "non_blocking": bool(payload.get("non_blocking", feature == "real_llm")),
        "outcome": outcome,
        "duration_s": _coerce_float(record.get("duration")),
        "final_status": _normalize_final_status(payload.get("final_status"), outcome),
        "failure_stage": _normalize_failure_stage(payload.get("failure_stage"), outcome),
        "reason": str(payload.get("reason") or ""),
        "metrics": metrics,
    }
    return case


def _build_summary(cases: list[dict[str, Any]], gate_result: str, warned: int) -> dict[str, Any]:
    passed = sum(1 for c in cases if c["outcome"] == "passed")
    failed = sum(1 for c in cases if c["outcome"] == "failed")
    total = len(cases)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "warned": warned,
        "gate_result": gate_result,
    }


def _build_failures(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for case in cases:
        if case["outcome"] != "failed":
            continue
        reason = case["reason"] or f"{case['nodeid']} failed"
        failures.append(
            {
                "case_id": case["case_id"],
                "feature": case["feature"],
                "failure_stage": case["failure_stage"],
                "reason": reason,
            }
        )
    return failures


def _base_scorecard(cases: list[dict[str, Any]]) -> dict[str, float]:
    considered = [c for c in cases if c["outcome"] in {"passed", "failed"}]
    if not considered:
        pass_rate = 1.0
    else:
        pass_rate = sum(1 for c in considered if c["outcome"] == "passed") / len(considered)

    tool_dispatch_cases = [c for c in cases if c.get("metrics", {}).get("tool_count") is not None]
    if not tool_dispatch_cases:
        tool_selection_acc = 1.0
    else:
        tool_selection_acc = (
            sum(1 for c in tool_dispatch_cases if c["final_status"] == "success") / len(tool_dispatch_cases)
        )

    context_cases = [c for c in cases if c.get("failure_stage") == "context_assembly" or c["feature"] == "agentic_tool_loop"]
    if not context_cases:
        context_usage_acc = 1.0
    else:
        context_usage_acc = (
            sum(1 for c in context_cases if c["final_status"] == "success") / len(context_cases)
        )

    return {
        "pass_rate": round(pass_rate, 4),
        "tool_selection_acc": round(tool_selection_acc, 4),
        "context_usage_acc": round(context_usage_acc, 4),
    }


def _baseline_file_name(profile: str) -> str:
    safe = profile.replace("/", "_").replace("\\", "_")
    return f"{safe}_main.json"


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_baseline_payload(
    run_id: str,
    profile: str,
    cases: list[dict[str, Any]],
    metrics: dict[str, Any],
    scorecard: dict[str, float],
) -> dict[str, Any]:
    return {
        "baseline_version": run_id[:10],
        "run_id": run_id,
        "profile": profile,
        "case_count": len(cases),
        "pass_rate": scorecard["pass_rate"],
        "tool_selection_acc": scorecard["tool_selection_acc"],
        "context_usage_acc": scorecard["context_usage_acc"],
        "avg_rounds": metrics.get("avg_tool_rounds"),
        "ttfb_p95_ms": metrics.get("ttfb_p95_ms"),
        "total_latency_p95_ms": metrics.get("total_latency_p95_ms"),
        "retry_count": metrics.get("retry_count", 0),
        "workflow_timeout_count": metrics.get("workflow_timeout_count", 0),
        "max_failure_rate": round(1.0 - scorecard["pass_rate"], 4),
    }


def _evaluate_gate(
    cases: list[dict[str, Any]],
    metrics: dict[str, Any],
    scorecard: dict[str, float],
    baseline: dict[str, Any] | None,
) -> tuple[str, list[str], dict[str, Any]]:
    reasons: list[str] = []
    warn_reasons: list[str] = []

    blocking_cases = [c for c in cases if c["blocking"] and not c["non_blocking"]]
    blocking_failures = [c for c in blocking_cases if c["outcome"] != "passed"]
    if blocking_failures:
        reasons.append(f"blocking cases failed: {len(blocking_failures)}")

    blocking_stability_failures = [
        c
        for c in blocking_cases
        if c["outcome"] != "passed"
        and (c["final_status"] == "failed" or c["failure_stage"] == "finalize" or c["failure_stage"] == "tool_dispatch")
    ]
    if blocking_stability_failures:
        reasons.append(f"blocking stability cases failed: {len(blocking_stability_failures)}")

    baseline_compare = {
        "baseline": None,
        "pass_rate_delta": None,
        "latency_delta": None,
        "rounds_delta": None,
        "bootstrap": False,
    }
    if baseline is not None:
        baseline_compare["baseline"] = baseline.get("baseline_version")
        baseline_compare["pass_rate_delta"] = _round_value(
            _safe_delta(scorecard["pass_rate"], _coerce_float(baseline.get("pass_rate"))),
            digits=4,
        )
        baseline_compare["latency_delta"] = _round_value(
            _ratio_delta(metrics.get("total_latency_p95_ms"), _coerce_float(baseline.get("total_latency_p95_ms"))),
            digits=4,
        )
        baseline_compare["rounds_delta"] = _round_value(
            _safe_delta(metrics.get("avg_tool_rounds"), _coerce_float(baseline.get("avg_rounds"))),
            digits=4,
        )

        baseline_pass_rate = _coerce_float(baseline.get("pass_rate"))
        if baseline_pass_rate is not None and scorecard["pass_rate"] < baseline_pass_rate - 0.05:
            reasons.append(
                f"pass_rate dropped below baseline tolerance ({scorecard['pass_rate']:.3f} < {baseline_pass_rate - 0.05:.3f})"
            )

        baseline_ttfb = _coerce_float(baseline.get("ttfb_p95_ms"))
        if baseline_ttfb and metrics.get("ttfb_p95_ms") is not None:
            if metrics["ttfb_p95_ms"] > baseline_ttfb * 1.5:
                reasons.append("ttfb_p95_ms severe regression (> baseline +50%)")
            elif metrics["ttfb_p95_ms"] > baseline_ttfb * 1.25:
                warn_reasons.append("ttfb_p95_ms regression (> baseline +25%)")

        baseline_latency = _coerce_float(baseline.get("total_latency_p95_ms"))
        if baseline_latency and metrics.get("total_latency_p95_ms") is not None:
            if metrics["total_latency_p95_ms"] > baseline_latency * 1.5:
                reasons.append("total_latency_p95_ms severe regression (> baseline +50%)")
            elif metrics["total_latency_p95_ms"] > baseline_latency * 1.25:
                warn_reasons.append("total_latency_p95_ms regression (> baseline +25%)")

        baseline_rounds = _coerce_float(baseline.get("avg_rounds"))
        if baseline_rounds is not None and metrics.get("avg_tool_rounds") is not None:
            if metrics["avg_tool_rounds"] > baseline_rounds + 2:
                reasons.append("avg_tool_rounds severe regression (> baseline +2)")
            elif metrics["avg_tool_rounds"] > baseline_rounds + 1:
                warn_reasons.append("avg_tool_rounds regression (> baseline +1)")

        baseline_retry = _coerce_int(baseline.get("retry_count"))
        if baseline_retry is not None and metrics.get("retry_count", 0) > baseline_retry + 1:
            warn_reasons.append("retry_count regression (> baseline +1)")

    if metrics.get("workflow_timeout_count", 0) > 0:
        warn_reasons.append("workflow_timeout_count > 0")

    if reasons:
        gate_result = "fail"
    elif warn_reasons:
        gate_result = "warn"
    else:
        gate_result = "pass"

    gate_meta = {
        "hard_fail_reasons": reasons,
        "warn_reasons": warn_reasons,
        "baseline_compare": baseline_compare,
        "warned": max(0, len(warn_reasons)),
    }
    return gate_result, reasons + warn_reasons, gate_meta


def _build_summary_markdown(payload: dict[str, Any], gate_notes: list[str]) -> str:
    summary = payload["summary"]
    metrics = payload["metrics"]
    regression = payload["regression"]
    failures = payload["failures"]
    lines = [
        "# Agent Quality Gate Summary",
        "",
        f"- run_id: `{payload['run_id']}`",
        f"- profile: `{payload['profile']}`",
        f"- suite: `{payload['suite']}`",
        f"- gate_result: `{summary['gate_result']}`",
        f"- total/passed/failed/warned: `{summary['total']}/{summary['passed']}/{summary['failed']}/{summary['warned']}`",
        "",
        "## Metrics",
        f"- ttfb_p95_ms: `{metrics.get('ttfb_p95_ms')}`",
        f"- total_latency_p95_ms: `{metrics.get('total_latency_p95_ms')}`",
        f"- avg_tool_rounds: `{metrics.get('avg_tool_rounds')}`",
        f"- max_tool_rounds: `{metrics.get('max_tool_rounds')}`",
        f"- retry_count: `{metrics.get('retry_count')}`",
        f"- workflow_timeout_count: `{metrics.get('workflow_timeout_count')}`",
        "",
        "## Regression",
        f"- baseline: `{regression.get('baseline')}`",
        f"- pass_rate_delta: `{regression.get('pass_rate_delta')}`",
        f"- latency_delta: `{regression.get('latency_delta')}`",
        f"- rounds_delta: `{regression.get('rounds_delta')}`",
    ]
    if gate_notes:
        lines.extend(["", "## Gate Notes"])
        for note in gate_notes:
            lines.append(f"- {note}")
    if failures:
        lines.extend(["", "## Failures"])
        for failure in failures[:10]:
            lines.append(
                f"- `{failure['case_id']}` @ `{failure['failure_stage']}`: {failure['reason']}"
            )
    return "\n".join(lines).rstrip() + "\n"


def _maybe_attach_allure_files(report_path: Path, summary_path: Path) -> bool:
    try:
        import allure  # type: ignore
    except Exception:
        return False
    try:
        allure.attach.file(
            str(report_path),
            name="agent_quality_report.json",
            attachment_type=allure.attachment_type.JSON,
        )
        allure.attach.file(
            str(summary_path),
            name="agent_quality_summary.md",
            attachment_type=allure.attachment_type.TEXT,
        )
        return True
    except Exception:
        return False


def generate_quality_gate_artifacts(
    *,
    config: QualityGateConfig,
    records: list[dict[str, Any]],
    allow_baseline_bootstrap: bool = True,
) -> QualityGateArtifacts:
    run_id = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cases = [_build_case_record(r) for r in records if should_include_for_gate(r["nodeid"], set(r.get("marker_names", [])))]

    metrics = _collect_metrics(cases)
    scorecard = _base_scorecard(cases)
    failures = _build_failures(cases)

    baseline_path = config.baseline_dir / _baseline_file_name(config.profile)
    baseline = _load_json_if_exists(baseline_path)
    gate_result, gate_notes, gate_meta = _evaluate_gate(cases, metrics, scorecard, baseline)

    if baseline is None and allow_baseline_bootstrap:
        baseline = _build_baseline_payload(run_id, config.profile, cases, metrics, scorecard)
        _write_json(baseline_path, baseline)
        gate_meta["baseline_compare"]["baseline"] = baseline.get("baseline_version")
        gate_meta["baseline_compare"]["bootstrap"] = True
    elif baseline is None:
        gate_meta["baseline_compare"]["baseline"] = None
        gate_meta["baseline_compare"]["bootstrap"] = False

    regression = {
        "baseline": str(baseline_path),
        "pass_rate_delta": gate_meta["baseline_compare"]["pass_rate_delta"],
        "latency_delta": gate_meta["baseline_compare"]["latency_delta"],
        "rounds_delta": gate_meta["baseline_compare"]["rounds_delta"],
        "baseline_bootstrap": bool(gate_meta["baseline_compare"]["bootstrap"]),
    }

    summary = _build_summary(cases, gate_result, warned=gate_meta["warned"])
    report_payload = {
        "run_id": run_id,
        "profile": config.profile,
        "suite": config.suite_name,
        "summary": summary,
        "metrics": metrics,
        "regression": regression,
        "failures": failures,
    }

    report_path = config.artifacts_dir / "agent_quality_report.json"
    summary_path = config.artifacts_dir / "agent_quality_summary.md"
    summary_markdown = _build_summary_markdown(report_payload, gate_notes)

    _write_json(report_path, report_payload)
    _write_text(summary_path, summary_markdown)

    allure_attached = _maybe_attach_allure_files(report_path, summary_path)

    return QualityGateArtifacts(
        report_path=report_path,
        summary_path=summary_path,
        baseline_path=baseline_path,
        report_payload=report_payload,
        summary_markdown=summary_markdown,
        allure_attached=allure_attached,
    )
