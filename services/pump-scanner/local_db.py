"""
本地 PostgreSQL 连接 — 用于高频中间数据（dex_address_stats）

与 Supabase 分离：避免高频 DEX 地址统计写入占用 Supabase 免费额度。
本地 PostgreSQL 无行数限制、无 API 限流、零网络延迟。

连接信息：
  DB: agent_trading_local
  User: agent_local
  Host: localhost (Unix socket)
"""

import logging
import os
import psycopg2
from psycopg2.extras import execute_values
from contextlib import contextmanager

log = logging.getLogger(__name__)

_LOCAL_DB_DSN = os.getenv(
    "LOCAL_DB_DSN",
    "dbname=agent_trading_local user=agent_local password=agent_local_2026 host=localhost"
)

_pool = None


def _get_conn():
    """获取或创建连接（单连接 + 存活探测）。

    R71: 修登录报 'server closed the connection unexpectedly' 根因。
    server 端关闭空闲连接 / PG 重启时,客户端 _pool.closed 仍是 0(本地不知情),
    只判断 .closed 会返回一个'看着活实际死'的连接,下一次查询直接抛错给用户。
    auth/login 等调用方没有重连兜底 → 必须在这里 SELECT 1 探活,死了就重连。
    本地 Unix socket ping 亚毫秒级,开销可忽略。
    """
    global _pool
    try:
        if _pool is not None and not _pool.closed:
            try:
                with _pool.cursor() as cur:
                    cur.execute("SELECT 1")
                return _pool
            except Exception:
                # 连接已被 server 关闭 → 丢弃重连
                try:
                    _pool.close()
                except Exception:
                    pass
                _pool = None
        _pool = psycopg2.connect(_LOCAL_DB_DSN)
        _pool.autocommit = True
        log.info("[LocalDB] 连接成功: %s", _LOCAL_DB_DSN.split("password=")[0] + "***")
        return _pool
    except Exception as e:
        log.error("[LocalDB] 连接失败: %s", e)
        _pool = None
        raise


def upsert_address_stats(rows: list):
    """批量 upsert dex_address_stats（累加式）

    rows: [{"wallet_address": str, "chain": str, "tx_count": int, "unique_tokens": int}]
    """
    if not rows:
        return 0

    conn = _get_conn()
    sql = """
        INSERT INTO dex_address_stats (wallet_address, chain, total_tx_count, total_unique_tokens, active_windows, first_seen, last_seen)
        VALUES %s
        ON CONFLICT (wallet_address) DO UPDATE SET
            total_tx_count = dex_address_stats.total_tx_count + EXCLUDED.total_tx_count,
            total_unique_tokens = GREATEST(dex_address_stats.total_unique_tokens, EXCLUDED.total_unique_tokens),
            active_windows = dex_address_stats.active_windows + 1,
            last_seen = EXCLUDED.last_seen
    """
    values = [
        (r["wallet_address"], r["chain"], r["tx_count"], r["unique_tokens"], 1, r["last_seen"], r["last_seen"])
        for r in rows
    ]
    for attempt in range(2):
        try:
            with conn.cursor() as cur:
                execute_values(cur, sql, values, page_size=200)
            return len(values)
        except Exception as e:
            log.warning("[LocalDB] upsert_address_stats (attempt %d): %s", attempt + 1, e)
            global _pool
            _pool = None
            if attempt == 0:
                try:
                    conn = _get_conn()  # 重连一次
                except Exception:
                    return 0
    return 0


def get_promotion_candidates(min_windows=3, min_tx=20, min_tokens=5, limit=500):
    """查询待晋升的高频活跃地址"""
    conn = _get_conn()
    sql = """
        SELECT wallet_address, chain, total_tx_count, total_unique_tokens, active_windows
        FROM dex_address_stats
        WHERE promoted_at IS NULL
          AND active_windows >= %s
          AND total_tx_count >= %s
          AND total_unique_tokens >= %s
        ORDER BY active_windows DESC, total_tx_count DESC
        LIMIT %s
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (min_windows, min_tx, min_tokens, limit))
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        log.warning("[LocalDB] get_promotion_candidates: %s", e)
        return []


def mark_promoted(wallet_address: str, tier: str):
    """标记地址已晋升"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE dex_address_stats SET promoted_at = NOW(), promoted_tier = %s WHERE wallet_address = %s",
                (tier, wallet_address)
            )
    except Exception as e:
        log.debug("[LocalDB] mark_promoted %s: %s", wallet_address[:12], e)


def cleanup_old(days=90):
    """清理 N 天前已晋升的记录（控制表大小）"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM dex_address_stats WHERE promoted_at IS NOT NULL AND promoted_at < NOW() - INTERVAL '%s days'",
                (days,)
            )
            deleted = cur.rowcount
            if deleted:
                log.info("[LocalDB] 清理 %d 条 >%d天 已晋升记录", deleted, days)
            return deleted
    except Exception as e:
        log.warning("[LocalDB] cleanup: %s", e)
        return 0


def get_stats():
    """表统计（调试用）"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*), count(*) FILTER (WHERE promoted_at IS NOT NULL) FROM dex_address_stats")
            total, promoted = cur.fetchone()
            return {"total": total, "promoted": promoted, "pending": total - promoted}
    except Exception as e:
        return {"error": str(e)}
