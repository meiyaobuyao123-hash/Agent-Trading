"""
共创 Chat Loop — 把 P01 / P11 prompt + cocreation_state_machine + 12 Tool 串起来

引用 docs/agent-pm/05-tool-catalog.md S04 signal-strategy-builder
引用 docs/agent-pm/17-tech-plan.md Phase 2(Loop)
引用 agent/orchestration/cocreation_state_machine.py

流程:
  user_message → CocreationLoop.handle()
    1. load_active_state 或 create_state(初始 stage=clarifying)
    2. append_message(role=user)
    3. 根据 stage 选 prompt:
         clarifying → P01 chat_clarify
         refining   → P11 signal_strategy_builder
         dry_run    → 占位(W7-W12 接 backtest tool 真预估)
         confirming → 检测确认词 → 调 T12 save_strategy → saved
    4. 调 prompt_loader + Claude(失败降级:返启发式回复)
    5. 解析输出:
         P01:正文 + STAGE_TRANSITION:refining|aborted
         P11:JSON(spec / error)
    6. state.transition() + append_message(role=assistant)
    7. 返回 {assistant_text, stage, current_state, draft, saved_strategy_id}

设计原则:
  - LLM 失败永远不抛错 → 用 suggest_next_stage 启发式 + 兜底文案
  - 任何阶段都接受 abort 词("算了/取消")
  - confirm 词触发 saved 时调 T12,失败 → 降回 confirming + 用户重试
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

CLAUDE_TIMEOUT_S = 30
ABORT_WORDS = ("算了", "取消", "不要了", "放弃", "abort", "cancel")
CONFIRM_WORDS = ("确认", "确定", "保存", "ok", "yes", "好的", "可以", "对")


@dataclass
class ChatLoopResult:
    ok: bool
    assistant_text: str
    stage: str
    conversation_id: str
    draft_data: Optional[Dict[str, Any]] = None
    saved_strategy_id: Optional[str] = None
    suggested_next_stage: Optional[str] = None
    source: str = "llm"  # "llm" | "rule_engine" | "abort" | "saved"
    error: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class CocreationLoop:
    """单次 turn 处理:输入 user_message,推进状态机,产出 assistant 回复。"""

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")

    async def handle(
        self,
        device_id: str,
        user_message: str,
        skill_name: str = "signal-strategy-builder",
    ) -> ChatLoopResult:
        from agent.orchestration import cocreation_state_machine as csm

        # 1. load 或 create state
        state = csm.load_active_state(device_id, skill_name)
        if state is None:
            state = csm.create_state(device_id, skill_name, initial_message=user_message)
            if state is None:
                return ChatLoopResult(
                    ok=False, assistant_text="对话状态创建失败,请稍后再试。",
                    stage="aborted", conversation_id="",
                    source="rule_engine", error="state_create_failed",
                )
        else:
            csm.append_message(state["conversation_id"], "user", user_message)
            # 重新 load 拿到最新 messages
            fresh = csm.load_active_state(device_id, skill_name)
            if fresh:
                state = fresh

        conv_id: str = state["conversation_id"]
        cur_stage: str = state["stage"]

        # 2. 全局 abort 检查
        text = user_message.lower()
        if any(w in text for w in ABORT_WORDS):
            csm.transition(conv_id, "aborted")
            csm.append_message(conv_id, "assistant", "好的,已取消本次共创,随时回来。")
            return ChatLoopResult(
                ok=True,
                assistant_text="好的,已取消本次共创,随时回来。",
                stage="aborted", conversation_id=conv_id,
                source="abort",
            )

        # 3. 路由到对应 stage handler
        if cur_stage == "clarifying":
            return await self._handle_clarifying(state, user_message)
        if cur_stage == "refining":
            return await self._handle_refining(state, user_message)
        if cur_stage == "dry_run":
            return await self._handle_dry_run(state, user_message)
        if cur_stage == "confirming":
            return await self._handle_confirming(state, user_message)

        # terminal(saved/aborted)— 返提示让用户开新 session
        return ChatLoopResult(
            ok=True,
            assistant_text="本次共创已结束,要开始新策略吗?",
            stage=cur_stage, conversation_id=conv_id,
            source="rule_engine",
        )

    # ── handlers ────────────────────────────────────────────

    async def _handle_clarifying(
        self, state: Dict[str, Any], user_message: str,
    ) -> ChatLoopResult:
        from agent.orchestration import cocreation_state_machine as csm
        conv_id = state["conversation_id"]

        # 调 P01 prompt
        text, source, err = await self._invoke_llm(
            prompt_id="P01",
            device_id=state["device_id"],
            user_message=user_message,
            vars_={
                "user_history": _summarize_messages(state.get("messages", [])),
                "collected": _collected_vars(state),
                "persona": "intermediate",
            },
            fallback_text=(
                "我帮你把策略想法变具体。"
                "先告诉我:你想关注哪条链?(SOL/BSC/Base/ETH 多选)"
            ),
        )

        # 检测 STAGE_TRANSITION 标记(P01 prompt 里教 LLM 输出)
        next_stage, cleaned_text = _extract_stage_transition(text)
        csm.append_message(conv_id, "assistant", cleaned_text)

        if next_stage in ("refining", "aborted"):
            ok, _ = csm.transition(conv_id, next_stage)
            return ChatLoopResult(
                ok=True, assistant_text=cleaned_text,
                stage=next_stage if ok else "clarifying",
                conversation_id=conv_id,
                source=source,
                suggested_next_stage=next_stage,
                error=err,
            )

        # 没 transition 标记 → 启发式判断是否到 refining
        suggested = csm.suggest_next_stage(
            "clarifying", user_message, has_draft=False,
        )
        return ChatLoopResult(
            ok=True, assistant_text=cleaned_text,
            stage="clarifying", conversation_id=conv_id,
            source=source, suggested_next_stage=suggested, error=err,
        )

    async def _handle_refining(
        self, state: Dict[str, Any], user_message: str,
    ) -> ChatLoopResult:
        from agent.orchestration import cocreation_state_machine as csm
        conv_id = state["conversation_id"]

        # 检测确认词 → 直接进 dry_run
        text = user_message.lower()
        has_draft = state.get("draft_data") is not None

        # 调 P11 让 LLM 产出 StrategySpec JSON
        collected = _collected_vars(state)
        # P11 期望 collected 各字段;若 draft 已存在,把 draft 喂回去
        prompt_vars = dict(collected)
        prompt_vars["user_proposed_name"] = state.get("draft_data", {}).get("name", "") if isinstance(state.get("draft_data"), dict) else ""

        json_text, source, err = await self._invoke_llm(
            prompt_id="P11",
            device_id=state["device_id"],
            user_message=user_message,
            vars_=prompt_vars,
            fallback_text='{"error":"missing","missing_fields":["chain","trigger","amount_usd","stop_loss_pct","take_profit_pct"]}',
        )

        parsed = _parse_json_block(json_text)
        if parsed and "error" not in parsed and "conditions" in parsed:
            # 写 draft_data;若用户说了确认词,直接进 dry_run
            csm.transition(conv_id, "refining", draft_data=parsed)
            csm.append_message(
                conv_id, "assistant",
                f"草案已生成:{parsed.get('name', '未命名')}。要预跑回测吗?(回 OK 进入 dry-run)",
            )
            if has_draft and any(w in text for w in CONFIRM_WORDS):
                csm.transition(conv_id, "dry_run")
                return ChatLoopResult(
                    ok=True,
                    assistant_text=f"开始回测:{parsed.get('name', '')}…",
                    stage="dry_run", conversation_id=conv_id,
                    draft_data=parsed, source=source, error=err,
                )
            return ChatLoopResult(
                ok=True,
                assistant_text=f"草案已生成:{parsed.get('name', '未命名')}。要预跑回测吗?(回 OK 进入 dry-run)",
                stage="refining", conversation_id=conv_id,
                draft_data=parsed, source=source, error=err,
            )

        # missing 字段或解析失败 → 留在 refining
        if parsed and parsed.get("error") == "missing":
            missing = parsed.get("missing_fields", [])
            assistant = f"还缺这几项:{', '.join(missing[:3])}。先告诉我其中 1 个?"
        else:
            assistant = "草案有点乱,我再问 1 个最关键的:每笔进场金额是多少 USD?"
        csm.append_message(conv_id, "assistant", assistant)
        return ChatLoopResult(
            ok=True, assistant_text=assistant,
            stage="refining", conversation_id=conv_id,
            source=source, error=err,
        )

    async def _handle_dry_run(
        self, state: Dict[str, Any], user_message: str,
    ) -> ChatLoopResult:
        """W3 D5+ 占位:dry_run 不真跑回测,直接进 confirming。
        W7-W12 接 T16 run_backtest 真实施。
        """
        from agent.orchestration import cocreation_state_machine as csm
        conv_id = state["conversation_id"]

        draft = state.get("draft_data") or {}
        # 假装回测完成(留 W7-W12 接 T16)
        dry_result = {
            "30d_simulated_pnl_pct": 0.0,
            "30d_trade_count": 0,
            "note": "dry_run 占位 — W7-W12 接 T16 run_backtest 真实施",
        }
        csm.transition(conv_id, "confirming", dry_run_result=dry_result)
        assistant = (
            f"回测占位完成(W7-W12 接真预估)。\n"
            f"草案:{draft.get('name', '未命名')}\n"
            f"确认保存?(回 '确认' 创建策略,回 '调整' 改细节)"
        )
        csm.append_message(conv_id, "assistant", assistant)
        return ChatLoopResult(
            ok=True, assistant_text=assistant,
            stage="confirming", conversation_id=conv_id,
            draft_data=draft, source="rule_engine",
            extra={"dry_run_result": dry_result},
        )

    async def _handle_confirming(
        self, state: Dict[str, Any], user_message: str,
    ) -> ChatLoopResult:
        from agent.orchestration import cocreation_state_machine as csm
        conv_id = state["conversation_id"]
        text = user_message.lower()
        draft = state.get("draft_data") or {}

        if any(w in text for w in CONFIRM_WORDS):
            # 调 T12 save_strategy
            saved_id, save_err = await self._call_save_strategy(
                user_id=state["device_id"], spec=draft,
            )
            if saved_id:
                csm.transition(conv_id, "saved", saved_strategy_id=saved_id)
                assistant = (
                    f"策略已保存!ID: {saved_id[:8]}…\n"
                    f"已进入 paper 模式跑 30 天,达标后可晋升 notify/auto。"
                )
                csm.append_message(conv_id, "assistant", assistant)
                return ChatLoopResult(
                    ok=True, assistant_text=assistant,
                    stage="saved", conversation_id=conv_id,
                    saved_strategy_id=saved_id,
                    source="saved",
                )
            # 保存失败 → 留在 confirming
            assistant = f"保存失败:{save_err or '未知错误'}。要再试一次吗?"
            csm.append_message(conv_id, "assistant", assistant)
            return ChatLoopResult(
                ok=False, assistant_text=assistant,
                stage="confirming", conversation_id=conv_id,
                draft_data=draft, source="rule_engine",
                error=save_err,
            )

        # 用户给反馈 → 回 refining
        csm.transition(conv_id, "refining")
        assistant = "好,回到调整阶段。具体改哪一项?"
        csm.append_message(conv_id, "assistant", assistant)
        return ChatLoopResult(
            ok=True, assistant_text=assistant,
            stage="refining", conversation_id=conv_id,
            draft_data=draft, source="rule_engine",
        )

    # ── LLM 调用 ──────────────────────────────────────────────

    async def _invoke_llm(
        self,
        prompt_id: str,
        device_id: str,
        user_message: str,
        vars_: Dict[str, Any],
        fallback_text: str,
    ) -> "tuple[str, str, Optional[str]]":
        """调 prompt_loader + Claude;失败返 fallback_text。

        W3 D5+ 续 15:接 cost_guard 在 LLM 调用前检查预算,
        HARD_STOP / BLOCKED → fallback;DEGRADE → 自动降 model。

        Returns: (text, source, error_or_None)
        """
        if not self._api_key:
            return fallback_text, "rule_engine", "no_api_key"
        try:
            from agent.prompt_loader import get_prompt_loader
            loader = get_prompt_loader()
            req = loader.to_messages_request(prompt_id, device_id, user_message, vars_)
        except Exception as e:
            log.warning("[chat_loop] prompt_loader %s failed: %s", prompt_id, e)
            return fallback_text, "rule_engine", f"prompt_loader_failed: {e}"

        # cost_guard 检查
        try:
            from agent.cost_guard import get_cost_guard
            allowed, actual_model, reason = await get_cost_guard().check_before_call(
                intended_model=req.get("model", "claude-haiku-4-5-20251001"),
                intended_level="L2",
            )
            if not allowed:
                log.info("[chat_loop] cost_guard blocked: %s", reason)
                return fallback_text, "rule_engine", f"cost_guard_block: {reason}"
            if actual_model != req.get("model"):
                req["model"] = actual_model  # 自动降级
        except Exception as e:
            log.debug("[chat_loop] cost_guard skipped: %s", e)

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self._api_key, timeout=CLAUDE_TIMEOUT_S)
            response = await asyncio.to_thread(client.messages.create, **req)
            text = response.content[0].text.strip()
            return text, "llm", None
        except Exception as e:
            log.warning("[chat_loop] Claude call %s failed: %s", prompt_id, e)
            return fallback_text, "rule_engine", f"llm_failed: {e}"

    async def _call_save_strategy(
        self, user_id: str, spec: Dict[str, Any],
    ) -> "tuple[Optional[str], Optional[str]]":
        """走 T12 Tool 保存。返回 (strategy_id, error_or_None)。"""
        try:
            from agent.tools import SaveStrategyTool
            tool = SaveStrategyTool()
            r = await tool.run({"user_id": user_id, "spec": spec})
            if r.ok and r.output.get("ok"):
                strategy = r.output.get("strategy") or {}
                return str(strategy.get("id", "")), None
            return None, (r.output or {}).get("reason", "tool_failed")
        except Exception as e:
            log.warning("[chat_loop] T12 save_strategy failed: %s", e)
            return None, str(e)[:200]


# ── helpers ───────────────────────────────────────────────


_STAGE_RE = re.compile(r"\nSTAGE_TRANSITION\s*:\s*(\w+)\s*$")


def _extract_stage_transition(text: str) -> "tuple[Optional[str], str]":
    """从 P01 输出末尾抽 STAGE_TRANSITION:xxx 行。"""
    if not text:
        return None, ""
    m = _STAGE_RE.search(text)
    if not m:
        return None, text.strip()
    cleaned = _STAGE_RE.sub("", text).strip()
    return m.group(1), cleaned


def _parse_json_block(text: str) -> Optional[Dict[str, Any]]:
    """解析 LLM 输出的 JSON(可能带 ```json 包裹)。"""
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


def _summarize_messages(messages: list, max_n: int = 6) -> str:
    """把最近 N 条 messages 拼成 user_history 字符串(给 P01 prompt 用)。"""
    if not messages:
        return "(尚无)"
    parts = []
    for m in messages[-max_n:]:
        role = m.get("role", "")
        content = (m.get("content") or "")[:200]
        parts.append(f"[{role}] {content}")
    return "\n".join(parts)


def _collected_vars(state: Dict[str, Any]) -> Dict[str, Any]:
    """从 state.draft_data 抽出 P01/P11 需要的字段(空字段保 None/空串)。"""
    draft = state.get("draft_data") or {}
    if not isinstance(draft, dict):
        draft = {}
    risk = (draft.get("risk_params") or {}) if isinstance(draft.get("risk_params"), dict) else {}
    filt = (draft.get("filters") or {}) if isinstance(draft.get("filters"), dict) else {}
    actions = (draft.get("actions") or []) if isinstance(draft.get("actions"), list) else []
    amount_usd = ""
    if actions and isinstance(actions[0], dict):
        amount_usd = (actions[0].get("params") or {}).get("amount_usd", "")
    return {
        "chain": ",".join(filt.get("chains", []) or []),
        "trigger": "",  # 留 LLM 自己识别
        "amount_usd": amount_usd or "",
        "stop_loss": risk.get("stop_loss_pct", ""),
        "take_profit": risk.get("take_profit_pct", ""),
        "cooldown_min": draft.get("cooldown_minutes", ""),
        "stop_loss_pct": risk.get("stop_loss_pct", ""),
        "take_profit_pct": risk.get("take_profit_pct", ""),
        "persona": "intermediate",
    }


# ── singleton ────────────────────────────────────────────


_loop: Optional[CocreationLoop] = None


def get_cocreation_loop() -> CocreationLoop:
    global _loop
    if _loop is None:
        _loop = CocreationLoop()
    return _loop


def reset_loop_for_test() -> None:
    global _loop
    _loop = None
