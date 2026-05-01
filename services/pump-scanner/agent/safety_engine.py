"""
Safety Engine — runtime check 入口
引用 docs/agent-pm/08-safety-policy.md + docs/agent-pm/17-tech-plan.md Phase 0

加载 safety_policy.yaml → 构建 30 HR + 13 CB + 5 C 规则集
fail-safe: 加载失败 → 整个 Agent 进入 BLOCKED(CB12)

调用方:
  - agent/trade_executor.py: T08 execute_swap pre_condition 全校验
  - agent/loops/notify_loop.py: 触发前
  - agent/loops/chat_loop.py: LLM 调用前(C 规则的 user_message blocklist)
  - api/routes_*: 中间件层

状态:🔴 v0.1 占位(W3-W4 实施)
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any
from pathlib import Path
import yaml
import logging

log = logging.getLogger(__name__)

POLICY_PATH = Path(__file__).parent / "safety_policy.yaml"


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    BLOCK = "BLOCK"


class CheckOutcome(str, Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class CheckResult:
    rule_id: str
    rule_name: str
    outcome: CheckOutcome
    reason: str | None = None
    payload: dict[str, Any] | None = None


class SafetyEngine:
    """单例;启动时加载 yaml,fail-safe 走 BLOCKED。"""

    def __init__(self) -> None:
        self.hard_rules: list[dict] = []
        self.circuit_breakers: list[dict] = []
        self.constitutional: list[dict] = []
        self.loaded: bool = False
        self.load_error: str | None = None

    def load(self) -> None:
        try:
            with POLICY_PATH.open("r", encoding="utf-8") as f:
                policy = yaml.safe_load(f)
            self.hard_rules = policy.get("hard_rules", [])
            self.circuit_breakers = policy.get("circuit_breakers", [])
            self.constitutional = policy.get("constitutional", [])
            self.loaded = True
            log.info(
                "[SafetyEngine] loaded HR=%d CB=%d C=%d",
                len(self.hard_rules),
                len(self.circuit_breakers),
                len(self.constitutional),
            )
        except Exception as e:
            self.load_error = str(e)
            self.loaded = False
            log.critical(
                "[SafetyEngine] FAIL-SAFE: policy load failed → BLOCKED. err=%s", e
            )

    # ----- HR 检查入口(trade_executor 调) -----
    def check_trade(self, ctx: dict) -> list[CheckResult]:
        """对一笔潜在交易跑全部 HR;返回所有 BLOCK 结果。
        ctx 包括: amount_usd, device_id, chain, token_address, action, regime, ...
        TODO: 逐条实施 HR01-HR30 对照 yaml.check 字段
        """
        if not self.loaded:
            return [
                CheckResult(
                    rule_id="CB12",
                    rule_name="safety_policy 加载失败 fail-safe BLOCKED",
                    outcome=CheckOutcome.BLOCK,
                    reason=self.load_error or "policy not loaded",
                )
            ]
        results: list[CheckResult] = []
        # TODO: HR01-HR30 实施
        return results

    # ----- CB 状态查询 -----
    def is_breaker_active(self, cb_id: str) -> bool:
        """检查指定 CB 是否在冷却期内。
        TODO: 配合 agent_global_state 表实施
        """
        return False

    # ----- Constitutional 检查(LLM 输出过滤,output_filter.py 调) -----
    def check_constitutional(self, text: str, persona: str) -> list[CheckResult]:
        """对 LLM 输出文本跑 C1-C5;blocklist 用 regex,语义判断由 output_filter 调 LLM judge。
        TODO: 实施
        """
        if not self.loaded:
            return []
        return []


# 全局单例
_engine: SafetyEngine | None = None


def get_safety_engine() -> SafetyEngine:
    global _engine
    if _engine is None:
        _engine = SafetyEngine()
        _engine.load()
    return _engine
