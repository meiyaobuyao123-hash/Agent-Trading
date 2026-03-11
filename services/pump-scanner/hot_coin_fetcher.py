"""
热币榜多链数据采集器

数据流：
  GeckoTerminal（发现）
    → 硬过滤（年龄/流动性/市值/成交量）
    → GoPlus（安全检测 + 持有者数量 + 集中度）
    → Helius（SOL链：Top1持有者精确占比）
    → DexScreener（社交链接：Twitter/Telegram/网站）
    → 返回富化后的候选列表，供 hot_scorer 打分

覆盖链：SOL / BSC / Base（三链均有活跃新项目生态，GeckoTerminal trending 含大量 3~90d 目标）
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import aiohttp

from config import (
    GECKO_API, GOPLUS_API, DEXSCREENER_API, HELIUS_RPC,
    HOT_CHAINS, GECKO_PAGES,
    HOT_MIN_AGE_DAYS, HOT_MAX_AGE_DAYS,
    HOT_MIN_LIQ_USD, HOT_MAX_LIQ_USD,
    HOT_MIN_MC_USD, HOT_MAX_MC_USD,
    HOT_MIN_VOL_24H_USD, HOT_MIN_LIQ_MC_RATIO,
    HOT_MAX_TAX, HOT_MAX_TOP10_PCT,
)

log = logging.getLogger(__name__)

# GeckoTerminal 要求显式传版本 header
_GECKO_HEADERS = {"Accept": "application/json;version=20230302"}
_TIMEOUT = aiohttp.ClientTimeout(total=12)

# 稳定币符号，作为 base_token 时跳过（防止把 USDC 本身选进来）
_STABLECOINS = {"USDC", "USDT", "BUSD", "DAI", "TUSD", "FRAX", "USDD", "USDP"}


# ═══════════════════════════════════════════════════════════
# Step 1 — GeckoTerminal：发现候选池
# ═══════════════════════════════════════════════════════════

async def _fetch_gecko_pools(
    session: aiohttp.ClientSession,
    gecko_net: str,
    endpoint: str,          # 'trending_pools' | 'new_pools'
) -> List[dict]:
    """拉取 GeckoTerminal 池列表（多页，含 base_token 信息）"""
    results: List[dict] = []

    for page in range(1, GECKO_PAGES + 1):
        url = f"{GECKO_API}/networks/{gecko_net}/{endpoint}"
        params = {"include": "base_token", "page": page}

        # 内层重试循环：专门处理 429 限速
        page_result = None   # None=未成功, False=终止翻页, (pools, map)=成功
        for attempt in range(3):
            try:
                async with session.get(
                    url, params=params, headers=_GECKO_HEADERS, timeout=_TIMEOUT
                ) as resp:
                    if resp.status == 429:
                        wait = 25 * (attempt + 1)   # 25s / 50s / 75s 递增等待
                        log.warning(
                            f"GeckoTerminal 限速(429)，等待{wait}s 后重试 "
                            f"{gecko_net}/{endpoint} p{page} (第{attempt+1}次)"
                        )
                        await asyncio.sleep(wait)
                        continue                     # ← 重试同一页（而非跳到下一页）

                    if resp.status != 200:
                        log.debug(f"GeckoTerminal {gecko_net}/{endpoint} p{page} → {resp.status}")
                        page_result = False           # 非限速错误，停止翻页
                        break

                    data  = await resp.json()
                    pools = data.get("data", [])
                    if not pools:
                        page_result = False           # 无数据，后续页也没有意义
                        break

                    # 构建 included token 映射（id → attributes）
                    included_map: Dict[str, dict] = {}
                    for item in data.get("included", []):
                        if item.get("type") == "token":
                            included_map[item["id"]] = item.get("attributes", {})

                    page_result = (pools, included_map)
                    break                             # 成功，退出重试循环

            except asyncio.TimeoutError:
                log.warning(f"GeckoTerminal timeout: {gecko_net}/{endpoint} p{page}")
                page_result = False
                break
            except Exception as e:
                log.warning(f"GeckoTerminal {gecko_net}/{endpoint} p{page}: {e}")
                page_result = False
                break

        # 外层：根据内层结果决定是否继续翻页
        if page_result is False:
            break                                     # 停止翻页
        if isinstance(page_result, tuple):
            pools, included_map = page_result
            for pool in pools:
                parsed = _parse_gecko_pool(pool, included_map)
                if parsed:
                    results.append(parsed)

        await asyncio.sleep(2.5)   # GeckoTerminal 免费：~30 req/min ≈ 2s/req，保守2.5s

    return results


def _parse_gecko_pool(pool: dict, included_map: dict) -> Optional[dict]:
    """解析单个 GeckoTerminal Pool，返回标准化 dict 或 None"""
    try:
        attr = pool.get("attributes", {})
        rel  = pool.get("relationships", {})

        # base_token 信息
        base_id    = rel.get("base_token", {}).get("data", {}).get("id", "")
        token_attr = included_map.get(base_id, {})
        address    = token_attr.get("address", "")
        if not address:
            return None

        symbol = token_attr.get("symbol", "")
        if symbol.upper() in _STABLECOINS:
            return None

        name = token_attr.get("name", "")

        # 市场数据
        fdv = float(attr.get("fdv_usd") or 0)
        mc  = float(attr.get("market_cap_usd") or fdv)   # market_cap_usd 有时为 null
        liq = float(attr.get("reserve_in_usd") or 0)

        vol      = attr.get("volume_usd", {})
        vol_24h  = float(vol.get("h24") or 0)
        vol_1h   = float(vol.get("h1")  or 0)

        pct      = attr.get("price_change_percentage", {})
        pc_1h    = float(pct.get("h1")  or 0)
        pc_6h    = float(pct.get("h6")  or 0)
        pc_24h   = float(pct.get("h24") or 0)

        price_usd = float(attr.get("base_token_price_usd") or 0)

        txns      = attr.get("transactions", {})
        buys_1h   = int(txns.get("h1", {}).get("buys",  0) or 0)
        sells_1h  = int(txns.get("h1", {}).get("sells", 0) or 0)
        buys_24h  = int(txns.get("h24", {}).get("buys",  0) or 0)
        sells_24h = int(txns.get("h24", {}).get("sells", 0) or 0)

        # 代币年龄
        pair_created_at: Optional[datetime] = None
        age_days: Optional[float] = None
        created_str = attr.get("pool_created_at")
        if created_str:
            pair_created_at = datetime.fromisoformat(
                created_str.replace("Z", "+00:00")
            )
            age_days = (datetime.now(timezone.utc) - pair_created_at).total_seconds() / 86400

        dex_id       = rel.get("dex", {}).get("data", {}).get("id", "")
        pair_address = attr.get("address", "")

        return {
            "address":         address,
            "name":            name,
            "symbol":          symbol,
            "pair_address":    pair_address,
            "dex_id":          dex_id,
            "price_usd":       price_usd,
            "market_cap_usd":  mc,
            "liquidity_usd":   liq,
            "volume_24h_usd":  vol_24h,
            "volume_1h_usd":   vol_1h,
            "price_change_1h":  pc_1h,
            "price_change_6h":  pc_6h,
            "price_change_24h": pc_24h,
            "buys_1h":         buys_1h,
            "sells_1h":        sells_1h,
            "buys_24h":        buys_24h,
            "sells_24h":       sells_24h,
            "pair_created_at": pair_created_at,
            "age_days":        age_days,
        }
    except Exception as e:
        log.debug(f"_parse_gecko_pool: {e}")
        return None


# ═══════════════════════════════════════════════════════════
# Step 2 — 硬过滤
# ═══════════════════════════════════════════════════════════

def apply_hard_filter(
    coin: dict,
    mc_max_usd: float = None,
    liq_max_usd: float = None,
) -> Tuple[bool, str]:
    """
    返回 (通过, 拒绝原因)
    mc_max_usd / liq_max_usd: 链级别上限覆盖（None → 使用全局常量）
    """
    age = coin.get("age_days")
    if age is None:
        return False, "年龄未知"
    if not (HOT_MIN_AGE_DAYS <= age <= HOT_MAX_AGE_DAYS):
        return False, f"年龄不符 {age:.1f}d"

    liq     = coin.get("liquidity_usd", 0)
    liq_max = liq_max_usd if liq_max_usd is not None else HOT_MAX_LIQ_USD
    if not (HOT_MIN_LIQ_USD <= liq <= liq_max):
        return False, f"流动性不符 ${liq:,.0f}"

    mc     = coin.get("market_cap_usd", 0)
    mc_max = mc_max_usd if mc_max_usd is not None else HOT_MAX_MC_USD
    if not (HOT_MIN_MC_USD <= mc <= mc_max):
        return False, f"市值不符 ${mc:,.0f}"

    if coin.get("volume_24h_usd", 0) < HOT_MIN_VOL_24H_USD:
        return False, f"24h量不足 ${coin.get('volume_24h_usd', 0):,.0f}"

    if mc > 0 and liq / mc < HOT_MIN_LIQ_MC_RATIO:
        return False, f"流动性/市值比低 {liq/mc:.1%}"

    return True, ""


# ═══════════════════════════════════════════════════════════
# Step 3 — GoPlus：安全检测 + 持有者数据
# ═══════════════════════════════════════════════════════════

async def _check_goplus(
    session: aiohttp.ClientSession,
    chain: str,
    address: str,
    goplus_chain: str,
) -> dict:
    """
    返回字段：
      holder_count, top10_holder_pct,
      is_honeypot, is_open_source, buy_tax, sell_tax, goplus_risk
    """
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

            # GoPlus 以 address（可能大小写不一致）为 key
            token_data = (
                result.get(address)
                or result.get(address.lower())
                or (list(result.values())[0] if result else {})
            )
            if not token_data:
                return {}

            holder_count  = int(token_data.get("holder_count") or 0)
            top10_pct     = float(token_data.get("top10_holder_rate") or 0)

            # EVM 专属字段（SOL 链这些字段通常缺失，默认安全值）
            is_honeypot   = str(token_data.get("is_honeypot",   "0")) == "1"
            is_open       = str(token_data.get("is_open_source","1")) != "0"
            buy_tax       = float(token_data.get("buy_tax")  or 0)
            sell_tax      = float(token_data.get("sell_tax") or 0)
            cannot_sell   = str(token_data.get("cannot_sell_all", "0")) == "1"

            # SOL 无法检测蜜罐，用 cannot_buy 替代
            if chain == "solana":
                is_honeypot = str(token_data.get("cannot_buy", "0")) == "1"
                is_open     = True   # SOL 合约开源难验证，默认 True

            goplus_risk = (
                is_honeypot
                or cannot_sell
                or buy_tax  > HOT_MAX_TAX
                or sell_tax > HOT_MAX_TAX
                or (top10_pct > HOT_MAX_TOP10_PCT and top10_pct > 0)
            )

            return {
                "holder_count":     holder_count,
                "top10_holder_pct": top10_pct,
                "is_honeypot":      is_honeypot,
                "is_open_source":   is_open,
                "buy_tax":          buy_tax,
                "sell_tax":         sell_tax,
                "goplus_risk":      goplus_risk,
            }

    except asyncio.TimeoutError:
        log.debug(f"GoPlus timeout: {chain}/{address[:8]}")
        return {}
    except Exception as e:
        log.debug(f"GoPlus {chain}/{address[:8]}: {e}")
        return {}


# ═══════════════════════════════════════════════════════════
# Step 4 — Helius：SOL Top1 持有者精确占比
# ═══════════════════════════════════════════════════════════

async def _get_sol_top1_pct(
    session: aiohttp.ClientSession,
    mint: str,
) -> Optional[float]:
    """
    使用 Helius RPC 同时查询：
      getTokenSupply         → 总供应量
      getTokenLargestAccounts → Top20 账户持仓
    计算 Top1 持有者占比（排除流动性池地址误差已被GoPlus top10分析覆盖）
    """
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
# Step 5 — DexScreener：社交链接
# ═══════════════════════════════════════════════════════════

async def _get_dexscreener_socials(
    session: aiohttp.ClientSession,
    address: str,
) -> dict:
    """从 DexScreener 获取 Twitter / Telegram / 网站 存在性 + 代币图标"""
    try:
        url = f"{DEXSCREENER_API}/latest/dex/tokens/{address}"
        async with session.get(url, timeout=_TIMEOUT) as resp:
            if resp.status != 200:
                return {}

            data  = await resp.json()
            pairs = data.get("pairs") or []
            if not pairs:
                return {}

            info     = pairs[0].get("info", {})
            socials  = info.get("socials", [])
            websites = info.get("websites", [])
            image_url = info.get("imageUrl") or ""

            return {
                "has_twitter":  any(s.get("type") == "twitter"  for s in socials),
                "has_telegram": any(s.get("type") == "telegram" for s in socials),
                "has_website":  len(websites) > 0,
                "image_url":    image_url,
            }
    except Exception as e:
        log.debug(f"DexScreener socials {address[:8]}: {e}")
        return {}


# ═══════════════════════════════════════════════════════════
# 主函数：全链扫描并富化
# ═══════════════════════════════════════════════════════════

async def fetch_hot_coin_candidates() -> List[dict]:
    """
    扫描所有目标链（SOL / BSC / ETH / Base），
    经过硬过滤 → GoPlus → Helius → DexScreener 富化后返回候选列表。
    每条 dict 包含打分所需的全部字段。
    """
    all_candidates: List[dict] = []

    async with aiohttp.ClientSession() as session:
        for chain, cfg in HOT_CHAINS.items():
            log.info(f"🔍 扫描 {chain}...")
            gecko_net    = cfg["gecko_net"]
            goplus_chain = cfg["goplus_chain"]

            # ── 1. GeckoTerminal：获取候选池 ───────────────────
            trending  = await _fetch_gecko_pools(session, gecko_net, "trending_pools")
            new_pools = await _fetch_gecko_pools(session, gecko_net, "new_pools")

            # 按 address 去重（trending 和 new_pools 可能重叠）
            seen: Dict[str, dict] = {}
            for coin in trending + new_pools:
                addr = coin["address"]
                # 若已存在，保留 volume 更大的（trending 数据通常更新）
                if addr not in seen or coin.get("volume_24h_usd", 0) > seen[addr].get("volume_24h_usd", 0):
                    seen[addr] = coin
            raw = list(seen.values())
            log.info(f"  {chain}: 原始候选 {len(raw)} 个")

            # ── 2. 硬过滤 ──────────────────────────────────────
            mc_max_usd  = cfg.get("mc_max_usd")   # 链级别覆盖，None→使用全局值
            liq_max_usd = cfg.get("liq_max_usd")
            filtered: List[dict] = []
            for coin in raw:
                ok, reason = apply_hard_filter(
                    coin, mc_max_usd=mc_max_usd, liq_max_usd=liq_max_usd
                )
                if ok:
                    filtered.append(coin)
                else:
                    log.debug(f"  ✗ {coin.get('symbol','?')} ({coin['address'][:8]}): {reason}")
            log.info(f"  {chain}: 硬过滤后 {len(filtered)} 个")

            # ── 3. GoPlus + Helius + DexScreener 富化 ─────────
            enriched: List[dict] = []
            for coin in filtered:
                addr = coin["address"]

                # GoPlus 安全检测
                gp = await _check_goplus(session, chain, addr, goplus_chain)
                await asyncio.sleep(0.35)   # GoPlus 速率保护

                # 蜜罐直接排除（不进打分池）
                if gp.get("is_honeypot"):
                    log.debug(f"  ⚠ 蜜罐排除: {coin.get('symbol')} ({addr[:8]})")
                    continue

                # GoPlus 持有者数量过滤（> 0 才过滤，= 0 表示 GoPlus 无数据，放行）
                holder_count = gp.get("holder_count", 0)
                if 0 < holder_count < 150:
                    log.debug(f"  ✗ 持有者不足 {holder_count}: {coin.get('symbol')}")
                    continue

                # Helius：SOL 链 Top1 精确占比
                top1_pct: Optional[float] = None
                if chain == "solana":
                    top1_pct = await _get_sol_top1_pct(session, addr)
                    await asyncio.sleep(0.1)

                # DexScreener 社交
                socials = await _get_dexscreener_socials(session, addr)
                await asyncio.sleep(0.2)

                enriched.append({
                    **coin,
                    "chain":            chain,
                    "holder_count":     holder_count,
                    "top10_holder_pct": gp.get("top10_holder_pct"),
                    "top1_holder_pct":  top1_pct,
                    "is_honeypot":      gp.get("is_honeypot", False),
                    "is_open_source":   gp.get("is_open_source", True),
                    "buy_tax":          gp.get("buy_tax", 0.0),
                    "sell_tax":         gp.get("sell_tax", 0.0),
                    "goplus_risk":      gp.get("goplus_risk", False),
                    "has_twitter":      socials.get("has_twitter", False),
                    "has_telegram":     socials.get("has_telegram", False),
                    "has_website":      socials.get("has_website", False),
                    "image_url":        socials.get("image_url", ""),
                })

            log.info(f"  {chain}: 富化完成 {len(enriched)} 个进入打分")
            all_candidates.extend(enriched)

            # ── 链间冷却：等待 GeckoTerminal 全局限速恢复 ──────
            await asyncio.sleep(8)

    log.info(f"✅ 全链扫描完成，候选总计: {len(all_candidates)} 个")
    return all_candidates
