"""
L3 Chain Eval Runner 单元测试 — W3 D5+ autonomous-loop 续 22

跑法:python3 -m pytest tests/test_eval_chain_runner.py -v
真跑 fixture 见 `python3 -m agent.eval.chain_runner --suite=l3_chain`
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.eval.chain_runner import (  # noqa: E402
    CHAIN_REGISTRY,
    ChainCaseResult,
    ChainEvalReport,
    ChainReport,
    GoldenChainCase,
    _check_class_loadable,
    _check_cron_registered,
    _check_entry_method,
    _check_route_registered,
    _check_tools_wired,
    _load_golden_chain_cases,
    _run_one_case,
    run_l3_chain_suite,
)


# ── Report dataclasses ───────────────────────────────────────


def test_chain_eval_report_zero_pass_rate():
    r = ChainEvalReport(suite="l3_chain")
    assert r.pass_rate == 0.0


def test_chain_eval_report_pass_rate():
    r = ChainEvalReport(suite="l3_chain", total_cases=10,
                         total_passed=8, total_failed=2)
    assert r.pass_rate == 0.8


def test_chain_eval_report_summary_line():
    r = ChainEvalReport(suite="l3_chain", total_cases=46,
                         total_passed=46, total_failed=0, duration_s=0.52)
    line = r.summary_line()
    assert "46/46" in line
    assert "100.0%" in line


def test_chain_report_pass_rate():
    cr = ChainReport(chain_id="thesis", total=10, passed=9, failed=1)
    assert cr.pass_rate == 0.9


# ── _check_class_loadable ────────────────────────────────────


def test_check_class_loadable_unknown_chain():
    ok, err = _check_class_loadable("nonexistent_chain")
    assert ok is False
    assert "未在 CHAIN_REGISTRY" in (err or "")


def test_check_class_loadable_real_thesis():
    ok, err = _check_class_loadable("thesis")
    assert ok is True
    assert err is None


def test_check_class_loadable_real_reflect():
    ok, err = _check_class_loadable("reflect")
    assert ok is True


# ── _check_entry_method ──────────────────────────────────────


def test_check_entry_method_real_thesis_generate():
    ok, err = _check_entry_method("thesis", "generate")
    assert ok is True


def test_check_entry_method_real_reflect_run_cycle():
    ok, err = _check_entry_method("reflect", "run_cycle")
    assert ok is True


def test_check_entry_method_missing():
    ok, err = _check_entry_method("thesis", "no_such_method")
    assert ok is False
    assert "缺方法" in (err or "")


def test_check_entry_method_unknown_chain():
    ok, err = _check_entry_method("nonexistent", "process")
    assert ok is False


# ── _check_tools_wired ───────────────────────────────────────


def test_check_tools_wired_all_known():
    ok, err = _check_tools_wired(["calc_risk_metrics", "recall_memory"])
    assert ok is True


def test_check_tools_wired_unknown_fails():
    ok, err = _check_tools_wired(["calc_risk_metrics", "fake_tool_xyz"])
    assert ok is False
    assert "未注册工具" in (err or "")


# ── _check_route_registered ──────────────────────────────────


def test_check_route_registered_real_route():
    ok, err = _check_route_registered(
        "/api/agent/notify/trigger", "POST", "api.routes_agent",
    )
    assert ok is True


def test_check_route_registered_unknown_route():
    ok, err = _check_route_registered(
        "/api/agent/totally/fake/path", "POST", "api.routes_agent",
    )
    assert ok is False
    assert "未注册" in (err or "") or "未找到" in (err or "")


def test_check_route_registered_source_grep_fallback_for_thesis():
    """Py3.9 thesis route import 失败 → 走 source-grep 降级。"""
    ok, err = _check_route_registered(
        "", "POST", "api.routes_thesis",
    )
    # 源码中确实有 @router.post("")
    assert ok is True


# ── _check_cron_registered ───────────────────────────────────


def test_check_cron_registered_real_reflect_daily():
    ok, err = _check_cron_registered("reflect_daily")
    assert ok is True


def test_check_cron_registered_real_memory_wal_flush():
    ok, err = _check_cron_registered("memory_wal_flush")
    assert ok is True


def test_check_cron_registered_unknown_job():
    ok, err = _check_cron_registered("totally_fake_job_id_xyz")
    assert ok is False
    assert "未注册" in (err or "")


# ── _run_one_case ────────────────────────────────────────────


def test_run_one_case_class_loadable():
    case = GoldenChainCase(
        name="cl", chain_id="thesis", expected_outcome="class_loadable",
    )
    cr = _run_one_case(case)
    assert cr.passed is True


def test_run_one_case_unknown_outcome():
    case = GoldenChainCase(
        name="weird", chain_id="thesis", expected_outcome="bogus",
    )
    cr = _run_one_case(case)
    assert cr.passed is False
    assert cr.actual_outcome == "unknown_outcome"


def test_run_one_case_entry_method_no_method_param():
    case = GoldenChainCase(
        name="x", chain_id="thesis", expected_outcome="entry_method_present",
        entry_method=None,
    )
    cr = _run_one_case(case)
    assert cr.passed is False


def test_run_one_case_route_path_empty_string_allowed():
    """route_path='' 是合法值(routes_thesis 主入口),不应触发"未指定" error。"""
    case = GoldenChainCase(
        name="x", chain_id="thesis", expected_outcome="route_registered",
        route_path="", route_method="POST", route_module="api.routes_thesis",
    )
    cr = _run_one_case(case)
    assert cr.passed is True


# ── golden loader ────────────────────────────────────────────


def test_load_golden_chain_missing_returns_empty():
    cases = _load_golden_chain_cases("nonexistent_chain")
    assert cases == []


def test_load_golden_chain_loads_real_thesis():
    cases = _load_golden_chain_cases("thesis")
    assert len(cases) >= 5
    assert any(c.name == "class_loadable" for c in cases)


# ── 端到端 ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_l3_chain_suite_all_pass():
    report = await run_l3_chain_suite()
    assert report.suite == "l3_chain"
    assert report.total_failed == 0, (
        f"L3 Chain 失败: "
        f"{[(cr.chain_id, [c.case_name for c in cr.cases if not c.passed]) for cr in report.chain_reports if cr.failed]}"
    )
    assert len(report.chain_reports) >= 4


@pytest.mark.asyncio
async def test_run_l3_chain_suite_with_filter():
    report = await run_l3_chain_suite(chain_filter=["thesis"])
    assert len(report.chain_reports) == 1
    assert report.chain_reports[0].chain_id == "thesis"


# ── CHAIN_REGISTRY structure ─────────────────────────────────


def test_chain_registry_has_4_required_chains():
    """对齐 17-tech-plan.md L3 Agentic chain 4 chain。"""
    required = {"thesis", "notify", "reflect", "cocreation"}
    assert required.issubset(set(CHAIN_REGISTRY.keys()))


def test_chain_registry_entries_have_module_class():
    for chain_id, info in CHAIN_REGISTRY.items():
        assert "module" in info, f"{chain_id} 缺 module"
        assert "class" in info, f"{chain_id} 缺 class"
        assert info["module"].startswith("agent.loops."), f"{chain_id} module 不在 agent.loops"
