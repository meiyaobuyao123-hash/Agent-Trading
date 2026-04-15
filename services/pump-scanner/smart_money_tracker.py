"""
Multi-chain Smart Money Tracker
- SOL: Helius accountSubscribe WebSocket (~400ms感知)
- ETH/BSC/Base: OKX Wallet API 5s轮询 (平均2.5s感知，20 req/s)
"""
import json
import logging
import asyncio
import os
import hmac
import hashlib
import base64
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Set
from collections import defaultdict

import aiohttp
import websockets

from database import get_db
import okx_market_client as okx
from config import OKX_CHAIN_INDEX

logger = logging.getLogger("smart_money_tracker")

# OKX Wallet API — 不需要白名单，20 req/s
_OKX_WALLET_BASE = "https://web3.okx.com"
_OKX_TX_PATH = "/api/v5/wallet/post-transaction/transactions-by-address"
_OKX_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# EVM chainIndex → chain name
_EVM_CHAINS = {
    "eth":  "1",
    "bsc":  "56",
    "base": "8453",
}

# Helius WS
_HELIUS_KEY = os.getenv("HELIUS_API_KEY", "")
_HELIUS_WS = f"wss://mainnet.helius-rpc.com/?api-key={_HELIUS_KEY}"

# 扫描窗口
_SCAN_HOURS = 1          # 每次轮询拉最近 1h 交易
_EVM_POLL_INTERVAL = 5   # EVM 轮询间隔（秒）


def _okx_sign(secret: str, timestamp: str, method: str, path: str, body: str = "") -> str:
    msg = timestamp + method + path + body
    return base64.b64encode(
        hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
    ).decode()


class SmartMoneyTracker:
    """
    实时聪明钱追踪器。
    调用 start() 启动后台任务，不再依赖 APScheduler 每15分钟调度。
    """

    DEXSCREENER_BASE = "https://api.dexscreener.com"

    def __init__(self):
        self.db = get_db()
        self.wallets: Dict[str, List[Dict[str, Any]]] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._helius_key = _HELIUS_KEY
        self._okx_key = os.getenv("OKX_API_KEY", "")
        self._okx_secret = os.getenv("OKX_SECRET_KEY", "")
        self._okx_pass = os.getenv("OKX_PASSPHRASE", "")
        # 去重：避免同一笔 tx 被重复处理
        self._seen_txids: Set[str] = set()
        self._running = False
        # OKX toplist 冷却：每条链最多每10s调一次，防429
        self._last_okx_toplist: Dict[str, float] = {}
        self._okx_toplist_cooldown = 10.0
        # 模拟盘去重：同一代币同一来源只触发一次买入
        self._sim_triggered: Set[str] = set()

    async def init(self):
        self._session = aiohttp.ClientSession()
        await self._load_wallets()
        total = sum(len(v) for v in self.wallets.values())
        logger.info("SmartMoneyTracker init: %d wallets, %d chains", total, len(self.wallets))

    async def close(self):
        self._running = False
        if self._session:
            await self._session.close()

    # ──────────────────────────────────────────────
    # 钱包加载
    # ──────────────────────────────────────────────

    async def _load_wallets(self):
        try:
            # 分页加载所有钱包（Supabase 默认 limit 1000）
            all_data = []
            page_size = 1000
            offset = 0
            while True:
                res = (
                    self.db.table("smart_wallets")
                    .select("wallet, tier")
                    .eq("is_blacklisted", False)
                    .range(offset, offset + page_size - 1)
                    .execute()
                )
                batch = res.data or []
                all_data.extend(batch)
                if len(batch) < page_size:
                    break
                offset += page_size

            for w in all_data:
                addr = w["wallet"]
                tier = w.get("tier", "watching")
                if addr.startswith("0x"):
                    for ch in ("eth", "bsc", "base"):
                        self.wallets.setdefault(ch, []).append({"address": addr, "chain": ch, "tier": tier})
                else:
                    self.wallets.setdefault("solana", []).append({"address": addr, "chain": "solana", "tier": tier})
            logger.info("Loaded %d wallets from DB (paginated)", len(all_data))
        except Exception as e:
            logger.warning("DB wallets load failed: %s", e)

        seed_path = os.path.join(os.path.dirname(__file__), "data", "smart_wallets_expanded.json")
        if os.path.exists(seed_path):
            try:
                with open(seed_path) as f:
                    data = json.load(f)
                existing: Set[str] = {w["address"].lower() for wl in self.wallets.values() for w in wl}
                for w in data.get("wallets", []):
                    if w["address"].lower() not in existing:
                        chain = w.get("chain", "solana")
                        self.wallets.setdefault(chain, []).append(w)
                        existing.add(w["address"].lower())
            except Exception as e:
                logger.warning("Seed wallets load failed: %s", e)

    # ──────────────────────────────────────────────
    # 主入口：启动实时追踪
    # ──────────────────────────────────────────────

    async def start(self):
        """启动实时追踪 — 在 main.py 中 asyncio.create_task(tracker.start())"""
        self._running = True

        # 构建 SOL 钱包 HashSet（O(1) 查找）
        sol_wallets = self.wallets.get("solana", [])
        self._sol_wallet_set: Dict[str, Dict[str, Any]] = {
            w["address"].lower(): w for w in sol_wallets
        }
        # 构建 EVM 钱包 HashSet
        self._evm_wallet_set: Dict[str, Dict[str, Any]] = {}
        for chain in ("eth", "bsc", "base"):
            for w in self.wallets.get(chain, []):
                self._evm_wallet_set[w["address"].lower()] = w

        sol_count = len(self._sol_wallet_set)
        evm_count = len(self._evm_wallet_set)
        logger.info(
            "SmartMoneyTracker started (SOL DEX Monitor %d wallets + EVM DEX Monitor %d wallets)",
            sol_count, evm_count,
        )
        await asyncio.gather(
            self._run_sol_dex_monitor(),
            self._run_evm_dex_monitor(),
            self._run_evm_poll_loop(),  # 保留 OKX 轮询作为补充
        )

    # ──────────────────────────────────────────────
    # SOL: DEX 程序级监控（毫秒级，全量覆盖）
    # 监控 Raydium/Jupiter/Pump.fun 的所有 swap
    # 用 HashSet 匹配我们的钱包地址
    # ──────────────────────────────────────────────

    # Solana DEX 程序 ID
    _SOL_DEX_PROGRAMS = [
        "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM V4
        "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",   # Jupiter V6
        "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",   # Pump.fun
        "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",   # Raydium CLMM
        "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",    # Orca Whirlpool
        "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo",   # Meteora DLMM
    ]

    async def _run_sol_dex_monitor(self):
        """监控 SOL DEX 程序的所有 swap，用 HashSet 匹配聪明钱"""
        if not self._sol_wallet_set or not self._helius_key:
            logger.warning("SOL DEX Monitor: no wallets or Helius key, skip")
            return

        logger.info(
            "SOL DEX Monitor: watching %d programs, matching %d wallets",
            len(self._SOL_DEX_PROGRAMS), len(self._sol_wallet_set),
        )
        backoff = 5
        while self._running:
            try:
                await self._connect_sol_dex_ws()
                backoff = 5
            except Exception as e:
                # Helius 免费版 429 需要更长冷却（10 分钟级），普通错误保持 120s
                err_str = str(e)
                is_429 = "429" in err_str or "rejected" in err_str.lower() or "rate" in err_str.lower()
                max_backoff = 600 if is_429 else 120
                logger.warning(
                    "SOL DEX WS disconnected: %s, reconnect in %ds (max=%ds, 429=%s)",
                    e, backoff, max_backoff, is_429,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def _connect_sol_dex_ws(self):
        """订阅 DEX 程序的 logsSubscribe，解析每笔 swap"""
        async with websockets.connect(
            _HELIUS_WS,
            ping_interval=30,
            ping_timeout=15,
            close_timeout=5,
            max_size=2**20,
        ) as ws:
            # 每个 DEX 程序一个 logsSubscribe — 间隔 1s 避免 Helius 免费版 429 burst
            for i, program_id in enumerate(self._SOL_DEX_PROGRAMS):
                await ws.send(json.dumps({
                    "jsonrpc": "2.0",
                    "id": i + 1,
                    "method": "logsSubscribe",
                    "params": [
                        {"mentions": [program_id]},
                        {"commitment": "processed"},
                    ],
                }))
                await asyncio.sleep(1.0)
            logger.info("SOL DEX WS: %d program subscriptions sent", len(self._SOL_DEX_PROGRAMS))

            async for raw in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue

                # 跳过订阅确认
                if "id" in msg and "result" in msg:
                    continue

                # logsNotification → 解析 signature → 获取交易详情
                if msg.get("method") == "logsNotification":
                    params = msg.get("params", {})
                    value = params.get("result", {}).get("value", {})
                    sig = value.get("signature", "")
                    err = value.get("err")
                    if not sig or err or sig in self._seen_txids:
                        continue
                    self._seen_txids.add(sig)
                    # 异步处理，不阻塞 WS 读取
                    asyncio.create_task(self._process_sol_dex_tx(sig))

    async def _process_sol_dex_tx(self, signature: str):
        """获取交易详情，匹配聪明钱地址"""
        try:
            # Helius Enhanced Transaction API — 返回解析后的交易
            url = f"https://api.helius.xyz/v0/transactions/?api-key={self._helius_key}"
            async with self._session.post(
                url,
                json={"transactions": [signature]},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
                    return
                txs = await resp.json()
                if not txs:
                    return
                tx = txs[0]

            # 检查 feePayer 是否是我们的钱包
            fee_payer = tx.get("feePayer", "").lower()
            wallet = self._sol_wallet_set.get(fee_payer)

            if not wallet:
                # 检查所有 accountData
                for acc in tx.get("accountData", []):
                    addr = acc.get("account", "").lower()
                    wallet = self._sol_wallet_set.get(addr)
                    if wallet:
                        break

            if not wallet:
                return  # 不是我们的钱包

            address = wallet["address"]
            parsed = []

            # 解析 swap events
            native_sol = 0.0
            for nt in tx.get("nativeTransfers", []):
                if nt.get("fromUserAccount", "").lower() == address.lower():
                    native_sol += abs(float(nt.get("amount", 0))) / 1e9

            ts = tx.get("timestamp", 0)
            tx_time = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else datetime.now(timezone.utc).isoformat()

            for event in tx.get("events", {}).get("swap", {}).get("tokenOutputs", []):
                mint = event.get("mint", "")
                if not mint or mint == "So11111111111111111111111111111111111111112":
                    continue
                token_amount = float(event.get("rawTokenAmount", {}).get("tokenAmount", 0) or 0)
                decimals = int(event.get("rawTokenAmount", {}).get("decimals", 0) or 0)
                qty = token_amount / (10 ** decimals) if decimals > 0 else token_amount
                parsed.append({
                    "token_address": mint,
                    "type": "buy",
                    "volume_usd": native_sol * 150,
                    "_token_qty": qty,
                    "_is_token_qty": True,
                    "timestamp": tx_time,
                })

            for event in tx.get("events", {}).get("swap", {}).get("tokenInputs", []):
                mint = event.get("mint", "")
                if not mint or mint == "So11111111111111111111111111111111111111112":
                    continue
                token_amount = float(event.get("rawTokenAmount", {}).get("tokenAmount", 0) or 0)
                decimals = int(event.get("rawTokenAmount", {}).get("decimals", 0) or 0)
                qty = token_amount / (10 ** decimals) if decimals > 0 else token_amount
                parsed.append({
                    "token_address": mint,
                    "type": "sell",
                    "volume_usd": 0.0,
                    "_token_qty": qty,
                    "_is_token_qty": True,
                    "timestamp": tx_time,
                })

            if parsed:
                sym = wallet.get("tier", "watching")
                logger.info(
                    "[SOL DEX] 聪明钱交易 %s(%s): %d 笔 swap",
                    address[:8], sym, len(parsed),
                )
                signals, txns = self._aggregate([{**wallet, "txs": parsed}], "solana")
                await self._enrich_and_save(signals, txns, "solana")

        except Exception as e:
            logger.debug("SOL DEX tx %s: %s", signature[:12], e)

    async def _handle_sol_wallet_change(self, wallet: Dict[str, Any]):
        """WS触发后，立即拉该钱包最新1条SWAP交易"""
        address = wallet["address"]
        url = f"https://api.helius.xyz/v0/addresses/{address}/transactions"
        params = {"api-key": self._helius_key, "type": "SWAP", "limit": "5"}
        try:
            async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return
                txs = await resp.json()
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)
                parsed = []
                for tx in txs:
                    ts = tx.get("timestamp", 0)
                    if not ts:
                        continue
                    tx_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                    if tx_time < cutoff:
                        break  # 已按时间倒序，后面更旧
                    sig = tx.get("signature", "")
                    if sig in self._seen_txids:
                        continue
                    self._seen_txids.add(sig)
                    # Helius swap events: tokenOutputs = buy, tokenInputs = sell
                    # tokenAmount = raw amount, 需要除以 decimals 再乘价格（enrich 阶段）
                    # nativeTransfers 里有 SOL 金额可以近似 USD
                    native_sol = 0.0
                    for nt in tx.get("nativeTransfers", []):
                        if nt.get("fromUserAccount", "").lower() == address.lower():
                            native_sol += abs(float(nt.get("amount", 0))) / 1e9
                    for event in tx.get("events", {}).get("swap", {}).get("tokenOutputs", []):
                        mint = event.get("mint", "")
                        if not mint or mint == "So11111111111111111111111111111111111111112":
                            continue
                        token_amount = float(event.get("rawTokenAmount", {}).get("tokenAmount", 0) or 0)
                        decimals = int(event.get("rawTokenAmount", {}).get("decimals", 0) or 0)
                        qty = token_amount / (10 ** decimals) if decimals > 0 else token_amount
                        parsed.append({
                            "token_address": mint,
                            "type": "buy",
                            "volume_usd": native_sol * 150,  # 近似: SOL 花费 × $150 估价
                            "_token_qty": qty,
                            "_is_token_qty": True,
                            "timestamp": tx_time.isoformat(),
                        })
                    for event in tx.get("events", {}).get("swap", {}).get("tokenInputs", []):
                        mint = event.get("mint", "")
                        if not mint or mint == "So11111111111111111111111111111111111111112":
                            continue
                        token_amount = float(event.get("rawTokenAmount", {}).get("tokenAmount", 0) or 0)
                        decimals = int(event.get("rawTokenAmount", {}).get("decimals", 0) or 0)
                        qty = token_amount / (10 ** decimals) if decimals > 0 else token_amount
                        parsed.append({
                            "token_address": mint,
                            "type": "sell",
                            "volume_usd": 0.0,
                            "_token_qty": qty,
                            "_is_token_qty": True,
                            "timestamp": tx_time.isoformat(),
                        })
                if parsed:
                    signals, txns = self._aggregate([{**wallet, "txs": parsed}], "solana")
                    await self._enrich_and_save(signals, txns, "solana")
        except Exception as e:
            logger.debug("SOL handle_change %s: %s", address[:8], e)

    # ──────────────────────────────────────────────
    # EVM: DEX Swap 事件监控（毫秒级）
    # ──────────────────────────────────────────────

    # Swap event topic: Transfer/Swap 通用签名
    _SWAP_TOPIC = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"  # UniswapV2 Swap
    _SWAP_V3_TOPIC = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"  # UniswapV3 Swap

    # 免费公共 WS 端点
    _EVM_WS_ENDPOINTS = {
        "eth": os.getenv("ETH_WS_URL", "wss://ethereum-rpc.publicnode.com"),
        "bsc": os.getenv("BSC_WS_URL", "wss://bsc-rpc.publicnode.com"),
        "base": os.getenv("BASE_WS_URL", "wss://base-rpc.publicnode.com"),
    }

    async def _run_evm_dex_monitor(self):
        """监控 EVM DEX Swap 事件，匹配聪明钱"""
        if not self._evm_wallet_set:
            logger.warning("EVM DEX Monitor: no EVM wallets, skip")
            return

        tasks = []
        for chain, ws_url in self._EVM_WS_ENDPOINTS.items():
            if ws_url:
                tasks.append(self._monitor_evm_chain(chain, ws_url))

        if tasks:
            logger.info("EVM DEX Monitor: watching %d chains, matching %d wallets",
                        len(tasks), len(self._evm_wallet_set))
            await asyncio.gather(*tasks)

    async def _monitor_evm_chain(self, chain: str, ws_url: str):
        """单链 DEX Swap 事件监控"""
        backoff = 5
        while self._running:
            try:
                await self._connect_evm_dex_ws(chain, ws_url)
                backoff = 5
            except Exception as e:
                logger.warning("EVM DEX WS %s disconnected: %s, reconnect in %ds", chain, e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 120)

    async def _connect_evm_dex_ws(self, chain: str, ws_url: str):
        """订阅 EVM 链上 Swap 事件 log"""
        async with websockets.connect(
            ws_url,
            ping_interval=30,
            ping_timeout=15,
            close_timeout=5,
            max_size=2**20,
        ) as ws:
            # 订阅 Swap 事件 (V2 + V3)
            sub_msg = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_subscribe",
                "params": ["logs", {
                    "topics": [[self._SWAP_TOPIC, self._SWAP_V3_TOPIC]],
                }],
            })
            await ws.send(sub_msg)
            logger.info("EVM DEX WS %s: subscribed to Swap events", chain)

            async for raw in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue

                # 跳过订阅确认
                if "id" in msg:
                    continue

                params = msg.get("params", {})
                result = params.get("result", {})
                if not result:
                    continue

                tx_hash = result.get("transactionHash", "")
                if not tx_hash or tx_hash in self._seen_txids:
                    continue

                # Swap 事件的 topics[1] 或 topics[2] 通常是 sender/recipient
                topics = result.get("topics", [])
                data = result.get("data", "")

                # 从 topics 提取地址（去掉前缀0x + 24个0）
                involved_addrs = set()
                for t in topics[1:]:
                    if len(t) == 66:  # 0x + 64 hex
                        addr = "0x" + t[26:]  # 取后 40 个字符
                        involved_addrs.add(addr.lower())

                # 检查是否匹配我们的钱包
                matched_wallet = None
                for addr in involved_addrs:
                    wallet = self._evm_wallet_set.get(addr)
                    if wallet:
                        matched_wallet = wallet
                        break

                if not matched_wallet:
                    continue

                self._seen_txids.add(tx_hash)
                # 异步获取交易详情
                asyncio.create_task(
                    self._process_evm_dex_swap(chain, tx_hash, matched_wallet)
                )

    async def _process_evm_dex_swap(self, chain: str, tx_hash: str, wallet: Dict[str, Any]):
        """获取 EVM swap 交易详情"""
        try:
            # 使用 OKX 获取交易详情
            txs = await self._get_evm_txs_okx(chain, wallet["address"])
            if txs:
                logger.info(
                    "[EVM DEX] 聪明钱交易 %s(%s/%s): %d 笔",
                    wallet["address"][:8], chain, wallet.get("tier", "?"), len(txs),
                )
                signals, txn_list = self._aggregate([{**wallet, "txs": txs}], chain)
                await self._enrich_and_save(signals, txn_list, chain)
        except Exception as e:
            logger.debug("EVM DEX swap %s/%s: %s", chain, tx_hash[:12], e)

    # ──────────────────────────────────────────────
    # EVM: OKX 轮询（补充，覆盖非 DEX swap 交易）
    # ──────────────────────────────────────────────

    _EVM_GROUP_A_INTERVAL = 120   # elite/verified: 每 2 分钟一轮
    _EVM_GROUP_B_INTERVAL = 900   # watching: 每 15 分钟一轮

    async def _run_evm_poll_loop(self):
        evm_wallets: List[Dict[str, Any]] = []
        for chain in ("eth", "bsc", "base"):
            evm_wallets.extend(self.wallets.get(chain, []))

        if not evm_wallets:
            logger.warning("EVM: no wallets, skip poll loop")
            return

        # 分优先级
        group_a = [w for w in evm_wallets if w.get("tier") in ("elite", "verified")]
        group_b = [w for w in evm_wallets if w.get("tier") not in ("elite", "verified")]
        logger.info(
            "EVM: %d total — Group A (elite/verified): %d, Group B (watching): %d",
            len(evm_wallets), len(group_a), len(group_b),
        )

        # 并发运行两组
        await asyncio.gather(
            self._evm_poll_group(group_a, "A", self._EVM_GROUP_A_INTERVAL),
            self._evm_poll_group(group_b, "B", self._EVM_GROUP_B_INTERVAL),
        )

    async def _evm_poll_group(self, wallets: List[Dict[str, Any]], group: str, interval: int):
        """按间隔轮询一组 EVM 钱包"""
        if not wallets:
            return
        while self._running:
            start = asyncio.get_event_loop().time()
            try:
                await self._poll_evm_wallets(wallets)
                elapsed = asyncio.get_event_loop().time() - start
                logger.info("EVM Group %s: polled %d wallets in %.1fs", group, len(wallets), elapsed)
            except Exception as e:
                logger.warning("EVM Group %s poll error: %s", group, e)
            elapsed = asyncio.get_event_loop().time() - start
            wait = max(0, interval - elapsed)
            await asyncio.sleep(wait)

    async def _poll_evm_wallets(self, wallets: List[Dict[str, Any]]):
        """OKX Wallet API: 20 req/s 并发，每5s扫完所有EVM钱包"""
        semaphore = asyncio.Semaphore(20)  # OKX限速20 req/s

        async def fetch_one(w: Dict[str, Any]):
            async with semaphore:
                txs = await self._get_evm_txs_okx(w["chain"], w["address"])
                return w, txs

        tasks = [fetch_one(w) for w in wallets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 按链聚合
        by_chain: Dict[str, List[Dict[str, Any]]] = {}
        for result in results:
            if isinstance(result, Exception):
                continue
            w, txs = result
            if not txs:
                continue
            entry = {**w, "txs": txs}
            by_chain.setdefault(w["chain"], []).append(entry)

        for chain, entries in by_chain.items():
            signals, txns = self._aggregate(entries, chain)
            if signals:
                await self._enrich_and_save(signals, txns, chain)

    async def _get_evm_txs_okx(self, chain: str, address: str) -> List[Dict[str, Any]]:
        """OKX Wallet API 查询钱包最近交易 — 20 req/s，无需白名单
        端点: POST /api/v5/wallet/post-transaction/transactions-by-address
        参数: address, chains (不是 chainIndex)
        需要: User-Agent 绕过 Cloudflare + web3.okx.com base URL
        """
        chain_index = _EVM_CHAINS.get(chain, "1")
        begin_time = int((time.time() - _SCAN_HOURS * 3600) * 1000)  # ms

        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        params_str = f"address={address}&chains={chain_index}&limit=50"
        path_with_params = f"{_OKX_TX_PATH}?{params_str}"
        sign = _okx_sign(self._okx_secret, timestamp, "GET", path_with_params)

        headers = {
            "OK-ACCESS-KEY": self._okx_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self._okx_pass,
            "Content-Type": "application/json",
            "User-Agent": _OKX_UA,
        }
        url = _OKX_WALLET_BASE + path_with_params

        try:
            async with self._session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    logger.debug("OKX Wallet API HTTP %s for %s %s", resp.status, chain, address[:8])
                    return []
                data = await resp.json()
                if data.get("code") != "0":
                    logger.debug("OKX Wallet API %s %s: %s", chain, address[:8], data.get("msg"))
                    return []

                results: List[Dict[str, Any]] = []
                cutoff_ms = begin_time
                # 新结构: data[0].transactionList[]
                for page in data.get("data", []):
                    for tx in page.get("transactionList", []):
                        tx_time_ms = int(tx.get("txTime", 0))
                        if tx_time_ms < cutoff_ms:
                            continue
                        tx_hash = tx.get("txHash", "")
                        if not tx_hash or tx_hash in self._seen_txids:
                            continue
                        if tx.get("txStatus") != "success":
                            continue
                        self._seen_txids.add(tx_hash)

                        token_addr = tx.get("tokenAddress", "")
                        if not token_addr or token_addr == "0x0000000000000000000000000000000000000000":
                            continue

                        tx_time = datetime.fromtimestamp(tx_time_ms / 1000, tz=timezone.utc).isoformat()
                        # 判断买卖：to 里有 address = buy，from 里有 address = sell
                        addr_lower = address.lower()
                        to_addrs = [t.get("address", "").lower() for t in tx.get("to", [])]
                        is_buy = addr_lower in to_addrs
                        # OKX 返回 amount（原始代币数量）和 tokenAmount（可能有 USD）
                        raw_amount = float(tx.get("amount") or tx.get("tokenAmount") or 0)
                        results.append({
                            "token_address": token_addr.lower(),
                            "token_name": tx.get("symbol", ""),
                            "token_symbol": tx.get("symbol", ""),
                            "type": "buy" if is_buy else "sell",
                            "volume_usd": raw_amount,  # 代币数量，enrich阶段乘价格转USD
                            "_is_token_qty": True,
                            "timestamp": tx_time,
                        })
                return results
        except Exception as e:
            logger.debug("OKX Wallet API error %s %s: %s", chain, address[:8], e)
            return []

    # ──────────────────────────────────────────────
    # 信号聚合
    # ──────────────────────────────────────────────

    def _aggregate(
        self, wallet_entries: List[Dict[str, Any]], chain: str
    ):
        """将 wallet+txs 列表聚合为 signals dict + txns list"""
        signals: Dict[str, Dict[str, Any]] = {}
        txns: List[Dict[str, Any]] = []

        for entry in wallet_entries:
            wallet_addr = entry["address"]
            tier = entry.get("tier", "watching")
            for tx in entry.get("txs", []):
                token_addr = tx.get("token_address", "")
                if not token_addr:
                    continue
                key = f"{chain}:{token_addr}"
                if key not in signals:
                    signals[key] = {
                        "chain": chain, "token_address": token_addr,
                        "token_name": tx.get("token_name", ""),
                        "token_symbol": tx.get("token_symbol", ""),
                        "buy_count": 0, "sell_count": 0,
                        "buy_volume": 0.0, "sell_volume": 0.0,
                        "unique_buyers": 0, "unique_sellers": 0,
                        "elite_buy_count": 0, "elite_sell_count": 0,
                        "verified_buy_count": 0, "verified_sell_count": 0,
                        "_buyers": set(), "_sellers": set(),
                        "latest_signal_at": None,
                    }
                sig = signals[key]
                is_buy = tx.get("type") == "buy"
                volume = float(tx.get("volume_usd", 0) or 0)
                if is_buy:
                    sig["buy_count"] += 1
                    sig["buy_volume"] += volume
                    sig["_buyers"].add(wallet_addr)
                    if tier == "elite":
                        sig["elite_buy_count"] += 1
                    elif tier == "verified":
                        sig["verified_buy_count"] += 1
                else:
                    sig["sell_count"] += 1
                    sig["sell_volume"] += volume
                    sig["_sellers"].add(wallet_addr)
                    if tier == "elite":
                        sig["elite_sell_count"] += 1
                    elif tier == "verified":
                        sig["verified_sell_count"] += 1

                tx_time = tx.get("timestamp")
                if tx_time and (sig["latest_signal_at"] is None or tx_time > sig["latest_signal_at"]):
                    sig["latest_signal_at"] = tx_time

                txns.append({
                    "chain": chain,
                    "token_address": token_addr,
                    "wallet_address": wallet_addr,
                    "wallet_tier": tier,
                    "tx_type": "buy" if is_buy else "sell",
                    "volume_usd": volume,
                    "_is_token_qty": tx.get("_is_token_qty", False),
                    "_token_qty": tx.get("_token_qty", 0),
                    "tx_time": tx_time,
                })

        for sig in signals.values():
            sig["unique_buyers"] = len(sig.pop("_buyers", set()))
            sig["unique_sellers"] = len(sig.pop("_sellers", set()))

        return signals, txns

    # ──────────────────────────────────────────────
    # 模拟盘去重（持久化）
    # ──────────────────────────────────────────────

    async def _already_sim_triggered(self, chain: str, address: str) -> bool:
        """查询 24h 内是否已有同代币的 smart_money sim 买入

        用 DB 作为权威去重，防止进程重启后 _sim_triggered 丢失导致重复买入。
        """
        try:
            import asyncio as _asyncio
            from datetime import datetime as _dt, timedelta as _td, timezone as _tz

            cutoff = (_dt.now(_tz.utc) - _td(hours=24)).isoformat()
            from database import get_db
            # supabase-py 是同步客户端，用 to_thread 避免阻塞事件循环
            def _query():
                return (get_db().table("hot_sim_trades")
                        .select("id", count="exact")
                        .eq("source", "smart_money")
                        .eq("chain", chain)
                        .eq("address", address)
                        .gte("entered_at", cutoff)
                        .limit(0)
                        .execute())
            res = await _asyncio.to_thread(_query)
            return (res.count or 0) > 0
        except Exception as e:
            logger.debug("[SM] sim 去重查询失败 %s: %s", address[:10], e)
            return False  # fail-open：查询失败时允许触发（宁可多买也别漏买）

    # ──────────────────────────────────────────────
    # 市场数据 Enrich + 保存
    # ──────────────────────────────────────────────

    async def _enrich_and_save(
        self, signals: Dict[str, Dict[str, Any]], txns: List[Dict[str, Any]], chain: str
    ):
        chain_index = OKX_CHAIN_INDEX.get(chain)
        okx_by_addr: Dict[str, dict] = {}
        if chain_index:
            now_ts = time.time()
            last = self._last_okx_toplist.get(chain, 0)
            if now_ts - last >= self._okx_toplist_cooldown:
                self._last_okx_toplist[chain] = now_ts
                try:
                    okx_by_addr = await okx.get_toplist_multi_sort(chain_index, session=self._session)
                except Exception as e:
                    logger.debug("OKX toplist %s: %s", chain, e)

        unfilled: List[Dict[str, Any]] = []
        for sig in signals.values():
            item = okx_by_addr.get(sig["token_address"].lower())
            if item:
                sig["price_usd"] = item["price_usd"]
                sig["market_cap_usd"] = item["market_cap_usd"]
                sig["liquidity_usd"] = item["liquidity_usd"]
                sig["volume_24h_usd"] = item["volume_24h"]
                sig["price_change_24h"] = item["change_24h"]
                sig["price_change_1h"] = 0
                sig["image_url"] = item.get("token_logo_url", "")
                if not sig["token_symbol"]:
                    sig["token_symbol"] = item.get("symbol", "")
            else:
                unfilled.append(sig)

        if unfilled:
            await self._enrich_dexscreener(chain, unfilled)

        # 计算得分
        for sig in signals.values():
            sig["heat_score"] = self._calc_heat_score(sig)
            sig["net_flow"] = sig.get("buy_count", 0) - sig.get("sell_count", 0)
            sig["signal_strength"] = self._calc_strength(sig)

        # token数量 → USD（SOL + EVM 通用）
        price_map = {sig["token_address"].lower(): sig.get("price_usd", 0) for sig in signals.values()}
        for txn in txns:
            if txn.pop("_is_token_qty", False):
                price = price_map.get(txn["token_address"].lower(), 0)
                token_qty = txn.pop("_token_qty", 0)
                if price > 0 and token_qty > 0:
                    txn["volume_usd"] = token_qty * price
                elif price > 0 and txn["volume_usd"] > 0:
                    txn["volume_usd"] = txn["volume_usd"] * price
            else:
                txn.pop("_token_qty", None)

        # 注意：先写 txns，后写 signals。
        # 因为 _upsert_signals 内部会从 txns 表 SELECT 真实窗口聚合（修复 unique_buyers bug），
        # 必须确保当前批次的 txns 已写入，否则会少算最新数据。
        self._upsert_txns(txns)
        self._upsert_signals(list(signals.values()))
        self._cleanup_old_txns()

        # 实时 bot 检测：同代币60秒内买卖 → 立即黑名单
        self._realtime_bot_detect(txns, chain)

        # DEX swap 搭车推价格 → PriceFeed（所有 callback 自动收到）
        # + 聪明钱强信号触发模拟买入
        try:
            from price_feed import price_feed
            watched = price_feed.get_watched_tokens()
            from hot_sim_trader import get_sim_trader
            sim = get_sim_trader()
            for sig in signals.values():
                price = sig.get("price_usd", 0)
                addr = sig.get("token_address", "")
                if price > 0 and addr:
                    # 搭车推价格：如果该代币在追踪列表中，走 PriceFeed 统一分发
                    if addr.lower() in watched:
                        price_feed.update_price(addr, price)
                    else:
                        # 不在追踪列表，仍直接推给 sim_trader
                        sim.on_price_update(addr, price)
                    # 聪明钱强信号触发模拟买入（基于真实数据校准阈值 + 去重）
                    # 根因：原阈值 buyers>=3 过严，实际 99% 信号 buyers 是 1-2
                    # 改为：heat>=10 或 (elite买≥1 且 buyers>=2)，更贴合真实分布
                    heat = sig.get("heat_score", 0) or 0
                    buyers = sig.get("unique_buyers", 0) or 0
                    elite_buys = sig.get("elite_buy_count", 0) or 0
                    verified_buys = sig.get("verified_buy_count", 0) or 0
                    mc = sig.get("market_cap_usd", 0) or 0
                    _sim_key = f"sm:{chain}:{addr}"

                    # 触发条件（满足任一）：
                    #   A. heat_score >= 10（强信号）
                    #   B. elite 买入 ≥ 1 且 buyers ≥ 2（精英+跟风）
                    #   C. verified 买入 ≥ 2 且 buyers ≥ 2（多个验证钱包）
                    cond_a = heat >= 10
                    cond_b = elite_buys >= 1 and buyers >= 2
                    cond_c = verified_buys >= 2 and buyers >= 2
                    if ((cond_a or cond_b or cond_c)
                            and price > 0 and (mc <= 0 or price < mc)
                            and _sim_key not in self._sim_triggered):
                        # DB 查重：24h 内已有同代币的 smart_money 仓位则跳过
                        # （内存 _sim_triggered 重启丢失，DB 作为权威去重）
                        if await self._already_sim_triggered(chain, addr):
                            self._sim_triggered.add(_sim_key)  # 加入内存避免下次再查
                            continue
                        self._sim_triggered.add(_sim_key)
                        sim.on_token_enter(
                            address=addr,
                            chain=sig.get("chain", ""),
                            symbol=sig.get("token_symbol", "?"),
                            price=price,
                            score=heat,
                            source="smart_money",
                        )
        except Exception:
            pass

        logger.info("Smart money [%s]: %d signals, %d txns saved", chain, len(signals), len(txns))

    async def _enrich_dexscreener(self, chain: str, sigs: List[Dict[str, Any]]):
        chain_map = {"solana": "solana", "eth": "ethereum", "bsc": "bsc", "base": "base"}
        ds_chain = chain_map.get(chain, chain)
        for i in range(0, len(sigs), 30):
            batch = sigs[i:i + 30]
            addresses = ",".join(s["token_address"] for s in batch)
            url = f"{self.DEXSCREENER_BASE}/tokens/v1/{ds_chain}/{addresses}"
            try:
                async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    pairs = data if isinstance(data, list) else data.get("pairs", [])
                    by_addr = {p.get("baseToken", {}).get("address", "").lower(): p for p in pairs}
                    for sig in batch:
                        pair = by_addr.get(sig["token_address"].lower())
                        if not pair:
                            continue
                        sig["price_usd"] = float(pair.get("priceUsd") or 0)
                        sig["market_cap_usd"] = float(pair.get("marketCap") or pair.get("fdv") or 0)
                        sig["liquidity_usd"] = float(pair.get("liquidity", {}).get("usd") or 0)
                        sig["volume_24h_usd"] = float(pair.get("volume", {}).get("h24") or 0)
                        pc = pair.get("priceChange", {})
                        sig["price_change_24h"] = float(pc.get("h24") or 0)
                        sig["price_change_1h"] = float(pc.get("h1") or 0)
                        sig["image_url"] = pair.get("info", {}).get("imageUrl", "")
                        sig["pair_address"] = pair.get("pairAddress", "")
                        sig["dex_id"] = pair.get("dexId", "")
                        if not sig["token_name"]:
                            sig["token_name"] = pair.get("baseToken", {}).get("name", "")
                        if not sig["token_symbol"]:
                            sig["token_symbol"] = pair.get("baseToken", {}).get("symbol", "")
            except Exception as e:
                logger.warning("DexScreener %s: %s", chain, e)
            await asyncio.sleep(0.5)

    # ──────────────────────────────────────────────
    # 打分
    # ──────────────────────────────────────────────

    def _calc_heat_score(self, sig: Dict[str, Any]) -> float:
        watching_buy = max(sig.get("buy_count", 0) - sig.get("elite_buy_count", 0) - sig.get("verified_buy_count", 0), 0)
        watching_sell = max(sig.get("sell_count", 0) - sig.get("elite_sell_count", 0) - sig.get("verified_sell_count", 0), 0)

        # 基础 tier 权重分
        tier_score = (
            sig.get("elite_buy_count", 0) * 5
            + sig.get("verified_buy_count", 0) * 3
            + watching_buy * 1
            - sig.get("elite_sell_count", 0) * 4
            - sig.get("verified_sell_count", 0) * 2
            - watching_sell * 0.5
        )

        # 集中度加成：多个不同钱包买入同一代币 = 强信号
        unique_buyers = sig.get("unique_buyers", 0)
        if unique_buyers >= 20:
            concentration_bonus = 40
        elif unique_buyers >= 10:
            concentration_bonus = 20
        elif unique_buyers >= 5:
            concentration_bonus = 10
        elif unique_buyers >= 3:
            concentration_bonus = 5
        else:
            concentration_bonus = 0

        return round(tier_score + concentration_bonus, 1)

    def _calc_strength(self, sig: Dict[str, Any]) -> str:
        unique_buyers = sig.get("unique_buyers", 0)
        elite_buys = sig.get("elite_buy_count", 0)
        net_flow = sig.get("net_flow", 0)

        # 强信号：elite 多次买入 或 多钱包集中买入
        if (elite_buys >= 2 and net_flow >= 3) or unique_buyers >= 5:
            return "strong"
        if elite_buys >= 1 or net_flow >= 2 or unique_buyers >= 3:
            return "medium"
        return "weak"

    # ──────────────────────────────────────────────
    # 信号统计重算（修复 unique_buyers 永远=1 的 bug）
    # ──────────────────────────────────────────────

    # 聚合窗口：用最近 6h 的 txns 计算 unique_buyers 等
    _SIGNAL_AGG_WINDOW_HOURS = 6

    def _recompute_signal_from_txns(self, sig: Dict[str, Any]) -> None:
        """从 smart_money_txns 表查最近 N 小时数据，重算 sig 的统计字段

        修复根因：原 _aggregate 每次只处理 1 个 wallet 的 txs（WS 单笔触发），
        upsert 时按 (chain, token_address) 冲突 → 后写覆盖前面所有数据，
        导致 unique_buyers 永远 = 1。

        正确做法：按时间窗口从 txns 表 SELECT 所有交易，应用层去重计算。
        """
        try:
            from datetime import datetime as _dt, timedelta as _td, timezone as _tz
            cutoff = (_dt.now(_tz.utc) - _td(hours=self._SIGNAL_AGG_WINDOW_HOURS)).isoformat()
            res = (self.db.table("smart_money_txns")
                   .select("wallet_address,wallet_tier,tx_type,volume_usd")
                   .eq("chain", sig["chain"])
                   .eq("token_address", sig["token_address"])
                   .gte("tx_time", cutoff)
                   .limit(1000)
                   .execute())
            txns = res.data or []
            if not txns:
                return  # 保留 _aggregate 计算的原值

            buyers, sellers = set(), set()
            buy_count = sell_count = 0
            buy_vol = sell_vol = 0.0
            elite_buy = elite_sell = 0
            verified_buy = verified_sell = 0

            for t in txns:
                w = t.get("wallet_address", "")
                tier = t.get("wallet_tier", "watching")
                vol = float(t.get("volume_usd") or 0)
                if t.get("tx_type") == "buy":
                    buy_count += 1
                    buy_vol += vol
                    if w:
                        buyers.add(w)
                    if tier == "elite":
                        elite_buy += 1
                    elif tier == "verified":
                        verified_buy += 1
                else:
                    sell_count += 1
                    sell_vol += vol
                    if w:
                        sellers.add(w)
                    if tier == "elite":
                        elite_sell += 1
                    elif tier == "verified":
                        verified_sell += 1

            # 用真实窗口数据覆盖
            sig["unique_buyers"] = len(buyers)
            sig["unique_sellers"] = len(sellers)
            sig["buy_count"] = buy_count
            sig["sell_count"] = sell_count
            sig["buy_volume"] = round(buy_vol, 2)
            sig["sell_volume"] = round(sell_vol, 2)
            sig["elite_buy_count"] = elite_buy
            sig["elite_sell_count"] = elite_sell
            sig["verified_buy_count"] = verified_buy
            sig["verified_sell_count"] = verified_sell
            sig["net_flow"] = round(buy_vol - sell_vol, 2)
            # 重算 heat 和 strength（依赖 unique_buyers）
            sig["heat_score"] = self._calc_heat_score(sig)
            sig["signal_strength"] = self._calc_strength(sig)
        except Exception as e:
            logger.debug("[SM] recompute %s:%s 失败: %s",
                         sig.get("chain"), sig.get("token_address", "")[:10], e)

    # ──────────────────────────────────────────────
    # DB 写入
    # ──────────────────────────────────────────────

    @staticmethod
    def _to_int(v) -> int:
        """安全转 int — DB integer 列不接受 float 字符串"""
        try:
            if v is None:
                return 0
            return int(round(float(v)))
        except (ValueError, TypeError):
            return 0

    def _upsert_signals(self, signals: List[Dict[str, Any]]):
        now = datetime.now(timezone.utc).isoformat()
        _i = self._to_int  # 简写
        for sig in signals:
            # 写入前从 txns 表查真实窗口聚合（修复 unique_buyers 覆盖 bug）
            self._recompute_signal_from_txns(sig)
            row = {
                "chain": sig["chain"],
                "token_address": sig["token_address"],
                "token_name": sig.get("token_name", ""),
                "token_symbol": sig.get("token_symbol", ""),
                # ── DB 是 integer 类型的字段，强制转 int 防止 "invalid input syntax for type integer" ──
                "buy_count": _i(sig.get("buy_count", 0)),
                "sell_count": _i(sig.get("sell_count", 0)),
                "buy_volume": _i(sig.get("buy_volume", 0)),
                "sell_volume": _i(sig.get("sell_volume", 0)),
                "unique_buyers": _i(sig.get("unique_buyers", 0)),
                "unique_sellers": _i(sig.get("unique_sellers", 0)),
                "elite_buy_count": _i(sig.get("elite_buy_count", 0)),
                "elite_sell_count": _i(sig.get("elite_sell_count", 0)),
                "verified_buy_count": _i(sig.get("verified_buy_count", 0)),
                "verified_sell_count": _i(sig.get("verified_sell_count", 0)),
                "heat_score": _i(sig.get("heat_score", 0)),
                "net_flow": _i(sig.get("net_flow", 0)),
                "signal_strength": sig.get("signal_strength", "weak"),
                "price_usd": sig.get("price_usd", 0),
                "market_cap_usd": sig.get("market_cap_usd", 0),
                "liquidity_usd": sig.get("liquidity_usd", 0),
                "volume_24h_usd": sig.get("volume_24h_usd", 0),
                "price_change_24h": sig.get("price_change_24h", 0),
                "price_change_1h": sig.get("price_change_1h", 0),
                "image_url": sig.get("image_url"),
                "pair_address": sig.get("pair_address"),
                "dex_id": sig.get("dex_id"),
                "latest_signal_at": sig.get("latest_signal_at"),
                "scan_time": now,
            }
            try:
                self.db.table("smart_money_signals").upsert(row, on_conflict="chain,token_address").execute()
            except Exception as e:
                logger.warning("Upsert signal %s:%s: %s", sig["chain"], sig["token_address"][:10], e)

    def _upsert_txns(self, txns: List[Dict[str, Any]]):
        if not txns:
            return
        now = datetime.now(timezone.utc).isoformat()
        seen_keys: Set[tuple] = set()
        rows = []
        for t in txns:
            if not t.get("tx_time"):
                continue
            # 同批次按冲突键去重，避免 PostgreSQL "cannot affect row a second time"
            dedup_key = (t["chain"], t["token_address"], t["wallet_address"], t["tx_type"], t["tx_time"])
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            rows.append({
                "chain": t["chain"],
                "token_address": t["token_address"],
                "wallet_address": t["wallet_address"],
                "wallet_tier": t.get("wallet_tier", "watching"),
                "tx_type": t["tx_type"],
                "volume_usd": t.get("volume_usd", 0),
                "market_cap_at_tx": t.get("market_cap_at_tx", 0),
                "price_at_tx": t.get("price_at_tx", 0),
                "tx_time": t["tx_time"],
                "scan_time": now,
            })
        for i in range(0, len(rows), 50):
            try:
                self.db.table("smart_money_txns").upsert(
                    rows[i:i + 50],
                    on_conflict="chain,token_address,wallet_address,tx_type,tx_time",
                ).execute()
            except Exception as e:
                logger.warning("Upsert txns batch: %s", e)
        logger.info("Upserted %d txns", len(rows))

        # 更新有交易的钱包的 last_seen（防止活跃钱包被误淘汰）
        active_wallets = {t["wallet_address"] for t in txns if t.get("wallet_address")}
        if active_wallets:
            now_iso = datetime.now(timezone.utc).isoformat()
            for wallet in active_wallets:
                try:
                    self.db.table("smart_wallets").update(
                        {"last_seen": now_iso}
                    ).eq("wallet", wallet).execute()
                except Exception:
                    pass
            logger.debug("Updated last_seen for %d active wallets", len(active_wallets))

    def _cleanup_old_txns(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        try:
            self.db.table("smart_money_txns").delete().lt("scan_time", cutoff).execute()
        except Exception as e:
            logger.debug("Cleanup txns: %s", e)

    def _realtime_bot_detect(self, txns: List[Dict[str, Any]], chain: str):
        """实时检测：同代币60秒内买卖 → 立即黑名单（不等2h评估）"""
        # 按钱包+代币分组
        wallet_token_times: Dict[str, Dict[str, List]] = defaultdict(lambda: defaultdict(list))
        for t in txns:
            wallet = t.get("wallet_address", "")
            token = t.get("token_address", "")
            tx_type = t.get("tx_type", "")
            tx_time = t.get("tx_time", "")
            if wallet and token and tx_time:
                wallet_token_times[wallet][token].append((tx_type, tx_time))

        bot_wallets = set()
        for wallet, tokens in wallet_token_times.items():
            for token, entries in tokens.items():
                buys = [e[1] for e in entries if e[0] == "buy"]
                sells = [e[1] for e in entries if e[0] == "sell"]
                if not buys or not sells:
                    continue
                for b_time in buys:
                    for s_time in sells:
                        try:
                            bt = datetime.fromisoformat(b_time.replace("Z", "+00:00"))
                            st = datetime.fromisoformat(s_time.replace("Z", "+00:00"))
                            if abs((st - bt).total_seconds()) < 60:
                                bot_wallets.add(wallet)
                                break
                        except Exception:
                            pass
                    if wallet in bot_wallets:
                        break
                if wallet in bot_wallets:
                    break

        if not bot_wallets:
            return

        # 立即写入黑名单
        now_iso = datetime.now(timezone.utc).isoformat()
        for wallet in bot_wallets:
            try:
                self.db.table("smart_wallets").upsert({
                    "wallet": wallet,
                    "tier": "blacklisted",
                    "is_blacklisted": True,
                    "last_seen": now_iso,
                    "total_trades": 0,
                    "win_trades": 0,
                    "total_sol_in": 0,
                    "active_weeks": 0,
                }, on_conflict="wallet").execute()
            except Exception:
                pass
        logger.warning("[实时Bot检测] %s: 黑名单 %d 个钱包", chain, len(bot_wallets))

    # ──────────────────────────────────────────────
    # 兼容旧接口（APScheduler 调用）
    # ──────────────────────────────────────────────

    async def scan_all_chains(self):
        """兼容旧调用，执行一次全量扫描（EVM用OKX，SOL用Helius REST）"""
        logger.info("scan_all_chains (one-shot, OKX+Helius REST)")
        evm_wallets = []
        for chain in ("eth", "bsc", "base"):
            evm_wallets.extend(self.wallets.get(chain, []))
        if evm_wallets:
            await self._poll_evm_wallets(evm_wallets)
        sol_wallets = self.wallets.get("solana", [])
        for w in sol_wallets:
            txs = await self._get_sol_txs_rest(w["address"])
            if txs:
                signals, txns = self._aggregate([{**w, "txs": txs}], "solana")
                await self._enrich_and_save(signals, txns, "solana")

    async def _get_sol_txs_rest(self, address: str) -> List[Dict[str, Any]]:
        """Helius REST fallback（scan_all_chains 用）"""
        if not self._helius_key:
            return []
        url = f"https://api.helius.xyz/v0/addresses/{address}/transactions"
        params = {"api-key": self._helius_key, "type": "SWAP", "limit": "50"}
        try:
            async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                results = []
                cutoff = datetime.now(timezone.utc) - timedelta(hours=_SCAN_HOURS)
                for tx in data:
                    ts = tx.get("timestamp", 0)
                    if not ts:
                        continue
                    tx_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                    if tx_time < cutoff:
                        break
                    for ev in tx.get("events", {}).get("swap", {}).get("tokenOutputs", []):
                        results.append({"token_address": ev.get("mint", ""), "type": "buy", "volume_usd": 0.0, "timestamp": tx_time.isoformat()})
                    for ev in tx.get("events", {}).get("swap", {}).get("tokenInputs", []):
                        results.append({"token_address": ev.get("mint", ""), "type": "sell", "volume_usd": 0.0, "timestamp": tx_time.isoformat()})
                return results
        except Exception as e:
            logger.debug("Helius REST %s: %s", address[:8], e)
            return []


# ──────────────────────────────────────────────
# 单例
# ──────────────────────────────────────────────

_tracker: Optional[SmartMoneyTracker] = None


async def get_tracker() -> SmartMoneyTracker:
    global _tracker
    if _tracker is None:
        _tracker = SmartMoneyTracker()
        await _tracker.init()
    return _tracker


async def run_smart_money_scan():
    """兼容旧 APScheduler 调用入口"""
    tracker = await get_tracker()
    await tracker.scan_all_chains()
