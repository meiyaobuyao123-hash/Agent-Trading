"""
Helius Webhook 接收端点 — SOL 聪明钱全量追踪

Helius 注册 webhook 后，任何被监听地址的交易都会 POST 到此端点。
支持 100,000+ 地址，延迟 <1s。
"""

import logging
from typing import List, Dict, Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook", tags=["webhook"])

# 全局回调：由 smart_money_tracker 注册
_on_sol_txs_callback = None


def set_sol_webhook_callback(callback):
    """smart_money_tracker 注册回调函数"""
    global _on_sol_txs_callback
    _on_sol_txs_callback = callback
    logger.info("[Webhook] SOL callback registered")


@router.post("/helius")
async def helius_webhook(request: Request):
    """接收 Helius webhook 推送的 SOL 交易"""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)

    # Helius webhook 推送格式: 直接是交易列表 [tx1, tx2, ...]
    txs = payload if isinstance(payload, list) else [payload]

    if _on_sol_txs_callback and txs:
        try:
            await _on_sol_txs_callback(txs)
        except Exception as e:
            logger.warning("[Webhook] callback error: %s", e)

    return JSONResponse({"ok": True})
