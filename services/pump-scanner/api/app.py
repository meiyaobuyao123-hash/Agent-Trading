"""
FastAPI 应用入口

将 FastAPI 嵌入到现有的 pump-scanner 进程中，
与 APScheduler 共存。

启动方式 1（独立）：
    uvicorn api.app:app --host 0.0.0.0 --port 8000

启动方式 2（嵌入到 main.py）：
    from api.app import start_api_server
    await start_api_server(port=8000)

Python 3.9 兼容。
"""
import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes_agent import router as agent_router
from api.routes_price import router as price_router
from api.routes_risk import router as risk_router
from api.routes_device import router as device_router
from api.routes_pump import router as pump_router
from api.routes_optimizer import router as optimizer_router
from api.geo_middleware import GeoBlockMiddleware
from routes_smart_money import router as smart_money_router
from api.routes_webhook import router as webhook_router
from api.routes_token import router as token_router
from api.routes_btc_eth import router as btc_eth_router
from api.routes_data import router as data_router
from api.routes_backtest import router as backtest_router
from api.routes_hot import router as hot_router
from api.routes_thesis import router as thesis_router      # W3 D3
from api.routes_audit import router as audit_router        # W3 D3
from api.routes_admin import router as admin_router        # W3 D3
from api.routes_wallet import router as wallet_router      # R42 P1 私钥加密

log = logging.getLogger(__name__)

# FastAPI 实例
app = FastAPI(
    title="Agent Trading API",
    description="交易策略管理和告警系统 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── 地理位置屏蔽中间件（中国大陆 IP → HTTP 451）─────────────
# 注意：中间件按 add_middleware 的反序执行，GeoBlock 需在 CORS 之前注册
# 故此处先 add GeoBlock，再 add CORS
#
# R36 加 env 开关:DISABLE_GEO_BLOCK=true 时跳过(团队内测期用,生产期务必关)
import os as _os_geo
if _os_geo.getenv("DISABLE_GEO_BLOCK", "").lower() not in ("true", "1", "yes"):
    app.add_middleware(GeoBlockMiddleware)
else:
    import logging as _log_geo
    _log_geo.getLogger(__name__).warning(
        "[geo] GeoBlockMiddleware DISABLED via DISABLE_GEO_BLOCK env "
        "(内测期用,GA 前务必关 env 关回)"
    )

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:*",
        "http://127.0.0.1:*",
        "https://*.supabase.co",
        "*",  # 开发阶段允许所有来源
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(agent_router)
app.include_router(price_router)
app.include_router(risk_router)
app.include_router(device_router)
app.include_router(pump_router)
app.include_router(smart_money_router)
app.include_router(optimizer_router)
app.include_router(token_router)
app.include_router(webhook_router)
app.include_router(btc_eth_router)
app.include_router(data_router)
app.include_router(backtest_router)
app.include_router(hot_router)
# W3 D3 — Agent v1 新增 endpoints(默认 MOCK_MODE,真实施 W4-W12)
app.include_router(thesis_router)
app.include_router(audit_router)
app.include_router(admin_router)
app.include_router(wallet_router)  # R42 P1 钱包私钥加密管理


# ── 健康检查 ──────────────────────────────────────────────────

@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "agent-trading-api"}


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "Agent Trading API",
        "version": "1.0.0",
        "docs": "/docs",
    }


# ── 嵌入式启动 ───────────────────────────────────────────────

async def start_api_server(
    host: str = "0.0.0.0",
    port: int = 8000,
):
    """
    以嵌入方式启动 FastAPI（在现有 asyncio 事件循环中）

    用于集成到 main.py 的 APScheduler 进程
    """
    import uvicorn

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)
    log.info(f"Starting API server on {host}:{port}")
    await server.serve()
