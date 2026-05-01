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
    """触发新 thesis 生成(同步,~5s for L2 / ~15s for L3)。"""
    if MOCK_MODE:
        return _mock_thesis(req)
    raise HTTPException(status_code=501, detail="thesis_loop W3-W6 实施;当前请用 MOCK_MODE=true")


@router.get("/{thesis_id}")
async def get_thesis(thesis_id: str):
    if MOCK_MODE:
        return _mock_thesis_by_id(thesis_id)
    raise HTTPException(status_code=501, detail="W3-W6 实施")


@router.get("")
async def list_thesis(token_address: str | None = None, limit: int = 20):
    if MOCK_MODE:
        return {"thesis": [], "total": 0}
    raise HTTPException(status_code=501, detail="W3-W6 实施")


@router.post("/{thesis_id}/feedback")
async def feedback_thesis(thesis_id: str, fb: ThesisFeedback):
    if MOCK_MODE:
        return {"ok": True, "thesis_id": thesis_id}
    raise HTTPException(status_code=501, detail="W3-W6 实施")


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
