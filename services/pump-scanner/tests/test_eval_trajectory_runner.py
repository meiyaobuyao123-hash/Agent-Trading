"""
L4 Trajectory Eval Runner 单元测试 — W3 D5+ autonomous-loop 续 25

跑法:python3 -m pytest tests/test_eval_trajectory_runner.py -v
真跑 fixture 见 `python3 -m agent.eval.trajectory_runner --suite=l4_trajectory`
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.eval.trajectory_runner import (  # noqa: E402
    CategoryReport,
    GoldenTrajectoryCase,
    StepResult,
    TrajectoryCaseResult,
    TrajectoryEvalReport,
    TrajectoryStep,
    _check_class_method,
    _check_route_call,
    _check_side_effect,
    _check_stage_transition,
    _check_tool_call,
    _list_categories,
    _load_golden_trajectory_cases,
    _run_step,
    _run_trajectory,
    run_l4_trajectory_suite,
)


# ── dataclasses ──────────────────────────────────────────────


def test_eval_report_zero_pass_rate():
    r = TrajectoryEvalReport(suite="l4_trajectory")
    assert r.trajectory_pass_rate == 0.0
    assert r.step_pass_rate == 0.0


def test_eval_report_pass_rate():
    r = TrajectoryEvalReport(
        suite="l4_trajectory",
        total_trajectories=20, passed_trajectories=18, failed_trajectories=2,
        total_steps=100, passed_steps=95, failed_steps=5,
    )
    assert r.trajectory_pass_rate == 0.9
    assert r.step_pass_rate == 0.95


def test_eval_report_summary_line():
    r = TrajectoryEvalReport(
        suite="l4_trajectory",
        total_trajectories=20, passed_trajectories=20,
        total_steps=88, passed_steps=88, duration_s=0.53,
    )
    line = r.summary_line()
    assert "20/20" in line
    assert "88/88" in line
    assert "100.0%" in line


def test_category_report_pass_rates():
    cr = CategoryReport(
        category="cocreation",
        total_trajectories=5, passed_trajectories=4, failed_trajectories=1,
        total_steps=30, passed_steps=28, failed_steps=2,
    )
    assert cr.trajectory_pass_rate == 0.8
    assert abs(cr.step_pass_rate - 28/30) < 1e-9


def test_trajectory_case_result_passed_when_zero_failed():
    tcr = TrajectoryCaseResult(
        case_name="t", category="x", total_steps=3,
        passed_steps=3, failed_steps=0,
    )
    assert tcr.passed is True


def test_trajectory_case_result_failed_when_any_step_fails():
    tcr = TrajectoryCaseResult(
        case_name="t", category="x", total_steps=3,
        passed_steps=2, failed_steps=1,
    )
    assert tcr.passed is False


# ── _check_class_method ──────────────────────────────────────


def test_check_class_method_real_thesis_loop():
    ok, err = _check_class_method(
        "agent.loops.thesis_loop", "ThesisLoop", "generate",
    )
    assert ok is True


def test_check_class_method_missing_method():
    ok, err = _check_class_method(
        "agent.loops.thesis_loop", "ThesisLoop", "no_such_method",
    )
    assert ok is False
    assert "缺方法" in (err or "")


def test_check_class_method_missing_class():
    ok, err = _check_class_method(
        "agent.loops.thesis_loop", "FakeClass", "x",
    )
    assert ok is False


# ── _check_stage_transition ──────────────────────────────────


def test_check_stage_transition_valid():
    ok, _ = _check_stage_transition("clarifying", "refining")
    assert ok is True


def test_check_stage_transition_terminal_saved():
    """saved 是 terminal,不能再转。"""
    ok, err = _check_stage_transition("saved", "refining")
    assert ok is False


def test_check_stage_transition_invalid_jump():
    """不允许 clarifying → confirming 直跳。"""
    ok, err = _check_stage_transition("clarifying", "confirming")
    assert ok is False


def test_check_stage_transition_invalid_from():
    ok, err = _check_stage_transition("not_a_stage", "saved")
    assert ok is False


def test_check_stage_transition_self_loop_clarifying():
    """clarifying → clarifying 是合法的(继续澄清)。"""
    ok, _ = _check_stage_transition("clarifying", "clarifying")
    assert ok is True


# ── _check_tool_call ─────────────────────────────────────────


def test_check_tool_call_real_tool():
    ok, _ = _check_tool_call("calc_risk_metrics")
    assert ok is True


def test_check_tool_call_unknown():
    ok, err = _check_tool_call("nonexistent_tool")
    assert ok is False


# ── _check_route_call ────────────────────────────────────────


def test_check_route_call_real_agent_route():
    ok, _ = _check_route_call(
        "/api/agent/cocreation/start", "POST", "api.routes_agent",
    )
    assert ok is True


def test_check_route_call_thesis_root_via_grep():
    """routes_thesis 因 PEP604 import 失败 → 走 source-grep fallback。"""
    ok, _ = _check_route_call("", "POST", "api.routes_thesis")
    assert ok is True


# ── _check_side_effect ───────────────────────────────────────


def test_check_side_effect_send_push():
    ok, _ = _check_side_effect("agent.push_service", "send_push")
    assert ok is True


def test_check_side_effect_unknown_fn():
    ok, err = _check_side_effect("agent.push_service", "no_such_fn")
    assert ok is False


# ── _run_step ────────────────────────────────────────────────


def test_run_step_class_method():
    step = TrajectoryStep(
        name="t", action_type="class_method",
        cls_module="agent.loops.thesis_loop", cls_name="ThesisLoop",
        method="generate",
    )
    sr = _run_step(step)
    assert sr.passed is True


def test_run_step_unknown_action():
    step = TrajectoryStep(name="t", action_type="bogus")
    sr = _run_step(step)
    assert sr.passed is False
    assert "未知 action_type" in (sr.failure_reason or "")


def test_run_step_missing_required_field():
    step = TrajectoryStep(name="t", action_type="tool_call")
    sr = _run_step(step)
    assert sr.passed is False
    assert "缺 tool_name" in (sr.failure_reason or "")


# ── golden loader ────────────────────────────────────────────


def test_load_golden_missing_returns_empty():
    cases = _load_golden_trajectory_cases("nonexistent")
    assert cases == []


def test_load_golden_loads_cocreation():
    cases = _load_golden_trajectory_cases("cocreation")
    assert len(cases) >= 5


def test_list_categories_has_4():
    cats = _list_categories()
    assert "cocreation" in cats
    assert "trading" in cats
    assert "reflect" in cats
    assert "thesis" in cats


# ── 端到端 ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_l4_suite_loads_all():
    report = await run_l4_trajectory_suite()
    assert report.suite == "l4_trajectory"
    assert report.total_trajectories >= 20  # ≥20 per spec


@pytest.mark.asyncio
async def test_run_l4_suite_meets_85pct_threshold():
    """对齐 17-tech-plan.md:trajectory_pass_rate ≥ 85%。"""
    report = await run_l4_trajectory_suite()
    assert report.trajectory_pass_rate >= 0.85, (
        f"trajectory pass rate {report.trajectory_pass_rate*100:.1f}% < 85%; "
        f"failed: {[(cr.category, [c.case_name for c in cr.cases if not c.passed]) for cr in report.category_reports if cr.failed_trajectories]}"
    )


@pytest.mark.asyncio
async def test_run_l4_suite_filter_one_category():
    report = await run_l4_trajectory_suite(cat_filter=["cocreation"])
    assert len(report.category_reports) == 1
    assert report.category_reports[0].category == "cocreation"


@pytest.mark.asyncio
async def test_each_category_has_at_least_5_trajectories():
    """对齐 17-tech-plan.md:4 category × ≥5 = 20。"""
    report = await run_l4_trajectory_suite()
    for cr in report.category_reports:
        assert cr.total_trajectories >= 5, (
            f"{cr.category} 仅 {cr.total_trajectories} 个 trajectory,应 ≥5"
        )
