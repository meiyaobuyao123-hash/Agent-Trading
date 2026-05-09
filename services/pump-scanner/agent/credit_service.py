"""
R47 — Credit 算力服务
R51 — 价目表抽到 pricing.yaml(单一来源 + verifier);1% 充值手续费

计费模型:
  cost_usd = (tokens_in × in_price + tokens_out × out_price) / 1M × MARKUP
  recharge_credited = amount_usd × (1 - RECHARGE_FEE_RATE)

价目表来源:agent/pricing.yaml(对照 Anthropic 公开 2026 May)
  - 改价跑:scripts/verify_pricing.py(对比 LiteLLM 社区源)
  - 单测:tests/test_pricing.py

API:
  get_balance(user_id) -> Decimal
  can_proceed(user_id, min_usd=0.0001) -> (bool, reason)
  deduct(user_id, model, tokens_in, tokens_out, request_id) -> Decimal new balance
  add_credit(user_id, amount_usd, source_type, ref) -> Decimal new balance
  list_transactions(user_id, limit=50) -> List[Dict]
  estimate_remaining_messages(balance, model='claude-sonnet-4-6') -> int

失败永不抛(返默认值或 False),让 chat 路径降级处理。

Python 3.9 兼容。
"""
from __future__ import annotations
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


# ── 价目表来自 pricing.yaml(单一来源,改价 → 改 yaml + 跑 verifier) ─

def _load_pricing_yaml() -> Dict[str, Any]:
    """启动时读 pricing.yaml,失败 fallback 到 hardcoded 默认(防 yaml 误删)。"""
    try:
        import yaml  # type: ignore
        p = Path(__file__).parent / "pricing.yaml"
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.error("[credit] failed to load pricing.yaml, using emergency fallback: %s", e)
        return {
            "markup": 1.0,
            "recharge_fee_rate": 0.01,
            "models": {
                "claude-sonnet-4-6":         {"in": 3.0, "out": 15.0},
                "claude-sonnet-4-20250514":  {"in": 3.0, "out": 15.0},
                "claude-haiku-4-5":          {"in": 0.25, "out": 1.25},
                "claude-opus-4-6":           {"in": 15.0, "out": 75.0},
            },
            "estimate_assumptions": {
                "default_model": "claude-sonnet-4-6",
                "avg_input_tokens": 3000,
                "avg_output_tokens": 500,
            },
        }


_PRICING = _load_pricing_yaml()

LLM_PRICES: Dict[str, Dict[str, float]] = _PRICING.get("models", {})
MARKUP: Decimal = Decimal(str(_PRICING.get("markup", 1.0)))
RECHARGE_FEE_RATE: Decimal = Decimal(str(_PRICING.get("recharge_fee_rate", 0.01)))

# 估算用默认 model(用户没指定时)
DEFAULT_MODEL: str = _PRICING.get("estimate_assumptions", {}).get("default_model", "claude-sonnet-4-6")
ESTIMATE_AVG_IN: int = _PRICING.get("estimate_assumptions", {}).get("avg_input_tokens", 3000)
ESTIMATE_AVG_OUT: int = _PRICING.get("estimate_assumptions", {}).get("avg_output_tokens", 500)

# 最小余额门槛 — 低于这个值拒新请求(避免负余额,留 buffer 给当前请求扣费)
MIN_BALANCE_USD = Decimal("0.0001")


def calc_cost(model: str, tokens_in: int, tokens_out: int) -> Decimal:
    """计算一次 LLM 调用的成本(USD)。

    返 Decimal(精确到 8 位小数)。
    """
    p = LLM_PRICES.get(model)
    if not p:
        # 未知 model 用 Sonnet 价(保守)
        log.warning("[credit] unknown model %s, using sonnet price", model)
        p = LLM_PRICES["claude-sonnet-4-6"]
    raw = (Decimal(tokens_in) * Decimal(p["in"]) + Decimal(tokens_out) * Decimal(p["out"]))
    cost = raw / Decimal(1_000_000) * MARKUP
    return cost.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


# ── DB helpers(本地 PG)──────────────────────────────────

def _get_conn():
    """返本地 PG conn;失败抛(让 caller 降级)。"""
    from local_db import _get_conn as _gc
    return _gc()


def _ensure_user_credit_row(cur, user_id: str) -> None:
    """如果 user_credits 没行就 insert 一个 default row(并发安全用 ON CONFLICT)。"""
    cur.execute(
        """
        INSERT INTO user_credits (user_id, balance_usd, total_recharged, total_consumed)
        VALUES (%s, 0, 0, 0)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id,),
    )


# ── 公共 API ──────────────────────────────────────────────

def get_balance(user_id: str) -> Decimal:
    """返用户当前余额。无记录返 0(默认无配额)。失败返 0(降级)。"""
    if not user_id:
        return Decimal(0)
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT balance_usd FROM user_credits WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            return Decimal(str(row[0])) if row else Decimal(0)
    except Exception as e:
        log.warning("[credit] get_balance fail: %s", e)
        return Decimal(0)


def get_full_balance(user_id: str) -> Dict[str, Any]:
    """返用户余额详情:{balance, total_recharged, total_consumed, has_account}"""
    if not user_id:
        return {
            "balance_usd": "0",
            "total_recharged": "0",
            "total_consumed": "0",
            "has_account": False,
        }
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT balance_usd, total_recharged, total_consumed
                FROM user_credits
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if not row:
                return {
                    "balance_usd": "0",
                    "total_recharged": "0",
                    "total_consumed": "0",
                    "has_account": False,
                }
            return {
                "balance_usd": str(row[0]),
                "total_recharged": str(row[1]),
                "total_consumed": str(row[2]),
                "has_account": True,
            }
    except Exception as e:
        log.warning("[credit] get_full_balance fail: %s", e)
        return {
            "balance_usd": "0",
            "total_recharged": "0",
            "total_consumed": "0",
            "has_account": False,
        }


def can_proceed(user_id: str, min_usd: Decimal = MIN_BALANCE_USD) -> Tuple[bool, Optional[str]]:
    """检查用户是否能继续 chat。
    True / None = 通过;False / reason = 拒绝
    """
    # DEV mode 默认 user(00000000-...) 不收费(测试用)
    if user_id == "00000000-0000-0000-0000-000000000001":
        return True, None
    bal = get_balance(user_id)
    if bal < min_usd:
        return False, f"余额不足({bal} USD < ${min_usd})"
    return True, None


def deduct(
    user_id: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    request_id: Optional[str] = None,
) -> Decimal:
    """LLM 调用成功后扣费。
    返扣费后余额(Decimal)。失败返当前余额(降级,不抛)。

    并发安全:用 UPDATE ... RETURNING 原子操作。
    """
    if not user_id or user_id == "00000000-0000-0000-0000-000000000001":
        return Decimal(0)  # DEV bypass 不扣费

    cost = calc_cost(model, tokens_in, tokens_out)
    if cost <= 0:
        return get_balance(user_id)

    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            _ensure_user_credit_row(cur, user_id)
            # 原子扣费 + 累计 total_consumed
            cur.execute(
                """
                UPDATE user_credits
                   SET balance_usd     = balance_usd - %s,
                       total_consumed  = total_consumed + %s,
                       updated_at      = now()
                 WHERE user_id = %s
                RETURNING balance_usd
                """,
                (cost, cost, user_id),
            )
            row = cur.fetchone()
            new_balance = Decimal(str(row[0])) if row else Decimal(0)
            # 写交易流水
            cur.execute(
                """
                INSERT INTO credit_transactions
                  (user_id, type, amount_usd, balance_after, model, tokens_in, tokens_out, request_id)
                VALUES (%s, 'consume', %s, %s, %s, %s, %s, %s)
                """,
                (user_id, -cost, new_balance, model, tokens_in, tokens_out, request_id),
            )
        conn.commit()
        log.info(
            "[credit] deduct user=%s model=%s tokens=%d/%d cost=$%s balance=$%s",
            user_id[:8], model, tokens_in, tokens_out, cost, new_balance,
        )
        return new_balance
    except Exception as e:
        log.error("[credit] deduct fail: %s", e)
        return get_balance(user_id)


def add_credit(
    user_id: str,
    amount_usd: Decimal,
    source_type: str = "recharge",
    chain_tx_hash: Optional[str] = None,
    recharge_order_id: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Decimal:
    """加 credit(充值 / admin 调整 / refund)。
    source_type: 'recharge' / 'adjust' / 'refund'
    返新余额。失败返当前余额(降级)。
    """
    if not user_id or amount_usd <= 0:
        return get_balance(user_id)
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            _ensure_user_credit_row(cur, user_id)
            # 原子加 + 累计 total_recharged(只在 recharge 时累)
            if source_type == "recharge":
                cur.execute(
                    """
                    UPDATE user_credits
                       SET balance_usd     = balance_usd + %s,
                           total_recharged = total_recharged + %s,
                           updated_at      = now()
                     WHERE user_id = %s
                    RETURNING balance_usd
                    """,
                    (amount_usd, amount_usd, user_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE user_credits
                       SET balance_usd = balance_usd + %s,
                           updated_at  = now()
                     WHERE user_id = %s
                    RETURNING balance_usd
                    """,
                    (amount_usd, user_id),
                )
            row = cur.fetchone()
            new_balance = Decimal(str(row[0])) if row else Decimal(0)
            import json as _json
            cur.execute(
                """
                INSERT INTO credit_transactions
                  (user_id, type, amount_usd, balance_after, recharge_order_id, chain_tx_hash, meta)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    user_id, source_type, amount_usd, new_balance,
                    recharge_order_id, chain_tx_hash,
                    _json.dumps(meta or {}, ensure_ascii=False),
                ),
            )
        conn.commit()
        log.info(
            "[credit] add user=%s type=%s amount=$%s balance=$%s",
            user_id[:8], source_type, amount_usd, new_balance,
        )
        return new_balance
    except Exception as e:
        log.error("[credit] add_credit fail: %s", e)
        return get_balance(user_id)


def list_transactions(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """返用户交易历史(最新在前)。失败返空。"""
    if not user_id:
        return []
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, type, amount_usd, balance_after, model, tokens_in, tokens_out,
                       chain_tx_hash, ts
                FROM credit_transactions
                WHERE user_id = %s
                ORDER BY ts DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cur.fetchall() or []
        return [
            {
                "id": int(r[0]),
                "type": r[1],
                "amount_usd": str(r[2]),
                "balance_after": str(r[3]),
                "model": r[4],
                "tokens_in": r[5],
                "tokens_out": r[6],
                "chain_tx_hash": r[7],
                "ts": r[8].isoformat() if r[8] else None,
            }
            for r in rows
        ]
    except Exception as e:
        log.warning("[credit] list_transactions fail: %s", e)
        return []


# ── 充值订单 ──────────────────────────────────────────────

# 收款地址(R47 hot wallet)
DEFAULT_RECHARGE_ADDRESS = {
    "solana": "",  # GA 前必须配 .env RECHARGE_ADDRESS_SOLANA
    "base":   "",
}


def _gen_amount_with_nonce(amount_int: int) -> Tuple[Decimal, Decimal]:
    """生成"$X.XXXX"形的金额(用 4 位小数随机零头唯一识别 tx)。
    返 (amount_exact, nonce)。
    例:amount_int=10 → ($10.0034, $0.0034)
    """
    # 4 位小数随机:0001 - 9999(避开 0000 防混淆)
    nonce_int = secrets.randbelow(9999) + 1
    nonce = Decimal(nonce_int) / Decimal(10000)
    amount_exact = Decimal(amount_int) + nonce
    return amount_exact.quantize(Decimal("0.000001")), nonce.quantize(Decimal("0.000001"))


def create_recharge_order(
    user_id: str,
    chain: str,
    amount_usd_int: int,
    expires_minutes: int = 30,
) -> Optional[Dict[str, Any]]:
    """创建充值订单。返 dict 带 {id, address, amount_exact, expires_at}。
    地址不可用时返 None。"""
    if not user_id or amount_usd_int <= 0 or amount_usd_int > 10000:
        return None
    if chain not in ("solana", "base", "bsc", "ethereum"):
        return None

    import os as _os
    address = _os.getenv(f"RECHARGE_ADDRESS_{chain.upper()}", "")
    if not address:
        log.warning("[credit] RECHARGE_ADDRESS_%s 未配", chain.upper())
        return None

    amount_exact, nonce = _gen_amount_with_nonce(amount_usd_int)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)

    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            # 防 nonce 撞车:同一 chain pending 中不能有相同 amount_exact
            for _ in range(5):
                cur.execute(
                    """
                    SELECT 1 FROM recharge_orders
                    WHERE chain = %s AND status = 'pending' AND amount_usd = %s
                    """,
                    (chain, amount_exact),
                )
                if not cur.fetchone():
                    break
                amount_exact, nonce = _gen_amount_with_nonce(amount_usd_int)
            cur.execute(
                """
                INSERT INTO recharge_orders
                  (user_id, chain, receive_address, amount_usd, amount_base, amount_nonce, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (user_id, chain, address, amount_exact, Decimal(amount_usd_int), nonce, expires_at),
            )
            row = cur.fetchone()
        conn.commit()
        return {
            "id": int(row[0]),
            "chain": chain,
            "address": address,
            "amount_exact": str(amount_exact),
            "amount_base": str(amount_usd_int),
            "amount_nonce": str(nonce),
            "expires_at": expires_at.isoformat(),
            "created_at": row[1].isoformat() if row[1] else None,
            "status": "pending",
        }
    except Exception as e:
        log.error("[credit] create_recharge_order fail: %s", e)
        return None


def list_pending_orders_by_chain(chain: str) -> List[Dict[str, Any]]:
    """R47 P2 监听 cron 用:拉某链所有 status='pending' 且未过期的 orders。
    cron 拿到后从链上查 USDC 转账,匹配 amount_exact 命中 → 调 confirm_recharge_order。
    """
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, chain, receive_address, amount_usd, amount_base,
                       amount_nonce, created_at, expires_at
                FROM recharge_orders
                WHERE chain = %s AND status = 'pending' AND expires_at > now()
                ORDER BY created_at ASC
                """,
                (chain,),
            )
            rows = cur.fetchall() or []
        return [
            {
                "id": int(r[0]),
                "user_id": str(r[1]),
                "chain": r[2],
                "receive_address": r[3],
                "amount_usd": Decimal(str(r[4])),       # 精确金额(含 nonce)
                "amount_base": Decimal(str(r[5])),
                "amount_nonce": Decimal(str(r[6])),
                "created_at": r[7],
                "expires_at": r[8],
            }
            for r in rows
        ]
    except Exception as e:
        log.warning("[credit] list_pending_orders_by_chain(%s) fail: %s", chain, e)
        return []


def list_recharge_orders(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """返用户充值订单(最新在前)"""
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, chain, receive_address, amount_usd, amount_base, amount_nonce,
                       status, chain_tx_hash, created_at, confirmed_at, expires_at
                FROM recharge_orders
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cur.fetchall() or []
        return [
            {
                "id": int(r[0]),
                "chain": r[1],
                "address": r[2],
                "amount_exact": str(r[3]),
                "amount_base": str(r[4]),
                "amount_nonce": str(r[5]),
                "status": r[6],
                "chain_tx_hash": r[7],
                "created_at": r[8].isoformat() if r[8] else None,
                "confirmed_at": r[9].isoformat() if r[9] else None,
                "expires_at": r[10].isoformat() if r[10] else None,
            }
            for r in rows
        ]
    except Exception as e:
        log.warning("[credit] list_recharge_orders fail: %s", e)
        return []


def confirm_recharge_order(
    order_id: int,
    chain_tx_hash: str,
) -> Optional[Dict[str, Any]]:
    """cron 监听到 USDC 入账后调:把 order 标 confirmed + 加 user balance。
    返 {user_id, amount, new_balance}。失败返 None(订单已 confirmed/expired/不存在)。
    """
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE recharge_orders
                   SET status        = 'confirmed',
                       chain_tx_hash = %s,
                       confirmed_at  = now()
                 WHERE id = %s
                   AND status = 'pending'
                   AND expires_at > now()
                RETURNING user_id, amount_usd, amount_base
                """,
                (chain_tx_hash, order_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            user_id, amount_usd, amount_base = row
        conn.commit()

        # R51 — 平台 1% 充值手续费
        # 用户支付 amount_base (e.g. $100),平台扣 1% (= $1),实际到账 $99
        # nonce 零头(amount_usd - amount_base)始终免费(订单识别用)
        amount_base_dec = Decimal(str(amount_base))
        fee = (amount_base_dec * RECHARGE_FEE_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        amount_credited = amount_base_dec - fee

        new_balance = add_credit(
            str(user_id),
            amount_credited,
            source_type="recharge",
            chain_tx_hash=chain_tx_hash,
            recharge_order_id=order_id,
            meta={
                "received_amount": str(amount_usd),
                "fee_usd": str(fee),
                "fee_rate": str(RECHARGE_FEE_RATE),
            },
        )
        return {
            "user_id": str(user_id),
            "amount_received": str(amount_base),       # 用户实际付的(USDC 链上)
            "fee_charged": str(fee),                   # 平台 1% 手续费
            "amount_credited": str(amount_credited),   # 实际加到余额的
            "new_balance": str(new_balance),
        }
    except Exception as e:
        log.error("[credit] confirm_recharge_order fail: %s", e)
        return None


def expire_pending_orders() -> int:
    """cron 调:把超时未付款的 order 标 expired。返过期的 order 数量。"""
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE recharge_orders
                   SET status = 'expired'
                 WHERE status = 'pending' AND expires_at < now()
                """,
            )
            count = cur.rowcount
        conn.commit()
        if count > 0:
            log.info("[credit] expired %d recharge orders", count)
        return count
    except Exception as e:
        log.warning("[credit] expire_pending_orders fail: %s", e)
        return 0


def estimate_remaining_messages(balance: Decimal, model: str = DEFAULT_MODEL) -> int:
    """估算剩余余额能跑多少条平均长度的 chat(用于 UI 提示)。
    平均一条 chat:用 pricing.yaml 的 estimate_assumptions(默认 3000 in / 500 out)。
    """
    avg_cost = calc_cost(model, ESTIMATE_AVG_IN, ESTIMATE_AVG_OUT)
    if avg_cost <= 0:
        return 0
    return int(balance / avg_cost)


def estimate_messages_for_recharge(amount_usd: Decimal, model: str = DEFAULT_MODEL) -> int:
    """R51 — 给 Flutter 充值 sheet 用:充 X 美金能问多少次?
    扣完 1% 手续费后,按 pricing.yaml 的 estimate_assumptions 算。
    """
    credited = Decimal(str(amount_usd)) * (Decimal("1") - RECHARGE_FEE_RATE)
    return estimate_remaining_messages(credited, model)
