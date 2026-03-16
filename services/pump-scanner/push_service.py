"""
pump-scanner 实时推送服务（带防刷限流）

对 agent/push_service.py 的上层封装，增加：
  - 每用户每小时最多 10 条推送（内存计数器）
  - 每天总推送不超过 30 条（系统级）
  - 全量用户广播：查询所有注册设备，逐用户发送

Python 3.9 兼容。
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# 内存限流状态
# ──────────────────────────────────────────────────────────────────

# 每用户每小时计数：user_id → (hour_bucket: int, count: int)
# hour_bucket = UTC 小时戳（unix_ts // 3600）
_user_hourly: Dict[str, Tuple[int, int]] = {}

# 每日总推送计数：date_str → count
_daily_total: Dict[str, int] = {}

# 每用户每小时上限
_MAX_PER_USER_HOURLY = 10

# 每天系统总推送上限
_MAX_DAILY_TOTAL = 30


def _check_rate_limit(user_id: str) -> bool:
    """
    检查是否超出限流阈值。

    Returns:
        True  = 允许发送
        False = 超出限制，应跳过
    """
    now = datetime.now(timezone.utc)
    date_str = now.date().isoformat()
    hour_bucket = int(now.timestamp()) // 3600

    # 1. 每日系统总量检查
    daily_count = _daily_total.get(date_str, 0)
    if daily_count >= _MAX_DAILY_TOTAL:
        log.debug("每日总推送已达上限 (%d)，跳过", _MAX_DAILY_TOTAL)
        return False

    # 2. 每用户每小时检查
    bucket, count = _user_hourly.get(user_id, (hour_bucket, 0))
    if bucket != hour_bucket:
        # 新的小时段，重置
        count = 0
        bucket = hour_bucket

    if count >= _MAX_PER_USER_HOURLY:
        log.debug("用户 %s 本小时推送已达上限 (%d)", user_id, _MAX_PER_USER_HOURLY)
        return False

    return True


def _incr_counters(user_id: str) -> None:
    """推送成功后递增计数器"""
    now = datetime.now(timezone.utc)
    date_str = now.date().isoformat()
    hour_bucket = int(now.timestamp()) // 3600

    # 日计数
    _daily_total[date_str] = _daily_total.get(date_str, 0) + 1

    # 用户每小时计数
    bucket, count = _user_hourly.get(user_id, (hour_bucket, 0))
    if bucket != hour_bucket:
        count = 0
        bucket = hour_bucket
    _user_hourly[user_id] = (bucket, count + 1)


# ──────────────────────────────────────────────────────────────────
# 获取所有活跃用户
# ──────────────────────────────────────────────────────────────────

def _get_all_user_ids() -> list:
    """
    查询 device_tokens 表中所有活跃设备对应的唯一 user_id 列表。
    """
    from database import get_db
    try:
        resp = (
            get_db()
            .table("device_tokens")
            .select("user_id")
            .eq("is_active", True)
            .execute()
        )
        rows = resp.data or []
        # 去重
        seen = set()
        result = []
        for r in rows:
            uid = r.get("user_id")
            if uid and uid not in seen:
                seen.add(uid)
                result.append(uid)
        return result
    except Exception as e:
        log.error("获取活跃用户列表失败: %s", e)
        return []


# ──────────────────────────────────────────────────────────────────
# 核心发送函数
# ──────────────────────────────────────────────────────────────────

async def broadcast_push(
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
) -> int:
    """
    向所有注册了设备令牌的用户广播推送通知（带限流）。

    Args:
        title: 通知标题
        body:  通知正文
        data:  附加数据（键值均为 str）

    Returns:
        实际发送成功的用户数
    """
    # 延迟导入，避免循环依赖
    from agent.push_service import send_push

    user_ids = await asyncio.to_thread(_get_all_user_ids)
    if not user_ids:
        log.debug("broadcast_push: 无活跃用户，跳过")
        return 0

    sent_users = 0
    for uid in user_ids:
        if not _check_rate_limit(uid):
            continue
        try:
            cnt = await send_push(uid, title, body, data)
            if cnt > 0:
                _incr_counters(uid)
                sent_users += 1
        except Exception as e:
            log.error("broadcast_push 发送用户 %s 失败: %s", uid, e)

    if sent_users > 0:
        log.info("broadcast_push 完成: title=%r, 成功 %d 用户", title, sent_users)
    return sent_users


# ──────────────────────────────────────────────────────────────────
# 业务推送快捷函数
# ──────────────────────────────────────────────────────────────────

async def push_high_score(
    mint: str,
    symbol: str,
    score: float,
    bc_progress: float,
) -> int:
    """
    高分新币推送

    触发条件：新代币首次打分 score >= 70
    """
    title = "🚀 高分新币"
    body = f"{symbol}  BC={bc_progress:.0f}%  Score={score:.0f}"
    data = {
        "mint": mint,
        "type": "high_score",
        "symbol": symbol,
        "score": str(score),
        "bc_progress": str(bc_progress),
    }
    log.info("push_high_score: %s score=%.0f bc=%.0f%%", symbol, score, bc_progress)
    return await broadcast_push(title, body, data)


async def push_bc_milestone(
    mint: str,
    symbol: str,
    milestone: int,
    bc_progress: float,
) -> int:
    """
    BC 里程碑推送

    触发条件：BC 首次跨过 30% 或 60%
    """
    title = f"📈 BC 里程碑 {milestone}%"
    body = f"{symbol}  BC 已达 {bc_progress:.0f}%"
    data = {
        "mint": mint,
        "type": "bc_milestone",
        "symbol": symbol,
        "milestone": str(milestone),
        "bc_progress": str(bc_progress),
    }
    log.info("push_bc_milestone: %s milestone=%d%%", symbol, milestone)
    return await broadcast_push(title, body, data)


async def push_smart_money(
    mint: str,
    symbol: str,
    wallet_tier: str,
    net_sol: float,
    bc_progress: float,
) -> int:
    """
    聪明钱入场推送

    触发条件：聪明钱买入且 net_sol >= 1.0
    """
    title = "🧠 聪明钱入场"
    tier_label = {"elite": "精英", "verified": "验证", "watching": "观察"}.get(
        wallet_tier, wallet_tier
    )
    body = f"{symbol}  [{tier_label}] 净买入 {net_sol:.2f} SOL  BC={bc_progress:.0f}%"
    data = {
        "mint": mint,
        "type": "smart_money",
        "symbol": symbol,
        "wallet_tier": wallet_tier,
        "net_sol": str(net_sol),
        "bc_progress": str(bc_progress),
    }
    log.info("push_smart_money: %s tier=%s net_sol=%.2f", symbol, wallet_tier, net_sol)
    return await broadcast_push(title, body, data)


async def push_graduated(
    mint: str,
    symbol: str,
) -> int:
    """
    代币毕业推送

    触发条件：代币 BC 进度达到 100%，完成毕业
    """
    title = "🎓 代币毕业"
    body = f"{symbol} 已从 pump.fun 毕业，上线 Raydium"
    data = {
        "mint": mint,
        "type": "graduated",
        "symbol": symbol,
    }
    log.info("push_graduated: %s", symbol)
    return await broadcast_push(title, body, data)
