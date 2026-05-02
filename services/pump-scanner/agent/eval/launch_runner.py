"""
Launch Criteria Eval Runner — 62 项上线门槛静态契约 + sign-off 跟踪

引用 docs/agent-pm/17-tech-plan.md Phase 4 — 62 项 Launch Criteria 100%
  - 12 Tech sign-off:工程
  - 7 Product:PM(种子用户 20 人 + NPS ≥ 30)
  - 14 Safety:安全 lead(灾难 L1/L2/L3 100% 修复 + AE 对抗 + 13 CB 演练)
  - 12 Legal:法务最终签字(CN/US/EU)
  - 12 Cost/Ops:Ops lead(月预算 ≤ $1500 + Incident SOP + Kill Switch 演练)
  - 5 HITL:10 触发 + 5/15/60min 超时 + 生物认证

设计:
  每条 criterion 是一个静态可机器验证或 sign-off 跟踪的 check_item。
  分两种 check_type:
    - automated:有具体 python check 函数,本框架直接跑(file/import/regex/registry)
    - manual:需人工签字(legal/PM/safety lead),只跟踪状态

  Status enum:
    - automated_pass        自动检查通过
    - automated_fail        自动检查失败
    - pending_signoff       等签字
    - signed_off            已签字(JSON 中标 signed_off=true 视为通过)
    - not_applicable        v1 N/A
    - blocked               依赖未实施(KMS / 真 LLM judge 等留 W7-W12)

  Pass 判定:automated_pass + signed_off + not_applicable 算 pass;其他都算 fail。

CLI:
  python -m agent.eval.launch_runner --suite=launch_criteria [--cat=tech]
"""
from __future__ import annotations
import asyncio
import importlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

GOLDEN_DIR = Path(__file__).parent / "golden"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT.parent.parent  # /Users/wenruiwei/Desktop/Agent-Trading

# ── Status enum ──────────────────────────────────────────────

STATUS_PASS = {"automated_pass", "signed_off", "not_applicable"}
STATUS_FAIL = {"automated_fail", "pending_signoff", "blocked"}

VALID_STATUSES = STATUS_PASS | STATUS_FAIL


# ── Criterion ────────────────────────────────────────────────


@dataclass
class CriterionItem:
    name: str
    category: str
    description: str
    check_type: str            # "automated" | "manual"
    owner: str = ""
    # automated 专用
    check_fn: Optional[str] = None
    check_args: Dict[str, Any] = field(default_factory=dict)
    # manual 专用
    signed_off: bool = False
    blocking_reason: Optional[str] = None
    not_applicable_reason: Optional[str] = None


@dataclass
class CriterionResult:
    name: str
    category: str
    status: str
    failure_reason: Optional[str] = None
    latency_ms: int = 0


@dataclass
class CategoryReport:
    category: str
    total: int
    passed: int
    failed: int
    items: List[CriterionResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total


@dataclass
class LaunchEvalReport:
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

    @property
    def all_categories_100(self) -> bool:
        return all(cr.passed == cr.total for cr in self.category_reports)

    def summary_line(self) -> str:
        return (
            f"[Eval {self.suite}] {self.passed}/{self.total} criteria "
            f"({self.pass_rate*100:.1f}%) in {self.duration_s:.2f}s"
        )


# ── automated check 函数(name → impl)── ────────────────────


def _check_file_exists(args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    rel = args.get("path", "")
    fp = (REPO_ROOT / rel) if not rel.startswith("/") else Path(rel)
    if fp.exists():
        return True, None
    return False, f"file not found: {rel}"


def _check_module_importable(args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    mod_name = args.get("module", "")
    try:
        importlib.import_module(mod_name)
        return True, None
    except Exception as e:
        return False, f"{mod_name} import failed: {e}"


def _check_attr_exists(args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    mod_name = args.get("module", "")
    attr = args.get("attr", "")
    try:
        mod = importlib.import_module(mod_name)
        if hasattr(mod, attr):
            return True, None
        return False, f"{mod_name}.{attr} 缺"
    except Exception as e:
        return False, f"{mod_name} import failed: {e}"


def _check_tool_count(args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    min_count = int(args.get("min", 13))
    try:
        from agent.tools import get_tool_registry
        n = len(get_tool_registry())
        if n >= min_count:
            return True, None
        return False, f"Tool 数量 {n} < {min_count}"
    except Exception as e:
        return False, f"tool registry 加载失败: {e}"


def _check_safety_engine_loaded(args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """30 HR + 13 CB + 5 C 都加载。"""
    try:
        from agent.safety_engine import get_safety_engine
        eng = get_safety_engine()
        n_hr = len(getattr(eng, "hard_rules", []) or [])
        n_cb = len(getattr(eng, "circuit_breakers", []) or [])
        n_c = len(getattr(eng, "constitutional", []) or [])
        if n_hr >= 30 and n_cb >= 13 and n_c >= 5:
            return True, None
        return False, f"HR={n_hr} CB={n_cb} C={n_c}(期望 30/13/5)"
    except Exception as e:
        return False, f"safety_engine 加载失败: {e}"


def _check_skill_count(args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    min_count = int(args.get("min", 7))
    try:
        from agent.skills.loader import SkillLoader
        loader = SkillLoader()
        loader.load_all()
        n = len(loader.list_skills())
        if n >= min_count:
            return True, None
        return False, f"Skill 数量 {n} < {min_count}"
    except Exception as e:
        return False, f"SkillLoader 加载失败: {e}"


def _check_prompt_count(args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    min_count = int(args.get("min", 18))
    try:
        from agent.prompt_loader import PromptLoader
        loader = PromptLoader()
        loader.load_from_disk()
        n = len(loader.list_prompts())
        if n >= min_count:
            return True, None
        return False, f"Prompt 数量 {n} < {min_count}"
    except Exception as e:
        return False, f"PromptLoader 加载失败: {e}"


def _check_main_cron_id(args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """复用 chain_runner 的 cron_registered grep 逻辑。"""
    job_id = args.get("job_id", "")
    try:
        from agent.eval.chain_runner import _check_cron_registered
        return _check_cron_registered(job_id)
    except Exception as e:
        return False, f"check_cron 抛错: {e}"


def _check_route_registered(args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    try:
        from agent.eval.chain_runner import _check_route_registered as f
        return f(
            args.get("path", ""),
            args.get("method", "POST"),
            args.get("module", "api.routes_agent"),
        )
    except Exception as e:
        return False, f"check_route 抛错: {e}"


def _check_safety_ae_severity(args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """同步跑 safety AE,要求指定 severity 达门槛(避免异步嵌套)。"""
    sev = args.get("severity", "SEV-0")
    try:
        from agent.eval.safety_runner import (
            _list_ae_ids, _load_golden_safety_cases, _run_one_case,
            SEVERITY_THRESHOLDS,
        )
        threshold = SEVERITY_THRESHOLDS.get(sev, 1.0)
        total = passed = 0
        for ae_id in _list_ae_ids():
            for case in _load_golden_safety_cases(ae_id):
                if case.severity != sev:
                    continue
                cr = _run_one_case(case)
                total += 1
                if cr.passed:
                    passed += 1
        if total == 0:
            return True, None  # 无该 severity 案例,视为通过
        rate = passed / total
        if rate >= threshold:
            return True, None
        return False, f"{sev}: {rate*100:.1f}% < {threshold*100:.0f}% ({passed}/{total})"
    except Exception as e:
        return False, f"safety eval 抛错: {e}"


def _check_l4_trajectory_threshold(args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """同步跑 L4 Trajectory,要求 pass rate ≥ 85%。"""
    try:
        from agent.eval.trajectory_runner import (
            _list_categories, _load_golden_trajectory_cases, _run_trajectory,
        )
        total = passed = 0
        for cat in _list_categories():
            for case in _load_golden_trajectory_cases(cat):
                tcr = _run_trajectory(case)
                total += 1
                if tcr.passed:
                    passed += 1
        if total == 0:
            return True, None
        rate = passed / total
        if rate >= 0.85:
            return True, None
        return False, f"trajectory pass rate {rate*100:.1f}% < 85% ({passed}/{total})"
    except Exception as e:
        return False, f"l4 eval 抛错: {e}"


def _check_input_filter_classes(args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """input_filter 5 attack class 全在。"""
    expected = {
        "PROMPT_INJECTION_REGEX", "HITL_BYPASS_REGEX",
        "REGULATION_SKIRT_REGEX", "IMPLICIT_PROMISE_REGEX", "HYPE_EXTENDED_REGEX",
    }
    try:
        import agent.input_filter as mod
        present = set(dir(mod))
        missing = expected - present
        if missing:
            return False, f"input_filter 缺: {missing}"
        return True, None
    except Exception as e:
        return False, f"input_filter import 失败: {e}"


# 注册表
CHECK_FN_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Tuple[bool, Optional[str]]]] = {
    "file_exists": _check_file_exists,
    "module_importable": _check_module_importable,
    "attr_exists": _check_attr_exists,
    "tool_count": _check_tool_count,
    "safety_engine_loaded": _check_safety_engine_loaded,
    "skill_count": _check_skill_count,
    "prompt_count": _check_prompt_count,
    "main_cron_id": _check_main_cron_id,
    "route_registered": _check_route_registered,
    "safety_ae_severity": _check_safety_ae_severity,
    "l4_trajectory_threshold": _check_l4_trajectory_threshold,
    "input_filter_classes": _check_input_filter_classes,
}


# ── case runner ──────────────────────────────────────────────


def _run_one_criterion(item: CriterionItem) -> CriterionResult:
    t0 = time.monotonic()
    # not_applicable / blocked / signed_off:直接按 marker 返
    if item.not_applicable_reason:
        status = "not_applicable"
        reason = None
    elif item.blocking_reason:
        status = "blocked"
        reason = item.blocking_reason
    elif item.check_type == "manual":
        if item.signed_off:
            status = "signed_off"
            reason = None
        else:
            status = "pending_signoff"
            reason = "等待 sign-off"
    elif item.check_type == "automated":
        fn_name = item.check_fn
        if not fn_name or fn_name not in CHECK_FN_REGISTRY:
            status = "automated_fail"
            reason = f"未知 check_fn: {fn_name}"
        else:
            try:
                ok, err = CHECK_FN_REGISTRY[fn_name](item.check_args or {})
                status = "automated_pass" if ok else "automated_fail"
                reason = err if not ok else None
            except Exception as e:
                status = "automated_fail"
                reason = f"check_fn 抛错: {e}"
    else:
        status = "automated_fail"
        reason = f"未知 check_type: {item.check_type}"

    latency_ms = int((time.monotonic() - t0) * 1000)
    return CriterionResult(
        name=item.name, category=item.category, status=status,
        failure_reason=reason, latency_ms=latency_ms,
    )


# ── golden loader ────────────────────────────────────────────


def _load_golden_criteria(category: str) -> List[CriterionItem]:
    fp = GOLDEN_DIR / "launch_criteria" / f"{category}.json"
    if not fp.exists():
        return []
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("[launch_eval] golden load %s failed: %s", fp, e)
        return []
    items = []
    for it in (data.get("criteria") or []):
        items.append(CriterionItem(
            name=it.get("name", "unnamed"),
            category=category,
            description=it.get("description", ""),
            check_type=it.get("check_type", "manual"),
            owner=it.get("owner", ""),
            check_fn=it.get("check_fn"),
            check_args=it.get("check_args") or {},
            signed_off=bool(it.get("signed_off", False)),
            blocking_reason=it.get("blocking_reason"),
            not_applicable_reason=it.get("not_applicable_reason"),
        ))
    return items


def _list_categories() -> List[str]:
    d = GOLDEN_DIR / "launch_criteria"
    if not d.exists():
        return []
    return sorted([fp.stem for fp in d.glob("*.json")])


# ── public runner ────────────────────────────────────────────


async def run_launch_criteria_suite(
    cat_filter: Optional[List[str]] = None,
) -> LaunchEvalReport:
    t0 = time.monotonic()
    cats = _list_categories()
    if cat_filter:
        cats = [c for c in cats if c in cat_filter]

    report = LaunchEvalReport(suite="launch_criteria")
    for cat in cats:
        items = _load_golden_criteria(cat)
        cr = CategoryReport(category=cat, total=len(items), passed=0, failed=0)
        for item in items:
            res = _run_one_criterion(item)
            cr.items.append(res)
            if res.status in STATUS_PASS:
                cr.passed += 1
            else:
                cr.failed += 1
        report.category_reports.append(cr)
        report.total += cr.total
        report.passed += cr.passed
        report.failed += cr.failed

    report.duration_s = round(time.monotonic() - t0, 2)
    return report


# ── CLI ──────────────────────────────────────────────────────


def _print_report(report: LaunchEvalReport) -> None:
    print(f"\n=== {report.suite} Eval Report ===")
    for cr in report.category_reports:
        rate = cr.pass_rate * 100
        print(
            f"  {cr.category:10s}  {cr.passed:3d}/{cr.total:3d} ({rate:5.1f}%)"
        )
        for item in cr.items:
            if item.status not in STATUS_PASS:
                print(f"    ✗ {item.name} [{item.status}]: {item.failure_reason}")
    print(f"\n{report.summary_line()}")
    print(f"all_categories_100 = {report.all_categories_100}")


async def _amain():
    import argparse
    parser = argparse.ArgumentParser(description="Agent v1 Launch Criteria Eval Runner")
    parser.add_argument("--suite", default="launch_criteria",
                        choices=["launch_criteria"], help="测试套件")
    parser.add_argument("--cat", default=None,
                        help="只跑这些 category(逗号分隔,默认全部)")
    args = parser.parse_args()

    cat_filter = args.cat.split(",") if args.cat else None
    report = await run_launch_criteria_suite(cat_filter)
    _print_report(report)
    # exit code:任一 category 不达 100% → 1
    return 0 if report.all_categories_100 else 1


if __name__ == "__main__":
    import sys
    rc = asyncio.run(_amain())
    sys.exit(rc)
