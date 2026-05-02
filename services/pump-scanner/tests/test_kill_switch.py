"""
Kill Switch 真实施测试 — R37 P0-1
跑法:python3 -m pytest tests/test_kill_switch.py -v

验证:
  1. routes_admin /agent/kill-switch 触发 CB14 → engine.get_global_state() == 'blocked'
  2. /agent/kill-switch 必须 confirm=true(防误触)
  3. /agent/kill-switch/release 解除后 global_state 回 'normal'
  4. 全局 blocked 时 check_safety_for_trade 直接返 BLOCK(不论 ctx 内容)
  5. 重复 trip 幂等(同一 CB 不更新 tripped_at)
  6. trip 耗时 < 100ms(< 10s SLA 充分满足)
  7. /agent/state 返当前全局状态 + active CBs
  8. /cb 列表含 14 个 CB(CB01-CB14)
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.safety_engine import get_safety_engine, CheckOutcome, _engine  # noqa
from agent.trade_executor import check_safety_for_trade  # noqa


@pytest.fixture(autouse=True)
def _reset_engine_and_mock_mode(monkeypatch):
    """每个测试都重置 SafetyEngine 单例 + 强制 MOCK_MODE=false,避免互相污染。

    注:其他测试(test_routes_memory_reviews)会设 MOCK_MODE=true 但不清,
    routes_admin 在模块加载时读 env;这里直接 patch 模块属性兜底。
    """
    import agent.safety_engine as se
    se._engine = None
    # 强制 routes_admin 模块的 MOCK_MODE = False
    import api.routes_admin as ra
    monkeypatch.setattr(ra, "MOCK_MODE", False, raising=False)
    yield
    eng = get_safety_engine()
    if "CB14" in eng._active_breakers:
        eng.release_breaker("CB14", manual=True)


@pytest.fixture
def client():
    """嵌入式 FastAPI(只挂 routes_admin)。"""
    from api.routes_admin import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ── 基础 trip / release ─────────────────────────────────────


def test_engine_loads_cb14():
    """CB14 必须在 yaml 注册(safety_policy.yaml)。"""
    engine = get_safety_engine()
    assert "CB14" in engine._cb_index, "CB14 manual kill switch 未在 yaml 注册"
    cb14 = engine._cb_index["CB14"]
    assert cb14["severity"] == "blocked"
    assert cb14.get("auto_release_after_min") is None  # 永久 BLOCK


def test_kill_switch_trip_blocks_globally():
    """trip CB14 → global_state == 'blocked'。"""
    engine = get_safety_engine()
    assert engine.get_global_state() == "normal"
    state = engine.trip_breaker("CB14", "manual:测试")
    assert state is not None
    assert engine.get_global_state() == "blocked"
    assert "CB14" in engine.get_active_breakers()


def test_kill_switch_release():
    """release CB14 → global_state 回 'normal'。"""
    engine = get_safety_engine()
    engine.trip_breaker("CB14", "test")
    assert engine.get_global_state() == "blocked"
    released = engine.release_breaker("CB14", manual=True)
    assert released is True
    assert engine.get_global_state() == "normal"


def test_kill_switch_idempotent_trip():
    """重复 trip 同一 CB 不更新 tripped_at(幂等)。"""
    engine = get_safety_engine()
    s1 = engine.trip_breaker("CB14", "first")
    t1 = s1.tripped_at
    time.sleep(0.01)
    s2 = engine.trip_breaker("CB14", "second")
    assert s2.tripped_at == t1, "重复 trip 应保留首次时间"


def test_kill_switch_trip_under_10s_sla():
    """trip 耗时 < 100ms(SLA < 10s 充分满足)。"""
    engine = get_safety_engine()
    t0 = time.time()
    engine.trip_breaker("CB14", "perf-test")
    took_ms = (time.time() - t0) * 1000
    assert took_ms < 100, f"trip 耗时 {took_ms:.1f}ms > 100ms"


# ── trade_executor 接通 ────────────────────────────────────


def test_check_safety_for_trade_blocked_when_kill_switch_active():
    """全局 blocked 时 check_safety_for_trade 直接返 BLOCK,不论 ctx。"""
    engine = get_safety_engine()
    engine.trip_breaker("CB14", "manual kill")
    # 即便 ctx 完全干净,也应被 kill switch 拦
    block = check_safety_for_trade({
        "amount_usd": 50, "action": "buy", "mode": "paper",
        "agent_global_state": "normal",  # ctx 即便说 normal,kill switch 优先
        "is_honeypot": False, "liquidity_usd": 100000,
    })
    assert block is not None
    assert block.outcome == CheckOutcome.BLOCK
    assert block.rule_id == "CB14"


def test_check_safety_for_trade_not_blocked_when_normal():
    """无 kill switch 时 check_safety_for_trade 不会因 global_state 拦。"""
    engine = get_safety_engine()
    assert engine.get_global_state() == "normal"
    block = check_safety_for_trade({
        "amount_usd": 50, "action": "buy", "mode": "paper",
        "agent_global_state": "normal",
        "is_honeypot": False, "liquidity_usd": 100000,
        "is_blacklisted": False, "regime": "TRENDING_UP",
    })
    # paper 模式 + 干净 ctx → 应该不被拦(或仅其他 HR 拦,但 CB14 不会)
    if block is not None:
        assert block.rule_id != "CB14", f"非 kill switch 状态不应被 CB14 拦: {block}"


# ── routes_admin endpoints ─────────────────────────────────


def test_route_kill_switch_requires_confirm(client):
    """confirm=false 必须返 400。"""
    r = client.post("/api/admin/agent/kill-switch", json={"reason": "test", "confirm": False})
    assert r.status_code == 400


def test_route_kill_switch_trip_returns_200(client):
    r = client.post("/api/admin/agent/kill-switch", json={"reason": "drill", "confirm": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["global_state"] == "blocked"
    assert body["cb_id"] == "CB14"
    assert body["took_ms"] < 1000  # < 1s SLA,远 <10s


def test_route_kill_switch_release_returns_200(client):
    # 先 trip 再 release
    client.post("/api/admin/agent/kill-switch", json={"reason": "x", "confirm": True})
    r = client.post(
        "/api/admin/agent/kill-switch/release",
        json={"reason": "drill done", "confirm": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["released"] is True
    assert body["global_state"] == "normal"


def test_route_release_requires_confirm(client):
    r = client.post(
        "/api/admin/agent/kill-switch/release",
        json={"reason": "x", "confirm": False},
    )
    assert r.status_code == 400


def test_route_state_returns_normal_initially(client):
    r = client.get("/api/admin/agent/state")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "normal"
    assert body["active_cbs"] == []


def test_route_state_returns_blocked_after_kill(client):
    client.post("/api/admin/agent/kill-switch", json={"reason": "x", "confirm": True})
    r = client.get("/api/admin/agent/state")
    body = r.json()
    assert body["status"] == "blocked"
    assert len(body["active_cbs"]) == 1
    assert body["active_cbs"][0]["cb_id"] == "CB14"


def test_route_cb_list_returns_14_breakers(client):
    """全部 14 个 CB 都应在列表中。"""
    r = client.get("/api/admin/cb")
    assert r.status_code == 200
    body = r.json()
    cb_ids = {b["id"] for b in body["breakers"]}
    expected = {f"CB{i:02d}" for i in range(1, 15)}
    assert expected.issubset(cb_ids), f"缺 CB: {expected - cb_ids}"


def test_route_cb_reset(client):
    """人工 reset 任意 CB(测 CB14)。"""
    client.post("/api/admin/agent/kill-switch", json={"reason": "x", "confirm": True})
    r = client.post(
        "/api/admin/cb/CB14/reset",
        json={"reason": "test reset"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["released"] is True
    assert body["global_state"] == "normal"


def test_route_admin_token_check(client, monkeypatch):
    """ADMIN_TOKEN 设了之后必须匹配。"""
    monkeypatch.setattr("api.routes_admin.ADMIN_TOKEN", "secret123")
    # 不传 token → 403
    r = client.post("/api/admin/agent/kill-switch", json={"reason": "x", "confirm": True})
    assert r.status_code == 403
    # 错 token → 403
    r = client.post(
        "/api/admin/agent/kill-switch",
        json={"reason": "x", "confirm": True},
        headers={"X-Admin-Token": "wrong"},
    )
    assert r.status_code == 403
    # 对 token → 200
    r = client.post(
        "/api/admin/agent/kill-switch",
        json={"reason": "x", "confirm": True},
        headers={"X-Admin-Token": "secret123"},
    )
    assert r.status_code == 200
