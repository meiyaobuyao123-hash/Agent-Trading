"""
R47 — Credit 算力 API endpoints

- GET    /api/credit/balance              当前用户余额
- POST   /api/credit/recharge-orders      创建充值订单
- GET    /api/credit/recharge-orders      列出用户充值订单
- GET    /api/credit/transactions         交易历史
- POST   /api/credit/admin/grant          (admin) 手动给用户加 credit(R47 第一版替代真 USDC 监听)
"""
from __future__ import annotations
import logging
import os
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user
from agent import credit_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/credit", tags=["credit"])

# admin 邮箱列表(env 配,逗号分隔);DEV mode 默认含 dev-user
ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]


# ── 请求/响应 ─────────────────────────────────────────────

class BalanceResponse(BaseModel):
    balance_usd: str
    total_recharged: str
    total_consumed: str
    has_account: bool
    estimated_messages_left: int


class RechargeOrderRequest(BaseModel):
    chain: str = Field(..., pattern="^(solana|base|bsc|ethereum)$")
    amount_usd: int = Field(..., ge=1, le=10000)


class RechargeOrderResponse(BaseModel):
    id: int
    chain: str
    address: str
    amount_exact: str
    amount_base: str
    amount_nonce: str
    expires_at: str
    created_at: Optional[str] = None
    status: str


class AdminGrantRequest(BaseModel):
    """Admin 手动给用户加 credit(R47 第一版,在 USDC 监听 cron 上线前临时方案)"""
    target_user_email: str
    amount_usd: float = Field(..., ge=0.01, le=10000)
    note: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────

@router.get("/balance", response_model=BalanceResponse)
async def get_balance(user_id: str = Depends(get_current_user)):
    info = credit_service.get_full_balance(user_id)
    bal = Decimal(info["balance_usd"])
    return BalanceResponse(
        balance_usd=info["balance_usd"],
        total_recharged=info["total_recharged"],
        total_consumed=info["total_consumed"],
        has_account=info["has_account"],
        estimated_messages_left=credit_service.estimate_remaining_messages(bal),
    )


@router.post("/recharge-orders", response_model=RechargeOrderResponse, status_code=201)
async def create_recharge(
    req: RechargeOrderRequest,
    user_id: str = Depends(get_current_user),
):
    """创建 USDC 充值订单。
    1. 后端生成 amount_exact = $X.XXXX(随机零头识别 tx)
    2. 返 receive_address + amount_exact + 30 min expires_at
    3. 用户从他自己钱包转 USDC(精确金额到 6 位小数)
    4. 后端 cron 监听到账 → confirmed + 加 balance
    """
    order = credit_service.create_recharge_order(user_id, req.chain, req.amount_usd)
    if not order:
        raise HTTPException(503, f"暂时不支持 {req.chain} 链充值,或服务器未配置收款地址")
    return RechargeOrderResponse(**order)


@router.get("/recharge-orders")
async def list_orders(
    limit: int = 20,
    user_id: str = Depends(get_current_user),
):
    return {"orders": credit_service.list_recharge_orders(user_id, limit=limit)}


@router.get("/transactions")
async def list_txs(
    limit: int = 50,
    user_id: str = Depends(get_current_user),
):
    return {"transactions": credit_service.list_transactions(user_id, limit=limit)}


@router.get("/estimate")
async def estimate_messages(
    amount_usd: float,
    model: Optional[str] = None,
):
    """R51 — Flutter 充值 sheet 用:估算充 X 美金能问多少次。
    自动扣 1% 手续费,再按 pricing.yaml 默认 3000 in / 500 out 算。
    无需登录(纯客户端展示用)。
    """
    if amount_usd <= 0 or amount_usd > 100000:
        raise HTTPException(400, "amount_usd 必须在 (0, 100000] 范围内")
    used_model = model or credit_service.DEFAULT_MODEL
    n = credit_service.estimate_messages_for_recharge(Decimal(str(amount_usd)), used_model)
    return {
        "amount_usd": amount_usd,
        "fee_rate": str(credit_service.RECHARGE_FEE_RATE),
        "amount_credited": str(Decimal(str(amount_usd)) * (Decimal("1") - credit_service.RECHARGE_FEE_RATE)),
        "model": used_model,
        "estimated_messages": n,
        "avg_in_tokens": credit_service.ESTIMATE_AVG_IN,
        "avg_out_tokens": credit_service.ESTIMATE_AVG_OUT,
    }


@router.post("/admin/grant", status_code=200)
async def admin_grant(
    req: AdminGrantRequest,
    user_id: str = Depends(get_current_user),
):
    """Admin 给用户手动加 credit(R47 第一版替代真 USDC 监听)。
    需调用方是 admin(.env ADMIN_EMAILS 列表 或 DEV user)。
    """
    # 鉴权:DEV user 自动允许;否则要看 user 邮箱在 ADMIN_EMAILS
    if user_id != "00000000-0000-0000-0000-000000000001":
        from local_db import _get_conn
        try:
            conn = _get_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT email FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                caller_email = (row[0] if row else "").lower()
        except Exception:
            caller_email = ""
        if caller_email not in ADMIN_EMAILS:
            raise HTTPException(403, f"非 admin(配 ADMIN_EMAILS env 加入)")

    # 找目标用户
    try:
        from local_db import _get_conn
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE email = %s",
                (req.target_user_email.lower(),),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, f"用户 {req.target_user_email} 不存在")
            target_id = str(row[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"查用户失败: {e}")

    new_balance = credit_service.add_credit(
        target_id,
        Decimal(str(req.amount_usd)),
        source_type="adjust",
        meta={"granted_by": user_id, "note": req.note or ""},
    )
    return {
        "success": True,
        "target_user_id": target_id,
        "amount_usd": str(req.amount_usd),
        "new_balance": str(new_balance),
    }
