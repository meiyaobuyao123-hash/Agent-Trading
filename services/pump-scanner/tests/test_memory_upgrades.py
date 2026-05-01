"""
Memory 4 层升级 + T05/T06 Tool 单元测试 — W3 D5+

覆盖:
  - episodic.get_relevant 评分公式 + freshness + match_count + score>=3.0
  - semantic.check_strict_promotion_gates(5 条硬门槛)+ try_promote_strict
  - reflection.deduplicate_proposed_rules (JSON-diff threshold)
  - T05 list_strategies + T06 update_strategy_status

跑法:python3 -m pytest tests/test_memory_upgrades.py -v
"""
from __future__ import annotations
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ── Episodic.get_relevant ───────────────────────────────────

def _ep_record(**kwargs):
    base = {
        "id": "ep-x",
        "trigger_source": "pump",
        "chain": "SOL",
        "token_type": None,
        "mcap_bucket": None,
        "market_regime": None,
        "match_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "structured_data": {"pnl_pct": 0},
    }
    base.update(kwargs)
    return base


def test_episodic_get_relevant_filter_by_min_score():
    """score < 3.0 的记忆不返回。"""
    from agent.memory.episodic_memory import EpisodicMemory
    em = EpisodicMemory()
    # mock cache:一条只有 chain 匹配(2)和 fresh(1.5)的,total ~3.5 → 通过
    # 一条只有 chain(2)+fresh 0(很老),total 2 → 被过滤
    old_ts = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    em._cache = [
        _ep_record(id="fresh", trigger_source="pump", chain="SOL",
                    created_at=datetime.now(timezone.utc).isoformat()),
        _ep_record(id="old", trigger_source="other", chain="SOL",
                    created_at=old_ts),
    ]
    em._cache_ts = 1e10

    with patch.object(em, "_bump_match_count"):
        out = em.get_relevant(chain="SOL", trigger_source="pump", min_score=3.0)
    ids = [r["id"] for r in out]
    assert "fresh" in ids
    assert "old" not in ids  # 太老 + 无 trigger 匹配


def test_episodic_freshness_decays_to_zero_at_90d():
    from agent.memory.episodic_memory import EpisodicMemory
    em = EpisodicMemory()
    # 200d 老 + chain match 2 + trigger match 3 = 5 — 仍超过 3.0
    old_ts = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    em._cache = [
        _ep_record(id="old_but_strong", trigger_source="pump", chain="SOL",
                    created_at=old_ts),
    ]
    em._cache_ts = 1e10
    with patch.object(em, "_bump_match_count"):
        out = em.get_relevant(chain="SOL", trigger_source="pump", min_score=3.0)
    assert len(out) == 1
    # freshness 应该接近 0(200d 远超 30d 半衰)
    assert out[0]["_score"] >= 5.0  # 3 + 2 + 极少 freshness
    assert out[0]["_score"] < 5.5


def test_episodic_regime_distance_partial_credit():
    from agent.memory.episodic_memory import EpisodicMemory
    em = EpisodicMemory()
    em._cache = [
        _ep_record(id="exact", market_regime="TRENDING_UP",
                    trigger_source="pump"),
        _ep_record(id="adj", market_regime="BREAKOUT",  # 相邻
                    trigger_source="pump"),
        _ep_record(id="far", market_regime="CRISIS",  # 远
                    trigger_source="pump"),
    ]
    em._cache_ts = 1e10
    with patch.object(em, "_bump_match_count"):
        out = em.get_relevant(regime="TRENDING_UP", trigger_source="pump", min_score=3.0)
    by_id = {r["id"]: r["_score"] for r in out}
    # exact: 3(trigger)+2(regime)+~1.5(fresh) ≈ 6.5
    # adj:   3(trigger)+1(adj regime)+~1.5(fresh) ≈ 5.5
    # far:   3(trigger)+0(far)+~1.5(fresh) ≈ 4.5
    assert by_id["exact"] > by_id["adj"]
    assert by_id["adj"] > by_id["far"]


def test_episodic_match_count_log_bonus():
    from agent.memory.episodic_memory import EpisodicMemory
    em = EpisodicMemory()
    em._cache = [
        _ep_record(id="hot", trigger_source="pump", chain="SOL", match_count=100),
        _ep_record(id="cold", trigger_source="pump", chain="SOL", match_count=0),
    ]
    em._cache_ts = 1e10
    with patch.object(em, "_bump_match_count"):
        out = em.get_relevant(chain="SOL", trigger_source="pump", min_score=3.0)
    by_id = {r["id"]: r["_score"] for r in out}
    assert by_id["hot"] > by_id["cold"]  # match_count log 加分


# ── Semantic 5 条硬晋升 ──────────────────────────────────────

def test_strict_gates_all_pass():
    from agent.memory.semantic_memory import SemanticMemory
    # 30 笔 comply 全胜 vs 30 笔 violate 全亏 → wilson 高,t-test 显著,2 regime
    comply = [10.0] * 30  # 全 +10% pnl
    violate = [-10.0] * 30
    res = SemanticMemory.check_strict_promotion_gates(
        reflections_count=3,
        comply_pnls=comply, violate_pnls=violate,
        regimes_observed=["TRENDING_UP", "BREAKOUT"],
    )
    assert res["passed"] is True


def test_strict_gates_fail_low_reflections():
    from agent.memory.semantic_memory import SemanticMemory
    res = SemanticMemory.check_strict_promotion_gates(
        reflections_count=1,
        comply_pnls=[10.0] * 30, violate_pnls=[-10.0] * 30,
        regimes_observed=["TRENDING_UP", "BREAKOUT"],
    )
    assert res["passed"] is False
    assert res["gates"]["reflections"]["ok"] is False


def test_strict_gates_fail_too_few_samples():
    from agent.memory.semantic_memory import SemanticMemory
    res = SemanticMemory.check_strict_promotion_gates(
        reflections_count=3,
        comply_pnls=[10.0] * 5,  # 5 < 20
        violate_pnls=[-10.0] * 5,
        regimes_observed=["TRENDING_UP", "BREAKOUT"],
    )
    assert res["passed"] is False
    assert res["gates"]["sample_size"]["ok"] is False


def test_strict_gates_fail_low_wilson():
    """胜率刚过 50% + n=20 → wilson 下界可能 < 0.55。"""
    from agent.memory.semantic_memory import SemanticMemory
    comply = [1.0 if i < 11 else -1.0 for i in range(20)]  # 55% 胜率
    res = SemanticMemory.check_strict_promotion_gates(
        reflections_count=3,
        comply_pnls=comply, violate_pnls=[-1.0] * 20,
        regimes_observed=["TRENDING_UP", "BREAKOUT"],
    )
    # wilson lower 应 < 0.55
    assert res["gates"]["wilson_ci_lower"]["value"] < 0.55
    assert res["passed"] is False


def test_strict_gates_fail_single_regime():
    from agent.memory.semantic_memory import SemanticMemory
    res = SemanticMemory.check_strict_promotion_gates(
        reflections_count=3,
        comply_pnls=[10.0] * 30, violate_pnls=[-10.0] * 30,
        regimes_observed=["TRENDING_UP"],  # 只 1 个
    )
    assert res["passed"] is False
    assert res["gates"]["regime_diversity"]["ok"] is False


def test_try_promote_strict_writes_with_shadow():
    from agent.memory.semantic_memory import SemanticMemory
    sm = SemanticMemory()
    # 已加载,不再去 DB 查
    sm._rules = []
    sm._last_load = 1e10

    fake_db = MagicMock()
    fake_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "new-uuid"}]
    )
    with patch("agent.memory.semantic_memory.get_db", return_value=fake_db):
        res = sm.try_promote_strict(
            condition="regime=RANGING AND bc<8",
            action="block_entry",
            reflections_count=3,
            comply_pnls=[5.0] * 25,
            violate_pnls=[-5.0] * 25,
            regimes_observed=["RANGING", "HIGH_VOLATILITY"],
        )
    assert res["ok"] is True
    assert res["promoted_rule_id"] == "new-uuid"
    assert "shadow_mode_until" in res
    # 验证 insert 被调用,且 row 含 shadow_mode_until
    fake_db.table.return_value.insert.assert_called_once()
    inserted = fake_db.table.return_value.insert.call_args.args[0]
    assert "shadow_mode_until" in inserted
    assert inserted["is_active"] is True


def test_try_promote_strict_blocks_duplicate():
    from agent.memory.semantic_memory import SemanticMemory
    sm = SemanticMemory()
    sm._rules = [{
        "id": "existing",
        "structured_data": {"condition": "REGIME=RANGING AND BC<8", "action": "block"},
    }]
    sm._last_load = 1e10

    res = sm.try_promote_strict(
        condition="regime=RANGING AND bc<8",  # 大写 normalize 后一样
        action="block_entry",
        reflections_count=3,
        comply_pnls=[5.0] * 25,
        violate_pnls=[-5.0] * 25,
        regimes_observed=["RANGING", "HIGH_VOLATILITY"],
    )
    assert res["ok"] is False
    assert res["reason"] == "duplicate_condition"


def test_try_promote_strict_blocks_when_gates_fail():
    from agent.memory.semantic_memory import SemanticMemory
    sm = SemanticMemory()
    sm._rules = []; sm._last_load = 1e10
    res = sm.try_promote_strict(
        condition="x", action="y",
        reflections_count=1,  # < 3
        comply_pnls=[5.0] * 30, violate_pnls=[-5.0] * 30,
        regimes_observed=["RANGING", "BREAKOUT"],
    )
    assert res["ok"] is False
    assert "FAILED gates" in res["reason"]


# ── Reflection JSON-diff dedupe ─────────────────────────────

def test_jaccard_distance_identical():
    from agent.memory.reflection import ReflectionEngine
    a = {"condition": "X>1", "action": "skip"}
    b = {"condition": "X>1", "action": "skip"}
    assert ReflectionEngine.jaccard_distance(a, b) == 0.0


def test_jaccard_distance_different():
    from agent.memory.reflection import ReflectionEngine
    a = {"condition": "X>1", "action": "skip"}
    b = {"condition": "Y<2", "action": "buy"}
    d = ReflectionEngine.jaccard_distance(a, b)
    assert d > 0.5


def test_dedupe_skips_close_match():
    from agent.memory.reflection import ReflectionEngine
    re = ReflectionEngine()
    new_rules = [
        {"condition": "X>1", "action": "skip"},
        {"condition": "Z<3", "action": "buy"},  # 不重复
    ]
    existing = [{
        "id": "r-1",
        "structured_data": {"condition": "X>1", "action": "skip"},
    }]
    kept = re.deduplicate_proposed_rules(new_rules, existing, threshold=0.20)
    assert len(kept) == 1
    assert kept[0]["condition"] == "Z<3"


def test_dedupe_normalize_case():
    from agent.memory.reflection import ReflectionEngine
    re = ReflectionEngine()
    new_rules = [{"condition": "x>1", "action": "SKIP"}]  # 小写 condition + 大写 action
    existing = [{
        "id": "r-1",
        "structured_data": {"condition": "X>1", "action": "skip"},
    }]
    kept = re.deduplicate_proposed_rules(new_rules, existing)
    assert kept == []  # 应该被 dedupe


def test_dedupe_empty_existing_keeps_all():
    from agent.memory.reflection import ReflectionEngine
    re = ReflectionEngine()
    new_rules = [{"condition": "X>1", "action": "skip"}]
    kept = re.deduplicate_proposed_rules(new_rules, [])
    assert len(kept) == 1


# ── T05 list_strategies ─────────────────────────────────────

@pytest.mark.asyncio
async def test_t05_basic_returns_slim():
    from agent.tools import ListStrategiesTool
    tool = ListStrategiesTool()
    fake_mgr = MagicMock()
    fake_mgr.list_strategies.return_value = [
        {
            "id": "s-1", "name": "Smart Money Follow", "status": "active",
            "mode": "paper", "data_sources": ["smart_money"],
            "created_at": "2026-04-01T00:00:00Z",
            "trigger_count_total": 10, "cooldown_min": 30,
        },
        {
            "id": "s-2", "name": "Hot Coin Buy", "status": "paused",
            "mode": "notify", "data_sources": ["hot"],
            "created_at": "2026-04-15T00:00:00Z",
        },
    ]
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr):
        r = await tool.run({"user_id": "u-1", "status": "all"})
    assert r.ok is True
    assert r.output["count"] == 2
    assert r.output["active_count"] == 1
    assert r.output["strategies"][0]["id"] == "s-1"
    assert r.output["strategies"][0]["status"] == "active"


@pytest.mark.asyncio
async def test_t05_invalid_status_400():
    from agent.tools import ListStrategiesTool
    tool = ListStrategiesTool()
    r = await tool.run({"user_id": "u-1", "status": "weird"})
    assert r.ok is False
    assert r.failure_mode == "INPUT_SCHEMA_INVALID"


@pytest.mark.asyncio
async def test_t05_empty_list_returns_zero():
    from agent.tools import ListStrategiesTool
    tool = ListStrategiesTool()
    fake_mgr = MagicMock()
    fake_mgr.list_strategies.return_value = []
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr):
        r = await tool.run({"user_id": "u-1"})
    assert r.ok is True
    assert r.output["count"] == 0
    assert r.output["active_count"] == 0


# ── T06 update_strategy_status ──────────────────────────────

@pytest.mark.asyncio
async def test_t06_active_to_paused():
    from agent.tools import UpdateStrategyStatusTool
    tool = UpdateStrategyStatusTool()
    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "s-1", "status": "active", "user_id": "u-1"}]
    )
    fake_mgr = MagicMock()
    fake_mgr.update_strategy.return_value = {"id": "s-1", "status": "paused"}
    with patch("database.get_db", return_value=fake_db), \
         patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr):
        r = await tool.run({"strategy_id": "s-1", "new_status": "paused"})
    assert r.ok is True
    assert r.output["ok"] is True
    assert r.output["previous_status"] == "active"
    assert r.output["new_status"] == "paused"
    assert r.output["noop"] is False


@pytest.mark.asyncio
async def test_t06_idempotent_same_status():
    from agent.tools import UpdateStrategyStatusTool
    tool = UpdateStrategyStatusTool()
    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "s-1", "status": "active", "user_id": "u-1"}]
    )
    with patch("database.get_db", return_value=fake_db):
        r = await tool.run({"strategy_id": "s-1", "new_status": "active"})
    assert r.ok is True
    assert r.output["noop"] is True


@pytest.mark.asyncio
async def test_t06_archived_terminal():
    from agent.tools import UpdateStrategyStatusTool
    tool = UpdateStrategyStatusTool()
    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "s-1", "status": "archived", "user_id": "u-1"}]
    )
    with patch("database.get_db", return_value=fake_db):
        r = await tool.run({"strategy_id": "s-1", "new_status": "active"})
    assert r.ok is True  # tool 本身不抛错,只是 ok=False 在 output
    assert r.output["ok"] is False
    assert "invalid_transition" in r.output["reason"]


@pytest.mark.asyncio
async def test_t06_strategy_not_found():
    from agent.tools import UpdateStrategyStatusTool
    tool = UpdateStrategyStatusTool()
    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    with patch("database.get_db", return_value=fake_db):
        r = await tool.run({"strategy_id": "missing", "new_status": "paused"})
    assert r.output["ok"] is False
    assert r.output["reason"] == "strategy_not_found"


@pytest.mark.asyncio
async def test_t06_paused_to_active_valid():
    from agent.tools import UpdateStrategyStatusTool
    tool = UpdateStrategyStatusTool()
    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "s-1", "status": "paused", "user_id": "u-1"}]
    )
    fake_mgr = MagicMock()
    fake_mgr.update_strategy.return_value = {"id": "s-1", "status": "active"}
    with patch("database.get_db", return_value=fake_db), \
         patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr):
        r = await tool.run({"strategy_id": "s-1", "new_status": "active"})
    assert r.output["ok"] is True
    assert r.output["previous_status"] == "paused"


# ── Registry now has 8 tools ────────────────────────────────

def test_registry_has_eight_tools():
    from agent.tools import get_tool_registry
    reg = get_tool_registry()
    assert len(reg) == 8
    assert "list_strategies" in reg
    assert "update_strategy_status" in reg
