"""
热币榜多链数据采集器 — OKX 优先

数据流：
  GeckoTerminal（仅发现新代币地址 + 年龄）
    → OKX Market API（批量价格/市值/流动性/volume/change/holders/tax）
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
from typing import Dict, List, Optional, Tuple

import aiohttp

from config import (
    GECKO_API, GOPLUS_API, DEXSCREENER_API, HELIUS_RPC,
    HOT_CHAINS, GECKO_PAGES, OKX_CHAIN_INDEX,
    HOT_MIN_AGE_DAYS, HOT_MAX_AGE_DAYS,
    HOT_MIN_LIQ_USD, HOT_MAX_LIQ_USD,
    HOT_MIN_MC_USD, HOT_MAX_MC_USD,
    HOT_MIN_VOL_24H_USD, HOT_MIN_LIQ_MC_RATIO,
    HOT_MAX_TAX, HOT_MAX_TOP10_PCT,
)
import okx_market_client as okx

log = logging.getLogger(__name__)

# GeckoTerminal 要求显式传版本 header
_GECKO_HEADERS = {"Accept": "application/json;version=20230302"}
_TIMEOUT = aiohttp.ClientTimeout(total=12)

# 稳定币符号，作为 base_token 时跳过
_STABLECOINS = {"USDC", "USDT", "BUSD", "DAI", "TUSD", "FRAX", "USDD", "USDP"}


# ═══════════════════════════════════════════════════════════
# Step 1 — GeckoTerminal：发现候选池（仅取地址+年龄）
# ═══════════════════════════════════════════════════════════

async def _fetch_gecko_pools(
    session: aiohttp.ClientSession,
    gecko_net: str,
    endpoint: str,          # 'trending_pools' | 'new_pools'
) -> List[dict]:
    """拉取 GeckoTerminal 池列表，仅提取 address + pair_created_at"""
    results = []  # type: List[dict]

    for page in range(1, GECKO_PAGES + 1):
        url = f"{GECKO_API}/networks/{gecko_net}/{endpoint}"
        params = {"include": "base_token", "page": page}

        page_result = None
        for attempt in range(3):
            try:
                async with session.get(
                    url, params=params, headers=_GECKO_HEADERS, timeout=_TIMEOUT
                ) as resp:
                    if resp.status == 429:
                        wait = 25 * (attempt + 1)
                        log.warning(
                            f"GeckoTerminal 限速(429)，等待{wait}s "
                            f"{gecko_net}/{endpoint} p{page} (第{attempt+1}次)"
                        )
                        await asyncio.sleep(wait)
                        continue

                    if resp.status != 200:
                        page_result = False
                        break

                    data = await resp.json()
                    pools = data.get("data", [])
                    if not pools:
                        page_result = False
                        break

                    included_map = {}  # type: Dict[str, dict]
                    for item in data.get("included", []):
                        if item.get("type") == "token":
                            included_map[item["id"]] = item.get("attributes", {})

                    page_result = (pools, included_map)
                    break

            except asyncio.TimeoutError:
                page_result = False
                break
            except Exception as e:
                log.warning(f"GeckoTerminal {gecko_net}/{endpoint} p{page}: {e}")
                page_result = False
                break

        if page_result is False:
            break
        if isinstance(page_result, tuple):
            pools, included_map = page_result
            for pool in pools:
                parsed = _parse_gecko_pool(pool, included_map)
                if parsed:
                    results.append(parsed)

        await asyncio.sleep(2.5)

    return results


def _parse_gecko_pool(pool: dict, included_map: dict) -> Optional[dict]:
    """解析 GeckoTerminal Pool — 仅提取地址、名称、年龄"""
    try:
        attr = pool.get("attributes", {})
        rel = pool.get("relationships", {})

        base_id = rel.get("base_token", {}).get("data", {}).get("id", "")
        token_attr = included_map.get(base_id, {})
        address = token_attr.get("address", "")
        if not address:
            return None

        symbol = token_attr.get("symbol", "")
        if symbol.upper() in _STABLECOINS:
            return None

        name = token_attr.get("name", "")

        # 年龄计算
        pair_created_at = None  # type: Optional[datetime]
        age_days = None  # type: Optional[float]
        created_str = attr.get("pool_created_at")
        if created_str:
            pair_created_at = datetime.fromisoformat(
                created_str.replace("Z", "+00:00")
            )
            age_days = (datetime.now(timezone.utc) - pair_created_at).total_seconds() / 86400

        dex_id = rel.get("dex", {}).get("data", {}).get("id", "")
        pair_address = attr.get("address", "")

        return {
            "address": address,
            "name": name,
            "symbol": symbol,
            "pair_address": pair_address,
            "dex_id": dex_id,
            "pair_created_at": pair_created_at,
            "age_days": age_days,
        }
    except Exception as e:
        log.debug(f"_parse_gecko_pool: {e}")
        return None


# ═══════════════════════════════════════════════════════════
# Step 2 — OKX 批量市场数据
# ═══════════════════════════════════════════════════════════

async def _enrich_with_okx(
    session: aiohttp.ClientSession,
    chain: str,
    coins: List[dict],
) -> List[dict]:
    """用 OKX price-info 批量获取市场数据，替换 GeckoTerminal 的价格数据"""
    chain_index = OKX_CHAIN_INDEX.get(chain)
    if not chain_index:
        log.warning(f"OKX 不支持链 {chain}，跳过")
        return coins

    addresses = [c["address"] for c in coins]
    okx_data = await okx.batch_price_info(chain_index, addresses, session=session)

    enriched = []  # type: List[dict]
    okx_hit = 0
    for coin in coins:
        addr_lower = coin["address"].lower()
        info = okx_data.get(addr_lower)
        if info and info["lastPriceUsd"] > 0:
            # OKX 数据可用 → 替换
            coin["price_usd"] = info["lastPriceUsd"]
            coin["market_cap_usd"] = info["marketCap"]
            coin["liquidity_usd"] = info["liquidity"]
            coin["volume_24h_usd"] = info["volume24H"]
            coin["volume_1h_usd"] = info["volume1H"]
            coin["volume_5m_usd"] = info["volume5M"]
            coin["volume_4h_usd"] = info["volume4H"]
            coin["price_change_1h"] = info["change1H"]
            coin["price_change_6h"] = 0  # OKX 无 6h，保留 0
            coin["price_change_24h"] = info["change24H"]
            coin["price_change_5m"] = info["change5M"]
            coin["price_change_4h"] = info["change4H"]
            coin["buys_1h"] = info["txsBuy1H"]
            coin["sells_1h"] = info["txsSell1H"]
            coin["buys_24h"] = info["txsBuy24H"]
            coin["sells_24h"] = info["txsSell24H"]
            coin["buys_5m"] = info["txsBuy5M"]
            coin["sells_5m"] = info["txsSell5M"]
            coin["okx_holders"] = info["holders"]
            coin["okx_buy_tax"] = info["buyTaxRate"]
            coin["okx_sell_tax"] = info["sellTaxRate"]
            coin["circ_supply"] = info["circulatingSupply"]
            coin["token_logo_url"] = info["tokenLogoUrl"]
            coin["data_source"] = "okx"
            okx_hit += 1
        else:
            # OKX 无数据 → 该代币可能太新/太小，标记为 gecko fallback
            coin["data_source"] = "gecko_fallback"
        enriched.append(coin)

    log.info(f"  OKX 命中 {okx_hit}/{len(coins)} 个代币")
    return enriched


# ═══════════════════════════════════════════════════════════
# Step 2b — GeckoTerminal Fallback（仅对 OKX 无数据的代币）
# ═══════════════════════════════════════════════════════════

async def _fallback_gecko_market_data(
    session: aiohttp.ClientSession,
    gecko_net: str,
    coins: List[dict],
) -> List[dict]:
    """对 OKX 无数据的代币，从 GeckoTerminal 原始池数据补充市场数据"""
    # GeckoTerminal 的数据已经在 _parse_gecko_pool 中被简化掉了
    # 对于 fallback 情况，重新查询单个代币的池数据
    for coin in coins:
        if coin.get("data_source") != "gecko_fallback":
            continue

        addr = coin["address"]
        try:
            url = f"{GECKO_API}/networks/{gecko_net}/tokens/{addr}/pools"
            params = {"page": 1}
            async with session.get(
                url, params=params, headers=_GECKO_HEADERS, timeout=_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    continue

                data = await resp.json()
                pools = data.get("data", [])
                if not pools:
                    continue

                # 取第一个池的数据
                attr = pools[0].get("attributes", {})
                fdv = float(attr.get("fdv_usd") or 0)
                mc = float(attr.get("market_cap_usd") or fdv)
                liq = float(attr.get("reserve_in_usd") or 0)

                vol = attr.get("volume_usd", {})
                pct = attr.get("price_change_percentage", {})
                txns = attr.get("transactions", {})

                coin["price_usd"] = float(attr.get("base_token_price_usd") or 0)
                coin["market_cap_usd"] = mc
                coin["liquidity_usd"] = liq
                coin["volume_24h_usd"] = float(vol.get("h24") or 0)
                coin["volume_1h_usd"] = float(vol.get("h1") or 0)
                coin["volume_5m_usd"] = 0
                coin["volume_4h_usd"] = 0
                coin["price_change_1h"] = float(pct.get("h1") or 0)
                coin["price_change_6h"] = float(pct.get("h6") or 0)
                coin["price_change_24h"] = float(pct.get("h24") or 0)
                coin["price_change_5m"] = 0
                coin["price_change_4h"] = 0
                coin["buys_1h"] = int(txns.get("h1", {}).get("buys", 0) or 0)
                coin["sells_1h"] = int(txns.get("h1", {}).get("sells", 0) or 0)
                coin["buys_24h"] = int(txns.get("h24", {}).get("buys", 0) or 0)
                coin["sells_24h"] = int(txns.get("h24", {}).get("sells", 0) or 0)
                coin["buys_5m"] = 0
                coin["sells_5m"] = 0

            await asyncio.sleep(2.5)  # GeckoTerminal 限速

        except Exception as e:
            log.debug(f"GeckoTerminal fallback {addr[:8]}: {e}")

    return coins


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
    GeckoTerminal 发现 → OKX 市场数据 → 硬过滤 → GoPlus → Helius → DexScreener

    incremental=True（默认）:
      已入库代币跳过 GoPlus/Helius/DexScreener，复用 DB 中的安全/社交数据。
      仅新发现的代币走完整富化流程。扫描时间从 3-5min 降至 ~30s。

    incremental=False:
      所有候选全量富化（用于首次全量扫描或定期安全刷新）。
    """
    all_candidates = []  # type: List[dict]

    async with aiohttp.ClientSession() as session:
        for chain, cfg in HOT_CHAINS.items():
            log.info(f"扫描 {chain}...")
            gecko_net = cfg["gecko_net"]
            goplus_chain = cfg["goplus_chain"]

            # ── 增量模式：加载已入库数据 ──────────────────────
            known_data = {}  # type: Dict[str, dict]
            if incremental:
                known_data = _get_known_addresses_with_data(chain)
                log.info(f"  {chain}: 已入库 {len(known_data)} 个代币")

            # ── 1. GeckoTerminal：发现候选地址 ──────────────────
            trending = await _fetch_gecko_pools(session, gecko_net, "trending_pools")
            new_pools = await _fetch_gecko_pools(session, gecko_net, "new_pools")

            # 按 address 去重
            seen = {}  # type: Dict[str, dict]
            for coin in trending + new_pools:
                addr = coin["address"]
                if addr not in seen:
                    seen[addr] = coin
            raw = list(seen.values())
            log.info(f"  {chain}: 发现 {len(raw)} 个候选地址")

            if not raw:
                continue

            # ── 2. OKX 批量获取市场数据 ─────────────────────────
            raw = await _enrich_with_okx(session, chain, raw)

            # 对 OKX 无数据的代币用 GeckoTerminal fallback
            fallback_count = sum(1 for c in raw if c.get("data_source") == "gecko_fallback")
            if fallback_count > 0:
                log.info(f"  {chain}: {fallback_count} 个代币 OKX 无数据，GeckoTerminal fallback")
                raw = await _fallback_gecko_market_data(session, gecko_net, raw)

            # ── 3. 硬过滤（用 OKX 数据） ───────────────────────
            mc_max_usd = cfg.get("mc_max_usd")
            liq_max_usd = cfg.get("liq_max_usd")
            filtered = []  # type: List[dict]
            for coin in raw:
                # 无价格数据的跳过
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

            # ── 4. 分流：已入库 vs 新发现 ──────────────────────
            new_coins = []     # type: List[dict]
            reuse_coins = []   # type: List[dict]
            for coin in filtered:
                addr_lower = coin["address"].lower()
                if incremental and addr_lower in known_data:
                    # 已入库：复用 DB 中的安全/社交字段，只用 OKX 新价格
                    db_row = known_data[addr_lower]
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
                        "image_url": db_row.get("image_url") or db_row.get("token_logo_url", ""),
                    })
                    reuse_coins.append(coin)
                else:
                    new_coins.append(coin)

            if incremental:
                log.info(f"  {chain}: 复用已入库 {len(reuse_coins)} 个，新发现 {len(new_coins)} 个需富化")

            # ── 5a. 新代币：完整 GoPlus + Helius + DexScreener ─
            enriched = []  # type: List[dict]
            for coin in new_coins:
                addr = coin["address"]

                # GoPlus 安全检测
                gp = await _check_goplus(session, chain, addr, goplus_chain)
                await asyncio.sleep(0.35)

                if gp.get("is_honeypot"):
                    log.debug(f"  蜜罐排除: {coin.get('symbol')} ({addr[:8]})")
                    continue

                # GoPlus 持有者数量
                gp_holder_count = gp.get("holder_count", 0)
                # 优先用 OKX holders，GoPlus 作为补充
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

                # DexScreener 社交
                socials = await _get_dexscreener_socials(session, addr)
                await asyncio.sleep(0.2)

                # 买卖税：OKX 有则用 OKX，否则用 GoPlus
                buy_tax = coin.get("okx_buy_tax", 0)
                sell_tax = coin.get("okx_sell_tax", 0)
                if buy_tax == 0 and sell_tax == 0:
                    buy_tax = gp.get("buy_tax", 0.0)
                    sell_tax = gp.get("sell_tax", 0.0)

                # 图标：OKX 有则用 OKX，否则用 DexScreener
                image_url = coin.get("token_logo_url") or socials.get("image_url", "")

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

            # ── 5b. 合并：已入库复用 + 新富化 ─────────────────
            chain_total = reuse_coins + enriched
            log.info(f"  {chain}: 富化完成 {len(chain_total)} 个进入打分 (复用={len(reuse_coins)} 新={len(enriched)})")
            all_candidates.extend(chain_total)

            # ── 链间冷却（增量模式缩短） ──────────────────────
            await asyncio.sleep(2 if incremental else 5)

    log.info(f"全链扫描完成，候选总计: {len(all_candidates)} 个")
    return all_candidates


# ═══════════════════════════════════════════════════════════
# 每5秒：OKX 全字段刷新已入库代币
# OKX price-info 一次返回：
#   实时字段：lastPriceUsd(毫秒级), liquidity(每笔成交), marketCap
#   聚合窗口：volume/change/txs 的 5M/1H/4H/24H
#   延迟字段：holders(5-15min), circulatingSupply(稳定)
# 所有字段来自同一接口，无额外 API 开销
# ═══════════════════════════════════════════════════════════

async def refresh_okx_prices() -> List[dict]:
    """
    从 hot_coins 表读取已入库代币，刷新全量市场数据。
    优先 OKX Market API，若 OKX 不可用则 fallback DexScreener。
    返回更新后的行列表（供 hot_coin_job 重新打分）。
    """
    from database import get_db

    updated_rows = []  # type: List[dict]

    try:
        db = get_db()

        async with aiohttp.ClientSession() as session:
            for chain, cfg in HOT_CHAINS.items():
                chain_index = OKX_CHAIN_INDEX.get(chain)

                # 从 DB 读取该链所有代币
                res = (
                    db.table("hot_coins")
                    .select("address, name, symbol, pair_address, dex_id, "
                            "pair_created_at, age_days, "
                            "top10_holder_pct, top1_holder_pct, "
                            "is_honeypot, is_open_source, goplus_risk, "
                            "has_twitter, has_telegram, has_website")
                    .eq("chain", chain)
                    .eq("is_honeypot", False)
                    .execute()
                )
                if not res.data:
                    continue

                addresses = [r["address"] for r in res.data]

                # ── 优先 OKX ──
                okx_data = {}  # type: Dict[str, dict]
                if chain_index:
                    okx_data = await okx.batch_price_info(
                        chain_index, addresses, session=session
                    )

                okx_hit = sum(1 for a in addresses if a.lower() in okx_data)

                # ── OKX 命中不足 → fallback DexScreener ──
                if okx_hit < len(addresses) * 0.3:
                    log.info(f"  OKX {chain} 命中 {okx_hit}/{len(addresses)}, fallback DexScreener")
                    dex_data = await _batch_dexscreener_prices(session, addresses)
                else:
                    dex_data = {}
                    log.info(f"  OKX 刷新 {chain}: {okx_hit}/{len(addresses)} 个代币")

                for row in res.data:
                    addr = row["address"]
                    addr_lower = addr.lower()

                    # 优先 OKX 数据
                    info = okx_data.get(addr_lower)
                    if info and info["lastPriceUsd"] > 0:
                        okx_holders = info["holders"]
                        updated_rows.append({
                            "chain": chain,
                            "address": addr,
                            "name": row.get("name"),
                            "symbol": row.get("symbol"),
                            "pair_address": row.get("pair_address"),
                            "dex_id": row.get("dex_id"),
                            "price_usd": info["lastPriceUsd"],
                            "market_cap_usd": info["marketCap"],
                            "liquidity_usd": info["liquidity"],
                            "volume_24h_usd": info["volume24H"],
                            "volume_1h_usd": info["volume1H"],
                            "volume_5m_usd": info["volume5M"],
                            "volume_4h_usd": info["volume4H"],
                            "price_change_1h": info["change1H"],
                            "price_change_6h": 0,
                            "price_change_24h": info["change24H"],
                            "price_change_5m": info["change5M"],
                            "price_change_4h": info["change4H"],
                            "buys_1h": info["txsBuy1H"],
                            "sells_1h": info["txsSell1H"],
                            "buys_24h": info["txsBuy24H"],
                            "sells_24h": info["txsSell24H"],
                            "pair_created_at": row.get("pair_created_at"),
                            "age_days": row.get("age_days"),
                            "holder_count": okx_holders if okx_holders > 0 else 0,
                            "top10_holder_pct": row.get("top10_holder_pct"),
                            "top1_holder_pct": row.get("top1_holder_pct"),
                            "is_honeypot": row.get("is_honeypot", False),
                            "is_open_source": row.get("is_open_source", True),
                            "buy_tax": info["buyTaxRate"],
                            "sell_tax": info["sellTaxRate"],
                            "goplus_risk": row.get("goplus_risk", False),
                            "has_twitter": row.get("has_twitter", False),
                            "has_telegram": row.get("has_telegram", False),
                            "has_website": row.get("has_website", False),
                            "circ_supply": info["circulatingSupply"],
                            "token_logo_url": info["tokenLogoUrl"],
                        })
                        continue

                    # fallback DexScreener
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
                            "token_logo_url": "",
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
