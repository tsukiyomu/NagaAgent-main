from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.support.quality_gate import (
    QualityGateConfig,
    apply_allure_case_labels,
    generate_quality_gate_artifacts,
    infer_feature,
    should_include_for_gate,
)


_QUALITY_GATE_STATE_ATTR = "_quality_gate_state"


def _quality_gate_enabled(config: Any) -> bool:
    return bool(config.getoption("--quality-gate", default=False))


def _quality_gate_state(config: Any) -> dict[str, Any] | None:
    return getattr(config, _QUALITY_GATE_STATE_ATTR, None)


def _allure_reporting_enabled(config: Any) -> bool:
    alluredir = config.getoption("--alluredir", default=None)
    if not alluredir:
        alluredir = config.getoption("allure_report_dir", default=None)
    return bool(alluredir)


def _build_gate_config(config: Any) -> QualityGateConfig:
    return QualityGateConfig(
        profile=str(config.getoption("--quality-gate-profile")),
        artifacts_dir=Path(str(config.getoption("--quality-gate-artifacts-dir"))),
        baseline_dir=Path(str(config.getoption("--quality-gate-baseline-dir"))),
    )


def pytest_addoption(parser):
    group = parser.getgroup("quality-gate")
    group.addoption(
        "--quality-gate",
        action="store_true",
        default=False,
        help="Enable local quality-gate aggregation and report emission.",
    )
    group.addoption(
        "--quality-gate-profile",
        action="store",
        default="stub",
        help="Quality-gate runtime profile name (default: %(default)s).",
    )
    group.addoption(
        "--quality-gate-artifacts-dir",
        action="store",
        default="tests/artifacts/quality_gate",
        help="Output directory for quality-gate artifacts (default: %(default)s).",
    )
    group.addoption(
        "--quality-gate-baseline-dir",
        action="store",
        default="tests/baseline/quality_gate",
        help="Baseline directory for quality-gate comparison (default: %(default)s).",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "real_llm: opt-in real LLM smoke profile.")
    if not _quality_gate_enabled(config):
        return
    setattr(
        config,
        _QUALITY_GATE_STATE_ATTR,
        {
            "records_by_nodeid": {},
            "artifacts": None,
        },
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if not _quality_gate_enabled(item.config):
        return

    marker_names = {mark.name for mark in item.iter_markers()}
    if not should_include_for_gate(report.nodeid, marker_names):
        return

    state = _quality_gate_state(item.config)
    if state is None:
        return

    if report.outcome == "failed":
        longrepr = str(report.longrepr)
        failure_reason = longrepr.strip().splitlines()[-1][:500] if longrepr else ""
    elif report.outcome == "skipped":
        failure_reason = str(report.longrepr).strip()[:500]
    else:
        failure_reason = ""

    candidate = {
        "nodeid": report.nodeid,
        "when": report.when,
        "outcome": report.outcome,
        "duration": getattr(report, "duration", None),
        "marker_names": sorted(marker_names),
        "user_properties": list(getattr(report, "user_properties", [])),
        "failure_reason": failure_reason,
    }
    quality_case_payload = None
    for key, value in candidate["user_properties"]:
        if key == "quality_gate_case" and isinstance(value, dict):
            quality_case_payload = value

    records_by_nodeid: dict[str, Any] = state["records_by_nodeid"]
    existing = records_by_nodeid.get(report.nodeid)

    if report.when == "call":
        feature = str(quality_case_payload.get("feature")) if isinstance(quality_case_payload, dict) else infer_feature(
            report.nodeid, marker_names
        )
        story = (
            str(quality_case_payload.get("story"))
            if isinstance(quality_case_payload, dict) and isinstance(quality_case_payload.get("story"), str)
            else "correctness"
        )
        if feature in {"p2_api", "agentic_tool_loop", "real_llm"}:
            apply_allure_case_labels(feature=feature, story=story)
        records_by_nodeid[report.nodeid] = candidate
        if _allure_reporting_enabled(item.config):
            snapshot = generate_quality_gate_artifacts(
                config=_build_gate_config(item.config),
                records=list(records_by_nodeid.values()),
                allow_baseline_bootstrap=False,
            )
            state["artifacts"] = snapshot
        return
    if report.when == "setup" and report.outcome in {"failed", "skipped"} and existing is None:
        records_by_nodeid[report.nodeid] = candidate
        return
    if report.when == "teardown" and report.outcome == "failed":
        records_by_nodeid[report.nodeid] = candidate


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    del exitstatus
    if not _quality_gate_enabled(config):
        return

    state = _quality_gate_state(config)
    if state is None:
        return

    records = list(state["records_by_nodeid"].values())
    gate_config = _build_gate_config(config)
    artifacts = generate_quality_gate_artifacts(config=gate_config, records=records)
    state["artifacts"] = artifacts

    summary = artifacts.report_payload["summary"]
    regression = artifacts.report_payload["regression"]
    terminalreporter.section("Quality Gate Summary", sep="-")
    terminalreporter.write_line(
        f"gate_result={summary['gate_result']} total={summary['total']} "
        f"passed={summary['passed']} failed={summary['failed']} warned={summary['warned']}"
    )
    terminalreporter.write_line(
        f"artifacts: {artifacts.report_path} | {artifacts.summary_path}"
    )
    terminalreporter.write_line(f"baseline: {artifacts.baseline_path}")
    if regression.get("pass_rate_delta") is not None:
        terminalreporter.write_line(f"pass_rate_delta={regression['pass_rate_delta']}")
    if regression.get("latency_delta") is not None:
        terminalreporter.write_line(f"latency_delta={regression['latency_delta']}")
    if regression.get("rounds_delta") is not None:
        terminalreporter.write_line(f"rounds_delta={regression['rounds_delta']}")
    if artifacts.allure_attached:
        terminalreporter.write_line("allure_attachments=enabled")


async def _noop_async(*_args, **_kwargs):
    """Generic async no-op used to disable external side effects in smoke tests."""
    return None


class _DummyLLMService:
    """Deterministic LLM stub for /chat smoke assertions."""

    async def chat_with_context_and_reasoning(self, _messages, _temperature=0.7):
        # Keep response shape consistent with production code path.
        from apiserver.llm_service import LLMResponse

        # Fixed output makes smoke assertions stable and offline-runnable.
        return LLMResponse(content="smoke-chat-ok", reasoning_content="")


async def _fake_run_agentic_loop(
    _messages,
    _session_id,
    max_rounds=5,
    model_override=None,
    tools=None,
    source_agent_id=None,
):
    """Deterministic SSE stub for /chat/stream smoke assertions.

    Event contract (minimal):
    1) content event exists
    2) round_end exists
    3) terminal [DONE] exists
    """
    # Keep signature aligned with real implementation, but these are unused in stub mode.
    del max_rounds, model_override, tools, source_agent_id

    # Minimal stream content to prove the stream produced business payload.
    yield 'data: {"type":"content","text":"smoke-stream-ok"}\n\n'
    # End one round explicitly, mirroring real loop semantics.
    yield 'data: {"type":"round_end","round":1,"has_more":false}\n\n'
    # Terminal event required by stream smoke gate.
    yield "data: [DONE]\n\n"


@pytest.fixture
def client(monkeypatch):
    """Shared TestClient fixture for all smoke tests.

    Responsibilities:
    - start/stop FastAPI app lifecycle once per test via context manager
    - replace unstable dependencies with deterministic stubs
    - keep smoke tests offline and repeatable
    """
    from apiserver.api_server import app
    import apiserver.agentic_tool_loop as agentic_tool_loop
    import apiserver.routes.chat as chat_routes

    # ---- Context/prompt assembly stabilization ----
    # Disable agent-specific prompt context to avoid environment-dependent branches.
    monkeypatch.setattr(chat_routes, "_build_agent_prompt_context", lambda _agent_id: None)
    # Use fixed prompt text to avoid content drift between runs.
    monkeypatch.setattr(
        chat_routes, "build_system_prompt", lambda *args, **kwargs: "SMOKE_SYSTEM_PROMPT"
    )
    monkeypatch.setattr(
        chat_routes, "build_context_supplement", lambda *args, **kwargs: "SMOKE_SUPPLEMENT"
    )

    # ---- Model/tool path stabilization ----
    # Force non-native function-calling path for deterministic smoke behavior.
    monkeypatch.setattr(chat_routes, "_supports_function_calling", lambda _model_name: False)
    # Replace real LLM service with deterministic response stub.
    monkeypatch.setattr(chat_routes, "get_llm_service", lambda: _DummyLLMService())
    # Replace real agentic loop with deterministic SSE sequence.
    monkeypatch.setattr(agentic_tool_loop, "run_agentic_loop", _fake_run_agentic_loop)

    # ---- Side-effect isolation ----
    # Disable background activity update (could trigger external interactions).
    monkeypatch.setattr(chat_routes, "_update_proactive_activity_silent", _noop_async)
    # Disable remote conversation lifecycle notification.
    monkeypatch.setattr(chat_routes, "_notify_conversation_event", _noop_async)
    # Disable persistence writes for smoke scope.
    monkeypatch.setattr(chat_routes, "_save_conversation_and_logs", lambda *_args, **_kwargs: None)
    # Disable telemetry emission to keep tests pure/offline.
    monkeypatch.setattr(chat_routes, "emit_telemetry", lambda *_args, **_kwargs: None)

    # TestClient context ensures startup/shutdown events are handled correctly.
    # monkeypatch automatically restores originals after fixture teardown.
    with TestClient(app) as test_client:
        yield test_client
