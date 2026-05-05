"""
R42 P1 — 钱包私钥管理 API (AES-256-GCM 加密存 DB)

设计:
- 用户在 Flutter 一次性导入私钥 → 后端用 master_key 加密 → 存 user_wallets 表
- 私钥永远不返给 Flutter(只返 public_key + label + 元数据)
- trade_executor 拉时调 crypto_box.decrypt_private_key,签名后立刻丢

Endpoints:
- POST   /api/wallet/import         导入新钱包(私钥加密 + 存)
- GET    /api/wallet/list           列出用户钱包(不含私钥)
- DELETE /api/wallet/{id}           删除钱包
- PATCH  /api/wallet/{id}/default   设为默认
- GET    /api/wallet/master-status  master_key 是否就绪(admin 排查用)

Python 3.9 兼容。
"""
from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


# ── 请求/响应模型 ────────────────────────────────────────

class ImportWalletRequest(BaseModel):
    chain: str = Field(..., description="solana / ethereum / bsc / base / arbitrum / polygon / optimism")
    public_key: str = Field(..., min_length=20, max_length=128, description="钱包地址(可公开)")
    private_key: str = Field(..., min_length=32, description="私钥明文(base58/hex);后端加密后丢弃")
    label: Optional[str] = Field(None, max_length=64, description="自起名字 '我的主钱包'")
    set_default: bool = Field(False, description="导入后设为默认")


class WalletInfo(BaseModel):
    """返给前端的钱包信息(永不含私钥)"""
    id: int
    chain: str
    public_key: str
    label: Optional[str] = None
    is_default: bool
    is_active: bool
    created_at: str
    last_used_at: Optional[str] = None


# ── helper:验证 chain + public_key 格式 ──────────────────

_VALID_CHAINS = {"solana", "ethereum", "bsc", "base", "arbitrum", "polygon", "optimism"}


def _validate_public_key(chain: str, public_key: str) -> None:
    """简易格式校验 — Solana base58 / EVM 0x...40 hex"""
    pk = public_key.strip()
    if chain == "solana":
        # base58, 通常 32-44 字符
        if not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", pk):
            raise HTTPException(400, f"Solana 地址格式错: {pk[:10]}...")
    else:
        # EVM: 0x + 40 hex
        if not re.match(r"^0x[0-9a-fA-F]{40}$", pk):
            raise HTTPException(400, f"EVM 地址格式错: {pk[:10]}...")


def _get_local_db_conn():
    """返本地 PG conn(失败抛 503)"""
    try:
        from local_db import _get_conn
        return _get_conn()
    except ImportError as e:
        raise HTTPException(503, f"本地 DB 不可用: {e}")
    except Exception as e:
        raise HTTPException(503, f"本地 DB 连接失败: {e}")


# ── Endpoints ────────────────────────────────────────────

@router.get("/master-status")
async def master_status(user_id: str = Depends(get_current_user)):
    """检查 master_key 是否就绪(用户首次导入前 Flutter 调一下)"""
    from agent.crypto_box import is_master_key_configured
    return {"ready": is_master_key_configured()}


@router.post("/import", status_code=201)
async def import_wallet(
    req: ImportWalletRequest,
    user_id: str = Depends(get_current_user),
):
    """R42 P1 导入新钱包 — 私钥用 master_key 加密后存 user_wallets。

    返:WalletInfo(永不含私钥)。
    """
    if req.chain not in _VALID_CHAINS:
        raise HTTPException(400, f"不支持的链: {req.chain}")
    _validate_public_key(req.chain, req.public_key)

    # 加密私钥(可能因 master_key 缺失抛)
    from agent.crypto_box import encrypt_private_key
    try:
        enc_blob = encrypt_private_key(req.private_key.strip())
    except RuntimeError as e:
        raise HTTPException(503, f"加密失败: {e}")
    except Exception as e:
        raise HTTPException(500, f"加密内部错: {str(e)[:200]}")

    conn = _get_local_db_conn()
    try:
        with conn.cursor() as cur:
            # 如果 set_default,先把同链其他钱包 default 取消
            if req.set_default:
                cur.execute(
                    "UPDATE user_wallets SET is_default = FALSE "
                    "WHERE user_id = %s AND chain = %s",
                    (user_id, req.chain),
                )
            # 插入(冲突时 update is_active=true 等)
            cur.execute(
                """
                INSERT INTO user_wallets
                  (user_id, chain, public_key, encrypted_private_key, label, is_default, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (user_id, chain, public_key) DO UPDATE SET
                  encrypted_private_key = EXCLUDED.encrypted_private_key,
                  label                 = COALESCE(EXCLUDED.label, user_wallets.label),
                  is_default            = EXCLUDED.is_default OR user_wallets.is_default,
                  is_active             = TRUE
                RETURNING id, chain, public_key, label, is_default, is_active,
                          created_at, last_used_at
                """,
                (user_id, req.chain, req.public_key.strip(),
                 enc_blob, req.label, req.set_default),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception as e:
        log.error("[wallet/import] DB error: %s", e)
        raise HTTPException(500, f"DB 写入失败: {str(e)[:200]}")

    return _row_to_info(row)


@router.get("/list", response_model=List[WalletInfo])
async def list_wallets(user_id: str = Depends(get_current_user)):
    """列出当前用户的活跃钱包(不含私钥)。"""
    conn = _get_local_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, chain, public_key, label, is_default, is_active,
                       created_at, last_used_at
                FROM user_wallets
                WHERE user_id = %s AND is_active = TRUE
                ORDER BY is_default DESC, created_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall() or []
    except Exception as e:
        log.warning("[wallet/list] DB error: %s", e)
        return []

    return [_row_to_info(r) for r in rows]


@router.delete("/{wallet_id}")
async def delete_wallet(
    wallet_id: int,
    user_id: str = Depends(get_current_user),
):
    """逻辑删除钱包(is_active=false,数据保留以便审计)"""
    conn = _get_local_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE user_wallets SET is_active = FALSE "
                "WHERE id = %s AND user_id = %s "
                "RETURNING id",
                (wallet_id, user_id),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception as e:
        log.error("[wallet/delete] DB error: %s", e)
        raise HTTPException(500, f"DB 错: {str(e)[:200]}")

    if not row:
        raise HTTPException(404, "钱包不存在或不属于你")
    return {"success": True, "id": wallet_id}


@router.patch("/{wallet_id}/default")
async def set_default(
    wallet_id: int,
    user_id: str = Depends(get_current_user),
):
    """设为该链默认钱包(同链其他自动取消 default)"""
    conn = _get_local_db_conn()
    try:
        with conn.cursor() as cur:
            # 先查目标钱包是否属于 user
            cur.execute(
                "SELECT chain FROM user_wallets "
                "WHERE id = %s AND user_id = %s AND is_active = TRUE",
                (wallet_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "钱包不存在")
            chain = row[0]
            # 取消同链其他默认
            cur.execute(
                "UPDATE user_wallets SET is_default = FALSE "
                "WHERE user_id = %s AND chain = %s AND id != %s",
                (user_id, chain, wallet_id),
            )
            # 设置目标为默认
            cur.execute(
                "UPDATE user_wallets SET is_default = TRUE WHERE id = %s",
                (wallet_id,),
            )
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("[wallet/default] DB error: %s", e)
        raise HTTPException(500, f"DB 错: {str(e)[:200]}")

    return {"success": True, "id": wallet_id}


# ── helper:row → WalletInfo dict ────────────────────────

def _row_to_info(row) -> Dict[str, Any]:
    """psycopg2 row(tuple) → WalletInfo dict(永不含私钥)"""
    return {
        "id": row[0],
        "chain": row[1],
        "public_key": row[2],
        "label": row[3],
        "is_default": row[4],
        "is_active": row[5],
        "created_at": row[6].isoformat() if row[6] else "",
        "last_used_at": row[7].isoformat() if row[7] else None,
    }


# ── 内部函数:trade_executor 用 — 拉解密后的私钥 ────────

def get_decrypted_wallet(
    user_id: str,
    chain: str,
    wallet_id: Optional[int] = None,
) -> Optional[Dict[str, str]]:
    """trade_executor 调:返 {public_key, private_key}(解密后)。
    wallet_id 不传则用 default。
    任何错误返 None。
    """
    try:
        from local_db import _get_conn
        conn = _get_conn()
    except Exception as e:
        log.warning("[wallet] get_decrypted DB unavailable: %s", e)
        return None

    try:
        with conn.cursor() as cur:
            if wallet_id is not None:
                cur.execute(
                    "SELECT public_key, encrypted_private_key FROM user_wallets "
                    "WHERE id = %s AND user_id = %s AND chain = %s AND is_active = TRUE",
                    (wallet_id, user_id, chain),
                )
            else:
                # 默认 wallet
                cur.execute(
                    "SELECT public_key, encrypted_private_key FROM user_wallets "
                    "WHERE user_id = %s AND chain = %s AND is_active = TRUE "
                    "ORDER BY is_default DESC, created_at DESC LIMIT 1",
                    (user_id, chain),
                )
            row = cur.fetchone()
            if not row:
                return None
            public_key, enc_blob = row[0], row[1]

            # 更新 last_used_at(失败不影响)
            try:
                cur.execute(
                    "UPDATE user_wallets SET last_used_at = now() "
                    "WHERE user_id = %s AND chain = %s AND public_key = %s",
                    (user_id, chain, public_key),
                )
                conn.commit()
            except Exception:
                pass
    except Exception as e:
        log.warning("[wallet] get_decrypted DB error: %s", e)
        return None

    try:
        from agent.crypto_box import decrypt_private_key
        private_key = decrypt_private_key(enc_blob)
    except Exception as e:
        log.error("[wallet] decrypt FAILED user=%s chain=%s: %s", user_id, chain, e)
        return None

    return {"public_key": public_key, "private_key": private_key}
