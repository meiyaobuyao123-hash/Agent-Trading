"""
交易执行器 — OKX DEX Aggregator v6 Swap

流程：
1. 获取报价（quote）
2. 获取交易数据（swap）
3. 签名交易（Solana: solders / EVM: eth-account）
4. 广播交易（RPC）
5. 记录结果

Python 3.9 兼容。
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

log = logging.getLogger(__name__)

# ── OKX DEX Aggregator 配置 ─────────────────────────────────
OKX_SWAP_BASE = "https://web3.okx.com"

# 链 ID
CHAIN_INDEX = {
    "solana": "501",
    "eth": "1",
    "bsc": "56",
    "base": "8453",
}

# 稳定币/原生币地址（买入时 from）
NATIVE_TOKEN = {
    "solana": "So11111111111111111111111111111111111111112",   # wSOL
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

# EVM chain IDs (for tx signing)
EVM_CHAIN_ID = {"eth": 1, "bsc": 56, "base": 8453}

# RPC 端点
SOLANA_RPC = os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
EVM_RPC = {
    "eth": os.getenv("ETH_RPC", "https://eth.llamarpc.com"),
    "bsc": os.getenv("BSC_RPC", "https://bsc-dataseed.binance.org"),
    "base": os.getenv("BASE_RPC", "https://mainnet.base.org"),
}

# R45 — EVM MEV 保护 RPC(开启时 broadcast 走这些 URL,不进公共 mempool)
# Flashbots Protect:免费 + 0 配置 + 自动防三明治
# bloXroute / 1inch Fusion 等留 R46 接入
EVM_RPC_MEV_PROTECTED = {
    "eth": os.getenv("ETH_FLASHBOTS_RPC", "https://rpc.flashbots.net/fast"),
    "bsc": "",   # 第一版无 Protect URL,fallback 公共 RPC + log warning
    "base": "",  # 同上,后续可接 1inch Fusion 自带保护
}

# 代币精度
TOKEN_DECIMALS_NATIVE = {
    "solana": 9,   # SOL = 9 decimals
    "eth": 18,
    "bsc": 18,
    "base": 18,
}


@dataclass
class TradeResult:
    """交易执行结果"""
    success: bool
    tx_hash: str = ""
    from_amount: float = 0.0
    to_amount: float = 0.0
    price: float = 0.0
    gas_fee: float = 0.0
    error: str = ""
    chain: str = ""
    token_address: str = ""
    action: str = ""


class TradeExecutor:
    """OKX DEX 交易执行器"""

    def __init__(self):
        from config import OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE
        self._api_key = OKX_API_KEY
        self._secret_key = OKX_SECRET_KEY
        self._passphrase = OKX_PASSPHRASE
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ── OKX 签名 ────────────────────────────────────────────

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        message = timestamp + method.upper() + path + body
        mac = hmac.new(
            self._secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        )
        return base64.b64encode(mac.digest()).decode("utf-8")

    def _headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
        return {
            "OK-ACCESS-KEY": self._api_key,
            "OK-ACCESS-SIGN": self._sign(ts, method, path, body),
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self._passphrase,
            "Content-Type": "application/json",
        }

    # ── API 调用 ─────────────────────────────────────────────

    async def _okx_get(self, path: str) -> Dict[str, Any]:
        """GET 请求 OKX DEX Aggregator"""
        session = await self._get_session()
        headers = self._headers("GET", path)
        url = OKX_SWAP_BASE + path
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            data = await resp.json()
            if data.get("code") != "0":
                raise RuntimeError(f"OKX API error: code={data.get('code')}, msg={data.get('msg', data)}")
            return data

    # ── 获取报价 ─────────────────────────────────────────────

    async def get_quote(
        self, chain: str, from_token: str, to_token: str,
        amount: str, slippage: str = "1",
    ) -> Dict[str, Any]:
        """获取交易报价"""
        chain_index = CHAIN_INDEX.get(chain, "501")
        path = (
            f"/api/v6/dex/aggregator/quote"
            f"?chainIndex={chain_index}"
            f"&fromTokenAddress={from_token}"
            f"&toTokenAddress={to_token}"
            f"&amount={amount}"
            f"&slippagePercent={slippage}"
        )
        return await self._okx_get(path)

    # ── 获取 Swap 交易数据 ───────────────────────────────────

    async def get_swap_data(
        self, chain: str, from_token: str, to_token: str,
        amount: str, slippage: str, wallet_address: str,
    ) -> Dict[str, Any]:
        """获取 swap 交易数据（用于签名和广播）"""
        chain_index = CHAIN_INDEX.get(chain, "501")
        path = (
            f"/api/v6/dex/aggregator/swap"
            f"?chainIndex={chain_index}"
            f"&fromTokenAddress={from_token}"
            f"&toTokenAddress={to_token}"
            f"&amount={amount}"
            f"&slippagePercent={slippage}"
            f"&userWalletAddress={wallet_address}"
            f"&swapMode=exactIn"
        )
        return await self._okx_get(path)

    # ── 执行交易入口 ─────────────────────────────────────────

    async def execute_trade(
        self,
        chain: str,
        token_address: str,
        action: str,
        amount_usd: float,
        slippage_pct: float = 1.0,
        wallet_address: Optional[str] = None,
        private_key: Optional[str] = None,
        safety_ctx: Optional[Dict[str, Any]] = None,
        risk_params: Optional[Dict[str, Any]] = None,
    ) -> TradeResult:
        """
        执行买入或卖出交易 — PRD-009: 通过 DexRouter 多 DEX 路由

        优先走 Jupiter(SOL)/1inch(EVM)，失败自动 fallback 到 OKX。
        大单自动拆分（price_impact > 2%）。

        Args:
            chain: 链名 (solana/eth/bsc/base)
            token_address: 目标代币地址
            action: buy 或 sell
            amount_usd: 交易金额 (USD)
            slippage_pct: 滑点百分比
            wallet_address: 钱包地址（不传则从环境变量读取）
            private_key: 私钥（不传则从环境变量读取）
            safety_ctx: W3 D3 加 — 可选 dict，传入后跑 SafetyEngine.check_trade
                        任何 BLOCK 直接返回失败，不调 DEX。
                        最小 ctx：{amount_usd, action, mode, agent_global_state, ...}
                        完整字段见 docs/agent-pm/08-safety-policy.md
            risk_params: R42 P0.2 — 策略级风控参数(覆盖默认值)
                         {max_slippage_pct, max_position_usd, priority_fee_sol, mev_bribe_sol}
                         详见 docs/agent-pm/18-trade-execution-spec.md §4 (HR34)

        Returns:
            TradeResult（safety BLOCK 时 success=False, error="safety: <rule_id> <reason>"）
        """
        # ── R42 P0.2:risk_params 真用(取代 hardcoded)─────────
        rp = risk_params or {}
        # max_position_usd 强制限仓(超出截断 + log)
        max_position = float(rp.get("max_position_usd", 1000.0))
        if amount_usd > max_position:
            log.warning(
                "[trade_executor] amount_usd %.2f > max_position %.2f → 截断",
                amount_usd, max_position,
            )
            amount_usd = max_position

        # ── R42 P0.3:全自动化 7 条兜底检查(取代 HITL 分层审批)─
        # 仅当 safety_ctx 含 user_id 且 mode=live 时跑(paper 不消耗 daily cap)
        if safety_ctx and safety_ctx.get("user_id") and safety_ctx.get("mode") == "live":
            try:
                from agent.hitl_router import is_allowed_to_auto_execute, record_executed
                strategy_dict = {
                    "id": safety_ctx.get("strategy_id"),
                    "status": safety_ctx.get("strategy_status", "active"),
                    "mode": "live",
                    "max_position_usd": max_position,
                    "daily_auto_cap_usd": rp.get("daily_auto_cap_usd"),
                    "consecutive_losses": safety_ctx.get("consecutive_losses", 0),
                    "max_drawdown_pct_30d": safety_ctx.get("max_drawdown_pct_30d", 0),
                }
                allowed, reason = is_allowed_to_auto_execute(
                    user_id=safety_ctx["user_id"],
                    strategy=strategy_dict,
                    amount_usd=amount_usd,
                    side=action,
                )
                if not allowed:
                    log.warning("[trade_executor] R42 兜底拒绝: %s", reason)
                    return TradeResult(
                        success=False,
                        error=f"全自动兜底拒绝: {reason}",
                        chain=chain, token_address=token_address, action=action,
                    )
                # 记到 daily cap 累计(buy 才算,sell 不算)
                # 注:必须在 trade 真成功后才 record,这里先标记
                _hitl_record_pending = (safety_ctx["user_id"], amount_usd, action)
            except Exception as e:
                log.debug("[hitl_router] check failed (降级允许): %s", e)
                _hitl_record_pending = None
        else:
            _hitl_record_pending = None
        # slippage 优先用 risk_params(0.01 = 1%),fallback 到入参
        if "max_slippage_pct" in rp:
            slippage_pct = float(rp["max_slippage_pct"]) * 100  # 0.01 → 1.0
        # priority_fee + MEV bribe 透传给 dex_router(SOL 链 Jito 用)
        priority_fee_sol = float(rp.get("priority_fee_sol", 0.0005))
        mev_bribe_sol = float(rp.get("mev_bribe_sol", 0.0))
        # ─────────────────────────────────────────────────────

        # ── W3 D3 Safety pre-check ──────────────────────────────
        if safety_ctx is not None:
            block = check_safety_for_trade(
                {**safety_ctx,
                 "chain": chain, "token_address": token_address,
                 "action": action, "amount_usd": amount_usd,
                 "slippage_pct": safety_ctx.get("slippage_pct", slippage_pct / 100.0)},
            )
            if block is not None:
                return TradeResult(
                    success=False,
                    error=f"safety BLOCKED: {block.rule_id} - {block.reason}",
                    chain=chain,
                    token_address=token_address,
                    action=action,
                )

        from config import USE_AVE
        if USE_AVE:
            return await self._execute_trade_ave(
                chain, token_address, action, amount_usd,
                slippage_pct, wallet_address, private_key,
            )

        try:
            from agent.dex_router import get_dex_router

            router = get_dex_router()
            route_result = await router.execute(
                chain=chain,
                token_address=token_address,
                action=action,
                amount_usd=amount_usd,
                slippage_pct=slippage_pct,
                wallet_address=wallet_address,
                private_key=private_key,
                priority_fee_sol=priority_fee_sol,   # R42 P0.2
                mev_bribe_sol=mev_bribe_sol,         # R42 P0.2
            )

            # 转换 RouteResult → TradeResult
            result = TradeResult(
                success=route_result.success,
                tx_hash=route_result.tx_hash,
                from_amount=route_result.from_amount,
                to_amount=route_result.to_amount,
                price=route_result.price,
                gas_fee=route_result.gas_fee,
                error=route_result.error,
                chain=chain,
                token_address=token_address,
                action=action,
            )

            if result.success:
                # R42 P0.3:trade 真成功 → 累加到 daily cap
                if _hitl_record_pending is not None:
                    try:
                        from agent.hitl_router import record_executed
                        new_total = record_executed(*_hitl_record_pending)
                        log.info("[hitl_router] daily total → $%.0f", new_total)
                    except Exception as e:
                        log.debug("[hitl_router] record fail: %s", e)
                log.info(
                    f"Trade SUCCESS via {route_result.dex_used}: "
                    f"{action} {token_address[:10]}.. tx={result.tx_hash}"
                    f"{' (fallback)' if route_result.fallback_used else ''}"
                    f"{f' (split x{route_result.split_count})' if route_result.split_count > 1 else ''}"
                )

            return result

        except Exception as e:
            log.error(f"Trade execution error: {e}", exc_info=True)
            return TradeResult(
                success=False, error=str(e),
                chain=chain, token_address=token_address, action=action,
            )

    async def execute_trade_okx_direct(
        self,
        chain: str,
        token_address: str,
        action: str,
        amount_usd: float,
        slippage_pct: float = 1.0,
        wallet_address: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> TradeResult:
        """
        OKX 直连执行（保留原始路径，供 DexRouter fallback 使用）

        Returns:
            TradeResult
        """
        try:
            # 获取钱包信息
            wallet_addr, priv_key = self._resolve_wallet(chain, wallet_address, private_key)
            if not wallet_addr or not priv_key:
                return TradeResult(
                    success=False, error="No wallet configured for trading",
                    chain=chain, token_address=token_address, action=action,
                )

            # 确定交易方向
            if action == "buy":
                from_token = USDC_ADDRESS.get(chain, NATIVE_TOKEN[chain])
                to_token = token_address
                # 将 USD 转换为最小单位（USDC 6 decimals）
                amount_raw = str(int(amount_usd * 1_000_000))
            elif action == "sell":
                from_token = token_address
                to_token = USDC_ADDRESS.get(chain, NATIVE_TOKEN[chain])
                # 查询链上代币余额
                balance_raw = await self._query_token_balance(chain, wallet_addr, token_address)
                if balance_raw <= 0:
                    return TradeResult(
                        success=False, error="Token balance is zero, nothing to sell",
                        chain=chain, token_address=token_address, action=action,
                    )
                # 支持部分卖出（amount_usd < 0 表示全仓，>0 表示卖出指定比例）
                sell_pct = min(amount_usd, 1.0) if 0 < amount_usd <= 1.0 else 1.0
                amount_raw = str(int(balance_raw * sell_pct))
                # EVM 需要 approve
                if chain != "solana":
                    await self._approve_if_needed(chain, wallet_addr, token_address, priv_key, amount_raw)
            else:
                return TradeResult(
                    success=False, error=f"Unknown action: {action}",
                    chain=chain, token_address=token_address, action=action,
                )

            log.info(f"Executing OKX direct {action}: {from_token[:10]}.. → {to_token[:10]}.. amount_raw={amount_raw} on {chain}")

            # Step 1: 获取 swap 数据
            swap_data = await self.get_swap_data(
                chain=chain,
                from_token=from_token,
                to_token=to_token,
                amount=amount_raw,
                slippage=str(slippage_pct),
                wallet_address=wallet_addr,
            )

            if not swap_data.get("data"):
                return TradeResult(
                    success=False, error=f"No swap data returned: {swap_data}",
                    chain=chain, token_address=token_address, action=action,
                )

            swap_info = swap_data["data"][0]
            router_result = swap_info.get("routerResult", {})
            tx_data = swap_info.get("tx", {})

            to_amount_raw = router_result.get("toTokenAmount", "0")
            estimate_gas = router_result.get("estimateGasFee", "0")

            log.info(
                f"Swap quote: to_amount={to_amount_raw}, "
                f"gas={estimate_gas}, impact={router_result.get('priceImpactPercent', '?')}%"
            )

            # Step 2: 签名交易
            if chain == "solana":
                signed_tx = self._sign_solana_tx(tx_data, priv_key)
            else:
                signed_tx = await self._sign_evm_tx(tx_data, priv_key, chain)

            if not signed_tx:
                return TradeResult(
                    success=False, error="Transaction signing failed",
                    chain=chain, token_address=token_address, action=action,
                )

            # Step 3: 广播交易
            tx_hash = await self._broadcast_tx(chain, signed_tx, wallet_addr)

            if not tx_hash:
                return TradeResult(
                    success=False, error="Transaction broadcast failed",
                    chain=chain, token_address=token_address, action=action,
                )

            # 计算价格 — 使用 OKX 返回的 toTokenDecimalNum 而非硬编码
            to_decimals = int(router_result.get("toTokenDecimalNum", 6))
            from_decimals = int(router_result.get("fromTokenDecimalNum", 6))
            to_amount_float = float(to_amount_raw) / (10 ** to_decimals)
            from_amount_float = float(amount_raw) / (10 ** from_decimals)

            if action == "buy":
                price = amount_usd / to_amount_float if to_amount_float > 0 else 0
            else:
                # 卖出：to_amount 是 USDC，即卖出所得 USD
                price = to_amount_float / from_amount_float if from_amount_float > 0 else 0
                amount_usd = to_amount_float  # 实际卖出所得

            result = TradeResult(
                success=True,
                tx_hash=tx_hash,
                from_amount=amount_usd,
                to_amount=to_amount_float,
                price=price,
                gas_fee=float(estimate_gas) if estimate_gas else 0,
                chain=chain,
                token_address=token_address,
                action=action,
            )

            log.info(f"Trade SUCCESS (OKX direct): {action} {token_address[:10]}.. tx={tx_hash}")

            return result

        except Exception as e:
            log.error(f"Trade execution error: {e}", exc_info=True)
            return TradeResult(
                success=False, error=str(e),
                chain=chain, token_address=token_address, action=action,
            )

    # ── 钱包解析(R42 P1: 优先 DB user_wallets,fallback .env)─

    def _resolve_wallet(
        self, chain: str,
        wallet_address: Optional[str], private_key: Optional[str],
        user_id: Optional[str] = None,
    ) -> Tuple[str, str]:
        """解析钱包地址 + 私钥。

        R42 P1 优先级:
          1. 函数入参 wallet_address + private_key(callers 显式传)
          2. user_id 提供 → 查 user_wallets 表(AES 解密)
          3. .env TRADE_WALLET_PRIVATE_KEY[_CHAIN](过渡期/dev 用)

        永远不返私钥到 log / response。
        """
        # 1. 入参优先
        if wallet_address and private_key:
            return wallet_address, private_key
        addr = wallet_address or ""
        key = private_key or ""

        # 2. R42 P1:从 DB 拉(user_id 提供时)
        if not key and user_id:
            try:
                from api.routes_wallet import get_decrypted_wallet
                w = get_decrypted_wallet(user_id, chain)
                if w:
                    return w["public_key"], w["private_key"]
            except Exception as e:
                log.debug("[trade_executor] user_wallets 拉失败,fallback env: %s", e)

        # 3. fallback .env(过渡期 / dev 用)
        if not addr:
            addr = os.getenv("TRADE_WALLET_ADDRESS", "")
        if not key:
            key = os.getenv("TRADE_WALLET_PRIVATE_KEY", "")

        # 支持按链指定 env
        if not addr:
            addr = os.getenv(f"TRADE_WALLET_ADDRESS_{chain.upper()}", "")
        if not key:
            key = os.getenv(f"TRADE_WALLET_PRIVATE_KEY_{chain.upper()}", "")

        return addr, key

    # ── AVE Cloud Skill 交易（USE_AVE=true）──────────────────

    async def _execute_trade_ave(
        self, chain: str, token_address: str, action: str,
        amount_usd: float, slippage_pct: float = 1.0,
        wallet_address: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> TradeResult:
        """通过 AVE Cloud chainWallet API 执行交易"""
        try:
            from ave_client import ave

            addr, key = self._resolve_wallet(chain, wallet_address, private_key)
            if not addr or not key:
                return TradeResult(success=False, error="No wallet configured for AVE trade")

            # 确定输入输出代币
            if action == "buy":
                in_token = "sol" if chain == "solana" else "usdt"
                out_token = token_address
                swap_type = "buy"
                # 将 USD 转为链原生数量（粗算，实际用 quote 验证）
                amount_raw = str(int(amount_usd * 1_000_000))  # USDC 6 decimals
            else:
                in_token = token_address
                out_token = "sol" if chain == "solana" else "usdt"
                swap_type = "sell"
                amount_raw = str(int(amount_usd * 1_000_000))

            # 1. 报价
            quote = await ave.get_quote(chain, in_token, out_token, amount_raw, swap_type)
            if not quote:
                return TradeResult(success=False, error="AVE quote failed")

            estimate_out = quote.get("estimateOut", "0")
            log.info("[AVE Trade] %s %s $%.2f → quote out=%s", action, token_address[:12], amount_usd, estimate_out)

            # 2. 创建交易
            if chain == "solana":
                tx_data = await ave.create_solana_tx(
                    in_token, out_token, amount_raw, swap_type,
                    slippage_pct, addr,
                )
            else:
                tx_data = await ave.create_evm_tx(
                    chain, in_token, out_token, amount_raw, swap_type,
                    slippage_pct, addr,
                )

            if not tx_data:
                return TradeResult(success=False, error="AVE create tx failed")

            # 3. 本地签名
            request_tx_id = tx_data.get("requestTxId", "")
            raw_tx = tx_data.get("rawTransaction") or tx_data.get("tx", "")

            if chain == "solana":
                signed = self._sign_solana_tx({"tx": raw_tx}, key)
            else:
                signed = await self._sign_evm_tx(tx_data, key, chain)

            if not signed:
                return TradeResult(success=False, error="AVE tx signing failed")

            # 4. 发送签名交易
            if chain == "solana":
                result = await ave.send_signed_solana_tx(request_tx_id, signed)
            else:
                result = await ave.send_signed_evm_tx(chain, request_tx_id, signed)

            if not result:
                return TradeResult(success=False, error="AVE send tx failed")

            tx_hash = result.get("txHash", result.get("tx_hash", ""))
            out_decimals = int(quote.get("decimals", 9))
            out_amount = int(estimate_out) / (10 ** out_decimals) if estimate_out else 0
            price = amount_usd / out_amount if out_amount > 0 and action == "buy" else 0

            log.info("[AVE Trade] ✅ %s %s tx=%s", action, token_address[:12], tx_hash[:16] if tx_hash else "?")

            return TradeResult(
                success=True,
                tx_hash=tx_hash,
                price=price,
                amount_usd=amount_usd,
                gas_fee=0,
            )

        except Exception as e:
            log.error("[AVE Trade] %s %s failed: %s", action, token_address[:12], e)
            return TradeResult(success=False, error=f"AVE trade error: {e}")

    # ── Solana 签名 ──────────────────────────────────────────

    def _sign_solana_tx(self, tx_data: Dict[str, Any], private_key: str) -> Optional[str]:
        """签名 Solana 交易"""
        try:
            import base58 as b58
            from solders.keypair import Keypair  # type: ignore
            from solders.transaction import VersionedTransaction  # type: ignore

            # 解析私钥（支持 base58 和 JSON 数组格式）
            if private_key.startswith("["):
                key_bytes = bytes(json.loads(private_key))
            else:
                key_bytes = b58.b58decode(private_key)
            keypair = Keypair.from_bytes(key_bytes)

            # 反序列化 OKX 返回的交易
            raw_tx = tx_data.get("data", "")
            if not raw_tx:
                log.error("No transaction data in OKX response")
                return None

            tx_bytes = b58.b58decode(raw_tx)
            tx = VersionedTransaction.from_bytes(tx_bytes)

            # 签名
            tx.sign([keypair])
            signed_bytes = bytes(tx)

            return b58.b58encode(signed_bytes).decode("utf-8")

        except ImportError:
            log.error("solders/base58 not installed: pip install solders base58")
            return None
        except Exception as e:
            log.error(f"Solana tx signing error: {e}")
            return None

    # ── EVM 签名 ─────────────────────────────────────────────

    async def _sign_evm_tx(self, tx_data: Dict[str, Any], private_key: str, chain: str) -> Optional[str]:
        """签名 EVM 交易（async: 查询链上 nonce）"""
        try:
            from eth_account import Account

            account = Account.from_key(private_key)
            chain_id = EVM_CHAIN_ID.get(chain, 1)

            def _parse_hex_or_int(val, default=0) -> int:
                """安全解析 hex 字符串或 int"""
                if val is None:
                    return default
                if isinstance(val, int):
                    return val
                s = str(val)
                if s.startswith("0x") or s.startswith("0X"):
                    return int(s, 16)
                return int(s) if s else default

            # 获取链上 nonce
            nonce = await self._get_evm_nonce(chain, account.address)

            # 构建交易
            tx = {
                "to": tx_data.get("to", ""),
                "data": tx_data.get("data", "0x"),
                "value": _parse_hex_or_int(tx_data.get("value"), 0),
                "gas": _parse_hex_or_int(tx_data.get("gas"), 21000),
                "gasPrice": _parse_hex_or_int(tx_data.get("gasPrice"), 0),
                "chainId": chain_id,
                "nonce": nonce,
            }

            signed = account.sign_transaction(tx)
            return signed.raw_transaction.hex()

        except ImportError:
            log.error("eth-account not installed: pip install eth-account")
            return None
        except Exception as e:
            log.error(f"EVM tx signing error: {e}")
            return None

    async def _get_evm_nonce(self, chain: str, address: str) -> int:
        """查询 EVM 链上 nonce（eth_getTransactionCount）"""
        rpc_url = EVM_RPC.get(chain, "")
        if not rpc_url:
            log.warning("No RPC URL for chain %s, nonce=0", chain)
            return 0
        try:
            session = await self._get_session()
            payload = {
                "jsonrpc": "2.0", "id": 1,
                "method": "eth_getTransactionCount",
                "params": [address, "pending"],
            }
            async with session.post(
                rpc_url, json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                if "error" in data:
                    log.warning("Nonce query error: %s", data["error"])
                    return 0
                return int(data.get("result", "0x0"), 16)
        except Exception as e:
            log.warning("Failed to get nonce for %s on %s: %s", address[:10], chain, e)
            return 0

    # ── 广播交易 ──────────────────────────────────────────────

    async def _broadcast_tx(self, chain: str, signed_tx: str, wallet_address: str) -> Optional[str]:
        """广播已签名的交易"""
        try:
            if chain == "solana":
                return await self._broadcast_solana(signed_tx)
            else:
                return await self._broadcast_evm(chain, signed_tx)
        except Exception as e:
            log.error(f"Broadcast error on {chain}: {e}")
            return None

    async def _broadcast_solana(self, signed_tx_b58: str) -> Optional[str]:
        """通过 Solana RPC 广播"""
        session = await self._get_session()
        rpc_url = os.getenv("SOLANA_RPC", SOLANA_RPC)

        # 如果 Helius RPC 可用，优先使用
        from config import HELIUS_RPC
        if HELIUS_RPC and "helius" in HELIUS_RPC:
            rpc_url = HELIUS_RPC

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                signed_tx_b58,
                {
                    "encoding": "base58",
                    "skipPreflight": False,
                    "preflightCommitment": "confirmed",
                    "maxRetries": 3,
                },
            ],
        }

        async with session.post(rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            data = await resp.json()
            if "error" in data:
                log.error(f"Solana RPC error: {data['error']}")
                return None
            tx_hash = data.get("result", "")
            log.info(f"Solana tx broadcast: {tx_hash}")
            return tx_hash

    async def _broadcast_evm(self, chain: str, signed_tx_hex: str,
                              mev_protected: bool = False) -> Optional[str]:
        """通过 EVM RPC 广播

        R45: mev_protected=True 时优先走 Flashbots Protect / bloXroute 等私有 mempool,
              防三明治攻击。无 Protect URL 的链 → 降级公共 RPC + log warning。
        """
        session = await self._get_session()
        # R45 优先 Protect URL
        rpc_url = ""
        used_mev = False
        if mev_protected:
            rpc_url = EVM_RPC_MEV_PROTECTED.get(chain, "")
            if rpc_url:
                used_mev = True
                log.info(f"[broadcast] {chain} 走 MEV Protect: {rpc_url}")
            else:
                log.warning(
                    f"[broadcast] {chain} 启用 MEV 但无 Protect URL,降级公共 RPC(后续可接 bloXroute / 1inch Fusion)"
                )
        if not rpc_url:
            rpc_url = EVM_RPC.get(chain, "")
        if not rpc_url:
            log.error(f"No RPC URL for chain: {chain}")
            return None
        # 标记给 audit 追溯
        if not used_mev:
            log.debug(f"[broadcast] {chain} 走公共 mempool: {rpc_url}")

        if not signed_tx_hex.startswith("0x"):
            signed_tx_hex = "0x" + signed_tx_hex

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_sendRawTransaction",
            "params": [signed_tx_hex],
        }

        async with session.post(rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            data = await resp.json()
            if "error" in data:
                log.error(f"EVM RPC error ({chain}): {data['error']}")
                return None
            tx_hash = data.get("result", "")
            log.info(f"EVM tx broadcast ({chain}): {tx_hash}")
            return tx_hash

    # ── 记录交易结果到 DB ────────────────────────────────────

    async def _record_execution(
        self,
        result: TradeResult,
        user_id: str = "",
        strategy_id: str = "",
    ):
        """记录交易执行到 agent_executions 表"""
        try:
            from database import get_db
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
            }
            if user_id:
                row["user_id"] = user_id
            if strategy_id:
                row["strategy_id"] = strategy_id
            get_db().table("agent_executions").insert(row).execute()
        except Exception as e:
            log.error(f"Failed to record execution: {e}")


    # ── 代币余额查询 ─────────────────────────────────────────

    async def _query_token_balance(self, chain: str, wallet: str, token_address: str) -> int:
        """查询链上代币余额（返回最小单位 raw amount）"""
        try:
            if chain == "solana":
                return await self._query_sol_balance(wallet, token_address)
            else:
                return await self._query_evm_balance(chain, wallet, token_address)
        except Exception as e:
            log.error(f"Balance query error {chain}/{token_address[:10]}: {e}")
            return 0

    async def _query_sol_balance(self, wallet: str, token_mint: str) -> int:
        """Solana SPL 代币余额"""
        session = await self._get_session()
        from config import HELIUS_RPC
        rpc_url = HELIUS_RPC if HELIUS_RPC else SOLANA_RPC

        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                wallet,
                {"mint": token_mint},
                {"encoding": "jsonParsed"},
            ],
        }
        async with session.post(rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            data = await resp.json()
            accounts = data.get("result", {}).get("value", [])
            if not accounts:
                return 0
            info = accounts[0].get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
            amount = info.get("tokenAmount", {}).get("amount", "0")
            return int(amount)

    async def _query_evm_balance(self, chain: str, wallet: str, token_address: str) -> int:
        """ERC20 代币余额"""
        session = await self._get_session()
        rpc_url = EVM_RPC.get(chain, "")
        if not rpc_url:
            return 0

        # balanceOf(address) = 0x70a08231
        addr_padded = wallet[2:].lower().zfill(64) if wallet.startswith("0x") else wallet.zfill(64)
        call_data = "0x70a08231" + addr_padded

        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "eth_call",
            "params": [{"to": token_address, "data": call_data}, "latest"],
        }
        async with session.post(rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            data = await resp.json()
            result = data.get("result", "0x0")
            return int(result, 16) if result and result != "0x" else 0

    # ── EVM Approve ────────────────────────────────────────────

    async def _approve_if_needed(
        self, chain: str, wallet: str, token_address: str,
        private_key: str, amount_raw: str,
    ):
        """EVM 卖出前检查 allowance，不足则发 approve 交易"""
        try:
            session = await self._get_session()
            rpc_url = EVM_RPC.get(chain, "")
            if not rpc_url:
                return

            # OKX DEX Router 地址（approve 的 spender）
            # 从 OKX swap 返回的 tx.to 获取，这里用已知的聚合器地址
            spender = "0x40aA958dd87FC8305b97f2BA922CDdCa374bcD7f"  # OKX DEX Router

            # 查 allowance: allowance(owner, spender) = 0xdd62ed3e
            owner_padded = wallet[2:].lower().zfill(64)
            spender_padded = spender[2:].lower().zfill(64)
            call_data = "0xdd62ed3e" + owner_padded + spender_padded

            payload = {
                "jsonrpc": "2.0", "id": 1,
                "method": "eth_call",
                "params": [{"to": token_address, "data": call_data}, "latest"],
            }
            async with session.post(rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                allowance = int(data.get("result", "0x0"), 16)

            needed = int(amount_raw)
            if allowance >= needed:
                return  # 已 approve 过

            log.info(f"Approving {token_address[:10]} for OKX DEX on {chain}")

            # approve(spender, MAX_UINT256) = 0x095ea7b3
            max_uint = "f" * 64
            approve_data = "0x095ea7b3" + spender_padded + max_uint

            from eth_account import Account
            account = Account.from_key(private_key)
            nonce = await self._get_evm_nonce(chain, account.address)
            chain_id = EVM_CHAIN_ID.get(chain, 1)

            tx = {
                "to": token_address,
                "data": approve_data,
                "value": 0,
                "gas": 60000,
                "gasPrice": 5_000_000_000,  # 5 gwei default
                "chainId": chain_id,
                "nonce": nonce,
            }
            signed = account.sign_transaction(tx)
            tx_hex = signed.raw_transaction.hex()
            if not tx_hex.startswith("0x"):
                tx_hex = "0x" + tx_hex

            # 广播 approve
            broadcast_payload = {
                "jsonrpc": "2.0", "id": 1,
                "method": "eth_sendRawTransaction",
                "params": [tx_hex],
            }
            async with session.post(rpc_url, json=broadcast_payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.json()
                if "error" in data:
                    log.warning(f"Approve failed: {data['error']}")
                else:
                    log.info(f"Approve tx: {data.get('result', '')}")
                    await asyncio.sleep(3)  # 等待 approve 确认

        except Exception as e:
            log.warning(f"Approve check/send error: {e}")

    # ── 全局单例 ──────────────────────────────────────────────────

_executor: Optional[TradeExecutor] = None


def get_trade_executor() -> TradeExecutor:
    global _executor
    if _executor is None:
        _executor = TradeExecutor()
    return _executor


# ═══════════════════════════════════════════════════════════════
# W3 D3 — Safety Pre-Check Helper
# ═══════════════════════════════════════════════════════════════

def check_safety_for_trade(ctx: Dict[str, Any]):
    """跑 SafetyEngine.check_trade,返回第一条 BLOCK (或 None 全过)。

    用法:
      block = check_safety_for_trade({
        "amount_usd": 250, "action": "buy", "mode": "auto",
        "regime": "TRENDING_UP", "agent_global_state": "normal",
        "is_honeypot": False, "liquidity_usd": 50000,
        "hitl_required": False, "hitl_approved": True,
        ...  # 完整字段见 docs/agent-pm/08-safety-policy.md
      })
      if block is not None:
          return TradeResult(success=False, error=f"BLOCKED: {block.rule_id}")
      # 否则继续执行真金交易

    引用: docs/agent-pm/17-tech-plan.md Phase 0 + agent/safety_engine.py
    无副作用,幂等,纯查询(但 SafetyEngine 内部可能 trip CB)。
    """
    try:
        from agent.safety_engine import get_safety_engine, CheckOutcome, CheckResult
        engine = get_safety_engine()
        # R37 Kill Switch:任何 severity=blocked 的 CB(含 CB14 manual kill switch)
        # 立即拒绝所有交易,无论 ctx 内容如何
        if engine.get_global_state() == "blocked":
            actives = engine.get_active_breakers()
            if actives:
                cb_id = next(iter(actives.keys()))
                state = actives[cb_id]
                return CheckResult(
                    rule_id=cb_id,
                    rule_name=f"agent globally blocked ({state.name})",
                    outcome=CheckOutcome.BLOCK,
                    reason=state.reason or "global blocked",
                    severity="BLOCK",
                )
        results = engine.check_trade(ctx)
        for r in results:
            if r.outcome == CheckOutcome.BLOCK:
                return r
    except Exception as e:
        log.error("safety check failed: %s", e, exc_info=True)
        # SafetyEngine 自身故障 → fail-safe BLOCK(对应 CB12)
        try:
            from agent.safety_engine import CheckResult, CheckOutcome
            return CheckResult(
                rule_id="CB12",
                rule_name="SafetyEngine 不可用 fail-safe",
                outcome=CheckOutcome.BLOCK,
                reason=str(e),
            )
        except Exception:
            # 连 import 都失败,只能裸 dataclass
            class _MinimalBlock:
                rule_id = "CB12"
                rule_name = "fail-safe"
                reason = str(e)
            return _MinimalBlock()
    return None
