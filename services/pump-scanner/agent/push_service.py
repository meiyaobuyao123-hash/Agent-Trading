"""
FCM 推送通知服务

通过 Firebase Admin SDK 向用户设备发送推送通知。
需要 GOOGLE_APPLICATION_CREDENTIALS 环境变量指向服务账号 JSON 文件。

缺少 Firebase 配置时 graceful fallback（仅记录日志，不崩溃）。

Python 3.9 兼容。
"""
import asyncio
import logging
import os
from typing import Optional, Dict, List
from urllib.parse import quote

log = logging.getLogger(__name__)


# ── Deep link 构造器(W3 D5+) ────────────────────────────────
# Flutter 拿到推送 data["deep_link"] 后路由跳转

DEEP_LINK_SCHEME = "aitrading://"


def build_deep_link(category: str, **params) -> str:
    """构造深链 URL,Flutter 端解析跳转。

    支持 category:
      - strategy_triggered:  aitrading://strategy/{strategy_id}
      - hitl_approval:       aitrading://hitl/{approval_id}
      - review_ready:        aitrading://review/{period}
      - token_alert:         aitrading://token/{chain}/{address}
      - rule_proposal:       aitrading://memory/proposals/{proposal_id}
      - default:             aitrading://home

    参数缺失时返回 home(降级)。
    """
    def q(v):
        return quote(str(v), safe="")

    if category == "strategy_triggered":
        sid = params.get("strategy_id")
        return f"{DEEP_LINK_SCHEME}strategy/{q(sid)}" if sid else f"{DEEP_LINK_SCHEME}home"
    if category == "hitl_approval":
        aid = params.get("approval_id")
        return f"{DEEP_LINK_SCHEME}hitl/{q(aid)}" if aid else f"{DEEP_LINK_SCHEME}home"
    if category == "review_ready":
        period = params.get("period", "daily")
        return f"{DEEP_LINK_SCHEME}review/{q(period)}"
    if category == "token_alert":
        chain = params.get("chain")
        addr = params.get("address")
        if chain and addr:
            return f"{DEEP_LINK_SCHEME}token/{q(chain)}/{q(addr)}"
    if category == "rule_proposal":
        pid = params.get("proposal_id")
        return f"{DEEP_LINK_SCHEME}memory/proposals/{q(pid)}" if pid else f"{DEEP_LINK_SCHEME}memory"
    return f"{DEEP_LINK_SCHEME}home"

# Firebase Admin SDK 延迟初始化
_firebase_app = None
_init_attempted = False


def _init_firebase() -> bool:
    """
    延迟初始化 Firebase Admin SDK

    Returns:
        True if initialized (or already initialized), False otherwise
    """
    global _firebase_app, _init_attempted

    if _firebase_app is not None:
        return True

    # 只尝试一次，避免重复错误日志
    if _init_attempted:
        return False
    _init_attempted = True

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not cred_path:
            log.warning(
                "GOOGLE_APPLICATION_CREDENTIALS not set — "
                "push notifications disabled"
            )
            return False

        if not os.path.isfile(cred_path):
            log.warning(
                "Firebase credentials file not found: %s — "
                "push notifications disabled",
                cred_path,
            )
            return False

        cred = credentials.Certificate(cred_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        log.info("Firebase Admin SDK initialized successfully")
        return True

    except ImportError:
        log.warning(
            "firebase-admin package not installed — "
            "push notifications disabled"
        )
        return False
    except Exception as e:
        log.error("Firebase init failed: %s", e)
        return False


async def send_push(
    user_id: str,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
) -> int:
    """
    发送推送给用户所有活跃设备

    Args:
        user_id: 用户 UUID
        title:   通知标题
        body:    通知正文
        data:    附加数据（键值均为 str）

    Returns:
        成功发送的设备数
    """
    if not _init_firebase():
        log.debug("Push skipped: Firebase not initialized")
        return 0

    from firebase_admin import messaging
    from database import get_db

    # 查询用户活跃设备（使用 device_tokens 表，列名 platform）
    try:
        result = (
            get_db()
            .table("device_tokens")
            .select("id, token, platform")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .execute()
        )
        tokens = result.data or []
    except Exception as e:
        log.error("Failed to query device tokens for user %s: %s", user_id, e)
        return 0

    if not tokens:
        log.debug("No active devices for user %s", user_id)
        return 0

    sent = 0
    stale_ids = []  # type: List[str]

    for device in tokens:
        try:
            # 构造 FCM 消息
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=device["token"],
            )

            # Firebase Admin SDK send() 是同步的，放到线程池
            await asyncio.to_thread(messaging.send, message)
            sent += 1

        except messaging.UnregisteredError:
            # 令牌失效 → 标记不活跃
            log.info(
                "Token unregistered, marking inactive: device=%s",
                device["id"],
            )
            stale_ids.append(device["id"])

        except messaging.SenderIdMismatchError:
            log.warning(
                "Sender ID mismatch for device %s — marking inactive",
                device["id"],
            )
            stale_ids.append(device["id"])

        except Exception as e:
            log.error(
                "Push send failed for device %s: %s",
                device["id"],
                e,
            )

    # 批量标记失效令牌
    if stale_ids:
        try:
            for device_id in stale_ids:
                get_db().table("device_tokens").update(
                    {"is_active": False}
                ).eq("id", device_id).execute()
            log.info("Marked %d stale tokens inactive", len(stale_ids))
        except Exception as e:
            log.error("Failed to mark stale tokens: %s", e)

    log.info(
        "Push sent to user %s: %d/%d devices",
        user_id,
        sent,
        len(tokens),
    )
    return sent


async def send_push_batch(
    user_ids: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
) -> int:
    """
    批量推送给多个用户

    Returns:
        总成功发送数
    """
    total = 0
    for uid in user_ids:
        total += await send_push(uid, title, body, data)
    return total
