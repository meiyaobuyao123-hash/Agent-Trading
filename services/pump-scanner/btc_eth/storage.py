"""BTC/ETH 模块 DB 操作"""
import logging
from typing import Dict, Any, List, Optional

from database import get_db

log = logging.getLogger(__name__)


def save_indicators(asset: str, snapshot: Dict[str, Any]) -> None:
    """写入指标快照到 btc_eth_indicators"""
    try:
        # 过滤内部字段（以 _ 开头）
        row = {k: v for k, v in snapshot.items() if not k.startswith("_")}
        row["asset"] = asset
        get_db().table("btc_eth_indicators").insert(row).execute()
    except Exception as e:
        log.error("[BTC/ETH Storage] save_indicators: %s", e)


def save_report(report: Dict[str, Any]) -> None:
    """写入周期报告"""
    try:
        get_db().table("btc_eth_reports").upsert(
            report, on_conflict="asset,report_date"
        ).execute()
    except Exception as e:
        log.error("[BTC/ETH Storage] save_report: %s", e)


def save_signal(signal: Dict[str, Any]) -> str:
    """写入交易信号，返回 signal ID"""
    try:
        res = get_db().table("btc_eth_signals").insert(signal).execute()
        if res.data:
            return res.data[0].get("id", "")
    except Exception as e:
        log.error("[BTC/ETH Storage] save_signal: %s", e)
    return ""


def update_signal(signal_id: str, updates: Dict[str, Any]) -> None:
    """更新信号状态（追踪价格/关闭）"""
    try:
        get_db().table("btc_eth_signals").update(updates).eq("id", signal_id).execute()
    except Exception as e:
        log.error("[BTC/ETH Storage] update_signal: %s", e)


def get_active_signals(asset: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取活跃信号"""
    try:
        q = get_db().table("btc_eth_signals").select("*").eq("status", "active")
        if asset:
            q = q.eq("asset", asset)
        res = q.order("created_at", desc=True).limit(50).execute()
        return res.data or []
    except Exception as e:
        log.error("[BTC/ETH Storage] get_active_signals: %s", e)
        return []


def save_alert(alert: Dict[str, Any]) -> None:
    """写入风险预警"""
    try:
        get_db().table("btc_eth_alerts").insert(alert).execute()
    except Exception as e:
        log.error("[BTC/ETH Storage] save_alert: %s", e)


def get_latest_report(asset: str) -> Optional[Dict[str, Any]]:
    """获取最新报告"""
    try:
        res = (get_db().table("btc_eth_reports")
               .select("*").eq("asset", asset)
               .order("report_date", desc=True).limit(1).execute())
        return res.data[0] if res.data else None
    except Exception as e:
        log.error("[BTC/ETH Storage] get_latest_report: %s", e)
        return None


def get_portfolio(user_id: str) -> Optional[Dict[str, Any]]:
    """获取用户模拟盘组合"""
    try:
        res = (get_db().table("btc_eth_portfolios")
               .select("*").eq("user_id", user_id).limit(1).execute())
        return res.data[0] if res.data else None
    except Exception as e:
        log.error("[BTC/ETH Storage] get_portfolio: %s", e)
        return None


def upsert_portfolio(portfolio: Dict[str, Any]) -> None:
    """创建/更新模拟盘组合"""
    try:
        get_db().table("btc_eth_portfolios").upsert(
            portfolio, on_conflict="user_id"
        ).execute()
    except Exception as e:
        log.error("[BTC/ETH Storage] upsert_portfolio: %s", e)


def save_paper_trade(trade: Dict[str, Any]) -> None:
    """保存模拟交易"""
    try:
        get_db().table("btc_eth_paper_trades").insert(trade).execute()
    except Exception as e:
        log.error("[BTC/ETH Storage] save_paper_trade: %s", e)
