"""
Global State Persister 单元测试 — W3 D3
覆盖:
  persist_to_pg 幂等
  persist_to_pg DB 失败吞掉异常
  load_from_pg 表不存在返 None
  restore_engine_state 端到端
  attach_to_engine 一键挂载

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_global_state_persister.py -v
"""
from __future__ import annotations
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import global_state_persister as gsp  # noqa: E402
from agent.safety_engine import (  # noqa: E402
    SafetyEngine,
    reset_safety_engine_singleton,
)


@pytest.fixture(autouse=True)
def reset_cache():
    gsp.reset_persister_cache()
    yield
    gsp.reset_persister_cache()


@pytest.fixture
def fresh_engine() -> SafetyEngine:
    reset_safety_engine_singleton()
    e = SafetyEngine()
    e.load()
    return e


# ============================================================
# 1. _hash_payload 幂等检测
# ============================================================

class TestHashPayload:

    def test_same_payload_same_hash(self):
        p1 = {"state": "blocked", "active_breakers": [{"cb_id": "CB01"}]}
        p2 = {"state": "blocked", "active_breakers": [{"cb_id": "CB01"}]}
        assert gsp._hash_payload(p1) == gsp._hash_payload(p2)

    def test_different_state_diff_hash(self):
        p1 = {"state": "normal", "active_breakers": []}
        p2 = {"state": "blocked", "active_breakers": []}
        assert gsp._hash_payload(p1) != gsp._hash_payload(p2)

    def test_field_order_invariant(self):
        # JSON sort_keys → 顺序无关
        p1 = {"state": "normal", "active_breakers": []}
        p2 = {"active_breakers": [], "state": "normal"}
        assert gsp._hash_payload(p1) == gsp._hash_payload(p2)


# ============================================================
# 2. persist_to_pg 幂等 + 异常吞掉
# ============================================================

class TestPersist:

    def test_idempotent_skip_same_payload(self):
        """连续 2 次相同 payload,只第一次实际写 DB"""
        with patch("local_db._get_conn") as mock_conn:
            cur = MagicMock()
            mock_conn.return_value.cursor.return_value.__enter__.return_value = cur
            cur.fetchone.return_value = ("normal",)

            payload = {"state": "blocked", "active_breakers": [{"cb_id": "CB01"}]}
            ok1 = gsp.persist_to_pg(payload)
            ok2 = gsp.persist_to_pg(payload)
            assert ok1 is True
            assert ok2 is True
            # cursor.execute 应该只被调 2 次(UPDATE + SELECT + INSERT 一轮),不是 6 次
            assert cur.execute.call_count == 3

    def test_table_missing_swallowed(self):
        """表不存在错误 → 静默返 False"""
        with patch("local_db._get_conn") as mock_conn:
            cur = MagicMock()
            mock_conn.return_value.cursor.return_value.__enter__.return_value = cur
            cur.execute.side_effect = Exception(
                'relation "agent_global_state" does not exist'
            )
            ok = gsp.persist_to_pg({"state": "normal", "active_breakers": []})
            assert ok is False

    def test_connection_failure_swallowed(self):
        """连接失败 → 返 False 不抛"""
        with patch("local_db._get_conn") as mock_conn:
            mock_conn.side_effect = Exception("connection refused")
            ok = gsp.persist_to_pg({"state": "normal", "active_breakers": []})
            assert ok is False

    def test_local_db_unavailable(self):
        """ImportError → 返 False"""
        with patch.dict("sys.modules", {"local_db": None}):
            ok = gsp.persist_to_pg({"state": "normal", "active_breakers": []})
            # 实际上 sys.modules None 会导致 import 错误,但函数应该捕获返 False
            assert ok is False


# ============================================================
# 3. load_from_pg 端到端
# ============================================================

class TestLoad:

    def test_load_with_data(self):
        with patch("local_db._get_conn") as mock_conn:
            cur = MagicMock()
            mock_conn.return_value.cursor.return_value.__enter__.return_value = cur
            cur.fetchone.return_value = (
                "blocked",
                '[{"cb_id": "CB01", "name": "日亏损熔断"}]',
            )
            payload = gsp.load_from_pg()
            assert payload is not None
            assert payload["state"] == "blocked"
            assert len(payload["active_breakers"]) == 1
            assert payload["active_breakers"][0]["cb_id"] == "CB01"

    def test_load_empty_state(self):
        with patch("local_db._get_conn") as mock_conn:
            cur = MagicMock()
            mock_conn.return_value.cursor.return_value.__enter__.return_value = cur
            cur.fetchone.return_value = ("normal", "[]")
            payload = gsp.load_from_pg()
            assert payload == {"state": "normal", "active_breakers": []}

    def test_load_table_missing(self):
        with patch("local_db._get_conn") as mock_conn:
            cur = MagicMock()
            mock_conn.return_value.cursor.return_value.__enter__.return_value = cur
            cur.execute.side_effect = Exception('relation "x" does not exist')
            payload = gsp.load_from_pg()
            assert payload is None

    def test_load_connection_fail(self):
        with patch("local_db._get_conn") as mock_conn:
            mock_conn.side_effect = Exception("connection refused")
            payload = gsp.load_from_pg()
            assert payload is None

    def test_load_no_row(self):
        with patch("local_db._get_conn") as mock_conn:
            cur = MagicMock()
            mock_conn.return_value.cursor.return_value.__enter__.return_value = cur
            cur.fetchone.return_value = None
            payload = gsp.load_from_pg()
            assert payload is None

    def test_load_jsonb_already_dict(self):
        """psycopg2 默认会反序列化 JSONB 为 list/dict"""
        with patch("local_db._get_conn") as mock_conn:
            cur = MagicMock()
            mock_conn.return_value.cursor.return_value.__enter__.return_value = cur
            cur.fetchone.return_value = (
                "degraded",
                [{"cb_id": "CB03"}],  # 已是 list
            )
            payload = gsp.load_from_pg()
            assert payload["state"] == "degraded"
            assert payload["active_breakers"][0]["cb_id"] == "CB03"


# ============================================================
# 4. restore_engine_state 端到端(配合 SafetyEngine)
# ============================================================

class TestRestore:

    def test_restore_no_data(self, fresh_engine):
        with patch.object(gsp, "load_from_pg", return_value=None):
            n = gsp.restore_engine_state(fresh_engine)
            assert n == 0
            assert not fresh_engine.get_active_breakers()

    def test_restore_empty_breakers(self, fresh_engine):
        with patch.object(gsp, "load_from_pg",
                          return_value={"state": "normal", "active_breakers": []}):
            n = gsp.restore_engine_state(fresh_engine)
            assert n == 0

    def test_restore_one_breaker(self, fresh_engine):
        tripped = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        auto_release = (datetime.now(timezone.utc) + timedelta(hours=23)).isoformat()
        with patch.object(gsp, "load_from_pg", return_value={
            "state": "blocked",
            "active_breakers": [
                {
                    "cb_id": "CB01",
                    "name": "日亏损熔断",
                    "tripped_at": tripped,
                    "auto_release_at": auto_release,
                    "reason": "test restore",
                    "severity": "blocked",
                }
            ],
        }):
            n = gsp.restore_engine_state(fresh_engine)
            assert n == 1
            assert fresh_engine.is_breaker_active("CB01")
            assert fresh_engine.get_global_state() == "blocked"

    def test_restore_unknown_cb_skipped(self, fresh_engine):
        """yaml 里没有的 CB 自动忽略(不爆)"""
        with patch.object(gsp, "load_from_pg", return_value={
            "state": "blocked",
            "active_breakers": [
                {"cb_id": "CB99", "tripped_at": "", "auto_release_at": ""},
            ],
        }):
            n = gsp.restore_engine_state(fresh_engine)
            assert n == 0

    def test_restore_invalid_timestamp_kept_in_engine(self, fresh_engine):
        """tripped_at 解析失败时保留默认 now,但不丢 CB"""
        with patch.object(gsp, "load_from_pg", return_value={
            "state": "blocked",
            "active_breakers": [
                {
                    "cb_id": "CB01",
                    "tripped_at": "not-a-date",
                    "auto_release_at": "also-not",
                    "reason": "x",
                }
            ],
        }):
            n = gsp.restore_engine_state(fresh_engine)
            assert n == 1
            assert fresh_engine.is_breaker_active("CB01")


# ============================================================
# 5. attach_to_engine 一键挂载
# ============================================================

class TestAttach:

    def test_attach_sets_persister(self, fresh_engine):
        with patch.object(gsp, "load_from_pg", return_value=None):
            gsp.attach_to_engine(fresh_engine)
            assert fresh_engine._state_persister is gsp.persist_to_pg

    def test_attach_swallows_errors(self, fresh_engine):
        """attach 内部异常不应抛出(safety 不能被基础设施故障阻断)"""
        with patch.object(gsp, "load_from_pg",
                          side_effect=RuntimeError("boom")):
            # 不应抛
            gsp.attach_to_engine(fresh_engine)


# ============================================================
# 6. 端到端:trip → persister 调用 → DB 写
# ============================================================

class TestEndToEnd:

    def test_trip_triggers_persist(self, fresh_engine):
        """trip CB 后 persister 应被调用(本测试用 spy 而非真 DB)"""
        spy_calls: list[dict] = []
        def spy(payload):
            spy_calls.append(payload)
            return True
        fresh_engine.set_state_persister(spy)

        fresh_engine.trip_breaker("CB01", reason="end-to-end")

        assert len(spy_calls) == 1
        assert spy_calls[0]["state"] == "blocked"
        assert spy_calls[0]["active_breakers"][0]["cb_id"] == "CB01"

    def test_release_triggers_persist(self, fresh_engine):
        spy_calls: list[dict] = []
        fresh_engine.set_state_persister(lambda p: spy_calls.append(p))

        fresh_engine.trip_breaker("CB02", reason="x")
        fresh_engine.release_breaker("CB02")

        assert len(spy_calls) == 2
        assert spy_calls[0]["state"] == "blocked"
        assert spy_calls[1]["state"] == "normal"
