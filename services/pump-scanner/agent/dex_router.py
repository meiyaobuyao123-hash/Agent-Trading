"""
多 DEX 路由 — 比价选优 + 自动 fallback + 大单拆分

PRD-009: 多 DEX 执行路由
- SOL → Jupiter 优先, OKX fallback
- EVM → 1inch 优先 (if key configured), OKX fallback
- 并行报价, 2s 超时 (v1.1 Q10)
- price_impact > 2% 大单拆分 (v1.1 Q11)
- 每笔记录 dex_used/quotes/actual_slippage (v1.1 Q12)

Python 3.9 兼容。
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

# R71: 真实 token decimals 查询(带缓存),修 buy 路径硬编码 9/18 → entry_price 算错。
# pump.fun/SPL meme 多为 6 decimals,硬编码 9 会把价格算高 ~1000 倍 → SL/TP 全偏。
_DECIMALS_CACHE: Dict[str, int] = {}


async def _resolve_solana_decimals(mint: str, fallback: int = 9) -> int:
    """查 SPL token decimals(getTokenSupply,Helius RPC),带缓存。
    失败回退到 fallback(旧默认值)→ 绝不比修复前更糟。"""
    if not mint:
        return fallback
    if mint in _DECIMALS_CACHE:
        return _DECIMALS_CACHE[mint]
    try:
        from config import HELIUS_RPC
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getTokenSupply",
                   "params": [mint]}
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.post(HELIUS_RPC, json=payload) as r:
                data = await r.json()
        dec = int(data["result"]["value"]["decimals"])
        if 0 <= dec <= 18:
            _DECIMALS_CACHE[mint] = dec
            return dec
    except Exception as e:
        log.debug("[dex_router] decimals 查询失败 mint=%s: %s", str(mint)[:12], e)
    return fallback

log = logging.getLogger(__name__)

# ── 常量 ─────────────────────────────────────────────────────
QUOTE_TIMEOUT = 2.0        # 并行报价超时 2s (v1.1 Q10)
SPLIT_IMPACT_THRESHOLD = 0.02  # price_impact > 2% 拆分 (v1.1 Q11)
MIN_SPLIT_AMOUNT_USD = 20  # 最小拆分金额 $20
SPLIT_INTERVAL_S = 2       # 拆分间隔 2s

# 链 → primary DEX
PRIMARY_DEX = {
    "solana": "jupiter",
    "eth": "oneinch",
    "bsc": "oneinch",
    "base": "oneinch",
}

# SOL native / USDC 地址 (从 trade_executor 复用)
NATIVE_TOKEN = {
    "solana": "So11111111111111111111111111111111111111112",
    "eth": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
    "bsc": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
    "base": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
}

USDC_ADDRESS = {
    "solana": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "eth": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "bsc": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    "base": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
}

# 1inch chain IDs
ONEINCH_CHAIN_ID = {"eth": 1, "bsc": 56, "base": 8453}


@dataclass
class QuoteResult:
    """统一报价结果"""
    dex: str                   # "jupiter" / "oneinch" / "okx"
    out_amount: str = "0"      # 输出数量（最小单位）
    price_impact: float = 0.0  # 价格冲击百分比
    raw: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def success(self) -> bool:
        return self.error == "" and int(self.out_amount) > 0

    @property
    def out_amount_int(self) -> int:
        try:
            return int(self.out_amount)
        except (ValueError, TypeError):
            return 0


@dataclass
class RouteResult:
    """路由执行结果"""
    success: bool
    dex_used: str = ""
    tx_hash: str = ""
    from_amount: float = 0.0
    to_amount: float = 0.0
    price: float = 0.0
    gas_fee: float = 0.0
    error: str = ""
    chain: str = ""
    token_address: str = ""
    action: str = ""
    quotes_received: List[Dict[str, Any]] = field(default_factory=list)
    actual_slippage: float = 0.0
    fallback_used: bool = False
    split_count: int = 1


class DexRouter:
    """多 DEX 路由器"""

    def __init__(self):
        self._okx_executor = None  # lazy init

    def _get_okx_executor(self):
        """懒加载 OKX TradeExecutor"""
        if self._okx_executor is None:
            from agent.trade_executor import TradeExecutor
            self._okx_executor = TradeExecutor()
        return self._okx_executor

    async def close(self):
        if self._okx_executor:
            await self._okx_executor.close()

    # ── 主入口 ─────────────────────────────────────────────

    async def execute(
        self,
        chain: str,
        token_address: str,
        action: str,
        amount_usd: float,
        slippage_pct: float = 1.0,
        wallet_address: Optional[str] = None,
        private_key: Optional[str] = None,
        priority_fee_sol: float = 0.0005,    # R42 P0.2:Solana 优先 Gas Fee
        mev_bribe_sol: float = 0.0,          # R42 P0.2:Solana Jito MEV 贿赂(0=不走 Jito)
        user_id: Optional[str] = None,       # R47 P5:透传给 _resolve_wallet 拉 user_wallets
        request_id: Optional[str] = None,    # R59 P0:idempotency key 写入 agent_executions
    ) -> RouteResult:
        """
        多 DEX 路由执行

        1. 判断是否需要大单拆分
        2. 并行获取 primary + OKX 报价 (2s 超时)
        3. 选最优报价
        4. 执行 → 失败自动 fallback
        5. 记录路由决策

        R42 P0.2:priority_fee_sol / mev_bribe_sol 从 strategy.risk_params 透传。
        - SOL 链 + mev_bribe_sol > 0 → 走 Jito bundle(P1 WalletConnect 后真接入)
        - 其他场景 → 仅设 priority_fee 字段
        当前版本:参数已透传 + log,真实 Jito tip tx 构造留 P1。
        """
        # R42 P0.2:log 收到的 risk_params(给运维/审计追溯)
        if chain == "solana" and (priority_fee_sol > 0.0005 or mev_bribe_sol > 0):
            log.info(
                "[dex_router] R42 risk_params: priority_fee=%.4f SOL, mev_bribe=%.4f SOL "
                "(%s)", priority_fee_sol, mev_bribe_sol,
                "Jito bundle (P1 待接)" if mev_bribe_sol > 0 else "公共 mempool + 高优先",
            )

        # R47 P5 + R59 P0 — 预解析钱包(若入参未提供)。
        # 传 user_id 给 _resolve_wallet → 优先从 user_wallets AES 解密拉私钥(R42 P1 路径),
        # 否则 fallback env。预解析后的 wallet/priv 透传给所有 _execute_* 子函数。
        # R59 P0 fix: 若 user_id 提供但预解析失败 → fail-fast,不再 silent fallback 让子路径
        # 调 _resolve_wallet 时丢 user_id → 用 DEV_WALLET 替用户签字(audit 揭露的真 bug)。
        if (not wallet_address or not private_key) and user_id:
            try:
                executor = self._get_okx_executor()
                resolved_addr, resolved_key = executor._resolve_wallet(
                    chain, wallet_address, private_key, user_id=user_id,
                )
                if resolved_addr and resolved_key:
                    wallet_address = resolved_addr
                    private_key = resolved_key
                    log.info(
                        "[dex_router] R47 P5 钱包预解析成功 user=%s chain=%s addr=%s..%s",
                        user_id[:8], chain, resolved_addr[:6], resolved_addr[-4:],
                    )
                else:
                    # R59 P0:user_id 在但拉不到钱包 → fail-fast 不冒 dev wallet 风险
                    log.error(
                        "[dex_router] R59 P0 钱包预解析返空 user=%s chain=%s — 拒绝执行避免 DEV_WALLET fallback",
                        user_id[:8], chain,
                    )
                    return RouteResult(
                        success=False,
                        error="Wallet resolution failed for user — refusing to fall back to DEV_WALLET",
                        chain=chain, token_address=token_address, action=action,
                    )
            except Exception as e:
                log.error("[dex_router] R59 P0 钱包预解析异常 user=%s: %s — fail-fast", user_id[:8], e)
                return RouteResult(
                    success=False, error=f"Wallet resolution error: {e}",
                    chain=chain, token_address=token_address, action=action,
                )

        try:
            # 确定交易方向
            if action == "buy":
                from_token = USDC_ADDRESS.get(chain, NATIVE_TOKEN[chain])
                to_token = token_address
                amount_raw = str(int(amount_usd * 1_000_000))  # USDC 6 decimals
            elif action == "sell":
                from_token = token_address
                to_token = USDC_ADDRESS.get(chain, NATIVE_TOKEN[chain])
                # sell 需要查余额，委托给 OKX executor
                amount_raw = None  # 后面在 OKX 路径中处理
            else:
                return RouteResult(
                    success=False, error=f"Unknown action: {action}",
                    chain=chain, token_address=token_address, action=action,
                )

            # 1. 大单拆分检查（仅 buy 且有明确金额）
            if action == "buy" and amount_usd > MIN_SPLIT_AMOUNT_USD * 2:
                should_split = await self._should_split(
                    chain, from_token, to_token, amount_raw, slippage_pct,
                )
                if should_split:
                    return await self._execute_split(
                        chain, token_address, action, amount_usd,
                        slippage_pct, wallet_address, private_key,
                    )

            # 2. 并行获取报价
            quotes = await self._get_parallel_quotes(
                chain, from_token, to_token, amount_raw, slippage_pct,
            )

            # 3. 选最优
            best = self._select_best(quotes)
            if best is None:
                # 所有报价都失败 → 直接走 OKX 完整路径
                log.warning("All quotes failed, falling back to OKX direct")
                return await self._execute_okx_direct(
                    chain, token_address, action, amount_usd,
                    slippage_pct, wallet_address, private_key,
                    quotes=quotes,
                )

            log.info(
                f"Best quote: dex={best.dex}, out={best.out_amount}, "
                f"impact={best.price_impact:.2f}%"
            )

            # 4. 执行最优报价
            result = await self._execute_quote(
                best, chain, token_address, action, amount_usd,
                slippage_pct, wallet_address, private_key,
                priority_fee_sol=priority_fee_sol, mev_bribe_sol=mev_bribe_sol,
            )

            # 5. 失败 → fallback
            if not result.success:
                fallback_quotes = [q for q in quotes if q.dex != best.dex and q.success]
                for fq in fallback_quotes:
                    log.info(f"Primary {best.dex} failed, trying fallback {fq.dex}")
                    result = await self._execute_quote(
                        fq, chain, token_address, action, amount_usd,
                        slippage_pct, wallet_address, private_key,
                        priority_fee_sol=priority_fee_sol, mev_bribe_sol=mev_bribe_sol,
                    )
                    if result.success:
                        result.fallback_used = True
                        break

                # 所有报价执行都失败 → OKX 完整路径作为最终 fallback
                if not result.success and best.dex != "okx":
                    log.info("All quote-based execution failed, trying OKX direct")
                    result = await self._execute_okx_direct(
                        chain, token_address, action, amount_usd,
                        slippage_pct, wallet_address, private_key,
                        quotes=quotes,
                    )
                    result.fallback_used = True

            # 6. 记录路由决策 (v1.1 Q12)
            result.quotes_received = [
                {"dex": q.dex, "out_amount": q.out_amount,
                 "price_impact": q.price_impact, "error": q.error}
                for q in quotes
            ]
            await self._record_routing(result, request_id=request_id)

            return result

        except Exception as e:
            log.error(f"DexRouter execute error: {e}", exc_info=True)
            return RouteResult(
                success=False, error=str(e),
                chain=chain, token_address=token_address, action=action,
            )

    # ── 大单拆分 ─────────────────────────────────────────────

    async def _should_split(
        self,
        chain: str,
        from_token: str,
        to_token: str,
        amount_raw: Optional[str],
        slippage_pct: float,
    ) -> bool:
        """v1.1 Q11: 用 price_impact > 2% 判断是否需要拆分"""
        if amount_raw is None:
            return False
        try:
            quote = await self._get_primary_quote(
                chain, from_token, to_token, amount_raw, slippage_pct,
            )
            if quote.success and quote.price_impact > SPLIT_IMPACT_THRESHOLD * 100:
                log.info(
                    f"Large order detected: impact={quote.price_impact:.2f}%, "
                    f"will split"
                )
                return True
        except Exception as e:
            log.debug(f"Split check error: {e}")
        return False

    async def _execute_split(
        self,
        chain: str,
        token_address: str,
        action: str,
        total_amount_usd: float,
        slippage_pct: float,
        wallet_address: Optional[str],
        private_key: Optional[str],
    ) -> RouteResult:
        """大单拆分执行"""
        # 计算拆分数量（每笔 >= $20）
        n = max(2, int(total_amount_usd / MIN_SPLIT_AMOUNT_USD))
        # 限制最多 10 笔拆分
        n = min(n, 10)
        per_amount = total_amount_usd / n

        log.info(f"Splitting ${total_amount_usd} into {n} x ${per_amount:.2f}")

        results: List[RouteResult] = []
        total_to_amount = 0.0
        total_gas = 0.0
        all_tx_hashes = []
        dex_used_set = set()

        for i in range(n):
            # 递归调用 execute（但每笔金额小于阈值，不会再拆分）
            r = await self.execute(
                chain, token_address, action, per_amount,
                slippage_pct, wallet_address, private_key,
            )
            results.append(r)
            if r.success:
                total_to_amount += r.to_amount
                total_gas += r.gas_fee
                if r.tx_hash:
                    all_tx_hashes.append(r.tx_hash)
                dex_used_set.add(r.dex_used)
            else:
                log.warning(f"Split {i+1}/{n} failed: {r.error}")

            # 间隔 2s（最后一笔不等）
            if i < n - 1:
                await asyncio.sleep(SPLIT_INTERVAL_S)

        # 合并结果
        success_count = sum(1 for r in results if r.success)
        combined = RouteResult(
            success=success_count > 0,
            dex_used=",".join(sorted(dex_used_set)) if dex_used_set else "none",
            tx_hash=all_tx_hashes[0] if all_tx_hashes else "",
            from_amount=total_amount_usd,
            to_amount=total_to_amount,
            price=total_amount_usd / total_to_amount if total_to_amount > 0 else 0,
            gas_fee=total_gas,
            chain=chain,
            token_address=token_address,
            action=action,
            split_count=n,
        )
        if success_count < n:
            combined.error = f"{n - success_count}/{n} splits failed"

        await self._record_routing(combined)
        return combined

    # ── 并行报价 ─────────────────────────────────────────────

    async def _get_parallel_quotes(
        self,
        chain: str,
        from_token: str,
        to_token: str,
        amount_raw: Optional[str],
        slippage_pct: float,
    ) -> List[QuoteResult]:
        """并行获取 primary + OKX 报价，2s 超时"""
        if amount_raw is None:
            # sell without known amount → only OKX can handle
            return [QuoteResult(dex="okx", out_amount="0",
                                raw={"note": "sell_delegate_to_okx"})]

        tasks = [
            self._get_primary_quote(chain, from_token, to_token, amount_raw, slippage_pct),
            self._get_okx_quote(chain, from_token, to_token, amount_raw, slippage_pct),
        ]

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=QUOTE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            log.warning("Parallel quotes timed out (>2s)")
            # 超时：尝试收集已完成的结果
            results = []
            for t in tasks:
                if hasattr(t, 'result') and t.done():
                    results.append(t.result())
                else:
                    results.append(QuoteResult(dex="unknown", error="timeout"))

        quotes = []
        for r in results:
            if isinstance(r, Exception):
                quotes.append(QuoteResult(dex="unknown", error=str(r)))
            elif isinstance(r, QuoteResult):
                quotes.append(r)
            else:
                quotes.append(QuoteResult(dex="unknown", error=f"unexpected: {type(r)}"))

        return quotes

    async def _get_primary_quote(
        self,
        chain: str,
        from_token: str,
        to_token: str,
        amount_raw: str,
        slippage_pct: float,
    ) -> QuoteResult:
        """获取 primary DEX 报价"""
        primary = PRIMARY_DEX.get(chain, "okx")

        if primary == "jupiter" and chain == "solana":
            return await self._get_jupiter_quote(
                from_token, to_token, amount_raw, slippage_pct,
            )
        elif primary == "oneinch" and chain in ONEINCH_CHAIN_ID:
            return await self._get_oneinch_quote(
                chain, from_token, to_token, amount_raw,
            )
        else:
            # 未知链 → OKX
            return await self._get_okx_quote(
                chain, from_token, to_token, amount_raw, slippage_pct,
            )

    async def _get_jupiter_quote(
        self,
        from_token: str,
        to_token: str,
        amount_raw: str,
        slippage_pct: float,
    ) -> QuoteResult:
        """Jupiter 报价"""
        try:
            from agent.dex.jupiter import get_jupiter_dex

            jup = get_jupiter_dex()
            slippage_bps = int(slippage_pct * 100)  # 1% → 100 bps
            quote = await jup.get_quote(from_token, to_token, amount_raw, slippage_bps)

            if not quote.success:
                return QuoteResult(dex="jupiter", error=quote.error)

            return QuoteResult(
                dex="jupiter",
                out_amount=quote.out_amount,
                price_impact=quote.price_impact_pct,
                raw=quote.raw,
            )
        except Exception as e:
            return QuoteResult(dex="jupiter", error=str(e))

    async def _get_oneinch_quote(
        self,
        chain: str,
        from_token: str,
        to_token: str,
        amount_raw: str,
    ) -> QuoteResult:
        """1inch 报价"""
        try:
            from agent.dex.oneinch import get_oneinch_dex

            inch = get_oneinch_dex()
            if not inch.available:
                return QuoteResult(dex="oneinch", error="API key not configured")

            chain_id = ONEINCH_CHAIN_ID.get(chain, 1)
            quote = await inch.get_quote(chain_id, from_token, to_token, amount_raw)

            if not quote.success:
                return QuoteResult(dex="oneinch", error=quote.error)

            return QuoteResult(
                dex="oneinch",
                out_amount=quote.to_amount,
                price_impact=0.0,  # 1inch 不直接返回 price_impact
                raw=quote.raw,
            )
        except Exception as e:
            return QuoteResult(dex="oneinch", error=str(e))

    async def _get_okx_quote(
        self,
        chain: str,
        from_token: str,
        to_token: str,
        amount_raw: str,
        slippage_pct: float,
    ) -> QuoteResult:
        """OKX DEX 报价"""
        try:
            executor = self._get_okx_executor()
            data = await executor.get_quote(
                chain=chain,
                from_token=from_token,
                to_token=to_token,
                amount=amount_raw,
                slippage=str(slippage_pct),
            )

            # OKX 返回格式: {code: "0", data: [{routerResult: {toTokenAmount, priceImpactPercent}}]}
            if not data.get("data"):
                return QuoteResult(dex="okx", error=f"No data: {data}")

            router = data["data"][0].get("routerResult", {})
            out_amount = router.get("toTokenAmount", "0")
            impact_str = router.get("priceImpactPercent", "0")
            try:
                price_impact = abs(float(impact_str))
            except (ValueError, TypeError):
                price_impact = 0.0

            return QuoteResult(
                dex="okx",
                out_amount=str(out_amount),
                price_impact=price_impact,
                raw=data,
            )
        except Exception as e:
            return QuoteResult(dex="okx", error=str(e))

    # ── 选最优 ───────────────────────────────────────────────

    def _select_best(self, quotes: List[QuoteResult]) -> Optional[QuoteResult]:
        """选择输出数量最高的报价"""
        valid = [q for q in quotes if q.success]
        if not valid:
            return None
        # 按 out_amount 降序，选最大
        return max(valid, key=lambda q: q.out_amount_int)

    # ── 执行报价 ─────────────────────────────────────────────

    async def _execute_quote(
        self,
        quote: QuoteResult,
        chain: str,
        token_address: str,
        action: str,
        amount_usd: float,
        slippage_pct: float,
        wallet_address: Optional[str],
        private_key: Optional[str],
        priority_fee_sol: float = 0.0,    # R64
        mev_bribe_sol: float = 0.0,       # R64
    ) -> RouteResult:
        """根据报价执行交易"""

        if quote.dex == "jupiter":
            return await self._execute_jupiter(
                quote, chain, token_address, action, amount_usd,
                slippage_pct, wallet_address, private_key,
                priority_fee_sol=priority_fee_sol, mev_bribe_sol=mev_bribe_sol,
            )
        elif quote.dex == "oneinch":
            return await self._execute_oneinch(
                quote, chain, token_address, action, amount_usd,
                slippage_pct, wallet_address, private_key,
            )
        elif quote.dex == "okx":
            return await self._execute_okx_direct(
                chain, token_address, action, amount_usd,
                slippage_pct, wallet_address, private_key,
            )
        else:
            return RouteResult(
                success=False, error=f"Unknown DEX: {quote.dex}",
                chain=chain, token_address=token_address, action=action,
            )

    async def _execute_jupiter(
        self,
        quote: QuoteResult,
        chain: str,
        token_address: str,
        action: str,
        amount_usd: float,
        slippage_pct: float,
        wallet_address: Optional[str],
        private_key: Optional[str],
        priority_fee_sol: float = 0.0,    # R64
        mev_bribe_sol: float = 0.0,       # R64
    ) -> RouteResult:
        """通过 Jupiter 执行交易

        R59 P0 fix: 直接用 execute() 预解析过的 wallet_address/private_key,
        不再调 executor._resolve_wallet() — 那会丢 user_id 上下文 fallback 到 DEV_WALLET。

        R64: priority_fee_sol / mev_bribe_sol 透传给 jup.get_swap(),
        Jupiter v6 会把这两个值写入 swap tx(prioritizationFeeLamports + jitoTipLamports)。
        """
        try:
            from agent.dex.jupiter import get_jupiter_dex
            from agent.trade_executor import TradeExecutor

            # R59 P0:execute() 已预解析(user_id-aware)→ 直接用入参,**不再二次解析**
            if not wallet_address or not private_key:
                return RouteResult(
                    success=False,
                    error="No wallet configured (pre-resolve required, no fallback)",
                    chain=chain, token_address=token_address, action=action,
                )
            wallet_addr = wallet_address
            priv_key = private_key
            executor = self._get_okx_executor()  # 仍需要 executor._broadcast_solana

            jup = get_jupiter_dex()

            # 获取 swap 交易(R64 — 真传 priority_fee + jito_tip)
            swap_data = await jup.get_swap(
                quote.raw, wallet_addr,
                priority_fee_sol=priority_fee_sol,
                jito_tip_sol=mev_bribe_sol,
            )
            if "error" in swap_data:
                return RouteResult(
                    success=False, error=f"Jupiter swap: {swap_data['error']}",
                    dex_used="jupiter",
                    chain=chain, token_address=token_address, action=action,
                )

            swap_tx = swap_data.get("swapTransaction", "")
            if not swap_tx:
                return RouteResult(
                    success=False, error="No swapTransaction in Jupiter response",
                    dex_used="jupiter",
                    chain=chain, token_address=token_address, action=action,
                )

            # 签名 + 广播（复用 OKX executor 的 Solana 签名逻辑）
            # Jupiter 返回 base64 编码的 VersionedTransaction
            import base64 as b64
            try:
                import base58 as b58
                from solders.keypair import Keypair  # type: ignore
                from solders.transaction import VersionedTransaction  # type: ignore

                # 解析私钥
                if priv_key.startswith("["):
                    import json as _json
                    key_bytes = bytes(_json.loads(priv_key))
                else:
                    key_bytes = b58.b58decode(priv_key)
                keypair = Keypair.from_bytes(key_bytes)

                # 反序列化 Jupiter 返回的 base64 交易
                tx_bytes = b64.b64decode(swap_tx)
                tx = VersionedTransaction.from_bytes(tx_bytes)
                tx.sign([keypair])
                signed_bytes = bytes(tx)
                signed_b58 = b58.b58encode(signed_bytes).decode("utf-8")

                # 广播
                tx_hash = await executor._broadcast_solana(signed_b58)

            except ImportError:
                return RouteResult(
                    success=False, error="solders/base58 not installed",
                    dex_used="jupiter",
                    chain=chain, token_address=token_address, action=action,
                )

            if not tx_hash:
                return RouteResult(
                    success=False, error="Jupiter tx broadcast failed",
                    dex_used="jupiter",
                    chain=chain, token_address=token_address, action=action,
                )

            # 计算输出
            out_amount_raw = int(quote.out_amount)
            # R71: sell→USDC(6);buy→查 token 真实 decimals(原硬编码 9,pump=6 会错算)
            if action == "sell":
                to_decimals = 6
            else:
                to_decimals = await _resolve_solana_decimals(token_address, fallback=9)
            to_amount_float = out_amount_raw / (10 ** to_decimals)

            return RouteResult(
                success=True,
                dex_used="jupiter",
                tx_hash=tx_hash,
                from_amount=amount_usd,
                to_amount=to_amount_float,
                price=amount_usd / to_amount_float if to_amount_float > 0 else 0,
                chain=chain,
                token_address=token_address,
                action=action,
                actual_slippage=quote.price_impact,
            )

        except Exception as e:
            log.error(f"Jupiter execution error: {e}", exc_info=True)
            return RouteResult(
                success=False, error=str(e), dex_used="jupiter",
                chain=chain, token_address=token_address, action=action,
            )

    async def _execute_oneinch(
        self,
        quote: QuoteResult,
        chain: str,
        token_address: str,
        action: str,
        amount_usd: float,
        slippage_pct: float,
        wallet_address: Optional[str],
        private_key: Optional[str],
    ) -> RouteResult:
        """通过 1inch 执行交易

        R59 P0 fix: 同 _execute_jupiter,直接用 execute() 预解析过的 wallet/priv。
        """
        try:
            from agent.dex.oneinch import get_oneinch_dex

            # R59 P0:不再二次 _resolve_wallet — execute() 已 user_id-aware 预解析
            if not wallet_address or not private_key:
                return RouteResult(
                    success=False,
                    error="No wallet configured (pre-resolve required, no fallback)",
                    chain=chain, token_address=token_address, action=action,
                )
            wallet_addr = wallet_address
            priv_key = private_key
            executor = self._get_okx_executor()

            inch = get_oneinch_dex()
            chain_id = ONEINCH_CHAIN_ID.get(chain, 1)

            # 确定 from/to
            if action == "buy":
                from_token = USDC_ADDRESS.get(chain, NATIVE_TOKEN[chain])
                to_token = token_address
                amount_raw = str(int(amount_usd * 1_000_000))
            else:
                from_token = token_address
                to_token = USDC_ADDRESS.get(chain, NATIVE_TOKEN[chain])
                # sell: 查余额
                balance = await executor._query_token_balance(chain, wallet_addr, token_address)
                if balance <= 0:
                    return RouteResult(
                        success=False, error="Token balance is zero",
                        chain=chain, token_address=token_address, action=action,
                    )
                amount_raw = str(balance)

            # EVM approve (buy USDC 不需要, sell token 需要)
            if action == "sell":
                await executor._approve_if_needed(
                    chain, wallet_addr, token_address, priv_key, amount_raw,
                )

            # 获取 swap 交易
            swap_data = await inch.get_swap(
                chain_id, from_token, to_token, amount_raw,
                wallet_addr, slippage_pct,
            )

            if "error" in swap_data:
                return RouteResult(
                    success=False, error=f"1inch swap: {swap_data['error']}",
                    dex_used="oneinch",
                    chain=chain, token_address=token_address, action=action,
                )

            tx_data = swap_data.get("tx", {})
            if not tx_data:
                return RouteResult(
                    success=False, error="No tx data in 1inch response",
                    dex_used="oneinch",
                    chain=chain, token_address=token_address, action=action,
                )

            # 签名 + 广播（复用 OKX executor 的 EVM 签名逻辑）
            signed_tx = await executor._sign_evm_tx(tx_data, priv_key, chain)
            if not signed_tx:
                return RouteResult(
                    success=False, error="1inch tx signing failed",
                    dex_used="oneinch",
                    chain=chain, token_address=token_address, action=action,
                )

            tx_hash = await executor._broadcast_evm(chain, signed_tx)
            if not tx_hash:
                return RouteResult(
                    success=False, error="1inch tx broadcast failed",
                    dex_used="oneinch",
                    chain=chain, token_address=token_address, action=action,
                )

            # 计算输出
            out_amount_raw = int(quote.out_amount) if quote.out_amount != "0" else 0
            # sell→USDC(6);buy→ERC20 多数 18(标准),少数非标(如 USDC/USDT=6)会偏。
            # TODO(R71): EVM 也接 eth_call decimals();目前无现成 EVM RPC 端点,
            # 且 18 命中率远高于 SOL 的 9,EVM 侧潜伏 P2,留后续。
            to_decimals = 6 if action == "sell" else 18
            to_amount_float = out_amount_raw / (10 ** to_decimals)

            return RouteResult(
                success=True,
                dex_used="oneinch",
                tx_hash=tx_hash,
                from_amount=amount_usd,
                to_amount=to_amount_float,
                price=amount_usd / to_amount_float if to_amount_float > 0 else 0,
                chain=chain,
                token_address=token_address,
                action=action,
                actual_slippage=quote.price_impact,
            )

        except Exception as e:
            log.error(f"1inch execution error: {e}", exc_info=True)
            return RouteResult(
                success=False, error=str(e), dex_used="oneinch",
                chain=chain, token_address=token_address, action=action,
            )

    async def _execute_okx_direct(
        self,
        chain: str,
        token_address: str,
        action: str,
        amount_usd: float,
        slippage_pct: float,
        wallet_address: Optional[str],
        private_key: Optional[str],
        quotes: Optional[List[QuoteResult]] = None,
    ) -> RouteResult:
        """直接通过 OKX executor 执行（完整路径，含余额查询/approve/签名/广播）"""
        try:
            executor = self._get_okx_executor()
            result = await executor.execute_trade_okx_direct(
                chain=chain,
                token_address=token_address,
                action=action,
                amount_usd=amount_usd,
                slippage_pct=slippage_pct,
                wallet_address=wallet_address,
                private_key=private_key,
            )

            return RouteResult(
                success=result.success,
                dex_used="okx",
                tx_hash=result.tx_hash,
                from_amount=result.from_amount,
                to_amount=result.to_amount,
                price=result.price,
                gas_fee=result.gas_fee,
                error=result.error,
                chain=chain,
                token_address=token_address,
                action=action,
            )

        except Exception as e:
            log.error(f"OKX direct execution error: {e}", exc_info=True)
            return RouteResult(
                success=False, error=str(e), dex_used="okx",
                chain=chain, token_address=token_address, action=action,
            )

    # ── 记录路由决策 ─────────────────────────────────────────

    async def _record_routing(self, result: RouteResult, request_id: Optional[str] = None):
        """v1.1 Q12: 记录路由决策到 agent_executions"""
        try:
            from database import get_db
            db = get_db()

            row = {
                "chain": result.chain,
                "token_address": result.token_address,
                "action": result.action,
                "amount_usd": result.from_amount,
                "amount_token": result.to_amount,
                "executed_price": result.price,
                "gas_fee_usd": result.gas_fee,
                "tx_hash": result.tx_hash or None,
                "status": "confirmed" if result.success else "failed",
                "error_message": result.error or None,
                # PRD-009 路由字段
                "dex_used": result.dex_used,
                "quotes_received": json.dumps(result.quotes_received) if result.quotes_received else None,
                "actual_slippage": result.actual_slippage,
                "fallback_used": result.fallback_used,
                "split_count": result.split_count,
            }
            # R59 P0:idempotency key 写入,下次同 request_id retry 时 trade_executor
            # 顶部 SELECT 命中 → 短路不重复 broadcast
            if request_id:
                row["request_id"] = request_id

            try:
                db.table("agent_executions").insert(row).execute()
            except Exception as e:
                # UNIQUE INDEX 触发(同 request_id 已存在)→ 说明重复执行,静默
                if "duplicate key" in str(e).lower() or "23505" in str(e):
                    log.debug("[dex_router] R59 _record_routing dup request_id=%s — skip", request_id)
                    return
                raise
            log.info(
                f"Routing recorded: dex={result.dex_used}, "
                f"fallback={result.fallback_used}, splits={result.split_count}"
            )

        except Exception as e:
            log.error(f"Failed to record routing: {e}")


# ── 全局单例 ──────────────────────────────────────────────────

_router: Optional[DexRouter] = None


def get_dex_router() -> DexRouter:
    global _router
    if _router is None:
        _router = DexRouter()
    return _router
