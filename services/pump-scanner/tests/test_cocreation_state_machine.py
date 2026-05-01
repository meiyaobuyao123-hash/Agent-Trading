"""
共创状态机单元测试 — W3 D5+
覆盖:
  - is_valid_transition 各种合法 / 非法转移
  - suggest_next_stage 启发式
  - load/create/append/transition/cleanup(mock psycopg2 connection)

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_cocreation_state_machine.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.orchestration.cocreation_state_machine import (  # noqa: E402
    VALID_STAGES,
    STAGE_TRANSITIONS,
    is_valid_transition,
    suggest_next_stage,
    load_active_state,
    create_state,
    append_message,
    transition,
    cleanup_expired,
)


# ── is_valid_transition ─────────────────────────────────────

def test_valid_transitions_clarifying_to_refining():
    assert is_valid_transition("clarifying", "refining") is True


def test_valid_transitions_refining_to_dry_run():
    assert is_valid_transition("refining", "dry_run") is True


def test_valid_transitions_confirming_to_saved():
    assert is_valid_transition("confirming", "saved") is True


def test_valid_transitions_any_to_aborted():
    for s in ("clarifying", "refining", "dry_run", "confirming"):
        assert is_valid_transition(s, "aborted") is True


def test_invalid_transition_terminal_stays_terminal():
    assert is_valid_transition("saved", "refining") is False
    assert is_valid_transition("aborted", "refining") is False


def test_invalid_transition_skip_stages():
    """clarifying 不能直接到 saved。"""
    assert is_valid_transition("clarifying", "saved") is False


def test_invalid_transition_unknown_stage():
    assert is_valid_transition("foo", "refining") is False


# ── suggest_next_stage ──────────────────────────────────────

def test_suggest_clarifying_short_msg_stays():
    assert suggest_next_stage("clarifying", "嗯", has_draft=False) == "clarifying"


def test_suggest_clarifying_intent_word_advances():
    assert suggest_next_stage("clarifying", "我想做聪明钱跟单", has_draft=False) == "refining"


def test_suggest_clarifying_long_msg_advances():
    text = "我想要一个能在 SOL 链上跟单 elite 聪明钱的策略"
    assert suggest_next_stage("clarifying", text, has_draft=False) == "refining"


def test_suggest_abort_word_terminates():
    assert suggest_next_stage("refining", "算了不要了", has_draft=True) == "aborted"
    assert suggest_next_stage("clarifying", "取消", has_draft=False) == "aborted"


def test_suggest_refining_satisfied_advances():
    assert suggest_next_stage("refining", "好的", has_draft=True, user_satisfied=True) == "dry_run"


def test_suggest_refining_confirm_word_advances():
    assert suggest_next_stage("refining", "ok 这样可以", has_draft=True) == "dry_run"


def test_suggest_refining_no_draft_stays():
    assert suggest_next_stage("refining", "ok", has_draft=False) == "refining"


def test_suggest_dry_run_default_to_confirming():
    assert suggest_next_stage("dry_run", "看看回测", has_draft=True) == "confirming"


def test_suggest_confirming_confirm_to_saved():
    assert suggest_next_stage("confirming", "确认保存", has_draft=True) == "saved"


def test_suggest_confirming_feedback_back_to_refining():
    assert suggest_next_stage("confirming", "再调整一下止损", has_draft=True) == "refining"


def test_suggest_terminal_stays():
    assert suggest_next_stage("saved", "再开一个", has_draft=False) == "saved"
    assert suggest_next_stage("aborted", "好", has_draft=False) == "aborted"


# ── DB integration (mock psycopg2 connection) ───────────────

def _make_fake_conn():
    """构造一个支持 cursor() / cursor().__enter__/__exit__ 的 mock。"""
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = None
    return conn, cur


def test_load_active_state_returns_none_when_empty():
    conn, cur = _make_fake_conn()
    cur.fetchone.return_value = None
    with patch("agent.orchestration.cocreation_state_machine._get_conn", return_value=conn):
        r = load_active_state("dev-1")
    assert r is None


def test_load_active_state_maps_row():
    from datetime import datetime, timezone
    conn, cur = _make_fake_conn()
    fake_row = (
        "conv-uuid", "dev-1", "signal-strategy-builder", "refining",
        [{"role": "user", "content": "hi", "ts": "2026-05-01T00:00:00Z"}],
        {"name": "draft1"}, None, None,
        datetime.now(timezone.utc), datetime.now(timezone.utc),
        datetime.now(timezone.utc), None,
    )
    cur.fetchone.return_value = fake_row
    with patch("agent.orchestration.cocreation_state_machine._get_conn", return_value=conn):
        r = load_active_state("dev-1")
    assert r is not None
    assert r["conversation_id"] == "conv-uuid"
    assert r["stage"] == "refining"
    assert len(r["messages"]) == 1


def test_create_state_inserts_with_initial_message():
    from datetime import datetime, timezone
    conn, cur = _make_fake_conn()
    now = datetime.now(timezone.utc)
    cur.fetchone.return_value = (
        "new-id", "dev-2", "signal-strategy-builder", "clarifying",
        [{"role": "user", "content": "make me a strat", "ts": now.isoformat()}],
        None, None, None, now, now, now, None,
    )
    with patch("agent.orchestration.cocreation_state_machine._get_conn", return_value=conn):
        r = create_state("dev-2", "signal-strategy-builder", "make me a strat")
    assert r is not None
    assert r["stage"] == "clarifying"
    # 验证 INSERT 被调用
    cur.execute.assert_called_once()


def test_append_message_truncates_to_keep_last_n():
    conn, cur = _make_fake_conn()
    # 现有 20 条 message,加 1 条应该截断回 20 条
    existing = [{"role": "user", "content": f"m{i}", "ts": "x"} for i in range(20)]
    cur.fetchone.return_value = (existing,)
    with patch("agent.orchestration.cocreation_state_machine._get_conn", return_value=conn):
        ok = append_message("conv-1", "user", "m20")
    assert ok is True
    # 第 2 次 execute 是 UPDATE 写回的 truncated list
    update_call = cur.execute.call_args_list[1]
    new_messages_json = update_call.args[1][0]
    import json as _json
    new = _json.loads(new_messages_json)
    assert len(new) == 20  # keep_last_n
    assert new[-1]["content"] == "m20"


def test_append_message_invalid_role_returns_false():
    assert append_message("conv-x", "robot", "hi") is False


def test_transition_invalid_stage_400():
    ok, err = transition("conv-1", "weird_stage")
    assert ok is False
    assert "invalid stage" in err


def test_transition_valid_path():
    conn, cur = _make_fake_conn()
    cur.fetchone.return_value = ("clarifying",)  # 当前 stage
    with patch("agent.orchestration.cocreation_state_machine._get_conn", return_value=conn):
        ok, err = transition("conv-1", "refining")
    assert ok is True
    assert err is None


def test_transition_invalid_path():
    conn, cur = _make_fake_conn()
    cur.fetchone.return_value = ("clarifying",)
    with patch("agent.orchestration.cocreation_state_machine._get_conn", return_value=conn):
        ok, err = transition("conv-1", "saved")
    assert ok is False
    assert "invalid transition" in err


def test_transition_with_draft_data():
    conn, cur = _make_fake_conn()
    cur.fetchone.return_value = ("clarifying",)
    with patch("agent.orchestration.cocreation_state_machine._get_conn", return_value=conn):
        ok, err = transition("conv-1", "refining", draft_data={"name": "draft"})
    assert ok is True
    # UPDATE 调用应该包含 draft_data 字段
    upd_call = cur.execute.call_args_list[1]
    assert "draft_data" in upd_call.args[0]


def test_cleanup_expired_returns_count():
    conn, cur = _make_fake_conn()
    cur.rowcount = 7
    with patch("agent.orchestration.cocreation_state_machine._get_conn", return_value=conn):
        n = cleanup_expired()
    assert n == 7


def test_load_active_state_db_failure_returns_none():
    with patch("agent.orchestration.cocreation_state_machine._get_conn",
               side_effect=Exception("PG down")):
        r = load_active_state("dev-x")
    assert r is None
