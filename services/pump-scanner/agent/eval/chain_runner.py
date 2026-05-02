"""
Chain Eval Runner — L3 Agentic Chain 静态结构校验框架

引用 docs/agent-pm/17-tech-plan.md Phase 4 L3 Agentic chain (4 chain × ≥10 = 40)
引用 agent/loops/{chat,thesis,notify,reflect,scout}_loop.py
引用 main.py(cron 注册)
引用 api/routes_agent.py(端点路由)

设计:
  本框架只验 Chain 的**静态可用性**(类可加载 / 入口方法存在 / 依赖 tool 全在 registry /
  路由注册 / cron 已注册),**不真跑 chain**(W7-W12 配 LLM cassette 后再实施真 chain eval)。

  4 个 Chain(对齐 docs/agent-pm/04-agent-spec.md):
    - **thesis**:chat → S08 → 3 路 analyst → P02 → debate → final thesis(ThesisLoop)
    - **notify**:strategy.triggered → safety pre-check → RiskManager → T17 → mode 分支 → T13(NotifyLoop)
    - **reflect**:cron 20:00 / 10 笔 / 单笔 < -25% → load trades → review_engine → reflection(ReflectLoop)
    - **cocreation**:idle → clarifying → refining → dry_run → confirming → saved(CocreationLoop)

GoldenChainCase 5 outcome 类型:
  - "class_loadable"        Loop 类可 import + 实例化
  - "entry_method_present"  Loop 类有指定的入口 async method
  - "tools_wired"           Loop 声明的 required_tools 全在 Tool registry
  - "route_registered"      指定的 FastAPI 路径 + method 已注册
  - "cron_registered"       指定的 cron job_id 已注册到 scheduler

CLI:
  python -m agent.eval.chain_runner --suite=l3_chain [--chain=thesis]
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
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

GOLDEN_DIR = Path(__file__).parent / "golden"

# Chain 名称 → 模块 + 类
CHAIN_REGISTRY: Dict[str, Dict[str, str]] = {
    "thesis": {"module": "agent.loops.thesis_loop", "class": "ThesisLoop"},
    "notify": {"module": "agent.loops.notify_loop", "class": "NotifyLoop"},
    "reflect": {"module": "agent.loops.reflect_loop", "class": "ReflectLoop"},
    "cocreation": {"module": "agent.loops.chat_loop", "class": "CocreationLoop"},
    "scout": {"module": "agent.loops.scout_loop", "class": "ScoutLoop"},
}


@dataclass
class GoldenChainCase:
    name: str
    chain_id: str
    expected_outcome: str
    description: str = ""
    entry_method: Optional[str] = None         # entry_method_present 时
    required_tools: Optional[List[str]] = None # tools_wired 时
    route_path: Optional[str] = None           # route_registered 时
    route_method: str = "POST"                 # route_registered 时
    route_module: str = "api.routes_agent"     # route_registered 时(默认 routes_agent)
    cron_job_id: Optional[str] = None          # cron_registered 时


@dataclass
class ChainCaseResult:
    case_name: str
    passed: bool
    actual_outcome: str
    failure_reason: Optional[str] = None
    latency_ms: int = 0


@dataclass
class ChainReport:
    chain_id: str
    total: int
    passed: int
    failed: int
    cases: List[ChainCaseResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total


@dataclass
class ChainEvalReport:
    suite: str
    chain_reports: List[ChainReport] = field(default_factory=list)
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


# ── case-specific checks ─────────────────────────────────────


def _check_class_loadable(chain_id: str) -> Tuple[bool, Optional[str]]:
    """Loop 类可 import + 实例化(无 args)。"""
    info = CHAIN_REGISTRY.get(chain_id)
    if not info:
        return False, f"chain '{chain_id}' 未在 CHAIN_REGISTRY 注册"
    try:
        mod = importlib.import_module(info["module"])
        cls = getattr(mod, info["class"], None)
        if cls is None:
            return False, f"模块 {info['module']} 缺类 {info['class']}"
        # 实例化(Loop 类构造函数应无必填 args)
        cls()
        return True, None
    except Exception as e:
        return False, f"加载/实例化失败: {e}"


def _check_entry_method(chain_id: str, method_name: str) -> Tuple[bool, Optional[str]]:
    """Loop 类有指定的 async method(主入口)。"""
    info = CHAIN_REGISTRY.get(chain_id)
    if not info:
        return False, f"chain '{chain_id}' 未注册"
    try:
        mod = importlib.import_module(info["module"])
        cls = getattr(mod, info["class"], None)
        if cls is None:
            return False, f"缺类 {info['class']}"
        method = getattr(cls, method_name, None)
        if method is None:
            return False, f"缺方法 {method_name}"
        if not asyncio.iscoroutinefunction(method):
            return False, f"{method_name} 不是 async 方法"
        return True, None
    except Exception as e:
        return False, f"check_entry_method 抛错: {e}"


def _check_tools_wired(required_tools: List[str]) -> Tuple[bool, Optional[str]]:
    """required_tools 全在 Tool registry。"""
    try:
        from agent.tools import get_tool_registry
        registry = get_tool_registry()
    except Exception as e:
        return False, f"tool registry 加载失败: {e}"
    unknown = [t for t in required_tools if t not in registry]
    if unknown:
        return False, f"未注册工具: {unknown}"
    return True, None


def _check_route_registered(
    route_path: str, method: str = "POST",
    route_module: str = "api.routes_agent",
) -> Tuple[bool, Optional[str]]:
    """指定的 FastAPI 路径 + method 已注册到 {route_module}.router。

    优先 import + router 检查;失败时降级到 source grep
    (避免 Py3.9 不支持 PEP 604 联合类型注解 `dict | None` 时整段 fail)。
    """
    method_upper = method.upper()
    try:
        mod = importlib.import_module(route_module)
        router = getattr(mod, "router", None)
        if router is not None:
            for r in router.routes:
                path = getattr(r, "path", None)
                methods = getattr(r, "methods", None) or set()
                if path == route_path and method_upper in methods:
                    return True, None
            return False, f"未注册: {method_upper} {route_path} in {route_module}"
    except Exception:
        pass

    # 降级:source grep
    try:
        rel_path = route_module.replace(".", "/") + ".py"
        src_path = Path(__file__).resolve().parents[2] / rel_path
        if not src_path.exists():
            return False, f"源码 {rel_path} not found"
        text = src_path.read_text(encoding="utf-8")
        # 匹配 @router.{method}("path") — 容忍 prefix 因为 routes 内部不带 /api/agent
        # 用户传 route_path 是含 prefix 的,grep 用 endswith 匹配
        decorator_re = re.compile(
            rf'@router\.{method_upper.lower()}\(\s*[\'"]([^\'"]*)[\'"]'
        )
        matched_paths = decorator_re.findall(text)
        # 匹配规则:用户传的路径以 found path 结尾(prefix 由 mount 决定)
        for found in matched_paths:
            if route_path.endswith(found) and found != "":
                return True, None
            if route_path == "" and found == "":
                return True, None
        return False, (
            f"source grep 未找到 @router.{method_upper.lower()}('{route_path}') "
            f"in {rel_path}"
        )
    except Exception as e:
        return False, f"source grep 抛错: {e}"


def _check_cron_registered(job_id: str) -> Tuple[bool, Optional[str]]:
    """检查 main.py 源码中是否有指定 id= 的 add_job 调用(避免真启动 scheduler)。"""
    try:
        main_path = Path(__file__).resolve().parents[2] / "main.py"
        if not main_path.exists():
            return False, "main.py not found"
        text = main_path.read_text(encoding="utf-8")
        # 匹配 id="job_id" 或 id='job_id'
        pattern = re.compile(rf'\bid\s*=\s*[\'"]{re.escape(job_id)}[\'"]')
        if pattern.search(text):
            return True, None
        return False, f"main.py 未注册 cron job_id={job_id}"
    except Exception as e:
        return False, f"check_cron 抛错: {e}"


# ── case runner ──────────────────────────────────────────────


def _run_one_case(case: GoldenChainCase) -> ChainCaseResult:
    t0 = time.monotonic()
    expected = case.expected_outcome
    actual: str
    reason: Optional[str] = None

    try:
        if expected == "class_loadable":
            ok, err = _check_class_loadable(case.chain_id)
            actual = "class_loadable" if ok else "class_load_failed"
            reason = err if not ok else None
        elif expected == "entry_method_present":
            if not case.entry_method:
                ok, err = False, "case 未指定 entry_method"
            else:
                ok, err = _check_entry_method(case.chain_id, case.entry_method)
            actual = "entry_method_present" if ok else "entry_method_missing"
            reason = err if not ok else None
        elif expected == "tools_wired":
            if not case.required_tools:
                ok, err = False, "case 未指定 required_tools"
            else:
                ok, err = _check_tools_wired(case.required_tools)
            actual = "tools_wired" if ok else "tools_missing"
            reason = err if not ok else None
        elif expected == "route_registered":
            # route_path 允许 ""(routes_thesis 用空字符串挂主入口)
            if case.route_path is None:
                ok, err = False, "case 未指定 route_path"
            else:
                ok, err = _check_route_registered(
                    case.route_path, case.route_method, case.route_module,
                )
            actual = "route_registered" if ok else "route_missing"
            reason = err if not ok else None
        elif expected == "cron_registered":
            if not case.cron_job_id:
                ok, err = False, "case 未指定 cron_job_id"
            else:
                ok, err = _check_cron_registered(case.cron_job_id)
            actual = "cron_registered" if ok else "cron_missing"
            reason = err if not ok else None
        else:
            actual = "unknown_outcome"
            reason = f"未知 expected_outcome: {expected}"
    except Exception as e:
        actual = "exception"
        reason = f"case 执行抛错: {e}"

    latency_ms = int((time.monotonic() - t0) * 1000)
    passed = (expected == actual)
    return ChainCaseResult(
        case_name=case.name, passed=passed,
        actual_outcome=actual, failure_reason=reason if not passed else None,
        latency_ms=latency_ms,
    )


# ── golden loader ────────────────────────────────────────────


def _load_golden_chain_cases(chain_id: str) -> List[GoldenChainCase]:
    fp = GOLDEN_DIR / "l3_chain" / f"{chain_id}.json"
    if not fp.exists():
        return []
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("[chain_eval] golden load %s failed: %s", fp, e)
        return []
    cases = []
    for item in (data.get("cases") or []):
        cases.append(GoldenChainCase(
            name=item.get("name", "unnamed"),
            chain_id=chain_id,
            expected_outcome=item.get("expected_outcome", "class_loadable"),
            description=item.get("description", ""),
            entry_method=item.get("entry_method"),
            required_tools=item.get("required_tools"),
            route_path=item.get("route_path"),
            route_method=item.get("route_method", "POST"),
            route_module=item.get("route_module", "api.routes_agent"),
            cron_job_id=item.get("cron_job_id"),
        ))
    return cases


# ── public runner ────────────────────────────────────────────


async def run_l3_chain_suite(
    chain_filter: Optional[List[str]] = None,
) -> ChainEvalReport:
    t0 = time.monotonic()
    chain_ids = sorted(CHAIN_REGISTRY.keys())
    if chain_filter:
        chain_ids = [c for c in chain_ids if c in chain_filter]

    report = ChainEvalReport(suite="l3_chain")
    for chain_id in chain_ids:
        cases = _load_golden_chain_cases(chain_id)
        cr_report = ChainReport(
            chain_id=chain_id, total=len(cases), passed=0, failed=0,
        )
        for case in cases:
            cr = _run_one_case(case)
            cr_report.cases.append(cr)
            if cr.passed:
                cr_report.passed += 1
            else:
                cr_report.failed += 1
        report.chain_reports.append(cr_report)
        report.total_cases += cr_report.total
        report.total_passed += cr_report.passed
        report.total_failed += cr_report.failed

    report.duration_s = round(time.monotonic() - t0, 2)
    return report


# ── CLI ──────────────────────────────────────────────────────


def _print_report(report: ChainEvalReport) -> None:
    print(f"\n=== {report.suite} Eval Report ===")
    for cr_report in report.chain_reports:
        rate = cr_report.pass_rate * 100
        print(
            f"  {cr_report.chain_id:12s}  {cr_report.passed:3d}/{cr_report.total:3d} "
            f"({rate:5.1f}%)"
        )
        for cr in cr_report.cases:
            if not cr.passed:
                print(f"    ✗ {cr.case_name}: {cr.failure_reason}")
    print(f"\n{report.summary_line()}")


async def _amain():
    import argparse
    parser = argparse.ArgumentParser(description="Agent v1 L3 Chain Eval Runner")
    parser.add_argument("--suite", default="l3_chain",
                        choices=["l3_chain"], help="测试套件")
    parser.add_argument("--chain", default=None,
                        help="只跑这些 chain(逗号分隔,默认全部)")
    args = parser.parse_args()

    chain_filter = args.chain.split(",") if args.chain else None

    if args.suite == "l3_chain":
        report = await run_l3_chain_suite(chain_filter)
    else:
        raise NotImplementedError(args.suite)

    _print_report(report)
    return 0 if report.total_failed == 0 else 1


if __name__ == "__main__":
    import sys
    rc = asyncio.run(_amain())
    sys.exit(rc)
