"""
自有数据聪明钱挖掘器 — 从 smart_money_txns 表中发现活跃交易地址

运行时机：每 6h（APScheduler 调度）

策略（替代 Dune，数据 100% 来自我们监控的 DEX）：
1. 拉最近 14 天 smart_money_txns 全量数据（~9000 行，内存聚合）
2. 按 wallet_address 聚合：交易数 / 代币种类 / 活跃天数 / 买卖比
3. 过滤 bot（>2000 笔）和不活跃（<10 笔 or <3 代币 or <3 天）
4. 排除已在 smart_wallets 表中的地址
5. 新地址写入 smart_wallets（tier=watching）

优势：
- 天然 100% 跟我们的 DEX 监控重合（数据就来自 DEX WS/轮询）
- 每 6h 增量发现（比 Dune 每周一次快得多）
- 零外部 API 成本
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from database import get_db

log = logging.getLogger(__name__)

# ── 过滤参数 ──
MIN_TX_COUNT = 10       # 至少 10 笔交易（数据源精准，不需要 Dune 的 50）
MAX_TX_COUNT = 2000     # 超过 2000 = bot/MEV
MIN_UNIQUE_TOKENS = 3   # 至少交易 3 个不同代币
MIN_ACTIVE_DAYS = 3     # 至少 3 天有交易
MIN_BUY_COUNT = 3       # 至少 3 笔买入（排除纯卖出的清仓钱包）
LOOKBACK_DAYS = 14      # 14 天回溯窗口
PAGE_SIZE = 1000        # Supabase 分页大小


def run_txns_wallet_miner():
    """从 smart_money_txns 挖掘活跃交易地址 → 补充聪明钱池"""
    log.info("=== Txns Wallet Miner 开始 ===")
    db = get_db()

    # ── Step 1: 分页拉最近 14 天 txns ──
    cutoff = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    all_txns = []
    offset = 0
    while True:
        try:
            res = (
                db.table("smart_money_txns")
                .select("wallet_address, chain, tx_type, token_address, tx_time")
                .gte("tx_time", cutoff)
                .range(offset, offset + PAGE_SIZE - 1)
                .execute()
            )
            batch = res.data or []
            all_txns.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        except Exception as e:
            log.error("[TxnsMiner] 查询 smart_money_txns 失败: %s", e)
            return

    if not all_txns:
        log.info("[TxnsMiner] 14 天内无 txns 数据，跳过")
        return

    log.info("[TxnsMiner] 拉取 %d 条 txns（%d 天窗口）", len(all_txns), LOOKBACK_DAYS)

    # ── Step 2: Python 聚合（Supabase PostgREST 不支持 GROUP BY）──
    wallet_stats = defaultdict(lambda: {
        "chains": set(),
        "tx_count": 0,
        "buy_count": 0,
        "sell_count": 0,
        "unique_tokens": set(),
        "active_days": set(),
    })

    for tx in all_txns:
        addr = tx.get("wallet_address", "")
        if not addr:
            continue
        w = wallet_stats[addr]
        w["chains"].add(tx.get("chain", ""))
        w["tx_count"] += 1
        if tx.get("tx_type") == "buy":
            w["buy_count"] += 1
        else:
            w["sell_count"] += 1
        token = tx.get("token_address", "")
        if token:
            w["unique_tokens"].add(token)
        tx_time = tx.get("tx_time", "")
        if tx_time:
            w["active_days"].add(tx_time[:10])  # YYYY-MM-DD

    log.info("[TxnsMiner] %d 个唯一钱包", len(wallet_stats))

    # ── Step 3: 过滤 ──
    candidates = {}
    for addr, s in wallet_stats.items():
        tx_count = s["tx_count"]
        unique_tokens = len(s["unique_tokens"])
        active_days = len(s["active_days"])
        buy_count = s["buy_count"]

        if tx_count < MIN_TX_COUNT or tx_count > MAX_TX_COUNT:
            continue
        if unique_tokens < MIN_UNIQUE_TOKENS:
            continue
        if active_days < MIN_ACTIVE_DAYS:
            continue
        if buy_count < MIN_BUY_COUNT:
            continue

        candidates[addr] = {
            "chains": s["chains"],
            "tx_count": tx_count,
            "buy_count": buy_count,
            "unique_tokens": unique_tokens,
            "active_days": active_days,
        }

    log.info("[TxnsMiner] 过滤后 %d 个候选（%d txns → %d 唯一 → %d 通过过滤）",
             len(candidates), len(all_txns), len(wallet_stats), len(candidates))

    if not candidates:
        log.info("[TxnsMiner] 无新候选，结束")
        return

    # ── Step 4: 排除已存在的 smart_wallets ──
    existing = set()
    offset = 0
    while True:
        try:
            res = (
                db.table("smart_wallets")
                .select("wallet")
                .range(offset, offset + PAGE_SIZE - 1)
                .execute()
            )
            batch = res.data or []
            for r in batch:
                existing.add(r["wallet"].lower())
            if len(batch) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        except Exception as e:
            log.warning("[TxnsMiner] 查询 smart_wallets 失败: %s", e)
            break

    new_candidates = {
        addr: stats for addr, stats in candidates.items()
        if addr.lower() not in existing
    }
    log.info("[TxnsMiner] %d 个已存在，%d 个新发现", len(candidates) - len(new_candidates), len(new_candidates))

    # ── Step 5: 写入 smart_wallets ──
    now_iso = datetime.now(timezone.utc).isoformat()
    new_count = 0
    for addr, stats in new_candidates.items():
        row = {
            "wallet": addr,
            "tier": "watching",
            "total_trades": stats["tx_count"],
            "win_trades": 0,  # 留给 v3 评估器实算
            "total_sol_in": 0,
            "avg_entry_bc": 0,
            "active_weeks": stats["active_days"],
            "last_seen": now_iso,
            "is_blacklisted": False,
        }
        try:
            db.table("smart_wallets").upsert(row, on_conflict="wallet").execute()
            new_count += 1
        except Exception as e:
            log.debug("[TxnsMiner] 写入 %s: %s", addr[:12], e)

    log.info("=== Txns Miner（源1）完成: %d 条 txns → %d 候选 → %d 新增 ===",
             len(all_txns), len(candidates), new_count)

    # ── 源 2: 从 dex_address_stats 挖掘高频活跃未知地址 ──
    _mine_from_unknown_stats(db)


# ── 新增：未知地址晋升 ──────────────────────────────────────

# 从 dex_address_stats 晋升 watching 的阈值
_PROMOTE_MIN_WINDOWS = 3      # 至少出现在 3 个 30min 窗口（= 1.5h+ 持续活跃）
_PROMOTE_MIN_TX = 20           # 累积 20+ 笔交易
_PROMOTE_MIN_TOKENS = 5        # 交易 5+ 不同代币


def _mine_from_unknown_stats(db):
    """从 dex_address_stats 找高频活跃地址 → 晋升 smart_wallets.watching"""
    log.info("[TxnsMiner] 源2: 从 dex_address_stats 挖掘未知高频地址")

    try:
        res = (
            db.table("dex_address_stats")
            .select("wallet_address, chain, total_tx_count, total_unique_tokens, active_windows")
            .gte("active_windows", _PROMOTE_MIN_WINDOWS)
            .gte("total_tx_count", _PROMOTE_MIN_TX)
            .gte("total_unique_tokens", _PROMOTE_MIN_TOKENS)
            .is_("promoted_at", "null")
            .limit(500)
            .execute()
        )
        candidates = res.data or []
    except Exception as e:
        log.warning("[TxnsMiner] 查询 dex_address_stats 失败: %s", e)
        return

    if not candidates:
        log.info("[TxnsMiner] 源2: 无达标候选")
        return

    log.info("[TxnsMiner] 源2: %d 个达标候选", len(candidates))

    # 排除已在 smart_wallets 的
    existing = set()
    offset = 0
    while True:
        try:
            r = db.table("smart_wallets").select("wallet").range(offset, offset + 999).execute()
            batch = r.data or []
            for row in batch:
                existing.add(row["wallet"].lower())
            if len(batch) < 1000:
                break
            offset += 1000
        except Exception:
            break

    now_iso = datetime.now(timezone.utc).isoformat()
    promoted = 0
    for c in candidates:
        addr = c["wallet_address"]
        if addr.lower() in existing:
            # 已存在但未标记 promoted → 更新标记
            try:
                db.table("dex_address_stats").update({
                    "promoted_at": now_iso, "promoted_tier": "existing"
                }).eq("wallet_address", addr).execute()
            except Exception:
                pass
            continue

        # 新地址 → 写入 smart_wallets
        try:
            db.table("smart_wallets").insert({
                "wallet": addr,
                "tier": "watching",
                "total_trades": c.get("total_tx_count", 0),
                "win_trades": 0,
                "active_weeks": c.get("active_windows", 1),
                "last_seen": now_iso,
                "is_blacklisted": False,
            }).execute()

            # 标记已晋升
            db.table("dex_address_stats").update({
                "promoted_at": now_iso, "promoted_tier": "watching"
            }).eq("wallet_address", addr).execute()

            promoted += 1
            existing.add(addr.lower())
        except Exception as e:
            log.debug("[TxnsMiner] 源2 写入 %s: %s", addr[:12], e)

    log.info("[TxnsMiner] 源2 完成: %d 候选 → %d 新增 watching", len(candidates), promoted)


if __name__ == "__main__":
    import logging as _log
    _log.basicConfig(level=_log.INFO)
    from dotenv import load_dotenv
    load_dotenv()
    run_txns_wallet_miner()
