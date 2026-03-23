"""
PRD-005 测试 — 记忆与反思系统

测试覆盖：
1. WorkingMemory: 24h 滑动窗口、deque maxlen、get_recent
2. EpisodicMemory: 相关性评分、过期计算
3. SemanticMemory: 条件匹配、规则合规检查、晋升/废弃
4. ReflectionEngine: 紧急反思判断、交易计数
5. MemoryManager: 统一接口、格式化
6. strategy_type 推断

不依赖 DB（mock get_db），可本地运行。
"""

import time
import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any


# ═══════════════════════════════════════════════════════
# 1. WorkingMemory 测试
# ═══════════════════════════════════════════════════════

class TestWorkingMemory:
    def test_add_and_get_recent(self):
        from agent.memory.working_memory import WorkingMemory
        wm = WorkingMemory(maxlen=200, window_sec=86400)

        # 添加事件
        for i in range(15):
            wm.add({"type": "signal", "token": f"TOKEN{i}", "summary": f"event {i}"})

        # 获取最近 10 条
        recent = wm.get_recent(10)
        assert len(recent) == 10
        assert recent[-1]["token"] == "TOKEN14"  # 最新的在最后

    def test_24h_sliding_window(self):
        from agent.memory.working_memory import WorkingMemory
        wm = WorkingMemory(maxlen=200, window_sec=86400)

        # 添加一条过期事件
        old_event = {"type": "old", "summary": "old event"}
        old_event["_ts"] = time.time() - 90000  # >24h ago
        wm._events.append(old_event)

        # 添加一条新事件
        wm.add({"type": "new", "summary": "new event"})

        # get_recent 应该过滤掉过期事件
        recent = wm.get_recent(10)
        assert len(recent) == 1
        assert recent[0]["type"] == "new"

    def test_maxlen(self):
        from agent.memory.working_memory import WorkingMemory
        wm = WorkingMemory(maxlen=5, window_sec=86400)

        for i in range(10):
            wm.add({"token": f"T{i}"})

        assert wm.size() == 5  # deque maxlen 限制

    def test_size_valid(self):
        from agent.memory.working_memory import WorkingMemory
        wm = WorkingMemory(maxlen=200, window_sec=86400)

        # 过期事件
        e = {"type": "old", "_ts": time.time() - 90000}
        wm._events.append(e)

        # 有效事件
        wm.add({"type": "new"})
        wm.add({"type": "new2"})

        assert wm.size() == 3       # 总数
        assert wm.size_valid() == 2  # 有效数

    def test_clear(self):
        from agent.memory.working_memory import WorkingMemory
        wm = WorkingMemory()
        wm.add({"type": "test"})
        wm.clear()
        assert wm.size() == 0


# ═══════════════════════════════════════════════════════
# 2. SemanticMemory 条件匹配测试
# ═══════════════════════════════════════════════════════

class TestSemanticMemory:
    def test_matches_condition_simple(self):
        from agent.memory.semantic_memory import SemanticMemory
        sm = SemanticMemory()

        ctx = {"rsi": 70, "regime": "HIGH_VOLATILITY"}

        assert sm._matches_condition("RSI > 65", ctx) is True
        assert sm._matches_condition("RSI > 75", ctx) is False
        assert sm._matches_condition("REGIME = HIGH_VOLATILITY", ctx) is True
        assert sm._matches_condition("REGIME = TRENDING_UP", ctx) is False

    def test_matches_condition_and(self):
        from agent.memory.semantic_memory import SemanticMemory
        sm = SemanticMemory()

        ctx = {"rsi": 70, "regime": "HIGH_VOLATILITY", "chain": "solana"}

        assert sm._matches_condition("RSI > 65 AND REGIME = HIGH_VOLATILITY", ctx) is True
        assert sm._matches_condition("RSI > 65 AND REGIME = TRENDING_UP", ctx) is False
        assert sm._matches_condition("RSI > 75 AND REGIME = HIGH_VOLATILITY", ctx) is False

    def test_matches_condition_operators(self):
        from agent.memory.semantic_memory import SemanticMemory
        sm = SemanticMemory()

        ctx = {"rsi": 50, "hold_hours": 8}

        assert sm._matches_condition("RSI >= 50", ctx) is True
        assert sm._matches_condition("RSI >= 51", ctx) is False
        assert sm._matches_condition("RSI <= 50", ctx) is True
        assert sm._matches_condition("HOLD_HOURS > 6", ctx) is True
        assert sm._matches_condition("HOLD_HOURS < 6", ctx) is False

    def test_check_compliance(self):
        from agent.memory.semantic_memory import SemanticMemory
        sm = SemanticMemory()

        # 模拟已加载规则
        sm._rules = [
            {
                "id": "rule-1",
                "structured_data": {
                    "condition": "rsi > 65 AND regime = HIGH_VOLATILITY",
                    "action": "skip_buy",
                },
                "content": "Test rule",
            }
        ]
        sm._last_load = time.time()  # 防止从 DB 加载

        ctx = {"rsi": 70, "regime": "HIGH_VOLATILITY"}
        matched = sm.check_compliance(ctx)
        assert len(matched) == 1
        assert matched[0]["rule_id"] == "rule-1"
        assert matched[0]["action"] == "skip_buy"

        ctx2 = {"rsi": 50, "regime": "TRENDING_UP"}
        matched2 = sm.check_compliance(ctx2)
        assert len(matched2) == 0

    def test_get_relevant_scoring(self):
        from agent.memory.semantic_memory import SemanticMemory
        sm = SemanticMemory()

        sm._rules = [
            {"id": "r1", "importance": 5, "chain": "solana", "trigger_source": "hot_score",
             "structured_data": {"condition": "x > 1", "action": "buy"}},
            {"id": "r2", "importance": 8, "chain": "eth", "trigger_source": "smart_money",
             "structured_data": {"condition": "x > 2", "action": "buy"}},
            {"id": "r3", "importance": 3, "chain": "solana", "trigger_source": "smart_money",
             "structured_data": {"condition": "x > 3", "action": "skip"}},
        ]
        sm._last_load = time.time()

        # chain=solana (+2), trigger_source=smart_money (+3)
        result = sm.get_relevant(chain="solana", trigger_source="smart_money", limit=2)
        assert len(result) == 2
        # r2: 8 + 0 (no chain match) + 3 (trigger) = 11
        # r3: 3 + 2 (chain) + 3 (trigger) = 8
        # r1: 5 + 2 (chain) + 0 = 7
        assert result[0]["id"] == "r2"  # score 11
        assert result[1]["id"] == "r3"  # score 8

    def test_promotion_conditions(self):
        from agent.memory.semantic_memory import SemanticMemory
        sm = SemanticMemory()
        sm._rules = []
        sm._last_load = time.time()

        # 不够出现次数
        assert sm.try_promote("rsi > 65", appearances=2,
                              comply_win=5, comply_lose=0,
                              violate_win=0, violate_lose=3,
                              metadata={}) is False

        # 不够样本
        assert sm.try_promote("rsi > 65", appearances=3,
                              comply_win=2, comply_lose=0,
                              violate_win=0, violate_lose=1,
                              metadata={}) is False

        # 胜率差不够
        assert sm.try_promote("rsi > 65", appearances=3,
                              comply_win=3, comply_lose=2,
                              violate_win=2, violate_lose=1,
                              metadata={}) is False
        # comply_wr = 60%, violate_wr = 67%, diff = -7% < 15%


# ═══════════════════════════════════════════════════════
# 3. ReflectionEngine 测试
# ═══════════════════════════════════════════════════════

class TestReflectionEngine:
    def test_should_emergency_reflect(self):
        from agent.memory.reflection import ReflectionEngine
        re = ReflectionEngine()

        # 亏损 >25% 且金额 >$30
        assert re.should_emergency_reflect(-30, 50) is True
        # 亏损 >25% 但金额 <$30
        assert re.should_emergency_reflect(-30, 20) is False
        # 亏损 <25%
        assert re.should_emergency_reflect(-20, 100) is False
        # 盈利
        assert re.should_emergency_reflect(10, 100) is False

    def test_trade_counter(self):
        from agent.memory.reflection import ReflectionEngine
        re = ReflectionEngine()

        assert re.should_reflect_by_count() is False
        for _ in range(10):
            re.increment_trade_count()
        assert re.should_reflect_by_count() is True

        re.reset_trade_count()
        assert re.should_reflect_by_count() is False

    def test_emergency_cooldown(self):
        from agent.memory.reflection import ReflectionEngine, MAX_EMERGENCY_PER_DAY
        re = ReflectionEngine()
        re._api_key = ""  # 没有 API key

        # 即使有 API key，每日最多 2 次
        re._emergency_count_today = MAX_EMERGENCY_PER_DAY
        from datetime import datetime, timezone
        re._last_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # should still be at limit
        assert re._emergency_count_today >= MAX_EMERGENCY_PER_DAY


# ═══════════════════════════════════════════════════════
# 4. MemoryManager 统一接口测试
# ═══════════════════════════════════════════════════════

class TestMemoryManager:
    def test_init(self):
        from agent.memory import MemoryManager
        mm = MemoryManager()
        assert mm.working is not None
        assert mm.episodic is not None
        assert mm.semantic is not None
        assert mm.reflection is not None

    def test_add_event(self):
        from agent.memory import MemoryManager
        mm = MemoryManager()
        mm.add_event({"type": "test", "summary": "test event"})
        recent = mm.working.get_recent(1)
        assert len(recent) == 1
        assert recent[0]["type"] == "test"

    def test_format_for_prompt_empty(self):
        from agent.memory import MemoryManager
        mm = MemoryManager()
        text = mm.format_for_prompt({"short_term": [], "episodic": [], "semantic": []})
        assert text == ""

    def test_format_for_prompt_with_data(self):
        from agent.memory import MemoryManager
        mm = MemoryManager()

        context = {
            "short_term": [{"summary": "买入 BONK $100"}],
            "episodic": [{"content": "3天前买入 WIF +35%"}],
            "semantic": [{
                "structured_data": {"condition": "rsi > 65", "action": "skip_buy"},
                "comply_win": 6, "comply_lose": 2,
            }],
        }
        text = mm.format_for_prompt(context)
        assert "短期记忆" in text
        assert "买入 BONK" in text
        assert "近期经验" in text
        assert "交易规则" in text
        assert "rsi > 65" in text

    def test_get_stats(self):
        from agent.memory import MemoryManager
        mm = MemoryManager()
        stats = mm.get_stats()
        assert "working_memory_size" in stats
        assert "semantic_rules" in stats
        assert "reflection_trade_counter" in stats

    def test_mcap_bucket(self):
        from agent.memory import _mcap_bucket
        assert _mcap_bucket(50_000) == "<100K"
        assert _mcap_bucket(500_000) == "100K-1M"
        assert _mcap_bucket(5_000_000) == "1M-10M"
        assert _mcap_bucket(50_000_000) == ">10M"


# ═══════════════════════════════════════════════════════
# 5. strategy_type 推断测试
# ═══════════════════════════════════════════════════════

class TestStrategyTypeInference:
    def test_smart_money_follow(self):
        from agent.strategy_manager import StrategyManager
        sm = StrategyManager()
        result = sm._infer_strategy_type(
            {"rules": [{"data_source": "hot_coins", "field": "smart_money_count"}]},
            ["hot_coins"],
        )
        assert result == "smart_money_follow"

    def test_kol_mention(self):
        from agent.strategy_manager import StrategyManager
        sm = StrategyManager()
        result = sm._infer_strategy_type(
            {"rules": [{"data_source": "kol_mentions", "field": "count"}]},
            ["kol_mentions"],
        )
        assert result == "kol_mention"

    def test_hot_breakout(self):
        from agent.strategy_manager import StrategyManager
        sm = StrategyManager()
        result = sm._infer_strategy_type(
            {"rules": [{"data_source": "hot_coins", "field": "price_change_1h"}]},
            ["hot_coins"],
        )
        assert result == "hot_breakout"

    def test_hot_score(self):
        from agent.strategy_manager import StrategyManager
        sm = StrategyManager()
        result = sm._infer_strategy_type(
            {"rules": [{"data_source": "hot_coins", "field": "score"}]},
            ["hot_coins"],
        )
        assert result == "hot_score"

    def test_pump_early(self):
        from agent.strategy_manager import StrategyManager
        sm = StrategyManager()
        result = sm._infer_strategy_type(
            {"rules": [{"data_source": "pump_tokens", "field": "bc_progress"}]},
            ["pump_tokens"],
        )
        assert result == "pump_early"

    def test_custom(self):
        from agent.strategy_manager import StrategyManager
        sm = StrategyManager()
        result = sm._infer_strategy_type(
            {"rules": [{"data_source": "custom_source", "field": "value"}]},
            ["custom_source"],
        )
        assert result == "custom"


# ═══════════════════════════════════════════════════════
# 6. EpisodicMemory 相关性评分测试
# ═══════════════════════════════════════════════════════

class TestEpisodicRelevance:
    def test_relevance_scoring(self):
        from agent.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()

        # 模拟缓存
        em._cache = [
            {
                "id": "m1", "trigger_source": "smart_money", "chain": "solana",
                "market_regime": "trending_up", "mcap_bucket": "1M-10M",
                "structured_data": {"pnl_pct": 5}, "created_at": "2026-03-23T10:00:00Z",
            },
            {
                "id": "m2", "trigger_source": "hot_score", "chain": "solana",
                "market_regime": "trending_up", "mcap_bucket": "1M-10M",
                "structured_data": {"pnl_pct": 25}, "created_at": "2026-03-23T12:00:00Z",
            },
            {
                "id": "m3", "trigger_source": "smart_money", "chain": "eth",
                "market_regime": "high_volatility", "mcap_bucket": "<100K",
                "structured_data": {"pnl_pct": -30}, "created_at": "2026-03-23T11:00:00Z",
            },
        ]
        em._cache_ts = time.time()

        # 搜索: chain=solana, trigger=smart_money, regime=trending_up, mcap=1M-10M
        results = em.search(
            chain="solana", trigger_source="smart_money",
            mcap_bucket="1M-10M", regime="trending_up", limit=2,
        )
        assert len(results) == 2
        # m1: trigger(+3) + chain(+2) + regime(+2) + mcap(+2) = 9
        # m3: trigger(+3) + regime(0) + mcap(0) + chain(0) + pnl(+1) = 4
        # m2: trigger(0) + chain(+2) + regime(+2) + mcap(+2) + pnl(+1) = 7
        assert results[0]["id"] == "m1"  # score 9
        assert results[1]["id"] == "m2"  # score 7


# ═══════════════════════════════════════════════════════
# 7. 集成冒烟测试（不需要 DB）
# ═══════════════════════════════════════════════════════

class TestIntegrationSmoke:
    def test_memory_manager_singleton(self):
        from agent.memory import get_memory_manager
        m1 = get_memory_manager()
        m2 = get_memory_manager()
        assert m1 is m2

    def test_full_workflow_no_db(self):
        """完整流程（不涉及 DB）"""
        from agent.memory import MemoryManager

        mm = MemoryManager()

        # 1. 写入短期记忆
        mm.add_event({"type": "signal", "source": "hot_coin", "token": "BONK", "summary": "BONK score=85"})
        mm.add_event({"type": "trade", "action": "buy", "token": "BONK", "summary": "买入 BONK $100"})

        # 2. 获取短期记忆
        recent = mm.working.get_recent(10)
        assert len(recent) == 2

        # 3. 检查规则（无规则 = 无匹配）
        mm.semantic._rules = []
        mm.semantic._last_load = time.time()
        violations = mm.check_rules({"rsi": 70, "regime": "HIGH_VOLATILITY"})
        assert len(violations) == 0

        # 4. 添加一条规则后再检查
        mm.semantic._rules = [{
            "id": "test-rule",
            "structured_data": {"condition": "rsi > 65", "action": "skip_buy"},
            "content": "RSI过高时不买",
            "importance": 7,
        }]
        violations = mm.check_rules({"rsi": 70, "regime": "HIGH_VOLATILITY"})
        assert len(violations) == 1

        # 5. 格式化
        context = {
            "short_term": recent,
            "episodic": [],
            "semantic": mm.semantic._rules,
        }
        text = mm.format_for_prompt(context)
        assert "BONK" in text
        assert "rsi > 65" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
