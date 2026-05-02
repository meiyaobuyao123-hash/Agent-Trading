"""
Quality Rubric Eval Runner 单元测试 — W3 D5+ autonomous-loop 续 27

跑法:python3 -m pytest tests/test_eval_rubric_runner.py -v
真跑 fixture 见 `python3 -m agent.eval.rubric_runner --suite=quality_rubric`
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.eval.rubric_runner import (  # noqa: E402
    CategoryReport,
    DEFAULT_WEIGHTS,
    DIMENSIONS,
    GoldenRubricCase,
    OVERALL_PASS_THRESHOLD,
    RubricEvalReport,
    RubricResult,
    SCORERS,
    _check_veto_rules,
    _list_categories,
    _load_golden_rubric_cases,
    _run_one_case,
    _score_actionability,
    _score_calibration,
    _score_format,
    _score_length,
    _score_relevance,
    _score_risk,
    _score_safety,
    _score_structure,
    run_quality_rubric_suite,
)


# ── DIMENSIONS / weights ─────────────────────────────────────


def test_dimensions_has_10():
    assert len(DIMENSIONS) == 10


def test_dimensions_split_5_product_5_tech():
    """5 product + 5 tech 维度。"""
    product = ("relevance", "reasoning", "actionability", "risk", "calibration")
    tech = ("format", "structure", "length", "disclaimer", "safety")
    assert all(p in DIMENSIONS for p in product)
    assert all(t in DIMENSIONS for t in tech)


def test_default_weights_sum_to_dim_count():
    """默认全 1.0 weight。"""
    assert all(w == 1.0 for w in DEFAULT_WEIGHTS.values())


def test_scorers_registered_for_all_dims():
    for d in DIMENSIONS:
        assert d in SCORERS


# ── individual scorer 行为 ──────────────────────────────────


def _mk_case(**kw):
    return GoldenRubricCase(
        name=kw.get("name", "t"),
        category=kw.get("category", "test"),
        output_text=kw.get("output_text", ""),
        topic_keywords=kw.get("topic_keywords", []),
        expected_format=kw.get("expected_format", "free"),
        is_thesis=kw.get("is_thesis", False),
        min_len=kw.get("min_len", 30),
        max_len=kw.get("max_len", 2000),
    )


def test_score_relevance_full_match():
    case = _mk_case(topic_keywords=["TRUMP", "SOL"])
    s, _ = _score_relevance("TRUMP on SOL chain", case)
    assert s >= 9


def test_score_relevance_no_keywords_default():
    case = _mk_case(topic_keywords=[])
    s, _ = _score_relevance("anything", case)
    assert s == 7.0


def test_score_actionability_with_action():
    case = _mk_case()
    s, _ = _score_actionability("建议买入 $100 止损 -10%", case)
    assert s > 0


def test_score_actionability_no_action_returns_0_veto():
    case = _mk_case()
    s, _ = _score_actionability("数据如下:RSI 35,MACD -0.05", case)
    assert s == 0.0


def test_score_actionability_thesis_uses_direction():
    case = _mk_case(is_thesis=True, expected_format="json_thesis")
    s, _ = _score_actionability(
        '{"direction": "bullish", "conviction": 0.7, "risks": ["a","b"]}', case,
    )
    assert s == 10.0


def test_score_actionability_thesis_unknown_direction_veto():
    case = _mk_case(is_thesis=True)
    s, _ = _score_actionability('{"direction": "unknown"}', case)
    assert s == 0.0


def test_score_risk_thesis_2_risks_full():
    case = _mk_case(is_thesis=True)
    s, _ = _score_risk(
        '{"direction":"hold","risks":["a","b"],"evidence":[{"layer":"x"}]}', case,
    )
    assert s == 10.0


def test_score_risk_thesis_zero_risks_veto():
    case = _mk_case(is_thesis=True)
    s, _ = _score_risk('{"risks": []}', case)
    assert s == 0.0


def test_score_risk_thesis_one_risk_partial():
    case = _mk_case(is_thesis=True)
    s, _ = _score_risk('{"risks": ["only one"]}', case)
    assert s == 5.0


def test_score_risk_free_text_no_risk_veto():
    case = _mk_case()
    s, _ = _score_risk("RSI 35 数据", case)
    assert s == 0.0


def test_score_risk_free_text_disclaimer_counts():
    case = _mk_case()
    s, _ = _score_risk("DYOR,请自行判断,不构成投资建议", case)
    assert s > 0


def test_score_calibration_with_pct():
    case = _mk_case()
    s, _ = _score_calibration("信心 65%", case)
    assert s > 5


def test_score_calibration_no_conviction_default():
    case = _mk_case()
    s, _ = _score_calibration("一些文字", case)
    assert s == 3.0


def test_score_format_json_valid():
    case = _mk_case(expected_format="json_thesis")
    s, _ = _score_format('{"a": 1}', case)
    assert s == 10.0


def test_score_format_json_invalid():
    case = _mk_case(expected_format="json_thesis")
    s, _ = _score_format("not json", case)
    assert s < 5


def test_score_structure_thesis_all_keys():
    case = _mk_case(is_thesis=True)
    s, _ = _score_structure(
        '{"direction":"x","risks":["a"],"evidence":[]}', case,
    )
    assert s >= 9


def test_score_structure_thesis_partial_keys():
    case = _mk_case(is_thesis=True)
    s, _ = _score_structure('{"direction": "x"}', case)
    assert 3 < s < 4  # 3.3


def test_score_length_too_short_zero():
    case = _mk_case(min_len=100)
    s, _ = _score_length("short", case)
    assert s == 0.0


def test_score_length_within_range():
    case = _mk_case(min_len=10, max_len=200)
    s, _ = _score_length("a" * 100, case)
    assert s == 10.0


def test_score_length_too_long_partial():
    case = _mk_case(min_len=10, max_len=100)
    s, _ = _score_length("a" * 200, case)
    assert 0 < s < 10


def test_score_safety_passes_clean_text():
    case = _mk_case()
    s, _ = _score_safety("正常的技术分析输出", case)
    assert s == 10.0


def test_score_safety_blocked_returns_0_veto():
    case = _mk_case()
    s, _ = _score_safety("百倍稳的", case)
    assert s == 0.0


# ── veto rules ───────────────────────────────────────────────


def test_veto_rules_all_clean():
    scores = {"actionability": 8, "risk": 7, "safety": 10}
    assert _check_veto_rules(scores) == []


def test_veto_rules_actionability_zero():
    scores = {"actionability": 0, "risk": 7, "safety": 10}
    v = _check_veto_rules(scores)
    assert any("actionability=0" in x for x in v)


def test_veto_rules_risk_zero():
    scores = {"actionability": 8, "risk": 0, "safety": 10}
    v = _check_veto_rules(scores)
    assert any("risk=0" in x for x in v)


def test_veto_rules_safety_below_10():
    scores = {"actionability": 8, "risk": 7, "safety": 9}
    v = _check_veto_rules(scores)
    assert any("safety" in x for x in v)


def test_veto_rules_multiple():
    scores = {"actionability": 0, "risk": 0, "safety": 0}
    v = _check_veto_rules(scores)
    assert len(v) == 3


# ── _run_one_case ────────────────────────────────────────────


def test_run_one_case_high_quality_passes():
    case = _mk_case(
        output_text='{"direction": "bullish", "conviction": 0.72, "summary": "TRUMP 三路一致看涨", "risks": ["流动性偏薄", "regime 风险"], "evidence": [{"layer": "tech", "text": "RSI 35"}]}',
        topic_keywords=["TRUMP", "bullish"],
        is_thesis=True, expected_format="json_thesis",
        min_len=80, max_len=500,
    )
    res = _run_one_case(case)
    assert res.passed is True
    assert res.veto_violations == []


def test_run_one_case_bad_no_risks_veto():
    case = _mk_case(
        output_text='{"direction": "bullish", "risks": [], "evidence": []}',
        is_thesis=True, expected_format="json_thesis",
    )
    res = _run_one_case(case)
    assert res.passed is False
    assert any("risk" in v for v in res.veto_violations)


def test_run_one_case_bad_blocklist_safety_veto():
    case = _mk_case(
        output_text="百倍稳的,to the moon",
    )
    res = _run_one_case(case)
    assert res.passed is False
    assert any("safety" in v for v in res.veto_violations)


# ── golden loader / 端到端 ──────────────────────────────────


def test_load_golden_missing_returns_empty():
    assert _load_golden_rubric_cases("nonexistent") == []


def test_load_golden_loads_thesis():
    cases = _load_golden_rubric_cases("thesis")
    assert len(cases) >= 5


def test_list_categories_has_4():
    cats = _list_categories()
    expected = {"thesis", "review", "notify", "chat"}
    assert expected.issubset(set(cats))


@pytest.mark.asyncio
async def test_run_suite_loads_40_samples():
    report = await run_quality_rubric_suite()
    assert report.suite == "quality_rubric"
    assert report.total >= 40


@pytest.mark.asyncio
async def test_run_suite_all_BAD_samples_fail():
    """fixture 中所有 name 以 BAD_ 开头的样本应当 fail(veto 触发)。"""
    report = await run_quality_rubric_suite()
    bad_passes = []
    for cr in report.category_reports:
        for case_res in cr.cases:
            if case_res.case_name.startswith("BAD_") and case_res.passed:
                bad_passes.append(case_res.case_name)
    assert not bad_passes, f"BAD samples 不应 pass: {bad_passes}"


@pytest.mark.asyncio
async def test_run_suite_real_samples_high_pass_rate():
    """非 BAD_ 真样本 pass rate 应 ≥ 80%(v1 heuristic baseline)。"""
    report = await run_quality_rubric_suite()
    real_total = real_passed = 0
    for cr in report.category_reports:
        for case_res in cr.cases:
            if case_res.case_name.startswith("BAD_"):
                continue
            real_total += 1
            if case_res.passed:
                real_passed += 1
    rate = real_passed / real_total if real_total else 0
    assert rate >= 0.80, (
        f"real sample pass rate {rate*100:.1f}% < 80%; "
        f"failed: {[(cr.category, [c.case_name for c in cr.cases if not c.passed and not c.case_name.startswith('BAD_')]) for cr in report.category_reports]}"
    )


@pytest.mark.asyncio
async def test_run_suite_4_categories():
    report = await run_quality_rubric_suite()
    cats = {cr.category for cr in report.category_reports}
    assert cats == {"thesis", "review", "notify", "chat"}


@pytest.mark.asyncio
async def test_run_suite_filter_one_category():
    report = await run_quality_rubric_suite(cat_filter=["thesis"])
    assert len(report.category_reports) == 1
    assert report.category_reports[0].category == "thesis"


# ── threshold ────────────────────────────────────────────────


def test_overall_threshold_baseline_60():
    """v1 heuristic baseline 60;GA LLM-judge target 80(per 17-tech-plan)。"""
    assert OVERALL_PASS_THRESHOLD == 60.0


# ── Report dataclasses ───────────────────────────────────────


def test_eval_report_zero_when_no_cases():
    r = RubricEvalReport(suite="quality_rubric")
    assert r.pass_rate == 0.0


def test_eval_report_summary_line():
    r = RubricEvalReport(
        suite="quality_rubric", total=40, passed=29,
        failed=11, duration_s=0.01,
    )
    line = r.summary_line()
    assert "29/40" in line
    assert "72.5%" in line


def test_category_report_pass_rate():
    cr = CategoryReport(category="thesis", total=10, passed=7, failed=3)
    assert cr.pass_rate == 0.7
