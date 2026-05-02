"""
共创 chat_loop 单元测试 — W3 D5+ autonomous-loop 续 8

跑法:python3 -m pytest tests/test_chat_loop.py -v
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.loops import chat_loop  # noqa: E402
from agent.loops.chat_loop import (  # noqa: E402
    ChatLoopResult,
    CocreationLoop,
    _collected_vars,
    _extract_stage_transition,
    _parse_json_block,
    _summarize_messages,
    reset_loop_for_test,
)


# ── helpers tests ───────────────────────────────────────────

def test_extract_stage_transition_present():
    text = "好的,我帮你梳理一下。\n\nSTAGE_TRANSITION:refining"
    next_stage, cleaned = _extract_stage_transition(text)
    assert next_stage == "refining"
    assert "STAGE_TRANSITION" not in cleaned
    assert cleaned.endswith("梳理一下。") or cleaned.endswith("梳理一下")


def test_extract_stage_transition_absent():
    text = "你想做哪条链的策略?"
    next_stage, cleaned = _extract_stage_transition(text)
    assert next_stage is None
    assert cleaned == text.strip()


def test_extract_stage_transition_empty():
    next_stage, cleaned = _extract_stage_transition("")
    assert next_stage is None
    assert cleaned == ""


def test_parse_json_block_clean():
    assert _parse_json_block('{"a":1}') == {"a": 1}


def test_parse_json_block_markdown_fence():
    raw = "```json\n{\"name\":\"X\",\"conditions\":{\"rules\":[]}}\n```"
    r = _parse_json_block(raw)
    assert r["name"] == "X"


def test_parse_json_block_invalid():
    assert _parse_json_block("not json") is None
    assert _parse_json_block("") is None


def test_summarize_messages_truncates():
    msgs = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
    summary = _summarize_messages(msgs, max_n=3)
    assert "msg 17" in summary
    assert "msg 19" in summary
    assert "msg 5" not in summary


def test_summarize_messages_empty():
    assert "尚无" in _summarize_messages([])


def test_collected_vars_with_draft():
    state = {
        "draft_data": {
            "name": "Test",
            "filters": {"chains": ["SOL", "ETH"]},
            "risk_params": {"stop_loss_pct": -10, "take_profit_pct": 25},
            "actions": [{"type": "paper_buy", "params": {"amount_usd": 100}}],
            "cooldown_minutes": 15,
        },
    }
    v = _collected_vars(state)
    assert v["chain"] == "SOL,ETH"
    assert v["amount_usd"] == 100
    assert v["stop_loss"] == -10
    assert v["take_profit"] == 25
    assert v["cooldown_min"] == 15


def test_collected_vars_empty_draft():
    v = _collected_vars({})
    assert v["chain"] == ""
    assert v["amount_usd"] == ""


# ── handle: state creation + abort ──────────────────────────

@pytest.mark.asyncio
async def test_handle_creates_state_when_none():
    """无现有 state → 创建 + clarifying。"""
    reset_loop_for_test()
    loop = CocreationLoop()
    fake_state = {
        "conversation_id": "conv-1", "device_id": "u-1",
        "skill_name": "signal-strategy-builder", "stage": "clarifying",
        "messages": [], "draft_data": None,
    }
    with patch("agent.orchestration.cocreation_state_machine.load_active_state",
               side_effect=[None, fake_state]), \
         patch("agent.orchestration.cocreation_state_machine.create_state",
               return_value=fake_state), \
         patch("agent.orchestration.cocreation_state_machine.append_message"), \
         patch("agent.orchestration.cocreation_state_machine.transition",
               return_value=(True, None)), \
         patch.object(loop, "_invoke_llm",
                      AsyncMock(return_value=("Hello, what chain?", "llm", None))):
        r = await loop.handle("u-1", "想做策略")
    assert r.ok is True
    assert r.stage == "clarifying"


@pytest.mark.asyncio
async def test_handle_abort_word_terminates():
    """用户说"算了" → stage=aborted。"""
    loop = CocreationLoop()
    fake_state = {
        "conversation_id": "conv-1", "device_id": "u-1",
        "skill_name": "signal-strategy-builder", "stage": "clarifying",
        "messages": [], "draft_data": None,
    }
    with patch("agent.orchestration.cocreation_state_machine.load_active_state",
               return_value=fake_state), \
         patch("agent.orchestration.cocreation_state_machine.append_message"), \
         patch("agent.orchestration.cocreation_state_machine.transition",
               return_value=(True, None)) as mock_trans:
        r = await loop.handle("u-1", "算了不要了")
    assert r.stage == "aborted"
    assert r.source == "abort"
    mock_trans.assert_called_with("conv-1", "aborted")


# ── _handle_clarifying ──────────────────────────────────────

@pytest.mark.asyncio
async def test_clarifying_llm_returns_stage_transition():
    """LLM 返带 STAGE_TRANSITION:refining → 真正 transition。"""
    loop = CocreationLoop()
    fake_state = {
        "conversation_id": "conv-1", "device_id": "u-1",
        "stage": "clarifying", "messages": [], "draft_data": None,
    }
    with patch.object(loop, "_invoke_llm",
                      AsyncMock(return_value=("Got it. \n\nSTAGE_TRANSITION:refining", "llm", None))), \
         patch("agent.orchestration.cocreation_state_machine.append_message"), \
         patch("agent.orchestration.cocreation_state_machine.transition",
               return_value=(True, None)) as mock_trans:
        r = await loop._handle_clarifying(fake_state, "SOL 跟单 $100 -10/+30 15min")
    assert r.stage == "refining"
    assert "Got it" in r.assistant_text
    mock_trans.assert_called_with("conv-1", "refining")


@pytest.mark.asyncio
async def test_clarifying_llm_failure_uses_fallback():
    """LLM 抛错 → 用 fallback_text 回复 + 留在 clarifying。"""
    loop = CocreationLoop()
    fake_state = {
        "conversation_id": "conv-1", "device_id": "u-1",
        "stage": "clarifying", "messages": [], "draft_data": None,
    }
    with patch.object(loop, "_invoke_llm",
                      AsyncMock(return_value=("我帮你把策略想法变具体。先告诉我:你想关注哪条链?(SOL/BSC/Base/ETH 多选)",
                                              "rule_engine", "no_api_key"))), \
         patch("agent.orchestration.cocreation_state_machine.append_message"), \
         patch("agent.orchestration.cocreation_state_machine.suggest_next_stage",
               return_value="clarifying"):
        r = await loop._handle_clarifying(fake_state, "嗯")
    assert r.stage == "clarifying"
    assert r.source == "rule_engine"
    assert "哪条链" in r.assistant_text


# ── _handle_refining ────────────────────────────────────────

@pytest.mark.asyncio
async def test_refining_valid_spec_writes_draft():
    """LLM 返合法 spec JSON → draft 写入,assistant 提示进 dry-run。"""
    loop = CocreationLoop()
    fake_state = {
        "conversation_id": "conv-1", "device_id": "u-1",
        "stage": "refining", "messages": [], "draft_data": None,
    }
    spec_json = '{"name":"SOL 跟单","conditions":{"rules":[{"data_source":"smart_money","field":"elite_score","op":">=","value":75}]},"actions":[{"type":"paper_buy","params":{"amount_usd":100}}],"filters":{"chains":["SOL"]},"risk_params":{"stop_loss_pct":-10,"take_profit_pct":30},"cooldown_minutes":15,"mode":"paper"}'
    with patch.object(loop, "_invoke_llm",
                      AsyncMock(return_value=(spec_json, "llm", None))), \
         patch("agent.orchestration.cocreation_state_machine.append_message"), \
         patch("agent.orchestration.cocreation_state_machine.transition",
               return_value=(True, None)) as mock_trans:
        r = await loop._handle_refining(fake_state, "ok")
    # draft 写入了
    assert r.draft_data is not None
    assert r.draft_data["name"] == "SOL 跟单"
    # transition refining(写 draft)被调
    args, kwargs = mock_trans.call_args
    assert args[1] == "refining"
    assert kwargs["draft_data"]["name"] == "SOL 跟单"


@pytest.mark.asyncio
async def test_refining_missing_fields_stays():
    """LLM 返 {error:missing} → 留 refining + 问缺哪项。"""
    loop = CocreationLoop()
    fake_state = {
        "conversation_id": "conv-1", "device_id": "u-1",
        "stage": "refining", "messages": [], "draft_data": None,
    }
    err_json = '{"error":"missing","missing_fields":["amount_usd","stop_loss_pct"]}'
    with patch.object(loop, "_invoke_llm",
                      AsyncMock(return_value=(err_json, "llm", None))), \
         patch("agent.orchestration.cocreation_state_machine.append_message"):
        r = await loop._handle_refining(fake_state, "继续")
    assert r.stage == "refining"
    assert "amount_usd" in r.assistant_text or "进场金额" in r.assistant_text


@pytest.mark.asyncio
async def test_refining_with_draft_and_confirm_advances_to_dry_run():
    """已有 draft + 用户说 OK → 进 dry_run。"""
    loop = CocreationLoop()
    fake_state = {
        "conversation_id": "conv-1", "device_id": "u-1",
        "stage": "refining", "messages": [],
        "draft_data": {"name": "Existing", "filters": {"chains": ["SOL"]}},
    }
    spec_json = '{"name":"Existing","conditions":{"rules":[{"data_source":"x","field":"y","op":">","value":1}]},"actions":[{"type":"alert"}],"filters":{"chains":["SOL"]},"risk_params":{},"cooldown_minutes":15,"mode":"paper"}'
    with patch.object(loop, "_invoke_llm",
                      AsyncMock(return_value=(spec_json, "llm", None))), \
         patch("agent.orchestration.cocreation_state_machine.append_message"), \
         patch("agent.orchestration.cocreation_state_machine.transition",
               return_value=(True, None)) as mock_trans:
        r = await loop._handle_refining(fake_state, "ok 这样可以")
    assert r.stage == "dry_run"
    # 应该调过两次 transition:refining(写 draft) + dry_run
    calls = [c.args[1] for c in mock_trans.call_args_list]
    assert "refining" in calls
    assert "dry_run" in calls


# ── _handle_dry_run ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_dry_run_advances_to_confirming():
    """dry_run 占位 → 直接进 confirming + 写 dry_result。"""
    loop = CocreationLoop()
    fake_state = {
        "conversation_id": "conv-1", "device_id": "u-1",
        "stage": "dry_run", "messages": [],
        "draft_data": {"name": "Test"},
    }
    with patch("agent.orchestration.cocreation_state_machine.append_message"), \
         patch("agent.orchestration.cocreation_state_machine.transition",
               return_value=(True, None)) as mock_trans:
        r = await loop._handle_dry_run(fake_state, "ok")
    assert r.stage == "confirming"
    # transition 被调 confirming
    args, kwargs = mock_trans.call_args
    assert args[1] == "confirming"
    assert "dry_run_result" in kwargs


# ── _handle_confirming ──────────────────────────────────────

@pytest.mark.asyncio
async def test_confirming_with_confirm_word_saves():
    """用户说 '确认' → 调 T12,saved。"""
    loop = CocreationLoop()
    fake_state = {
        "conversation_id": "conv-1", "device_id": "u-1",
        "stage": "confirming", "messages": [],
        "draft_data": {
            "name": "Test",
            "conditions": {"rules": [{"data_source": "x", "field": "y"}]},
            "actions": [{"type": "alert"}],
        },
    }
    with patch.object(loop, "_call_save_strategy",
                      AsyncMock(return_value=("strat-uuid-12345", None))), \
         patch("agent.orchestration.cocreation_state_machine.append_message"), \
         patch("agent.orchestration.cocreation_state_machine.transition",
               return_value=(True, None)) as mock_trans:
        r = await loop._handle_confirming(fake_state, "确认保存")
    assert r.stage == "saved"
    assert r.saved_strategy_id == "strat-uuid-12345"
    args, kwargs = mock_trans.call_args
    assert args[1] == "saved"


@pytest.mark.asyncio
async def test_confirming_save_failure_stays():
    """T12 失败 → 留 confirming + 提示重试。"""
    loop = CocreationLoop()
    fake_state = {
        "conversation_id": "conv-1", "device_id": "u-1",
        "stage": "confirming", "messages": [], "draft_data": {"name": "X"},
    }
    with patch.object(loop, "_call_save_strategy",
                      AsyncMock(return_value=(None, "quota_exceeded"))), \
         patch("agent.orchestration.cocreation_state_machine.append_message"):
        r = await loop._handle_confirming(fake_state, "确认")
    assert r.ok is False
    assert r.stage == "confirming"
    assert "quota_exceeded" in (r.error or "")


@pytest.mark.asyncio
async def test_confirming_feedback_returns_to_refining():
    """用户给非确认词 → 回 refining。"""
    loop = CocreationLoop()
    fake_state = {
        "conversation_id": "conv-1", "device_id": "u-1",
        "stage": "confirming", "messages": [],
        "draft_data": {"name": "X"},
    }
    with patch("agent.orchestration.cocreation_state_machine.append_message"), \
         patch("agent.orchestration.cocreation_state_machine.transition",
               return_value=(True, None)) as mock_trans:
        r = await loop._handle_confirming(fake_state, "再加一个止盈条件")
    assert r.stage == "refining"
    args, _ = mock_trans.call_args
    assert args[1] == "refining"


# ── _invoke_llm ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invoke_llm_no_api_key_returns_fallback():
    loop = CocreationLoop()
    loop._api_key = ""  # 强制没 key
    text, src, err = await loop._invoke_llm(
        "P01", "u-1", "msg", {}, fallback_text="FALLBACK",
    )
    assert text == "FALLBACK"
    assert src == "rule_engine"
    assert err == "no_api_key"


@pytest.mark.asyncio
async def test_invoke_llm_anthropic_failure_returns_fallback():
    loop = CocreationLoop()
    loop._api_key = "sk-test"
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.side_effect = Exception("API down")
    with patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        text, src, err = await loop._invoke_llm(
            "P01", "u-1", "msg", {}, fallback_text="FALLBACK",
        )
    assert text == "FALLBACK"
    assert src == "rule_engine"
    assert "llm_failed" in err


@pytest.mark.asyncio
async def test_invoke_llm_success():
    loop = CocreationLoop()
    loop._api_key = "sk-test"
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text="LLM RESPONSE")]
    fake_client = MagicMock()
    fake_client.messages.create = MagicMock(return_value=fake_resp)
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = fake_client
    with patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        text, src, err = await loop._invoke_llm(
            "P01", "u-1", "msg", {}, fallback_text="FALLBACK",
        )
    assert text == "LLM RESPONSE"
    assert src == "llm"
    assert err is None


# ── _call_save_strategy ─────────────────────────────────────

@pytest.mark.asyncio
async def test_call_save_strategy_success():
    loop = CocreationLoop()
    fake_tool = MagicMock()
    fake_result = MagicMock()
    fake_result.ok = True
    fake_result.output = {"ok": True, "strategy": {"id": "s-100"}}
    import asyncio as _aio
    fake_tool.run = AsyncMock(return_value=fake_result)
    with patch("agent.tools.SaveStrategyTool", return_value=fake_tool):
        sid, err = await loop._call_save_strategy("u-1", {"name": "X"})
    assert sid == "s-100"
    assert err is None


@pytest.mark.asyncio
async def test_call_save_strategy_failure():
    loop = CocreationLoop()
    fake_tool = MagicMock()
    fake_result = MagicMock()
    fake_result.ok = True
    fake_result.output = {"ok": False, "reason": "spec_invalid"}
    fake_tool.run = AsyncMock(return_value=fake_result)
    with patch("agent.tools.SaveStrategyTool", return_value=fake_tool):
        sid, err = await loop._call_save_strategy("u-1", {})
    assert sid is None
    assert err == "spec_invalid"


# ── helpers for pytest ──────────────────────────────────────

def _async_value(v):
    """生成已完成的 Future,值为 v(给 mock 用)。"""
    import asyncio
    fut = asyncio.Future()
    fut.set_result(v)
    return fut
