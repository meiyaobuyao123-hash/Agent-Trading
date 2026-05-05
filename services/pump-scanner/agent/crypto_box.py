"""
R42 P1 — 私钥加密保险箱(AES-256-GCM)

设计决策(2026-05-05 与用户对齐):
  - **WalletConnect 弃用**:每笔 user 签名跟全自动化冲突
  - **KMS 弃用**:收费 + 复杂度高,后端依然要持有 unwrapped key
  - **本方案**:AES-256-GCM 加密私钥 + master_key 单独管(env / 后续 KMS)
    - 加密:nonce(12B) + ciphertext + auth_tag(16B) 一起 base64 存 PG
    - 解密:master_key + 存的 blob → plain
    - master_key 来源:WALLET_MASTER_KEY env(32 字节 base64)
    - master_key 不在,模块仍可 import,加密/解密时返 error(不阻断启动)

API:
  encrypt_private_key(plain: str) -> str (base64 blob)
  decrypt_private_key(blob: str) -> str (plain)
  is_master_key_configured() -> bool

安全性:
  - 私钥永不落地文件系统(只在 PG 加密列里)
  - master_key 单独管(部署时 .env 或 systemd Environment=)
  - PG dump 单独泄漏 → 拿不出私钥(没 master_key)
  - master_key 单独泄漏 → 拿不出私钥(没 PG)
  - 同时拿到 → 私钥可解(同 KMS 用服务器身份调 API 一样)

Python 3.9 兼容。
"""
from __future__ import annotations
import base64
import logging
import os
import secrets
from typing import Optional

log = logging.getLogger(__name__)


# ── 配置 ──────────────────────────────────────────────────

_MASTER_KEY_ENV = "WALLET_MASTER_KEY"  # base64 编码的 32 字节 master key
_NONCE_LEN = 12  # AES-GCM 标准 nonce 长度
_KEY_LEN = 32    # 256 bits


# ── master_key 加载(惰性,失败不抛)─────────────────────

_cached_master: Optional[bytes] = None


def _get_master_key() -> Optional[bytes]:
    """惰性加载 master_key。无 env / 解码失败 → 返 None,caller 处理。"""
    global _cached_master
    if _cached_master is not None:
        return _cached_master
    raw = os.environ.get(_MASTER_KEY_ENV, "").strip()
    if not raw:
        return None
    try:
        decoded = base64.b64decode(raw)
        if len(decoded) != _KEY_LEN:
            log.warning("[crypto_box] %s len=%d 不是 %d 字节(base64 of 32 bytes)",
                        _MASTER_KEY_ENV, len(decoded), _KEY_LEN)
            return None
        _cached_master = decoded
        return decoded
    except Exception as e:
        log.warning("[crypto_box] %s decode 失败: %s", _MASTER_KEY_ENV, e)
        return None


def is_master_key_configured() -> bool:
    """检查 master_key 是否就绪 — admin endpoint / health check 用"""
    return _get_master_key() is not None


def _reset_cache_for_test() -> None:
    """测试用:清缓存让重读 env"""
    global _cached_master
    _cached_master = None


# ── 加密 / 解密 ────────────────────────────────────────────

def encrypt_private_key(plain: str) -> str:
    """加密私钥 → 返 base64 blob。

    blob 格式:base64(nonce(12B) + ciphertext + auth_tag(16B))
    任何错误 → 抛 RuntimeError(因为这是要存的关键步,不能静默)
    """
    if not plain:
        raise ValueError("空私钥")
    key = _get_master_key()
    if key is None:
        raise RuntimeError(
            f"{_MASTER_KEY_ENV} 未配置或格式错。"
            f"请运行 `python -c \"import secrets, base64; "
            f"print(base64.b64encode(secrets.token_bytes(32)).decode())\"` "
            f"生成,然后写入 .env"
        )
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as e:
        raise RuntimeError(f"cryptography 未装: {e}")

    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(_NONCE_LEN)
    plain_bytes = plain.encode("utf-8")
    # AESGCM.encrypt 返 ciphertext + auth_tag(自动拼接)
    ct = aesgcm.encrypt(nonce, plain_bytes, associated_data=None)
    blob = nonce + ct  # base64(nonce|ct|tag)
    return base64.b64encode(blob).decode("ascii")


def decrypt_private_key(blob: str) -> str:
    """解密 → 返明文私钥。

    任何错误 → 抛 RuntimeError(因为如果失败,trade 不能用错的 key 签名)
    """
    if not blob:
        raise ValueError("空 blob")
    key = _get_master_key()
    if key is None:
        raise RuntimeError(f"{_MASTER_KEY_ENV} 未配置")
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.exceptions import InvalidTag
    except ImportError as e:
        raise RuntimeError(f"cryptography 未装: {e}")

    try:
        raw = base64.b64decode(blob)
    except Exception as e:
        raise RuntimeError(f"blob base64 解码失败: {e}")
    if len(raw) < _NONCE_LEN + 16:
        raise RuntimeError(f"blob 长度异常: {len(raw)}")
    nonce, ct = raw[:_NONCE_LEN], raw[_NONCE_LEN:]

    aesgcm = AESGCM(key)
    try:
        plain_bytes = aesgcm.decrypt(nonce, ct, associated_data=None)
    except InvalidTag:
        # 篡改 / 用错 master_key
        raise RuntimeError("解密失败(auth tag 不匹配,可能 master_key 不对或 blob 被篡改)")
    return plain_bytes.decode("utf-8")


# ── 工具:生成 master_key(给运维用)─────────────────────

def generate_new_master_key_b64() -> str:
    """生成新 32 字节 master_key,返 base64。
    用法:
      python -c "from agent.crypto_box import generate_new_master_key_b64; print(generate_new_master_key_b64())"
    存到 .env:
      WALLET_MASTER_KEY=<output>
    """
    return base64.b64encode(secrets.token_bytes(_KEY_LEN)).decode("ascii")
