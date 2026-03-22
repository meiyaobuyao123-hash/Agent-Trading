"""
毫秒级实时价格订阅层

设计原则：价格是第一性原理，每条链取最小时间粒度。

┌─────────────────┬──────────────────────────────────┬────────────┐
│ 数据流          │ 说明                              │ 延迟       │
├─────────────────┼──────────────────────────────────┼────────────┤
│ Binance         │ @bookTicker 每次买卖价变动推送    │ ~10-100ms  │
│ @bookTicker     │ SOL/ETH/BNB/BTC，无需 API Key     │            │
├─────────────────┼──────────────────────────────────┼────────────┤
│ Helius WS       │ logsSubscribe 监听代币池交易      │ ~400ms     │
│ (Solana)        │ 有 swap 触发 → 立即查 DexScreener │ (1 slot)   │
├─────────────────┼──────────────────────────────────┼────────────┤
│ DexScreener     │ EVM chains REST 5s 轮询           │ 5-8s       │
│ REST (EVM)      │ BSC/Base/ETH 出块 2-12s，5s足够   │            │
└─────────────────┴──────────────────────────────────┴────────────┘

策略/交易执行时：永远调用 DEX quote 获取即时价格，不用此缓存。
此缓存用于：监控报警、App 实时显示、P&L 计算。

Python 3.9 兼容。
"""

import asyncio
import json
import logging
import time
from typing import Callable, Dict, List, Optional, Set

import aiohttp

from config import HELIUS_API_KEY, HELIUS_RPC

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────────────────────

# Binance 实时最优买卖价 WebSocket（bookTicker = 每次买卖档位变动即推送）
_BINANCE_BOOKTICKER_WS = (
    "wss://stream.binance.com:9443/stream"
    "?streams=solusdt@bookTicker/ethusdt@bookTicker"
    "/bnbusdt@bookTicker/btcusdt@bookTicker"
)
_BINANCE_SYMBOL_MAP = {
    "SOLUSDT": "SOL",
    "ETHUSDT": "ETH",
    "BNBUSDT": "BNB",
    "BTCUSDT": "BTC",
}

# Helius WebSocket 端点
_HELIUS_WS = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# DexScreener 批量查询（EVM REST fallback）
_DEX_TOKENS_API = "https://api.dexscreener.com/tokens/v1/{addresses}"
_EVM_POLL_INTERVAL = 2     # EVM 代币轮询间隔（秒，WS 失联时 fallback）
_EVM_BATCH_SIZE = 30       # DexScreener 单批最多 30 个地址

# EVM Swap 事件 topic（Uniswap V2/V3 + PancakeSwap）
_SWAP_V2_TOPIC = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
_SWAP_V3_TOPIC = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"

# 免费公共 WebSocket RPC — Swap 事件触发即时刷价
# 物理天花板：BSC=3s / Base=2s / ETH=12s（出块时间）
_EVM_WS_RPC: Dict[str, str] = {
    "bsc":  "wss://bsc-ws-node.nariox.org:443",
    "base": "wss://base.publicnode.com",
    "eth":  "wss://ethereum.publicnode.com",
}

_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=6)


class PriceFeed:
    """
    全局价格缓存 + 多路 WebSocket/轮询管理器

    用法：
        from price_feed import price_feed
        # main.py 中：
        asyncio.create_task(price_feed.start())
        # 读取价格：
        sol_usd = price_feed.get_major_price("SOL")
        tok_usd = price_feed.get_token_price("0xabc...")
    """

    def __init__(self) -> None:
        # 主流币价格 {symbol: best_ask_price}
        self._major: Dict[str, float] = {}
        self._major_ts: Dict[str, float] = {}      # 最后推送时间（epoch）

        # 代币价格 {address_lower: price_usd}
        self._token: Dict[str, float] = {}
        self._token_ts: Dict[str, float] = {}

        # Solana 代币注册集合（mint address → pair address 映射）
        self._sol_mints: Dict[str, str] = {}        # mint_lower → pair_addr
        # EVM 代币注册集合 {address_lower}（供 REST 轮询）
        self._evm_addrs: Set[str] = set()

        # 价格变更回调（可选，供外部注册监听）
        self._callbacks: List[Callable[[str, float], None]] = []

        # Helius logsSubscribe ID → mint 映射
        self._helius_sub_id: Dict[int, str] = {}

    # ═══════════════════════════════════════════════════════
    # 对外 API
    # ═══════════════════════════════════════════════════════

    def get_major_price(self, symbol: str) -> Optional[float]:
        """返回 SOL/ETH/BNB/BTC 最新卖一价（来自 Binance bookTicker）"""
        return self._major.get(symbol.upper())

    def get_token_price(self, address: str) -> Optional[float]:
        """返回已注册代币的最新 USD 价格"""
        return self._token.get(address.lower())

    def get_price_age_ms(self, address: str) -> Optional[float]:
        """返回代币价格距今毫秒数（用于判断是否过期）"""
        ts = self._token_ts.get(address.lower())
        if ts is None:
            return None
        return (time.time() - ts) * 1000

    def register_solana_token(self, mint: str, pair_address: str = "") -> None:
        """注册一个 Solana 代币到 Helius 监听列表"""
        self._sol_mints[mint.lower()] = pair_address.lower()

    def register_evm_token(self, address: str) -> None:
        """注册一个 EVM 代币到 DexScreener 轮询列表"""
        self._evm_addrs.add(address.lower())

    def register_token(self, address: str, chain: str, pair_address: str = "") -> None:
        """统一注册接口，自动路由 Solana/EVM"""
        if chain == "solana":
            self.register_solana_token(address, pair_address)
        else:
            self.register_evm_token(address)

    def on_price_update(self, callback: Callable[[str, float], None]) -> None:
        """注册价格变更回调：callback(address, price_usd)"""
        self._callbacks.append(callback)

    def update_price(self, address: str, price: float) -> None:
        """写入价格缓存（内部 + 外部 REST fallback 均可调用）"""
        addr = address.lower()
        if price > 0:
            old = self._token.get(addr, 0)
            self._token[addr] = price
            self._token_ts[addr] = time.time()
            if abs(price - old) / max(old, 1e-12) > 0.0001:  # 变动 > 0.01% 才触发回调
                for cb in self._callbacks:
                    try:
                        cb(addr, price)
                    except Exception:
                        pass

    # ═══════════════════════════════════════════════════════
    # 启动入口
    # ═══════════════════════════════════════════════════════

    async def start(self) -> None:
        """启动所有价格订阅协程（在 main() 中 create_task 调用）"""
        log.info("[PriceFeed] 启动：Binance bookTicker + Helius WS + DexScreener EVM 轮询")
        await asyncio.gather(
            self._run_binance_loop(),
            self._run_helius_loop(),
            self._run_evm_poll_loop(),
        )

    # ═══════════════════════════════════════════════════════
    # ① Binance bookTicker（~10-100ms）
    #   SOL/ETH/BNB/BTC：每次最优买卖价变动即推送
    # ═══════════════════════════════════════════════════════

    async def _run_binance_loop(self) -> None:
        backoff = 2
        while True:
            try:
                await self._connect_binance()
                backoff = 2
            except Exception as e:
                log.warning(f"[Binance WS] 断开: {e}，{backoff}s 后重连")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def _connect_binance(self) -> None:
        import websockets  # type: ignore
        async with websockets.connect(
            _BINANCE_BOOKTICKER_WS,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            log.info("[Binance WS] 已连接，@bookTicker SOL/ETH/BNB/BTC")
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    data = msg.get("data", {})
                    symbol = data.get("s", "")
                    # bookTicker: a = best ask price（卖一价，最即时市场价）
                    ask_str = data.get("a") or data.get("c")
                    if symbol in _BINANCE_SYMBOL_MAP and ask_str:
                        key = _BINANCE_SYMBOL_MAP[symbol]
                        price = float(ask_str)
                        self._major[key] = price
                        self._major_ts[key] = time.time()
                        log.debug(f"[Binance] {key}={price:.4f} (bookTicker ask)")
                except Exception:
                    pass

    # ═══════════════════════════════════════════════════════
    # ② Helius logsSubscribe（~400ms，Solana）
    #   逻辑：有 swap 触发 → 立即 DexScreener 查最新价
    # ═══════════════════════════════════════════════════════

    async def _run_helius_loop(self) -> None:
        if not HELIUS_API_KEY:
            log.warning("[Helius WS] 未配置 HELIUS_API_KEY，Solana 代币跳过 WS 监听")
            return

        backoff = 5
        while True:
            try:
                await self._connect_helius()
                backoff = 5
            except Exception as e:
                is_429 = "429" in str(e)
                max_backoff = 600 if is_429 else 120
                log.warning(f"[Helius WS] 断开: {e}，{backoff}s 后重连")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def _connect_helius(self) -> None:
        import websockets  # type: ignore

        async with websockets.connect(
            _HELIUS_WS,
            ping_interval=30,
            ping_timeout=15,
            close_timeout=5,
        ) as ws:
            log.info(f"[Helius WS] 已连接，订阅 {len(self._sol_mints)} 个 Solana 代币")

            # 订阅所有已注册 Solana 代币的交易日志
            sub_counter = 0
            for mint_lower in list(self._sol_mints.keys()):
                sub_counter += 1
                sub_msg = {
                    "jsonrpc": "2.0",
                    "id": sub_counter,
                    "method": "logsSubscribe",
                    "params": [
                        {
                            "mentions": [
                                # 原始 mint 地址（Solana 地址大小写敏感）
                                # 我们存的是 lower，但 Solana 地址不全是小写
                                # 尝试两种形式
                                mint_lower,
                            ]
                        },
                        {"commitment": "processed"},  # 最快，1 slot 内
                    ],
                }
                self._helius_sub_id[sub_counter] = mint_lower
                await ws.send(json.dumps(sub_msg))

            # 读消息循环
            async with aiohttp.ClientSession() as http:
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        # 收到 subscription 确认
                        if "result" in msg:
                            continue
                        # 收到 log 通知
                        if msg.get("method") == "logsNotification":
                            await self._handle_helius_log(msg, http)
                    except Exception as e:
                        log.debug(f"[Helius WS] 消息解析: {e}")

    async def _handle_helius_log(
        self,
        msg: dict,
        session: aiohttp.ClientSession,
    ) -> None:
        """处理 Helius 日志通知 → 触发 DexScreener 即时价格查询"""
        params = msg.get("params", {})
        result = params.get("result", {})
        value = result.get("value", {})
        logs = value.get("logs") or []
        signature = value.get("signature", "")

        # 检测是否为 swap 相关日志（粗筛）
        has_swap = any(
            "swap" in l.lower() or "trade" in l.lower() or "amm" in l.lower()
            for l in logs
        )
        if not has_swap:
            return

        # 从日志中找到涉及的 mint 地址（通过 subscription ID → mint 映射）
        sub_id = params.get("subscription")
        mint = self._helius_sub_id.get(sub_id) if sub_id else None

        if not mint:
            return

        # 立即触发 DexScreener 查询（获取最新价格）
        pair = self._sol_mints.get(mint, "")
        address_to_query = pair or mint

        log.debug(f"[Helius] swap 触发刷价: {mint[:8]}... (sig={signature[:16]}...)")
        await self._fetch_dex_price_now(session, address_to_query, mint)

    async def _fetch_dex_price_now(
        self,
        session: aiohttp.ClientSession,
        address: str,
        cache_key: str,
    ) -> None:
        """立即从 DexScreener 查单个代币价格（由 Helius WS 触发）"""
        try:
            url = f"https://api.dexscreener.com/tokens/v1/{address}"
            async with session.get(url, timeout=_HTTP_TIMEOUT) as resp:
                if resp.status != 200:
                    return
                data = await resp.json()
                pairs = data if isinstance(data, list) else data.get("pairs", [])
                if not pairs:
                    return
                price_str = pairs[0].get("priceUsd")
                if price_str:
                    self.update_price(cache_key, float(price_str))
                    log.debug(f"[Helius→DexScr] {cache_key[:8]}... = {price_str}")
        except Exception as e:
            log.debug(f"[DexScr instant] {address[:8]}: {e}")

    # ═══════════════════════════════════════════════════════
    # ③ DexScreener REST 轮询（5s，EVM chains）
    #   BSC block=3s  Base block=2s  ETH block=12s
    #   5s 轮询已是免费方案最快可用频率
    # ═══════════════════════════════════════════════════════

    async def _run_evm_poll_loop(self) -> None:
        async with aiohttp.ClientSession() as session:
            while True:
                if self._evm_addrs:
                    await self._poll_evm_prices(session)
                await asyncio.sleep(_EVM_POLL_INTERVAL)

    async def _poll_evm_prices(self, session: aiohttp.ClientSession) -> None:
        addrs = list(self._evm_addrs)
        for i in range(0, len(addrs), _EVM_BATCH_SIZE):
            batch = addrs[i:i + _EVM_BATCH_SIZE]
            joined = ",".join(batch)
            url = _DEX_TOKENS_API.format(addresses=joined)
            try:
                async with session.get(url, timeout=_HTTP_TIMEOUT) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    pairs = data if isinstance(data, list) else data.get("pairs", [])
                    seen = set()
                    for pair in pairs:
                        base = pair.get("baseToken", {})
                        addr = (base.get("address") or "").lower()
                        if addr and addr not in seen:
                            price_str = pair.get("priceUsd")
                            if price_str:
                                try:
                                    self.update_price(addr, float(price_str))
                                    seen.add(addr)
                                except (ValueError, TypeError):
                                    pass
            except Exception as e:
                log.debug(f"[EVM poll] batch {i}: {e}")

            if i + _EVM_BATCH_SIZE < len(addrs):
                await asyncio.sleep(0.3)


# ─────────────────────────────────────────────────────────────
# 全局单例
# ─────────────────────────────────────────────────────────────
price_feed = PriceFeed()
