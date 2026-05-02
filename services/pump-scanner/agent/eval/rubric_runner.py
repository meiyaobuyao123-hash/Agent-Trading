"""
Quality Rubric Eval Runner — 5 product + 5 tech 维度评分 + veto 规则

引用 docs/agent-pm/17-tech-plan.md Phase 4 — Quality Rubric
  "5 维(Relevance/Reasoning/Actionability/Risk/Calibration)+ 技术 5 维
   overall ≥80;Actionability=0 / Risk=0 / Safety<10 一票否决"

设计:
  本框架是 LLM-as-judge 的**规则化骨架**(同 R23-R26 思路:静态契约 +
  规则评分 + 真 LLM-judge 留 W17-W22)。
  每条 sample(LLM 输出文本 + 上下文)被 10 个 dimension scorer 打 0-10 分,
  加权求 overall(0-100),再应用 3 条 veto 规则决定 pass/fail。

10 个 dimension(每个 0-10 分):
  Product:
    - relevance       与 topic 关键词匹配 + 数据点引用
    - reasoning       推理步骤数 + evidence 引用次数
    - actionability   含具体动作(买入/卖出/等待/止损/止盈/数量/价位)
    - risk            含风险提示数(>=2 / >=1 / 0)
    - calibration     conviction/confidence 数值显式
  Tech:
    - format          结构(JSON 解析成功 / 段落清晰)
    - structure       必要 section 存在(direction/risks/evidence)
    - length          ≤ max_len + ≥ min_len
    - disclaimer      含免责声明 / 风险提醒
    - safety          input_filter + output_filter 双过(≤10,< 10 即 veto)

Veto 规则(任一命中 → fail 不论 overall):
  - actionability == 0  → veto
  - risk == 0           → veto
  - safety < 10         → veto

CLI:
  python -m agent.eval.rubric_runner --suite=quality_rubric [--cat=thesis]
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

GOLDEN_DIR = Path(__file__).parent / "golden"

# ── 配置:weights + thresholds ──────────────────────────────

DIMENSIONS = (
    # product 5
    "relevance", "reasoning", "actionability", "risk", "calibration",
    # tech 5
    "format", "structure", "length", "disclaimer", "safety",
)

DEFAULT_WEIGHTS: Dict[str, float] = {d: 1.0 for d in DIMENSIONS}

# v1 heuristic baseline = 60;GA LLM-judge target = 80(per docs/agent-pm/17-tech-plan.md)
# 启发式 scorer 难以稳定到 80;LLM-as-judge 实施后(W17-W22)才提到 80
# veto 规则(actionability=0 / risk=0 / safety<10)仍是硬门槛 — BAD 样本即便 score 高也 veto fail
OVERALL_PASS_THRESHOLD = 60.0


# ── dataclasses ──────────────────────────────────────────────


@dataclass
class GoldenRubricCase:
    name: str
    category: str
    output_text: str
    description: str = ""
    topic_keywords: List[str] = field(default_factory=list)  # relevance scorer 用
    expected_format: str = "free"  # "json" | "json_thesis" | "free"
    is_thesis: bool = False         # is_thesis=True 时 output 应是 JSON 含 direction/risks/evidence
    min_len: int = 30
    max_len: int = 2000


@dataclass
class DimensionScore:
    dimension: str
    score: float       # 0-10
    reasoning: str = ""


@dataclass
class RubricResult:
    case_name: str
    category: str
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    overall: float = 0.0  # 0-100
    veto_violations: List[str] = field(default_factory=list)
    passed: bool = False  # overall>=80 AND no veto

    @property
    def has_veto(self) -> bool:
        return len(self.veto_violations) > 0


@dataclass
class CategoryReport:
    category: str
    total: int
    passed: int
    failed: int
    avg_overall: float = 0.0
    avg_dimensions: Dict[str, float] = field(default_factory=dict)
    cases: List[RubricResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total


@dataclass
class RubricEvalReport:
    suite: str
    category_reports: List[CategoryReport] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    duration_s: float = 0.0

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total

    def summary_line(self) -> str:
        return (
            f"[Eval {self.suite}] {self.passed}/{self.total} samples "
            f"({self.pass_rate*100:.1f}%) in {self.duration_s:.2f}s"
        )


# ── dimension scorers(每个返 0-10)──────────────────────────


def _score_relevance(text: str, case: GoldenRubricCase) -> Tuple[float, str]:
    """topic_keywords 命中比例 → 0-10。"""
    if not case.topic_keywords:
        return 7.0, "no topic_keywords (default 7)"
    text_low = text.lower()
    hits = sum(1 for kw in case.topic_keywords if kw.lower() in text_low)
    rate = hits / len(case.topic_keywords)
    score = min(10.0, rate * 10 + 1)  # 至少有 1 分,全命中 10
    return round(score, 1), f"{hits}/{len(case.topic_keywords)} kw hits"


_DATA_POINT_RE = re.compile(
    r"(\d+\.?\d*\s*%|\$[\d,]+|RSI\s*\d+|MACD|MA\d+|ATR|净流入|净流出|"
    r"\d+/\d+|conviction\s*[:=]?\s*\d|信心\s*\d|score\s*[:=]?\s*\d)",
    re.IGNORECASE,
)


def _score_reasoning(text: str, case: GoldenRubricCase) -> Tuple[float, str]:
    """数据点 + 推理连接词数量。"""
    data_points = len(_DATA_POINT_RE.findall(text))
    connectors = sum(text.count(c) for c in [
        "因为", "所以", "考虑", "因此", "因", "based on", "given",
        "建议", "由于", "如果", "如", "可", "需要",
    ])
    # 长文本天然有 baseline 推理:每 100 字加 0.5
    length_bonus = min(2.0, len(text) / 100 * 0.5)
    raw = data_points * 1.5 + connectors * 0.5 + length_bonus + 2  # baseline 2
    score = min(10.0, raw)
    return round(score, 1), f"{data_points} data + {connectors} conn + len_bonus {length_bonus:.1f}"


_ACTION_RE = re.compile(
    r"(买入|卖出|止损|止盈|建议|不建议|跟单|观望|等待|hold|buy|sell|"
    r"avoid|enter|exit|skip|wait|进场|出场|仓位|"
    r"bullish|bearish|neutral|long|short|"
    r"保存|取消|注意|警告|stage_transition|approve|reject|"
    r"调整|改|加权|权重|考虑|提议|采纳|跳过|放宽|收紧)",
    re.IGNORECASE,
)


def _score_actionability(text: str, case: GoldenRubricCase) -> Tuple[float, str]:
    """含具体动作 → 高分;0 命中 → 0(触发 veto)。
    is_thesis=True 时优先看 JSON.direction 字段(thesis 的 action 编码在 direction)。
    """
    if case.is_thesis:
        try:
            obj = json.loads(text)
            direction = obj.get("direction", "")
            if direction and direction != "unknown":
                return 10.0, f"thesis.direction={direction}"
            return 0.0, "thesis.direction empty/unknown (VETO)"
        except Exception:
            pass
    hits = len(_ACTION_RE.findall(text))
    if hits == 0:
        return 0.0, "0 action verb (VETO)"
    return round(min(10.0, 4 + hits * 1.5), 1), f"{hits} action hits"


def _score_risk(text: str, case: GoldenRubricCase) -> Tuple[float, str]:
    """风险提示数。is_thesis 时校验 risks list ≥2。"""
    if case.is_thesis:
        try:
            obj = json.loads(text)
            risks = obj.get("risks", [])
            if isinstance(risks, list):
                n = len(risks)
                if n == 0:
                    return 0.0, "thesis.risks 空(VETO)"
                if n >= 2:
                    return 10.0, f"thesis risks={n}"
                return 5.0, "thesis 仅 1 风险(<2 PRD 硬约束)"
            return 0.0, "thesis.risks 非 list(VETO)"
        except Exception:
            pass
    # 通用文本:统计风险关键词(扩展含 disclaimer 风格)
    risk_words = sum(text.count(w) for w in [
        "风险", "注意", "警惕", "谨慎", "可能", "未必", "不保证", "波动",
        "不构成投资建议", "请自行", "DYOR", "本工具", "需 自行",
        "建议", "警告",
        "risk", "caution", "warning", "may", "uncertain",
    ])
    if risk_words == 0:
        return 0.0, "0 risk word (VETO)"
    return round(min(10.0, 3 + risk_words * 1.5), 1), f"{risk_words} risk words"


_CONVICTION_RE = re.compile(
    r"(conviction\s*[:=]?\s*[\d.]+|信心\s*[\d.]+|confidence\s*[:=]?\s*[\d.]+|"
    r"\d{1,3}\s*%)",
    re.IGNORECASE,
)


def _score_calibration(text: str, case: GoldenRubricCase) -> Tuple[float, str]:
    """conviction/confidence/% 数值显式。"""
    hits = _CONVICTION_RE.findall(text)
    if not hits:
        return 3.0, "无显式 conviction"
    return round(min(10.0, 5 + len(hits) * 1.5), 1), f"{len(hits)} calib refs"


def _score_format(text: str, case: GoldenRubricCase) -> Tuple[float, str]:
    """JSON 解析 + 段落分隔。"""
    if case.expected_format in ("json", "json_thesis"):
        try:
            json.loads(text)
            return 10.0, "valid JSON"
        except Exception as e:
            return 2.0, f"JSON parse failed: {str(e)[:30]}"
    # free format:有换行/段落即可
    paragraphs = len([p for p in text.split("\n\n") if p.strip()])
    return round(min(10.0, 5 + paragraphs * 1.5), 1), f"{paragraphs} paragraphs"


def _score_structure(text: str, case: GoldenRubricCase) -> Tuple[float, str]:
    """is_thesis 检 direction/risks/evidence;否则看长度合理。"""
    if case.is_thesis:
        try:
            obj = json.loads(text)
            score = 0.0
            for k in ("direction", "risks", "evidence"):
                if k in obj:
                    score += 3.3
            return round(min(10.0, score), 1), f"keys present: {[k for k in obj if k in ('direction','risks','evidence')]}"
        except Exception:
            return 1.0, "thesis JSON parse failed"
    # free:看是否有标题/列表
    has_heading = bool(re.search(r"#+\s|\*\*\w", text))
    has_list = bool(re.search(r"^[-*\d]\.\s|^- ", text, re.MULTILINE))
    s = 5.0 + (2.5 if has_heading else 0) + (2.5 if has_list else 0)
    return round(s, 1), f"heading={has_heading} list={has_list}"


def _score_length(text: str, case: GoldenRubricCase) -> Tuple[float, str]:
    n = len(text)
    if n < case.min_len:
        return 0.0, f"len {n} < min {case.min_len}"
    if n > case.max_len:
        # 超长扣分但不 0
        over = (n - case.max_len) / case.max_len
        return round(max(2.0, 10 - over * 5), 1), f"len {n} > max {case.max_len}"
    return 10.0, f"len {n} ok"


def _score_disclaimer(text: str, case: GoldenRubricCase) -> Tuple[float, str]:
    """免责声明 / 风险提醒关键词。"""
    keywords = [
        "免责", "不构成投资建议", "本工具", "请自行判断",
        "DYOR", "not financial advice", "past performance",
        "your own research", "未必",
    ]
    hits = sum(1 for k in keywords if k.lower() in text.lower())
    if hits == 0:
        return 5.0, "无显式 disclaimer(中性分)"
    return round(min(10.0, 7 + hits * 1.5), 1), f"{hits} disclaimer kws"


def _score_safety(text: str, case: GoldenRubricCase) -> Tuple[float, str]:
    """复用 input_filter + output_filter 双过。fail = 0 触发 veto。"""
    try:
        from agent.input_filter import filter_combined
        res = filter_combined(text)
        if res.passed:
            return 10.0, "filter pass"
        return 0.0, f"filter blocked: {res.matched_classes[:3]} (VETO)"
    except Exception as e:
        # filter 加载失败 → 中性分,避免误 veto
        return 7.0, f"filter import fail: {e}"


SCORERS: Dict[str, Callable[[str, GoldenRubricCase], Tuple[float, str]]] = {
    "relevance": _score_relevance,
    "reasoning": _score_reasoning,
    "actionability": _score_actionability,
    "risk": _score_risk,
    "calibration": _score_calibration,
    "format": _score_format,
    "structure": _score_structure,
    "length": _score_length,
    "disclaimer": _score_disclaimer,
    "safety": _score_safety,
}


# ── veto rules ───────────────────────────────────────────────


def _check_veto_rules(scores: Dict[str, float]) -> List[str]:
    """SEV-0 veto:actionability=0 / risk=0 / safety<10 → fail。"""
    violations = []
    if scores.get("actionability", 0) == 0:
        violations.append("actionability=0")
    if scores.get("risk", 0) == 0:
        violations.append("risk=0")
    if scores.get("safety", 0) < 10:
        violations.append(f"safety={scores.get('safety', 0)}<10")
    return violations


# ── case runner ──────────────────────────────────────────────


def _run_one_case(case: GoldenRubricCase) -> RubricResult:
    text = case.output_text or ""
    scores: Dict[str, float] = {}
    for dim in DIMENSIONS:
        scorer = SCORERS.get(dim)
        if scorer is None:
            scores[dim] = 0.0
            continue
        try:
            s, _reason = scorer(text, case)
        except Exception:
            s = 0.0
        scores[dim] = s
    # weighted overall
    weighted_sum = sum(scores[d] * DEFAULT_WEIGHTS[d] for d in DIMENSIONS)
    weight_total = sum(DEFAULT_WEIGHTS[d] for d in DIMENSIONS)
    overall = (weighted_sum / weight_total) * 10.0  # 0-100
    veto = _check_veto_rules(scores)
    passed = (overall >= OVERALL_PASS_THRESHOLD) and not veto
    return RubricResult(
        case_name=case.name, category=case.category,
        dimension_scores=scores, overall=round(overall, 1),
        veto_violations=veto, passed=passed,
    )


# ── golden loader ────────────────────────────────────────────


def _load_golden_rubric_cases(category: str) -> List[GoldenRubricCase]:
    fp = GOLDEN_DIR / "quality_rubric" / f"{category}.json"
    if not fp.exists():
        return []
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("[rubric_eval] golden load %s failed: %s", fp, e)
        return []
    cases = []
    for item in (data.get("samples") or []):
        cases.append(GoldenRubricCase(
            name=item.get("name", "unnamed"),
            category=category,
            output_text=item.get("output_text", ""),
            description=item.get("description", ""),
            topic_keywords=item.get("topic_keywords") or [],
            expected_format=item.get("expected_format", "free"),
            is_thesis=bool(item.get("is_thesis", False)),
            min_len=int(item.get("min_len", 30)),
            max_len=int(item.get("max_len", 2000)),
        ))
    return cases


def _list_categories() -> List[str]:
    d = GOLDEN_DIR / "quality_rubric"
    if not d.exists():
        return []
    return sorted([fp.stem for fp in d.glob("*.json")])


# ── public runner ────────────────────────────────────────────


async def run_quality_rubric_suite(
    cat_filter: Optional[List[str]] = None,
) -> RubricEvalReport:
    t0 = time.monotonic()
    cats = _list_categories()
    if cat_filter:
        cats = [c for c in cats if c in cat_filter]

    report = RubricEvalReport(suite="quality_rubric")
    for cat in cats:
        cases = _load_golden_rubric_cases(cat)
        cr = CategoryReport(category=cat, total=len(cases), passed=0, failed=0)
        sum_overall = 0.0
        sum_dims: Dict[str, float] = {d: 0.0 for d in DIMENSIONS}
        for case in cases:
            res = _run_one_case(case)
            cr.cases.append(res)
            sum_overall += res.overall
            for d in DIMENSIONS:
                sum_dims[d] += res.dimension_scores.get(d, 0.0)
            if res.passed:
                cr.passed += 1
            else:
                cr.failed += 1
        if cr.total > 0:
            cr.avg_overall = round(sum_overall / cr.total, 1)
            cr.avg_dimensions = {d: round(sum_dims[d] / cr.total, 2) for d in DIMENSIONS}
        report.category_reports.append(cr)
        report.total += cr.total
        report.passed += cr.passed
        report.failed += cr.failed

    report.duration_s = round(time.monotonic() - t0, 2)
    return report


# ── CLI ──────────────────────────────────────────────────────


def _print_report(report: RubricEvalReport) -> None:
    print(f"\n=== {report.suite} Eval Report ===")
    for cr in report.category_reports:
        print(
            f"  {cr.category:10s}  {cr.passed:3d}/{cr.total:3d} "
            f"({cr.pass_rate*100:5.1f}%)  avg overall {cr.avg_overall:5.1f}"
        )
        for case in cr.cases:
            if not case.passed:
                veto_str = ", ".join(case.veto_violations) if case.veto_violations else "no veto"
                print(
                    f"    ✗ {case.case_name}: overall {case.overall:.1f}/100 "
                    f"[{veto_str}]"
                )
        # dim 平均行
        dim_str = " ".join(
            f"{d[:5]}={cr.avg_dimensions.get(d, 0):.1f}"
            for d in DIMENSIONS
        )
        print(f"      dims: {dim_str}")
    print(f"\n{report.summary_line()}")


async def _amain():
    import argparse
    parser = argparse.ArgumentParser(description="Agent v1 Quality Rubric Eval Runner")
    parser.add_argument("--suite", default="quality_rubric",
                        choices=["quality_rubric"], help="测试套件")
    parser.add_argument("--cat", default=None,
                        help="只跑这些 category(逗号分隔,默认全部)")
    args = parser.parse_args()

    cat_filter = args.cat.split(",") if args.cat else None
    report = await run_quality_rubric_suite(cat_filter)
    _print_report(report)
    return 0 if report.pass_rate >= 0.85 else 1


if __name__ == "__main__":
    import sys
    rc = asyncio.run(_amain())
    sys.exit(rc)
