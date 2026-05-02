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
    BreakerState,
    CheckOutcome,
    SafetyEngine,
    _eval_check,
    _format_message,
    c2_thesis_risks_min_2,
    c3_thesis_evidence_non_empty,
    c5_hitl_completeness,
    get_safety_engine,
    hr10_within_authorization,
    hr11_credentials_revoked,
    hr24_slippage_within_limit,
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
    """合规默认 ctx(应通过所有 30 HR)。"""
    return {
        # HR01-04
        "amount_usd": 100.0,
        "daily_total_usd": 500.0,
        "monthly_total_usd": 5000.0,
        "strategy_position_pct": 0.05,
        "chain_concentration_pct": 0.20,
        "open_position_count": 5,
        # HR07-09
        "liquidity_usd": 50000.0,
        "buy_tax_pct": 0.02,
        "sell_tax_pct": 0.02,
        "is_honeypot": False,
        # HR10-12
        "auth_single_trade_max": 500.0,
        "credentials_revoked_at": None,
        "kms_unavailable": False,
        # HR13-15
        "holders_count": 2000,
        "top10_pct": 0.40,
        "price_change_24h_pct": 0.05,
        # HR16
        "regime": "TRENDING_UP",
        "action": "buy",
        # HR17-20
        "daily_loss_usd": 0,
        "weekly_loss_usd": 0,
        "consecutive_losses": 0,
        "max_drawdown_pct": 0.05,
        # HR21-25
        "token_address": "Mock1111",
        "blacklist_tokens": [],
        "seconds_since_last_trade": 600,
        "trades_last_hour": 1,
        "slippage_pct": 0.01,
        "max_slippage_pct": 0.05,
        "hitl_required": False,
        "hitl_approved": True,
        # HR26-30
        "strategy_stage": "saved",
        "copy_target_wallet": None,
        "blacklist_wallets": [],
        "token_age_seconds": 86400 * 7,    # 7 天
        "mode": "paper",
        "user_quota_exhausted": False,
        # 全局
        "agent_global_state": "normal",
    }


# ============================================================
# 1. yaml 加载 + fail-safe
# ============================================================

class TestLoading:

    def test_load_succeeds(self, engine: SafetyEngine):
        assert engine.loaded
        # v0.3 全部 30 HR + 13 CB + 5 C 都 implemented;R37 加 CB14 manual kill switch → 14 CB
        assert len(engine.hard_rules) == 30
        assert len(engine.circuit_breakers) == 14
        assert len(engine.constitutional) == 5
        impl_hr = [r for r in engine.hard_rules if r.get("implemented")]
        impl_cb = [r for r in engine.circuit_breakers if r.get("implemented")]
        assert len(impl_hr) == 30
        assert len(impl_cb) == 14  # R37 加 CB14
        # hr_to_cb_map 至少 5 条
        assert len(engine.hr_to_cb_map) >= 5
        # cb_index 应包含 14 条(CB01-CB14)
        assert len(engine._cb_index) == 14

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
# 6. 新增 20 条 HR 各 1-2 路(v0.3)
# ============================================================

class TestNewHardRules:
    """HR03/05/06/08/10/11/12/13/14/15/17/18/19/20/23/24/26/27/29/30"""

    def test_hr03_monthly_under_pass(self, engine, base_ctx):
        base_ctx["monthly_total_usd"] = 15000
        assert "HR03" not in _ids(engine.check_trade(base_ctx))

    def test_hr03_monthly_over_block(self, engine, base_ctx):
        base_ctx["monthly_total_usd"] = 25000
        assert "HR03" in _ids(engine.check_trade(base_ctx))

    def test_hr05_chain_conc_low_pass(self, engine, base_ctx):
        base_ctx["chain_concentration_pct"] = 0.30
        assert "HR05" not in _ids(engine.check_trade(base_ctx))

    def test_hr05_chain_conc_high_block(self, engine, base_ctx):
        base_ctx["chain_concentration_pct"] = 0.70
        assert "HR05" in _ids(engine.check_trade(base_ctx))

    def test_hr06_position_count_under_pass(self, engine, base_ctx):
        base_ctx["open_position_count"] = 10
        assert "HR06" not in _ids(engine.check_trade(base_ctx))

    def test_hr06_position_count_over_block(self, engine, base_ctx):
        base_ctx["open_position_count"] = 22
        assert "HR06" in _ids(engine.check_trade(base_ctx))

    def test_hr08_low_tax_pass(self, engine, base_ctx):
        base_ctx["buy_tax_pct"] = 0.05
        base_ctx["sell_tax_pct"] = 0.05
        assert "HR08" not in _ids(engine.check_trade(base_ctx))

    def test_hr08_high_buy_tax_block(self, engine, base_ctx):
        base_ctx["buy_tax_pct"] = 0.15
        assert "HR08" in _ids(engine.check_trade(base_ctx))

    def test_hr08_high_sell_tax_block(self, engine, base_ctx):
        base_ctx["sell_tax_pct"] = 0.20
        assert "HR08" in _ids(engine.check_trade(base_ctx))

    def test_hr10_within_auth_pass(self, engine, base_ctx):
        base_ctx["amount_usd"] = 100
        base_ctx["auth_single_trade_max"] = 500
        assert "HR10" not in _ids(engine.check_trade(base_ctx))

    def test_hr10_over_auth_block(self, engine, base_ctx):
        base_ctx["amount_usd"] = 400
        base_ctx["auth_single_trade_max"] = 200
        assert "HR10" in _ids(engine.check_trade(base_ctx))

    def test_hr10_missing_auth_block(self, engine, base_ctx):
        base_ctx["amount_usd"] = 100
        base_ctx["auth_single_trade_max"] = None
        assert "HR10" in _ids(engine.check_trade(base_ctx))

    def test_hr11_revoked_paper_pass(self, engine, base_ctx):
        # paper 模式即使 revoked 也通过 HR11(只禁真金)
        base_ctx["mode"] = "paper"
        base_ctx["credentials_revoked_at"] = "2026-04-01T00:00:00Z"
        assert "HR11" not in _ids(engine.check_trade(base_ctx))

    def test_hr11_revoked_live_block(self, engine, base_ctx):
        base_ctx["mode"] = "auto"
        base_ctx["credentials_revoked_at"] = "2026-04-01T00:00:00Z"
        assert "HR11" in _ids(engine.check_trade(base_ctx))

    def test_hr12_kms_available_pass(self, engine, base_ctx):
        base_ctx["kms_unavailable"] = False
        assert "HR12" not in _ids(engine.check_trade(base_ctx))

    def test_hr12_kms_unavailable_block(self, engine, base_ctx):
        base_ctx["kms_unavailable"] = True
        assert "HR12" in _ids(engine.check_trade(base_ctx))

    def test_hr13_holders_enough_pass(self, engine, base_ctx):
        base_ctx["holders_count"] = 200
        assert "HR13" not in _ids(engine.check_trade(base_ctx))

    def test_hr13_holders_few_block(self, engine, base_ctx):
        base_ctx["holders_count"] = 30
        assert "HR13" in _ids(engine.check_trade(base_ctx))

    def test_hr14_top10_low_pass(self, engine, base_ctx):
        base_ctx["top10_pct"] = 0.50
        assert "HR14" not in _ids(engine.check_trade(base_ctx))

    def test_hr14_top10_high_block(self, engine, base_ctx):
        base_ctx["top10_pct"] = 0.85
        assert "HR14" in _ids(engine.check_trade(base_ctx))

    def test_hr15_24h_drop_buy_block(self, engine, base_ctx):
        base_ctx["price_change_24h_pct"] = -0.45
        base_ctx["action"] = "buy"
        assert "HR15" in _ids(engine.check_trade(base_ctx))

    def test_hr15_24h_drop_sell_pass(self, engine, base_ctx):
        # 大跌允许卖
        base_ctx["price_change_24h_pct"] = -0.45
        base_ctx["action"] = "sell"
        assert "HR15" not in _ids(engine.check_trade(base_ctx))

    def test_hr15_normal_buy_pass(self, engine, base_ctx):
        base_ctx["price_change_24h_pct"] = -0.10
        assert "HR15" not in _ids(engine.check_trade(base_ctx))

    def test_hr17_daily_loss_under_pass(self, engine, base_ctx):
        base_ctx["daily_loss_usd"] = 200
        assert "HR17" not in _ids(engine.check_trade(base_ctx))

    def test_hr17_daily_loss_over_block(self, engine, base_ctx):
        base_ctx["daily_loss_usd"] = 600
        assert "HR17" in _ids(engine.check_trade(base_ctx))

    def test_hr18_weekly_loss_block(self, engine, base_ctx):
        base_ctx["weekly_loss_usd"] = 2000
        assert "HR18" in _ids(engine.check_trade(base_ctx))

    def test_hr19_consecutive_losses_block(self, engine, base_ctx):
        base_ctx["consecutive_losses"] = 4
        assert "HR19" in _ids(engine.check_trade(base_ctx))

    def test_hr20_max_drawdown_block(self, engine, base_ctx):
        base_ctx["max_drawdown_pct"] = 0.25
        assert "HR20" in _ids(engine.check_trade(base_ctx))

    def test_hr23_trades_last_hour_block(self, engine, base_ctx):
        base_ctx["trades_last_hour"] = 6
        assert "HR23" in _ids(engine.check_trade(base_ctx))

    def test_hr24_slippage_within_pass(self, engine, base_ctx):
        base_ctx["slippage_pct"] = 0.02
        base_ctx["max_slippage_pct"] = 0.05
        assert "HR24" not in _ids(engine.check_trade(base_ctx))

    def test_hr24_slippage_over_block(self, engine, base_ctx):
        base_ctx["slippage_pct"] = 0.10
        base_ctx["max_slippage_pct"] = 0.05
        assert "HR24" in _ids(engine.check_trade(base_ctx))

    def test_hr26_unsaved_strategy_activation_block(self, engine, base_ctx):
        base_ctx["action"] = "activate_strategy"
        base_ctx["strategy_stage"] = "clarifying"
        assert "HR26" in _ids(engine.check_trade(base_ctx))

    def test_hr26_saved_activation_pass(self, engine, base_ctx):
        base_ctx["action"] = "activate_strategy"
        base_ctx["strategy_stage"] = "saved"
        assert "HR26" not in _ids(engine.check_trade(base_ctx))

    def test_hr27_copy_blacklisted_block(self, engine, base_ctx):
        base_ctx["action"] = "copy_trade"
        base_ctx["copy_target_wallet"] = "BadWallet"
        base_ctx["blacklist_wallets"] = ["BadWallet", "WorseWallet"]
        assert "HR27" in _ids(engine.check_trade(base_ctx))

    def test_hr27_copy_clean_pass(self, engine, base_ctx):
        base_ctx["action"] = "copy_trade"
        base_ctx["copy_target_wallet"] = "GoodWallet"
        base_ctx["blacklist_wallets"] = ["BadWallet"]
        assert "HR27" not in _ids(engine.check_trade(base_ctx))

    def test_hr29_new_token_auto_block(self, engine, base_ctx):
        base_ctx["token_age_seconds"] = 1000     # < 1h
        base_ctx["mode"] = "auto"
        assert "HR29" in _ids(engine.check_trade(base_ctx))

    def test_hr29_new_token_paper_pass(self, engine, base_ctx):
        # paper 模式允许新币
        base_ctx["token_age_seconds"] = 1000
        base_ctx["mode"] = "paper"
        assert "HR29" not in _ids(engine.check_trade(base_ctx))

    def test_hr29_old_token_auto_pass(self, engine, base_ctx):
        # 老币 auto 通过
        base_ctx["token_age_seconds"] = 86400 * 30
        base_ctx["mode"] = "auto"
        assert "HR29" not in _ids(engine.check_trade(base_ctx))

    def test_hr30_quota_exhausted_block(self, engine, base_ctx):
        base_ctx["user_quota_exhausted"] = True
        assert "HR30" in _ids(engine.check_trade(base_ctx))

    def test_hr30_quota_ok_pass(self, engine, base_ctx):
        base_ctx["user_quota_exhausted"] = False
        assert "HR30" not in _ids(engine.check_trade(base_ctx))


# ============================================================
# 7. CB 状态管理(trip / release / auto-expire / persister)
# ============================================================

class TestCircuitBreakers:

    def test_trip_unknown_cb_ignored(self, engine):
        result = engine.trip_breaker("CB99", reason="bogus")
        assert result is None
        assert not engine.is_breaker_active("CB99")

    def test_trip_cb01_blocks_trade(self, engine, base_ctx):
        engine.trip_breaker("CB01", reason="manual test")
        assert engine.is_breaker_active("CB01")
        results = engine.check_trade(base_ctx)
        # base_ctx 是合规的,但 CB01 active 应该 BLOCK
        assert "CB01" in _ids(results)

    def test_release_breaker(self, engine):
        engine.trip_breaker("CB03", reason="test")
        assert engine.is_breaker_active("CB03")
        ok = engine.release_breaker("CB03")
        assert ok is True
        assert not engine.is_breaker_active("CB03")

    def test_release_unknown_returns_false(self, engine):
        assert engine.release_breaker("CB99") is False

    def test_idempotent_trip(self, engine):
        s1 = engine.trip_breaker("CB05", reason="r1")
        s2 = engine.trip_breaker("CB05", reason="r2")  # second trip 不更新
        assert s1 is s2
        assert s1.reason == "r1"

    def test_auto_expire(self, engine):
        """CB06 auto_release_after_min=10 → 模拟过期"""
        from datetime import datetime, timezone, timedelta
        engine.trip_breaker("CB06", reason="api err")
        # 强制改 auto_release_at 到过去
        state = engine._active_breakers["CB06"]
        state.auto_release_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        # 触发自动 release
        engine._release_expired_breakers()
        assert not engine.is_breaker_active("CB06")

    def test_get_active_breakers(self, engine):
        engine.trip_breaker("CB01", reason="x")
        engine.trip_breaker("CB13", reason="y")
        active = engine.get_active_breakers()
        assert {"CB01", "CB13"}.issubset(active.keys())
        assert isinstance(active["CB01"], BreakerState)

    def test_global_state_normal(self, engine):
        assert engine.get_global_state() == "normal"

    def test_global_state_blocked(self, engine):
        engine.trip_breaker("CB01", reason="x")  # severity=blocked
        assert engine.get_global_state() == "blocked"

    def test_global_state_degraded(self, engine):
        engine.trip_breaker("CB03", reason="x")  # severity=degraded
        assert engine.get_global_state() == "degraded"

    def test_global_state_blocked_wins_over_degraded(self, engine):
        engine.trip_breaker("CB03", reason="x")  # degraded
        engine.trip_breaker("CB01", reason="y")  # blocked
        assert engine.get_global_state() == "blocked"

    def test_state_persister_called(self, engine):
        """注入 persister 验证每次 trip/release 都调用。"""
        snapshots: list[dict] = []
        engine.set_state_persister(lambda payload: snapshots.append(payload))

        engine.trip_breaker("CB01", reason="test")
        assert len(snapshots) == 1
        assert snapshots[-1]["state"] == "blocked"
        assert any(b["cb_id"] == "CB01" for b in snapshots[-1]["active_breakers"])

        engine.release_breaker("CB01")
        assert len(snapshots) == 2
        assert snapshots[-1]["state"] == "normal"

    def test_persister_exception_swallowed(self, engine):
        """持久化失败不应阻断 CB 状态变化。"""
        def boom(payload):
            raise RuntimeError("DB down")

        engine.set_state_persister(boom)
        # 应该不抛
        state = engine.trip_breaker("CB02", reason="test")
        assert state is not None
        assert engine.is_breaker_active("CB02")


# ============================================================
# 8. HR ↔ CB 联动(HR 触发 → 自动 trip CB)
# ============================================================

class TestHrCbLinkage:

    def test_hr17_trips_cb01(self, engine, base_ctx):
        base_ctx["daily_loss_usd"] = 600
        results = engine.check_trade(base_ctx)
        assert "HR17" in _ids(results)
        assert engine.is_breaker_active("CB01")

    def test_hr18_trips_cb02(self, engine, base_ctx):
        base_ctx["weekly_loss_usd"] = 2000
        engine.check_trade(base_ctx)
        assert engine.is_breaker_active("CB02")

    def test_hr19_trips_cb03(self, engine, base_ctx):
        base_ctx["consecutive_losses"] = 5
        engine.check_trade(base_ctx)
        assert engine.is_breaker_active("CB03")

    def test_hr20_trips_cb05(self, engine, base_ctx):
        base_ctx["max_drawdown_pct"] = 0.30
        engine.check_trade(base_ctx)
        assert engine.is_breaker_active("CB05")

    def test_hr16_trips_cb13(self, engine, base_ctx):
        base_ctx["regime"] = "CRISIS"
        base_ctx["action"] = "buy"
        engine.check_trade(base_ctx)
        assert engine.is_breaker_active("CB13")

    def test_hr12_trips_cb12(self, engine, base_ctx):
        base_ctx["kms_unavailable"] = True
        engine.check_trade(base_ctx)
        assert engine.is_breaker_active("CB12")

    def test_clean_ctx_no_cb_tripped(self, engine, base_ctx):
        engine.check_trade(base_ctx)
        assert engine.get_global_state() == "normal"
        assert not engine.get_active_breakers()


# ============================================================
# 9. HR10/11/24 函数直测
# ============================================================

class TestNewHrFunctions:

    def test_hr10_within(self):
        assert not hr10_within_authorization({"amount_usd": 100, "auth_single_trade_max": 500})

    def test_hr10_over(self):
        assert hr10_within_authorization({"amount_usd": 600, "auth_single_trade_max": 500})

    def test_hr10_missing_amount_pass(self):
        assert not hr10_within_authorization({})

    def test_hr10_missing_cap_blocks(self):
        assert hr10_within_authorization({"amount_usd": 100, "auth_single_trade_max": None})

    def test_hr11_paper_safe(self):
        assert not hr11_credentials_revoked({
            "mode": "paper",
            "credentials_revoked_at": "2026-04-01",
        })

    def test_hr11_live_revoked_blocks(self):
        assert hr11_credentials_revoked({
            "mode": "auto",
            "credentials_revoked_at": "2026-04-01",
        })

    def test_hr11_live_not_revoked_safe(self):
        assert not hr11_credentials_revoked({
            "mode": "live",
            "credentials_revoked_at": None,
        })

    def test_hr24_within_limit(self):
        assert not hr24_slippage_within_limit({"slippage_pct": 0.01, "max_slippage_pct": 0.05})

    def test_hr24_over_limit(self):
        assert hr24_slippage_within_limit({"slippage_pct": 0.10, "max_slippage_pct": 0.05})

    def test_hr24_missing_fields_safe(self):
        assert not hr24_slippage_within_limit({})


# ============================================================
# helpers
# ============================================================

def _ids(results) -> set[str]:
    return {r.rule_id for r in results}
