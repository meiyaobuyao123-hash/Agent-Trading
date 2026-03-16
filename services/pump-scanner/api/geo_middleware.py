"""
地理位置屏蔽中间件 — 拒绝中国大陆 IP 访问

使用 ip-api.com 免费接口（无需 API Key，45次/分钟限制）
查询结果本地缓存 24 小时，避免重复请求。

豁免：
  - /health — 健康检查
  - /          — 根路径
  - 127.0.0.1 / 10.x / 192.168.x — 私有/本地 IP
"""
import ipaddress
import logging
import time
from typing import Optional

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger(__name__)

# ── 内存缓存：{ip: (country_code, timestamp)} ───────────────
_ip_cache: dict = {}
_CACHE_TTL = 86400  # 24 小时

# ── 豁免路径（不做地理检查）───────────────────────────────
_EXEMPT_PATHS = {"/health", "/", "/docs", "/redoc", "/openapi.json"}

# ── 屏蔽国家代码 ──────────────────────────────────────────
_BLOCKED_COUNTRIES = {"CN"}


def _is_private_ip(ip: str) -> bool:
    """判断是否为私有/本地 IP，私有IP直接放行"""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return False


def _get_client_ip(request: Request) -> str:
    """从请求中提取真实客户端 IP（兼容 Nginx 反向代理）"""
    # X-Forwarded-For 头（Nginx 反代时）
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # 取第一个 IP（最左边为原始客户端）
        return forwarded_for.split(",")[0].strip()
    # X-Real-IP 头
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    # 直连
    if request.client:
        return request.client.host
    return "0.0.0.0"


async def _lookup_country(ip: str) -> Optional[str]:
    """查询 IP 所在国家，带本地缓存"""
    now = time.time()

    # 命中缓存
    if ip in _ip_cache:
        code, ts = _ip_cache[ip]
        if now - ts < _CACHE_TTL:
            return code

    # 调用 ip-api.com
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,countryCode"},
            )
            data = resp.json()
            if data.get("status") == "success":
                code = data.get("countryCode", "")
                _ip_cache[ip] = (code, now)
                return code
    except Exception as e:
        log.debug(f"IP lookup failed for {ip}: {e}")

    return None


class GeoBlockMiddleware(BaseHTTPMiddleware):
    """屏蔽中国大陆 IP 的 FastAPI 中间件"""

    async def dispatch(self, request: Request, call_next):
        # 豁免路径直接放行
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        ip = _get_client_ip(request)

        # 私有/本地 IP 直接放行（开发环境）
        if _is_private_ip(ip):
            return await call_next(request)

        # 查询地理位置
        country = await _lookup_country(ip)

        if country and country in _BLOCKED_COUNTRIES:
            log.info(f"GeoBlock: denied {ip} (country={country}) → {request.url.path}")
            return JSONResponse(
                status_code=451,  # HTTP 451 Unavailable For Legal Reasons
                content={
                    "error": "Service Unavailable For Legal Reasons",
                    "message": (
                        "本服务不向中华人民共和国大陆地区提供。\n"
                        "This service is not available in mainland China (PRC)."
                    ),
                    "code": "GEO_BLOCKED",
                },
                headers={"Retry-After": "0"},
            )

        return await call_next(request)
