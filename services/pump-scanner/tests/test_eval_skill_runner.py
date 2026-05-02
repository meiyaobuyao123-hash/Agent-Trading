"""
L2 Skill Eval Runner 单元测试 — W3 D5+ autonomous-loop 续 19

跑法:python3 -m pytest tests/test_eval_skill_runner.py -v

注意:这测的是 skill_runner 框架本身,真跑 fixture 见
   `python3 -m agent.eval.skill_runner --suite=l2_skill`
"""
from __future__ import annotations
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.eval.skill_runner import (  # noqa: E402
    GoldenSkillCase,
    SkillCaseResult,
    SkillEvalReport,
    SkillReport,
    _check_full_content,
    _check_tools_known,
    _load_golden_skill_cases,
    _run_one_case,
    _validate_skill_metadata,
    run_l2_skill_suite,
)


# ── SkillEvalReport / SkillReport ────────────────────────────


def test_skill_eval_report_pass_rate_zero_when_no_cases():
    r = SkillEvalReport(suite="l2_skill")
    assert r.pass_rate == 0.0


def test_skill_eval_report_pass_rate():
    r = SkillEvalReport(suite="l2_skill", total_cases=10,
                         total_passed=8, total_failed=2)
    assert r.pass_rate == 0.8


def test_skill_eval_report_summary_line():
    r = SkillEvalReport(suite="l2_skill", total_cases=7, total_passed=7,
                         total_failed=0, duration_s=0.05)
    line = r.summary_line()
    assert "7/7" in line
    assert "100.0%" in line


def test_skill_report_pass_rate():
    sr = SkillReport(skill_id="S08", skill_name="thesis-writer",
                     total=4, passed=3, failed=1)
    assert sr.pass_rate == 0.75


# ── _validate_skill_metadata ─────────────────────────────────


def _mk_meta(**overrides):
    """构造合法的 SkillMeta-like mock。"""
    m = MagicMock()
    m.skill_id = overrides.get("skill_id", "S08")
    m.name = overrides.get("name", "thesis-writer")
    m.description = overrides.get(
        "description",
        "把 3 路分析(技术/情绪/链上)合成 thesis JSON",
    )
    m.tools_required = overrides.get("tools_required", ["calc_risk_metrics"])
    m.sub_skills_allowed = overrides.get("sub_skills_allowed", ["S01"])
    m.model = overrides.get("model", "claude-sonnet-4-6")
    m.version = overrides.get("version", "v1.0")
    return m


def test_validate_metadata_ok():
    meta = _mk_meta()
    ok, issues = _validate_skill_metadata("S08", meta)
    assert ok is True
    assert issues == []


def test_validate_metadata_none_meta_invalid():
    ok, issues = _validate_skill_metadata("S99", None)
    assert ok is False
    assert any("未在 SkillLoader 注册" in i for i in issues)


def test_validate_metadata_skill_id_mismatch():
    meta = _mk_meta(skill_id="S08")
    ok, issues = _validate_skill_metadata("S07", meta)
    assert ok is False
    assert any("不匹配" in i for i in issues)


def test_validate_metadata_description_too_short():
    meta = _mk_meta(description="短描述")
    ok, issues = _validate_skill_metadata("S08", meta)
    assert ok is False
    assert any("description 太短" in i for i in issues)


def test_validate_metadata_tools_required_empty():
    meta = _mk_meta(tools_required=[])
    ok, issues = _validate_skill_metadata("S08", meta)
    assert ok is False
    assert any("tools_required 为空" in i for i in issues)


def test_validate_metadata_model_not_claude():
    meta = _mk_meta(model="gpt-4")
    ok, issues = _validate_skill_metadata("S08", meta)
    assert ok is False
    assert any("model 不合法" in i for i in issues)


def test_validate_metadata_version_missing():
    meta = _mk_meta(version="")
    ok, issues = _validate_skill_metadata("S08", meta)
    assert ok is False
    assert any("version 缺失" in i for i in issues)


# ── _check_tools_known ───────────────────────────────────────


def test_check_tools_known_all_in_registry():
    meta = _mk_meta(tools_required=["calc_risk_metrics", "recall_memory"])
    ok, err = _check_tools_known(meta)
    assert ok is True
    assert err is None


def test_check_tools_known_unknown_tool():
    meta = _mk_meta(tools_required=["nonexistent_tool"])
    ok, err = _check_tools_known(meta)
    assert ok is False
    assert "未注册工具" in err


# ── _check_full_content ──────────────────────────────────────


def test_check_full_content_returns_none_fail():
    loader = MagicMock()
    loader.load_full = MagicMock(return_value=None)
    ok, err = _check_full_content(loader, "S08")
    assert ok is False
    assert "load_full 返 None" in err


def test_check_full_content_too_short_fail():
    loader = MagicMock()
    loader.load_full = MagicMock(return_value="too short")
    ok, err = _check_full_content(loader, "S08")
    assert ok is False
    assert "body 太短" in err


def test_check_full_content_ok():
    loader = MagicMock()
    loader.load_full = MagicMock(return_value="x" * 500)
    ok, err = _check_full_content(loader, "S08")
    assert ok is True
    assert err is None


# ── _run_one_case ────────────────────────────────────────────


def test_run_one_case_metadata_ok_passes():
    meta = _mk_meta()
    loader = MagicMock()
    case = GoldenSkillCase(
        name="meta_ok", skill_id="S08",
        expected_outcome="metadata_ok",
    )
    cr = _run_one_case(loader, meta, case)
    assert cr.passed is True
    assert cr.actual_outcome == "metadata_ok"


def test_run_one_case_metadata_invalid_fails():
    meta = _mk_meta(description="x")
    loader = MagicMock()
    case = GoldenSkillCase(
        name="meta_bad", skill_id="S08",
        expected_outcome="metadata_ok",
    )
    cr = _run_one_case(loader, meta, case)
    assert cr.passed is False
    assert cr.actual_outcome == "metadata_invalid"


def test_run_one_case_expect_fields_subset_list():
    meta = _mk_meta(tools_required=["a", "b", "c"])
    loader = MagicMock()
    case = GoldenSkillCase(
        name="ef", skill_id="S08",
        expected_outcome="expect_fields",
        expect_fields={"tools_required": ["a", "b"]},
    )
    cr = _run_one_case(loader, meta, case)
    assert cr.passed is True


def test_run_one_case_expect_fields_subset_missing_fails():
    meta = _mk_meta(tools_required=["a", "b"])
    loader = MagicMock()
    case = GoldenSkillCase(
        name="ef_miss", skill_id="S08",
        expected_outcome="expect_fields",
        expect_fields={"tools_required": ["a", "z"]},
    )
    cr = _run_one_case(loader, meta, case)
    assert cr.passed is False
    assert "missing" in (cr.failure_reason or "")


def test_run_one_case_expect_fields_scalar_match():
    meta = _mk_meta(model="claude-sonnet-4-6")
    loader = MagicMock()
    case = GoldenSkillCase(
        name="ef_model", skill_id="S08",
        expected_outcome="expect_fields",
        expect_fields={"model": "claude-sonnet-4-6"},
    )
    cr = _run_one_case(loader, meta, case)
    assert cr.passed is True


def test_run_one_case_unknown_outcome_fails():
    meta = _mk_meta()
    loader = MagicMock()
    case = GoldenSkillCase(
        name="weird", skill_id="S08",
        expected_outcome="some_unknown_outcome",
    )
    cr = _run_one_case(loader, meta, case)
    assert cr.passed is False
    assert cr.actual_outcome == "unknown_outcome"


# ── _load_golden_skill_cases ─────────────────────────────────


def test_load_golden_skill_cases_missing_file_returns_empty():
    cases = _load_golden_skill_cases("S99_nonexistent")
    assert cases == []


def test_load_golden_skill_cases_loads_real_S08():
    cases = _load_golden_skill_cases("S08")
    assert len(cases) >= 5
    names = {c.name for c in cases}
    assert "metadata_ok" in names


# ── 端到端 run_l2_skill_suite ────────────────────────────────


@pytest.mark.asyncio
async def test_run_l2_skill_suite_all_pass():
    """跑真实 L2 Skill suite,期望 7 个 Skill 全过。"""
    report = await run_l2_skill_suite()
    assert report.suite == "l2_skill"
    assert report.total_failed == 0, (
        f"L2 Skill 失败: {[(sr.skill_id, [c.case_name for c in sr.cases if not c.passed]) for sr in report.skill_reports if sr.failed]}"
    )
    assert len(report.skill_reports) >= 7
    for sr in report.skill_reports:
        assert sr.metadata_ok, f"{sr.skill_id} metadata 问题: {sr.metadata_issues}"


@pytest.mark.asyncio
async def test_run_l2_skill_suite_with_filter():
    """只跑 S01,期望只返 1 个 SkillReport。"""
    report = await run_l2_skill_suite(skill_filter=["S01"])
    assert len(report.skill_reports) == 1
    assert report.skill_reports[0].skill_id == "S01"
