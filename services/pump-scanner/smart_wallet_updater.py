"""
聪明钱识别器 v3 — 五维度 100 分评估体系

运行时机：每 2 小时（APScheduler 调度）

━━━━ 五维度评分（每项 0-20 分，总分 100）━━━━━━━━━━━

1. 胜率维度（0-20）
   买入后 72h 内最高价 ≥ 买入价 × 1.2（涨 20%+ 才算赢）
   ≥60%:20  ≥45%:15  ≥30%:10  <30%:5
   最低样本: ≥5 笔买入（不够=0）

2. PNL 维度（0-20）
   (卖出均价 / 买入均价) 中位数
   ≥2.0x:20  ≥1.5x:15  ≥1.2x:10  ≥1.0x:5  <1.0x:0

3. 交易规模维度（0-20）
   单笔交易 USD 中位数
   ≥$5K:20  ≥$1K:15  ≥$200:10  <$200:5

4. 活跃度维度（0-20）
   频率 + 天数分布（检测 bot）
   10-500笔 且 ≥5天:20   5-1000笔 且 ≥3天:15
   >2000笔:0(bot黑名单)  仅1天:5  0笔:-10

5. 时效性维度（0-20）
   买入时代币市值（越早=越聪明）
   <$500K:20  <$2M:15  <$10M:10  ≥$10M:5

━━━━ 分层 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  elite:    总分≥75 且 胜率≥15 且 PNL≥10 且 无bot
  verified: 总分≥55 且 胜率≥10 且 活跃度≥10
  watching: 总分 35-54 或 数据不足
  blacklisted: bot行为 / 总分<30且≥10笔 / 频率>2000

━━━━ 降级 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  14天无交易 → 降一级
  28天无交易 → 移除
  同代币60秒买卖 → 立即黑名单

Python 3.9 兼容。
"""

import logging
import statistics
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Set

from database import get_db

log = logging.getLogger(__name__)

# ── 配置 ────────────────────────────────────────────────────
EVAL_WINDOW_DAYS = 14        # 滚动评估窗口
BOT_HOLD_SECONDS = 60        # 买卖同代币<60秒 = bot
BOT_MAX_TRADES_14D = 2000    # 14天内>2000笔 = 高频bot
WIN_PRICE_RATIO = 1.2        # 涨20%才算赢
MIN_TRADES_FOR_SCORE = 5     # 最少5笔才评分
INACTIVE_DEMOTE_DAYS = 14    # 14天无交易降级
INACTIVE_REMOVE_DAYS = 28    # 28天无交易移除

# ── 分层阈值 ──────────────────────────────────────────────
ELITE_TOTAL = 75
ELITE_WIN_MIN = 15
ELITE_PNL_MIN = 10

VERIFIED_TOTAL = 55
VERIFIED_WIN_MIN = 10
VERIFIED_ACTIVE_MIN = 10

WATCHING_TOTAL = 35

BLACKLIST_TOTAL = 30
BLACKLIST_MIN_TRADES = 10


# ═══════════════════════════════════════════════════════════
# 维度打分函数
# ═══════════════════════════════════════════════════════════

def _score_win_rate(win_rate: float, trade_count: int) -> int:
    """维度1: 胜率（0-20）"""
    if trade_count < MIN_TRADES_FOR_SCORE:
        return 0
    if win_rate >= 0.60:
        return 20
    if win_rate >= 0.45:
        return 15
    if win_rate >= 0.30:
        return 10
    return 5


def _score_pnl(pnl_median: float) -> int:
    """维度2: PNL中位数（0-20）"""
    if pnl_median <= 0:
        return 0  # 无数据
    if pnl_median >= 2.0:
        return 20
    if pnl_median >= 1.5:
        return 15
    if pnl_median >= 1.2:
        return 10
    if pnl_median >= 1.0:
        return 5
    return 0  # 亏钱


def _score_trade_size(median_usd: float) -> int:
    """维度3: 交易规模（0-20）"""
    if median_usd >= 5000:
        return 20
    if median_usd >= 1000:
        return 15
    if median_usd >= 200:
        return 10
    return 5


def _score_activity(trade_count: int, active_days: int) -> int:
    """维度4: 活跃度（0-20），同时检测bot"""
    if trade_count > BOT_MAX_TRADES_14D:
        return 0  # bot
    if trade_count == 0:
        return -10  # 不活跃惩罚
    if 10 <= trade_count <= 500 and active_days >= 5:
        return 20
    if 5 <= trade_count <= 1000 and active_days >= 3:
        return 15
    if active_days <= 1:
        return 5
    return 10


def _score_timing(avg_mc_at_buy: float) -> int:
    """维度5: 时效性/早期发现（0-20）"""
    if avg_mc_at_buy <= 0:
        return 10  # 无数据，给中间分
    if avg_mc_at_buy < 500_000:
        return 20
    if avg_mc_at_buy < 2_000_000:
        return 15
    if avg_mc_at_buy < 10_000_000:
        return 10
    return 5


# ═══════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════

def run_smart_wallet_updater():
    log.info("⚙️  聪明钱 v3 评估开始（5维度100分）...")
    db = get_db()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=EVAL_WINDOW_DAYS)).isoformat()

    # ── Step 1: 从 smart_money_txns 拉取14天内交易 ──────────
    try:
        txns_res = db.table("smart_money_txns").select(
            "wallet_address, token_address, chain, tx_type, volume_usd, "
            "market_cap_at_tx, price_at_tx, tx_time, wallet_tier"
        ).gte("tx_time", cutoff).execute()
    except Exception as e:
        log.error(f"查询 smart_money_txns 失败: {e}")
        return

    txns = txns_res.data or []
    log.info(f"14天内交易记录: {len(txns)} 条")

    if not txns:
        log.info("无交易记录，执行降级检查后退出")
        _handle_inactive(db, now)
        _evaluate_top_holders(db)
        return

    # ── Step 2: 按钱包聚合统计 ──────────────────────────────
    wallet_data = defaultdict(lambda: {
        "buys": [],           # [{token, price, volume_usd, mc, time}]
        "sells": [],          # [{token, price, volume_usd, time}]
        "buy_tokens": set(),  # 买过的代币
        "sell_tokens": {},    # {token: [sell_price]}
        "volumes": [],        # 所有交易的 volume_usd
        "active_dates": set(),
        "last_seen": "",
        "mint_buy_times": defaultdict(list),  # bot检测
    })

    for t in txns:
        wallet = t.get("wallet_address", "")
        if not wallet:
            continue
        wd = wallet_data[wallet]
        tx_type = t.get("tx_type", "")
        token = t.get("token_address", "")
        volume = float(t.get("volume_usd") or 0)
        mc = float(t.get("market_cap_at_tx") or 0)
        price = float(t.get("price_at_tx") or 0)
        tx_time = t.get("tx_time", "")

        if volume > 0:
            wd["volumes"].append(volume)

        # 提取日期
        try:
            dt = datetime.fromisoformat(tx_time.replace("Z", "+00:00"))
            wd["active_dates"].add(dt.strftime("%Y-%m-%d"))
            if tx_time > wd["last_seen"]:
                wd["last_seen"] = tx_time
        except Exception:
            pass

        if tx_type == "buy":
            wd["buys"].append({
                "token": token, "price": price,
                "volume_usd": volume, "mc": mc, "time": tx_time,
            })
            wd["buy_tokens"].add(token)
            try:
                bt = datetime.fromisoformat(tx_time.replace("Z", "+00:00"))
                wd["mint_buy_times"][token].append(bt)
            except Exception:
                pass
        elif tx_type == "sell":
            wd["sells"].append({
                "token": token, "price": price,
                "volume_usd": volume, "time": tx_time,
            })
            if token not in wd["sell_tokens"]:
                wd["sell_tokens"][token] = []
            if price > 0:
                wd["sell_tokens"][token].append(price)

    log.info(f"活跃钱包: {len(wallet_data)} 个")

    # ── Step 3: Bot 检测（60秒买卖同代币）────────────────────
    bot_wallets: Set[str] = set()
    for wallet, wd in wallet_data.items():
        # 高频 bot
        total_trades = len(wd["buys"]) + len(wd["sells"])
        if total_trades > BOT_MAX_TRADES_14D:
            bot_wallets.add(wallet)
            continue

        # 60秒买卖检测
        for sell in wd["sells"]:
            token = sell["token"]
            buy_times = wd["mint_buy_times"].get(token, [])
            if not buy_times:
                continue
            try:
                st = datetime.fromisoformat(sell["time"].replace("Z", "+00:00"))
                for bt in buy_times:
                    diff = abs((st - bt).total_seconds())
                    if diff < BOT_HOLD_SECONDS:
                        bot_wallets.add(wallet)
                        break
            except Exception:
                pass
            if wallet in bot_wallets:
                break

    log.info(f"Bot 检测: {len(bot_wallets)} 个")

    # ── Step 4: 五维度评分 ──────────────────────────────────
    now_str = now.isoformat()
    upsert_rows: List[dict] = []
    tier_counts: Dict[str, int] = defaultdict(int)

    for wallet, wd in wallet_data.items():
        total_trades = len(wd["buys"]) + len(wd["sells"])
        active_days = len(wd["active_dates"])

        # --- 维度1: 胜率 ---
        # 用 DexScreener enrich 后的 price_at_tx 计算
        # 简化：检查同代币是否有卖出且卖出价 > 买入价 × 1.2
        win_count = 0
        loss_count = 0
        pnl_ratios = []
        mc_at_buys = []

        for buy in wd["buys"]:
            token = buy["token"]
            buy_price = buy["price"]
            mc = buy["mc"]
            if mc > 0:
                mc_at_buys.append(mc)

            if buy_price <= 0:
                continue

            # 检查该代币是否有卖出
            sell_prices = wd["sell_tokens"].get(token, [])
            if sell_prices:
                best_sell = max(sell_prices)
                ratio = best_sell / buy_price
                pnl_ratios.append(ratio)
                if ratio >= WIN_PRICE_RATIO:
                    win_count += 1
                else:
                    loss_count += 1
            else:
                # 没卖出的不计入胜率（可能还在持有）
                pass

        evaluated_trades = win_count + loss_count
        win_rate = win_count / evaluated_trades if evaluated_trades > 0 else 0
        pnl_median = statistics.median(pnl_ratios) if pnl_ratios else 0
        avg_mc = statistics.mean(mc_at_buys) if mc_at_buys else 0
        median_volume = statistics.median(wd["volumes"]) if wd["volumes"] else 0

        # 打分
        s_win = _score_win_rate(win_rate, len(wd["buys"]))
        s_pnl = _score_pnl(pnl_median)
        s_size = _score_trade_size(median_volume)
        s_act = _score_activity(total_trades, active_days)
        s_time = _score_timing(avg_mc)
        total_score = s_win + s_pnl + s_size + s_act + s_time

        # 构建 row
        row = {
            "wallet": wallet,
            "total_trades": total_trades,
            "win_trades": win_count,
            "total_sol_in": round(sum(b["volume_usd"] for b in wd["buys"]), 2),
            "avg_entry_bc": round(avg_mc, 0) if avg_mc > 0 else None,
            "active_weeks": active_days,  # 复用字段存活跃天数
            "last_seen": wd["last_seen"] or now_str,
        }

        # --- 分层 ---
        if wallet in bot_wallets:
            tier = "blacklisted"
            row["is_blacklisted"] = True
        elif total_score < BLACKLIST_TOTAL and total_trades >= BLACKLIST_MIN_TRADES:
            tier = "blacklisted"
            row["is_blacklisted"] = True
        elif (total_score >= ELITE_TOTAL
              and s_win >= ELITE_WIN_MIN
              and s_pnl >= ELITE_PNL_MIN
              and total_trades >= MIN_TRADES_FOR_SCORE  # 硬性门槛：至少 5 笔真实交易
              and wallet not in bot_wallets):
            tier = "elite"
            row["is_blacklisted"] = False
        elif (total_score >= VERIFIED_TOTAL
              and s_win >= VERIFIED_WIN_MIN
              and s_act >= VERIFIED_ACTIVE_MIN):
            tier = "verified"
            row["is_blacklisted"] = False
        elif total_score >= WATCHING_TOTAL:
            tier = "watching"
            row["is_blacklisted"] = False
        elif len(wd["buys"]) < MIN_TRADES_FOR_SCORE:
            tier = "watching"  # 数据不足，保留观察
            row["is_blacklisted"] = False
        else:
            continue  # 分数太低且数据充足，不写入

        row["tier"] = tier
        upsert_rows.append(row)
        tier_counts[tier] += 1

    log.info(
        f"v3 评估结果 → "
        f"精英:{tier_counts['elite']}  "
        f"验证:{tier_counts['verified']}  "
        f"观察:{tier_counts['watching']}  "
        f"黑名单:{tier_counts['blacklisted']}"
    )

    # ── Step 5: 批量 upsert ──────────────────────────────────
    success_count = 0
    for i in range(0, len(upsert_rows), 100):
        batch = upsert_rows[i:i + 100]
        try:
            db.table("smart_wallets").upsert(
                batch, on_conflict="wallet"
            ).execute()
            success_count += len(batch)
        except Exception as e:
            log.error(f"upsert batch {i // 100}: {e}")

    log.info(f"✅ 聪明钱 v3 更新完成: {success_count} 个钱包")

    # ── Step 6: 降级/移除不活跃钱包 ──────────────────────────
    _handle_inactive(db, now)

    # ── Step 7: Top Holder 自动晋升 ──────────────────────────
    _evaluate_top_holders(db)


# ═══════════════════════════════════════════════════════════
# 降级/移除不活跃钱包
# ═══════════════════════════════════════════════════════════

def _handle_inactive(db, now: datetime):
    """14天无交易降级，28天无交易移除"""
    demote_cutoff = (now - timedelta(days=INACTIVE_DEMOTE_DAYS)).isoformat()
    remove_cutoff = (now - timedelta(days=INACTIVE_REMOVE_DAYS)).isoformat()

    try:
        # 28天无交易 → 移除
        remove_res = db.table("smart_wallets").select(
            "wallet"
        ).lt("last_seen", remove_cutoff).neq(
            "tier", "blacklisted"
        ).execute()
        removed = 0
        for r in (remove_res.data or []):
            try:
                db.table("smart_wallets").delete().eq(
                    "wallet", r["wallet"]
                ).execute()
                removed += 1
            except Exception:
                pass
        if removed:
            log.info(f"[降级] 移除 {removed} 个 28天无交易钱包")

        # 14天无交易 → 降一级
        demote_map = {"elite": "verified", "verified": "watching"}
        for old_tier, new_tier in demote_map.items():
            demote_res = db.table("smart_wallets").select(
                "wallet"
            ).eq("tier", old_tier).lt(
                "last_seen", demote_cutoff
            ).execute()
            demoted = 0
            for r in (demote_res.data or []):
                try:
                    db.table("smart_wallets").update(
                        {"tier": new_tier}
                    ).eq("wallet", r["wallet"]).execute()
                    demoted += 1
                except Exception:
                    pass
            if demoted:
                log.info(f"[降级] {old_tier}→{new_tier}: {demoted} 个")

    except Exception as e:
        log.warning(f"[降级] 失败: {e}")


# ═══════════════════════════════════════════════════════════
# Top Holder 自动晋升
# ═══════════════════════════════════════════════════════════

def _evaluate_top_holders(db):
    """评估 hot_coin_top_holders，表现好的自动晋升为聪明钱"""
    try:
        perf_res = db.table("token_performance").select(
            "chain, address, daily_highs, best_pct"
        ).eq("source", "hot_live").eq("is_active", False).execute()

        good_tokens = set()
        for p in (perf_res.data or []):
            highs = p.get("daily_highs") or {}
            d3 = highs.get("D3", highs.get("3", {}))
            d3_pct = d3.get("pct", 0) if isinstance(d3, dict) else 0
            if d3_pct >= 20:
                good_tokens.add((p["chain"], p["address"]))

        if not good_tokens:
            log.info("[TopHolder晋升] 暂无 D3>=20% 的热币")
            return

        holder_counts = defaultdict(int)
        for chain, addr in good_tokens:
            try:
                holders_res = db.table("hot_coin_top_holders").select(
                    "holder_address"
                ).eq("chain", chain).eq("token_address", addr).execute()
                for h in (holders_res.data or []):
                    holder_counts[h["holder_address"]] += 1
            except Exception:
                pass

        existing_res = db.table("smart_wallets").select("wallet, tier").execute()
        existing = {r["wallet"].lower(): r["tier"] for r in (existing_res.data or [])}

        now_iso = datetime.now(timezone.utc).isoformat()
        promoted = 0
        for wallet, count in holder_counts.items():
            wallet_lower = wallet.lower()
            current_tier = existing.get(wallet_lower)

            # 已 elite 或已 blacklisted 一律跳过 — 不能用 holder count 解除黑名单，
            # 也不能用它降 elite
            if current_tier in ("elite", "blacklisted"):
                continue

            if count >= 3:
                new_tier = "verified"
            elif count >= 1 and current_tier is None:
                new_tier = "watching"
            else:
                continue

            # count 是"出现在好代币的次数"，不是真实交易数 —
            # 不要写入 total_trades / win_trades，防止 v3 评估误以为有真交易
            try:
                if current_tier is not None:
                    # 已存在：只更新 tier + last_seen，不覆盖真实交易数
                    db.table("smart_wallets").update({
                        "tier": new_tier,
                        "last_seen": now_iso,
                    }).eq("wallet", wallet).execute()
                else:
                    # 新钱包：插入空壳记录，total_trades 留给 v3 评估器从 txns 实算
                    db.table("smart_wallets").insert({
                        "wallet": wallet,
                        "tier": new_tier,
                        "active_weeks": 1,
                        "last_seen": now_iso,
                        "is_blacklisted": False,
                    }).execute()
                promoted += 1
            except Exception as e:
                log.debug(f"[TopHolder晋升] 跳过 {wallet[:8]}…: {e}")

        log.info(f"[TopHolder晋升] 好代币 {len(good_tokens)} 个，新增/升级 {promoted} 个聪明钱")

    except Exception as e:
        log.warning(f"[TopHolder晋升] 失败: {e}")


if __name__ == "__main__":
    import logging as _log
    _log.basicConfig(level=_log.INFO)
    run_smart_wallet_updater()
