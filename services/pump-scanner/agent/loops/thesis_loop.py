"""
Thesis Loop — 3 路分析合成 thesis JSON

引用 docs/agent-pm/05-tool-catalog.md S08 thesis-writer
引用 docs/agent-pm/03-prd.md §2.7 Thesis Schema
引用 docs/agent-pm/17-tech-plan.md Phase 2 Thesis Loop
引用 services/pump-scanner/migrations/local_pg/039_agent_thesis.sql

流程(单 turn):
  ThesisLoop.generate(device_id, chain, token_address, level='auto')
    1. _select_level:
       - level='auto':
         * 总仓位 < $30 → L1(纯规则,0 LLM)
         * 单笔金额 < $30 / 简单信号(score < 70) → L2(P02 直出)
         * 单笔 ≥ $30 + 关键决策 / score ≥ 70 → L3(P02 + 辩论)
         * (W3 D5+ autonomous-loop 续 9:暂只实施 L1 + L2;L3 留 W7-W12)
    2. _gather_evidence:并行拉 3 路 analyst output(技术/情绪/链上)
       - 失败的 layer 用 NEUTRAL_FALLBACK,不阻断
    3. _gather_similar_cases:T04 recall_memory 拉 3 条 episodic(可选)
    4. 组装 P02 prompt vars
    5. 调 prompt_loader + Claude(Sonnet for L2/L3,Haiku for L1)
    6. 解析 JSON → 校验必要字段(direction/conviction/risks≥2/evidence/level)
    7. 写本地 PG agent_thesis 表
    8. 返 ThesisResult(完整 thesis JSON + thesis_id + cost_usd + latency_ms)

LLM 失败降级:
  - L2 LLM 失败 → 降到 L1 规则化 thesis(neutral / conviction 0.3)
  - L1 一定不调 LLM,所以无失败

L1 规则化 thesis(0 LLM 成本):
  - direction:rule_engine 的 score 高低判断;score≥70 bullish,≤30 bearish,否则 neutral
  - conviction:固定 0.4(rule_engine 不超过 0.5 用于触发 L2)
  - summary_30w:模板"L1 规则信号:{direction} (score=X)"
  - risks:固定 2 条("L1 仅基于规则信号,未做 LLM 深度分析","流动性 / 集中度风险未量化")
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

CLAUDE_TIMEOUT_S = 30
THESIS_PROMPT_ID = "P02"
SONNET_MODEL_ID = "claude-sonnet-4-6"
HAIKU_MODEL_ID = "claude-haiku-4-5-20251001"

# auto-level 决策阈值
LEVEL_THRESHOLDS = {
    "L1_max_position_usd": 30.0,
    "L2_max_score": 70,        # score < 70 → L2;否则 L3
}


@dataclass
class ThesisResult:
    ok: bool
    thesis: Dict[str, Any]
    thesis_id: Optional[str] = None
    level: str = "L1"
    source: str = "rule_engine"  # rule_engine | llm
    cost_usd: float = 0.0
    latency_ms: int = 0
    error: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class ThesisLoop:
    """单 turn thesis 生成。"""

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")

    async def generate(
        self,
        device_id: str,
        chain: str,
        token_address: str,
        token_symbol: Optional[str] = None,
        level: str = "auto",
        position_usd: Optional[float] = None,
        score: Optional[float] = None,
        regime: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> ThesisResult:
        """主入口。

        Args:
          device_id: 用户 UUID(用于 prompt bucket + DB write + recall_memory)
          chain / token_address / token_symbol: 标的
          level: 'auto' | 'L1' | 'L2' | 'L3'(L3 留 W7-W12,目前 fallback L2)
          position_usd: 该笔候选交易金额(用于 auto level 决策)
          score: 规则引擎打分(用于 auto level)
          regime: 当前 regime(给 P02 prompt 用)
          extra_context: 额外字段透传 prompt
        """
        t0 = time.monotonic()

        # 1. 决策 level
        chosen_level = self._select_level(level, position_usd, score)

        # 2. 拉 3 路 evidence(并发)
        tech, sent, onc = await self._gather_evidence(
            chain=chain, token_address=token_address,
            extra_context=extra_context or {},
        )

        # 3. 拉 similar_past_cases(可选,失败不阻断)
        similar = await self._gather_similar_cases(device_id, chain)

        # 4. 路由
        if chosen_level == "L1":
            thesis = self._make_l1_thesis(
                chain=chain, token_address=token_address,
                token_symbol=token_symbol, score=score,
                regime=regime, tech=tech, sent=sent, onc=onc,
            )
            tid = await self._persist_thesis(device_id, thesis, "L1",
                                              tech, sent, onc, similar,
                                              cost_usd=0.0, latency_ms=int((time.monotonic() - t0) * 1000))
            return ThesisResult(
                ok=True, thesis=thesis, thesis_id=tid,
                level="L1", source="rule_engine",
                cost_usd=0.0,
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # L2 / L3 → 调 P02
        # L3 真实施(辩论)留 W7-W12,目前 fallback 到 L2
        if chosen_level == "L3":
            log.info("[thesis_loop] L3 fallback to L2 (debate impl pending W7-W12)")
            chosen_level = "L2"
        target_level = chosen_level

        thesis_json, llm_err, cost_usd, llm_tokens = await self._invoke_p02(
            device_id=device_id, level=target_level,
            chain=chain, token_address=token_address, token_symbol=token_symbol,
            tech=tech, sent=sent, onc=onc, similar=similar, regime=regime,
        )

        if thesis_json is None:
            # LLM 失败 → 降级 L1
            log.warning("[thesis_loop] L2 LLM failed (%s),degrading to L1", llm_err)
            thesis = self._make_l1_thesis(
                chain=chain, token_address=token_address,
                token_symbol=token_symbol, score=score,
                regime=regime, tech=tech, sent=sent, onc=onc,
            )
            tid = await self._persist_thesis(device_id, thesis, "L1",
                                              tech, sent, onc, similar,
                                              cost_usd=0.0, latency_ms=int((time.monotonic() - t0) * 1000))
            return ThesisResult(
                ok=True, thesis=thesis, thesis_id=tid,
                level="L1", source="rule_engine",
                cost_usd=0.0,
                latency_ms=int((time.monotonic() - t0) * 1000),
                error=f"l2_failed_degraded: {llm_err}",
            )

        # 校验 + 修正
        normalized = self._normalize_and_validate(
            thesis_json, chain=chain, token_address=token_address,
            token_symbol=token_symbol, level=target_level,
        )

        latency_ms = int((time.monotonic() - t0) * 1000)
        tid = await self._persist_thesis(
            device_id, normalized, target_level,
            tech, sent, onc, similar,
            cost_usd=cost_usd, latency_ms=latency_ms,
            tokens_used=llm_tokens,
        )

        return ThesisResult(
            ok=True, thesis=normalized, thesis_id=tid,
            level=target_level, source="llm",
            cost_usd=cost_usd, latency_ms=latency_ms,
        )

    # ── helpers ──────────────────────────────────────────────

    def _select_level(
        self, requested: str, position_usd: Optional[float], score: Optional[float],
    ) -> str:
        """auto level 决策:position_usd + score 综合判断。"""
        if requested in ("L1", "L2", "L3"):
            return requested

        # auto
        pos = position_usd or 0.0
        sc = score or 0.0
        if pos < LEVEL_THRESHOLDS["L1_max_position_usd"] and sc < 50:
            return "L1"
        if sc < LEVEL_THRESHOLDS["L2_max_score"]:
            return "L2"
        return "L3"

    async def _gather_evidence(
        self, chain: str, token_address: str, extra_context: Dict[str, Any],
    ) -> Tuple[Dict, Dict, Dict]:
        """并发调 3 路 analyst。返 (technical, sentiment, onchain)。

        失败 layer 用 NEUTRAL_FALLBACK,不阻断其他层。
        """
        try:
            from agent.analysts.technical import TechnicalAnalyst, NEUTRAL_FALLBACK as TECH_FB
            from agent.analysts.sentiment import SentimentAnalyst, NEUTRAL_FALLBACK as SENT_FB
            from agent.analysts.onchain import OnchainAnalyst, NEUTRAL_FALLBACK as ONC_FB
        except Exception as e:
            log.warning("[thesis_loop] analyst import failed: %s", e)
            return ({"direction": "neutral", "confidence": 0.3, "_error": "analyst_import"},) * 3  # type: ignore

        token_data = extra_context.get("token_data") or {
            "chain": chain, "address": token_address,
        }
        market_data = extra_context.get("market_data") or {}

        async def _safe(coro, fallback):
            try:
                return await coro
            except Exception as e:
                log.warning("[thesis_loop] analyst failed: %s", e)
                return dict(fallback)

        tech_task = _safe(
            TechnicalAnalyst().analyze(token_data, market_data), TECH_FB,
        )
        sent_task = _safe(
            SentimentAnalyst().analyze(token_data, market_data), SENT_FB,
        )
        onc_task = _safe(
            OnchainAnalyst().analyze(token_data, market_data), ONC_FB,
        )
        results = await asyncio.gather(tech_task, sent_task, onc_task)
        return results[0], results[1], results[2]

    async def _gather_similar_cases(
        self, device_id: str, chain: str,
    ) -> List[Dict[str, Any]]:
        """T04 recall_memory 拉 episodic(可选)。"""
        try:
            from agent.tools import RecallMemoryTool
            tool = RecallMemoryTool()
            r = await tool.run({
                "device_id": device_id, "layers": ["episodic"],
                "chain": chain, "limit_per_layer": 3,
            })
            if r.ok and r.output.get("episodic"):
                return r.output["episodic"][:3]
        except Exception as e:
            log.debug("[thesis_loop] recall_memory failed: %s", e)
        return []

    def _make_l1_thesis(
        self, chain: str, token_address: str, token_symbol: Optional[str],
        score: Optional[float], regime: Optional[str],
        tech: Dict, sent: Dict, onc: Dict,
    ) -> Dict[str, Any]:
        """L1 规则化 thesis(0 LLM 成本)。conviction 上限 0.49 — 不能超 L2 阈值。"""
        sc = score or 0.0
        if sc >= 70:
            direction = "bullish"
        elif sc <= 30:
            direction = "bearish"
        else:
            direction = "neutral"

        # conviction:rule_engine 不超 0.5(避免 PRD 硬约束 conviction<0.5 必须 hold/avoid 触发)
        # 强制保 0.4(代表"中等可信"但还没到 LLM 论证)
        conviction = 0.4 if direction != "neutral" else 0.30

        return {
            "direction": direction if direction != "neutral" else "hold",
            "conviction": conviction,
            "summary_30w": f"L1 规则信号:{direction} (score={int(sc)})"[:30],
            "entry_zone": None,
            "stop_loss": None,
            "target": None,
            "risks": [
                "L1 仅基于规则信号,未做 LLM 深度分析",
                "流动性 / 集中度风险未量化,执行前请人工核验",
            ],
            "evidence": [
                {"layer": "rule_engine", "text": f"score={sc}", "weight": 0.5},
            ],
            "level": "L1",
            "_chain": chain,
            "_token_address": token_address,
            "_token_symbol": token_symbol or "",
            "_regime": regime or "UNKNOWN",
        }

    async def _invoke_p02(
        self,
        device_id: str, level: str,
        chain: str, token_address: str, token_symbol: Optional[str],
        tech: Dict, sent: Dict, onc: Dict,
        similar: List[Dict], regime: Optional[str],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], float, int]:
        """调 P02 thesis_writer。返 (thesis_json, error, cost_usd, tokens)。"""
        if not self._api_key:
            return None, "no_api_key", 0.0, 0

        # P02 vars
        vars_ = {
            "technical_summary": _summarize_analyst("技术", tech),
            "sentiment_summary": _summarize_analyst("情绪", sent),
            "onchain_summary": _summarize_analyst("链上", onc),
            "regime": regime or "UNKNOWN",
            "chain": chain,
            "token_symbol": token_symbol or token_address[:8],
            "token_address": token_address,
            "similar_past_cases": _summarize_similar_cases(similar),
        }

        try:
            from agent.prompt_loader import get_prompt_loader
            loader = get_prompt_loader()
            req = loader.to_messages_request(
                THESIS_PROMPT_ID, device_id,
                user_message=f"为 {chain}/{token_symbol or token_address[:8]} 生成 {level} thesis",
                vars=vars_,
            )
        except Exception as e:
            return None, f"prompt_loader: {e}", 0.0, 0

        # L1 用 Haiku;L2/L3 用 Sonnet(P02 frontmatter 默认 sonnet)
        if level == "L1":
            req["model"] = HAIKU_MODEL_ID
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self._api_key, timeout=CLAUDE_TIMEOUT_S)
            response = await asyncio.to_thread(client.messages.create, **req)
            text = response.content[0].text.strip()
            input_tokens = getattr(response.usage, "input_tokens", 0) or 0
            output_tokens = getattr(response.usage, "output_tokens", 0) or 0
            tokens_used = input_tokens + output_tokens
            cost_usd = _estimate_cost_usd(req.get("model", SONNET_MODEL_ID),
                                           input_tokens, output_tokens)
        except Exception as e:
            log.warning("[thesis_loop] Claude call failed: %s", e)
            return None, f"claude_failed: {e}", 0.0, 0

        parsed = _parse_json_block(text)
        if not parsed:
            return None, f"json_parse_failed: {text[:200]}", cost_usd, tokens_used
        return parsed, None, cost_usd, tokens_used

    def _normalize_and_validate(
        self, thesis: Dict[str, Any],
        chain: str, token_address: str, token_symbol: Optional[str], level: str,
    ) -> Dict[str, Any]:
        """对齐 PRD 硬约束 + 兜底缺失字段。"""
        out = dict(thesis)
        out.setdefault("level", level)
        out["_chain"] = chain
        out["_token_address"] = token_address
        out["_token_symbol"] = token_symbol or ""

        # direction enum normalize
        dir_ = (out.get("direction") or "neutral").lower()
        if dir_ in ("long",):
            dir_ = "bullish"
        elif dir_ in ("short",):
            dir_ = "bearish"
        out["direction"] = dir_

        # conviction range 0..1
        conv = float(out.get("conviction", 0) or 0)
        out["conviction"] = max(0.0, min(1.0, conv))

        # PRD 硬约束:conviction < 0.5 必须 direction in {hold,avoid,neutral}
        if out["conviction"] < 0.5 and dir_ not in ("hold", "avoid", "neutral"):
            out["direction"] = "neutral"
            out.setdefault("summary_30w", out.get("summary_30w", "") or "")
            if "低置信度" not in (out["summary_30w"] or ""):
                out["summary_30w"] = ("低置信度 — " + (out["summary_30w"] or ""))[:60]

        # risks ≥ 2
        risks = out.get("risks") or []
        if not isinstance(risks, list):
            risks = []
        if len(risks) < 2:
            risks = list(risks) + [
                "Risk 字段不足 2 条,自动补占位:LLM 输出未通过 PRD 硬约束",
                "请人工核验真实风险",
            ][: 2 - len(risks)]
        out["risks"] = risks

        # summary_30w 必填
        if not out.get("summary_30w"):
            out["summary_30w"] = f"{dir_} 候选 — 自动占位"
        out["summary_30w"] = str(out["summary_30w"])[:60]

        # evidence 兜底
        if not out.get("evidence"):
            out["evidence"] = [{"layer": "system", "text": "evidence missing", "weight": 0.0}]

        return out

    async def _persist_thesis(
        self, device_id: str, thesis: Dict[str, Any], level: str,
        tech: Dict, sent: Dict, onc: Dict,
        similar: List[Dict],
        cost_usd: float = 0.0, latency_ms: int = 0,
        tokens_used: int = 0,
    ) -> Optional[str]:
        """写本地 PG agent_thesis 表。失败返 None,不阻断。"""
        try:
            from local_db import _get_conn
            conn = _get_conn()
        except Exception as e:
            log.debug("[thesis_loop] local_db conn failed: %s", e)
            return None

        # device_id 必须 UUID
        if not _is_uuid(device_id):
            log.debug("[thesis_loop] non-UUID device_id, skip persist: %s", device_id)
            return None

        # direction 映射到表 enum:bullish|bearish|neutral|hold|avoid
        direction = thesis.get("direction", "neutral")
        if direction not in ("bullish", "bearish", "neutral", "hold", "avoid"):
            direction = "neutral"

        risks = thesis.get("risks") or []
        if not isinstance(risks, list):
            risks = ["risks 字段格式错误,自动占位 1", "risks 字段格式错误,自动占位 2"]
        if len(risks) < 2:
            risks = list(risks) + ["占位 risk"] * (2 - len(risks))

        new_id = str(uuid.uuid4())
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_thesis
                      (thesis_id, device_id, chain, token_address, token_symbol,
                       level, direction, conviction,
                       entry_zone, stop_loss, target_price,
                       risks, summary_30w, evidence,
                       similar_past_cases,
                       technical_report, sentiment_report, onchain_report,
                       cost_usd, latency_ms, prompt_version_used)
                    VALUES (%s, %s, %s, %s, %s,
                            %s, %s, %s,
                            %s::jsonb, %s, %s::jsonb,
                            %s, %s, %s::jsonb,
                            %s::jsonb,
                            %s::jsonb, %s::jsonb, %s::jsonb,
                            %s, %s, %s)
                    RETURNING thesis_id
                    """,
                    (
                        new_id, device_id,
                        thesis.get("_chain") or "unknown",
                        thesis.get("_token_address") or "",
                        thesis.get("_token_symbol") or None,
                        level, direction, float(thesis.get("conviction", 0)),
                        json.dumps(thesis.get("entry_zone")) if thesis.get("entry_zone") else None,
                        thesis.get("stop_loss"),
                        json.dumps(thesis.get("target")) if thesis.get("target") is not None else None,
                        risks, thesis.get("summary_30w", "")[:200],
                        json.dumps(thesis.get("evidence") or [], default=str),
                        json.dumps(similar or [], default=str),
                        json.dumps(tech, default=str),
                        json.dumps(sent, default=str),
                        json.dumps(onc, default=str),
                        cost_usd, latency_ms,
                        "P02-v1.0",
                    ),
                )
                row = cur.fetchone()
                return str(row[0]) if row else new_id
        except Exception as e:
            log.warning("[thesis_loop] persist agent_thesis failed: %s", e)
            return None


# ── module helpers ──────────────────────────────────────────


def _summarize_analyst(layer_name: str, result: Dict[str, Any]) -> str:
    """把 analyst 结果压缩成 P02 prompt 用的短文本。"""
    if not result:
        return f"{layer_name} 数据不可用"
    direction = result.get("direction", "neutral")
    confidence = result.get("confidence", 0.5)
    points = result.get("points") or []
    points_str = "; ".join(str(p)[:60] for p in points[:3])
    return f"{layer_name}: dir={direction} conf={confidence:.2f}; {points_str}"


def _summarize_similar_cases(cases: List[Dict[str, Any]]) -> str:
    if not cases:
        return "(无相似历史案例)"
    parts = []
    for c in cases[:3]:
        summary = (c.get("summary") or "")[:80]
        score = c.get("score")
        parts.append(f"- {summary}" + (f" (相关度 {score})" if score else ""))
    return "\n".join(parts)


def _parse_json_block(text: str) -> Optional[Dict[str, Any]]:
    s = text.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines:
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            s = "\n".join(lines).strip()
    try:
        return json.loads(s)
    except Exception:
        first = s.find("{")
        last = s.rfind("}")
        if first >= 0 and last > first:
            try:
                return json.loads(s[first:last + 1])
            except Exception:
                return None
        return None


# 简易 cost 估算(per 1M tokens,USD)— 对齐 anthropic 公开价
COST_PER_1M = {
    HAIKU_MODEL_ID: {"input": 1.0, "output": 5.0},
    SONNET_MODEL_ID: {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
}


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = COST_PER_1M.get(model, COST_PER_1M[SONNET_MODEL_ID])
    return round(
        input_tokens / 1_000_000 * rates["input"]
        + output_tokens / 1_000_000 * rates["output"],
        6,
    )


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _is_uuid(s: str) -> bool:
    return bool(s and _UUID_RE.match(s))


# ── singleton ────────────────────────────────────────────


_loop: Optional[ThesisLoop] = None


def get_thesis_loop() -> ThesisLoop:
    global _loop
    if _loop is None:
        _loop = ThesisLoop()
    return _loop


def reset_loop_for_test() -> None:
    global _loop
    _loop = None
