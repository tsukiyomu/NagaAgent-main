from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.golden_cases import (
    assert_golden_case_report,
    load_golden_cases,
    run_stub_golden_case,
)


pytestmark = [pytest.mark.golden_case]


CASES_DIR = Path(__file__).with_name("cases")
GOLDEN_CASES = load_golden_cases(CASES_DIR)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda case: case.case_id)
async def test_agent_workflow_golden_case_stub_profile(case, monkeypatch):
    report = await run_stub_golden_case(case, monkeypatch)

    result = assert_golden_case_report(case, report)

    assert result.passed is True
