"""
Semantic Shadow Mode 14d 评估测试 — R37 P0-4
跑法:python3 -m pytest tests/test_shadow_eval.py -v

验证 evaluate_shadow_rules 三态:
  1. match_count < 3 → dormant(rule 14d 内从未触发)
  2. 胜率 < 40% (samples >= 3) → failed(set is_active=False)
  3. 胜率 >= 40% (samples >= 3) → graduated(清 shadow_mode_until)
  4. match_count >= 3 但无 comply 数据 → 延 7d
  5. shadow_mode_until > now → 不动
  6. db 查询失败 → errors >= 1 不抛
"""
from __future__ import annotations
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _mock_db(rules: list, update_capture: list | None = None):
    """构造 mock DB chain。update 操作存到 update_capture 列表。"""
    db = MagicMock()
    update_capture = update_capture if update_capture is not None else []

    def _table(name):
        m = MagicMock()
        # select chain
        chain = MagicMock()
        chain.execute.return_value.data = rules
        m.select.return_value.eq.return_value.eq.return_value.lte.return_value = chain

        # update chain — capture payload
        def _update(payload):
            up_chain = MagicMock()
            def _eq(*args, **kwargs):
                eq_chain = MagicMock()
                eq_chain.execute.return_value.data = []
                update_capture.append({"payload": payload, "id": args[1] if len(args) > 1 else None})
                return eq_chain
            up_chain.eq = _eq
            return up_chain
        m.update = _update
        return m

    db.table = _table
    return db


def _shadow_rule(
    rule_id: str = "r1",
    match_count: int = 0,
    comply_win: int = 0,
    comply_lose: int = 0,
    expired: bool = True,
    content: str = "test rule",
):
    return {
        "id": rule_id,
        "match_count": match_count,
        "comply_win": comply_win,
        "comply_lose": comply_lose,
        "shadow_mode_until": (
            (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            if expired else
            (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        ),
        "content": content,
        "metadata": {},
        "is_active": True,
    }


# ── 三态 ─────────────────────────────────────────────────────


def test_evaluate_dormant_when_no_matches():
    from agent.memory.semantic_memory import SemanticMemory
    sm = SemanticMemory()
    captured = []
    db = _mock_db([_shadow_rule(match_count=0)], captured)
    with patch("agent.memory.semantic_memory.get_db", return_value=db):
        counts = sm.evaluate_shadow_rules()
    assert counts["dormant"] == 1
    assert counts["graduated"] == 0
    assert counts["failed"] == 0
    # is_active=False
    assert captured[0]["payload"]["is_active"] is False
    assert captured[0]["payload"]["metadata"]["shadow_outcome"] == "dormant"


def test_evaluate_failed_when_low_win_rate():
    from agent.memory.semantic_memory import SemanticMemory
    sm = SemanticMemory()
    captured = []
    # 30% 胜率
    db = _mock_db([_shadow_rule(match_count=10, comply_win=3, comply_lose=7)], captured)
    with patch("agent.memory.semantic_memory.get_db", return_value=db):
        counts = sm.evaluate_shadow_rules()
    assert counts["failed"] == 1
    assert counts["graduated"] == 0
    assert captured[0]["payload"]["is_active"] is False
    assert captured[0]["payload"]["metadata"]["shadow_outcome"] == "failed"


def test_evaluate_graduated_when_high_win_rate():
    from agent.memory.semantic_memory import SemanticMemory
    sm = SemanticMemory()
    captured = []
    # 70% 胜率
    db = _mock_db([_shadow_rule(match_count=10, comply_win=7, comply_lose=3)], captured)
    with patch("agent.memory.semantic_memory.get_db", return_value=db):
        counts = sm.evaluate_shadow_rules()
    assert counts["graduated"] == 1
    assert counts["dormant"] == 0
    # graduated 不动 is_active(默认 True),只清 shadow_mode_until
    assert "is_active" not in captured[0]["payload"]
    assert captured[0]["payload"]["shadow_mode_until"] is None
    assert captured[0]["payload"]["metadata"]["shadow_outcome"] == "graduated"


def test_evaluate_extends_when_no_comply_data():
    """match_count >= 3 但无 win/lose 记录 → 延 7d。"""
    from agent.memory.semantic_memory import SemanticMemory
    sm = SemanticMemory()
    captured = []
    db = _mock_db([_shadow_rule(match_count=5, comply_win=0, comply_lose=0)], captured)
    with patch("agent.memory.semantic_memory.get_db", return_value=db):
        counts = sm.evaluate_shadow_rules()
    # 既不 graduated 也不 dormant 也不 failed,只延期
    assert counts["graduated"] == 0
    assert counts["dormant"] == 0
    assert counts["failed"] == 0
    # 延期 update 写了 shadow_mode_until 新值
    assert "shadow_mode_until" in captured[0]["payload"]
    extended = captured[0]["payload"]["shadow_mode_until"]
    assert extended is not None  # 7 天后


def test_evaluate_empty_rules():
    """无 expired shadow rules → 全 0。"""
    from agent.memory.semantic_memory import SemanticMemory
    sm = SemanticMemory()
    db = _mock_db([])
    with patch("agent.memory.semantic_memory.get_db", return_value=db):
        counts = sm.evaluate_shadow_rules()
    assert counts == {"graduated": 0, "dormant": 0, "failed": 0, "errors": 0}


def test_evaluate_db_failure():
    """get_db 抛错 → errors >= 1 不抛。"""
    from agent.memory.semantic_memory import SemanticMemory
    sm = SemanticMemory()
    db = MagicMock()
    db.table.side_effect = RuntimeError("PG down")
    with patch("agent.memory.semantic_memory.get_db", return_value=db):
        counts = sm.evaluate_shadow_rules()
    assert counts["errors"] >= 1


def test_evaluate_mixed_three_categories():
    """单次扫描混合三态 → 各 1。"""
    from agent.memory.semantic_memory import SemanticMemory
    sm = SemanticMemory()
    captured = []
    rules = [
        _shadow_rule("r-dormant", match_count=0),
        _shadow_rule("r-failed", match_count=10, comply_win=2, comply_lose=8),
        _shadow_rule("r-graduated", match_count=10, comply_win=7, comply_lose=3),
    ]
    db = _mock_db(rules, captured)
    with patch("agent.memory.semantic_memory.get_db", return_value=db):
        counts = sm.evaluate_shadow_rules()
    assert counts["dormant"] == 1
    assert counts["failed"] == 1
    assert counts["graduated"] == 1
    assert len(captured) == 3
