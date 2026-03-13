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
from routes_smart_money import router as smart_money_router

log = logging.getLogger(__name__)

# FastAPI 实例
app = FastAPI(
    title="Agent Trading API",
    description="交易策略管理和告警系统 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
app.include_router(smart_money_router)


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
