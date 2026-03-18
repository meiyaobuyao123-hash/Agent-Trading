"""
Dune Analytics 聪明钱地址导入器

运行时机：每周一次（APScheduler 调度，每周一 UTC 05:00）

策略：
1. 从 Dune 查询 SOL/EVM 链上高频 DEX 交易者
2. 过滤 bot（交易次数 > 10000/14天 = 明显自动化）
3. 筛选有意义的交易者（30-10000 笔，5+ 代币，5+ 活跃天）
4. 写入 smart_wallets（tier=watching, source=dune）
5. 已存在的地址不重复写入
"""

import logging
import os
from datetime import datetime, timezone
from typing import List, Dict, Any

import requests

from database import get_db

log = logging.getLogger(__name__)

DUNE_API_KEY = os.getenv("DUNE_API_KEY", "")
DUNE_BASE = "https://api.dune.com/api/v1"

# Dune 查询 ID（在 dune.com 网页上创建并保存）
# 每个查询返回该链上14天内高频 DEX 交易者（过滤 bot，LIMIT 5000）
DUNE_QUERY_IDS = {
    "solana": int(os.getenv("DUNE_QUERY_SOL", "6850812")),
    "eth": int(os.getenv("DUNE_QUERY_ETH", "0")),
    "bsc": int(os.getenv("DUNE_QUERY_BSC", "0")),
    "base": int(os.getenv("DUNE_QUERY_BASE", "0")),
}

# Bot 过滤：14 天内超过 5000 笔交易 → 大概率是 bot/MEV
MAX_SWAPS_14D = 5000
# 最低交易数
MIN_SWAPS_14D = 30
# 最少交易代币种类
MIN_UNIQUE_TOKENS = 5
# 最少活跃天数
MIN_ACTIVE_DAYS = 5
# Dune 查询已在 SQL 层做了过滤（BETWEEN 30 AND 5000），这里做二次校验


def run_dune_wallet_import():
    """从 Dune Analytics 导入聪明钱地址"""
    if not DUNE_API_KEY:
        log.warning("[Dune] DUNE_API_KEY 未设置，跳过")
        return

    log.info("=== Dune Wallet Importer 开始 ===")
    db = get_db()
    total_new = 0

    for chain, query_id in DUNE_QUERY_IDS.items():
        if query_id <= 0:
            continue  # 未配置该链的查询
        try:
            wallets = _fetch_dune_results(query_id, chain)
            if not wallets:
                log.info(f"[Dune] {chain}: 无结果")
                continue

            new_count = _import_wallets(db, wallets, chain)
            total_new += new_count
            log.info(f"[Dune] {chain}: 获取 {len(wallets)} 个候选，新增 {new_count} 个")
        except Exception as e:
            log.error(f"[Dune] {chain} 导入失败: {e}")

    log.info(f"=== Dune Importer 完成: 总新增 {total_new} 个地址 ===")


def _fetch_dune_results(query_id: int, chain: str) -> List[Dict[str, Any]]:
    """从 Dune API 获取查询结果，过滤 bot"""
    headers = {"X-Dune-API-Key": DUNE_API_KEY}

    # 先尝试触发执行（如果结果太旧）
    try:
        exec_resp = requests.post(
            f"{DUNE_BASE}/query/{query_id}/execute",
            headers=headers,
            timeout=15,
        )
        if exec_resp.status_code == 200:
            execution_id = exec_resp.json().get("execution_id")
            log.info(f"[Dune] 触发执行 query {query_id}: {execution_id}")
            # 等待执行完成（最多 60 秒）
            import time
            for _ in range(12):
                time.sleep(5)
                status_resp = requests.get(
                    f"{DUNE_BASE}/execution/{execution_id}/status",
                    headers=headers,
                    timeout=10,
                )
                if status_resp.status_code == 200:
                    state = status_resp.json().get("state", "")
                    if state == "QUERY_STATE_COMPLETED":
                        break
                    elif state in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED"):
                        log.warning(f"[Dune] 查询执行失败: {state}")
                        return []
    except Exception as e:
        log.debug(f"[Dune] 触发执行失败（使用缓存结果）: {e}")

    # 获取结果
    resp = requests.get(
        f"{DUNE_BASE}/query/{query_id}/results",
        headers=headers,
        timeout=30,
    )
    if resp.status_code != 200:
        log.warning(f"[Dune] 获取结果失败: {resp.status_code} {resp.text[:200]}")
        return []

    rows = resp.json().get("result", {}).get("rows", [])
    if not rows:
        return []

    # 过滤 bot 和不活跃地址
    filtered = []
    for r in rows:
        swaps = r.get("total_swaps", 0)
        tokens = r.get("unique_tokens", 0)
        days = r.get("active_days", 0)
        wallet = r.get("wallet", "")

        if not wallet:
            continue
        if swaps > MAX_SWAPS_14D:
            continue  # bot/MEV
        if swaps < MIN_SWAPS_14D:
            continue
        if tokens < MIN_UNIQUE_TOKENS:
            continue
        if days < MIN_ACTIVE_DAYS:
            continue

        filtered.append({
            "wallet": wallet,
            "chain": chain,
            "swaps": swaps,
            "tokens": tokens,
            "days": days,
        })

    log.info(f"[Dune] {chain}: {len(rows)} 行 → 过滤后 {len(filtered)} 个有效地址")
    return filtered


def _import_wallets(db, wallets: List[Dict[str, Any]], chain: str) -> int:
    """写入 smart_wallets 表，去重"""
    # 查现有地址
    try:
        existing_res = db.table("smart_wallets").select("wallet").execute()
        existing = {r["wallet"].lower() for r in (existing_res.data or [])}
    except Exception:
        existing = set()

    now_iso = datetime.now(timezone.utc).isoformat()
    new_count = 0

    for w in wallets:
        addr = w["wallet"]
        if addr.lower() in existing:
            continue

        row = {
            "wallet": addr,
            "tier": "watching",
            "total_trades": w.get("swaps", 0),
            "win_trades": 0,
            "total_sol_in": 0,
            "avg_entry_bc": 0,
            "active_weeks": w.get("days", 1),
            "last_seen": now_iso,
            "is_blacklisted": False,
        }
        try:
            db.table("smart_wallets").upsert(row, on_conflict="wallet").execute()
            new_count += 1
            existing.add(addr.lower())
        except Exception as e:
            log.debug(f"[Dune] 写入 {addr[:12]}: {e}")

    return new_count


if __name__ == "__main__":
    import logging as _log
    _log.basicConfig(level=_log.INFO)
    run_dune_wallet_import()
