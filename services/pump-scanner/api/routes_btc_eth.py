"""BTC/ETH 投资 Agent API 端点"""
import logging
from typing import Optional

from fastapi import APIRouter, Query

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/btc-eth", tags=["btc-eth"])

# 全局 manager 引用（main.py 启动后设置）
_manager = None


def set_manager(mgr) -> None:
    global _manager
    _manager = mgr


@router.get("/health")
async def health():
    """模块健康状态"""
    if not _manager:
        return {"status": "not_started"}
    return _manager.get_health()


@router.get("/indicators/{asset}")
async def get_indicators(asset: str):
    """获取最新 50 项指标"""
    if not _manager:
        return {"error": "module not started"}
    asset = asset.upper()
    if asset not in ("BTC", "ETH"):
        return {"error": "asset must be BTC or ETH"}
    return _manager.get_snapshot(asset)


@router.get("/dashboard")
async def get_dashboard():
    """聚合仪表盘"""
    if not _manager:
        return {"error": "module not started"}
    btc = _manager.get_snapshot("BTC")
    eth = _manager.get_snapshot("ETH")
    return {
        "btc": {
            "price": btc.get("price_usd", 0),
            "change_24h": btc.get("price_change_24h", 0),
            "rsi": btc.get("rsi_14"),
            "fear_greed": btc.get("fear_greed_index"),
            "funding_rate": btc.get("funding_rate"),
            "scores": _manager._indicator_engine.get_composite_scores("BTC"),
        },
        "eth": {
            "price": eth.get("price_usd", 0),
            "change_24h": eth.get("price_change_24h", 0),
            "rsi": eth.get("rsi_14"),
            "scores": _manager._indicator_engine.get_composite_scores("ETH"),
        },
    }


@router.get("/signals")
async def get_signals(
    asset: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
):
    """获取交易信号"""
    from btc_eth.storage import get_active_signals
    signals = get_active_signals(asset.upper() if asset else None)
    return {"signals": signals[:limit], "count": len(signals)}


@router.get("/alerts")
async def get_alerts(severity: Optional[str] = Query(None)):
    """获取风险预警"""
    from database import get_db
    try:
        q = get_db().table("btc_eth_alerts").select("*").eq("is_active", True)
        if severity:
            q = q.eq("severity", severity)
        res = q.order("created_at", desc=True).limit(20).execute()
        return {"alerts": res.data or []}
    except Exception as e:
        return {"alerts": [], "error": str(e)}


@router.get("/reports/{asset}/latest")
async def get_latest_report(asset: str):
    """获取最新周期报告"""
    from btc_eth.storage import get_latest_report
    report = get_latest_report(asset.upper())
    if report:
        return report
    return {"error": "no report found"}
