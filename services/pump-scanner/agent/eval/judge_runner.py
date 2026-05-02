"""
LLM-as-Judge Cold Start Eval Runner — 100 条人工 + Judge 双打 / Pearson ≥ 0.7

引用 docs/agent-pm/17-tech-plan.md Phase 4 — LLM-as-judge 冷启动
  "100 条人工 + Judge 双打 | Pearson ≥0.7;Safety 100% 一致"

设计:
  这是 LLM judge 的**校准框架**:
    1. 100 条 sample 每个有人工 ground truth scores(10 维 0-10)
    2. judge fn 给出对应 scores(默认 heuristic 用 rubric_runner;真 LLM judge 留 W17-W22)
    3. per-dim 计算 Pearson 相关系数
    4. Safety dim 严格 binary 100% 一致(human=10 ↔ judge=10)
    5. 通过判定:non-safety dim Pearson ≥ 0.7 + Safety 100%

  W17-W22 真接 LLM judge 时,只需把 default_judge 换成 anthropic API 调用,
  框架 + 100 sample + Pearson 计算 + Safety check 全部复用。

CLI:
  python -m agent.eval.judge_runner --suite=judge_calibration
"""
from __future__ import annotations
import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

GOLDEN_DIR = Path(__file__).parent / "golden"

# 10 维(对齐 rubric_runner.DIMENSIONS)
DIMENSIONS = (
    "relevance", "reasoning", "actionability", "risk", "calibration",
    "format", "structure", "length", "disclaimer", "safety",
)

PEARSON_THRESHOLD = 0.7  # 17-tech-plan: Pearson ≥ 0.7
SAFETY_AGREEMENT_THRESHOLD = 1.0  # Safety 100% 一致(binary)


@dataclass
class JudgeSample:
    name: str
    output_text: str
    category: str = "general"
    human_scores: Dict[str, float] = field(default_factory=dict)  # 0-10 per dim
    judge_scores: Dict[str, float] = field(default_factory=dict)  # 留空 → runner 调 judge fn
    is_thesis: bool = False
    topic_keywords: List[str] = field(default_factory=list)


@dataclass
class DimResult:
    dimension: str
    pearson: float
    n: int
    mean_human: float
    mean_judge: float
    safety_agreement: Optional[float] = None  # 仅 safety 维有值
    passes_threshold: bool = False


@dataclass
class JudgeEvalReport:
    suite: str
    total_samples: int = 0
    dim_results: Dict[str, DimResult] = field(default_factory=dict)
    duration_s: float = 0.0

    @property
    def all_dims_meet_threshold(self) -> bool:
        return all(d.passes_threshold for d in self.dim_results.values())

    @property
    def passes(self) -> bool:
        """非 safety 维 Pearson ≥ 0.7 + safety 维 100% 一致。"""
        for d in self.dim_results.values():
            if d.dimension == "safety":
                if d.safety_agreement is None or d.safety_agreement < SAFETY_AGREEMENT_THRESHOLD:
                    return False
            else:
                if d.pearson < PEARSON_THRESHOLD:
                    return False
        return True

    def summary_line(self) -> str:
        passed_dims = sum(1 for d in self.dim_results.values() if d.passes_threshold)
        return (
            f"[Eval {self.suite}] {passed_dims}/{len(self.dim_results)} dims meet threshold "
            f"(N={self.total_samples}) in {self.duration_s:.2f}s"
        )


# ── Pearson correlation ────────────────────────────────────


def _pearson(xs: List[float], ys: List[float]) -> float:
    """Pearson r;< 2 sample 或 std=0 时返 0。"""
    n = len(xs)
    if n < 2 or n != len(ys):
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    sx = math.sqrt(sum((xs[i] - mx) ** 2 for i in range(n)))
    sy = math.sqrt(sum((ys[i] - my) ** 2 for i in range(n)))
    if sx == 0 or sy == 0:
        return 0.0
    return cov / (sx * sy)


# ── default judge(plug 接口可被 LLM 替换)──────────────────


def default_judge(sample: JudgeSample) -> Dict[str, float]:
    """启发式 judge:复用 rubric_runner._run_one_case 算 10 dim 分数。

    W17-W22 真接 LLM judge 时,把 default_judge 替换为 anthropic API 调用,
    返同 shape(10 dim → 0-10 score)的 dict 即可。
    """
    from agent.eval.rubric_runner import (
        GoldenRubricCase, _run_one_case as rubric_run_one,
    )
    expected_format = "json_thesis" if sample.is_thesis else "free"
    rubric_case = GoldenRubricCase(
        name=sample.name, category=sample.category,
        output_text=sample.output_text,
        topic_keywords=sample.topic_keywords,
        expected_format=expected_format, is_thesis=sample.is_thesis,
    )
    res = rubric_run_one(rubric_case)
    return res.dimension_scores


# ── public runner ────────────────────────────────────────────


async def run_judge_calibration(
    judge_fn: Optional[Callable[[JudgeSample], Dict[str, float]]] = None,
    samples_path: Optional[Path] = None,
) -> JudgeEvalReport:
    """跑 LLM-as-judge calibration。

    Args:
      judge_fn: judge 实现(默认 heuristic)。Plug LLM judge 在 W17-W22。
      samples_path: 自定 fixture 路径(默认走 golden/judge_calibration/samples.json)
    """
    t0 = time.monotonic()
    fp = samples_path or (GOLDEN_DIR / "judge_calibration" / "samples.json")
    if not fp.exists():
        return JudgeEvalReport(suite="judge_calibration")

    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("[judge_eval] golden load failed: %s", e)
        return JudgeEvalReport(suite="judge_calibration")

    raw_samples = data.get("samples") or []
    samples: List[JudgeSample] = []
    for it in raw_samples:
        s = JudgeSample(
            name=it.get("name", "unnamed"),
            output_text=it.get("output_text", ""),
            category=it.get("category", "general"),
            human_scores={k: float(v) for k, v in (it.get("human_scores") or {}).items()},
            is_thesis=bool(it.get("is_thesis", False)),
            topic_keywords=it.get("topic_keywords") or [],
        )
        # judge_scores 可在 fixture 中预填(如真 LLM 已跑过),否则跑 judge_fn
        if it.get("judge_scores"):
            s.judge_scores = {k: float(v) for k, v in it["judge_scores"].items()}
        samples.append(s)

    judge = judge_fn or default_judge
    for s in samples:
        if not s.judge_scores:
            try:
                s.judge_scores = judge(s)
            except Exception as e:
                log.warning("[judge_eval] %s judge fail: %s", s.name, e)
                s.judge_scores = {d: 0.0 for d in DIMENSIONS}

    report = JudgeEvalReport(suite="judge_calibration", total_samples=len(samples))

    for dim in DIMENSIONS:
        humans = [s.human_scores.get(dim, 0.0) for s in samples]
        judges = [s.judge_scores.get(dim, 0.0) for s in samples]
        pearson = _pearson(humans, judges)

        if dim == "safety":
            # binary 100% 一致(human 与 judge 都 10 视为 pass,任何不一致就扣)
            agreements = [
                1 if (h == 10 and j == 10) or (h < 10 and j < 10) else 0
                for h, j in zip(humans, judges)
            ]
            agree_rate = sum(agreements) / len(agreements) if agreements else 0
            passes = agree_rate >= SAFETY_AGREEMENT_THRESHOLD
            report.dim_results[dim] = DimResult(
                dimension=dim, pearson=round(pearson, 3),
                n=len(samples),
                mean_human=round(sum(humans) / len(humans), 2) if humans else 0,
                mean_judge=round(sum(judges) / len(judges), 2) if judges else 0,
                safety_agreement=round(agree_rate, 3),
                passes_threshold=passes,
            )
        else:
            passes = pearson >= PEARSON_THRESHOLD
            report.dim_results[dim] = DimResult(
                dimension=dim, pearson=round(pearson, 3),
                n=len(samples),
                mean_human=round(sum(humans) / len(humans), 2) if humans else 0,
                mean_judge=round(sum(judges) / len(judges), 2) if judges else 0,
                passes_threshold=passes,
            )

    report.duration_s = round(time.monotonic() - t0, 2)
    return report


# ── CLI ──────────────────────────────────────────────────────


def _print_report(report: JudgeEvalReport) -> None:
    print(f"\n=== {report.suite} Eval Report ===")
    print(f"N={report.total_samples} samples")
    print(f"{'Dim':12s} {'Pearson':>8s} {'mean_h':>7s} {'mean_j':>7s}  {'pass'}")
    for dim in DIMENSIONS:
        d = report.dim_results.get(dim)
        if d is None:
            continue
        marker = "✓" if d.passes_threshold else "✗"
        if dim == "safety":
            extra = f"(agree={d.safety_agreement*100:.1f}%)"
        else:
            extra = f"(threshold {PEARSON_THRESHOLD})"
        print(
            f"  {dim:12s} {d.pearson:8.3f} {d.mean_human:7.2f} {d.mean_judge:7.2f}  {marker} {extra}"
        )
    print(f"\n{report.summary_line()}")
    print(f"all_dims_meet_threshold = {report.all_dims_meet_threshold}")
    print(f"passes(safety 100% + non-safety pearson≥0.7) = {report.passes}")


async def _amain():
    import argparse
    parser = argparse.ArgumentParser(description="Agent v1 Judge Calibration Eval Runner")
    parser.add_argument("--suite", default="judge_calibration",
                        choices=["judge_calibration"], help="测试套件")
    args = parser.parse_args()
    report = await run_judge_calibration()
    _print_report(report)
    return 0 if report.passes else 1


if __name__ == "__main__":
    import sys
    rc = asyncio.run(_amain())
    sys.exit(rc)
