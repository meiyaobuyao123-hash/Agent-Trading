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
            res = self.db.table("smart_wallets").select("wallet, tier").eq("is_blacklisted", False).execute()
            for w in res.data:
                addr = w["wallet"]
                tier = w.get("tier", "watching")
                if addr.startswith("0x"):
                    for ch in ("eth", "bsc", "base"):
                        self.wallets.setdefault(ch, []).append({"address": addr, "chain": ch, "tier": tier})
                else:
                    self.wallets.setdefault("solana", []).append({"address": addr, "chain": "solana", "tier": tier})
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
        logger.info("SmartMoneyTracker started (SOL WS + EVM 5s OKX polling)")
        await asyncio.gather(
            self._run_sol_ws(),
            self._run_evm_poll_loop(),
        )

    # ──────────────────────────────────────────────
    # SOL: Helius accountSubscribe WebSocket (~400ms)
    # ──────────────────────────────────────────────

    async def _run_sol_ws(self):
        sol_wallets = self.wallets.get("solana", [])
        if not sol_wallets or not self._helius_key:
            logger.warning("SOL: no wallets or Helius key missing, skip WS")
            return

        while self._running:
            try:
                await self._connect_sol_ws(sol_wallets)
            except Exception as e:
                logger.warning("SOL WS disconnected: %s, reconnect in 5s", e)
                await asyncio.sleep(5)

    async def _connect_sol_ws(self, sol_wallets: List[Dict[str, Any]]):
        logger.info("SOL: connecting Helius WS, subscribing %d wallets", len(sol_wallets))
        async with websockets.connect(_HELIUS_WS, ping_interval=20) as ws:
            # 每个钱包发一条订阅
            sub_id_to_wallet: Dict[int, Dict[str, Any]] = {}
            req_id_to_wallet: Dict[int, Dict[str, Any]] = {}
            for i, w in enumerate(sol_wallets):
                req_id = i + 1
                req_id_to_wallet[req_id] = w
                await ws.send(json.dumps({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "method": "accountSubscribe",
                    "params": [
                        w["address"],
                        {"encoding": "jsonParsed", "commitment": "processed"}
                    ]
                }))
                await asyncio.sleep(0.05)  # 避免WS突发

            logger.info("SOL: %d subscriptions sent", len(sol_wallets))

            async for raw in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue

                # 订阅确认 → 记录 subscriptionId
                if "id" in msg and "result" in msg:
                    req_id = msg["id"]
                    sub_id = msg["result"]
                    if req_id in req_id_to_wallet:
                        sub_id_to_wallet[sub_id] = req_id_to_wallet[req_id]
                    continue

                # 账户变更通知
                if msg.get("method") == "accountNotification":
                    sub_id = msg.get("params", {}).get("subscription")
                    wallet = sub_id_to_wallet.get(sub_id)
                    if wallet:
                        asyncio.create_task(
                            self._handle_sol_wallet_change(wallet)
                        )

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
                    for event in tx.get("events", {}).get("swap", {}).get("tokenOutputs", []):
                        parsed.append({
                            "token_address": event.get("mint", ""),
                            "type": "buy", "volume_usd": 0.0,
                            "timestamp": tx_time.isoformat(),
                        })
                    for event in tx.get("events", {}).get("swap", {}).get("tokenInputs", []):
                        parsed.append({
                            "token_address": event.get("mint", ""),
                            "type": "sell", "volume_usd": 0.0,
                            "timestamp": tx_time.isoformat(),
                        })
                if parsed:
                    signals, txns = self._aggregate([{**wallet, "txs": parsed}], "solana")
                    await self._enrich_and_save(signals, txns, "solana")
        except Exception as e:
            logger.debug("SOL handle_change %s: %s", address[:8], e)

    # ──────────────────────────────────────────────
    # EVM: OKX Wallet API 5s轮询 (20 req/s, 平均2.5s感知)
    # ──────────────────────────────────────────────

    async def _run_evm_poll_loop(self):
        evm_wallets: List[Dict[str, Any]] = []
        for chain in ("eth", "bsc", "base"):
            evm_wallets.extend(self.wallets.get(chain, []))

        if not evm_wallets:
            logger.warning("EVM: no wallets, skip poll loop")
            return

        logger.info("EVM: starting OKX 5s poll for %d wallets", len(evm_wallets))
        while self._running:
            start = asyncio.get_event_loop().time()
            try:
                await self._poll_evm_wallets(evm_wallets)
            except Exception as e:
                logger.warning("EVM poll error: %s", e)
            elapsed = asyncio.get_event_loop().time() - start
            wait = max(0, _EVM_POLL_INTERVAL - elapsed)
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
                        results.append({
                            "token_address": token_addr.lower(),
                            "token_name": tx.get("symbol", ""),
                            "token_symbol": tx.get("symbol", ""),
                            "type": "buy" if is_buy else "sell",
                            "volume_usd": 0.0,     # 原始数量未知价格，enrich后换算USD
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
                    "tx_time": tx_time,
                })

        for sig in signals.values():
            sig["unique_buyers"] = len(sig.pop("_buyers", set()))
            sig["unique_sellers"] = len(sig.pop("_sellers", set()))

        return signals, txns

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

        # EVM token数量 → USD
        price_map = {sig["token_address"].lower(): sig.get("price_usd", 0) for sig in signals.values()}
        for txn in txns:
            if txn.pop("_is_token_qty", False):
                price = price_map.get(txn["token_address"].lower(), 0)
                if price > 0:
                    txn["volume_usd"] = txn["volume_usd"] * price

        self._upsert_signals(list(signals.values()))
        self._upsert_txns(txns)
        self._cleanup_old_txns()
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
        score = (
            sig.get("elite_buy_count", 0) * 5
            + sig.get("verified_buy_count", 0) * 3
            + watching_buy * 1
            - sig.get("elite_sell_count", 0) * 4
            - sig.get("verified_sell_count", 0) * 2
            - watching_sell * 0.5
        )
        return round(score, 1)

    def _calc_strength(self, sig: Dict[str, Any]) -> str:
        if sig.get("elite_buy_count", 0) >= 2 and sig.get("net_flow", 0) >= 3:
            return "strong"
        if sig.get("elite_buy_count", 0) >= 1 or sig.get("net_flow", 0) >= 2:
            return "medium"
        return "weak"

    # ──────────────────────────────────────────────
    # DB 写入
    # ──────────────────────────────────────────────

    def _upsert_signals(self, signals: List[Dict[str, Any]]):
        now = datetime.now(timezone.utc).isoformat()
        for sig in signals:
            row = {
                "chain": sig["chain"],
                "token_address": sig["token_address"],
                "token_name": sig.get("token_name", ""),
                "token_symbol": sig.get("token_symbol", ""),
                "buy_count": sig.get("buy_count", 0),
                "sell_count": sig.get("sell_count", 0),
                "buy_volume": sig.get("buy_volume", 0),
                "sell_volume": sig.get("sell_volume", 0),
                "unique_buyers": sig.get("unique_buyers", 0),
                "unique_sellers": sig.get("unique_sellers", 0),
                "elite_buy_count": sig.get("elite_buy_count", 0),
                "elite_sell_count": sig.get("elite_sell_count", 0),
                "verified_buy_count": sig.get("verified_buy_count", 0),
                "verified_sell_count": sig.get("verified_sell_count", 0),
                "heat_score": sig.get("heat_score", 0),
                "net_flow": sig.get("net_flow", 0),
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

    def _cleanup_old_txns(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        try:
            self.db.table("smart_money_txns").delete().lt("scan_time", cutoff).execute()
        except Exception as e:
            logger.debug("Cleanup txns: %s", e)

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
