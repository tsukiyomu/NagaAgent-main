from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.golden_cases import (
    GoldenCaseAssertionError,
    assert_golden_case_report,
    evaluate_golden_case_report,
    load_golden_cases,
    run_stub_golden_case,
)


pytestmark = [pytest.mark.unit]


def _case_by_id(case_id: str):
    cases = load_golden_cases(Path("tests/golden_cases/cases"))
    return next(case for case in cases if case.case_id == case_id)


@pytest.mark.asyncio
async def test_stub_runner_executes_no_tool_case(monkeypatch):
    case = _case_by_id("gc_no_tool_answer_001")

    report = await run_stub_golden_case(case, monkeypatch)

    assert report.case_id == "gc_no_tool_answer_001"
    assert report.final_status == "success"
    assert report.called_tools == ()
    assert report.tool_call_count == 0
    assert report.rounds == 1
    assert "smoke gate" in report.final_answer


@pytest.mark.asyncio
async def test_stub_runner_executes_multi_tool_case(monkeypatch):
    case = _case_by_id("gc_multi_tool_search_fetch_001")

    report = await run_stub_golden_case(case, monkeypatch)

    assert report.final_status == "success"
    assert report.called_tools == ("tool__web_search", "tool__web_fetch")
    assert report.tool_call_count == 2
    assert [result["status"] for result in report.tool_results] == ["success", "success"]
    assert "python main.py --headless" in report.final_answer


@pytest.mark.asyncio
async def test_stub_runner_maps_tool_timeout_to_degraded_report(monkeypatch):
    case = _case_by_id("gc_tool_timeout_fallback_001")

    report = await run_stub_golden_case(case, monkeypatch)

    assert report.final_status == "degraded"
    assert report.failure_stage == "tool_dispatch"
    assert report.called_tools == ("tool__web_search",)
    assert report.tool_results[0]["status"] == "error"
    assert "timed out" in report.final_answer


@pytest.mark.asyncio
async def test_assertion_checker_accepts_repository_stub_cases(monkeypatch):
    cases = load_golden_cases(Path("tests/golden_cases/cases"))

    reports = [await run_stub_golden_case(case, monkeypatch) for case in cases]
    results = [
        assert_golden_case_report(case, report)
        for case, report in zip(cases, reports)
    ]

    assert [result.case_id for result in results] == [case.case_id for case in cases]
    assert all(result.passed for result in results)


@pytest.mark.asyncio
async def test_assertion_checker_reports_multiple_contract_failures(monkeypatch):
    case = _case_by_id("gc_tool_web_search_001")
    report = await run_stub_golden_case(case, monkeypatch)
    broken_report = type(report)(
        **{
            **report.__dict__,
            "called_tools": ("tool__web_fetch",),
            "final_answer": "This answer invents an unverified release date.",
            "rounds": case.expected.max_rounds + 1,
        }
    )

    result = evaluate_golden_case_report(case, broken_report)

    assert result.passed is False
    assert "required tool not called: tool__web_search" in result.failures
    assert "forbidden tool called: tool__web_fetch" in result.failures
    assert any(failure.startswith("rounds exceeded") for failure in result.failures)
    assert "forbidden answer point present: unverified release date" in result.failures
    with pytest.raises(GoldenCaseAssertionError):
        assert_golden_case_report(case, broken_report)
