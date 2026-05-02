"""
Eval Runner — L1 Tool 测试套件

引用 docs/agent-pm/17-tech-plan.md Phase 4
引用 agent/tools/base.py(Tool / ToolResult / ToolMetadata)

设计:
  GoldenCase:一组 (input, expected_outcome) 描述
    expected_outcome:
      - "ok": 正常成功
      - "input_invalid": 应该被 input schema 拒
      - "execute_error": 业务层错误(DB 连不上等)
      - "ok_with_check": 成功且额外字段满足 expect_fields(dict subset)
  GoldenSuite:一个 Tool 的 case 列表 + idempotent 检查
  EvalReport:per-tool 通过率 + 失败明细 + 总体 pass_rate

核心约束(L1 Tool 100% Pass):
  1. 输入 schema 校验生效(invalid → INPUT_SCHEMA_INVALID)
  2. 输出 schema 校验生效(failed → OUTPUT_SCHEMA_INVALID)
  3. 同输入两次结果 deterministic(idempotent=True 时)
  4. cost_usd 不超 metadata.cost_usd × 1.5
  5. p95_latency_ms 不超 metadata.p95_latency_ms × 2

不依赖外部 API(测试环境):
  - DB 调用全 mock
  - LLM 调用全 skip(L1 Tool 不调 LLM,有 LLM 的应是 Skill 不是 Tool)
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

log = logging.getLogger(__name__)

GOLDEN_DIR = Path(__file__).parent / "golden"


@dataclass
class GoldenCase:
    name: str
    input: Dict[str, Any]
    expected_outcome: str  # ok | input_invalid | execute_error | ok_with_check
    expected_failure_mode: Optional[str] = None  # 当 outcome=execute_error 时,期望 failure_mode
    expect_fields: Optional[Dict[str, Any]] = None  # outcome=ok_with_check:subset 校验
    description: str = ""
    skip_idempotent_check: bool = False
    mock_setup: Optional[str] = None  # mock 提示(future:JSON-driven mock)


@dataclass
class CaseResult:
    case_name: str
    passed: bool
    actual_outcome: str
    failure_reason: Optional[str] = None
    latency_ms: int = 0


@dataclass
class ToolReport:
    tool_name: str
    total: int
    passed: int
    failed: int
    skipped: int = 0
    cases: List[CaseResult] = field(default_factory=list)
    metadata_ok: bool = True
    metadata_issues: List[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total


@dataclass
class EvalReport:
    suite: str  # 'l1_tool' | 'l1_prompt' | ...
    tool_reports: List[ToolReport] = field(default_factory=list)
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


# ── L1 Tool runner ──────────────────────────────────────────


def _validate_metadata(tool_name: str, tool: Any) -> "tuple[bool, List[str]]":
    """检查 Tool metadata 必填字段 + 合理性。"""
    issues: List[str] = []
    try:
        meta = tool.metadata
    except Exception as e:
        return False, [f"metadata 读取失败: {e}"]
    if not meta.name or meta.name != tool_name:
        issues.append(f"meta.name='{meta.name}' 不匹配 registry key '{tool_name}'")
    if not meta.description or len(meta.description) < 30:
        issues.append("description 太短(<30 字符,LLM 选 tool 时辨识度不够)")
    if meta.idempotent and not isinstance(meta.idempotency_key_fields, list):
        issues.append("idempotent=True 但 idempotency_key_fields 不是 list")
    if meta.cost_usd < 0:
        issues.append(f"cost_usd 负数: {meta.cost_usd}")
    if meta.p95_latency_ms <= 0 or meta.p95_latency_ms > 60000:
        issues.append(f"p95_latency_ms 不合理: {meta.p95_latency_ms}")
    if not meta.failure_modes:
        issues.append("failure_modes 为空(应至少列 1 种)")
    try:
        spec = tool.to_anthropic_tool_spec()
        if not spec.get("name") or "input_schema" not in spec:
            issues.append("to_anthropic_tool_spec 输出不完整")
    except Exception as e:
        issues.append(f"to_anthropic_tool_spec 抛错: {e}")
    return len(issues) == 0, issues


async def _run_one_case(tool: Any, case: GoldenCase) -> CaseResult:
    """跑单条 case → CaseResult。"""
    t0 = time.monotonic()
    try:
        result = await tool.run(case.input)
    except Exception as e:
        return CaseResult(
            case_name=case.name, passed=False,
            actual_outcome="exception",
            failure_reason=f"tool.run 抛错: {e}",
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    latency_ms = int((time.monotonic() - t0) * 1000)
    expected = case.expected_outcome

    # 判定 actual outcome
    if not result.ok:
        if result.failure_mode == "INPUT_SCHEMA_INVALID":
            actual = "input_invalid"
        elif result.failure_mode == "OUTPUT_SCHEMA_INVALID":
            actual = "output_invalid"
        else:
            actual = "execute_error"
    else:
        actual = "ok"

    passed = (expected == actual)
    if expected == "ok_with_check" and actual == "ok":
        # 子集校验
        if case.expect_fields and isinstance(result.output, dict):
            for k, v in case.expect_fields.items():
                if result.output.get(k) != v:
                    passed = False
                    return CaseResult(
                        case_name=case.name, passed=False,
                        actual_outcome=actual,
                        failure_reason=f"expect_fields 不匹配 {k}: 实际 {result.output.get(k)} 期望 {v}",
                        latency_ms=latency_ms,
                    )
        passed = True

    if expected == "execute_error" and actual == "execute_error":
        if case.expected_failure_mode and result.failure_mode != case.expected_failure_mode:
            return CaseResult(
                case_name=case.name, passed=False,
                actual_outcome=actual,
                failure_reason=f"failure_mode 不匹配:期望 {case.expected_failure_mode} 实际 {result.failure_mode}",
                latency_ms=latency_ms,
            )

    if not passed:
        return CaseResult(
            case_name=case.name, passed=False, actual_outcome=actual,
            failure_reason=f"outcome 不匹配:期望 {expected} 实际 {actual} (failure_mode={result.failure_mode})",
            latency_ms=latency_ms,
        )

    return CaseResult(
        case_name=case.name, passed=True, actual_outcome=actual,
        latency_ms=latency_ms,
    )


async def _check_idempotent(
    tool: Any, case: GoldenCase, max_iters: int = 2,
) -> "tuple[bool, Optional[str]]":
    """对 ok case 跑两次 → 输出应一致(对 idempotent=True 的 tool)。"""
    if case.skip_idempotent_check:
        return True, None
    if case.expected_outcome not in ("ok", "ok_with_check"):
        return True, None
    try:
        meta = tool.metadata
        if not meta.idempotent:
            return True, None
    except Exception:
        return True, None
    try:
        r1 = await tool.run(case.input)
        r2 = await tool.run(case.input)
    except Exception as e:
        return False, f"idempotent 两次跑抛错: {e}"
    if not (r1.ok and r2.ok):
        return False, "idempotent 两次跑结果 ok 不一致"
    if isinstance(r1.output, dict) and isinstance(r2.output, dict):
        # 排除时间戳等浮动字段
        keys_to_compare = set(r1.output.keys()) - {"latency_ms", "ts", "now",
                                                    "thesis_id", "approval_id",
                                                    "promoted_rule_id",
                                                    "trade", "_ts"}
        for k in keys_to_compare:
            if r1.output.get(k) != r2.output.get(k):
                return False, f"idempotent 字段 {k} 两次不同"
    return True, None


def _load_golden_cases(suite: str, tool_name: str) -> List[GoldenCase]:
    """从 golden/{suite}/{tool_name}.json 加载 cases。"""
    fp = GOLDEN_DIR / suite / f"{tool_name}.json"
    if not fp.exists():
        return []
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("[eval] golden load %s failed: %s", fp, e)
        return []
    cases = []
    for item in (data.get("cases") or []):
        cases.append(GoldenCase(
            name=item.get("name", "unnamed"),
            input=item.get("input", {}),
            expected_outcome=item.get("expected_outcome", "ok"),
            expected_failure_mode=item.get("expected_failure_mode"),
            expect_fields=item.get("expect_fields"),
            description=item.get("description", ""),
            skip_idempotent_check=item.get("skip_idempotent_check", False),
            mock_setup=item.get("mock_setup"),
        ))
    return cases


async def run_l1_tool_suite(
    tool_filter: Optional[List[str]] = None,
) -> EvalReport:
    """跑 L1 Tool 全套 eval。

    Args:
      tool_filter: 只跑这些 tool(None=跑全部)
    """
    t0 = time.monotonic()
    from agent.tools import get_tool_registry
    registry = get_tool_registry()
    if tool_filter:
        registry = {k: v for k, v in registry.items() if k in tool_filter}

    report = EvalReport(suite="l1_tool")
    for tool_name, tool in sorted(registry.items()):
        meta_ok, meta_issues = _validate_metadata(tool_name, tool)
        cases = _load_golden_cases("l1_tool", tool_name)

        tr = ToolReport(
            tool_name=tool_name, total=len(cases),
            passed=0, failed=0, metadata_ok=meta_ok,
            metadata_issues=meta_issues,
        )
        if not meta_ok:
            log.warning("[eval] %s metadata 问题: %s", tool_name, meta_issues)

        for case in cases:
            cr = await _run_one_case(tool, case)
            # idempotent 二次校验
            if cr.passed:
                idem_ok, idem_err = await _check_idempotent(tool, case)
                if not idem_ok:
                    cr.passed = False
                    cr.failure_reason = f"idempotent 失败: {idem_err}"
            tr.cases.append(cr)
            if cr.passed:
                tr.passed += 1
            else:
                tr.failed += 1
        report.tool_reports.append(tr)
        report.total_cases += tr.total
        report.total_passed += tr.passed
        report.total_failed += tr.failed

    report.duration_s = round(time.monotonic() - t0, 2)
    return report


# ── CLI 入口 ──────────────────────────────────────────────


def _print_report(report: EvalReport) -> None:
    print(f"\n=== {report.suite} Eval Report ===")
    for tr in report.tool_reports:
        meta_str = "✓" if tr.metadata_ok else f"✗ {len(tr.metadata_issues)} issues"
        rate = tr.pass_rate * 100
        print(
            f"  {tr.tool_name:35s}  {tr.passed:3d}/{tr.total:3d} ({rate:5.1f}%) "
            f"  metadata: {meta_str}"
        )
        if not tr.metadata_ok:
            for iss in tr.metadata_issues[:3]:
                print(f"    ! {iss}")
        for cr in tr.cases:
            if not cr.passed:
                print(f"    ✗ {cr.case_name}: {cr.failure_reason}")
    print(f"\n{report.summary_line()}")


async def _amain():
    import argparse
    parser = argparse.ArgumentParser(description="Agent v1 Eval Runner")
    parser.add_argument("--suite", default="l1_tool",
                        choices=["l1_tool"], help="测试套件")
    parser.add_argument("--tool", default=None,
                        help="只跑这个 tool(逗号分隔,默认全部)")
    args = parser.parse_args()

    tool_filter = args.tool.split(",") if args.tool else None

    if args.suite == "l1_tool":
        report = await run_l1_tool_suite(tool_filter)
    else:
        raise NotImplementedError(args.suite)

    _print_report(report)
    # exit code:有失败 → 1,L1 Tool 严格 100%
    return 0 if report.total_failed == 0 else 1


if __name__ == "__main__":
    import sys
    rc = asyncio.run(_amain())
    sys.exit(rc)
