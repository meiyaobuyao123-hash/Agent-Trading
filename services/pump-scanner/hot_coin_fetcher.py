"""
热币榜多链数据采集器 — OKX 全链路

数据流：
  OKX toplist（发现 + 市场数据：价格/市值/流动性/成交量/涨幅/持仓/Logo）
    → 硬过滤（年龄/流动性/市值/成交量）
    → GoPlus（安全检测：蜜罐/开源/Top10集中度 — OKX 无此数据）
    → Helius（SOL链：Top1持有者精确占比）
    → DexScreener（社交链接：Twitter/Telegram/网站 — OKX 无此数据）
    → 返回富化后的候选列表，供 hot_scorer 打分

覆盖链：SOL / BSC / Base / ETH
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from config import (
    GOPLUS_API, DEXSCREENER_API, HELIUS_RPC,
    HOT_CHAINS, OKX_CHAIN_INDEX,
    HOT_MIN_AGE_DAYS, HOT_MAX_AGE_DAYS,
    HOT_MIN_LIQ_USD, HOT_MAX_LIQ_USD,
    HOT_MIN_MC_USD, HOT_MAX_MC_USD,
    HOT_MIN_VOL_24H_USD, HOT_MIN_LIQ_MC_RATIO,
    HOT_MAX_TAX, HOT_MAX_TOP10_PCT,
)
import okx_market_client as okx
import bitget_market_client as bitget
from price_feed import price_feed

log = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=12)

# 稳定币符号，跳过
_STABLECOINS = {"USDC", "USDT", "BUSD", "DAI", "TUSD", "FRAX", "USDD", "USDP"}


# ═══════════════════════════════════════════════════════════
# Step 1 — OKX toplist：发现候选代币（含市场数据）
# ═══════════════════════════════════════════════════════════

async def _fetch_okx_candidates(
    session: aiohttp.ClientSession,
    chain: str,
) -> List[dict]:
    """
    用 OKX toplist 多时间帧合并发现候选代币。
    4 个时间帧(5m/1h/4h/24h) × 2 个排序(成交量+涨幅) = 8 次调用/链。
    每个代币自带多时间帧的 volume/change/txs 数据，供 scorer 全维度打分。
    """
    chain_index = OKX_CHAIN_INDEX.get(chain)
    if not chain_index:
        log.warning(f"OKX 不支持链 {chain}，跳过")
        return []

    merged = await okx.get_toplist_multi_timeframe(chain_index, session=session)

    # ── OKX 失败时立即切换 Bitget Wallet fallback ────────────
    if not merged:
        log.warning(f"  {chain}: OKX toplist 无数据，切换 Bitget Wallet fallback")
        merged = await bitget.get_toplist_multi_timeframe(chain_index, session=session)
        if merged:
            log.info(f"  {chain}: Bitget fallback 发现 {len(merged)} 个候选")
        else:
            log.warning(f"  {chain}: Bitget fallback 也无数据，跳过本链")
            return []

    log.info(f"  {chain}: OKX 多时间帧发现 {len(merged)} 个候选")

    results = []  # type: List[dict]
    for addr_lower, item in merged.items():
        symbol = item.get("symbol", "")
        if symbol.upper() in _STABLECOINS:
            continue

        results.append({
            "address": item["address"],
            "name": "",
            "symbol": symbol,
            "pair_address": "",
            "dex_id": "",
            "pair_created_at": None,
            "age_days": item.get("age_days"),
            "price_usd": item["price_usd"],
            "market_cap_usd": item["market_cap_usd"],
            "liquidity_usd": item["liquidity_usd"],
            # 多时间帧成交量
            "volume_5m_usd": item.get("volume_5m", 0),
            "volume_1h_usd": item.get("volume_1h", 0),
            "volume_4h_usd": item.get("volume_4h", 0),
            "volume_24h_usd": item.get("volume_24h", 0),
            # 多时间帧涨幅
            "price_change_5m": item.get("change_5m", 0),
            "price_change_1h": item.get("change_1h", 0),
            "price_change_4h": item.get("change_4h", 0),
            "price_change_6h": item.get("change_4h", 0),  # 用 4h 近似 6h
            "price_change_24h": item.get("change_24h", 0),
            # 多时间帧买卖笔数
            "buys_5m": item.get("txs_buy_5m", 0),
            "sells_5m": item.get("txs_sell_5m", 0),
            "buys_1h": item.get("txs_buy_1h", 0),
            "sells_1h": item.get("txs_sell_1h", 0),
            "buys_24h": item.get("txs_buy_24h", 0),
            "sells_24h": item.get("txs_sell_24h", 0),
            # OKX 特有字段
            "okx_holders": item.get("holders", 0),
            "okx_buy_tax": 0,
            "okx_sell_tax": 0,
            "circ_supply": 0,
            "token_logo_url": item.get("token_logo_url", ""),
            "data_source": "okx_toplist",
            # 多时间帧命中数（越多=越强势）
            "timeframe_hits": item.get("timeframe_hits", 1),
            "unique_traders_1h": item.get("unique_traders_1h", 0),
            "unique_traders_24h": item.get("unique_traders_24h", 0),
        })

    return results


# ═══════════════════════════════════════════════════════════
# Step 3 — 硬过滤
# ═══════════════════════════════════════════════════════════

def apply_hard_filter(
    coin: dict,
    mc_max_usd: float = None,
    liq_max_usd: float = None,
) -> Tuple[bool, str]:
    """返回 (通过, 拒绝原因)"""
    age = coin.get("age_days")
    if age is None:
        return False, "年龄未知"
    if not (HOT_MIN_AGE_DAYS <= age <= HOT_MAX_AGE_DAYS):
        return False, f"年龄不符 {age:.1f}d"

    liq = coin.get("liquidity_usd", 0)
    liq_max = liq_max_usd if liq_max_usd is not None else HOT_MAX_LIQ_USD
    if not (HOT_MIN_LIQ_USD <= liq <= liq_max):
        return False, f"流动性不符 ${liq:,.0f}"

    mc = coin.get("market_cap_usd", 0)
    mc_max = mc_max_usd if mc_max_usd is not None else HOT_MAX_MC_USD
    if not (HOT_MIN_MC_USD <= mc <= mc_max):
        return False, f"市值不符 ${mc:,.0f}"

    if coin.get("volume_24h_usd", 0) < HOT_MIN_VOL_24H_USD:
        return False, f"24h量不足 ${coin.get('volume_24h_usd', 0):,.0f}"

    if mc > 0 and liq / mc < HOT_MIN_LIQ_MC_RATIO:
        return False, f"流动性/市值比低 {liq/mc:.1%}"

    return True, ""


# ═══════════════════════════════════════════════════════════
# Step 4 — GoPlus：安全检测 + 持有者数据
# ═══════════════════════════════════════════════════════════

async def _check_goplus(
    session: aiohttp.ClientSession,
    chain: str,
    address: str,
    goplus_chain: str,
) -> dict:
    """返回安全检测字段"""
    try:
        if chain == "solana":
            url = f"{GOPLUS_API}/solana/token_security"
        else:
            url = f"{GOPLUS_API}/token_security/{goplus_chain}"

        async with session.get(
            url, params={"contract_addresses": address}, timeout=_TIMEOUT
        ) as resp:
            if resp.status != 200:
                return {}

            data = await resp.json()
            result = data.get("result", {})

            token_data = (
                result.get(address)
                or result.get(address.lower())
                or (list(result.values())[0] if result else {})
            )
            if not token_data:
                return {}

            holder_count = int(token_data.get("holder_count") or 0)
            top10_pct = float(token_data.get("top10_holder_rate") or 0)

            is_honeypot = str(token_data.get("is_honeypot", "0")) == "1"
            is_open = str(token_data.get("is_open_source", "1")) != "0"
            buy_tax = float(token_data.get("buy_tax") or 0)
            sell_tax = float(token_data.get("sell_tax") or 0)
            cannot_sell = str(token_data.get("cannot_sell_all", "0")) == "1"

            if chain == "solana":
                is_honeypot = str(token_data.get("cannot_buy", "0")) == "1"
                is_open = True

            goplus_risk = (
                is_honeypot
                or cannot_sell
                or buy_tax > HOT_MAX_TAX
                or sell_tax > HOT_MAX_TAX
                or (top10_pct > HOT_MAX_TOP10_PCT and top10_pct > 0)
            )

            return {
                "holder_count": holder_count,
                "top10_holder_pct": top10_pct,
                "is_honeypot": is_honeypot,
                "is_open_source": is_open,
                "buy_tax": buy_tax,
                "sell_tax": sell_tax,
                "goplus_risk": goplus_risk,
            }

    except asyncio.TimeoutError:
        log.debug(f"GoPlus timeout: {chain}/{address[:8]}")
        return {}
    except Exception as e:
        log.debug(f"GoPlus {chain}/{address[:8]}: {e}")
        return {}


# ═══════════════════════════════════════════════════════════
# Step 5 — Helius：SOL Top1 持有者精确占比
# ═══════════════════════════════════════════════════════════

async def _get_sol_top1_pct(
    session: aiohttp.ClientSession,
    mint: str,
) -> Optional[float]:
    """Helius RPC 查询 Top1 持有者占比"""
    supply_payload = {
        "jsonrpc": "2.0", "id": 1,
        "method": "getTokenSupply",
        "params": [mint],
    }
    largest_payload = {
        "jsonrpc": "2.0", "id": 2,
        "method": "getTokenLargestAccounts",
        "params": [mint, {"commitment": "confirmed"}],
    }

    async def _post(payload: dict) -> dict:
        async with session.post(HELIUS_RPC, json=payload, timeout=_TIMEOUT) as r:
            return await r.json()

    try:
        s_data, l_data = await asyncio.gather(
            _post(supply_payload),
            _post(largest_payload),
            return_exceptions=True,
        )
        if isinstance(s_data, Exception) or isinstance(l_data, Exception):
            return None

        total_supply = int(
            s_data.get("result", {}).get("value", {}).get("amount", 0)
        )
        largest = l_data.get("result", {}).get("value", [])

        if not largest or total_supply == 0:
            return None

        top1_amount = int(largest[0].get("amount", 0))
        return round(top1_amount / total_supply, 4)

    except Exception as e:
        log.debug(f"Helius top1 {mint[:8]}: {e}")
        return None


# ═══════════════════════════════════════════════════════════
# Step 6 — DexScreener：社交链接
# ═══════════════════════════════════════════════════════════

async def _get_dexscreener_socials(
    session: aiohttp.ClientSession,
    address: str,
) -> dict:
    """从 DexScreener 获取 Twitter / Telegram / 网站 + 图标"""
    try:
        url = f"{DEXSCREENER_API}/latest/dex/tokens/{address}"
        async with session.get(url, timeout=_TIMEOUT) as resp:
            if resp.status != 200:
                return {}

            data = await resp.json()
            pairs = data.get("pairs") or []
            if not pairs:
                return {}

            info = pairs[0].get("info", {})
            socials = info.get("socials", [])
            websites = info.get("websites", [])
            image_url = info.get("imageUrl") or ""

            return {
                "has_twitter": any(s.get("type") == "twitter" for s in socials),
                "has_telegram": any(s.get("type") == "telegram" for s in socials),
                "has_website": len(websites) > 0,
                "image_url": image_url,
            }
    except Exception as e:
        log.debug(f"DexScreener socials {address[:8]}: {e}")
        return {}


# ═══════════════════════════════════════════════════════════
# 辅助：从 pump_tokens 获取代币图标
# ═══════════════════════════════════════════════════════════

# 简单缓存，避免每个代币重复查询
_pump_image_cache: Dict[str, Optional[str]] = {}

def _get_pump_image(mint: str) -> Optional[str]:
    """从 pump_tokens 表查找代币 image_uri，失败时 fallback Solana RPC 元数据"""
    if mint in _pump_image_cache:
        return _pump_image_cache[mint]
    # Step 1: pump_tokens 表
    try:
        from database import get_db
        db = get_db()
        res = (
            db.table("pump_tokens")
            .select("image_uri")
            .eq("mint", mint)
            .limit(1)
            .execute()
        )
        if res.data and res.data[0].get("image_uri"):
            uri = res.data[0]["image_uri"]
            _pump_image_cache[mint] = uri
            return uri
    except Exception as e:
        log.debug(f"pump_tokens lookup {mint[:8]}: {e}")
    # Step 2: Solana RPC on-chain tokenMetadata
    uri = _get_solana_metadata_image(mint)
    _pump_image_cache[mint] = uri
    return uri


def _get_solana_metadata_image(mint: str) -> Optional[str]:
    """从 Solana RPC 读取 Token-2022 tokenMetadata 扩展中的 image URI"""
    import urllib.request
    import json as _json
    SOLANA_RPC = "https://api.mainnet-beta.solana.com"
    try:
        payload = _json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "getAccountInfo",
            "params": [mint, {"encoding": "jsonParsed"}],
        }).encode()
        req = urllib.request.Request(SOLANA_RPC, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
        extensions = data.get("result", {}).get("value", {}).get("data", {}).get("parsed", {}).get("info", {}).get("extensions", [])
        uri = None
        for ext in extensions:
            if isinstance(ext, dict) and ext.get("extension") == "tokenMetadata":
                uri = ext.get("state", {}).get("uri", "")
                break
        if not uri:
            return None
        # Try to fetch metadata JSON → image field
        meta_urls = [uri]
        if "/ipfs/" in uri:
            h = uri.split("/ipfs/")[-1]
            meta_urls = [
                f"https://quicknode.quicknode-ipfs.com/ipfs/{h}",
                f"https://cloudflare-ipfs.com/ipfs/{h}",
                uri,
            ]
        for murl in meta_urls:
            try:
                req2 = urllib.request.Request(murl, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req2, timeout=8) as r:
                    ct = r.headers.get("Content-Type", "")
                    if "json" in ct or "text" in ct:
                        meta = _json.loads(r.read())
                        img = meta.get("image", "")
                        if img:
                            return img
                    else:
                        return murl
            except Exception:
                continue
        return uri
    except Exception as e:
        log.debug(f"solana metadata {mint[:8]}: {e}")
        return None


# ═══════════════════════════════════════════════════════════
# 辅助：获取已入库代币地址集合
# ═══════════════════════════════════════════════════════════

def _get_known_addresses(chain: str) -> set:
    """从 hot_coins 表读取指定链已入库的代币地址（小写集合）"""
    try:
        from database import get_db
        db = get_db()
        res = (
            db.table("hot_coins")
            .select("address")
            .eq("chain", chain)
            .execute()
        )
        return {r["address"].lower() for r in (res.data or [])}
    except Exception as e:
        log.warning(f"读取已入库地址失败 {chain}: {e}")
        return set()


def _get_known_addresses_with_data(chain: str) -> Dict[str, dict]:
    """从 hot_coins 表读取指定链已入库代币的安全/社交字段（用于增量跳过）"""
    try:
        from database import get_db
        db = get_db()
        res = (
            db.table("hot_coins")
            .select("address, name, symbol, pair_address, dex_id, "
                    "pair_created_at, age_days, "
                    "top10_holder_pct, top1_holder_pct, "
                    "is_honeypot, is_open_source, buy_tax, sell_tax, goplus_risk, "
                    "has_twitter, has_telegram, has_website, "
                    "holder_count, image_url, token_logo_url, circ_supply")
            .eq("chain", chain)
            .execute()
        )
        return {r["address"].lower(): r for r in (res.data or [])}
    except Exception as e:
        log.warning(f"读取已入库数据失败 {chain}: {e}")
        return {}


# ═══════════════════════════════════════════════════════════
# 主函数：全链扫描并富化（支持增量模式）
# ═══════════════════════════════════════════════════════════

async def fetch_hot_coin_candidates(incremental: bool = True) -> List[dict]:
    """
    扫描所有目标链（SOL / BSC / ETH / Base），
    OKX toplist 发现+市场数据 → 硬过滤 → GoPlus → Helius → DexScreener

    incremental=True（默认）:
      已入库代币跳过 GoPlus/Helius/DexScreener，复用 DB 中的安全/社交数据。
      仅新发现的代币走完整富化流程。

    incremental=False:
      所有候选全量富化（用于首次全量扫描或定期安全刷新）。
    """
    all_candidates = []  # type: List[dict]

    async with aiohttp.ClientSession() as session:
        for chain, cfg in HOT_CHAINS.items():
            log.info(f"扫描 {chain}...")
            goplus_chain = cfg["goplus_chain"]

            # ── 增量模式：加载已入库数据 ──────────────────────
            known_data = {}  # type: Dict[str, dict]
            if incremental:
                known_data = _get_known_addresses_with_data(chain)
                log.info(f"  {chain}: 已入库 {len(known_data)} 个代币")

            # ── 1. OKX toplist：发现候选（自带市场数据） ────────
            raw = await _fetch_okx_candidates(session, chain)

            if not raw:
                log.warning(f"  {chain}: OKX toplist 无数据")
                # 链间冷却
                await asyncio.sleep(2)
                continue

            # ── 2. 硬过滤 ───────────────────────────────────────
            mc_max_usd = cfg.get("mc_max_usd")
            liq_max_usd = cfg.get("liq_max_usd")
            filtered = []  # type: List[dict]
            for coin in raw:
                if not coin.get("price_usd"):
                    continue
                ok, reason = apply_hard_filter(
                    coin, mc_max_usd=mc_max_usd, liq_max_usd=liq_max_usd
                )
                if ok:
                    filtered.append(coin)
                else:
                    log.debug(f"  x {coin.get('symbol', '?')} ({coin['address'][:8]}): {reason}")
            log.info(f"  {chain}: 硬过滤后 {len(filtered)} 个")

            # ── 3. 分流：已入库 vs 新发现 ──────────────────────
            new_coins = []     # type: List[dict]
            reuse_coins = []   # type: List[dict]
            for coin in filtered:
                addr_lower = coin["address"].lower()
                if incremental and addr_lower in known_data:
                    db_row = known_data[addr_lower]
                    addr = coin["address"]
                    coin.update({
                        "chain": chain,
                        "holder_count": db_row.get("holder_count", 0),
                        "top10_holder_pct": db_row.get("top10_holder_pct"),
                        "top1_holder_pct": db_row.get("top1_holder_pct"),
                        "is_honeypot": db_row.get("is_honeypot", False),
                        "is_open_source": db_row.get("is_open_source", True),
                        "buy_tax": db_row.get("buy_tax", 0.0),
                        "sell_tax": db_row.get("sell_tax", 0.0),
                        "goplus_risk": db_row.get("goplus_risk", False),
                        "has_twitter": db_row.get("has_twitter", False),
                        "has_telegram": db_row.get("has_telegram", False),
                        "has_website": db_row.get("has_website", False),
                        "image_url": coin.get("token_logo_url") or db_row.get("image_url") or db_row.get("token_logo_url", "") or (_get_pump_image(addr) if addr.endswith("pump") else ""),
                    })
                    reuse_coins.append(coin)
                else:
                    new_coins.append(coin)

            if incremental:
                log.info(f"  {chain}: 复用已入库 {len(reuse_coins)} 个，新发现 {len(new_coins)} 个需富化")

            # ── 4a. 新代币：完整 GoPlus + Helius + DexScreener ─
            enriched = []  # type: List[dict]
            for coin in new_coins:
                addr = coin["address"]

                # GoPlus 安全检测
                gp = await _check_goplus(session, chain, addr, goplus_chain)
                await asyncio.sleep(0.35)

                if gp.get("is_honeypot"):
                    log.debug(f"  蜜罐排除: {coin.get('symbol')} ({addr[:8]})")
                    continue

                gp_holder_count = gp.get("holder_count", 0)
                okx_holders = coin.get("okx_holders", 0)
                holder_count = okx_holders if okx_holders > 0 else gp_holder_count

                if 0 < holder_count < 150:
                    log.debug(f"  x 持有者不足 {holder_count}: {coin.get('symbol')}")
                    continue

                # Helius：SOL 链 Top1 精确占比
                top1_pct = None  # type: Optional[float]
                if chain == "solana":
                    top1_pct = await _get_sol_top1_pct(session, addr)
                    await asyncio.sleep(0.1)

                # DexScreener 社交 + name 补充
                socials = await _get_dexscreener_socials(session, addr)
                await asyncio.sleep(0.2)

                # 买卖税：OKX 有则用 OKX，否则用 GoPlus
                buy_tax = coin.get("okx_buy_tax", 0)
                sell_tax = coin.get("okx_sell_tax", 0)
                if buy_tax == 0 and sell_tax == 0:
                    buy_tax = gp.get("buy_tax", 0.0)
                    sell_tax = gp.get("sell_tax", 0.0)

                # 图标：OKX toplist 自带 → DexScreener → pump fallback
                image_url = coin.get("token_logo_url") or socials.get("image_url", "")
                if not image_url and addr.endswith("pump"):
                    image_url = _get_pump_image(addr) or ""

                enriched.append({
                    **coin,
                    "chain": chain,
                    "holder_count": holder_count,
                    "top10_holder_pct": gp.get("top10_holder_pct"),
                    "top1_holder_pct": top1_pct,
                    "is_honeypot": gp.get("is_honeypot", False),
                    "is_open_source": gp.get("is_open_source", True),
                    "buy_tax": buy_tax,
                    "sell_tax": sell_tax,
                    "goplus_risk": gp.get("goplus_risk", False),
                    "has_twitter": socials.get("has_twitter", False),
                    "has_telegram": socials.get("has_telegram", False),
                    "has_website": socials.get("has_website", False),
                    "image_url": image_url,
                })

            # ── 4b. 合并：已入库复用 + 新富化 ─────────────────
            chain_total = reuse_coins + enriched
            log.info(f"  {chain}: 富化完成 {len(chain_total)} 个进入打分 (复用={len(reuse_coins)} 新={len(enriched)})")
            all_candidates.extend(chain_total)

            # ── 链间冷却 ────────────────────────────────────────
            await asyncio.sleep(2 if incremental else 5)

    log.info(f"全链扫描完成，候选总计: {len(all_candidates)} 个")
    return all_candidates


# ═══════════════════════════════════════════════════════════
# 价格刷新：DexScreener 批量查询已入库代币
# OKX price-info 需白名单(code:-1)，toplist 是排名不能按地址查
# 所以刷新用 DexScreener（支持按地址批量查，30个/批）
# ═══════════════════════════════════════════════════════════

async def refresh_okx_prices() -> List[dict]:
    """
    从 hot_coins 表读取已入库代币，刷新市场数据。
    OKX toplist 优先（能匹配到的直接用），未匹配的用 DexScreener fallback。
    返回更新后的行列表（供 hot_coin_job 重新打分）。
    """
    from database import get_db

    updated_rows = []  # type: List[dict]

    try:
        db = get_db()

        async with aiohttp.ClientSession() as session:
            for chain, cfg in HOT_CHAINS.items():
                res = (
                    db.table("hot_coins")
                    .select("address, name, symbol, pair_address, dex_id, "
                            "pair_created_at, age_days, "
                            "top10_holder_pct, top1_holder_pct, "
                            "is_honeypot, is_open_source, goplus_risk, "
                            "has_twitter, has_telegram, has_website, "
                            "image_url, token_logo_url")
                    .eq("chain", chain)
                    .eq("is_honeypot", False)
                    .execute()
                )
                if not res.data:
                    continue

                addresses = [r["address"] for r in res.data]
                addr_set = {a.lower() for a in addresses}

                # ── 1. DexScreener 批量刷新（返回 5m/1h/6h/24h 全时间帧数据）──
                # 30s 刷新用 DexScreener：按地址精确查询，多时间帧完整
                # OKX toplist 更适合 10min 发现（返回排名而非指定地址）
                dex_data = await _batch_dexscreener_prices(session, addresses)

                log.info(f"  刷新 {chain}: DexScreener {len(dex_data)}/{len(addresses)}")

                # ── 2. 合并 ──
                for row in res.data:
                    addr = row["address"]
                    addr_lower = addr.lower()
                    dex = dex_data.get(addr_lower)

                    if dex and dex.get("price_usd", 0) > 0:
                        updated_rows.append({
                            "chain": chain,
                            "address": addr,
                            "name": row.get("name"),
                            "symbol": row.get("symbol"),
                            "pair_address": dex.get("pair_address") or row.get("pair_address"),
                            "dex_id": dex.get("dex_id") or row.get("dex_id"),
                            "price_usd": dex["price_usd"],
                            "market_cap_usd": dex.get("market_cap_usd", 0),
                            "liquidity_usd": dex.get("liquidity_usd", 0),
                            "volume_24h_usd": dex.get("volume_24h_usd", 0),
                            "volume_1h_usd": dex.get("volume_1h_usd", 0),
                            "volume_5m_usd": dex.get("volume_5m_usd", 0),
                            "volume_4h_usd": 0,
                            "price_change_1h": dex.get("price_change_1h", 0),
                            "price_change_6h": dex.get("price_change_6h", 0),
                            "price_change_24h": dex.get("price_change_24h", 0),
                            "price_change_5m": dex.get("price_change_5m", 0),
                            "price_change_4h": 0,
                            "buys_1h": dex.get("buys_1h", 0),
                            "sells_1h": dex.get("sells_1h", 0),
                            "buys_24h": dex.get("buys_24h", 0),
                            "sells_24h": dex.get("sells_24h", 0),
                            "pair_created_at": row.get("pair_created_at"),
                            "age_days": row.get("age_days"),
                            "holder_count": 0,
                            "top10_holder_pct": row.get("top10_holder_pct"),
                            "top1_holder_pct": row.get("top1_holder_pct"),
                            "is_honeypot": row.get("is_honeypot", False),
                            "is_open_source": row.get("is_open_source", True),
                            "buy_tax": 0,
                            "sell_tax": 0,
                            "goplus_risk": row.get("goplus_risk", False),
                            "has_twitter": row.get("has_twitter", False),
                            "has_telegram": row.get("has_telegram", False),
                            "has_website": row.get("has_website", False),
                            "circ_supply": 0,
                            "token_logo_url": row.get("token_logo_url") or "",
                            "image_url": row.get("image_url") or "",
                        })

                await asyncio.sleep(0.3)

    except Exception as e:
        log.error(f"价格刷新失败: {e}", exc_info=True)

    log.info(f"价格刷新完成: {len(updated_rows)} 个代币已更新")
    return updated_rows


async def _batch_dexscreener_prices(
    session: aiohttp.ClientSession,
    addresses: List[str],
) -> Dict[str, dict]:
    """
    DexScreener 批量价格查询 — OKX 不可用时的 fallback。
    DexScreener /tokens 端点支持逗号分隔（最多30个地址/请求）。
    """
    result = {}  # type: Dict[str, dict]

    for i in range(0, len(addresses), 30):
        batch = addresses[i:i + 30]
        joined = ",".join(batch)
        url = f"{DEXSCREENER_API}/tokens/v1/{joined}"
        try:
            async with session.get(url, timeout=_TIMEOUT) as resp:
                if resp.status != 200:
                    # fallback: 逐个查询
                    for addr in batch:
                        single = await _dexscreener_single(session, addr)
                        if single:
                            result[addr.lower()] = single
                    continue

                data = await resp.json()
                # 返回 pairs 数组
                pairs = data if isinstance(data, list) else data.get("pairs", [])
                for pair in pairs:
                    base = pair.get("baseToken", {})
                    addr_lower = (base.get("address") or "").lower()
                    if not addr_lower or addr_lower in result:
                        continue
                    result[addr_lower] = _parse_dexscreener_pair(pair)

        except Exception as e:
            log.debug(f"DexScreener batch {i}: {e}")
            # fallback: 逐个查
            for addr in batch:
                single = await _dexscreener_single(session, addr)
                if single:
                    result[addr.lower()] = single

        if i + 30 < len(addresses):
            await asyncio.sleep(0.5)

    return result


async def _dexscreener_single(
    session: aiohttp.ClientSession,
    address: str,
) -> Optional[dict]:
    """单个代币的 DexScreener 查询"""
    try:
        url = f"{DEXSCREENER_API}/latest/dex/tokens/{address}"
        async with session.get(url, timeout=_TIMEOUT) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            pairs = data.get("pairs") or []
            if not pairs:
                return None
            return _parse_dexscreener_pair(pairs[0])
    except Exception:
        return None


def _parse_dexscreener_pair(pair: dict) -> dict:
    """解析 DexScreener pair 为统一格式"""
    vol = pair.get("volume", {})
    chg = pair.get("priceChange", {})
    txn = pair.get("txns", {})
    liq = pair.get("liquidity", {})

    def _f(v) -> float:
        try:
            return float(v) if v is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    return {
        "price_usd": _f(pair.get("priceUsd")),
        "market_cap_usd": _f(pair.get("marketCap") or pair.get("fdv")),
        "liquidity_usd": _f(liq.get("usd")),
        "volume_24h_usd": _f(vol.get("h24")),
        "volume_1h_usd": _f(vol.get("h1")),
        "volume_5m_usd": _f(vol.get("m5")),
        "price_change_1h": _f(chg.get("h1")),
        "price_change_6h": _f(chg.get("h6")),
        "price_change_24h": _f(chg.get("h24")),
        "price_change_5m": _f(chg.get("m5")),
        "buys_1h": int(_f(txn.get("h1", {}).get("buys"))),
        "sells_1h": int(_f(txn.get("h1", {}).get("sells"))),
        "buys_24h": int(_f(txn.get("h24", {}).get("buys"))),
        "sells_24h": int(_f(txn.get("h24", {}).get("sells"))),
        "pair_address": pair.get("pairAddress"),
        "dex_id": pair.get("dexId"),
    }


# ═══════════════════════════════════════════════════════════
# Top Holders 采集（聪明钱发现用）
# ═══════════════════════════════════════════════════════════

async def fetch_top_holders(
    chain: str, token_address: str, limit: int = 10
) -> List[Dict[str, Any]]:
    """获取代币 Top N 持仓地址
    SOL: Helius getTokenLargestAccounts
    EVM: GoPlus holders（已有 top10_holder_rate，此处尝试获取地址列表）
    返回: [{rank, wallet, pct, amount}]
    """
    async with aiohttp.ClientSession() as session:
        if chain == "solana":
            return await _fetch_sol_top_holders(session, token_address, limit)
        else:
            return await _fetch_evm_top_holders(session, chain, token_address, limit)


async def _fetch_sol_top_holders(
    session: aiohttp.ClientSession, mint: str, limit: int
) -> List[Dict[str, Any]]:
    """Helius RPC getTokenLargestAccounts → 返回地址+占比"""
    supply_payload = {
        "jsonrpc": "2.0", "id": 1,
        "method": "getTokenSupply",
        "params": [mint],
    }
    largest_payload = {
        "jsonrpc": "2.0", "id": 2,
        "method": "getTokenLargestAccounts",
        "params": [mint, {"commitment": "confirmed"}],
    }
    try:
        async def _post(payload):
            async with session.post(HELIUS_RPC, json=payload, timeout=_TIMEOUT) as r:
                return await r.json()

        s_data, l_data = await asyncio.gather(
            _post(supply_payload), _post(largest_payload), return_exceptions=True
        )
        if isinstance(s_data, Exception) or isinstance(l_data, Exception):
            return []

        total_supply = int(s_data.get("result", {}).get("value", {}).get("amount", 0))
        largest = l_data.get("result", {}).get("value", [])
        if not largest or total_supply == 0:
            return []

        holders = []
        for i, item in enumerate(largest[:limit]):
            amount = int(item.get("amount", 0))
            pct = round(amount / total_supply * 100, 2) if total_supply > 0 else 0
            holders.append({
                "rank": i + 1,
                "wallet": item.get("address", ""),
                "pct": pct,
                "amount": amount,
            })
        return holders
    except Exception as e:
        log.debug("fetch_sol_top_holders %s: %s", mint[:8], e)
        return []


async def _fetch_evm_top_holders(
    session: aiohttp.ClientSession, chain: str, address: str, limit: int
) -> List[Dict[str, Any]]:
    """GoPlus holder_info → 返回 Top N 持仓地址"""
    goplus_chain_map = {"eth": "1", "bsc": "56", "base": "8453"}
    gp_chain = goplus_chain_map.get(chain)
    if not gp_chain:
        return []
    try:
        url = f"{GOPLUS_API}/token_security/{gp_chain}"
        async with session.get(
            url, params={"contract_addresses": address}, timeout=_TIMEOUT
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            result = data.get("result", {})
            token_data = (
                result.get(address)
                or result.get(address.lower())
                or (list(result.values())[0] if result else {})
            )
            if not token_data:
                return []

            # GoPlus holders 字段可能包含地址列表
            raw_holders = token_data.get("holders", [])
            if not raw_holders:
                return []

            holders = []
            for i, h in enumerate(raw_holders[:limit]):
                holders.append({
                    "rank": i + 1,
                    "wallet": h.get("address", ""),
                    "pct": round(float(h.get("percent", 0) or 0) * 100, 2),
                    "amount": float(h.get("balance", 0) or 0),
                })
            return holders
    except Exception as e:
        log.debug("fetch_evm_top_holders %s/%s: %s", chain, address[:8], e)
        return []
