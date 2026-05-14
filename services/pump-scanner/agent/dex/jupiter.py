"""
Jupiter v6 API — SOL 链最优 DEX 聚合器

PRD-009: 多 DEX 执行路由
- 免费，无需 API Key
- Base URL: https://quote-api.jup.ag/v6
- 流程: GET /quote → POST /swap → sign → broadcast

Python 3.9 兼容。
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import aiohttp

log = logging.getLogger(__name__)

JUPITER_BASE = "https://quote-api.jup.ag/v6"

# SOL native mint (wSOL)
SOL_MINT = "So11111111111111111111111111111111111111112"


@dataclass
class JupiterQuote:
    """Jupiter 报价结果"""
    dex: str = "jupiter"
    input_mint: str = ""
    output_mint: str = ""
    in_amount: str = "0"
    out_amount: str = "0"
    price_impact_pct: float = 0.0
    route_plan: list = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def success(self) -> bool:
        return self.error == "" and int(self.out_amount) > 0


class JupiterDex:
    """Jupiter v6 REST API 客户端"""

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self):
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    # ── 获取报价 ─────────────────────────────────────────────

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: str,
        slippage_bps: int = 100,
    ) -> JupiterQuote:
        """
        获取 Jupiter 报价

        Args:
            input_mint: 输入代币 mint 地址
            output_mint: 输出代币 mint 地址
            amount: 输入数量（最小单位，如 lamports）
            slippage_bps: 滑点（basis points, 100 = 1%）

        Returns:
            JupiterQuote
        """
        try:
            session = await self._get_session()
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": str(int(slippage_bps)),
            }

            url = f"{JUPITER_BASE}/quote"
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return JupiterQuote(error=f"HTTP {resp.status}: {text[:200]}")

                data = await resp.json()

            # Jupiter 返回 error 字段
            if "error" in data:
                return JupiterQuote(error=data["error"])

            return JupiterQuote(
                input_mint=data.get("inputMint", input_mint),
                output_mint=data.get("outputMint", output_mint),
                in_amount=str(data.get("inAmount", "0")),
                out_amount=str(data.get("outAmount", "0")),
                price_impact_pct=float(data.get("priceImpactPct", 0)),
                route_plan=data.get("routePlan", []),
                raw=data,
            )

        except Exception as e:
            log.warning(f"Jupiter quote error: {e}")
            return JupiterQuote(error=str(e))

    # ── 获取 swap 交易 ──────────────────────────────────────

    async def get_swap(
        self,
        quote_response: Dict[str, Any],
        user_public_key: str,
        wrap_unwrap_sol: bool = True,
        priority_fee_sol: float = 0.0,
        jito_tip_sol: float = 0.0,
    ) -> Dict[str, Any]:
        """
        获取 Jupiter swap 交易（base64 编码）

        Args:
            quote_response: get_quote 返回的 raw 数据
            user_public_key: 用户 Solana 公钥地址
            wrap_unwrap_sol: 是否自动 wrap/unwrap SOL
            priority_fee_sol: R64 — Solana 优先费（lamports = SOL × 1e9）
            jito_tip_sol: R64 — Jito tip（走私有 mempool 防 MEV）

        Returns:
            {"swapTransaction": "<base64>", ...} 或 {"error": "..."}
        """
        try:
            session = await self._get_session()
            url = f"{JUPITER_BASE}/swap"

            payload: Dict[str, Any] = {
                "quoteResponse": quote_response,
                "userPublicKey": user_public_key,
                "wrapAndUnwrapSol": wrap_unwrap_sol,
                # R64 — 让 Jupiter 自动估算 CU,避免 OOM
                "dynamicComputeUnitLimit": True,
            }

            # R64 — 优先费（lamports = SOL × 1e9）
            if priority_fee_sol and priority_fee_sol > 0:
                payload["prioritizationFeeLamports"] = int(priority_fee_sol * 1_000_000_000)

            # R64 — Jito tip（私有 mempool 防三明治攻击）
            # Jupiter v6 swap endpoint 支持 jitoTipLamports（写入 tx 时附带转账 Jito tip account 的 instruction）
            if jito_tip_sol and jito_tip_sol > 0:
                payload["jitoTipLamports"] = int(jito_tip_sol * 1_000_000_000)

            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return {"error": f"HTTP {resp.status}: {text[:200]}"}

                data = await resp.json()

            if "error" in data:
                return {"error": data["error"]}

            return data

        except Exception as e:
            log.warning(f"Jupiter swap error: {e}")
            return {"error": str(e)}


# ── 全局单例 ──────────────────────────────────────────────────

_instance: Optional[JupiterDex] = None


def get_jupiter_dex() -> JupiterDex:
    global _instance
    if _instance is None:
        _instance = JupiterDex()
    return _instance
