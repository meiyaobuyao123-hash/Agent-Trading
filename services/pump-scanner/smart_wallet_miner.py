"""
聪明钱地址挖掘器 — 从自有数据中发现聪明钱

运行时机：每天 UTC 04:00（APScheduler 调度）

策略：
1. 找毕业代币（complete=True）的早期买家（bc < 10%）
2. 命中 2+ 个毕业代币 → 写入 smart_wallets（tier=watching, source=mined）
3. 已存在的地址不重复写入
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone

from database import get_db

log = logging.getLogger(__name__)

# 最低命中数：早期买入多少个毕业代币才算聪明钱候选
MIN_GRADUATED_HITS = 2
# 早期买家定义：BC < 10% 时买入
EARLY_BC_THRESHOLD = 10.0


def run_smart_wallet_miner():
    """从 token_trades 挖掘毕业代币早期买家"""
    log.info("=== Smart Wallet Miner 开始 ===")
    db = get_db()

    # 1. 获取所有毕业代币
    try:
        grad_res = db.table("pump_tokens").select("mint").eq("complete", True).execute()
        graduated_mints = {r["mint"] for r in (grad_res.data or [])}
    except Exception as e:
        log.error("查询毕业代币失败: %s", e)
        return
    log.info("毕业代币: %d 个", len(graduated_mints))
    if not graduated_mints:
        log.info("无毕业代币，跳过")
        return

    # 2. 查早期买家（分批查询避免超限）
    early_buyers = defaultdict(set)  # {trader: set(mint1, mint2, ...)}
    mints_list = list(graduated_mints)

    for i in range(0, len(mints_list), 20):
        batch = mints_list[i:i + 20]
        try:
            res = (
                db.table("token_trades")
                .select("trader, mint")
                .in_("mint", batch)
                .eq("tx_type", "buy")
                .lt("bc_progress", EARLY_BC_THRESHOLD)
                .execute()
            )
            for r in (res.data or []):
                trader = r.get("trader", "")
                mint = r.get("mint", "")
                if trader and mint:
                    early_buyers[trader].add(mint)
        except Exception as e:
            log.warning("查询 token_trades batch %d: %s", i, e)

    log.info("早期买家总数: %d", len(early_buyers))

    # 3. 筛选：命中 2+ 个毕业代币
    candidates = {
        trader: mints
        for trader, mints in early_buyers.items()
        if len(mints) >= MIN_GRADUATED_HITS
    }
    log.info("命中 %d+ 个毕业代币: %d 个候选", MIN_GRADUATED_HITS, len(candidates))

    if not candidates:
        log.info("无新候选，结束")
        return

    # 4. 查现有 smart_wallets，避免重复
    try:
        existing_res = db.table("smart_wallets").select("wallet").execute()
        existing_wallets = {r["wallet"].lower() for r in (existing_res.data or [])}
    except Exception as e:
        log.warning("查询现有 smart_wallets: %s", e)
        existing_wallets = set()

    # 5. 写入新地址
    new_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    for trader, mints in candidates.items():
        if trader.lower() in existing_wallets:
            continue
        row = {
            "wallet": trader,
            "tier": "watching",
            "total_trades": len(mints),
            "win_trades": len(mints),
            "total_sol_in": 0,
            "avg_entry_bc": 0,
            "active_weeks": 1,
            "last_seen": now_iso,
            "is_blacklisted": False,
        }
        try:
            db.table("smart_wallets").upsert(row, on_conflict="wallet").execute()
            new_count += 1
        except Exception as e:
            log.warning("写入 smart_wallets %s: %s", trader[:12], e)

    log.info("=== Miner 完成: 新增 %d 个聪明钱地址 (总候选 %d) ===", new_count, len(candidates))
