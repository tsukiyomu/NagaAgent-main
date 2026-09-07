from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.golden_cases import (
    GoldenCase,
    GoldenCaseDuplicateIdError,
    GoldenCaseExpected,
    GoldenCaseFixtures,
    GoldenCaseGate,
    GoldenCaseInput,
    GoldenCaseInvalidFieldError,
    GoldenCaseMissingFieldError,
    discover_golden_case_files,
    load_golden_cases,
)

pytestmark = [pytest.mark.unit]


def _minimal_case(**overrides) -> GoldenCase:
    data = {
        "case_id": "gc_no_tool_answer_001",
        "business_flow": "BF-01",
        "group": "no_tool",
        "profile": "stub",
        "title": "No-tool direct answer",
        "input": GoldenCaseInput(user_input="Summarize this fixed input."),
        "fixtures": GoldenCaseFixtures(),
        "expected": GoldenCaseExpected(final_status="success", max_rounds=1),
        "gate": GoldenCaseGate(blocking=True),
    }
    data.update(overrides)
    return GoldenCase(**data)


def test_golden_case_schema_accepts_minimal_stub_case():
    case = _minimal_case()

    assert case.validate_schema() is case


def test_golden_case_schema_rejects_missing_required_text():
    case = _minimal_case(case_id="")

    with pytest.raises(GoldenCaseMissingFieldError) as excinfo:
        case.validate_schema()

    assert excinfo.value.field == "case_id"


def test_golden_case_schema_rejects_unknown_profile():
    case = _minimal_case(profile="production")

    with pytest.raises(GoldenCaseInvalidFieldError) as excinfo:
        case.validate_schema()

    assert excinfo.value.case_id == "gc_no_tool_answer_001"
    assert excinfo.value.field == "profile"


def test_golden_case_schema_rejects_invalid_expected_contract():
    case = _minimal_case(expected=GoldenCaseExpected(final_status="success", max_rounds=0))

    with pytest.raises(GoldenCaseInvalidFieldError) as excinfo:
        case.validate_schema()

    assert excinfo.value.field == "expected.max_rounds"


def test_discover_golden_case_files_returns_stable_supported_files(tmp_path):
    (tmp_path / "nested").mkdir()
    first = tmp_path / "b.yaml"
    second = tmp_path / "nested" / "a.json"
    ignored = tmp_path / "notes.txt"
    first.write_text("case_id: gc_b\n", encoding="utf-8")
    second.write_text('{"case_id": "gc_a"}', encoding="utf-8")
    ignored.write_text("ignored", encoding="utf-8")

    assert discover_golden_case_files(tmp_path) == (first, second)


def test_load_golden_cases_reads_json_case(tmp_path):
    case_file = tmp_path / "gc_no_tool_answer_001.json"
    case_file.write_text(
        """
{
  "case_id": "gc_no_tool_answer_001",
  "business_flow": "BF-01",
  "group": "no_tool",
  "profile": "stub",
  "title": "No-tool direct answer",
  "input": {
    "user_input": "Summarize this fixed input.",
    "history": [{"role": "user", "content": "Use concise wording."}],
    "session": {"temporary": true}
  },
  "fixtures": {
    "llm_script": [{"final_answer": "Short answer."}],
    "tool_results": {}
  },
  "expected": {
    "final_status": "success",
    "required_tools": [],
    "forbidden_tools": ["tool__web_search"],
    "max_rounds": 1,
    "required_answer_points": ["Short answer"],
    "forbidden_answer_points": ["source:"],
    "summary_triggered": false,
    "unhandled_exception": false
  },
  "gate": {
    "blocking": true,
    "baseline_compare": false
  }
}
""".strip(),
        encoding="utf-8",
    )

    cases = load_golden_cases(tmp_path)

    assert len(cases) == 1
    assert cases[0].case_id == "gc_no_tool_answer_001"
    assert cases[0].input.history == ({"role": "user", "content": "Use concise wording."},)
    assert cases[0].expected.forbidden_tools == ("tool__web_search",)


def test_load_golden_cases_rejects_duplicate_case_ids(tmp_path):
    payload = """
case_id: gc_no_tool_answer_001
business_flow: BF-01
group: no_tool
profile: stub
title: No-tool direct answer
input:
  user_input: Summarize this fixed input.
fixtures: {}
expected:
  final_status: success
gate: {}
""".strip()
    (tmp_path / "a.yaml").write_text(payload, encoding="utf-8")
    (tmp_path / "b.yaml").write_text(payload, encoding="utf-8")

    with pytest.raises(GoldenCaseDuplicateIdError) as excinfo:
        load_golden_cases(tmp_path)

    assert excinfo.value.case_id == "gc_no_tool_answer_001"


def test_load_golden_cases_reports_missing_required_field(tmp_path):
    case_file = tmp_path / "missing_expected.json"
    case_file.write_text(
        """
{
  "case_id": "gc_no_tool_answer_001",
  "business_flow": "BF-01",
  "group": "no_tool",
  "profile": "stub",
  "title": "No-tool direct answer",
  "input": {"user_input": "Summarize this fixed input."},
  "fixtures": {},
  "gate": {}
}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(GoldenCaseMissingFieldError) as excinfo:
        load_golden_cases(case_file)

    assert excinfo.value.case_id == "gc_no_tool_answer_001"
    assert excinfo.value.field == "expected"


def test_load_repository_minimal_golden_case_files():
    cases_dir = Path("tests/golden_cases/cases")

    cases = load_golden_cases(cases_dir)

    assert [case.case_id for case in cases] == [
        "gc_history_continue_001",
        "gc_multi_tool_search_fetch_001",
        "gc_no_tool_answer_001",
        "gc_tool_timeout_fallback_001",
        "gc_tool_web_search_001",
    ]
    assert {case.profile for case in cases} == {"stub"}
    assert {case.business_flow for case in cases} == {"BF-01", "BF-02", "BF-05", "BF-06", "BF-07"}
