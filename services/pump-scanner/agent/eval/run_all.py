"""
Run All Eval — 一键跑所有 9 个 eval suite,聚合 pass/fail 总结

引用 docs/agent-pm/eval-summary.md(Phase 4 sign-off)
引用 docs/runbook/eval-runbook.md(Ops 实操)

设计:
  对应 9 个 eval suite,顺序跑、统一格式、每 suite 一行汇总,最后总览。
  exit code:任一 suite "硬门槛"(SEV-0 / Pearson 0.7 / Tech 100%)失败 → 1
  这是 CI 的入口(pre-deploy gate)+ Ops 的快速 health check。

CLI:
  python -m agent.eval.run_all                  # 跑全部
  python -m agent.eval.run_all --json           # 输出 JSON(给 CI parse)
  python -m agent.eval.run_all --skip launch    # 跳过 launch(开发期免 17 blocked 干扰)
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


# 9 suite + 是否 hard gate(任一 hard gate 失败 → run_all 失败)
SUITES: List[Dict[str, Any]] = [
    {
        "name": "l1_tool",
        "module": "agent.eval.runner",
        "fn": "run_l1_tool_suite",
        "hard_gate": True,  # L1 Tool 100% 必须
    },
    {
        "name": "l2_skill",
        "module": "agent.eval.skill_runner",
        "fn": "run_l2_skill_suite",
        "hard_gate": True,
    },
    {
        "name": "l1_prompt",
        "module": "agent.eval.prompt_runner",
        "fn": "run_l1_prompt_suite",
        "hard_gate": True,
    },
    {
        "name": "l3_chain",
        "module": "agent.eval.chain_runner",
        "fn": "run_l3_chain_suite",
        "hard_gate": True,
    },
    {
        "name": "safety_ae",
        "module": "agent.eval.safety_runner",
        "fn": "run_safety_ae_suite",
        "hard_gate": True,  # SEV-0 100% 必须
    },
    {
        "name": "l4_trajectory",
        "module": "agent.eval.trajectory_runner",
        "fn": "run_l4_trajectory_suite",
        "hard_gate": True,  # ≥85%
    },
    {
        "name": "launch_criteria",
        "module": "agent.eval.launch_runner",
        "fn": "run_launch_criteria_suite",
        "hard_gate": False,  # 17 blocked milestone-gated,GA 前 100%
    },
    {
        "name": "quality_rubric",
        "module": "agent.eval.rubric_runner",
        "fn": "run_quality_rubric_suite",
        "hard_gate": False,  # heuristic baseline 60,LLM-judge 80 留 W17-W22
    },
    {
        "name": "judge_calibration",
        "module": "agent.eval.judge_runner",
        "fn": "run_judge_calibration",
        "hard_gate": True,  # Pearson ≥ 0.7 + Safety 100%
    },
]


@dataclass
class SuiteResult:
    name: str
    total: int
    passed: int
    failed: int
    pass_rate: float
    hard_gate: bool
    duration_s: float
    extra: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def hard_gate_passed(self) -> bool:
        if not self.hard_gate:
            return True
        # 每个 suite 自己的 hard gate 判定
        if self.name == "l1_tool":
            return self.pass_rate >= 1.0  # 严格 100%
        if self.name == "l2_skill":
            return self.pass_rate >= 1.0
        if self.name == "l1_prompt":
            return self.pass_rate >= 1.0
        if self.name == "l3_chain":
            return self.pass_rate >= 1.0
        if self.name == "safety_ae":
            return bool(self.extra.get("all_severities_meet_threshold", False))
        if self.name == "l4_trajectory":
            return self.pass_rate >= 0.85
        if self.name == "judge_calibration":
            return bool(self.extra.get("passes", False))
        return self.pass_rate >= 0.85


@dataclass
class RunAllReport:
    suite_results: List[SuiteResult] = field(default_factory=list)
    total_duration_s: float = 0.0

    @property
    def all_hard_gates_passed(self) -> bool:
        return all(s.hard_gate_passed for s in self.suite_results)

    @property
    def total_cases(self) -> int:
        return sum(s.total for s in self.suite_results)

    @property
    def total_passed(self) -> int:
        return sum(s.passed for s in self.suite_results)

    def to_json(self) -> Dict[str, Any]:
        return {
            "all_hard_gates_passed": self.all_hard_gates_passed,
            "total_duration_s": self.total_duration_s,
            "total_cases": self.total_cases,
            "total_passed": self.total_passed,
            "suites": [
                {
                    "name": s.name,
                    "total": s.total, "passed": s.passed, "failed": s.failed,
                    "pass_rate": s.pass_rate,
                    "hard_gate": s.hard_gate,
                    "hard_gate_passed": s.hard_gate_passed,
                    "duration_s": s.duration_s,
                    "extra": s.extra,
                    "error": s.error,
                }
                for s in self.suite_results
            ],
        }


async def _run_suite(spec: Dict[str, Any]) -> SuiteResult:
    import importlib
    t0 = time.monotonic()
    name = spec["name"]
    try:
        mod = importlib.import_module(spec["module"])
        fn = getattr(mod, spec["fn"])
        report = await fn()
    except Exception as e:
        return SuiteResult(
            name=name, total=0, passed=0, failed=0, pass_rate=0.0,
            hard_gate=spec["hard_gate"],
            duration_s=round(time.monotonic() - t0, 2),
            error=str(e),
        )

    # 各 suite report shape 略有差异 — 统一拍平
    extra: Dict[str, Any] = {}
    if name == "l1_tool":
        total, passed, failed = report.total_cases, report.total_passed, report.total_failed
        rate = report.pass_rate
    elif name in ("l2_skill", "l1_prompt"):
        total, passed, failed = report.total_cases, report.total_passed, report.total_failed
        rate = report.pass_rate
    elif name == "l3_chain":
        total, passed, failed = report.total_cases, report.total_passed, report.total_failed
        rate = report.pass_rate
    elif name == "safety_ae":
        total, passed, failed = report.total_cases, report.total_passed, report.total_failed
        rate = report.pass_rate
        extra["all_severities_meet_threshold"] = report.all_severities_meet_threshold
        extra["sev_breakdown"] = {
            sr.severity: f"{sr.passed}/{sr.total} ({sr.pass_rate*100:.1f}%)"
            for sr in report.severity_reports
        }
    elif name == "l4_trajectory":
        # trajectory 用 trajectory_pass_rate(更代表"完整旅程")
        total, passed, failed = (
            report.total_trajectories,
            report.passed_trajectories,
            report.failed_trajectories,
        )
        rate = report.trajectory_pass_rate
        extra["step_pass_rate"] = report.step_pass_rate
        extra["total_steps"] = report.total_steps
    elif name == "launch_criteria":
        total, passed, failed = report.total, report.passed, report.failed
        rate = report.pass_rate
        extra["all_categories_100"] = report.all_categories_100
        extra["per_category"] = {
            cr.category: f"{cr.passed}/{cr.total}"
            for cr in report.category_reports
        }
    elif name == "quality_rubric":
        total, passed, failed = report.total, report.passed, report.failed
        rate = report.pass_rate
    elif name == "judge_calibration":
        # total = #dims(10),passed = pass-threshold dims;不要把 N=100 sample 当 total
        total = len(report.dim_results)
        passed = sum(1 for d in report.dim_results.values() if d.passes_threshold)
        failed = total - passed
        rate = passed / total if total else 0
        extra["passes"] = report.passes
        extra["n_samples"] = report.total_samples
        extra["pearsons"] = {
            d.dimension: d.pearson for d in report.dim_results.values()
        }
    else:
        total, passed, failed, rate = 0, 0, 0, 0.0

    return SuiteResult(
        name=name, total=total, passed=passed, failed=failed,
        pass_rate=rate, hard_gate=spec["hard_gate"],
        duration_s=round(time.monotonic() - t0, 2),
        extra=extra,
    )


async def run_all(skip: Optional[List[str]] = None) -> RunAllReport:
    t0 = time.monotonic()
    skip_set = set(skip or [])
    report = RunAllReport()
    for spec in SUITES:
        if spec["name"] in skip_set:
            continue
        result = await _run_suite(spec)
        report.suite_results.append(result)
    report.total_duration_s = round(time.monotonic() - t0, 2)
    return report


# ── CLI ──────────────────────────────────────────────────────


def _print_text(report: RunAllReport) -> None:
    print("\n=== Eval Run All ===")
    print(
        f"{'suite':18s} {'pass':>10s} {'rate':>7s} {'gate':>6s} {'time':>7s}  notes"
    )
    print("-" * 80)
    for s in report.suite_results:
        gate = "✓" if s.hard_gate_passed else ("-" if not s.hard_gate else "✗")
        rate_pct = f"{s.pass_rate*100:5.1f}%"
        time_str = f"{s.duration_s:5.2f}s"
        notes = ""
        if s.error:
            notes = f"ERROR: {s.error[:40]}"
        elif s.name == "safety_ae":
            sev = s.extra.get("sev_breakdown", {})
            notes = " ".join(f"{k}={v.split('(')[1].split(')')[0]}" for k, v in sev.items())
        elif s.name == "judge_calibration":
            notes = "passes" if s.extra.get("passes") else "FAIL"
        elif s.name == "launch_criteria":
            notes = "100%" if s.extra.get("all_categories_100") else "milestone-gated"
        print(
            f"  {s.name:16s} {s.passed:>4d}/{s.total:<5d} {rate_pct:>7s} {gate:>6s} {time_str:>7s}  {notes}"
        )
    print("-" * 80)
    print(
        f"  TOTAL              {report.total_passed:>4d}/{report.total_cases:<5d}  "
        f"all_hard_gates={'✓' if report.all_hard_gates_passed else '✗'}  "
        f"{report.total_duration_s:5.2f}s"
    )


async def _amain():
    import argparse
    parser = argparse.ArgumentParser(description="Agent v1 Eval Run All")
    parser.add_argument("--skip", default="",
                        help="逗号分隔 suite 跳过(eg. launch_criteria)")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 给 CI parse")
    args = parser.parse_args()

    skip = [s.strip() for s in args.skip.split(",") if s.strip()]
    report = await run_all(skip=skip)

    if args.json:
        print(json.dumps(report.to_json(), ensure_ascii=False, indent=2))
    else:
        _print_text(report)

    return 0 if report.all_hard_gates_passed else 1


if __name__ == "__main__":
    import sys
    rc = asyncio.run(_amain())
    sys.exit(rc)
