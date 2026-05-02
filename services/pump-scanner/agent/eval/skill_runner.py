"""
Skill Eval Runner — L2 Skill metadata + spec 校验框架

引用 docs/agent-pm/17-tech-plan.md Phase 4 L2 Skill integration
引用 docs/agent-pm/05-tool-catalog.md §5.4 Skill spec
引用 agent/skills/loader.py:SkillLoader / SkillMeta

设计:
  本框架只验 Skill 的 metadata 合规 + golden case 静态契约,
  **不调 LLM**(LLM cassette / mock 留 W17-W22 复盘真实 eval)。

  L2 真实施需 LLM mock(VCR 录回放)+ 输出 schema 校验 + Quality Rubric LLM-judge,
  本轮先把骨架定下来,可扩展到 ~50 cases/Skill = 350 cases。

GoldenSkillCase:
  expected_outcome:
    - "metadata_ok"          静态校验 metadata 合规
    - "loaded_full_content"  加载完整 SKILL.md content,验非空 + min_length
    - "tools_required_known" tools_required 列表中的 tool 存在 registry

CLI:
  python -m agent.eval.skill_runner --suite=l2_skill [--skill=S01]
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

GOLDEN_DIR = Path(__file__).parent / "golden"

# Skill metadata 必填字段(对齐 17-tech-plan + Anthropic Skill spec)
REQUIRED_META_FIELDS = (
    "skill_id", "name", "description",
    "tools_required", "model", "version",
)

# Skill description 最小长度(辨识度要求)
MIN_DESCRIPTION_LEN = 30

# SKILL.md body 最小长度(Persona + Rules + Output 至少要写明)
MIN_BODY_LEN = 200


@dataclass
class GoldenSkillCase:
    name: str
    skill_id: str
    expected_outcome: str  # metadata_ok | loaded_full_content | tools_required_known
    description: str = ""
    expect_fields: Optional[Dict[str, Any]] = None  # subset 校验


@dataclass
class SkillCaseResult:
    case_name: str
    passed: bool
    actual_outcome: str
    failure_reason: Optional[str] = None
    latency_ms: int = 0


@dataclass
class SkillReport:
    skill_id: str
    skill_name: str
    total: int
    passed: int
    failed: int
    metadata_ok: bool = True
    metadata_issues: List[str] = field(default_factory=list)
    cases: List[SkillCaseResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total


@dataclass
class SkillEvalReport:
    suite: str  # 'l2_skill'
    skill_reports: List[SkillReport] = field(default_factory=list)
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


def _validate_skill_metadata(skill_id: str, meta: Any) -> "tuple[bool, List[str]]":
    """检 SkillMeta 必填字段 + 合理性。"""
    issues: List[str] = []
    if meta is None:
        return False, [f"{skill_id} 未在 SkillLoader 注册"]
    if meta.skill_id != skill_id:
        issues.append(
            f"meta.skill_id='{meta.skill_id}' 不匹配 expected '{skill_id}'"
        )
    if not meta.name:
        issues.append("name 缺失")
    if not meta.description or len(meta.description) < MIN_DESCRIPTION_LEN:
        issues.append(
            f"description 太短(<{MIN_DESCRIPTION_LEN} 字符,Loop 选 Skill 时辨识度不够)"
        )
    if not meta.tools_required:
        issues.append("tools_required 为空(Skill 一定要绑 Tool)")
    if not meta.model or not meta.model.startswith("claude-"):
        issues.append(f"model 不合法: {meta.model}")
    if not meta.version:
        issues.append("version 缺失")
    return len(issues) == 0, issues


def _check_tools_known(meta: Any) -> "tuple[bool, Optional[str]]":
    """tools_required 中每个 tool 都应在 Tool registry 里。"""
    try:
        from agent.tools import get_tool_registry
        registry = get_tool_registry()
    except Exception as e:
        return False, f"tool registry 加载失败: {e}"
    unknown = [t for t in meta.tools_required if t not in registry]
    if unknown:
        return False, f"tools_required 含未注册工具: {unknown}"
    return True, None


def _check_full_content(loader: Any, skill_id: str) -> "tuple[bool, Optional[str]]":
    """SKILL.md body 应至少 MIN_BODY_LEN 字符(避免空骨架)。"""
    body = loader.load_full(skill_id)
    if body is None:
        return False, "load_full 返 None"
    if len(body) < MIN_BODY_LEN:
        return False, f"body 太短: {len(body)} < {MIN_BODY_LEN}"
    return True, None


# ── case runner ──────────────────────────────────────────────


def _run_one_case(loader: Any, meta: Any, case: GoldenSkillCase) -> SkillCaseResult:
    """跑单条 case → SkillCaseResult。"""
    t0 = time.monotonic()
    expected = case.expected_outcome
    actual: str
    reason: Optional[str] = None

    try:
        if expected == "metadata_ok":
            ok, issues = _validate_skill_metadata(case.skill_id, meta)
            actual = "metadata_ok" if ok else "metadata_invalid"
            if not ok:
                reason = "; ".join(issues[:3])
        elif expected == "loaded_full_content":
            ok, err = _check_full_content(loader, case.skill_id)
            actual = "loaded_full_content" if ok else "load_failed"
            if not ok:
                reason = err
        elif expected == "tools_required_known":
            ok, err = _check_tools_known(meta)
            actual = "tools_required_known" if ok else "tools_unknown"
            if not ok:
                reason = err
        elif expected == "expect_fields":
            # subset 校验 SkillMeta 字段
            ok = True
            mismatch = None
            for k, v in (case.expect_fields or {}).items():
                actual_val = getattr(meta, k, None)
                if isinstance(v, list) and isinstance(actual_val, list):
                    if not set(v).issubset(set(actual_val)):
                        ok = False
                        mismatch = f"{k}: missing {set(v) - set(actual_val)}"
                        break
                elif actual_val != v:
                    ok = False
                    mismatch = f"{k}: 实际 {actual_val} 期望 {v}"
                    break
            actual = "expect_fields" if ok else "expect_fields_mismatch"
            if not ok:
                reason = mismatch
        else:
            actual = "unknown_outcome"
            reason = f"未知 expected_outcome: {expected}"
    except Exception as e:
        actual = "exception"
        reason = f"case 执行抛错: {e}"

    latency_ms = int((time.monotonic() - t0) * 1000)
    passed = (expected == actual)
    return SkillCaseResult(
        case_name=case.name, passed=passed,
        actual_outcome=actual, failure_reason=reason if not passed else None,
        latency_ms=latency_ms,
    )


# ── golden loader ────────────────────────────────────────────


def _load_golden_skill_cases(skill_id: str) -> List[GoldenSkillCase]:
    """从 golden/l2_skill/{skill_id}.json 加载 cases。"""
    fp = GOLDEN_DIR / "l2_skill" / f"{skill_id}.json"
    if not fp.exists():
        return []
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("[skill_eval] golden load %s failed: %s", fp, e)
        return []
    cases = []
    for item in (data.get("cases") or []):
        cases.append(GoldenSkillCase(
            name=item.get("name", "unnamed"),
            skill_id=skill_id,
            expected_outcome=item.get("expected_outcome", "metadata_ok"),
            description=item.get("description", ""),
            expect_fields=item.get("expect_fields"),
        ))
    return cases


# ── public runner ────────────────────────────────────────────


async def run_l2_skill_suite(
    skill_filter: Optional[List[str]] = None,
) -> SkillEvalReport:
    """跑 L2 Skill 全套 metadata eval。

    Args:
      skill_filter: 只跑这些 skill_id(None=跑全部已 load 的)
    """
    t0 = time.monotonic()
    from agent.skills.loader import SkillLoader

    loader = SkillLoader()
    loader.load_all()
    skill_ids = loader.list_skills()
    if skill_filter:
        skill_ids = [s for s in skill_ids if s in skill_filter]

    report = SkillEvalReport(suite="l2_skill")
    for skill_id in skill_ids:
        meta = loader.get_meta(skill_id)
        meta_ok, meta_issues = _validate_skill_metadata(skill_id, meta)
        cases = _load_golden_skill_cases(skill_id)

        sr = SkillReport(
            skill_id=skill_id,
            skill_name=(meta.name if meta else "?"),
            total=len(cases),
            passed=0, failed=0,
            metadata_ok=meta_ok,
            metadata_issues=meta_issues,
        )
        if not meta_ok:
            log.warning("[skill_eval] %s metadata 问题: %s", skill_id, meta_issues)

        for case in cases:
            cr = _run_one_case(loader, meta, case)
            sr.cases.append(cr)
            if cr.passed:
                sr.passed += 1
            else:
                sr.failed += 1
        report.skill_reports.append(sr)
        report.total_cases += sr.total
        report.total_passed += sr.passed
        report.total_failed += sr.failed

    report.duration_s = round(time.monotonic() - t0, 2)
    return report


# ── CLI ──────────────────────────────────────────────────────


def _print_report(report: SkillEvalReport) -> None:
    print(f"\n=== {report.suite} Eval Report ===")
    for sr in report.skill_reports:
        meta_str = "✓" if sr.metadata_ok else f"✗ {len(sr.metadata_issues)} issues"
        rate = sr.pass_rate * 100
        print(
            f"  {sr.skill_id} {sr.skill_name:32s}  {sr.passed:3d}/{sr.total:3d} "
            f"({rate:5.1f}%)  metadata: {meta_str}"
        )
        if not sr.metadata_ok:
            for iss in sr.metadata_issues[:3]:
                print(f"    ! {iss}")
        for cr in sr.cases:
            if not cr.passed:
                print(f"    ✗ {cr.case_name}: {cr.failure_reason}")
    print(f"\n{report.summary_line()}")


async def _amain():
    import argparse
    parser = argparse.ArgumentParser(description="Agent v1 L2 Skill Eval Runner")
    parser.add_argument("--suite", default="l2_skill",
                        choices=["l2_skill"], help="测试套件")
    parser.add_argument("--skill", default=None,
                        help="只跑这些 skill(逗号分隔,默认全部)")
    args = parser.parse_args()

    skill_filter = args.skill.split(",") if args.skill else None

    if args.suite == "l2_skill":
        report = await run_l2_skill_suite(skill_filter)
    else:
        raise NotImplementedError(args.suite)

    _print_report(report)
    return 0 if report.total_failed == 0 else 1


if __name__ == "__main__":
    import sys
    rc = asyncio.run(_amain())
    sys.exit(rc)
