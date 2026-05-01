"""
routes_agent: memory rules CRUD + reviews 测试 — W3 D5+
对接 Phase 3 Flutter UI:
  - GET /api/agent/memory/rules
  - PATCH /api/agent/memory/rules/{id}
  - DELETE /api/agent/memory/rules/{id}
  - POST /api/agent/memory/rule-proposals/{id}/approve
  - GET /api/agent/reviews

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_routes_memory_reviews.py -v
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 一定要在 import 前设 MOCK_MODE,否则 routes 里 os.environ.get 已读
os.environ["MOCK_MODE"] = "true"

# 本地 Py3.9 vs routes_thesis PEP 604 union syntax 兼容:
# 直接挂 routes_agent.router 到迷你 FastAPI app,避免 import api.app(会拉一堆别的 router)
from fastapi import FastAPI  # noqa: E402
from api.routes_agent import router as agent_router  # noqa: E402

app = FastAPI()
app.include_router(agent_router)
client = TestClient(app)


# ── Memory rules ────────────────────────────────────────────

def test_list_rules_mock_mode_returns_empty():
    """MOCK_MODE 下 list 返空数组(不是 500)。"""
    resp = client.get("/api/agent/memory/rules")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "mock"
    assert body["rules"] == []


def test_list_rules_db_mode_maps_supabase_rows():
    """非 MOCK_MODE 下,读 Supabase agent_memory 并映射成 SemanticRule schema。"""
    fake_row = {
        "id": "rule-001",
        "content": "聪明钱 elite ≥ 75 + 流动性 > $50K → 仓位上调 20%",
        "structured_data": {
            "condition": "smart_score>=75 AND liquidity_usd>50000",
            "action": "position_size_multiplier:1.2",
            "active_regimes": ["TRENDING_UP"],
            "regimes_observed": ["TRENDING_UP", "BREAKOUT"],
        },
        "comply_win": 28, "comply_lose": 12,
        "is_active": True,
        "shadow_mode_until": None,
        "dormant_since": None,
        "match_count": 47,
        "wilson_ci_lower": 0.62,
        "created_at": "2026-04-09T00:00:00Z",
        "updated_at": "2026-04-29T00:00:00Z",
    }
    fake_resp = MagicMock(data=[fake_row])
    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = fake_resp

    with patch.dict(os.environ, {"MOCK_MODE": "false"}):
        with patch("database.get_db", return_value=fake_db):
            resp = client.get("/api/agent/memory/rules")

    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "db"
    assert body["count"] == 1
    rule = body["rules"][0]
    assert rule["rule_id"] == "rule-001"
    assert rule["status"] == "active"
    assert rule["match_count"] == 47
    assert rule["evidence"]["sample_size"] == 40  # 28 + 12
    assert rule["evidence"]["wilson_ci_lower"] == 0.62
    assert "TRENDING_UP" in rule["active_regimes"]


def test_list_rules_shadow_mode_status():
    """有 shadow_mode_until 的规则 status 标 shadow。"""
    fake_row = {
        "id": "rule-002",
        "content": "RANGING regime → BC < 8% 禁开仓",
        "structured_data": {"condition": "regime=RANGING AND bc<8", "action": "block_entry"},
        "is_active": True,
        "shadow_mode_until": "2026-05-15T00:00:00Z",
        "comply_win": 5, "comply_lose": 0,
    }
    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[fake_row])
    with patch.dict(os.environ, {"MOCK_MODE": "false"}):
        with patch("database.get_db", return_value=fake_db):
            resp = client.get("/api/agent/memory/rules")
    assert resp.json()["rules"][0]["status"] == "shadow"


def test_list_rules_dormant_status():
    """有 dormant_since 但无 shadow 的规则 status 标 dormant。"""
    fake_row = {
        "id": "rule-003",
        "content": "KOL Tier-1 sentiment > 0.7 → 加权 +5",
        "structured_data": {"condition": "kol_tier=1", "action": "score+5"},
        "is_active": True,
        "shadow_mode_until": None,
        "dormant_since": "2026-04-01T00:00:00Z",
        "comply_win": 12, "comply_lose": 8,
    }
    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[fake_row])
    with patch.dict(os.environ, {"MOCK_MODE": "false"}):
        with patch("database.get_db", return_value=fake_db):
            resp = client.get("/api/agent/memory/rules")
    assert resp.json()["rules"][0]["status"] == "dormant"


def test_list_rules_disabled_status():
    """is_active=false → status=disabled。"""
    fake_row = {
        "id": "rule-004",
        "content": "禁用的规则",
        "structured_data": {},
        "is_active": False,
        "shadow_mode_until": None,
        "dormant_since": None,
        "comply_win": 0, "comply_lose": 0,
    }
    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[fake_row])
    with patch.dict(os.environ, {"MOCK_MODE": "false"}):
        with patch("database.get_db", return_value=fake_db):
            resp = client.get("/api/agent/memory/rules")
    assert resp.json()["rules"][0]["status"] == "disabled"


def test_list_rules_db_error_returns_empty_not_500():
    """DB 不可达时返空数组而不是 500(Flutter 才能 fallback 到本地 mock)。"""
    with patch.dict(os.environ, {"MOCK_MODE": "false"}):
        with patch("database.get_db", side_effect=Exception("PG connection refused")):
            resp = client.get("/api/agent/memory/rules")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "error"
    assert body["rules"] == []


def test_update_rule_invalid_status_400():
    """status 必须是 active / disabled,其他值 400。"""
    resp = client.patch(
        "/api/agent/memory/rules/rule-x", json={"status": "shadow"}
    )
    assert resp.status_code == 400


def test_update_rule_active_in_mock_mode():
    resp = client.patch(
        "/api/agent/memory/rules/rule-x", json={"status": "active"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "rule_id": "rule-x", "status": "active"}


def test_update_rule_disabled_in_mock_mode():
    resp = client.patch(
        "/api/agent/memory/rules/rule-x", json={"status": "disabled"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"


def test_delete_rule_mock_mode():
    resp = client.delete("/api/agent/memory/rules/rule-y")
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] is True
    assert body["rule_id"] == "rule-y"


def test_approve_rule_proposal_mock_mode():
    resp = client.post("/api/agent/memory/rule-proposals/rp-001/approve")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["proposal_id"] == "rp-001"
    assert body["shadow_mode_days"] == 14
    assert body["promoted_rule_id"].startswith("sm-")


# ── Reviews ─────────────────────────────────────────────────

def test_review_daily_default_period():
    """默认 period=daily,返回 mock 复盘。"""
    resp = client.get("/api/agent/reviews")
    assert resp.status_code == 200
    r = resp.json()
    assert r["period"] == "daily"
    assert r["source"] == "mock"
    assert r["summary"]["headline"]
    assert len(r["insights"]) >= 2
    assert len(r["rule_proposals"]) >= 1
    assert r["metrics"]["trade_count"] > 0


def test_review_weekly_metrics_differ_from_daily():
    """weekly 期数据应与 daily 不同(确认 period 路由生效)。"""
    daily = client.get("/api/agent/reviews?period=daily").json()
    weekly = client.get("/api/agent/reviews?period=weekly").json()
    assert daily["metrics"]["trade_count"] != weekly["metrics"]["trade_count"]
    assert daily["summary"]["headline"] != weekly["summary"]["headline"]


def test_review_invalid_period_422():
    """非 daily/weekly/monthly 应被 query 验证拒绝。"""
    resp = client.get("/api/agent/reviews?period=hourly")
    assert resp.status_code == 422


def test_review_period_to_minus_from_matches_window():
    """period_to - period_from 大致等于 period 窗口。"""
    from datetime import datetime
    weekly = client.get("/api/agent/reviews?period=weekly").json()
    pf = datetime.fromisoformat(weekly["period_from"].replace("Z", "+00:00"))
    pt = datetime.fromisoformat(weekly["period_to"].replace("Z", "+00:00"))
    delta_days = (pt - pf).days
    assert delta_days == 7


def test_review_insights_have_required_fields():
    """每条 insight 必须有 type / text / llm_judge_score。"""
    r = client.get("/api/agent/reviews?period=daily").json()
    for ins in r["insights"]:
        assert ins["type"] in ("win_pattern", "loss_pattern", "risk_warning", "observation")
        assert ins["text"]
        assert "llm_judge_score" in ins
