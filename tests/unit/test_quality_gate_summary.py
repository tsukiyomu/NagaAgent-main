from __future__ import annotations

"""Unit tests for quality-gate summary decisions.

These tests do not run real pytest sessions. They feed the summary builder with
small synthetic records so gate logic can be checked deterministically.
"""

import json
from pathlib import Path

import pytest

from tests.support.quality_gate import QualityGateConfig, generate_quality_gate_artifacts


pytestmark = [pytest.mark.unit]


def _record(
    *,
    nodeid: str,
    outcome: str,
    blocking: bool,
    final_status: str,
    failure_stage: str,
    ttfb_ms: int = 100,
    total_latency_ms: int = 1000,
    tool_rounds: int = 1,
    retry_count: int = 0,
    workflow_timeout_count: int = 0,
) -> dict:
    """Build the minimum record shape expected by `generate_quality_gate_artifacts`.

    The helper mirrors the subset of pytest report data that the quality-gate
    layer consumes, so these tests can stay focused on gate decisions instead of
    full pytest collection/execution.
    """

    return {
        "nodeid": nodeid,
        "when": "call",
        "outcome": outcome,
        "duration": 0.01,
        "marker_names": ["smoke", "blocking"] if blocking else ["integration"],
        "user_properties": [
            (
                "quality_gate_case",
                {
                    "case_id": nodeid,
                    "feature": "p2_api",
                    "story": "performance",
                    "blocking": blocking,
                    "final_status": final_status,
                    "failure_stage": failure_stage,
                    "metrics": {
                        "ttfb_ms": ttfb_ms,
                        "total_latency_ms": total_latency_ms,
                        "event_count": 3,
                        "tool_rounds": tool_rounds,
                        "tool_count": 1,
                        "retry_count": retry_count,
                        "workflow_timeout_count": workflow_timeout_count,
                    },
                },
            )
        ],
        "failure_reason": "",
    }


def _baseline_path(base_dir: Path, profile: str = "stub") -> Path:
    """Keep baseline file naming aligned with the production summary code."""

    return base_dir / f"{profile}_main.json"


def _write_baseline(path: Path, *, pass_rate: float, ttfb: float, latency: float, avg_rounds: float) -> None:
    """Write one compact baseline snapshot for regression comparisons.

    Tests only need the fields that influence pass/warn/fail transitions, so
    the payload stays intentionally smaller than a full real artifact.
    """

    payload = {
        "baseline_version": "2026-05-05",
        "run_id": "2026-05-05T00:00:00+00:00",
        "profile": "stub",
        "case_count": 1,
        "pass_rate": pass_rate,
        "tool_selection_acc": 1.0,
        "context_usage_acc": 1.0,
        "avg_rounds": avg_rounds,
        "ttfb_p95_ms": ttfb,
        "total_latency_p95_ms": latency,
        "retry_count": 0,
        "workflow_timeout_count": 0,
        "max_failure_rate": 1.0 - pass_rate,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_gate(tmp_path: Path, records: list[dict]) -> dict:
    """Run the summary builder against isolated temp artifacts and baselines."""

    config = QualityGateConfig(
        profile="stub",
        artifacts_dir=tmp_path / "artifacts",
        baseline_dir=tmp_path / "baseline",
    )
    artifacts = generate_quality_gate_artifacts(config=config, records=records)
    return artifacts.report_payload


def test_quality_gate_blocking_correctness_failure_is_fail(tmp_path: Path):
    """Any blocking correctness failure should fail the gate immediately."""

    report = _run_gate(
        tmp_path,
        [
            _record(
                nodeid="tests/smoke/test_p2_smoke.py::test_blocking_correctness",
                outcome="failed",
                blocking=True,
                final_status="failed",
                failure_stage="finalize",
            )
        ],
    )
    assert report["summary"]["gate_result"] == "fail"


def test_quality_gate_blocking_stability_failure_is_fail(tmp_path: Path):
    """Blocking stability regressions should fail even when the run degrades gracefully."""

    report = _run_gate(
        tmp_path,
        [
            _record(
                nodeid="tests/integration/p2_api/test_chat_stream_resilience.py::test_midstream",
                outcome="failed",
                blocking=True,
                final_status="degraded",
                failure_stage="tool_dispatch",
            )
        ],
    )
    assert report["summary"]["gate_result"] == "fail"


def test_quality_gate_performance_small_regression_is_warn(tmp_path: Path):
    """A mild performance regression should degrade to warn, not hard fail."""

    baseline_path = _baseline_path(tmp_path / "baseline")
    _write_baseline(
        baseline_path,
        pass_rate=1.0,
        ttfb=100.0,
        latency=1000.0,
        avg_rounds=1.0,
    )
    report = _run_gate(
        tmp_path,
        [
            _record(
                nodeid="tests/smoke/test_p2_smoke.py::test_perf_warn",
                outcome="passed",
                blocking=True,
                final_status="success",
                failure_stage="none",
                ttfb_ms=130,
                total_latency_ms=1300,
            )
        ],
    )
    assert report["summary"]["gate_result"] == "warn"


def test_quality_gate_no_regression_is_pass(tmp_path: Path):
    """Matching the baseline on key metrics should keep the gate green."""

    baseline_path = _baseline_path(tmp_path / "baseline")
    _write_baseline(
        baseline_path,
        pass_rate=1.0,
        ttfb=100.0,
        latency=1000.0,
        avg_rounds=1.0,
    )
    report = _run_gate(
        tmp_path,
        [
            _record(
                nodeid="tests/smoke/test_p2_smoke.py::test_perf_ok",
                outcome="passed",
                blocking=True,
                final_status="success",
                failure_stage="none",
                ttfb_ms=100,
                total_latency_ms=1000,
            )
        ],
    )
    assert report["summary"]["gate_result"] == "pass"


def test_quality_gate_bootstrap_writes_missing_baseline(tmp_path: Path):
    """First run without a baseline should bootstrap one instead of crashing.

    The exact gate result may still vary with policy, so the contract here is
    baseline creation plus a structurally valid summary outcome.
    """

    report = _run_gate(
        tmp_path,
        [
            _record(
                nodeid="tests/smoke/test_p2_smoke.py::test_bootstrap",
                outcome="passed",
                blocking=True,
                final_status="success",
                failure_stage="none",
            )
        ],
    )
    baseline_path = _baseline_path(tmp_path / "baseline")
    assert baseline_path.exists()
    assert report["regression"]["baseline_bootstrap"] is True
    assert report["summary"]["gate_result"] in {"pass", "warn", "fail"}
