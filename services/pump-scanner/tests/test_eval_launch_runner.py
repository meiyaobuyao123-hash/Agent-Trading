"""
Launch Criteria Eval Runner 单元测试 — W3 D5+ autonomous-loop 续 26

跑法:python3 -m pytest tests/test_eval_launch_runner.py -v
真跑 fixture 见 `python3 -m agent.eval.launch_runner --suite=launch_criteria`

注意:本测试只验框架本身。launch eval 全过 100% 是 GA 时的 milestone,
今日多个 criterion 是 blocked(legal sign-off / KMS / Beta NPS 等),
这是 punch list,不是 framework bug。
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.eval.launch_runner import (  # noqa: E402
    CategoryReport,
    CHECK_FN_REGISTRY,
    CriterionItem,
    CriterionResult,
    LaunchEvalReport,
    STATUS_FAIL,
    STATUS_PASS,
    VALID_STATUSES,
    _check_attr_exists,
    _check_file_exists,
    _check_input_filter_classes,
    _check_module_importable,
    _check_safety_engine_loaded,
    _check_skill_count,
    _check_tool_count,
    _list_categories,
    _load_golden_criteria,
    _run_one_criterion,
    run_launch_criteria_suite,
)


# ── Status enum ──────────────────────────────────────────────


def test_status_enums_partition():
    """STATUS_PASS / STATUS_FAIL 不重叠且全是 valid。"""
    assert STATUS_PASS.isdisjoint(STATUS_FAIL)
    assert STATUS_PASS | STATUS_FAIL == VALID_STATUSES


def test_status_pass_includes_three():
    assert "automated_pass" in STATUS_PASS
    assert "signed_off" in STATUS_PASS
    assert "not_applicable" in STATUS_PASS


def test_status_fail_includes_three():
    assert "automated_fail" in STATUS_FAIL
    assert "pending_signoff" in STATUS_FAIL
    assert "blocked" in STATUS_FAIL


# ── Report dataclasses ───────────────────────────────────────


def test_launch_report_zero_pass_rate():
    r = LaunchEvalReport(suite="launch_criteria")
    assert r.pass_rate == 0.0
    assert r.all_categories_100 is True  # 空 categories 默认 True


def test_launch_report_pass_rate():
    r = LaunchEvalReport(suite="launch_criteria", total=62, passed=45, failed=17)
    assert abs(r.pass_rate - 45/62) < 1e-9


def test_launch_report_all_categories_100_false_when_any_failed():
    r = LaunchEvalReport(suite="launch_criteria")
    r.category_reports = [
        CategoryReport(category="tech", total=12, passed=12, failed=0),
        CategoryReport(category="legal", total=12, passed=0, failed=12),
    ]
    assert r.all_categories_100 is False


def test_launch_report_all_categories_100_true_when_all_pass():
    r = LaunchEvalReport(suite="launch_criteria")
    r.category_reports = [
        CategoryReport(category="tech", total=12, passed=12, failed=0),
    ]
    assert r.all_categories_100 is True


def test_launch_report_summary_line():
    r = LaunchEvalReport(suite="launch_criteria", total=62, passed=45,
                          failed=17, duration_s=0.5)
    line = r.summary_line()
    assert "45/62" in line
    assert "72.6%" in line


def test_category_report_pass_rate():
    cr = CategoryReport(category="tech", total=12, passed=12, failed=0)
    assert cr.pass_rate == 1.0


# ── automated check 函数 ────────────────────────────────────


def test_check_file_exists_real():
    ok, _ = _check_file_exists({"path": "services/pump-scanner/agent/input_filter.py"})
    assert ok is True


def test_check_file_exists_missing():
    ok, err = _check_file_exists({"path": "services/pump-scanner/no/such/file.py"})
    assert ok is False
    assert "not found" in (err or "")


def test_check_module_importable_real():
    ok, _ = _check_module_importable({"module": "agent.input_filter"})
    assert ok is True


def test_check_module_importable_missing():
    ok, err = _check_module_importable({"module": "no.such.module.xyz"})
    assert ok is False


def test_check_attr_exists_real():
    ok, _ = _check_attr_exists({
        "module": "agent.input_filter", "attr": "filter_input",
    })
    assert ok is True


def test_check_attr_exists_missing():
    ok, err = _check_attr_exists({
        "module": "agent.input_filter", "attr": "no_such_attr",
    })
    assert ok is False


def test_check_tool_count_real():
    ok, _ = _check_tool_count({"min": 13})
    assert ok is True


def test_check_skill_count_real():
    ok, _ = _check_skill_count({"min": 7})
    assert ok is True


def test_check_safety_engine_loaded_real():
    """30 HR + 13 CB + 5 C 全在。"""
    ok, err = _check_safety_engine_loaded({})
    assert ok is True, f"safety_engine 应满足 30/13/5: {err}"


def test_check_input_filter_classes_real():
    ok, _ = _check_input_filter_classes({})
    assert ok is True


# ── _run_one_criterion ───────────────────────────────────────


def test_run_one_automated_pass():
    item = CriterionItem(
        name="t", category="tech", description="x", check_type="automated",
        check_fn="file_exists",
        check_args={"path": "services/pump-scanner/agent/input_filter.py"},
    )
    res = _run_one_criterion(item)
    assert res.status == "automated_pass"


def test_run_one_automated_fail():
    item = CriterionItem(
        name="t", category="tech", description="x", check_type="automated",
        check_fn="file_exists", check_args={"path": "no/such.py"},
    )
    res = _run_one_criterion(item)
    assert res.status == "automated_fail"


def test_run_one_manual_pending():
    item = CriterionItem(
        name="t", category="legal", description="x", check_type="manual",
    )
    res = _run_one_criterion(item)
    assert res.status == "pending_signoff"


def test_run_one_manual_signed_off():
    item = CriterionItem(
        name="t", category="legal", description="x", check_type="manual",
        signed_off=True,
    )
    res = _run_one_criterion(item)
    assert res.status == "signed_off"


def test_run_one_blocked():
    item = CriterionItem(
        name="t", category="safety", description="x", check_type="manual",
        blocking_reason="留 W7-W12",
    )
    res = _run_one_criterion(item)
    assert res.status == "blocked"
    assert "W7-W12" in (res.failure_reason or "")


def test_run_one_not_applicable():
    item = CriterionItem(
        name="t", category="legal", description="x", check_type="manual",
        not_applicable_reason="Beta 不需要",
    )
    res = _run_one_criterion(item)
    assert res.status == "not_applicable"


def test_run_one_unknown_check_fn():
    item = CriterionItem(
        name="t", category="tech", description="x", check_type="automated",
        check_fn="no_such_check",
    )
    res = _run_one_criterion(item)
    assert res.status == "automated_fail"


# ── golden loader ────────────────────────────────────────────


def test_load_golden_missing_returns_empty():
    cases = _load_golden_criteria("nonexistent")
    assert cases == []


def test_load_golden_loads_tech():
    items = _load_golden_criteria("tech")
    assert len(items) >= 12


def test_list_categories_has_6():
    cats = _list_categories()
    expected = {"tech", "product", "safety", "legal", "cost_ops", "hitl"}
    assert expected.issubset(set(cats))


# ── 端到端 ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_launch_suite_loads_62():
    """对齐 17-tech-plan.md:62 项 Launch Criteria。"""
    report = await run_launch_criteria_suite()
    assert report.total == 62, f"应有 62 criteria,实际 {report.total}"


@pytest.mark.asyncio
async def test_run_launch_suite_tech_all_pass():
    """Tech 12 项都是 automated 应当全过(本仓库当前状态)。"""
    report = await run_launch_criteria_suite(cat_filter=["tech"])
    cr = report.category_reports[0]
    failures = [item.name for item in cr.items if item.status not in STATUS_PASS]
    assert not failures, f"Tech 应全过: 失败 {failures}"


@pytest.mark.asyncio
async def test_run_launch_suite_legal_all_pending():
    """Legal 12 项都是 manual blocked(等签字) — 期望 12 个失败。"""
    report = await run_launch_criteria_suite(cat_filter=["legal"])
    cr = report.category_reports[0]
    assert cr.total == 12
    assert cr.failed == 12  # 全等待签字
    assert cr.passed == 0


@pytest.mark.asyncio
async def test_run_launch_suite_filter_one_cat():
    report = await run_launch_criteria_suite(cat_filter=["hitl"])
    assert len(report.category_reports) == 1
    assert report.category_reports[0].category == "hitl"


@pytest.mark.asyncio
async def test_run_launch_suite_categories_breakdown():
    """6 category 全在 + per-category total 对齐 spec。"""
    report = await run_launch_criteria_suite()
    counts = {cr.category: cr.total for cr in report.category_reports}
    assert counts.get("tech") == 12
    assert counts.get("product") == 7
    assert counts.get("safety") == 14
    assert counts.get("legal") == 12
    assert counts.get("cost_ops") == 12
    assert counts.get("hitl") == 5


# ── CHECK_FN_REGISTRY ────────────────────────────────────────


def test_check_fn_registry_has_all_expected():
    expected = {
        "file_exists", "module_importable", "attr_exists", "tool_count",
        "safety_engine_loaded", "skill_count", "prompt_count",
        "main_cron_id", "route_registered",
        "safety_ae_severity", "l4_trajectory_threshold",
        "input_filter_classes",
    }
    assert expected.issubset(set(CHECK_FN_REGISTRY.keys()))
