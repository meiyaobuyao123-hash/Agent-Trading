"""
/api/thesis/* — Thesis 输出读取 + 触发请求
引用 docs/agent-pm/05-tool-catalog.md S08 thesis-writer
引用 docs/agent-pm/17-tech-plan.md Phase 2 + 3
引用 migration 039_agent_thesis.sql

接口清单:
  POST /api/thesis            触发新 thesis(level=auto|L1|L2|L3),返回 thesis_id
  GET  /api/thesis/{id}       查询 thesis 详情
  GET  /api/thesis            列出该 device 最近 N 条 thesis(可按 token 过滤)
  POST /api/thesis/{id}/feedback  用户标注 thesis 质量(helpful/neutral/misleading)

状态:🔴 v0.1 stub(W3-W6 实施)
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Literal
import os

router = APIRouter(prefix="/api/thesis", tags=["thesis"])

MOCK_MODE = os.environ.get("MOCK_MODE", "false").lower() == "true"


class ThesisRequest(BaseModel):
    chain: Literal["solana", "eth", "bsc", "base"]
    address: str = Field(min_length=1, max_length=64)
    level: Literal["auto", "L1", "L2", "L3"] = "auto"
    context: dict | None = None


class ThesisFeedback(BaseModel):
    feedback: Literal["helpful", "neutral", "misleading"]
    note: str | None = Field(default=None, max_length=500)


@router.post("")
async def request_thesis(req: ThesisRequest):
    """触发新 thesis 生成(同步,~5s for L2 / ~15s for L3)。

    W3 D5+ autonomous-loop 续 9:接通 thesis_loop。
    MOCK_MODE 仍返 fixture(给 Flutter 测试用)。
    """
    if MOCK_MODE:
        return _mock_thesis(req)

    try:
        from agent.loops.thesis_loop import get_thesis_loop
        loop = get_thesis_loop()
        # device_id 取默认 dev user(routes_thesis 当前不强制 auth)
        device_id = (req.context or {}).get("device_id") or "00000000-0000-0000-0000-000000000001"
        ctx = req.context or {}
        result = await loop.generate(
            device_id=device_id,
            chain=req.chain,
            token_address=req.address,
            token_symbol=ctx.get("token_symbol"),
            level=req.level,
            position_usd=ctx.get("position_usd"),
            score=ctx.get("score"),
            regime=ctx.get("regime"),
            extra_context={"token_data": ctx.get("token_data") or {},
                           "market_data": ctx.get("market_data") or {}},
        )
        # 拼出 Flutter Thesis schema 兼容的响应
        thesis = result.thesis
        return {
            "thesis_id": result.thesis_id or "",
            "chain": req.chain,
            "token_address": req.address,
            "token_symbol": ctx.get("token_symbol") or "",
            "level": result.level,
            "direction": thesis.get("direction"),
            "conviction": thesis.get("conviction"),
            "entry_zone": thesis.get("entry_zone"),
            "stop_loss": thesis.get("stop_loss"),
            "target_price": thesis.get("target") or thesis.get("target_price"),
            "risks": thesis.get("risks", []),
            "summary_30w": thesis.get("summary_30w", ""),
            "evidence": thesis.get("evidence", []),
            "similar_past_cases": thesis.get("similar_past_cases", []),
            "cost_usd": result.cost_usd,
            "latency_ms": result.latency_ms,
            "source": result.source,
            "error": result.error,
        }
    except Exception as e:
        # 失败不抛 500,降级到 mock(保 Flutter UI 不挂)
        import logging as _log
        _log.getLogger(__name__).warning("thesis_loop failed, fallback mock: %s", e)
        return _mock_thesis(req)


@router.get("/{thesis_id}")
async def get_thesis(thesis_id: str):
    if MOCK_MODE:
        return _mock_thesis_by_id(thesis_id)
    # 从本地 PG 拉
    try:
        from local_db import _get_conn
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT thesis_id, chain, token_address, token_symbol, level,
                       direction, conviction, entry_zone, stop_loss, target_price,
                       risks, summary_30w, evidence, similar_past_cases,
                       cost_usd, latency_ms, ts
                FROM agent_thesis WHERE thesis_id = %s
                """,
                (thesis_id,),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="thesis not found")
        return {
            "thesis_id": str(row[0]), "chain": row[1], "token_address": row[2],
            "token_symbol": row[3], "level": row[4],
            "direction": row[5], "conviction": float(row[6]),
            "entry_zone": row[7], "stop_loss": float(row[8]) if row[8] else None,
            "target_price": row[9],
            "risks": row[10] or [], "summary_30w": row[11],
            "evidence": row[12] or [], "similar_past_cases": row[13] or [],
            "cost_usd": float(row[14]) if row[14] else 0,
            "latency_ms": int(row[15]) if row[15] else 0,
            "ts": row[16].isoformat() if row[16] else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.get("")
async def list_thesis(token_address: str | None = None, limit: int = 20):
    if MOCK_MODE:
        return {"thesis": [], "total": 0}
    try:
        from local_db import _get_conn
        conn = _get_conn()
        with conn.cursor() as cur:
            if token_address:
                cur.execute(
                    """
                    SELECT thesis_id, chain, token_address, level, direction,
                           conviction, summary_30w, ts
                    FROM agent_thesis WHERE token_address = %s
                    ORDER BY ts DESC LIMIT %s
                    """,
                    (token_address, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT thesis_id, chain, token_address, level, direction,
                           conviction, summary_30w, ts
                    FROM agent_thesis ORDER BY ts DESC LIMIT %s
                    """,
                    (limit,),
                )
            rows = cur.fetchall()
        out = [
            {
                "thesis_id": str(r[0]), "chain": r[1], "token_address": r[2],
                "level": r[3], "direction": r[4], "conviction": float(r[5]),
                "summary_30w": r[6], "ts": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ]
        return {"thesis": out, "total": len(out)}
    except Exception as e:
        return {"thesis": [], "total": 0, "error": str(e)[:200]}


@router.post("/{thesis_id}/feedback")
async def feedback_thesis(thesis_id: str, fb: ThesisFeedback):
    if MOCK_MODE:
        return {"ok": True, "thesis_id": thesis_id}
    try:
        from local_db import _get_conn
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE agent_thesis SET user_feedback = %s WHERE thesis_id = %s",
                (fb.feedback, thesis_id),
            )
        return {"ok": True, "thesis_id": thesis_id, "feedback": fb.feedback}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])


# --- Mock fixtures(供 Flutter 联调用,不依赖后端 LLM)---
def _mock_thesis(req: ThesisRequest) -> dict:
    return {
        "thesis_id": "mock-uuid-thesis-001",
        "chain": req.chain,
        "token_address": req.address,
        "token_symbol": "TRUMP",
        "level": "L2" if req.level == "auto" else req.level,
        "direction": "bullish",
        "conviction": 0.72,
        "entry_zone": {"low": 1.10, "high": 1.20},
        "stop_loss": 0.95,
        "target_price": [1.45, 1.80, 2.40],
        "risks": [
            "代币年龄仅 48h,流动性可能突然枯竭",
            "Top10 持仓 58%,有大户砸盘风险",
        ],
        "summary_30w": "短期看涨,但建议小仓位试水,设硬止损 0.95",
        "evidence": [
            {"source": "smart_money_signals", "value": "+45000 USD net 24h", "ts": "2026-05-01T..."},
            {"source": "hot_coins.score", "value": 78, "ts": "2026-05-01T..."},
        ],
        "similar_past_cases": [],
        "cost_usd": 0.025,
        "latency_ms": 4200,
    }


def _mock_thesis_by_id(thesis_id: str) -> dict:
    return _mock_thesis(ThesisRequest(chain="solana", address="MockAddr", level="L2"))
