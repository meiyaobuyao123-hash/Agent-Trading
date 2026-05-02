"""
L1 Prompt Eval Runner 单元测试 — W3 D5+ autonomous-loop 续 20

跑法:python3 -m pytest tests/test_eval_prompt_runner.py -v

测的是 prompt_runner 框架本身。真跑 fixture 见
   `python3 -m agent.eval.prompt_runner --suite=l1_prompt`
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.eval.prompt_runner import (  # noqa: E402
    C1_BLOCKLIST_REGEX,
    GoldenPromptCase,
    PromptCaseResult,
    PromptEvalReport,
    PromptReport,
    UNRENDERED_VAR_RE,
    _check_examples_count,
    _check_examples_safe,
    _check_render_missing_vars,
    _check_render_ok,
    _check_version_select,
    _load_golden_prompt_cases,
    _run_one_case,
    _validate_prompt_metadata,
    run_l1_prompt_suite,
)


# ── Report dataclasses ───────────────────────────────────────


def test_prompt_eval_report_pass_rate_zero():
    r = PromptEvalReport(suite="l1_prompt")
    assert r.pass_rate == 0.0


def test_prompt_eval_report_pass_rate():
    r = PromptEvalReport(suite="l1_prompt", total_cases=10,
                          total_passed=9, total_failed=1)
    assert r.pass_rate == 0.9


def test_prompt_eval_report_summary_line():
    r = PromptEvalReport(suite="l1_prompt", total_cases=38,
                          total_passed=38, total_failed=0, duration_s=0.03)
    line = r.summary_line()
    assert "38/38" in line
    assert "100.0%" in line


def test_prompt_report_pass_rate():
    pr = PromptReport(prompt_id="P02", total=6, passed=5, failed=1)
    assert abs(pr.pass_rate - 5/6) < 1e-9


# ── _validate_prompt_metadata ────────────────────────────────


def _mk_spec(**overrides):
    """构造合法 PromptSpec mock。"""
    s = MagicMock()
    s.prompt_id = overrides.get("prompt_id", "P02")
    s.version = overrides.get("version", "v1.0")
    s.model = overrides.get("model", "claude-sonnet-4-6")
    s.temperature = overrides.get("temperature", 0.2)
    s.max_input_tokens = overrides.get("max_input_tokens", 12000)
    s.max_output_tokens = overrides.get("max_output_tokens", 1500)
    s.description = overrides.get(
        "description", "S08 thesis-writer:把 3 路分析合成 thesis JSON",
    )
    s.content = overrides.get("content", "x" * 500)
    s.status = overrides.get("status", "draft")
    s.rollout_pct = overrides.get("rollout_pct", 0)
    s.examples = overrides.get("examples", [
        {"user": "u1", "assistant": "a1"},
        {"user": "u2", "assistant": "a2"},
        {"user": "u3", "assistant": "a3"},
    ])
    return s


def test_validate_metadata_ok():
    spec = _mk_spec()
    ok, issues = _validate_prompt_metadata("P02", spec)
    assert ok is True
    assert issues == []


def test_validate_metadata_none_spec_invalid():
    ok, issues = _validate_prompt_metadata("P99", None)
    assert ok is False
    assert any("未在 PromptLoader 注册" in i for i in issues)


def test_validate_metadata_id_mismatch():
    spec = _mk_spec(prompt_id="P02")
    ok, issues = _validate_prompt_metadata("P10", spec)
    assert ok is False
    assert any("不匹配" in i for i in issues)


def test_validate_metadata_model_invalid():
    spec = _mk_spec(model="gpt-4")
    ok, issues = _validate_prompt_metadata("P02", spec)
    assert ok is False
    assert any("model 不合法" in i for i in issues)


def test_validate_metadata_temperature_oob():
    spec = _mk_spec(temperature=2.5)
    ok, issues = _validate_prompt_metadata("P02", spec)
    assert ok is False
    assert any("temperature" in i for i in issues)


def test_validate_metadata_body_too_short():
    spec = _mk_spec(content="x")
    ok, issues = _validate_prompt_metadata("P02", spec)
    assert ok is False
    assert any("body 太短" in i for i in issues)


def test_validate_metadata_status_invalid():
    spec = _mk_spec(status="weird_status")
    ok, issues = _validate_prompt_metadata("P02", spec)
    assert ok is False
    assert any("status 非法" in i for i in issues)


def test_validate_metadata_rollout_oob():
    spec = _mk_spec(rollout_pct=150)
    ok, issues = _validate_prompt_metadata("P02", spec)
    assert ok is False
    assert any("rollout_pct" in i for i in issues)


# ── render checks ────────────────────────────────────────────


def test_check_render_ok_passes():
    loader = MagicMock()
    loader.render = MagicMock(return_value="hello world no placeholders")
    spec = _mk_spec()
    ok, err = _check_render_ok(loader, spec, {"name": "world"})
    assert ok is True
    assert err is None


def test_check_render_ok_fails_with_leftover():
    loader = MagicMock()
    loader.render = MagicMock(return_value="hello {{name}} {{x.y}}")
    spec = _mk_spec()
    ok, err = _check_render_ok(loader, spec, {})
    assert ok is False
    assert "未替换" in (err or "")


def test_check_render_missing_vars_passes():
    loader = MagicMock()
    loader.render = MagicMock(return_value="hello {{name}}")
    spec = _mk_spec()
    ok, err = _check_render_missing_vars(loader, spec, {}, ["{{name}}"])
    assert ok is True


def test_check_render_missing_vars_fail_when_var_disappears():
    loader = MagicMock()
    loader.render = MagicMock(return_value="all replaced")
    spec = _mk_spec()
    ok, err = _check_render_missing_vars(loader, spec, {}, ["{{x}}"])
    assert ok is False


# ── examples checks ──────────────────────────────────────────


def test_check_examples_safe_passes():
    spec = _mk_spec(examples=[{"user": "u", "assistant": "正常输出"}])
    ok, err = _check_examples_safe(spec)
    assert ok is True


def test_check_examples_safe_fails_on_blocklist():
    spec = _mk_spec(examples=[{"user": "u", "assistant": "稳的可以买入"}])
    ok, err = _check_examples_safe(spec)
    assert ok is False
    assert "blocklist" in (err or "")


def test_check_examples_count_passes():
    spec = _mk_spec(examples=[{}, {}, {}])
    ok, err = _check_examples_count(spec, 3)
    assert ok is True


def test_check_examples_count_fails():
    spec = _mk_spec(examples=[{}, {}])
    ok, err = _check_examples_count(spec, 3)
    assert ok is False
    assert "< 3" in (err or "")


# ── version_select ───────────────────────────────────────────


def test_check_version_select_returns_none_fails():
    loader = MagicMock()
    loader.select_version = MagicMock(return_value=None)
    ok, err = _check_version_select(loader, "P02", "device-1", "draft")
    assert ok is False
    assert "None" in (err or "")


def test_check_version_select_status_match():
    loader = MagicMock()
    spec = _mk_spec(status="canary")
    loader.select_version = MagicMock(return_value=spec)
    ok, err = _check_version_select(loader, "P02", "device-1", "canary")
    assert ok is True


def test_check_version_select_status_mismatch():
    loader = MagicMock()
    spec = _mk_spec(status="ga")
    loader.select_version = MagicMock(return_value=spec)
    ok, err = _check_version_select(loader, "P02", "device-1", "draft")
    assert ok is False


# ── _run_one_case ────────────────────────────────────────────


def test_run_one_case_metadata_ok():
    loader = MagicMock()
    spec = _mk_spec()
    case = GoldenPromptCase(
        name="meta", prompt_id="P02", expected_outcome="metadata_ok",
    )
    cr = _run_one_case(loader, spec, case)
    assert cr.passed is True


def test_run_one_case_unknown_outcome():
    loader = MagicMock()
    spec = _mk_spec()
    case = GoldenPromptCase(
        name="weird", prompt_id="P02", expected_outcome="bogus",
    )
    cr = _run_one_case(loader, spec, case)
    assert cr.passed is False
    assert cr.actual_outcome == "unknown_outcome"


# ── golden loader ────────────────────────────────────────────


def test_load_golden_missing_returns_empty():
    cases = _load_golden_prompt_cases("P99")
    assert cases == []


def test_load_golden_loads_real_P01():
    cases = _load_golden_prompt_cases("P01")
    assert len(cases) >= 5
    assert any(c.name == "metadata_ok" for c in cases)


# ── 端到端 ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_l1_prompt_suite_all_pass():
    report = await run_l1_prompt_suite()
    assert report.suite == "l1_prompt"
    assert report.total_failed == 0, (
        f"L1 Prompt 失败: {[(pr.prompt_id, [c.case_name for c in pr.cases if not c.passed]) for pr in report.prompt_reports if pr.failed]}"
    )
    assert len(report.prompt_reports) >= 6


@pytest.mark.asyncio
async def test_run_l1_prompt_suite_with_filter():
    report = await run_l1_prompt_suite(prompt_filter=["P02"])
    assert len(report.prompt_reports) == 1
    assert report.prompt_reports[0].prompt_id == "P02"


# ── regex behaviors ──────────────────────────────────────────


def test_blocklist_regex_catches_phrases():
    assert C1_BLOCKLIST_REGEX.search("这个稳的")
    assert C1_BLOCKLIST_REGEX.search("百倍")
    assert C1_BLOCKLIST_REGEX.search("guaranteed return")
    assert not C1_BLOCKLIST_REGEX.search("一般的分析")


def test_unrendered_var_regex_finds_placeholders():
    assert UNRENDERED_VAR_RE.findall("{{a}} and {{b.c}}") == ["{{a}}", "{{b.c}}"]
    assert UNRENDERED_VAR_RE.findall("nothing here") == []
