"""
AVE Cloud Skill 统一客户端

黑客松开关：USE_AVE=true 时启用，所有 AVE API 调用集中在此文件。
Free plan: 1 RPS, Data REST + Chain-Wallet Trading

API 文档: https://github.com/AveCloud/ave-cloud-skill
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any

import aiohttp

from config import AVE_API_KEY, AVE_DATA_BASE, AVE_TRADE_BASE

log = logging.getLogger(__name__)

# AVE 链名映射（我们的链名 → AVE 链名）
_CHAIN_MAP = {
    "solana": "solana",
    "bsc": "bsc",
    "base": "base",
    "eth": "eth",
    "ethereum": "eth",
}

_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)


class AveClient:
    """AVE Cloud API 统一客户端（1 RPS 限速）"""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_req_ts: float = 0.0
        self._lock = asyncio.Lock()

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _throttle(self) -> None:
        """1 RPS 限速"""
        async with self._lock:
            now = time.time()
            gap = now - self._last_req_ts
            if gap < 1.0:
                await asyncio.sleep(1.0 - gap)
            self._last_req_ts = time.time()

    # ═══════════════════════════════════════════════════════
    # 内部 HTTP
    # ═══════════════════════════════════════════════════════

    async def _data_get(self, path: str, params: Optional[dict] = None) -> Optional[dict]:
        """Data REST GET 请求"""
        await self._throttle()
        url = f"{AVE_DATA_BASE}{path}"
        try:
            session = self._get_session()
            async with session.get(
                url, params=params, timeout=_HTTP_TIMEOUT,
                headers={"X-API-KEY": AVE_API_KEY, "Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    log.debug("[AVE] GET %s → %d", path, resp.status)
                    return None
                data = await resp.json()
                if data.get("status") != 1:
                    log.debug("[AVE] GET %s → %s", path, data.get("msg"))
                    return None
                return data.get("data")
        except Exception as e:
            log.warning("[AVE] GET %s error: %s", path, e)
            return None

    async def _trade_post(self, path: str, body: dict) -> Optional[dict]:
        """Trade REST POST 请求"""
        await self._throttle()
        url = f"{AVE_TRADE_BASE}{path}"
        try:
            session = self._get_session()
            async with session.post(
                url, json=body, timeout=_HTTP_TIMEOUT,
                headers={"AVE-ACCESS-KEY": AVE_API_KEY, "Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    log.debug("[AVE] POST %s → %d", path, resp.status)
                    return None
                data = await resp.json()
                if data.get("status") != 200 and data.get("status") != 1:
                    log.debug("[AVE] POST %s → %s", path, data.get("msg"))
                    return None
                return data.get("data")
        except Exception as e:
            log.warning("[AVE] POST %s error: %s", path, e)
            return None

    # ═══════════════════════════════════════════════════════
    # 数据 API（替代 DexScreener）
    # ═══════════════════════════════════════════════════════

    async def get_token_detail(self, address: str, chain: str) -> Optional[dict]:
        """获取单个代币详情（价格/市值/流动性/成交量/持有人）"""
        c = _CHAIN_MAP.get(chain, chain)
        data = await self._data_get(f"/tokens/{address}-{c}")
        if not data:
            return None
        # 嵌套结构：data.token
        token = data.get("token", data) if isinstance(data, dict) else data
        return token

    async def get_batch_prices(self, address_chain_pairs: List[str]) -> Dict[str, float]:
        """
        批量获取代币价格
        address_chain_pairs: ["addr1-solana", "addr2-bsc", ...]
        返回: {addr_lower: price_usd}

        注意: AVE 的 /tokens/price POST 返回空，改用逐个 /tokens/{addr-chain} 查
        但 1 RPS 限速下太慢。改用 trending + search 补充。
        实际策略：调用方应该用 get_token_detail 单个查，或用 get_trending 批量。
        这里做一个 fallback 用的批量（每个 1s）。
        """
        result: Dict[str, float] = {}
        for pair in address_chain_pairs:
            parts = pair.rsplit("-", 1)
            if len(parts) != 2:
                continue
            addr, chain = parts
            detail = await self.get_token_detail(addr, chain)
            if detail:
                price_str = detail.get("current_price_usd")
                if price_str:
                    try:
                        result[addr.lower()] = float(price_str)
                    except (ValueError, TypeError):
                        pass
        return result

    async def get_trending(self, chain: str, limit: int = 50) -> List[dict]:
        """获取链上 trending 代币（替代 OKX TopList）"""
        c = _CHAIN_MAP.get(chain, chain)
        data = await self._data_get("/tokens/trending", {"chain": c, "limit": limit})
        if not data:
            return []
        # 返回格式: {tokens: [...]} 或直接 [...]
        if isinstance(data, list):
            return data
        return data.get("tokens", [])

    # ═══════════════════════════════════════════════════════
    # 安全 API（替代 GoPlus）
    # ═══════════════════════════════════════════════════════

    async def check_risk(self, address: str, chain: str) -> Optional[dict]:
        """
        代币合约安全检测
        返回 GoPlus 兼容格式: {is_honeypot, buy_tax, sell_tax, is_open_source, top10_holder_pct, ...}
        """
        c = _CHAIN_MAP.get(chain, chain)
        data = await self._data_get(f"/contracts/{address}-{c}")
        if not data:
            return None
        return self._convert_risk_to_goplus(data)

    @staticmethod
    def _convert_risk_to_goplus(ave_risk: dict) -> dict:
        """将 AVE risk 格式转为现有 GoPlus 兼容格式"""
        # AVE is_honeypot: -1=未知, 0=否, 1=是
        hp_raw = ave_risk.get("is_honeypot", -1)
        is_honeypot = hp_raw == 1

        # 税率
        buy_tax = float(ave_risk.get("buy_tax") or 0)
        sell_tax = float(ave_risk.get("sell_tax") or 0)

        # Top10 持仓
        top10 = 0.0
        top1 = 0.0
        holders_detail = ave_risk.get("holders_detail", [])
        if isinstance(holders_detail, list):
            for i, h in enumerate(holders_detail[:10]):
                pct = float(h.get("percent", 0))
                top10 += pct
                if i == 0:
                    top1 = pct

        return {
            "is_honeypot": is_honeypot,
            "buy_tax": buy_tax,
            "sell_tax": sell_tax,
            "is_open_source": ave_risk.get("has_code", 0) == 1,
            "top10_holder_pct": round(top10, 4),
            "top1_holder_pct": round(top1, 4),
            "risk_score": ave_risk.get("risk_score", 50),
            "has_mint_method": ave_risk.get("has_mint_method", 0) == 1,
            "has_black_method": ave_risk.get("has_black_method", 0) == 1,
            "can_take_back_ownership": ave_risk.get("can_take_back_ownership", "0") == "1",
            # 原始数据保留
            "_ave_raw": ave_risk,
        }

    # ═══════════════════════════════════════════════════════
    # 聪明钱 API
    # ═══════════════════════════════════════════════════════

    async def get_smart_wallets(self, chain: str, limit: int = 100) -> List[dict]:
        """获取链上聪明钱钱包列表"""
        c = _CHAIN_MAP.get(chain, chain)
        data = await self._data_get(
            "/address/smart_wallet/list", {"chain": c, "limit": limit}
        )
        if not data:
            return []
        if isinstance(data, list):
            return data
        return data.get("list", data.get("wallets", []))

    # ═══════════════════════════════════════════════════════
    # 交易 API（替代 OKX DEX）
    # ═══════════════════════════════════════════════════════

    async def get_quote(
        self, chain: str, in_token: str, out_token: str,
        amount: str, swap_type: str = "buy",
    ) -> Optional[dict]:
        """获取交易报价"""
        c = _CHAIN_MAP.get(chain, chain)
        body = {
            "chain": c,
            "inAmount": amount,
            "inTokenAddress": in_token,
            "outTokenAddress": out_token,
            "swapType": swap_type,
        }
        return await self._trade_post(
            "/v1/thirdParty/chainWallet/getAmountOut", body
        )

    async def create_solana_tx(
        self, in_token: str, out_token: str, amount: str,
        swap_type: str = "buy", slippage: float = 1.0,
        wallet_address: str = "", fee: float = 0.0005,
    ) -> Optional[dict]:
        """创建 Solana 交易数据（需本地签名）"""
        body = {
            "chain": "solana",
            "inAmount": amount,
            "inTokenAddress": in_token,
            "outTokenAddress": out_token,
            "swapType": swap_type,
            "slippage": str(slippage),
            "userAddress": wallet_address,
            "fee": str(fee),
        }
        return await self._trade_post(
            "/v1/thirdParty/chainWallet/createSolanaTx", body
        )

    async def create_evm_tx(
        self, chain: str, in_token: str, out_token: str,
        amount: str, swap_type: str = "buy",
        slippage: float = 1.0, wallet_address: str = "",
    ) -> Optional[dict]:
        """创建 EVM 交易数据（需本地签名）"""
        c = _CHAIN_MAP.get(chain, chain)
        body = {
            "chain": c,
            "inAmount": amount,
            "inTokenAddress": in_token,
            "outTokenAddress": out_token,
            "swapType": swap_type,
            "slippage": str(slippage),
            "userAddress": wallet_address,
        }
        return await self._trade_post(
            "/v1/thirdParty/chainWallet/createEvmTx", body
        )

    async def send_signed_solana_tx(
        self, request_tx_id: str, signed_tx: str,
    ) -> Optional[dict]:
        """发送已签名的 Solana 交易"""
        body = {
            "chain": "solana",
            "requestTxId": request_tx_id,
            "signedTx": signed_tx,
        }
        return await self._trade_post(
            "/v1/thirdParty/chainWallet/sendSignedSolanaTx", body
        )

    async def send_signed_evm_tx(
        self, chain: str, request_tx_id: str, signed_tx: str,
    ) -> Optional[dict]:
        """发送已签名的 EVM 交易"""
        c = _CHAIN_MAP.get(chain, chain)
        body = {
            "chain": c,
            "requestTxId": request_tx_id,
            "signedTx": signed_tx,
        }
        return await self._trade_post(
            "/v1/thirdParty/chainWallet/sendSignedEvmTx", body
        )


# ─────────────────────────────────────────────────────────
# 全局单例
# ─────────────────────────────────────────────────────────
ave = AveClient()
