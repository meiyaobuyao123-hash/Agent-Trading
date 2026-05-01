"""
CB Monitor 单元测试 — W3 D4
覆盖 evaluate_cb07 / evaluate_cb08 / run_cb_monitor 主流程
mock CBDataSource 注入测试数据

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_cb_monitor.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.cb_monitor import (  # noqa: E402
    CBCheckResult,
    CBDataSource,
    CB07_TOKEN_TRIGGER_THRESHOLD,
    CB08_EXPIRED_APPROVALS_THRESHOLD,
    evaluate_cb07,
    evaluate_cb08,
    run_cb_monitor,
)
from agent.safety_engine import (  # noqa: E402
    get_safety_engine,
    reset_safety_engine_singleton,
)


@pytest.fixture(autouse=True)
def fresh_engine():
    reset_safety_engine_singleton()
    yield
    reset_safety_engine_singleton()


# ============================================================
# Mock 数据源
# ============================================================

class MockDataSource(CBDataSource):
    def __init__(
        self,
        token_counts: dict[str, int] | None = None,
        active_tokens: list[str] | None = None,
        expired_approvals: int | None = None,
        raise_on_count: bool = False,
        raise_on_expired: bool = False,
    ):
        self._counts = token_counts or {}
        self._active = active_tokens if active_tokens is not None else list(self._counts.keys())
        self._expired = expired_approvals
        self._raise_count = raise_on_count
        self._raise_expired = raise_on_expired

    async def list_active_tokens(self) -> list[str]:
        return self._active

    async def count_token_triggers_last_hour(self, token_address: str) -> int:
        if self._raise_count:
            raise RuntimeError("simulated DB error")
        return self._counts.get(token_address, 0)

    async def count_expired_approvals(self) -> int:
        if self._raise_expired:
            raise RuntimeError("simulated DB error")
        if self._expired is None:
            raise NotImplementedError("not configured")
        return self._expired


# ============================================================
# CB07 evaluator
# ============================================================

class TestEvaluateCB07:

    @pytest.mark.asyncio
    async def test_no_active_tokens(self):
        data = MockDataSource(active_tokens=[])
        results = await evaluate_cb07(data)
        assert results == []

    @pytest.mark.asyncio
    async def test_under_threshold_pass(self):
        # 阈值 5,3 次不触发
        data = MockDataSource(token_counts={"TokenA": 3})
        results = await evaluate_cb07(data)
        assert results == []

    @pytest.mark.asyncio
    async def test_at_threshold_triggers(self):
        # 5 次 == 阈值,触发
        data = MockDataSource(token_counts={"TokenA": CB07_TOKEN_TRIGGER_THRESHOLD})
        results = await evaluate_cb07(data)
        assert len(results) == 1
        assert results[0].cb_id == "CB07"
        assert results[0].triggered is True
        assert results[0].metric_value == 5
        assert "TokenA" in results[0].reason

    @pytest.mark.asyncio
    async def test_over_threshold_triggers(self):
        data = MockDataSource(token_counts={"TokenB": 10})
        results = await evaluate_cb07(data)
        assert len(results) == 1
        assert results[0].metric_value == 10

    @pytest.mark.asyncio
    async def test_count_error_skip(self):
        data = MockDataSource(
            active_tokens=["TokenX"],
            raise_on_count=True,
        )
        results = await evaluate_cb07(data)
        # 单个 token 失败不阻断,返回空
        assert results == []

    @pytest.mark.asyncio
    async def test_list_active_not_implemented(self):
        # 默认 CBDataSource 抛 NotImplementedError → 返空
        data = CBDataSource()
        results = await evaluate_cb07(data)
        assert results == []


# ============================================================
# CB08 evaluator
# ============================================================

class TestEvaluateCB08:

    @pytest.mark.asyncio
    async def test_under_threshold(self):
        data = MockDataSource(expired_approvals=10)
        result = await evaluate_cb08(data)
        assert result is not None
        assert result.triggered is False
        assert result.metric_value == 10

    @pytest.mark.asyncio
    async def test_at_threshold_no_trigger(self):
        # 阈值是 > 20,所以 == 20 不触发
        data = MockDataSource(expired_approvals=CB08_EXPIRED_APPROVALS_THRESHOLD)
        result = await evaluate_cb08(data)
        assert result.triggered is False

    @pytest.mark.asyncio
    async def test_over_threshold_triggers(self):
        data = MockDataSource(expired_approvals=25)
        result = await evaluate_cb08(data)
        assert result is not None
        assert result.triggered is True
        assert "25 条" in result.reason

    @pytest.mark.asyncio
    async def test_data_unavailable_returns_none(self):
        data = MockDataSource(expired_approvals=None)
        result = await evaluate_cb08(data)
        # NotImplementedError → 返 None(降级)
        assert result is None

    @pytest.mark.asyncio
    async def test_db_error_returns_none(self):
        data = MockDataSource(expired_approvals=10, raise_on_expired=True)
        result = await evaluate_cb08(data)
        # 通用异常也返 None
        assert result is None


# ============================================================
# run_cb_monitor 主流程
# ============================================================

class TestRunMonitor:

    @pytest.mark.asyncio
    async def test_clean_state_no_trigger(self):
        data = MockDataSource(
            token_counts={"TokenA": 1},
            expired_approvals=5,
        )
        result = await run_cb_monitor(data)
        assert result["triggered"] == []
        assert result["stats"]["cb07_token_count"] == 0
        assert result["stats"]["cb08_expired_count"] == 5
        # 任何 CB 都不应被 trip
        engine = get_safety_engine()
        assert not engine.is_breaker_active("CB07")
        assert not engine.is_breaker_active("CB08")

    @pytest.mark.asyncio
    async def test_cb07_triggers_engine(self):
        data = MockDataSource(
            token_counts={"BadToken": 8},
            expired_approvals=0,
        )
        result = await run_cb_monitor(data)
        assert "CB07" in result["triggered"]
        engine = get_safety_engine()
        assert engine.is_breaker_active("CB07")

    @pytest.mark.asyncio
    async def test_cb08_triggers_engine(self):
        data = MockDataSource(
            token_counts={},
            expired_approvals=30,
        )
        result = await run_cb_monitor(data)
        assert "CB08" in result["triggered"]
        engine = get_safety_engine()
        assert engine.is_breaker_active("CB08")

    @pytest.mark.asyncio
    async def test_already_active_cb_not_re_tripped(self):
        """已 active 的 CB 不重复 trip(幂等)"""
        engine = get_safety_engine()
        engine.trip_breaker("CB07", reason="initial")

        data = MockDataSource(token_counts={"TokenA": 100})
        result = await run_cb_monitor(data)
        # CB07 已 active,不应重复 trip → triggered 不含 CB07
        assert "CB07" not in result["triggered"]
        # 但 CB07 仍应 active
        assert engine.is_breaker_active("CB07")

    @pytest.mark.asyncio
    async def test_data_source_failures_skipped(self):
        data = MockDataSource(
            token_counts={"X": 0},
            raise_on_count=True,
            raise_on_expired=True,
        )
        result = await run_cb_monitor(data)
        # 两个 CB 都不应触发,但函数不抛
        assert result["triggered"] == []

    @pytest.mark.asyncio
    async def test_engine_unavailable_returns_skipped(self):
        with patch("agent.safety_engine.get_safety_engine") as mock_get:
            mock_get.side_effect = RuntimeError("engine gone")
            data = MockDataSource(token_counts={"X": 100}, expired_approvals=100)
            result = await run_cb_monitor(data)
            assert result["skipped"] == ["all"]
            assert result["triggered"] == []
