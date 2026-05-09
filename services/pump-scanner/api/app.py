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
from api.routes_auth import router as auth_router          # R46 邮箱/Google 登录
from api.routes_credit import router as credit_router      # R47 算力体系

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
# R47 P4 加固:
#   - 默认开(production 安全默认)
#   - 仅 ENVIRONMENT=development AND DISABLE_GEO_BLOCK=true 才 disable
#   - 单独配 DISABLE_GEO_BLOCK=true 在 production 无效(防误配)
import os as _os_geo
import logging as _log_geo

_env_geo = _os_geo.getenv("ENVIRONMENT", "production").lower()
_disable_geo = _os_geo.getenv("DISABLE_GEO_BLOCK", "").lower() in ("true", "1", "yes")

if _env_geo == "development" and _disable_geo:
    _log_geo.getLogger(__name__).warning(
        "[geo] GeoBlockMiddleware DISABLED (ENVIRONMENT=development + DISABLE_GEO_BLOCK=true)"
    )
else:
    app.add_middleware(GeoBlockMiddleware)
    if _disable_geo:
        # production 配了 DISABLE_GEO_BLOCK=true 但 ENVIRONMENT 不是 development → 忽略
        _log_geo.getLogger(__name__).warning(
            "[geo] DISABLE_GEO_BLOCK=true 在 production 无效;GeoBlockMiddleware 强制启用"
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
app.include_router(auth_router)    # R46 邮箱/Google 登录
app.include_router(credit_router)  # R47 算力体系


# ── 启动时拉起 Binance majors WS(BTC/ETH/SOL/BNB 实时价格) ────
# pump-scanner-api 跟 pump-scanner main 是两个进程,各自维护自己的
# PriceFeed 实例;为了让 /api/price/majors 有真数据,API 这边自己起一条
# Binance bookTicker 长连接(只跑 _run_binance_loop,不要 Helius/EVM)。
@app.on_event("startup")
async def _start_binance_majors_loop():
    import asyncio
    try:
        from price_feed import price_feed
        asyncio.create_task(price_feed._run_binance_loop())
        log.info("[api] Binance majors WS loop started (BTC/ETH/SOL/BNB)")
    except Exception as e:
        log.error(f"[api] failed to start binance majors loop: {e}")


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
