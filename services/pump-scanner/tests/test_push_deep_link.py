"""
push_service.build_deep_link 单元测试 — W3 D5+

跑法: python3 -m pytest tests/test_push_deep_link.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.push_service import build_deep_link  # noqa: E402


def test_strategy_triggered_with_id():
    assert build_deep_link("strategy_triggered", strategy_id="abc-123") == "aitrading://strategy/abc-123"


def test_strategy_triggered_missing_id_falls_to_home():
    assert build_deep_link("strategy_triggered") == "aitrading://home"


def test_hitl_approval():
    link = build_deep_link("hitl_approval", approval_id="appr-001")
    assert link == "aitrading://hitl/appr-001"


def test_hitl_missing_id():
    assert build_deep_link("hitl_approval") == "aitrading://home"


def test_review_default_period():
    assert build_deep_link("review_ready") == "aitrading://review/daily"


def test_review_custom_period():
    assert build_deep_link("review_ready", period="weekly") == "aitrading://review/weekly"


def test_token_alert():
    assert build_deep_link(
        "token_alert", chain="SOL", address="So11111"
    ) == "aitrading://token/SOL/So11111"


def test_token_alert_missing_chain_falls_to_home():
    assert build_deep_link("token_alert", address="x") == "aitrading://home"


def test_rule_proposal():
    assert build_deep_link(
        "rule_proposal", proposal_id="rp-001"
    ) == "aitrading://memory/proposals/rp-001"


def test_rule_proposal_missing():
    assert build_deep_link("rule_proposal") == "aitrading://memory"


def test_unknown_category_falls_to_home():
    assert build_deep_link("unknown_x") == "aitrading://home"


def test_special_chars_url_encoded():
    """ID 含特殊字符要 URL encode。"""
    link = build_deep_link("strategy_triggered", strategy_id="a/b c#d")
    assert "%2F" in link or "%2f" in link  # /
    assert "%20" in link  # space
    assert "%23" in link  # #
