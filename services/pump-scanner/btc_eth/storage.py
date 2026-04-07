"""BTC/ETH 模块 DB 操作"""
import logging
from typing import Dict, Any, List, Optional

from database import get_db

log = logging.getLogger(__name__)


def save_indicators(asset: str, snapshot: Dict[str, Any]) -> None:
    """写入指标快照到 btc_eth_indicators（PRD-004 M-04 修复）"""
    # btc_eth_indicators 表的有效列
    VALID_COLS = {
        "asset", "price_usd", "price_change_1h", "price_change_4h", "price_change_24h",
        "volume_24h_usd", "funding_rate", "oi_usd", "oi_change_4h",
        "long_short_ratio", "retail_long_short", "taker_buy_sell_ratio",
        "liquidation_24h_usd", "liq_long_pct", "exchange_netflow_usd",
        "active_addresses", "hash_rate", "sopr", "whale_txn_count",
        "dxy_index", "sp500_change_pct", "gold_change_pct",
        "fear_greed_index", "social_volume", "news_sentiment",
        "etf_flow_usd", "stablecoin_mcap", "total_tvl_usd",
        "rsi_14", "macd_signal", "bb_position", "atr_14",
        "mempool_size_mb", "avg_fee_sat_vb",
        "bid_depth_2pct", "ask_depth_2pct", "depth_imbalance",
        "score_momentum", "score_sentiment", "score_onchain",
        "score_macro", "score_risk",
    }
    try:
        row = {k: v for k, v in snapshot.items() if k in VALID_COLS and v is not None}
        row["asset"] = asset
        if row.get("price_usd", 0) <= 0:
            return
        get_db().table("btc_eth_indicators").insert(row).execute()
        # 模拟盘价格更新
        try:
            from hot_sim_trader import get_sim_trader
            get_sim_trader().on_price_update(f"{asset.lower()}_spot", row.get("price_usd", 0))
        except Exception:
            pass
        log.info("[BTC/ETH Storage] indicators saved: %s $%.0f", asset, row.get("price_usd", 0))
    except Exception as e:
        log.error("[BTC/ETH Storage] save_indicators failed: %s (cols: %s)", e, list(row.keys())[:5])


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
