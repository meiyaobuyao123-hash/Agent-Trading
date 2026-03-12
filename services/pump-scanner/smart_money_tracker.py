"""
Multi-chain Smart Money Tracker
Monitors smart wallet transactions across SOL/ETH/BSC/Base
Aggregates buy/sell signals and calculates heat scores
"""
import json
import logging
import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Set

import aiohttp

from database import get_db

logger = logging.getLogger("smart_money_tracker")


class SmartMoneyTracker:
    """Tracks smart money wallet activity across multiple chains."""

    DEXSCREENER_BASE = "https://api.dexscreener.com"

    EXPLORER_APIS = {
        "solana": "https://api.helius.xyz/v0",
        "eth": "https://api.etherscan.io/api",
        "bsc": "https://api.bscscan.com/api",
        "base": "https://api.basescan.org/api",
    }

    def __init__(self):
        self.db = get_db()
        self.wallets: Dict[str, List[Dict[str, Any]]] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._helius_key = os.getenv("HELIUS_API_KEY", "")
        self._etherscan_key = os.getenv("ETHERSCAN_API_KEY", "")
        self._bscscan_key = os.getenv("BSCSCAN_API_KEY", "")
        self._basescan_key = os.getenv("BASESCAN_API_KEY", "")

    async def init(self):
        """Load wallets and init HTTP session."""
        self._session = aiohttp.ClientSession()
        await self._load_wallets()
        total = sum(len(v) for v in self.wallets.values())
        logger.info("SmartMoneyTracker initialized: %d wallets, %d chains",
                     total, len(self.wallets))

    async def close(self):
        if self._session:
            await self._session.close()

    async def _load_wallets(self):
        """Load wallets from DB + seed JSON file."""
        # Load from DB
        try:
            res = self.db.table("smart_wallets").select(
                "wallet, chain, tier, label"
            ).eq("is_blacklisted", False).execute()
            for w in res.data:
                chain = w.get("chain", "solana")
                self.wallets.setdefault(chain, []).append({
                    "address": w["wallet"],
                    "chain": chain,
                    "tier": w.get("tier", "watching"),
                    "label": w.get("label", ""),
                })
        except Exception as e:
            logger.warning("Failed to load wallets from DB: %s", e)

        # Load from seed JSON
        seed_path = os.path.join(
            os.path.dirname(__file__), "data", "smart_wallets_expanded.json"
        )
        if os.path.exists(seed_path):
            try:
                with open(seed_path) as f:
                    data = json.load(f)
                existing: Set[str] = set()
                for chain_wallets in self.wallets.values():
                    for w in chain_wallets:
                        existing.add(w["address"].lower())
                for w in data.get("wallets", []):
                    if w["address"].lower() not in existing:
                        chain = w.get("chain", "solana")
                        self.wallets.setdefault(chain, []).append(w)
                        existing.add(w["address"].lower())
            except Exception as e:
                logger.warning("Failed to load seed wallets: %s", e)

    async def scan_all_chains(self):
        """Main entry: scan all chains and aggregate signals."""
        logger.info("Starting smart money scan across %d chains...",
                     len(self.wallets))
        all_signals: Dict[str, Dict[str, Any]] = {}

        for chain, wallets in self.wallets.items():
            try:
                chain_signals = await self._scan_chain(chain, wallets)
                for key, sig in chain_signals.items():
                    all_signals[key] = sig
                logger.info("Chain %s: %d signals from %d wallets",
                           chain, len(chain_signals), len(wallets))
            except Exception as e:
                logger.error("Failed to scan chain %s: %s", chain, e)

        if not all_signals:
            logger.info("No signals found, skipping enrichment")
            return

        # Enrich with market data from DexScreener
        await self._enrich_market_data(all_signals)

        # Calculate heat scores
        for sig in all_signals.values():
            sig["heat_score"] = self._calc_heat_score(sig)
            sig["net_flow"] = sig.get("buy_count", 0) - sig.get("sell_count", 0)
            sig["signal_strength"] = self._calc_strength(sig)

        # Upsert to DB
        self._upsert_signals(list(all_signals.values()))
        logger.info("Smart money scan complete: %d signals upserted",
                     len(all_signals))

    async def _scan_chain(
        self, chain: str, wallets: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Scan a single chain's wallets for recent token transactions."""
        signals: Dict[str, Dict[str, Any]] = {}

        for wallet in wallets:
            try:
                txs = await self._get_wallet_transactions(
                    chain, wallet["address"]
                )
                tier = wallet.get("tier", "watching")

                for tx in txs:
                    token_addr = tx.get("token_address", "")
                    if not token_addr:
                        continue
                    key = "%s:%s" % (chain, token_addr)
                    if key not in signals:
                        signals[key] = {
                            "chain": chain,
                            "token_address": token_addr,
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
                    volume = tx.get("volume_usd", 0.0)

                    if is_buy:
                        sig["buy_count"] += 1
                        sig["buy_volume"] += volume
                        sig["_buyers"].add(wallet["address"])
                        if tier == "elite":
                            sig["elite_buy_count"] += 1
                        elif tier == "verified":
                            sig["verified_buy_count"] += 1
                    else:
                        sig["sell_count"] += 1
                        sig["sell_volume"] += volume
                        sig["_sellers"].add(wallet["address"])
                        if tier == "elite":
                            sig["elite_sell_count"] += 1
                        elif tier == "verified":
                            sig["verified_sell_count"] += 1

                    tx_time = tx.get("timestamp")
                    if tx_time and (
                        sig["latest_signal_at"] is None
                        or tx_time > sig["latest_signal_at"]
                    ):
                        sig["latest_signal_at"] = tx_time

                await asyncio.sleep(0.3)  # Rate limiting
            except Exception as e:
                logger.warning(
                    "Failed to scan wallet %s on %s: %s",
                    wallet["address"][:10], chain, e,
                )

        # Finalize unique counts
        for sig in signals.values():
            sig["unique_buyers"] = len(sig.pop("_buyers", set()))
            sig["unique_sellers"] = len(sig.pop("_sellers", set()))

        return signals

    async def _get_wallet_transactions(
        self, chain: str, address: str
    ) -> List[Dict[str, Any]]:
        """Get recent swap transactions for a wallet."""
        if chain == "solana":
            return await self._get_solana_txs(address)
        else:
            return await self._get_evm_txs(chain, address)

    async def _get_solana_txs(self, address: str) -> List[Dict[str, Any]]:
        """Get recent Solana token swaps via Helius."""
        if not self._helius_key:
            return []
        url = "%s/addresses/%s/transactions" % (
            self.EXPLORER_APIS["solana"], address
        )
        params = {"api-key": self._helius_key, "type": "SWAP", "limit": "50"}
        try:
            async with self._session.get(
                url, params=params,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                results: List[Dict[str, Any]] = []
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                for tx in data:
                    ts = tx.get("timestamp", 0)
                    if not ts:
                        continue
                    tx_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                    if tx_time < cutoff:
                        continue
                    for event in tx.get("events", {}).get(
                        "swap", {}
                    ).get("tokenInputs", []):
                        results.append({
                            "token_address": event.get("mint", ""),
                            "token_name": "",
                            "token_symbol": "",
                            "type": "sell",
                            "volume_usd": 0.0,
                            "timestamp": tx_time.isoformat(),
                        })
                    for event in tx.get("events", {}).get(
                        "swap", {}
                    ).get("tokenOutputs", []):
                        results.append({
                            "token_address": event.get("mint", ""),
                            "token_name": "",
                            "token_symbol": "",
                            "type": "buy",
                            "volume_usd": 0.0,
                            "timestamp": tx_time.isoformat(),
                        })
                return results
        except Exception as e:
            logger.debug("Helius API error for %s: %s", address[:10], e)
            return []

    async def _get_evm_txs(
        self, chain: str, address: str
    ) -> List[Dict[str, Any]]:
        """Get recent EVM token transfers via block explorer APIs."""
        api_base = self.EXPLORER_APIS.get(chain, "")
        api_key = {
            "eth": self._etherscan_key,
            "bsc": self._bscscan_key,
            "base": self._basescan_key,
        }.get(chain, "")

        if not api_base:
            return []

        params: Dict[str, Any] = {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 50,
            "sort": "desc",
        }
        if api_key:
            params["apikey"] = api_key

        try:
            async with self._session.get(
                api_base, params=params,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                results: List[Dict[str, Any]] = []
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                for tx in data.get("result", []):
                    if not isinstance(tx, dict):
                        continue
                    ts = int(tx.get("timeStamp", "0"))
                    tx_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                    if tx_time < cutoff:
                        continue
                    is_buy = tx.get("to", "").lower() == address.lower()
                    decimals = int(tx.get("tokenDecimal", "18"))
                    raw_val = int(tx.get("value", "0"))
                    value = raw_val / (10 ** decimals) if decimals > 0 else 0.0
                    results.append({
                        "token_address": tx.get("contractAddress", ""),
                        "token_name": tx.get("tokenName", ""),
                        "token_symbol": tx.get("tokenSymbol", ""),
                        "type": "buy" if is_buy else "sell",
                        "volume_usd": value,
                        "timestamp": tx_time.isoformat(),
                    })
                return results
        except Exception as e:
            logger.debug(
                "Explorer API error for %s on %s: %s",
                address[:10], chain, e,
            )
            return []

    async def _enrich_market_data(
        self, signals: Dict[str, Dict[str, Any]]
    ):
        """Enrich signals with market data from DexScreener."""
        chain_map = {
            "solana": "solana", "eth": "ethereum",
            "bsc": "bsc", "base": "base",
        }

        for chain in set(sig["chain"] for sig in signals.values()):
            chain_sigs = [s for s in signals.values() if s["chain"] == chain]
            ds_chain = chain_map.get(chain, chain)

            for i in range(0, len(chain_sigs), 30):
                batch = chain_sigs[i:i + 30]
                addresses = ",".join(s["token_address"] for s in batch)
                url = "%s/tokens/v1/%s/%s" % (
                    self.DEXSCREENER_BASE, ds_chain, addresses
                )
                try:
                    async with self._session.get(
                        url, timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                        by_addr: Dict[str, Dict[str, Any]] = {}
                        pairs = data if isinstance(data, list) else data.get(
                            "pairs", []
                        )
                        for pair in pairs:
                            addr = pair.get("baseToken", {}).get(
                                "address", ""
                            ).lower()
                            if addr and addr not in by_addr:
                                by_addr[addr] = pair

                        for sig in batch:
                            pair = by_addr.get(
                                sig["token_address"].lower()
                            )
                            if pair:
                                sig["price_usd"] = float(
                                    pair.get("priceUsd") or 0
                                )
                                sig["market_cap_usd"] = float(
                                    pair.get("marketCap")
                                    or pair.get("fdv") or 0
                                )
                                sig["liquidity_usd"] = float(
                                    pair.get("liquidity", {}).get("usd") or 0
                                )
                                sig["volume_24h_usd"] = float(
                                    pair.get("volume", {}).get("h24") or 0
                                )
                                pc = pair.get("priceChange", {})
                                sig["price_change_24h"] = float(
                                    pc.get("h24") or 0
                                )
                                sig["price_change_1h"] = float(
                                    pc.get("h1") or 0
                                )
                                sig["image_url"] = pair.get(
                                    "info", {}
                                ).get("imageUrl", "")
                                sig["pair_address"] = pair.get(
                                    "pairAddress", ""
                                )
                                sig["dex_id"] = pair.get("dexId", "")
                                if not sig["token_name"]:
                                    sig["token_name"] = pair.get(
                                        "baseToken", {}
                                    ).get("name", "")
                                if not sig["token_symbol"]:
                                    sig["token_symbol"] = pair.get(
                                        "baseToken", {}
                                    ).get("symbol", "")
                except Exception as e:
                    logger.warning(
                        "DexScreener enrichment failed for %s: %s", chain, e
                    )
                await asyncio.sleep(1)

    def _calc_heat_score(self, sig: Dict[str, Any]) -> float:
        """Calculate heat score from tiered wallet activity."""
        watching_buy = max(
            sig.get("buy_count", 0)
            - sig.get("elite_buy_count", 0)
            - sig.get("verified_buy_count", 0),
            0,
        )
        watching_sell = max(
            sig.get("sell_count", 0)
            - sig.get("elite_sell_count", 0)
            - sig.get("verified_sell_count", 0),
            0,
        )

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
        """Calculate signal strength."""
        if (
            sig.get("elite_buy_count", 0) >= 2
            and sig.get("net_flow", 0) >= 3
        ):
            return "strong"
        if sig.get("elite_buy_count", 0) >= 1 or sig.get("net_flow", 0) >= 2:
            return "medium"
        return "weak"

    def _upsert_signals(self, signals: List[Dict[str, Any]]):
        """Upsert aggregated signals to smart_money_signals table."""
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
                self.db.table("smart_money_signals").upsert(
                    row, on_conflict="chain,token_address"
                ).execute()
            except Exception as e:
                logger.warning(
                    "Failed to upsert signal %s:%s: %s",
                    sig["chain"], sig["token_address"][:10], e,
                )


# Module-level singleton
_tracker: Optional[SmartMoneyTracker] = None


async def run_smart_money_scan():
    """Entry point for APScheduler."""
    global _tracker
    if _tracker is None:
        _tracker = SmartMoneyTracker()
        await _tracker.init()
    await _tracker.scan_all_chains()
