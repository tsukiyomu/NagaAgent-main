# Codex Task: Implement Agent Workflow Golden Cases v1

## 1. Goal

Implement the minimal executable **Agent Workflow Golden Cases v1**.

This task should add a local, deterministic, pytest-based golden case runner for Agent Workflow regression.

The goal is **not** to build a generic evaluation platform. The goal is to add a small but complete regression loop:

```text
case files
  -> loader
  -> runner
  -> fixtures
  -> assertion checker
  -> pytest entry
```

Golden Cases v1 should verify task-level workflow behavior for a tool-using agent under a deterministic `stub` profile.

## 2. Current Positioning

Golden Cases is a suite-level concept, not a name for every individual test file.

Use this naming rule:

```text
tests/golden_cases/
  cases/
    gc_no_tool_answer_001.yaml
    gc_tool_web_search_001.yaml
    gc_tool_timeout_fallback_001.yaml
    gc_multi_tool_search_fetch_001.yaml

  test_agent_workflow_golden_cases.py

tests/support/
  golden_cases.py
```

Meaning:

```text
tests/golden_cases/cases/
  Stores case data.

test_agent_workflow_golden_cases.py
  Pytest entry / runner test file.
  It loads golden case data and runs the shared runner.

tests/support/golden_cases.py
  Shared helper module.
  It contains schema loading, validation, runner, fixtures, assertion checker, and report building.
```

Do not create one test file per golden case.

Do not rename normal unit or integration test files to golden case files.

## 3. Must Reuse Existing Test Infrastructure

Before implementing new helpers, inspect and reuse existing project helpers if available:

```text
tests/support/agentic_tool_loop_helpers.py
tests/support/failure_attribution.py
tests/unit/agentic_tool_loop/
tests/integration/chat_stream/
```

Prefer reuse over rewriting.

Expected reusable capabilities may include:

```text
scripted LLM
fake queue
SSE helper
failure attribution fields
final_status
failure_stage
rounds
tool_call_count
summary_triggered
unhandled_exception
```

## 4. Must Keep Real vs Stub Boundary

Golden Cases v1 should keep the real workflow orchestration in the middle, but stub external dependencies.

### Real

Use the real workflow orchestration path:

```text
run_agentic_loop(...)
```

The runner should let the real loop decide:

```text
round progression
tool call parsing
tool dispatch decision
tool result injection
summary round
stop condition
SSE event order
final status
```

### Stub / Fake

Golden Cases v1 must stub or fake:

```text
LLM service
tool execution results
tool timeout/error
external network
real MCP
real OpenClaw
real LLM
real staging services
```

The `stub` profile must be offline, deterministic, and repeatable.

## 5. Must Not Do

Do not implement these in v1:

```text
real LLM profile
staging profile
real MCP / OpenClaw integration
Langfuse integration
LangSmith integration
LLM-as-a-Judge
semantic scoring platform
dashboard UI
memory governance
context compression evaluation
full Quality Gate rewrite
large golden case dataset
```

Golden Cases v1 should only implement the executable minimum.

## 6. Files to Create

Create these files:

```text
tests/
  golden_cases/
    cases/
      gc_no_tool_answer_001.yaml
      gc_tool_web_search_001.yaml
      gc_tool_timeout_fallback_001.yaml
      gc_multi_tool_search_fetch_001.yaml
    test_agent_workflow_golden_cases.py

  support/
    golden_cases.py
```

If the project already has a better local convention for support helpers, follow the existing convention, but keep these three roles separated:

```text
case data
pytest entry
support/helper logic
```

## 7. Required Case Schema

Each case file must include at least:

```yaml
case_id: string
business_flow: string
group: string
profile: string

input:
  messages: list
  tools: list

fixtures:
  llm_rounds: list
  tool_results: list

expected:
  final_status: string
  required_tools: list
  forbidden_tools: list
  max_rounds: int
  required_answer_points: list
  forbidden_answer_points: list
  summary_triggered: bool
  unhandled_exception: bool

gate:
  blocking: bool
```

Optional fields may be supported if easy:

```yaml
tags: list
oracle_type: deterministic
description: string
```

Use `deterministic` as the only supported `oracle_type` in v1.

## 8. Supported Values

### profile

v1 only needs to support:

```text
stub
```

If a case uses any other profile, the loader should fail with a clear schema error.

### business_flow

v1 should support at least these values:

```text
BF_NO_TOOL
BF_SINGLE_TOOL
BF_TOOL_FAILURE
BF_MULTI_TOOL
```

If the project already has official business flow IDs, reuse them.

### group

v1 should support at least:

```text
no_tool
single_tool
tool_failure
multi_tool
```

## 9. Implement `tests/support/golden_cases.py`

Implement the following structures and functions.

### 9.1 Data Structures

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GoldenCase:
    case_id: str
    business_flow: str
    group: str
    profile: str
    input: dict[str, Any]
    fixtures: dict[str, Any]
    expected: dict[str, Any]
    gate: dict[str, Any]
    source: Path | None = None


class GoldenCaseSchemaError(Exception):
    pass


class GoldenCaseAssertionError(AssertionError):
    pass
```

If the project already uses Pydantic or TypedDict for test schemas, it is acceptable to use that instead, but keep validation simple and readable.

### 9.2 Loader Functions

Implement:

```python
def discover_case_files(case_dir: Path) -> list[Path]:
    """Return all .yaml, .yml, and .json case files under case_dir."""
def load_golden_cases(case_dir: Path) -> list[GoldenCase]:
    """Load, validate, and return all golden cases from case_dir."""
def validate_case(raw: dict[str, Any], source: Path) -> GoldenCase:
    """Validate one raw case dict and convert it to GoldenCase."""
```

Required loader behavior:

```text
1. Read YAML or JSON.
2. Validate required top-level fields.
3. Validate required expected fields.
4. Validate profile is supported.
5. Validate business_flow is supported.
6. Validate case_id is unique across loaded cases.
7. Return helpful errors with case file path and missing/invalid field name.
```

If YAML support is not currently available in the project, either:

```text
1. Use existing YAML dependency if already installed.
2. Otherwise support JSON first and leave a clear TODO for YAML.
```

Do not add heavy new dependencies unless necessary.

### 9.3 Runner Function

Implement:

```python
async def run_golden_case(case: GoldenCase) -> dict[str, Any]:
    """Run one golden case through the real agent workflow with stubbed dependencies."""
```

The runner must:

```text
1. Build initial messages from case.input.messages.
2. Build tools from case.input.tools.
3. Inject scripted LLM rounds from case.fixtures.llm_rounds.
4. Inject fixed tool results or tool failures from case.fixtures.tool_results.
5. Call the real run_agentic_loop(...).
6. Collect all yielded SSE chunks.
7. Extract final answer text.
8. Extract called tools.
9. Extract rounds.
10. Extract summary_triggered.
11. Extract final_status.
12. Extract failure_stage.
13. Extract unhandled_exception.
14. Return a normalized workflow report.
```

Expected report shape:

```python
{
    "case_id": "...",
    "profile": "stub",
    "business_flow": "...",
    "group": "...",

    "final_status": "success",
    "failure_stage": None,
    "rounds": 1,
    "tool_call_count": 0,
    "called_tools": [],
    "summary_triggered": False,
    "unhandled_exception": False,

    "final_answer": "...",
    "events": [...],
    "chunks": [...],
}
```

The exact internal event format can follow existing helpers, but the report must provide stable keys used by the assertion checker.

### 9.4 Assertion Checker Function

Implement:

```python
def assert_golden_case_result(case: GoldenCase, report: dict[str, Any]) -> None:
    """Assert one workflow report against the expected fields in the case."""
```

The assertion checker must verify:

```text
1. report.final_status == expected.final_status
2. all expected.required_tools are in report.called_tools
3. no expected.forbidden_tools are in report.called_tools
4. report.rounds <= expected.max_rounds
5. all expected.required_answer_points appear in report.final_answer
6. no expected.forbidden_answer_points appear in report.final_answer
7. report.summary_triggered == expected.summary_triggered
8. report.unhandled_exception == expected.unhandled_exception
```

Failure messages must include:

```text
case_id
failed field
expected value
actual value
failure_stage if available
```

Example failure message:

```text
[gc_tool_web_search_001] required_tools failed:
expected tool 'tool__web_search' to be called.
actual called_tools=[]
failure_stage=tool_dispatch
```

### 9.5 Helper Functions

Implement small helpers if needed:

```python
def extract_sse_json_events(chunks: list[str]) -> list[dict[str, Any]]:
    ...
def extract_final_answer(events: list[dict[str, Any]]) -> str:
    ...
def extract_called_tools(events: list[dict[str, Any]]) -> list[str]:
    ...
def build_workflow_report(case: GoldenCase, chunks: list[str]) -> dict[str, Any]:
    ...
```

Reuse existing SSE helpers if available.

## 10. Implement Pytest Entry

Create:

```text
tests/golden_cases/test_agent_workflow_golden_cases.py
```

This file should:

```text
1. Load all cases from tests/golden_cases/cases.
2. Parametrize a single async pytest test over all loaded cases.
3. Mark the test with @pytest.mark.golden_case.
4. Run each case through run_golden_case(case).
5. Assert each report through assert_golden_case_result(case, report).
```

Example structure:

```python
from pathlib import Path

import pytest

from tests.support.golden_cases import (
    assert_golden_case_result,
    load_golden_cases,
    run_golden_case,
)


CASE_DIR = Path(__file__).parent / "cases"
CASES = load_golden_cases(CASE_DIR)


def _case_id(case):
    return case.case_id


@pytest.mark.golden_case
@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=_case_id)
async def test_agent_workflow_golden_case(case):
    report = await run_golden_case(case)
    assert_golden_case_result(case, report)
```

If the project uses a different async test plugin or any existing async pattern, follow the project convention.

## 11. Four Required Stub Cases

Create four case files.

### 11.1 `gc_no_tool_answer_001.yaml`

Purpose:

```text
No tool should be called when the task can be answered directly.
```

Expected behavior:

```text
final_status: success
required_tools: []
forbidden_tools: ["tool__web_search", "tool__fetch_page"]
max_rounds: 1
summary_triggered: false
unhandled_exception: false
required_answer_points:
  - "direct-answer-ok"
```

### 11.2 `gc_tool_web_search_001.yaml`

Purpose:

```text
A single web search tool should be called, and the final answer should consume the tool result.
```

Expected behavior:

```text
final_status: success
required_tools: ["tool__web_search"]
forbidden_tools: []
max_rounds: 3
summary_triggered: false
unhandled_exception: false
required_answer_points:
  - "search-result-used"
```

### 11.3 `gc_tool_timeout_fallback_001.yaml`

Purpose:

```text
When the tool times out or errors, the agent should not hallucinate tool results and should converge to a controlled degraded or summary status.
```

Expected behavior:

```text
final_status: degraded
required_tools: ["tool__web_search"]
forbidden_tools: []
max_rounds: 3
summary_triggered: true
unhandled_exception: false
required_answer_points:
  - "tool-unavailable"
forbidden_answer_points:
  - "fake search result"
```

### 11.4 `gc_multi_tool_search_fetch_001.yaml`

Purpose:

```text
The agent should call search first, then fetch page content, and synthesize the final answer from the second tool result.
```

Expected behavior:

```text
final_status: success
required_tools: ["tool__web_search", "tool__fetch_page"]
forbidden_tools: []
max_rounds: 4
summary_triggered: false
unhandled_exception: false
required_answer_points:
  - "fetched-content-used"
```

The exact fixture structure can be adjusted to fit existing scripted LLM helpers, but the case data must not be fully hardcoded inside the pytest test function.

## 12. Marker Registration

Add the `golden_case` marker to the project pytest configuration if needed.

Example:

```ini
[pytest]
markers =
    golden_case: task-level agent workflow golden case regression tests
```

Or add it to the existing `pyproject.toml` pytest configuration if the project uses that.

## 13. Local Command

The following command must pass:

```bash
uv run python -m pytest tests/golden_cases -m golden_case -q
```

If the project does not use `uv`, use the existing project test command, but document the equivalent command.

## 14. Acceptance Criteria

Golden Cases v1 is complete when all conditions below are true:

```text
1. Four case files are loaded from disk.
2. The four case files are not hardcoded inside the pytest test body.
3. All cases run through the same runner.
4. All cases use the same assertion checker.
5. The stub profile runs offline and deterministically.
6. No real LLM is called.
7. No real MCP, OpenClaw, external network, or staging service is called.
8. The pytest command passes locally.
9. A failing case error message includes case_id and failed assertion field.
10. The runner returns a normalized workflow report.
```

## 15. Implementation Order

Implement in this order:

```text
Step 1: Create schema dataclass and schema error classes.
Step 2: Implement file discovery and loader.
Step 3: Add four minimal case files.
Step 4: Implement runner with stub LLM and stub tool results.
Step 5: Implement assertion checker.
Step 6: Add pytest parametrized entry file.
Step 7: Register golden_case marker.
Step 8: Run the local pytest command and fix failures.
```

## 16. Out of Scope for This Task

Do not implement:

```text
Golden Case baseline file
Quality Gate integration
Allure integration
Langfuse integration
LangSmith integration
real_llm profile
staging profile
memory governance cases
context compression cases
LLM-as-a-Judge
semantic scoring
dashboard
CI workflow
```

These are planned follow-ups after Golden Cases v1 is stable.

## 17. Expected Final Summary

After implementation, summarize:

```text
1. Files created or changed.
2. How many cases were added.
3. How the runner stubs LLM and tools.
4. Which real workflow code path is exercised.
5. The exact pytest command used.
6. Whether the command passed.
7. Any assumptions or TODOs.
```
