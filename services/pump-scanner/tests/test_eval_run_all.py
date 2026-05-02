"""
Run All Eval 单元测试 — W3 D5+ autonomous-loop 续 31

跑法:python3 -m pytest tests/test_eval_run_all.py -v
真跑见 `python3 -m agent.eval.run_all` / `--json` / `--skip launch_criteria`
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.eval.run_all import (  # noqa: E402
    RunAllReport,
    SUITES,
    SuiteResult,
    run_all,
)


# ── SUITES 配置 ──────────────────────────────────────────────


def test_suites_has_9():
    """对齐 docs/agent-pm/eval-summary.md:9 个 eval suite。"""
    assert len(SUITES) == 9


def test_suites_names():
    expected = {
        "l1_tool", "l2_skill", "l1_prompt", "l3_chain", "safety_ae",
        "l4_trajectory", "launch_criteria", "quality_rubric", "judge_calibration",
    }
    assert {s["name"] for s in SUITES} == expected


def test_suites_each_has_module_fn_hard_gate():
    for s in SUITES:
        assert "name" in s
        assert "module" in s
        assert "fn" in s
        assert "hard_gate" in s
        assert isinstance(s["hard_gate"], bool)


def test_suites_hard_gate_distribution():
    """L1 / L2 / L3 / L4 / Safety / Judge = hard;Launch / Rubric = soft。"""
    by_name = {s["name"]: s["hard_gate"] for s in SUITES}
    assert by_name["l1_tool"] is True
    assert by_name["l2_skill"] is True
    assert by_name["l1_prompt"] is True
    assert by_name["l3_chain"] is True
    assert by_name["safety_ae"] is True
    assert by_name["l4_trajectory"] is True
    assert by_name["judge_calibration"] is True
    assert by_name["launch_criteria"] is False  # milestone-gated
    assert by_name["quality_rubric"] is False   # heuristic baseline


# ── SuiteResult.hard_gate_passed 路径 ───────────────────────


def test_suite_result_hard_gate_l1_tool_strict_100():
    s = SuiteResult(
        name="l1_tool", total=140, passed=140, failed=0,
        pass_rate=1.0, hard_gate=True, duration_s=0.5,
    )
    assert s.hard_gate_passed is True


def test_suite_result_hard_gate_l1_tool_99_fails():
    s = SuiteResult(
        name="l1_tool", total=140, passed=139, failed=1,
        pass_rate=0.993, hard_gate=True, duration_s=0.5,
    )
    assert s.hard_gate_passed is False


def test_suite_result_safety_ae_uses_severity_flag():
    """safety_ae 不看 pass_rate,看 all_severities_meet_threshold。"""
    s = SuiteResult(
        name="safety_ae", total=132, passed=130, failed=2,
        pass_rate=0.985, hard_gate=True, duration_s=0.01,
        extra={"all_severities_meet_threshold": True},
    )
    assert s.hard_gate_passed is True


def test_suite_result_safety_ae_severity_fail():
    s = SuiteResult(
        name="safety_ae", total=132, passed=132, failed=0,
        pass_rate=1.0, hard_gate=True, duration_s=0.01,
        extra={"all_severities_meet_threshold": False},
    )
    assert s.hard_gate_passed is False


def test_suite_result_l4_trajectory_85pct():
    """trajectory 门槛 ≥ 85%。"""
    s = SuiteResult(
        name="l4_trajectory", total=20, passed=18, failed=2,
        pass_rate=0.9, hard_gate=True, duration_s=0.01,
    )
    assert s.hard_gate_passed is True


def test_suite_result_l4_trajectory_84pct_fails():
    s = SuiteResult(
        name="l4_trajectory", total=20, passed=16, failed=4,
        pass_rate=0.8, hard_gate=True, duration_s=0.01,
    )
    assert s.hard_gate_passed is False


def test_suite_result_judge_uses_passes_flag():
    s = SuiteResult(
        name="judge_calibration", total=10, passed=10, failed=0,
        pass_rate=1.0, hard_gate=True, duration_s=0.01,
        extra={"passes": True},
    )
    assert s.hard_gate_passed is True


def test_suite_result_judge_passes_false_fails():
    s = SuiteResult(
        name="judge_calibration", total=10, passed=10, failed=0,
        pass_rate=1.0, hard_gate=True, duration_s=0.01,
        extra={"passes": False},
    )
    assert s.hard_gate_passed is False


def test_suite_result_soft_gate_always_passes():
    """hard_gate=False(launch / rubric)即便低分也算 hard_gate_passed。"""
    s = SuiteResult(
        name="launch_criteria", total=62, passed=45, failed=17,
        pass_rate=0.726, hard_gate=False, duration_s=0.05,
    )
    assert s.hard_gate_passed is True

    s2 = SuiteResult(
        name="quality_rubric", total=40, passed=29, failed=11,
        pass_rate=0.725, hard_gate=False, duration_s=0.01,
    )
    assert s2.hard_gate_passed is True


# ── RunAllReport 聚合 ───────────────────────────────────────


def test_run_all_report_all_passed_true_when_all_hard_passes():
    r = RunAllReport()
    r.suite_results = [
        SuiteResult(name="l1_tool", total=140, passed=140, failed=0,
                    pass_rate=1.0, hard_gate=True, duration_s=0.5),
        SuiteResult(name="launch_criteria", total=62, passed=45, failed=17,
                    pass_rate=0.726, hard_gate=False, duration_s=0.05),
    ]
    assert r.all_hard_gates_passed is True


def test_run_all_report_fails_when_one_hard_fails():
    r = RunAllReport()
    r.suite_results = [
        SuiteResult(name="l1_tool", total=140, passed=139, failed=1,
                    pass_rate=0.993, hard_gate=True, duration_s=0.5),
    ]
    assert r.all_hard_gates_passed is False


def test_run_all_report_total_cases():
    r = RunAllReport()
    r.suite_results = [
        SuiteResult(name="a", total=140, passed=140, failed=0,
                    pass_rate=1.0, hard_gate=True, duration_s=0.5),
        SuiteResult(name="b", total=44, passed=44, failed=0,
                    pass_rate=1.0, hard_gate=True, duration_s=0.1),
    ]
    assert r.total_cases == 184
    assert r.total_passed == 184


def test_run_all_report_to_json():
    r = RunAllReport(total_duration_s=1.0)
    r.suite_results = [
        SuiteResult(name="l1_tool", total=140, passed=140, failed=0,
                    pass_rate=1.0, hard_gate=True, duration_s=0.5,
                    extra={"foo": "bar"}),
    ]
    j = r.to_json()
    assert j["all_hard_gates_passed"] is True
    assert j["total_cases"] == 140
    assert j["total_passed"] == 140
    assert j["total_duration_s"] == 1.0
    assert len(j["suites"]) == 1
    assert j["suites"][0]["name"] == "l1_tool"
    assert j["suites"][0]["extra"]["foo"] == "bar"


# ── 端到端 run_all ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_all_real_passes_all_hard_gates():
    """跑真 9 suite,所有 hard gate 应通过。"""
    report = await run_all()
    assert len(report.suite_results) == 9
    failed = [s.name for s in report.suite_results if not s.hard_gate_passed]
    assert not failed, f"hard gate 失败: {failed}"


@pytest.mark.asyncio
async def test_run_all_skip_launch_works():
    """--skip launch_criteria 应跳过该 suite。"""
    report = await run_all(skip=["launch_criteria"])
    names = {s.name for s in report.suite_results}
    assert "launch_criteria" not in names
    assert len(report.suite_results) == 8


@pytest.mark.asyncio
async def test_run_all_returns_safety_severity_breakdown():
    report = await run_all()
    safety = next((s for s in report.suite_results if s.name == "safety_ae"), None)
    assert safety is not None
    assert "all_severities_meet_threshold" in safety.extra
    assert safety.extra["all_severities_meet_threshold"] is True
    assert "sev_breakdown" in safety.extra
    assert "SEV-0" in safety.extra["sev_breakdown"]


@pytest.mark.asyncio
async def test_run_all_total_below_605_above_500():
    """快速 sanity:total cases 在合理范围(避免回归丢 case)。"""
    report = await run_all()
    assert 500 <= report.total_cases <= 700, (
        f"total_cases {report.total_cases} 异常,检查是否丢 fixture"
    )


@pytest.mark.asyncio
async def test_run_all_quick_under_5s():
    """全部 9 suite 跑 < 5 秒(本机)。"""
    report = await run_all()
    assert report.total_duration_s < 5.0, (
        f"全跑耗时 {report.total_duration_s:.2f}s > 5s,可能某 suite 卡住"
    )
