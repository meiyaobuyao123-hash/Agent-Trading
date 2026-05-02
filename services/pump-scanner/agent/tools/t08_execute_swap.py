"""
T08 execute_swap — 执行真金交易(包装 trade_executor.TradeExecutor.execute_trade)

引用 docs/agent-pm/05-tool-catalog.md T08
引用 services/pump-scanner/agent/trade_executor.py(已对接 Jupiter SOL + 1inch EVM + OKX fallback)

⚠️ **真金交易,最高风险 Tool** ⚠️

input(全部 required 校验,缺一即拒):
  chain: "solana" | "eth" | "bsc" | "base"
  token_address: 目标代币
  action: "buy" | "sell"
  amount_usd: 交易金额(>0,HR01 单笔 ≤ $500 由 safety_engine 拦)
  wallet_address: 钱包地址
  private_key: 钱包私钥(从 Flutter `flutter_secure_storage` iOS Keychain 取)
可选:
  slippage_pct: 滑点百分比(默认 1.0)
  safety_ctx: dict 给 SafetyEngine.check_trade(R23 D3 已加,强烈推荐传)
  idempotency_key: 调用方提供(防 retry 重复下单)

output:
  ok: bool
  success: bool(同 ok,与 TradeResult 对齐)
  tx_hash: str
  exec_price: float
  from_amount / to_amount: float
  gas_fee: float
  error: str(失败原因)
  reason: str

side_effects=BLOCKCHAIN_WRITE(NOT idempotent — 同 input 不同时 token / nonce 可能不同 tx)
permission=DEVICE_ONLY + 签名 fail-safe(无 private_key → 直接拒)
"""
from __future__ import annotations
import logging
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect

log = logging.getLogger(__name__)

VALID_CHAINS = ("solana", "eth", "bsc", "base")
VALID_ACTIONS = ("buy", "sell")
MIN_AMOUNT_USD = 1.0       # 防误触发 $0 交易
MAX_AMOUNT_USD_HARD = 10000.0  # 框架硬上限(safety_engine HR01 还会更严)


class ExecuteSwapTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="execute_swap",
            description=(
                "执行真金 DEX 交易(Jupiter SOL / 1inch EVM / OKX fallback)。"
                "需 wallet_address + private_key(从 Flutter Keychain 取);"
                "强烈建议传 safety_ctx → safety_engine pre-check(HR01-30 + 13 CB)。"
                "amount_usd ∈ [$1, $10000] 框架硬限,实际由 safety_engine HR01 = $500 拦。"
                "side_effects=BLOCKCHAIN_WRITE,**non-idempotent**,调用方需保 idempotency_key。"
            ),
            idempotent=False,
            idempotency_key_fields=["idempotency_key"],
            side_effects=SideEffect.PUSH,  # 用 PUSH 表示有外部副作用(没有 BLOCKCHAIN 枚举,PUSH 是最接近的)
            p95_latency_ms=15000,
            cost_usd=0.0,  # 0 LLM cost;但 gas 实际付费,用户钱包出
            permission=Permission.DEVICE_ONLY,
            failure_modes=[
                "INPUT_SCHEMA_INVALID",
                "MISSING_PRIVATE_KEY",
                "MISSING_WALLET_ADDRESS",
                "AMOUNT_OUT_OF_RANGE",
                "SAFETY_BLOCKED",
                "DEX_ROUTE_FAILED",
                "TX_BROADCAST_FAILED",
                "INSUFFICIENT_BALANCE",
            ],
            owner="agent-team",
            version="1.0",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "chain": {"type": "string", "enum": list(VALID_CHAINS)},
                "token_address": {"type": "string", "minLength": 1},
                "action": {"type": "string", "enum": list(VALID_ACTIONS)},
                "amount_usd": {
                    "type": "number",
                    "minimum": MIN_AMOUNT_USD,
                    "maximum": MAX_AMOUNT_USD_HARD,
                },
                "wallet_address": {"type": "string", "minLength": 1},
                "private_key": {"type": "string", "minLength": 1},
                "slippage_pct": {
                    "type": "number", "minimum": 0.1, "maximum": 50.0,
                },
                "safety_ctx": {"type": "object"},
                "idempotency_key": {"type": "string"},
            },
            "required": [
                "chain", "token_address", "action", "amount_usd",
                "wallet_address", "private_key",
            ],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "success": {"type": "boolean"},
                "tx_hash": {"type": "string"},
                "exec_price": {"type": "number"},
                "from_amount": {"type": "number"},
                "to_amount": {"type": "number"},
                "gas_fee": {"type": "number"},
                "error": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["ok", "success", "reason"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        chain = payload["chain"]
        token_address = payload["token_address"]
        action = payload["action"]
        amount_usd = float(payload["amount_usd"])
        wallet_address = payload["wallet_address"]
        private_key = payload["private_key"]
        slippage_pct = float(payload.get("slippage_pct", 1.0))
        safety_ctx = payload.get("safety_ctx")

        # 二重防御(schema 已限,这里再守一层避免绕过)
        if not wallet_address:
            return self._fail("missing_wallet_address")
        if not private_key:
            return self._fail("missing_private_key")
        if amount_usd < MIN_AMOUNT_USD:
            return self._fail(f"amount_too_small: ${amount_usd}")
        if amount_usd > MAX_AMOUNT_USD_HARD:
            return self._fail(f"amount_too_large: ${amount_usd}")

        try:
            from agent.trade_executor import TradeExecutor
            executor = TradeExecutor()
            try:
                result = await executor.execute_trade(
                    chain=chain,
                    token_address=token_address,
                    action=action,
                    amount_usd=amount_usd,
                    slippage_pct=slippage_pct,
                    wallet_address=wallet_address,
                    private_key=private_key,
                    safety_ctx=safety_ctx,
                )
            finally:
                # 清理 session
                try:
                    await executor.close()
                except Exception:
                    pass
        except Exception as e:
            log.error("[T08] execute_trade exception: %s", e, exc_info=True)
            return self._fail(f"executor_exception: {e}")

        if not result.success:
            err = result.error or "unknown"
            # safety_engine BLOCK 的 error 含 "safety BLOCKED" 前缀
            if "safety" in err.lower() and "block" in err.lower():
                reason = "safety_blocked"
            else:
                reason = "dex_route_failed"
            return {
                "ok": False, "success": False,
                "tx_hash": "", "exec_price": 0.0,
                "from_amount": 0.0, "to_amount": 0.0, "gas_fee": 0.0,
                "error": err, "reason": reason,
            }

        return {
            "ok": True, "success": True,
            "tx_hash": result.tx_hash or "",
            "exec_price": float(result.price or 0),
            "from_amount": float(result.from_amount or 0),
            "to_amount": float(result.to_amount or 0),
            "gas_fee": float(result.gas_fee or 0),
            "error": "",
            "reason": "executed",
        }

    @staticmethod
    def _fail(reason: str) -> dict:
        return {
            "ok": False, "success": False,
            "tx_hash": "", "exec_price": 0.0,
            "from_amount": 0.0, "to_amount": 0.0, "gas_fee": 0.0,
            "error": reason, "reason": reason,
        }
