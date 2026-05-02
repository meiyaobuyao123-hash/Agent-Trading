"""
LLM-as-Judge Calibration Eval Runner 单元测试 — W3 D5+ autonomous-loop 续 28

跑法:python3 -m pytest tests/test_eval_judge_runner.py -v
真跑 fixture 见 `python3 -m agent.eval.judge_runner --suite=judge_calibration`
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.eval.judge_runner import (  # noqa: E402
    DIMENSIONS,
    DimResult,
    JudgeEvalReport,
    JudgeSample,
    PEARSON_THRESHOLD,
    SAFETY_AGREEMENT_THRESHOLD,
    _pearson,
    default_judge,
    run_judge_calibration,
)


# ── constants ────────────────────────────────────────────────


def test_dimensions_10():
    assert len(DIMENSIONS) == 10


def test_pearson_threshold_07():
    """对齐 17-tech-plan: Pearson ≥ 0.7。"""
    assert PEARSON_THRESHOLD == 0.7


def test_safety_agreement_100():
    """对齐 17-tech-plan: Safety 100% 一致。"""
    assert SAFETY_AGREEMENT_THRESHOLD == 1.0


# ── _pearson ─────────────────────────────────────────────────


def test_pearson_perfect_correlation():
    xs = [1, 2, 3, 4, 5]
    ys = [1, 2, 3, 4, 5]
    assert abs(_pearson(xs, ys) - 1.0) < 1e-9


def test_pearson_perfect_anti_correlation():
    xs = [1, 2, 3, 4, 5]
    ys = [5, 4, 3, 2, 1]
    assert abs(_pearson(xs, ys) - (-1.0)) < 1e-9


def test_pearson_no_correlation():
    xs = [1, 2, 3, 4, 5]
    ys = [3, 1, 4, 1, 5]
    r = _pearson(xs, ys)
    assert -0.5 < r < 0.5


def test_pearson_zero_std_returns_0():
    xs = [3, 3, 3, 3]
    ys = [1, 2, 3, 4]
    assert _pearson(xs, ys) == 0.0


def test_pearson_short_input_returns_0():
    assert _pearson([1], [2]) == 0.0
    assert _pearson([], []) == 0.0


def test_pearson_mismatched_length_returns_0():
    assert _pearson([1, 2, 3], [1, 2]) == 0.0


# ── default_judge ────────────────────────────────────────────


def test_default_judge_returns_10_dims():
    s = JudgeSample(
        name="t", output_text="技术分析:RSI 35,建议观望,谨慎判断风险",
    )
    scores = default_judge(s)
    assert set(scores.keys()) == set(DIMENSIONS)
    for d, v in scores.items():
        assert 0 <= v <= 10


def test_default_judge_thesis_uses_json():
    s = JudgeSample(
        name="t", is_thesis=True,
        output_text='{"direction": "bullish", "conviction": 0.7, "risks": ["a", "b"], "evidence": [{"layer": "x"}]}',
    )
    scores = default_judge(s)
    assert scores["actionability"] == 10.0  # direction="bullish"
    assert scores["risk"] == 10.0  # 2 risks


def test_default_judge_safety_blocked_returns_0():
    s = JudgeSample(name="t", output_text="百倍稳的")
    scores = default_judge(s)
    assert scores["safety"] == 0.0


# ── Report dataclasses ───────────────────────────────────────


def test_report_passes_when_all_meet():
    r = JudgeEvalReport(suite="judge_calibration", total_samples=100)
    for d in DIMENSIONS:
        if d == "safety":
            r.dim_results[d] = DimResult(
                dimension=d, pearson=0.0, n=100, mean_human=10, mean_judge=10,
                safety_agreement=1.0, passes_threshold=True,
            )
        else:
            r.dim_results[d] = DimResult(
                dimension=d, pearson=0.85, n=100, mean_human=6, mean_judge=6,
                passes_threshold=True,
            )
    assert r.passes is True
    assert r.all_dims_meet_threshold is True


def test_report_fails_when_safety_below_100():
    r = JudgeEvalReport(suite="judge_calibration", total_samples=100)
    for d in DIMENSIONS:
        if d == "safety":
            r.dim_results[d] = DimResult(
                dimension=d, pearson=0.0, n=100, mean_human=10, mean_judge=9,
                safety_agreement=0.95,  # 95% 不够
                passes_threshold=False,
            )
        else:
            r.dim_results[d] = DimResult(
                dimension=d, pearson=0.85, n=100, mean_human=6, mean_judge=6,
                passes_threshold=True,
            )
    assert r.passes is False


def test_report_fails_when_one_dim_below_07():
    r = JudgeEvalReport(suite="judge_calibration", total_samples=100)
    for d in DIMENSIONS:
        if d == "safety":
            r.dim_results[d] = DimResult(
                dimension=d, pearson=0, n=100, mean_human=10, mean_judge=10,
                safety_agreement=1.0, passes_threshold=True,
            )
        elif d == "reasoning":
            r.dim_results[d] = DimResult(
                dimension=d, pearson=0.55, n=100, mean_human=5, mean_judge=4,
                passes_threshold=False,
            )
        else:
            r.dim_results[d] = DimResult(
                dimension=d, pearson=0.85, n=100, mean_human=6, mean_judge=6,
                passes_threshold=True,
            )
    assert r.passes is False


def test_report_summary_line():
    r = JudgeEvalReport(
        suite="judge_calibration", total_samples=100, duration_s=0.01,
    )
    for d in DIMENSIONS:
        r.dim_results[d] = DimResult(
            dimension=d, pearson=0.9, n=100, mean_human=6, mean_judge=6,
            passes_threshold=True,
        )
    line = r.summary_line()
    assert "10/10" in line
    assert "N=100" in line


# ── 端到端 ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_judge_calibration_loads_100():
    report = await run_judge_calibration()
    assert report.suite == "judge_calibration"
    assert report.total_samples == 100, f"应有 100 sample,实际 {report.total_samples}"


@pytest.mark.asyncio
async def test_run_judge_calibration_passes_baseline():
    """启发式 judge baseline:Pearson ≥ 0.7 + safety 100%。"""
    report = await run_judge_calibration()
    failures = []
    for d in DIMENSIONS:
        dr = report.dim_results.get(d)
        if dr is None or not dr.passes_threshold:
            failures.append(f"{d}: pearson={dr.pearson if dr else 'n/a'}")
    assert not failures, f"未达门槛: {failures}"


@pytest.mark.asyncio
async def test_run_judge_calibration_safety_strict():
    report = await run_judge_calibration()
    safety = report.dim_results.get("safety")
    assert safety is not None
    assert safety.safety_agreement == 1.0, (
        f"Safety 必须 100%,实际 {safety.safety_agreement*100:.1f}%"
    )


@pytest.mark.asyncio
async def test_run_judge_calibration_all_dims_present():
    report = await run_judge_calibration()
    assert set(report.dim_results.keys()) == set(DIMENSIONS)


@pytest.mark.asyncio
async def test_run_judge_calibration_mean_scores_in_range():
    report = await run_judge_calibration()
    for d, dr in report.dim_results.items():
        assert 0 <= dr.mean_human <= 10
        assert 0 <= dr.mean_judge <= 10


# ── 自定 judge fn 替换接口 ──────────────────────────────────


@pytest.mark.asyncio
async def test_custom_judge_fn_replaces_default():
    """plug-in 自定 judge fn,验证替换生效。"""
    def all_8_judge(sample: JudgeSample):
        return {d: 8.0 for d in DIMENSIONS}

    report = await run_judge_calibration(judge_fn=all_8_judge)
    for d in DIMENSIONS:
        dr = report.dim_results.get(d)
        if d == "safety":
            # safety judge=8(不是 10)→ human=10 → 不一致
            assert dr.safety_agreement < 1.0
        else:
            # mean_judge 应 ≈ 8(略有浮动因 noise)
            assert abs(dr.mean_judge - 8.0) < 0.1


# ── samples.json sanity ──────────────────────────────────────


def test_samples_fixture_exists_with_100():
    fp = (Path(__file__).resolve().parents[1] /
          "agent/eval/golden/judge_calibration/samples.json")
    assert fp.exists()
    import json
    data = json.loads(fp.read_text(encoding="utf-8"))
    assert data.get("n_samples") == 100
    samples = data.get("samples", [])
    assert len(samples) == 100
    # 每个 sample 必含 output_text + human_scores 全 10 维
    for s in samples[:5]:  # 抽样
        assert s.get("output_text")
        assert set(s.get("human_scores", {}).keys()) == set(DIMENSIONS)


def test_samples_categories_4_balanced():
    fp = (Path(__file__).resolve().parents[1] /
          "agent/eval/golden/judge_calibration/samples.json")
    import json
    data = json.loads(fp.read_text(encoding="utf-8"))
    samples = data.get("samples", [])
    cats = {}
    for s in samples:
        cats[s.get("category", "?")] = cats.get(s.get("category", "?"), 0) + 1
    # 期望 4 category × ~25 samples
    assert len(cats) >= 4
    assert all(c >= 20 for c in cats.values())
