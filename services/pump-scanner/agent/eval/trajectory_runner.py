"""
Trajectory Eval Runner — L4 多轮场景静态契约校验框架

引用 docs/agent-pm/17-tech-plan.md Phase 4 L4 Trajectory (20 场景多轮 ≥85%)
引用 agent/orchestration/cocreation_state_machine.py:STAGE_TRANSITIONS
引用 agent/loops/{chat,thesis,notify,reflect,scout}_loop.py
引用 agent/eval/chain_runner.py:_check_route_registered(复用)

设计:
  L4 真实施需 LLM cassette 驱动多轮对话。本框架先做**静态轨迹契约**:
  把每个用户旅程拆成 N 个 step,每 step 有一个 action_type,runner 验证
  对应处理器/路由/工具/状态转移**存在 + 合法**。

  这能保证:任何旅程在不真跑的情况下,确认系统**结构上能支撑**它走完。
  W7-W12 加 LLM cassette 后,把 step 升级成"真跑该 step 期望产物"。

4 个 trajectory category(对齐 04-agent-spec.md 主旅程):
  - cocreation:用户共创策略(idle→clarifying→refining→dry_run→confirming→saved)
  - trading:策略触发→Notify→HITL→执行(scout→notify→approval→execute)
  - reflect:反思周期→规则提议→晋升(daily/count/emergency cron 路径)
  - thesis:用户问 thesis(L1/L2/L3 不同 level 路径)

action 5 类(每 step):
  - "class_method"      指定类有指定 method(class_loadable + method_present)
  - "stage_transition"  state machine STAGE_TRANSITIONS 包含 from→to
  - "tool_call"         指定 tool 在 Tool registry
  - "route_call"        指定 FastAPI 路径已注册(复用 chain_runner._check_route_registered)
  - "side_effect"       指定模块的指定函数存在(push_service.send_push 等)

CLI:
  python -m agent.eval.trajectory_runner --suite=l4_trajectory [--cat=cocreation]
"""
from __future__ import annotations
import asyncio
import importlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

GOLDEN_DIR = Path(__file__).parent / "golden"


@dataclass
class TrajectoryStep:
    name: str
    action_type: str
    description: str = ""
    # action-specific 字段:
    cls_module: Optional[str] = None
    cls_name: Optional[str] = None
    method: Optional[str] = None
    from_stage: Optional[str] = None
    to_stage: Optional[str] = None
    tool_name: Optional[str] = None
    route_path: Optional[str] = None
    route_method: str = "POST"
    route_module: str = "api.routes_agent"
    side_effect_module: Optional[str] = None
    side_effect_fn: Optional[str] = None


@dataclass
class GoldenTrajectoryCase:
    name: str
    category: str         # cocreation / trading / reflect / thesis
    description: str = ""
    steps: List[TrajectoryStep] = field(default_factory=list)


@dataclass
class StepResult:
    step_name: str
    action_type: str
    passed: bool
    failure_reason: Optional[str] = None


@dataclass
class TrajectoryCaseResult:
    case_name: str
    category: str
    total_steps: int
    passed_steps: int
    failed_steps: int
    step_results: List[StepResult] = field(default_factory=list)
    latency_ms: int = 0

    @property
    def passed(self) -> bool:
        return self.failed_steps == 0


@dataclass
class CategoryReport:
    category: str
    total_trajectories: int
    passed_trajectories: int
    failed_trajectories: int
    total_steps: int
    passed_steps: int
    failed_steps: int
    cases: List[TrajectoryCaseResult] = field(default_factory=list)

    @property
    def trajectory_pass_rate(self) -> float:
        if self.total_trajectories == 0:
            return 0.0
        return self.passed_trajectories / self.total_trajectories

    @property
    def step_pass_rate(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return self.passed_steps / self.total_steps


@dataclass
class TrajectoryEvalReport:
    suite: str
    category_reports: List[CategoryReport] = field(default_factory=list)
    total_trajectories: int = 0
    passed_trajectories: int = 0
    failed_trajectories: int = 0
    total_steps: int = 0
    passed_steps: int = 0
    failed_steps: int = 0
    duration_s: float = 0.0

    @property
    def trajectory_pass_rate(self) -> float:
        if self.total_trajectories == 0:
            return 0.0
        return self.passed_trajectories / self.total_trajectories

    @property
    def step_pass_rate(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return self.passed_steps / self.total_steps

    def summary_line(self) -> str:
        return (
            f"[Eval {self.suite}] {self.passed_trajectories}/{self.total_trajectories} "
            f"trajectories ({self.trajectory_pass_rate*100:.1f}%) "
            f"+ {self.passed_steps}/{self.total_steps} steps "
            f"({self.step_pass_rate*100:.1f}%) in {self.duration_s:.2f}s"
        )


# ── action-specific checks ──────────────────────────────────


def _check_class_method(module: str, cls: str, method: str) -> Tuple[bool, Optional[str]]:
    try:
        mod = importlib.import_module(module)
        c = getattr(mod, cls, None)
        if c is None:
            return False, f"{module} 缺类 {cls}"
        m = getattr(c, method, None)
        if m is None:
            return False, f"{cls} 缺方法 {method}"
        return True, None
    except Exception as e:
        return False, f"check_class_method 抛错: {e}"


def _check_stage_transition(from_stage: str, to_stage: str) -> Tuple[bool, Optional[str]]:
    try:
        from agent.orchestration.cocreation_state_machine import (
            STAGE_TRANSITIONS, VALID_STAGES,
        )
    except Exception as e:
        return False, f"state machine import 失败: {e}"
    if from_stage not in VALID_STAGES:
        return False, f"非法 from_stage: {from_stage}"
    if to_stage not in VALID_STAGES:
        return False, f"非法 to_stage: {to_stage}"
    if to_stage not in STAGE_TRANSITIONS.get(from_stage, []):
        return False, f"非法 transition: {from_stage} → {to_stage}"
    return True, None


def _check_tool_call(tool_name: str) -> Tuple[bool, Optional[str]]:
    try:
        from agent.tools import get_tool_registry
        registry = get_tool_registry()
    except Exception as e:
        return False, f"tool registry 加载失败: {e}"
    if tool_name not in registry:
        return False, f"未注册工具: {tool_name}"
    return True, None


def _check_route_call(
    route_path: str, method: str, route_module: str,
) -> Tuple[bool, Optional[str]]:
    """复用 chain_runner._check_route_registered。"""
    from agent.eval.chain_runner import _check_route_registered
    return _check_route_registered(route_path, method, route_module)


def _check_side_effect(module: str, fn_name: str) -> Tuple[bool, Optional[str]]:
    try:
        mod = importlib.import_module(module)
        fn = getattr(mod, fn_name, None)
        if fn is None:
            return False, f"{module} 缺函数 {fn_name}"
        if not callable(fn):
            return False, f"{module}.{fn_name} 不可调用"
        return True, None
    except Exception as e:
        return False, f"check_side_effect 抛错: {e}"


# ── step runner ──────────────────────────────────────────────


def _run_step(step: TrajectoryStep) -> StepResult:
    at = step.action_type
    try:
        if at == "class_method":
            if not (step.cls_module and step.cls_name and step.method):
                return StepResult(step.name, at, False, "缺 cls_module/cls_name/method")
            ok, err = _check_class_method(step.cls_module, step.cls_name, step.method)
        elif at == "stage_transition":
            if not (step.from_stage and step.to_stage):
                return StepResult(step.name, at, False, "缺 from_stage/to_stage")
            ok, err = _check_stage_transition(step.from_stage, step.to_stage)
        elif at == "tool_call":
            if not step.tool_name:
                return StepResult(step.name, at, False, "缺 tool_name")
            ok, err = _check_tool_call(step.tool_name)
        elif at == "route_call":
            if step.route_path is None:
                return StepResult(step.name, at, False, "缺 route_path")
            ok, err = _check_route_call(
                step.route_path, step.route_method, step.route_module,
            )
        elif at == "side_effect":
            if not (step.side_effect_module and step.side_effect_fn):
                return StepResult(step.name, at, False, "缺 side_effect_module/fn")
            ok, err = _check_side_effect(
                step.side_effect_module, step.side_effect_fn,
            )
        else:
            return StepResult(step.name, at, False, f"未知 action_type: {at}")
    except Exception as e:
        return StepResult(step.name, at, False, f"step 执行抛错: {e}")
    return StepResult(step.name, at, ok, None if ok else err)


def _run_trajectory(case: GoldenTrajectoryCase) -> TrajectoryCaseResult:
    t0 = time.monotonic()
    res = TrajectoryCaseResult(
        case_name=case.name, category=case.category,
        total_steps=len(case.steps), passed_steps=0, failed_steps=0,
    )
    for step in case.steps:
        sr = _run_step(step)
        res.step_results.append(sr)
        if sr.passed:
            res.passed_steps += 1
        else:
            res.failed_steps += 1
    res.latency_ms = int((time.monotonic() - t0) * 1000)
    return res


# ── golden loader ────────────────────────────────────────────


def _step_from_dict(d: Dict[str, Any]) -> TrajectoryStep:
    return TrajectoryStep(
        name=d.get("name", "unnamed"),
        action_type=d.get("action_type", ""),
        description=d.get("description", ""),
        cls_module=d.get("cls_module"),
        cls_name=d.get("cls_name"),
        method=d.get("method"),
        from_stage=d.get("from_stage"),
        to_stage=d.get("to_stage"),
        tool_name=d.get("tool_name"),
        route_path=d.get("route_path"),
        route_method=d.get("route_method", "POST"),
        route_module=d.get("route_module", "api.routes_agent"),
        side_effect_module=d.get("side_effect_module"),
        side_effect_fn=d.get("side_effect_fn"),
    )


def _load_golden_trajectory_cases(category: str) -> List[GoldenTrajectoryCase]:
    fp = GOLDEN_DIR / "l4_trajectory" / f"{category}.json"
    if not fp.exists():
        return []
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("[traj_eval] golden load %s failed: %s", fp, e)
        return []
    cases = []
    for item in (data.get("cases") or []):
        cases.append(GoldenTrajectoryCase(
            name=item.get("name", "unnamed"),
            category=category,
            description=item.get("description", ""),
            steps=[_step_from_dict(s) for s in (item.get("steps") or [])],
        ))
    return cases


def _list_categories() -> List[str]:
    d = GOLDEN_DIR / "l4_trajectory"
    if not d.exists():
        return []
    return sorted([fp.stem for fp in d.glob("*.json")])


# ── public runner ────────────────────────────────────────────


async def run_l4_trajectory_suite(
    cat_filter: Optional[List[str]] = None,
) -> TrajectoryEvalReport:
    t0 = time.monotonic()
    cats = _list_categories()
    if cat_filter:
        cats = [c for c in cats if c in cat_filter]

    report = TrajectoryEvalReport(suite="l4_trajectory")
    for cat in cats:
        cases = _load_golden_trajectory_cases(cat)
        cr = CategoryReport(
            category=cat,
            total_trajectories=len(cases),
            passed_trajectories=0, failed_trajectories=0,
            total_steps=0, passed_steps=0, failed_steps=0,
        )
        for case in cases:
            tcr = _run_trajectory(case)
            cr.cases.append(tcr)
            cr.total_steps += tcr.total_steps
            cr.passed_steps += tcr.passed_steps
            cr.failed_steps += tcr.failed_steps
            if tcr.passed:
                cr.passed_trajectories += 1
            else:
                cr.failed_trajectories += 1
        report.category_reports.append(cr)
        report.total_trajectories += cr.total_trajectories
        report.passed_trajectories += cr.passed_trajectories
        report.failed_trajectories += cr.failed_trajectories
        report.total_steps += cr.total_steps
        report.passed_steps += cr.passed_steps
        report.failed_steps += cr.failed_steps

    report.duration_s = round(time.monotonic() - t0, 2)
    return report


# ── CLI ──────────────────────────────────────────────────────


def _print_report(report: TrajectoryEvalReport) -> None:
    print(f"\n=== {report.suite} Eval Report ===")
    for cr in report.category_reports:
        traj_rate = cr.trajectory_pass_rate * 100
        step_rate = cr.step_pass_rate * 100
        print(
            f"  {cr.category:12s}  trajectories {cr.passed_trajectories:2d}/{cr.total_trajectories:2d} "
            f"({traj_rate:5.1f}%)  steps {cr.passed_steps:3d}/{cr.total_steps:3d} ({step_rate:5.1f}%)"
        )
        for tcr in cr.cases:
            if not tcr.passed:
                print(f"    ✗ {tcr.case_name}:")
                for sr in tcr.step_results:
                    if not sr.passed:
                        print(f"        - {sr.step_name} [{sr.action_type}]: {sr.failure_reason}")
    print(f"\n{report.summary_line()}")


async def _amain():
    import argparse
    parser = argparse.ArgumentParser(description="Agent v1 L4 Trajectory Eval Runner")
    parser.add_argument("--suite", default="l4_trajectory",
                        choices=["l4_trajectory"], help="测试套件")
    parser.add_argument("--cat", default=None,
                        help="只跑这些 category(逗号分隔,默认全部)")
    args = parser.parse_args()

    cat_filter = args.cat.split(",") if args.cat else None
    report = await run_l4_trajectory_suite(cat_filter)
    _print_report(report)
    # exit code:trajectory pass rate < 85% → 1(对齐 17-tech-plan)
    return 0 if report.trajectory_pass_rate >= 0.85 else 1


if __name__ == "__main__":
    import sys
    rc = asyncio.run(_amain())
    sys.exit(rc)
