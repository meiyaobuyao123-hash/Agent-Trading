"""
独立 FastAPI 服务入口 — 跟 main.py 的 scanner 完全脱钩
引用 docs/memory/pitfalls.md "pump-scanner systemd 重启 8000 不 LISTEN"

为什么:
  main.py 启动时同时跑 scanner.run + uvicorn task,SmartMoneyTracker 的
  WebSocket 重连 + Helius/EVM 大量 fd + EventBus 等持续抢占 event loop,
  导致 systemctl restart 时 uvicorn task 被 starve,8000 不 LISTEN。

  独立 process 跑 uvicorn → 不跟 scanner 抢 event loop,
  systemctl restart 各自独立,互不影响。

启动:
  ENABLE_API=false python main.py        # scanner 进程,不再启 FastAPI
  python api_server.py                    # 独立 FastAPI 进程,只跑 uvicorn

systemd:
  pump-scanner.service        ExecStart=python main.py     Environment=ENABLE_API=false
  pump-scanner-api.service    ExecStart=python api_server.py
"""
import logging
import os
import sys

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def main():
    port = int(os.getenv("API_PORT", "8000"))
    host = os.getenv("API_HOST", "0.0.0.0")
    log.info(f"独立 API server starting on {host}:{port}")
    log.info("(脱钩自 pump-scanner main.py;FastAPI 跑独立 event loop)")
    uvicorn.run(
        "api.app:app",
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        workers=1,
    )


if __name__ == "__main__":
    main()
