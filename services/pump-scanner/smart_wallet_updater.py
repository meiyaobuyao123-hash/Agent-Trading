"""
聪明钱识别器 v2 — 多维度分层体系

运行时机：每6小时（APScheduler 调度）

━━━━ 分层规则 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
精英(elite)
  - 加权胜率 ≥ 0.65
  - ≥ 10 笔有标签代币交易（60天内）
  - 活跃自然周 ≥ 2（能力稳定，非一周运气）
  - 平均入场BC < 15%（有数据时，买得早 = 真聪明）

验证(verified)
  - 加权胜率 ≥ 0.50
  - ≥ 5 笔有标签代币交易

观察(watching)
  - 加权胜率 ≥ 0.40
  - ≥ 3 笔有标签代币交易

黑名单(blacklisted)
  - 同代币买入后 60 秒内卖出（疑似 Bot/Sniper）
  - 或 胜率 < 20% 且 ≥ 10 笔（长期负盈利）

━━━━ 时间衰减 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  交易 < 30天前：权重 1.0（全权重）
  交易 30~60天前：权重 0.5
  交易 > 60天前：不计入（weight=0）

━━━━ 胜率定义 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  成功 = 买入代币最终 did_graduate=True 或 label_2x=True
  加权胜率 = Σ(weight × success) / Σ(weight)
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict

from database import get_db

log = logging.getLogger(__name__)

# ── 时间衰减窗口 ─────────────────────────────────────────────
DECAY_FULL_DAYS  = 30    # 30天内：权重 1.0
DECAY_HALF_DAYS  = 60    # 30-60天：权重 0.5（超过则不计入）

# ── Bot 检测阈值 ─────────────────────────────────────────────
BOT_HOLD_SECONDS = 60    # 买入后N秒内卖出同一代币 → 疑似Bot/Sniper

# ── 分层阈值 ─────────────────────────────────────────────────
ELITE_WIN_RATE      = 0.65
ELITE_MIN_TRADES    = 10
ELITE_MIN_WEEKS     = 2
ELITE_MAX_ENTRY_BC  = 15.0   # 仅在有 bc_progress_at_buy 数据时约束

VERIFIED_WIN_RATE   = 0.50
VERIFIED_MIN_TRADES = 5

WATCHING_WIN_RATE   = 0.40
WATCHING_MIN_TRADES = 3

BLACKLIST_WIN_RATE  = 0.20   # 胜率低于此 且 trade_count 足够 → 拉黑
BLACKLIST_MIN_TRADES = 10

# Supabase 每批处理的 mint 数量
BATCH_SIZE = 200


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def _time_weight(traded_at_str: str, now: datetime) -> float:
    """根据交易时间返回权重（时间衰减）"""
    try:
        t = datetime.fromisoformat(traded_at_str.replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        age_days = (now - t).total_seconds() / 86400.0
        if age_days > DECAY_HALF_DAYS:
            return 0.0
        elif age_days > DECAY_FULL_DAYS:
            return 0.5
        return 1.0
    except Exception:
        return 1.0  # 解析失败给全权重，保守处理


def _iso_week_key(traded_at_str: str) -> Optional[str]:
    """提取 'YYYY-WW' 用于统计活跃周数"""
    try:
        t = datetime.fromisoformat(traded_at_str.replace("Z", "+00:00"))
        iso = t.isocalendar()
        return f"{iso.year}-{iso.week:02d}"
    except Exception:
        return None


def _new_wallet_stats() -> dict:
    return {
        "weighted_wins":  0.0,
        "weighted_total": 0.0,
        "trade_count":    0,
        "win_count":      0,
        "entry_bc_list":  [],    # bc_progress_at_buy 值列表（非 None）
        "week_set":       set(), # 有效交易分布的自然周
        "last_active":    "",
        "mint_buy_times": defaultdict(list),  # mint → [buy_datetime, ...]
        "total_sol":      0.0,
    }


# ═══════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════

def run_smart_wallet_updater():
    log.info("⚙️  聪明钱多维度更新开始...")
    db  = get_db()
    now = datetime.now(timezone.utc)
    cutoff_60d = (now - timedelta(days=DECAY_HALF_DAYS)).isoformat()

    # ── Step 1: 拿所有已标签代币的结果 ──────────────────────
    outcomes_res = (
        db.table("token_outcomes")
        .select("mint, label_2x, did_graduate")
        .execute()
    )
    if not outcomes_res.data:
        log.info("暂无标签数据，跳过")
        return

    outcome_map: Dict[str, bool] = {}
    for r in outcomes_res.data:
        outcome_map[r["mint"]] = bool(r.get("label_2x")) or bool(r.get("did_graduate"))

    labeled_mints = list(outcome_map.keys())
    log.info(f"已标签代币: {len(labeled_mints)} 个  "
             f"（成功: {sum(outcome_map.values())} | 失败: {len(labeled_mints) - sum(outcome_map.values())}）")

    # ── Step 2: 分批拉取最近60天的买单 ──────────────────────
    wallet_stats: Dict[str, dict] = defaultdict(_new_wallet_stats)

    for i in range(0, len(labeled_mints), BATCH_SIZE):
        batch = labeled_mints[i:i + BATCH_SIZE]
        res = (
            db.table("token_trades")
            .select("mint, trader, sol_amount, traded_at, bc_progress")
            .in_("mint", batch)
            .eq("tx_type", "buy")
            .gte("traded_at", cutoff_60d)
            .execute()
        )
        for t in (res.data or []):
            wallet    = t.get("trader", "")
            if not wallet:
                continue
            mint      = t["mint"]
            traded_at = t.get("traded_at", "")
            weight    = _time_weight(traded_at, now)
            if weight == 0.0:
                continue  # 超出时间窗口，跳过

            ws      = wallet_stats[wallet]
            success = outcome_map.get(mint, False)

            ws["weighted_total"] += weight
            ws["weighted_wins"]  += weight * (1.0 if success else 0.0)
            ws["trade_count"]    += 1
            ws["win_count"]      += 1 if success else 0
            ws["total_sol"]      += float(t.get("sol_amount") or 0)

            # bc_progress 列：买入时的BC进度（自本次 migration 后开始有数据）
            bc_at_buy = t.get("bc_progress")
            if bc_at_buy is not None:
                ws["entry_bc_list"].append(float(bc_at_buy))

            week_key = _iso_week_key(traded_at)
            if week_key:
                ws["week_set"].add(week_key)

            if traded_at > ws["last_active"]:
                ws["last_active"] = traded_at

            # 记录买入时间戳（Bot检测用）
            try:
                bt = datetime.fromisoformat(traded_at.replace("Z", "+00:00"))
                if bt.tzinfo is None:
                    bt = bt.replace(tzinfo=timezone.utc)
                ws["mint_buy_times"][mint].append(bt)
            except Exception:
                pass

    log.info(f"统计到 {len(wallet_stats)} 个有效买入钱包")

    # ── Step 3: Bot 检测 ─────────────────────────────────────
    # 找出"买入后 BOT_HOLD_SECONDS 秒内卖出同一代币"的钱包
    bot_wallets: set = set()

    for i in range(0, len(labeled_mints), BATCH_SIZE):
        batch = labeled_mints[i:i + BATCH_SIZE]
        sell_res = (
            db.table("token_trades")
            .select("mint, trader, traded_at")
            .in_("mint", batch)
            .eq("tx_type", "sell")
            .gte("traded_at", cutoff_60d)
            .execute()
        )
        for s in (sell_res.data or []):
            wallet = s.get("trader", "")
            mint   = s["mint"]
            if not wallet or wallet not in wallet_stats:
                continue
            buy_times = wallet_stats[wallet]["mint_buy_times"].get(mint, [])
            if not buy_times:
                continue
            try:
                sell_time = datetime.fromisoformat(
                    s["traded_at"].replace("Z", "+00:00")
                )
                if sell_time.tzinfo is None:
                    sell_time = sell_time.replace(tzinfo=timezone.utc)
                for bt in buy_times:
                    diff = (sell_time - bt).total_seconds()
                    if 0 <= diff < BOT_HOLD_SECONDS:
                        bot_wallets.add(wallet)
                        break
            except Exception:
                pass

    log.info(f"疑似 Bot 钱包: {len(bot_wallets)} 个")

    # ── Step 4: 分层 & 构建 upsert 数据 ─────────────────────
    now_str = now.isoformat()
    upsert_rows: List[dict] = []
    tier_counts: Dict[str, int] = defaultdict(int)

    for wallet, ws in wallet_stats.items():
        total = ws["weighted_total"]
        if total <= 0:
            continue

        w_win_rate   = ws["weighted_wins"] / total
        trade_count  = ws["trade_count"]
        win_count    = ws["win_count"]
        active_weeks = len(ws["week_set"])
        last_active  = ws["last_active"] or now_str
        total_sol    = round(ws["total_sol"], 4)
        avg_entry_bc = (
            round(sum(ws["entry_bc_list"]) / len(ws["entry_bc_list"]), 2)
            if ws["entry_bc_list"] else None
        )

        # 匹配 smart_wallets 真实列名（003 migration schema）
        # total_trades / win_trades / last_seen + 新增列
        row_base = {
            "wallet":        wallet,
            "total_trades":  trade_count,   # 原列名
            "win_trades":    win_count,     # 原列名
            "total_sol_in":  total_sol,     # 004 新增
            "avg_entry_bc":  avg_entry_bc,  # 004 新增
            "active_weeks":  active_weeks,  # 004 新增
            "last_seen":     last_active,   # 原列名（替代 last_active_at）
            # win_rate 是 GENERATED 列，不能 INSERT
        }

        # ── 黑名单优先判断 ──────────────────────────────────
        # 1. Bot 行为
        if wallet in bot_wallets:
            upsert_rows.append({
                **row_base,
                "tier":           "blacklisted",
                "is_blacklisted": True,
            })
            tier_counts["blacklisted"] += 1
            continue

        # 2. 长期负盈利
        if trade_count >= BLACKLIST_MIN_TRADES and w_win_rate < BLACKLIST_WIN_RATE:
            upsert_rows.append({
                **row_base,
                "tier":           "blacklisted",
                "is_blacklisted": True,
            })
            tier_counts["blacklisted"] += 1
            continue

        # ── 正向分层 ──────────────────────────────────────
        # 精英：最严格，要求胜率高 + 样本多 + 跨周稳定 + 早期入场
        entry_ok = (avg_entry_bc is None or avg_entry_bc < ELITE_MAX_ENTRY_BC)
        if (w_win_rate >= ELITE_WIN_RATE
                and trade_count  >= ELITE_MIN_TRADES
                and active_weeks >= ELITE_MIN_WEEKS
                and entry_ok):
            tier = "elite"

        elif w_win_rate >= VERIFIED_WIN_RATE and trade_count >= VERIFIED_MIN_TRADES:
            tier = "verified"

        elif w_win_rate >= WATCHING_WIN_RATE and trade_count >= WATCHING_MIN_TRADES:
            tier = "watching"

        else:
            continue  # 不符合任何正向阈值，不写入

        upsert_rows.append({
            **row_base,
            "tier":           tier,
            "is_blacklisted": False,
        })
        tier_counts[tier] += 1

    log.info(
        f"分层结果 → 精英:{tier_counts['elite']}  "
        f"验证:{tier_counts['verified']}  "
        f"观察:{tier_counts['watching']}  "
        f"黑名单:{tier_counts['blacklisted']}"
    )

    # ── Step 5: 分批 upsert ──────────────────────────────────
    if not upsert_rows:
        log.info("暂无符合条件的钱包，本次跳过")
        return

    success_count = 0
    for i in range(0, len(upsert_rows), 100):
        batch = upsert_rows[i:i + 100]
        try:
            db.table("smart_wallets").upsert(
                batch, on_conflict="wallet"
            ).execute()
            success_count += len(batch)
        except Exception as e:
            log.error(f"upsert smart_wallets 失败 (batch {i//100}): {e}")

    log.info(f"✅ 聪明钱多维度更新完成，共写入 {success_count} 个钱包")

    # ── Step 6: Top Holder 自动晋升 ────────────────────────────
    _evaluate_top_holders(db)


def _evaluate_top_holders(db):
    """评估 hot_coin_top_holders，表现好的自动晋升为聪明钱"""
    try:
        # 查 D3 涨幅 >= 20% 的热币
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

        # 查这些热币的 top holders
        holder_counts = defaultdict(int)  # {wallet: count}
        promoted = 0
        for chain, addr in good_tokens:
            try:
                holders_res = db.table("hot_coin_top_holders").select(
                    "holder_address"
                ).eq("chain", chain).eq("token_address", addr).execute()
                for h in (holders_res.data or []):
                    holder_counts[h["holder_address"]] += 1
            except Exception:
                pass

        # 查现有 smart_wallets
        existing_res = db.table("smart_wallets").select("wallet, tier").execute()
        existing = {r["wallet"].lower(): r["tier"] for r in (existing_res.data or [])}

        now_iso = datetime.now(timezone.utc).isoformat()
        for wallet, count in holder_counts.items():
            wallet_lower = wallet.lower()
            current_tier = existing.get(wallet_lower)

            # 跨 3+ 个好代币 → verified
            if count >= 3 and current_tier != "elite":
                new_tier = "verified"
            # 至少 1 个好代币 → watching（如果还不在库里）
            elif count >= 1 and current_tier is None:
                new_tier = "watching"
            else:
                continue

            try:
                db.table("smart_wallets").upsert({
                    "wallet": wallet,
                    "tier": new_tier,
                    "total_trades": count,
                    "win_trades": count,
                    "total_sol_in": 0,
                    "avg_entry_bc": 0,
                    "active_weeks": 1,
                    "last_seen": now_iso,
                    "is_blacklisted": False,
                }, on_conflict="wallet").execute()
                promoted += 1
            except Exception:
                pass

        log.info(f"[TopHolder晋升] 好代币 {len(good_tokens)} 个，新增/升级 {promoted} 个聪明钱地址")

    except Exception as e:
        log.warning(f"[TopHolder晋升] 失败: {e}")


if __name__ == "__main__":
    import logging as _log
    _log.basicConfig(level=_log.INFO)
    run_smart_wallet_updater()
