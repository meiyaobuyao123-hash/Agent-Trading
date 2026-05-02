"""
Eval Runner 单元测试 — W3 D5+ autonomous-loop 续 18

跑法:python3 -m pytest tests/test_eval_runner.py -v

注意:这测的是 runner 框架本身,真正跑 fixture 见
   `python3 -m agent.eval.runner --suite=l1_tool`
"""
from __future__ import annotations
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.eval import runner as runner_mod  # noqa: E402
from agent.eval.runner import (  # noqa: E402
    CaseResult,
    EvalReport,
    GoldenCase,
    ToolReport,
    _check_idempotent,
    _load_golden_cases,
    _run_one_case,
    _validate_metadata,
    run_l1_tool_suite,
)


# ── EvalReport / ToolReport ─────────────────────────────────

def test_eval_report_pass_rate_zero_when_no_cases():
    r = EvalReport(suite="l1_tool")
    assert r.pass_rate == 0.0


def test_eval_report_pass_rate():
    r = EvalReport(suite="l1_tool", total_cases=10, total_passed=7, total_failed=3)
    assert r.pass_rate == 0.7


def test_eval_report_summary_line():
    r = EvalReport(suite="l1_tool", total_cases=5, total_passed=4,
                    total_failed=1, duration_s=0.5)
    line = r.summary_line()
    assert "4/5" in line
    assert "80.0%" in line
    assert "0.50s" in line


def test_tool_report_pass_rate():
    tr = ToolReport(tool_name="x", total=5, passed=3, failed=2)
    assert tr.pass_rate == 0.6


# ── _validate_metadata ──────────────────────────────────────

def test_validate_metadata_ok():
    fake = MagicMock()
    fake.metadata.name = "calc_x"
    fake.metadata.description = "x" * 50
    fake.metadata.idempotent = True
    fake.metadata.idempotency_key_fields = []
    fake.metadata.cost_usd = 0.0
    fake.metadata.p95_latency_ms = 100
    fake.metadata.failure_modes = ["INPUT_SCHEMA_INVALID"]
    fake.to_anthropic_tool_spec.return_value = {
        "name": "calc_x", "input_schema": {}, "description": "x" * 50,
    }
    ok, issues = _validate_metadata("calc_x", fake)
    assert ok is True
    assert issues == []


def test_validate_metadata_short_description_flagged():
    fake = MagicMock()
    fake.metadata.name = "calc_x"
    fake.metadata.description = "short"
    fake.metadata.idempotent = True
    fake.metadata.idempotency_key_fields = []
    fake.metadata.cost_usd = 0.0
    fake.metadata.p95_latency_ms = 100
    fake.metadata.failure_modes = ["x"]
    fake.to_anthropic_tool_spec.return_value = {"name": "calc_x", "input_schema": {}}
    ok, issues = _validate_metadata("calc_x", fake)
    assert ok is False
    assert any("description" in i for i in issues)


def test_validate_metadata_name_mismatch_flagged():
    fake = MagicMock()
    fake.metadata.name = "wrong_name"
    fake.metadata.description = "x" * 50
    fake.metadata.idempotent = True
    fake.metadata.idempotency_key_fields = []
    fake.metadata.cost_usd = 0.0
    fake.metadata.p95_latency_ms = 100
    fake.metadata.failure_modes = ["x"]
    fake.to_anthropic_tool_spec.return_value = {"name": "wrong_name", "input_schema": {}}
    ok, issues = _validate_metadata("expected_name", fake)
    assert ok is False
    assert any("name" in i for i in issues)


def test_validate_metadata_no_failure_modes_flagged():
    fake = MagicMock()
    fake.metadata.name = "x"
    fake.metadata.description = "x" * 50
    fake.metadata.idempotent = True
    fake.metadata.idempotency_key_fields = []
    fake.metadata.cost_usd = 0.0
    fake.metadata.p95_latency_ms = 100
    fake.metadata.failure_modes = []
    fake.to_anthropic_tool_spec.return_value = {"name": "x", "input_schema": {}}
    ok, issues = _validate_metadata("x", fake)
    assert ok is False
    assert any("failure_modes" in i for i in issues)


def test_validate_metadata_unreasonable_latency_flagged():
    fake = MagicMock()
    fake.metadata.name = "x"
    fake.metadata.description = "x" * 50
    fake.metadata.idempotent = True
    fake.metadata.idempotency_key_fields = []
    fake.metadata.cost_usd = 0.0
    fake.metadata.p95_latency_ms = -1
    fake.metadata.failure_modes = ["x"]
    fake.to_anthropic_tool_spec.return_value = {"name": "x", "input_schema": {}}
    ok, issues = _validate_metadata("x", fake)
    assert ok is False
    assert any("latency_ms" in i for i in issues)


def test_validate_metadata_anthropic_spec_missing_input_schema():
    fake = MagicMock()
    fake.metadata.name = "x"
    fake.metadata.description = "x" * 50
    fake.metadata.idempotent = True
    fake.metadata.idempotency_key_fields = []
    fake.metadata.cost_usd = 0.0
    fake.metadata.p95_latency_ms = 100
    fake.metadata.failure_modes = ["x"]
    fake.to_anthropic_tool_spec.return_value = {"name": "x"}  # 缺 input_schema
    ok, issues = _validate_metadata("x", fake)
    assert ok is False
    assert any("anthropic_tool_spec" in i for i in issues)


# ── _run_one_case ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_one_case_ok_path():
    """期望 ok + tool 实际返 ok → passed=True。"""
    fake_tool = MagicMock()
    fake_result = MagicMock(ok=True, output={"x": 1}, failure_mode=None)
    fake_tool.run = AsyncMock(return_value=fake_result)
    case = GoldenCase(name="t1", input={"a": 1}, expected_outcome="ok")
    cr = await _run_one_case(fake_tool, case)
    assert cr.passed is True


@pytest.mark.asyncio
async def test_run_one_case_input_invalid_match():
    fake_tool = MagicMock()
    fake_result = MagicMock(ok=False, output=None, failure_mode="INPUT_SCHEMA_INVALID")
    fake_tool.run = AsyncMock(return_value=fake_result)
    case = GoldenCase(name="t2", input={}, expected_outcome="input_invalid")
    cr = await _run_one_case(fake_tool, case)
    assert cr.passed is True


@pytest.mark.asyncio
async def test_run_one_case_outcome_mismatch():
    """期望 ok 但实际 input_invalid → failed。"""
    fake_tool = MagicMock()
    fake_result = MagicMock(ok=False, output=None, failure_mode="INPUT_SCHEMA_INVALID")
    fake_tool.run = AsyncMock(return_value=fake_result)
    case = GoldenCase(name="t3", input={}, expected_outcome="ok")
    cr = await _run_one_case(fake_tool, case)
    assert cr.passed is False
    assert "outcome 不匹配" in (cr.failure_reason or "")


@pytest.mark.asyncio
async def test_run_one_case_ok_with_check_subset():
    fake_tool = MagicMock()
    fake_result = MagicMock(ok=True, output={"win_rate": 0.6, "trade_count": 10},
                            failure_mode=None)
    fake_tool.run = AsyncMock(return_value=fake_result)
    case = GoldenCase(
        name="t4", input={"x": 1}, expected_outcome="ok_with_check",
        expect_fields={"win_rate": 0.6},
    )
    cr = await _run_one_case(fake_tool, case)
    assert cr.passed is True


@pytest.mark.asyncio
async def test_run_one_case_ok_with_check_field_mismatch():
    fake_tool = MagicMock()
    fake_result = MagicMock(ok=True, output={"win_rate": 0.5}, failure_mode=None)
    fake_tool.run = AsyncMock(return_value=fake_result)
    case = GoldenCase(
        name="t5", input={"x": 1}, expected_outcome="ok_with_check",
        expect_fields={"win_rate": 0.6},
    )
    cr = await _run_one_case(fake_tool, case)
    assert cr.passed is False
    assert "expect_fields 不匹配" in (cr.failure_reason or "")


@pytest.mark.asyncio
async def test_run_one_case_execute_error_failure_mode_check():
    fake_tool = MagicMock()
    fake_result = MagicMock(ok=False, output=None, failure_mode="EXECUTE_ERROR")
    fake_tool.run = AsyncMock(return_value=fake_result)
    case = GoldenCase(
        name="t6", input={"x": 1}, expected_outcome="execute_error",
        expected_failure_mode="EXECUTE_ERROR",
    )
    cr = await _run_one_case(fake_tool, case)
    assert cr.passed is True


@pytest.mark.asyncio
async def test_run_one_case_tool_run_throws():
    fake_tool = MagicMock()
    fake_tool.run = AsyncMock(side_effect=Exception("crash"))
    case = GoldenCase(name="t7", input={}, expected_outcome="ok")
    cr = await _run_one_case(fake_tool, case)
    assert cr.passed is False
    assert cr.actual_outcome == "exception"


# ── _check_idempotent ──────────────────────────────────────

@pytest.mark.asyncio
async def test_check_idempotent_skip_when_input_invalid():
    case = GoldenCase(name="t", input={}, expected_outcome="input_invalid")
    fake_tool = MagicMock()
    ok, err = await _check_idempotent(fake_tool, case)
    assert ok is True
    fake_tool.run.assert_not_called()


@pytest.mark.asyncio
async def test_check_idempotent_skip_when_skip_flag():
    case = GoldenCase(name="t", input={}, expected_outcome="ok",
                       skip_idempotent_check=True)
    fake_tool = MagicMock()
    ok, _ = await _check_idempotent(fake_tool, case)
    assert ok is True
    fake_tool.run.assert_not_called()


@pytest.mark.asyncio
async def test_check_idempotent_two_runs_match():
    fake_tool = MagicMock()
    fake_tool.metadata.idempotent = True
    same = MagicMock(ok=True, output={"x": 1, "y": 2})
    fake_tool.run = AsyncMock(return_value=same)
    case = GoldenCase(name="t", input={"a": 1}, expected_outcome="ok")
    ok, err = await _check_idempotent(fake_tool, case)
    assert ok is True


@pytest.mark.asyncio
async def test_check_idempotent_different_outputs_fail():
    fake_tool = MagicMock()
    fake_tool.metadata.idempotent = True
    fake_tool.run = AsyncMock(side_effect=[
        MagicMock(ok=True, output={"x": 1}),
        MagicMock(ok=True, output={"x": 2}),  # 不同
    ])
    case = GoldenCase(name="t", input={"a": 1}, expected_outcome="ok")
    ok, err = await _check_idempotent(fake_tool, case)
    assert ok is False
    assert "字段 x" in (err or "")


@pytest.mark.asyncio
async def test_check_idempotent_non_idempotent_skipped():
    fake_tool = MagicMock()
    fake_tool.metadata.idempotent = False
    case = GoldenCase(name="t", input={"a": 1}, expected_outcome="ok")
    ok, _ = await _check_idempotent(fake_tool, case)
    assert ok is True
    fake_tool.run.assert_not_called()


# ── _load_golden_cases ──────────────────────────────────────

def test_load_golden_cases_real_dir():
    """真实测试套件应至少加载到 calc_risk_metrics(本轮已写)。"""
    cases = _load_golden_cases("l1_tool", "calc_risk_metrics")
    assert len(cases) >= 5


def test_load_golden_cases_missing_returns_empty():
    cases = _load_golden_cases("l1_tool", "nonexistent_tool_xxx")
    assert cases == []


def test_load_golden_cases_invalid_json_returns_empty(tmp_path):
    # 写入坏 JSON
    bad = tmp_path / "l1_tool"
    bad.mkdir()
    (bad / "bad_tool.json").write_text("{not valid json")
    with patch.object(runner_mod, "GOLDEN_DIR", tmp_path):
        cases = _load_golden_cases("l1_tool", "bad_tool")
    assert cases == []


# ── run_l1_tool_suite (集成) ────────────────────────────────

@pytest.mark.asyncio
async def test_run_l1_tool_suite_filters():
    """tool_filter 限定只跑指定 tool。"""
    report = await run_l1_tool_suite(tool_filter=["calc_risk_metrics"])
    assert len(report.tool_reports) == 1
    assert report.tool_reports[0].tool_name == "calc_risk_metrics"


@pytest.mark.asyncio
async def test_run_l1_tool_suite_returns_report():
    report = await run_l1_tool_suite(tool_filter=["calc_position_size"])
    assert report.suite == "l1_tool"
    assert report.total_cases > 0
    assert report.duration_s >= 0
