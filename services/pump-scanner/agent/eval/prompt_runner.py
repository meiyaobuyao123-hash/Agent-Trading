"""
Prompt Eval Runner — L1 Prompt 静态契约校验框架

引用 docs/agent-pm/17-tech-plan.md Phase 4 L1 Prompt unit (18 P × ≥30 = 540)
引用 docs/agent-pm/07-prompt-library.md
引用 agent/prompt_loader.py:PromptLoader / PromptSpec

设计:
  本框架只验 Prompt 的**静态契约 + 安全 + 渲染**,**不调 LLM**(LLM-judge 留 W17-W22)。

  L1 Prompt 真实施(540 cases × 90% pass + Safety 100%)需 LLM 输出抽样 + judge,
  本轮先把骨架定下来,可扩展到 ~30 case/Prompt = 540 cases。

GoldenPromptCase 6 outcome 类型:
  - "metadata_ok"            frontmatter 必填字段合规
  - "render_ok"              {{var}} 占位符全部替换 + 无未替换
  - "render_missing_vars"    缺变量时占位符保留(不爆错)
  - "examples_safe"          examples.md 中 assistant 输出无 C1 blocklist 命中
  - "examples_count_min"     few-shot 例子 ≥ N 条(默认 3)
  - "version_select"         给定 device_id 选出符合预期 status 的 version

CLI:
  python -m agent.eval.prompt_runner --suite=l1_prompt [--prompt=P01]
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

GOLDEN_DIR = Path(__file__).parent / "golden"

# Prompt frontmatter 必填字段
REQUIRED_FM_FIELDS = (
    "prompt_id", "version", "model",
    "max_input_tokens", "max_output_tokens",
)

MIN_DESCRIPTION_LEN = 30
MIN_PROMPT_BODY_LEN = 200

# C1 blocklist (与 agent/output_filter.py 同步)
C1_BLOCKLIST_REGEX = re.compile(
    r"(稳的|百倍|千倍|暴涨|错过就亏|guaranteed|to the moon|ape in|10\s*x|100\s*x)",
    re.IGNORECASE,
)

# 未替换的 {{var}} 占位符
UNRENDERED_VAR_RE = re.compile(r"\{\{\s*[\w.]+\s*\}\}")


@dataclass
class GoldenPromptCase:
    name: str
    prompt_id: str
    expected_outcome: str
    description: str = ""
    vars: Optional[Dict[str, Any]] = None         # render_ok 时填入
    expected_unrendered: Optional[List[str]] = None  # render_missing_vars 时
    min_examples: int = 3                          # examples_count_min 时
    device_id: Optional[str] = None                # version_select 时
    expected_status: Optional[str] = None          # version_select 时


@dataclass
class PromptCaseResult:
    case_name: str
    passed: bool
    actual_outcome: str
    failure_reason: Optional[str] = None
    latency_ms: int = 0


@dataclass
class PromptReport:
    prompt_id: str
    total: int
    passed: int
    failed: int
    metadata_ok: bool = True
    metadata_issues: List[str] = field(default_factory=list)
    cases: List[PromptCaseResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total


@dataclass
class PromptEvalReport:
    suite: str
    prompt_reports: List[PromptReport] = field(default_factory=list)
    total_cases: int = 0
    total_passed: int = 0
    total_failed: int = 0
    duration_s: float = 0.0

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.total_passed / self.total_cases

    def summary_line(self) -> str:
        return (
            f"[Eval {self.suite}] {self.total_passed}/{self.total_cases} passed "
            f"({self.pass_rate*100:.1f}%) in {self.duration_s:.2f}s"
        )


# ── metadata validators ──────────────────────────────────────


def _validate_prompt_metadata(prompt_id: str, spec: Any) -> "tuple[bool, List[str]]":
    """检 PromptSpec frontmatter 必填字段 + 合理性。"""
    issues: List[str] = []
    if spec is None:
        return False, [f"{prompt_id} 未在 PromptLoader 注册"]
    if spec.prompt_id != prompt_id:
        issues.append(f"prompt_id='{spec.prompt_id}' 不匹配 expected '{prompt_id}'")
    if not spec.version:
        issues.append("version 缺失")
    if not spec.model or not spec.model.startswith("claude-"):
        issues.append(f"model 不合法: {spec.model}")
    if spec.temperature < 0 or spec.temperature > 1.5:
        issues.append(f"temperature 越界: {spec.temperature}")
    if spec.max_input_tokens <= 0 or spec.max_input_tokens > 200000:
        issues.append(f"max_input_tokens 不合理: {spec.max_input_tokens}")
    if spec.max_output_tokens <= 0 or spec.max_output_tokens > 8192:
        issues.append(f"max_output_tokens 不合理: {spec.max_output_tokens}")
    if not spec.description or len(spec.description) < MIN_DESCRIPTION_LEN:
        issues.append(
            f"description 太短(<{MIN_DESCRIPTION_LEN} chars,Loop 选 prompt 时辨识度不够)"
        )
    if not spec.content or len(spec.content) < MIN_PROMPT_BODY_LEN:
        issues.append(
            f"prompt body 太短(<{MIN_PROMPT_BODY_LEN} chars,缺 Persona/Rules/Output 之一)"
        )
    if spec.status not in ("draft", "canary", "beta", "ga", "retired"):
        issues.append(f"status 非法: {spec.status}")
    if spec.rollout_pct < 0 or spec.rollout_pct > 100:
        issues.append(f"rollout_pct 越界: {spec.rollout_pct}")
    return len(issues) == 0, issues


# ── case-specific checks ─────────────────────────────────────


def _check_render_ok(loader: Any, spec: Any, vars: Dict[str, Any]) -> "tuple[bool, Optional[str]]":
    """变量字典完整时:渲染后不应剩任何 {{var}}。"""
    rendered = loader.render(spec.prompt_id, "test-device", vars)
    leftover = UNRENDERED_VAR_RE.findall(rendered)
    if leftover:
        return False, f"未替换占位符: {leftover[:5]}"
    return True, None


def _check_render_missing_vars(
    loader: Any, spec: Any, vars: Optional[Dict[str, Any]],
    expected_unrendered: Optional[List[str]],
) -> "tuple[bool, Optional[str]]":
    """变量缺失时:占位符应**保留**(便于上层补)而不是抛错。"""
    try:
        rendered = loader.render(spec.prompt_id, "test-device", vars or {})
    except Exception as e:
        return False, f"render 抛错: {e}"
    leftover = UNRENDERED_VAR_RE.findall(rendered)
    if expected_unrendered:
        miss = [v for v in expected_unrendered if v not in rendered]
        if miss:
            return False, f"期望保留的变量未保留: {miss}"
    if not leftover:
        return False, "应该有未替换占位符,但全替换了"
    return True, None


def _check_examples_safe(spec: Any) -> "tuple[bool, Optional[str]]":
    """examples 里的 assistant 输出不应触发 C1 blocklist。"""
    for i, ex in enumerate(spec.examples):
        text = (ex.get("assistant") or "") if isinstance(ex, dict) else ""
        m = C1_BLOCKLIST_REGEX.search(text)
        if m:
            return False, f"example #{i+1} assistant 命中 blocklist: '{m.group(0)}'"
    return True, None


def _check_examples_count(spec: Any, min_count: int) -> "tuple[bool, Optional[str]]":
    if len(spec.examples) < min_count:
        return False, f"few-shot 数量 {len(spec.examples)} < {min_count}"
    return True, None


def _check_version_select(
    loader: Any, prompt_id: str, device_id: str,
    expected_status: Optional[str],
) -> "tuple[bool, Optional[str]]":
    """按 device_id 选 version → status 应符合 expected。"""
    spec = loader.select_version(prompt_id, device_id)
    if spec is None:
        return False, "select_version 返 None"
    if expected_status and spec.status != expected_status:
        return False, f"status 不匹配: 实际 {spec.status} 期望 {expected_status}"
    return True, None


# ── case runner ──────────────────────────────────────────────


def _run_one_case(loader: Any, spec: Any, case: GoldenPromptCase) -> PromptCaseResult:
    t0 = time.monotonic()
    expected = case.expected_outcome
    actual: str
    reason: Optional[str] = None

    try:
        if expected == "metadata_ok":
            ok, issues = _validate_prompt_metadata(case.prompt_id, spec)
            actual = "metadata_ok" if ok else "metadata_invalid"
            if not ok:
                reason = "; ".join(issues[:3])
        elif expected == "render_ok":
            ok, err = _check_render_ok(loader, spec, case.vars or {})
            actual = "render_ok" if ok else "render_failed"
            if not ok:
                reason = err
        elif expected == "render_missing_vars":
            ok, err = _check_render_missing_vars(
                loader, spec, case.vars, case.expected_unrendered,
            )
            actual = "render_missing_vars" if ok else "render_missing_failed"
            if not ok:
                reason = err
        elif expected == "examples_safe":
            ok, err = _check_examples_safe(spec)
            actual = "examples_safe" if ok else "examples_unsafe"
            if not ok:
                reason = err
        elif expected == "examples_count_min":
            ok, err = _check_examples_count(spec, case.min_examples)
            actual = "examples_count_min" if ok else "examples_too_few"
            if not ok:
                reason = err
        elif expected == "version_select":
            ok, err = _check_version_select(
                loader, case.prompt_id,
                case.device_id or "test-device",
                case.expected_status,
            )
            actual = "version_select" if ok else "version_select_failed"
            if not ok:
                reason = err
        else:
            actual = "unknown_outcome"
            reason = f"未知 expected_outcome: {expected}"
    except Exception as e:
        actual = "exception"
        reason = f"case 执行抛错: {e}"

    latency_ms = int((time.monotonic() - t0) * 1000)
    passed = (expected == actual)
    return PromptCaseResult(
        case_name=case.name, passed=passed,
        actual_outcome=actual, failure_reason=reason if not passed else None,
        latency_ms=latency_ms,
    )


# ── golden loader ────────────────────────────────────────────


def _load_golden_prompt_cases(prompt_id: str) -> List[GoldenPromptCase]:
    fp = GOLDEN_DIR / "l1_prompt" / f"{prompt_id}.json"
    if not fp.exists():
        return []
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("[prompt_eval] golden load %s failed: %s", fp, e)
        return []
    cases = []
    for item in (data.get("cases") or []):
        cases.append(GoldenPromptCase(
            name=item.get("name", "unnamed"),
            prompt_id=prompt_id,
            expected_outcome=item.get("expected_outcome", "metadata_ok"),
            description=item.get("description", ""),
            vars=item.get("vars"),
            expected_unrendered=item.get("expected_unrendered"),
            min_examples=int(item.get("min_examples", 3)),
            device_id=item.get("device_id"),
            expected_status=item.get("expected_status"),
        ))
    return cases


# ── public runner ────────────────────────────────────────────


async def run_l1_prompt_suite(
    prompt_filter: Optional[List[str]] = None,
) -> PromptEvalReport:
    t0 = time.monotonic()
    from agent.prompt_loader import PromptLoader

    loader = PromptLoader()
    loader.load_from_disk()
    prompt_ids = loader.list_prompts()
    if prompt_filter:
        prompt_ids = [p for p in prompt_ids if p in prompt_filter]

    report = PromptEvalReport(suite="l1_prompt")
    for pid in prompt_ids:
        # 拿 draft 版(eval 默认看 draft);上层可以扩展指定 status
        versions = loader.get_versions(pid)
        if not versions:
            continue
        spec = versions[0]  # 取首个 version(通常是 draft)
        meta_ok, meta_issues = _validate_prompt_metadata(pid, spec)
        cases = _load_golden_prompt_cases(pid)

        pr = PromptReport(
            prompt_id=pid, total=len(cases),
            passed=0, failed=0,
            metadata_ok=meta_ok,
            metadata_issues=meta_issues,
        )
        if not meta_ok:
            log.warning("[prompt_eval] %s metadata 问题: %s", pid, meta_issues)

        for case in cases:
            cr = _run_one_case(loader, spec, case)
            pr.cases.append(cr)
            if cr.passed:
                pr.passed += 1
            else:
                pr.failed += 1
        report.prompt_reports.append(pr)
        report.total_cases += pr.total
        report.total_passed += pr.passed
        report.total_failed += pr.failed

    report.duration_s = round(time.monotonic() - t0, 2)
    return report


# ── CLI ──────────────────────────────────────────────────────


def _print_report(report: PromptEvalReport) -> None:
    print(f"\n=== {report.suite} Eval Report ===")
    for pr in report.prompt_reports:
        meta_str = "✓" if pr.metadata_ok else f"✗ {len(pr.metadata_issues)} issues"
        rate = pr.pass_rate * 100
        print(
            f"  {pr.prompt_id:6s}  {pr.passed:3d}/{pr.total:3d} "
            f"({rate:5.1f}%)  metadata: {meta_str}"
        )
        if not pr.metadata_ok:
            for iss in pr.metadata_issues[:3]:
                print(f"    ! {iss}")
        for cr in pr.cases:
            if not cr.passed:
                print(f"    ✗ {cr.case_name}: {cr.failure_reason}")
    print(f"\n{report.summary_line()}")


async def _amain():
    import argparse
    parser = argparse.ArgumentParser(description="Agent v1 L1 Prompt Eval Runner")
    parser.add_argument("--suite", default="l1_prompt",
                        choices=["l1_prompt"], help="测试套件")
    parser.add_argument("--prompt", default=None,
                        help="只跑这些 prompt(逗号分隔,默认全部)")
    args = parser.parse_args()

    prompt_filter = args.prompt.split(",") if args.prompt else None

    if args.suite == "l1_prompt":
        report = await run_l1_prompt_suite(prompt_filter)
    else:
        raise NotImplementedError(args.suite)

    _print_report(report)
    return 0 if report.total_failed == 0 else 1


if __name__ == "__main__":
    import sys
    rc = asyncio.run(_amain())
    sys.exit(rc)
