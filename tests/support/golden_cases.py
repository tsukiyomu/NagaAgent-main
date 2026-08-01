"""Schema objects for deterministic Agent Workflow Golden Cases."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import apiserver.agentic_tool_loop as loop_module
import apiserver.context_compressor as context_compressor
import apiserver.llm_service as llm_service
import apiserver.message_queue as message_queue
from tests.support.agentic_tool_loop_helpers import (
    EmptyQueueStub,
    ScriptedStreamLLM,
    extract_sse_json_events,
    sse,
    sse_done,
)


ALLOWED_GOLDEN_CASE_PROFILES = {"stub", "real_llm", "staging"}
ALLOWED_GOLDEN_CASE_BUSINESS_FLOWS = {f"BF-{index:02d}" for index in range(1, 11)}
ALLOWED_GOLDEN_CASE_FINAL_STATUS = {"success", "degraded", "failed"}


class GoldenCaseSchemaError(ValueError):
    """Base error for malformed Golden Case schema data."""

    def __init__(self, message: str, *, case_id: str | None = None, field: str | None = None) -> None:
        self.case_id = case_id
        self.field = field
        details = []
        if case_id:
            details.append(f"case_id={case_id}")
        if field:
            details.append(f"field={field}")
        if details:
            message = f"{message} ({', '.join(details)})"
        super().__init__(message)


class GoldenCaseMissingFieldError(GoldenCaseSchemaError):
    """Raised when a required Golden Case schema field is absent or empty."""


class GoldenCaseInvalidFieldError(GoldenCaseSchemaError):
    """Raised when a Golden Case schema field has an unsupported value."""


class GoldenCaseDuplicateIdError(GoldenCaseSchemaError):
    """Raised when multiple case files define the same case_id."""


class GoldenCaseAssertionError(AssertionError):
    """Raised when a Golden Case run report violates its expected contract."""

    def __init__(self, case_id: str, failures: tuple[str, ...]) -> None:
        self.case_id = case_id
        self.failures = failures
        super().__init__(f"Golden Case {case_id} failed: {'; '.join(failures)}")


@dataclass(frozen=True)
class GoldenCaseInput:
    user_input: str
    history: tuple[dict[str, Any], ...] = ()
    session: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GoldenCaseFixtures:
    llm_script: tuple[dict[str, Any], ...] = ()
    tool_results: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GoldenCaseExpected:
    final_status: str
    required_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    max_rounds: int = 1
    required_answer_points: tuple[str, ...] = ()
    forbidden_answer_points: tuple[str, ...] = ()
    summary_triggered: bool = False
    unhandled_exception: bool = False


@dataclass(frozen=True)
class GoldenCaseGate:
    blocking: bool = True
    baseline_compare: bool = False


@dataclass(frozen=True)
class GoldenCaseRunReport:
    case_id: str
    profile: str
    final_status: str
    failure_stage: str
    rounds: int
    tool_call_count: int
    called_tools: tuple[str, ...]
    tool_results: tuple[dict[str, Any], ...]
    final_answer: str
    summary_triggered: bool
    unhandled_exception: bool
    sse_events: tuple[dict[str, Any], ...]
    llm_call_count: int


@dataclass(frozen=True)
class GoldenCaseAssertionResult:
    case_id: str
    passed: bool
    failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class GoldenCase:
    case_id: str
    business_flow: str
    group: str
    profile: str
    title: str
    input: GoldenCaseInput
    fixtures: GoldenCaseFixtures
    expected: GoldenCaseExpected
    gate: GoldenCaseGate

    def validate_schema(self) -> "GoldenCase":
        """Validate static schema fields before a case is executed."""
        _require_text(self.case_id, "case_id", self.case_id)
        _require_text(self.business_flow, "business_flow", self.case_id)
        _require_text(self.group, "group", self.case_id)
        _require_text(self.profile, "profile", self.case_id)
        _require_text(self.title, "title", self.case_id)
        _require_text(self.input.user_input, "input.user_input", self.case_id)

        if self.business_flow not in ALLOWED_GOLDEN_CASE_BUSINESS_FLOWS:
            raise GoldenCaseInvalidFieldError(
                "Unsupported Golden Case business flow",
                case_id=self.case_id,
                field="business_flow",
            )
        if self.profile not in ALLOWED_GOLDEN_CASE_PROFILES:
            raise GoldenCaseInvalidFieldError(
                "Unsupported Golden Case profile",
                case_id=self.case_id,
                field="profile",
            )
        if self.expected.final_status not in ALLOWED_GOLDEN_CASE_FINAL_STATUS:
            raise GoldenCaseInvalidFieldError(
                "Unsupported expected final_status",
                case_id=self.case_id,
                field="expected.final_status",
            )
        if self.expected.max_rounds < 1:
            raise GoldenCaseInvalidFieldError(
                "expected.max_rounds must be at least 1",
                case_id=self.case_id,
                field="expected.max_rounds",
            )
        return self


def _require_text(value: str, field_name: str, case_id: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise GoldenCaseMissingFieldError(
            "Required Golden Case field is empty",
            case_id=case_id,
            field=field_name,
        )


GOLDEN_CASE_FILE_SUFFIXES = {".json", ".yaml", ".yml"}


def discover_golden_case_files(path: str | Path) -> tuple[Path, ...]:
    """Return stable, recursive Golden Case data files under a file or directory."""
    root = Path(path)
    if not root.exists():
        raise GoldenCaseSchemaError(f"Golden Case path does not exist: {root}")
    if root.is_file():
        if root.suffix.lower() not in GOLDEN_CASE_FILE_SUFFIXES:
            raise GoldenCaseInvalidFieldError(
                "Unsupported Golden Case file extension",
                field="path",
            )
        return (root,)
    return tuple(
        sorted(
            candidate
            for candidate in root.rglob("*")
            if candidate.is_file() and candidate.suffix.lower() in GOLDEN_CASE_FILE_SUFFIXES
        )
    )


def load_golden_cases(path: str | Path) -> tuple[GoldenCase, ...]:
    """Load and validate all Golden Cases from a file or directory."""
    cases: list[GoldenCase] = []
    seen_case_ids: dict[str, Path] = {}
    for case_file in discover_golden_case_files(path):
        raw_case = _read_case_file(case_file)
        case = golden_case_from_mapping(raw_case, source=case_file).validate_schema()
        if case.case_id in seen_case_ids:
            raise GoldenCaseDuplicateIdError(
                "Duplicate Golden Case case_id",
                case_id=case.case_id,
                field=str(case_file),
            )
        seen_case_ids[case.case_id] = case_file
        cases.append(case)
    return tuple(cases)


def golden_case_from_mapping(raw: dict[str, Any], *, source: str | Path | None = None) -> GoldenCase:
    """Convert raw case data into a typed GoldenCase schema object."""
    case_id = _required_text(raw, "case_id", source=source)
    input_data = _required_mapping(raw, "input", case_id=case_id, source=source)
    fixtures_data = _required_mapping(raw, "fixtures", case_id=case_id, source=source)
    expected_data = _required_mapping(raw, "expected", case_id=case_id, source=source)
    gate_data = _required_mapping(raw, "gate", case_id=case_id, source=source)

    return GoldenCase(
        case_id=case_id,
        business_flow=_required_text(raw, "business_flow", case_id=case_id, source=source),
        group=_required_text(raw, "group", case_id=case_id, source=source),
        profile=_required_text(raw, "profile", case_id=case_id, source=source),
        title=_required_text(raw, "title", case_id=case_id, source=source),
        input=GoldenCaseInput(
            user_input=_required_text(input_data, "user_input", case_id=case_id, field_prefix="input", source=source),
            history=_coerce_mapping_tuple(
                input_data.get("history", []),
                case_id=case_id,
                field="input.history",
            ),
            session=_coerce_mapping(
                input_data.get("session", {}),
                case_id=case_id,
                field="input.session",
            ),
        ),
        fixtures=GoldenCaseFixtures(
            llm_script=_coerce_mapping_tuple(
                fixtures_data.get("llm_script", []),
                case_id=case_id,
                field="fixtures.llm_script",
            ),
            tool_results=_coerce_mapping(
                fixtures_data.get("tool_results", {}),
                case_id=case_id,
                field="fixtures.tool_results",
            ),
        ),
        expected=GoldenCaseExpected(
            final_status=_required_text(
                expected_data,
                "final_status",
                case_id=case_id,
                field_prefix="expected",
                source=source,
            ),
            required_tools=_coerce_text_tuple(
                expected_data.get("required_tools", []),
                case_id=case_id,
                field="expected.required_tools",
            ),
            forbidden_tools=_coerce_text_tuple(
                expected_data.get("forbidden_tools", []),
                case_id=case_id,
                field="expected.forbidden_tools",
            ),
            max_rounds=_coerce_int(
                expected_data.get("max_rounds", 1),
                case_id=case_id,
                field="expected.max_rounds",
            ),
            required_answer_points=_coerce_text_tuple(
                expected_data.get("required_answer_points", []),
                case_id=case_id,
                field="expected.required_answer_points",
            ),
            forbidden_answer_points=_coerce_text_tuple(
                expected_data.get("forbidden_answer_points", []),
                case_id=case_id,
                field="expected.forbidden_answer_points",
            ),
            summary_triggered=_coerce_bool(
                expected_data.get("summary_triggered", False),
                case_id=case_id,
                field="expected.summary_triggered",
            ),
            unhandled_exception=_coerce_bool(
                expected_data.get("unhandled_exception", False),
                case_id=case_id,
                field="expected.unhandled_exception",
            ),
        ),
        gate=GoldenCaseGate(
            blocking=_coerce_bool(gate_data.get("blocking", True), case_id=case_id, field="gate.blocking"),
            baseline_compare=_coerce_bool(
                gate_data.get("baseline_compare", False),
                case_id=case_id,
                field="gate.baseline_compare",
            ),
        ),
    )


def _read_case_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8")
        if suffix == ".json":
            parsed = json.loads(text)
        elif suffix in {".yaml", ".yml"}:
            parsed = _load_yaml(text)
        else:
            raise GoldenCaseInvalidFieldError("Unsupported Golden Case file extension", field=str(path))
    except GoldenCaseSchemaError:
        raise
    except Exception as exc:
        raise GoldenCaseSchemaError(f"Failed to parse Golden Case file: {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise GoldenCaseInvalidFieldError(
            "Golden Case file must contain a mapping object",
            field=str(path),
        )
    return parsed


def _load_yaml(text: str) -> Any:
    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise GoldenCaseSchemaError("PyYAML is required to load YAML Golden Case files") from exc
    return yaml.safe_load(text)


def _required_text(
    data: dict[str, Any],
    key: str,
    *,
    case_id: str | None = None,
    field_prefix: str | None = None,
    source: str | Path | None = None,
) -> str:
    field_name = f"{field_prefix}.{key}" if field_prefix else key
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        source_suffix = f" in {source}" if source else ""
        raise GoldenCaseMissingFieldError(
            f"Required Golden Case field is missing or empty{source_suffix}",
            case_id=case_id,
            field=field_name,
        )
    return value


def _required_mapping(
    data: dict[str, Any],
    key: str,
    *,
    case_id: str,
    source: str | Path | None,
) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        source_suffix = f" in {source}" if source else ""
        raise GoldenCaseMissingFieldError(
            f"Required Golden Case mapping is missing{source_suffix}",
            case_id=case_id,
            field=key,
        )
    return value


def _coerce_mapping(value: Any, *, case_id: str, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GoldenCaseInvalidFieldError("Expected a mapping", case_id=case_id, field=field)
    return value


def _coerce_mapping_tuple(value: Any, *, case_id: str, field: str) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise GoldenCaseInvalidFieldError("Expected a list of mappings", case_id=case_id, field=field)
    for item in value:
        if not isinstance(item, dict):
            raise GoldenCaseInvalidFieldError("Expected a list of mappings", case_id=case_id, field=field)
    return tuple(value)


def _coerce_text_tuple(value: Any, *, case_id: str, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise GoldenCaseInvalidFieldError("Expected a list of strings", case_id=case_id, field=field)
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise GoldenCaseInvalidFieldError("Expected a list of non-empty strings", case_id=case_id, field=field)
    return tuple(value)


def _coerce_bool(value: Any, *, case_id: str, field: str) -> bool:
    if not isinstance(value, bool):
        raise GoldenCaseInvalidFieldError("Expected a boolean", case_id=case_id, field=field)
    return value


def _coerce_int(value: Any, *, case_id: str, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GoldenCaseInvalidFieldError("Expected an integer", case_id=case_id, field=field)
    return value


async def run_stub_golden_case(case: GoldenCase, monkeypatch: Any) -> GoldenCaseRunReport:
    """Run one stub Golden Case through the real agentic loop with deterministic doubles."""
    case.validate_schema()
    if case.profile != "stub":
        raise GoldenCaseInvalidFieldError(
            "run_stub_golden_case only supports stub profile",
            case_id=case.case_id,
            field="profile",
        )

    messages = _build_case_messages(case)
    llm = ScriptedStreamLLM(_build_llm_round_scripts(case))
    dispatch_calls: list[list[dict[str, Any]]] = []
    dispatched_results: list[dict[str, Any]] = []

    async def _compress_passthrough(messages_to_compress):
        return context_compressor.CompressResult(
            messages=messages_to_compress,
            sse_events=[],
            compressed=False,
        )

    async def _dispatch_stub(calls, _session_id, source_agent_id=None):
        del source_agent_id
        dispatch_calls.append(copy.deepcopy(calls))
        results = [_build_stub_tool_result(case, call) for call in calls]
        dispatched_results.extend(copy.deepcopy(results))
        return results

    monkeypatch.setattr(
        loop_module,
        "get_config",
        lambda: SimpleNamespace(api=SimpleNamespace(temperature=0.0)),
    )
    monkeypatch.setattr(llm_service, "get_llm_service", lambda: llm)
    monkeypatch.setattr(context_compressor, "compress_context", _compress_passthrough)
    monkeypatch.setattr(message_queue, "get_message_queue", lambda: EmptyQueueStub())
    monkeypatch.setattr(loop_module, "execute_tool_calls", _dispatch_stub)

    chunks: list[str] = []
    unhandled_exception = False
    try:
        async for chunk in loop_module.run_agentic_loop(
            messages,
            session_id=f"golden-{case.case_id}",
            max_rounds=case.expected.max_rounds,
            tools=_build_tool_schemas(case),
        ):
            chunks.append(chunk)
    except Exception:
        unhandled_exception = True
        raise

    events = tuple(extract_sse_json_events(chunks))
    called_tools = tuple(
        call.get("_original_name") or _dispatch_tool_name(call)
        for round_calls in dispatch_calls
        for call in round_calls
    )
    final_answer = _last_content_text(events)
    had_tool_error = any(result.get("status") == "error" for result in dispatched_results)
    final_status = "failed" if unhandled_exception else "degraded" if had_tool_error else "success"

    return GoldenCaseRunReport(
        case_id=case.case_id,
        profile=case.profile,
        final_status=final_status,
        failure_stage="tool_dispatch" if had_tool_error else "none",
        rounds=len([event for event in events if event.get("type") == "round_end"]),
        tool_call_count=len(called_tools),
        called_tools=called_tools,
        tool_results=tuple(dispatched_results),
        final_answer=final_answer,
        summary_triggered=any(event.get("type") == "round_start" and event.get("summary") for event in events),
        unhandled_exception=unhandled_exception,
        sse_events=events,
        llm_call_count=len(llm.calls),
    )


def _build_case_messages(case: GoldenCase) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": "You are running a deterministic Golden Case."},
        *copy.deepcopy(list(case.input.history)),
        {"role": "user", "content": case.input.user_input},
    ]


def _build_llm_round_scripts(case: GoldenCase) -> list[list[str]]:
    scripts: list[list[str]] = []
    for index, step in enumerate(case.fixtures.llm_script, start=1):
        if "tool_call" in step:
            scripts.append([
                sse({"type": "content", "text": f"round-{index}: using tool"}),
                _native_tool_call_chunk(
                    call_id=f"{case.case_id}-call-{index}",
                    tool_name=str(step["tool_call"]),
                    args=_coerce_mapping(step.get("args", {}), case_id=case.case_id, field="fixtures.llm_script.args"),
                ),
                sse_done(),
            ])
        elif "final_answer" in step:
            scripts.append([
                sse({"type": "content", "text": str(step["final_answer"])}),
                sse_done(),
            ])
        else:
            raise GoldenCaseInvalidFieldError(
                "LLM script step must define tool_call or final_answer",
                case_id=case.case_id,
                field="fixtures.llm_script",
            )
    if not scripts:
        raise GoldenCaseMissingFieldError(
            "Golden Case requires at least one LLM script step",
            case_id=case.case_id,
            field="fixtures.llm_script",
        )
    return scripts


def _native_tool_call_chunk(call_id: str, *, tool_name: str, args: dict[str, Any]) -> str:
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


def _build_tool_schemas(case: GoldenCase) -> list[dict[str, Any]]:
    tool_names = sorted(
        {
            str(step["tool_call"])
            for step in case.fixtures.llm_script
            if "tool_call" in step
        }
    )
    return [
        {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": f"Stub schema for {tool_name}",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for tool_name in tool_names
    ]


def _build_stub_tool_result(case: GoldenCase, call: dict[str, Any]) -> dict[str, Any]:
    tool_name = call.get("_original_name") or _dispatch_tool_name(call)
    configured_result = case.fixtures.tool_results.get(tool_name)
    if not isinstance(configured_result, dict):
        return {
            "tool_call": call,
            "result": f"No stub result configured for {tool_name}",
            "status": "error",
            "service_name": call.get("agentType", "tool"),
            "tool_name": call.get("tool_name", tool_name),
        }

    configured_status = configured_result.get("status", "success")
    status = "success" if configured_status == "success" else "error"
    result = configured_result.get("result") or configured_result.get("error") or ""
    return {
        "tool_call": call,
        "result": str(result),
        "status": status,
        "service_name": call.get("agentType", "tool"),
        "tool_name": call.get("tool_name", tool_name),
    }


def _dispatch_tool_name(call: dict[str, Any]) -> str:
    agent_type = call.get("agentType")
    tool_name = call.get("tool_name", "")
    if agent_type == "tool" and tool_name:
        return f"tool__{tool_name}"
    if agent_type == "mcp":
        return f"mcp__{call.get('service_name', '')}__{tool_name}"
    return str(tool_name)


def _last_content_text(events: tuple[dict[str, Any], ...]) -> str:
    content_events = [event for event in events if event.get("type") == "content"]
    if not content_events:
        return ""
    return str(content_events[-1].get("text", ""))


def assert_golden_case_report(case: GoldenCase, report: GoldenCaseRunReport) -> GoldenCaseAssertionResult:
    """Assert a Golden Case run report against the deterministic v1 expected contract."""
    failures = evaluate_golden_case_report(case, report).failures
    if failures:
        raise GoldenCaseAssertionError(case.case_id, failures)
    return GoldenCaseAssertionResult(case_id=case.case_id, passed=True)


def evaluate_golden_case_report(case: GoldenCase, report: GoldenCaseRunReport) -> GoldenCaseAssertionResult:
    """Return all deterministic v1 assertion failures for a Golden Case report."""
    failures: list[str] = []
    if report.case_id != case.case_id:
        failures.append(f"case_id mismatch: expected {case.case_id}, got {report.case_id}")
    if report.final_status != case.expected.final_status:
        failures.append(
            f"final_status mismatch: expected {case.expected.final_status}, got {report.final_status}"
        )
    if report.rounds > case.expected.max_rounds:
        failures.append(f"rounds exceeded: expected <= {case.expected.max_rounds}, got {report.rounds}")
    if report.summary_triggered is not case.expected.summary_triggered:
        failures.append(
            "summary_triggered mismatch: "
            f"expected {case.expected.summary_triggered}, got {report.summary_triggered}"
        )
    if report.unhandled_exception is not case.expected.unhandled_exception:
        failures.append(
            "unhandled_exception mismatch: "
            f"expected {case.expected.unhandled_exception}, got {report.unhandled_exception}"
        )

    called_tools = list(report.called_tools)
    for tool_name in case.expected.required_tools:
        if tool_name not in called_tools:
            failures.append(f"required tool not called: {tool_name}")
    for tool_name in case.expected.forbidden_tools:
        if tool_name in called_tools:
            failures.append(f"forbidden tool called: {tool_name}")
    if case.expected.required_tools and not _contains_ordered_subsequence(
        called_tools,
        list(case.expected.required_tools),
    ):
        failures.append(
            "required tool order mismatch: "
            f"expected subsequence {list(case.expected.required_tools)}, got {called_tools}"
        )

    answer_lower = report.final_answer.lower()
    for answer_point in case.expected.required_answer_points:
        if answer_point.lower() not in answer_lower:
            failures.append(f"required answer point missing: {answer_point}")
    for answer_point in case.expected.forbidden_answer_points:
        if answer_point.lower() in answer_lower:
            failures.append(f"forbidden answer point present: {answer_point}")

    return GoldenCaseAssertionResult(
        case_id=case.case_id,
        passed=not failures,
        failures=tuple(failures),
    )


def _contains_ordered_subsequence(haystack: list[str], needle: list[str]) -> bool:
    if not needle:
        return True
    needle_index = 0
    for item in haystack:
        if item == needle[needle_index]:
            needle_index += 1
            if needle_index == len(needle):
                return True
    return False
