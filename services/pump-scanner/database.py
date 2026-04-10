from typing import Optional, List
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY
import logging

log = logging.getLogger(__name__)

_client: Optional[Client] = None

def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def upsert_token(token: dict):
    """保存/更新代币基础信息"""
    try:
        get_db().table("pump_tokens").upsert(token, on_conflict="mint").execute()
    except Exception as e:
        log.error(f"upsert_token error: {e}")


# 新增列（014 migration），首次失败后自动降级
_snapshot_extra_cols = {
    "inflow_acceleration", "smart_money_count", "smart_money_net_sol",
    "smart_elite_count", "smart_verified_count", "smart_watching_count",
}
_snapshot_cols_available = True  # 首次错误后置 False


_snapshot_buffer: list = []
_snapshot_buffer_lock = __import__("threading").Lock()
_SNAPSHOT_BATCH_SIZE = 50


def insert_snapshot(snapshot: dict):
    """缓冲插入快照 — 每 50 条批量写入"""
    global _snapshot_cols_available
    data = snapshot
    if not _snapshot_cols_available:
        data = {k: v for k, v in snapshot.items() if k not in _snapshot_extra_cols}
    with _snapshot_buffer_lock:
        _snapshot_buffer.append(data)
        if len(_snapshot_buffer) < _SNAPSHOT_BATCH_SIZE:
            return
        batch = list(_snapshot_buffer)
        _snapshot_buffer.clear()
    _flush_snapshot_batch(batch)


def flush_snapshot_buffer():
    """强制刷新快照缓冲区（定时器调用）"""
    with _snapshot_buffer_lock:
        if not _snapshot_buffer:
            return
        batch = list(_snapshot_buffer)
        _snapshot_buffer.clear()
    _flush_snapshot_batch(batch)


def _flush_snapshot_batch(batch: list):
    """批量写入 token_snapshots"""
    global _snapshot_cols_available
    if not batch:
        return
    try:
        get_db().table("token_snapshots").insert(batch).execute()
    except Exception as e:
        err_msg = str(e)
        if "does not exist" in err_msg and _snapshot_cols_available:
            _snapshot_cols_available = False
            log.warning("token_snapshots 缺少新列，降级模式")
            fallback = [{k: v for k, v in row.items() if k not in _snapshot_extra_cols} for row in batch]
            try:
                get_db().table("token_snapshots").insert(fallback).execute()
            except Exception as e2:
                log.error(f"batch insert_snapshot fallback error ({len(batch)} rows): {e2}")
        else:
            log.error(f"batch insert_snapshot error ({len(batch)} rows): {e}")


_trade_buffer: list = []
_trade_buffer_lock = __import__("threading").Lock()
_TRADE_BATCH_SIZE = 50  # 每 50 条批量写入一次


def insert_trade(trade: dict):
    """缓冲插入交易流水 — 每 50 条批量 upsert，减少 Supabase 连接消耗"""
    with _trade_buffer_lock:
        _trade_buffer.append(trade)
        if len(_trade_buffer) < _TRADE_BATCH_SIZE:
            return
        batch = list(_trade_buffer)
        _trade_buffer.clear()
    _flush_trade_batch(batch)


def flush_trade_buffer():
    """强制刷新缓冲区（定时器调用）"""
    with _trade_buffer_lock:
        if not _trade_buffer:
            return
        batch = list(_trade_buffer)
        _trade_buffer.clear()
    _flush_trade_batch(batch)


def _flush_trade_batch(batch: list):
    """批量写入 token_trades"""
    if not batch:
        return
    try:
        get_db().table("token_trades").upsert(batch, on_conflict="tx_sig").execute()
    except Exception as e:
        log.error(f"batch insert_trade error ({len(batch)} rows): {e}")


def get_active_tokens() -> List[str]:
    """获取当前追踪中的候选币 mint 列表（未毕业 + 未排除）"""
    try:
        res = (
            get_db()
            .table("pump_tokens")
            .select("mint")
            .eq("complete", False)
            .eq("is_banned", False)
            .execute()
        )
        return [r["mint"] for r in res.data]
    except Exception as e:
        log.error(f"get_active_tokens error: {e}")
        return []


def mark_graduated(mint: str, graduated_at: str):
    """标记代币已毕业"""
    try:
        get_db().table("pump_tokens").update({
            "complete": True,
            "graduated_at": graduated_at,
        }).eq("mint", mint).execute()
    except Exception as e:
        log.error(f"mark_graduated error: {e}")


def cleanup_old_trades():
    """清理 30 天前的交易流水"""
    try:
        get_db().rpc("delete_old_trades").execute()
    except Exception as e:
        log.error(f"cleanup_old_trades error: {e}")


def upsert_hot_coins(rows: List[dict]):
    """批量写入热币数据（每批50条）"""
    if not rows:
        return
    try:
        for i in range(0, len(rows), 50):
            batch = rows[i:i + 50]
            get_db().table("hot_coins").upsert(
                batch, on_conflict="chain,address"
            ).execute()
        log.info(f"upsert_hot_coins: {len(rows)} 条")
    except Exception as e:
        log.error(f"upsert_hot_coins error: {e}")


def save_hot_daily_picks(picks: List[dict]):
    """保存热币日榜（upsert，pick_date+chain+address 唯一）"""
    if not picks:
        return
    try:
        get_db().table("hot_daily_picks").upsert(
            picks, on_conflict="pick_date,chain,address"
        ).execute()
    except Exception as e:
        log.error(f"save_hot_daily_picks error: {e}")


def upsert_performance(rows: list):
    """批量写入代币表现追踪数据"""
    if not rows:
        return
    try:
        for i in range(0, len(rows), 50):
            batch = rows[i:i + 50]
            get_db().table("token_performance").upsert(
                batch, on_conflict="source,pick_date,chain,address"
            ).execute()
        log.info(f"upsert_performance: {len(rows)} 条")
    except Exception as e:
        log.error(f"upsert_performance error: {e}")


def get_active_performance() -> list:
    """获取所有活跃的表现追踪行"""
    try:
        res = (
            get_db()
            .table("token_performance")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        return res.data
    except Exception as e:
        log.error(f"get_active_performance error: {e}")
        return []


def get_smart_wallet_tiers() -> dict:
    """
    加载聪明钱分级数据
    返回: {wallet_address: tier_str}
    tier: 'elite' | 'verified' | 'watching'（黑名单不返回）
    """
    try:
        res = (
            get_db()
            .table("smart_wallets")
            .select("wallet, tier")
            .eq("is_blacklisted", False)
            .in_("tier", ["elite", "verified", "watching"])
            .execute()
        )
        return {r["wallet"]: r["tier"] for r in res.data}
    except Exception as e:
        log.error(f"get_smart_wallet_tiers error: {e}")
        return {}
