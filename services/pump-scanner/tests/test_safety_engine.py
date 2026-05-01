"""
Safety Engine 单元测试 — Phase 0 W3
引用 docs/agent-pm/09-eval-plan.md L1 unit
引用 services/pump-scanner/agent/safety_engine.py
引用 services/pump-scanner/agent/safety_policy.yaml v0.2

覆盖:
  yaml 加载 / fail-safe BLOCKED
  10 条 HR 各正反两路
  5 条 C 完整覆盖
  evaluator 各 check type
  format_message 替换

跑法:
  cd services/pump-scanner
  python -m pytest tests/test_safety_engine.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.safety_engine import (  # noqa: E402
    CheckOutcome,
    SafetyEngine,
    _eval_check,
    _format_message,
    c2_thesis_risks_min_2,
    c3_thesis_evidence_non_empty,
    c5_hitl_completeness,
    get_safety_engine,
    reset_safety_engine_singleton,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def engine() -> SafetyEngine:
    """全新 SafetyEngine,默认加载真实 yaml。"""
    e = SafetyEngine()
    e.load()
    assert e.loaded, f"yaml 加载失败: {e.load_error}"
    return e


@pytest.fixture
def base_ctx() -> dict:
    """合规默认 ctx(应通过所有 HR)。"""
    return {
        "amount_usd": 100.0,
        "daily_total_usd": 500.0,
        "strategy_position_pct": 0.05,
        "liquidity_usd": 50000.0,
        "is_honeypot": False,
        "regime": "TRENDING_UP",
        "action": "buy",
        "token_address": "Mock1111",
        "blacklist_tokens": [],
        "seconds_since_last_trade": 600,
        "hitl_required": False,
        "hitl_approved": True,
        "agent_global_state": "normal",
    }


# ============================================================
# 1. yaml 加载 + fail-safe
# ============================================================

class TestLoading:

    def test_load_succeeds(self, engine: SafetyEngine):
        assert engine.loaded
        assert len(engine.hard_rules) >= 10
        assert len(engine.constitutional) == 5
        # 至少 10 条 HR 标 implemented=True
        impl = [r for r in engine.hard_rules if r.get("implemented")]
        assert len(impl) >= 10

    def test_failsafe_when_yaml_missing(self, tmp_path):
        e = SafetyEngine()
        bad_path = tmp_path / "nonexistent.yaml"
        e.load(path=bad_path)
        assert not e.loaded
        # 任何 check 都返 CB12 BLOCK
        results = e.check_trade({"amount_usd": 1.0})
        assert len(results) == 1
        assert results[0].rule_id == "CB12"
        assert results[0].outcome == CheckOutcome.BLOCK

    def test_failsafe_when_yaml_corrupt(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(": not yaml :\n  - oops\n", encoding="utf-8")
        e = SafetyEngine()
        e.load(path=bad)
        assert not e.loaded
        results = e.check_trade({})
        assert results[0].rule_id == "CB12"

    def test_singleton(self):
        reset_safety_engine_singleton()
        e1 = get_safety_engine()
        e2 = get_safety_engine()
        assert e1 is e2


# ============================================================
# 2. 10 条核心 HR — 各正反两路(20 测试)
# ============================================================

class TestHardRules:

    def test_hr01_amount_under_500_pass(self, engine, base_ctx):
        base_ctx["amount_usd"] = 250.0
        assert not _ids(engine.check_trade(base_ctx)).intersection({"HR01"})

    def test_hr01_amount_over_500_block(self, engine, base_ctx):
        base_ctx["amount_usd"] = 750.0
        assert "HR01" in _ids(engine.check_trade(base_ctx))

    def test_hr02_daily_total_under_2000_pass(self, engine, base_ctx):
        base_ctx["daily_total_usd"] = 1500
        assert "HR02" not in _ids(engine.check_trade(base_ctx))

    def test_hr02_daily_total_over_2000_block(self, engine, base_ctx):
        base_ctx["daily_total_usd"] = 2500
        assert "HR02" in _ids(engine.check_trade(base_ctx))

    def test_hr04_position_pct_pass(self, engine, base_ctx):
        base_ctx["strategy_position_pct"] = 0.08
        assert "HR04" not in _ids(engine.check_trade(base_ctx))

    def test_hr04_position_pct_block(self, engine, base_ctx):
        base_ctx["strategy_position_pct"] = 0.15
        assert "HR04" in _ids(engine.check_trade(base_ctx))

    def test_hr07_liquidity_pass(self, engine, base_ctx):
        base_ctx["liquidity_usd"] = 50000
        assert "HR07" not in _ids(engine.check_trade(base_ctx))

    def test_hr07_liquidity_block(self, engine, base_ctx):
        base_ctx["liquidity_usd"] = 5000
        assert "HR07" in _ids(engine.check_trade(base_ctx))

    def test_hr09_honeypot_false_pass(self, engine, base_ctx):
        base_ctx["is_honeypot"] = False
        assert "HR09" not in _ids(engine.check_trade(base_ctx))

    def test_hr09_honeypot_true_block(self, engine, base_ctx):
        base_ctx["is_honeypot"] = True
        assert "HR09" in _ids(engine.check_trade(base_ctx))

    def test_hr16_regime_normal_buy_pass(self, engine, base_ctx):
        base_ctx["regime"] = "TRENDING_UP"
        base_ctx["action"] = "buy"
        assert "HR16" not in _ids(engine.check_trade(base_ctx))

    def test_hr16_regime_crisis_buy_block(self, engine, base_ctx):
        base_ctx["regime"] = "CRISIS"
        base_ctx["action"] = "buy"
        assert "HR16" in _ids(engine.check_trade(base_ctx))

    def test_hr16_regime_crisis_sell_pass(self, engine, base_ctx):
        # CRISIS 只禁 buy,sell 应通过
        base_ctx["regime"] = "CRISIS"
        base_ctx["action"] = "sell"
        assert "HR16" not in _ids(engine.check_trade(base_ctx))

    def test_hr21_blacklist_clean_pass(self, engine, base_ctx):
        base_ctx["token_address"] = "Token1"
        base_ctx["blacklist_tokens"] = ["BadToken"]
        assert "HR21" not in _ids(engine.check_trade(base_ctx))

    def test_hr21_blacklist_hit_block(self, engine, base_ctx):
        base_ctx["token_address"] = "BadToken"
        base_ctx["blacklist_tokens"] = ["BadToken", "WorseToken"]
        assert "HR21" in _ids(engine.check_trade(base_ctx))

    def test_hr22_interval_long_pass(self, engine, base_ctx):
        base_ctx["seconds_since_last_trade"] = 600
        assert "HR22" not in _ids(engine.check_trade(base_ctx))

    def test_hr22_interval_short_block(self, engine, base_ctx):
        base_ctx["seconds_since_last_trade"] = 30
        assert "HR22" in _ids(engine.check_trade(base_ctx))

    def test_hr25_hitl_not_required_pass(self, engine, base_ctx):
        base_ctx["hitl_required"] = False
        assert "HR25" not in _ids(engine.check_trade(base_ctx))

    def test_hr25_hitl_required_approved_pass(self, engine, base_ctx):
        base_ctx["hitl_required"] = True
        base_ctx["hitl_approved"] = True
        assert "HR25" not in _ids(engine.check_trade(base_ctx))

    def test_hr25_hitl_required_unapproved_block(self, engine, base_ctx):
        base_ctx["hitl_required"] = True
        base_ctx["hitl_approved"] = False
        assert "HR25" in _ids(engine.check_trade(base_ctx))

    def test_hr28_state_normal_pass(self, engine, base_ctx):
        base_ctx["agent_global_state"] = "normal"
        assert "HR28" not in _ids(engine.check_trade(base_ctx))

    def test_hr28_state_blocked_block(self, engine, base_ctx):
        base_ctx["agent_global_state"] = "blocked"
        assert "HR28" in _ids(engine.check_trade(base_ctx))

    def test_clean_ctx_pass_all(self, engine, base_ctx):
        """合规 ctx 不应触发任何 HR。"""
        results = engine.check_trade(base_ctx)
        assert results == [], f"clean ctx 触发: {[r.rule_id for r in results]}"

    def test_multiple_violations_all_reported(self, engine, base_ctx):
        """多条违规同时触发应全部返回。"""
        base_ctx["amount_usd"] = 750
        base_ctx["liquidity_usd"] = 1000
        base_ctx["is_honeypot"] = True
        ids = _ids(engine.check_trade(base_ctx))
        assert {"HR01", "HR07", "HR09"}.issubset(ids)


# ============================================================
# 3. Constitutional Rules (C1-C5)
# ============================================================

class TestConstitutional:

    def test_c1_clean_text_pass(self, engine):
        results = engine.check_constitutional("这是一份理性分析,有风险.")
        assert "C1" not in _ids(results)

    @pytest.mark.parametrize("text,reason", [
        ("这只币稳的,买就完事", "稳的"),
        ("百倍机会,错过就亏", "百倍"),
        ("guaranteed 10x return", "guaranteed/10x"),
        ("到 moon!ape in!", "moon/ape in"),
        ("千倍涨幅,不容错过", "千倍"),
    ])
    def test_c1_blocklist_hit(self, engine, text, reason):
        results = engine.check_constitutional(text)
        assert "C1" in _ids(results), f"{reason} 应触发 C1"

    def test_c1_case_insensitive(self, engine):
        results = engine.check_constitutional("GUARANTEED Profit")
        assert "C1" in _ids(results)

    def test_c2_risks_two_pass(self, engine):
        thesis = {"risks": ["流动性风险", "大户砸盘"], "evidence": [{"source": "x"}]}
        results = engine.check_constitutional("ok", thesis=thesis)
        assert "C2" not in _ids(results)

    def test_c2_risks_one_block(self, engine):
        thesis = {"risks": ["only one"], "evidence": [{"source": "x"}]}
        results = engine.check_constitutional("ok", thesis=thesis)
        assert "C2" in _ids(results)

    def test_c2_risks_empty_block(self, engine):
        thesis = {"risks": [], "evidence": [{"source": "x"}]}
        results = engine.check_constitutional("ok", thesis=thesis)
        assert "C2" in _ids(results)

    def test_c3_evidence_non_empty_pass(self, engine):
        thesis = {
            "risks": ["a", "b"],
            "evidence": [{"source": "smart_money_signals", "value": "+45000"}],
        }
        results = engine.check_constitutional("ok", thesis=thesis)
        assert "C3" not in _ids(results)

    def test_c3_evidence_empty_block(self, engine):
        thesis = {"risks": ["a", "b"], "evidence": []}
        results = engine.check_constitutional("ok", thesis=thesis)
        assert "C3" in _ids(results)

    def test_c3_evidence_missing_source_block(self, engine):
        thesis = {"risks": ["a", "b"], "evidence": [{"value": "x"}]}
        results = engine.check_constitutional("ok", thesis=thesis)
        assert "C3" in _ids(results)

    def test_c5_hitl_complete_pass(self, engine):
        hitl = {
            "hitl_required": True,
            "approval_id": "u1",
            "signature": "sig",
            "audit_log_id": "a1",
        }
        results = engine.check_constitutional("ok", hitl_ctx=hitl)
        assert "C5" not in _ids(results)

    def test_c5_hitl_not_required_pass(self, engine):
        hitl = {"hitl_required": False}
        results = engine.check_constitutional("ok", hitl_ctx=hitl)
        assert "C5" not in _ids(results)

    def test_c5_hitl_missing_signature_block(self, engine):
        hitl = {
            "hitl_required": True,
            "approval_id": "u1",
            "signature": None,
            "audit_log_id": "a1",
        }
        results = engine.check_constitutional("ok", hitl_ctx=hitl)
        assert "C5" in _ids(results)


# ============================================================
# 4. Evaluator 单元(_eval_check 各 type)
# ============================================================

class TestEvaluator:

    def test_simple_gt(self):
        assert _eval_check({"type": "simple", "field": "x", "op": "gt", "value": 5}, {"x": 10})
        assert not _eval_check({"type": "simple", "field": "x", "op": "gt", "value": 5}, {"x": 3})

    def test_simple_lt(self):
        assert _eval_check({"type": "simple", "field": "x", "op": "lt", "value": 5}, {"x": 3})
        assert not _eval_check({"type": "simple", "field": "x", "op": "lt", "value": 5}, {"x": 10})

    def test_simple_in_with_value_field(self):
        check = {"type": "simple", "field": "tok", "op": "in", "value_field": "blist"}
        assert _eval_check(check, {"tok": "X", "blist": ["X", "Y"]})
        assert not _eval_check(check, {"tok": "Z", "blist": ["X", "Y"]})

    def test_boolean(self):
        assert _eval_check({"type": "boolean", "field": "flag"}, {"flag": True})
        assert not _eval_check({"type": "boolean", "field": "flag"}, {"flag": False})

    def test_compound_and(self):
        check = {
            "type": "compound", "op": "AND",
            "items": [
                {"type": "simple", "field": "a", "op": "eq", "value": 1},
                {"type": "simple", "field": "b", "op": "eq", "value": 2},
            ],
        }
        assert _eval_check(check, {"a": 1, "b": 2})
        assert not _eval_check(check, {"a": 1, "b": 3})

    def test_compound_or(self):
        check = {
            "type": "compound", "op": "OR",
            "items": [
                {"type": "simple", "field": "a", "op": "eq", "value": 1},
                {"type": "simple", "field": "b", "op": "eq", "value": 2},
            ],
        }
        assert _eval_check(check, {"a": 1, "b": 999})
        assert _eval_check(check, {"a": 999, "b": 2})
        assert not _eval_check(check, {"a": 999, "b": 999})

    def test_regex_with_flags(self):
        check = {"type": "regex", "field": "t", "pattern": "(?:foo)", "flags": "IGNORECASE"}
        assert _eval_check(check, {"t": "FOO bar"})
        assert _eval_check(check, {"t": "foo bar"})
        assert not _eval_check(check, {"t": "baz"})

    def test_function_dispatch(self):
        check = {"type": "function", "fn": "c2_thesis_risks_min_2"}
        assert _eval_check(check, {"thesis": {"risks": ["only"]}})
        assert not _eval_check(check, {"thesis": {"risks": ["a", "b"]}})

    def test_unknown_type_returns_false(self):
        assert not _eval_check({"type": "made_up"}, {})

    def test_missing_field_no_crash(self):
        # ctx 里没该字段,应该不触发(不抛异常)
        assert not _eval_check(
            {"type": "simple", "field": "missing", "op": "gt", "value": 5},
            {},
        )


class TestMessageFormatting:

    def test_format_replaces_fields(self):
        msg = "amount=${amount} threshold=${threshold}"
        out = _format_message(msg, {"amount": 750, "threshold": 500})
        assert out == "amount=750 threshold=500"

    def test_format_empty_template(self):
        assert _format_message("", {"a": 1}) == ""

    def test_format_unknown_field_kept_as_placeholder(self):
        out = _format_message("x=${unknown}", {})
        assert "${unknown}" in out


# ============================================================
# 5. 单独 Python 函数(C 规则的 fn)
# ============================================================

class TestCFunctions:

    def test_c2_function_directly(self):
        assert c2_thesis_risks_min_2({"thesis": {}})  # 缺 risks
        assert c2_thesis_risks_min_2({"thesis": {"risks": []}})
        assert c2_thesis_risks_min_2({"thesis": {"risks": ["one"]}})
        assert not c2_thesis_risks_min_2({"thesis": {"risks": ["a", "b"]}})

    def test_c3_function_directly(self):
        assert c3_thesis_evidence_non_empty({"thesis": {}})
        assert c3_thesis_evidence_non_empty({"thesis": {"evidence": []}})
        # 缺 source 也算违反
        assert c3_thesis_evidence_non_empty({"thesis": {"evidence": [{"value": "x"}]}})
        assert not c3_thesis_evidence_non_empty(
            {"thesis": {"evidence": [{"source": "smart_money", "value": "+1k"}]}}
        )

    def test_c5_hitl_required_full(self):
        ctx = {
            "hitl_required": True,
            "approval_id": "a1",
            "signature": "sig",
            "audit_log_id": "audit-1",
        }
        assert not c5_hitl_completeness(ctx)

    def test_c5_hitl_not_required(self):
        assert not c5_hitl_completeness({"hitl_required": False})

    def test_c5_hitl_missing_one(self):
        for missing in ("approval_id", "signature", "audit_log_id"):
            ctx = {
                "hitl_required": True,
                "approval_id": "a",
                "signature": "s",
                "audit_log_id": "x",
            }
            ctx[missing] = None
            assert c5_hitl_completeness(ctx), f"缺 {missing} 应触发 C5"


# ============================================================
# helpers
# ============================================================

def _ids(results) -> set[str]:
    return {r.rule_id for r in results}
