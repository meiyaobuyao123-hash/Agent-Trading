"""
rollout_gate 单元测试 — W3 D5+ autonomous-loop 续 33

跑法:python3 -m pytest tests/test_rollout_gate.py -v
真用见 docs/runbook/beta-rollout.md
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.rollout_gate import (  # noqa: E402
    DEFAULT_ROLLOUT_PCT,
    RolloutDecision,
    _bucket,
    decide,
    get_rollout_pct,
    is_in_rollout,
    list_features,
)


# ── DEFAULT_ROLLOUT_PCT 配置健全性 ──────────────────────────


def test_default_rollout_pct_has_main_gate():
    """agent_v1 主门必须存在(灰度推进入口)。"""
    assert "agent_v1" in DEFAULT_ROLLOUT_PCT


def test_default_rollout_pct_main_open():
    """R35:主门 100%,内部团队试用全开。"""
    assert DEFAULT_ROLLOUT_PCT["agent_v1"] == 100


def test_default_rollout_pct_safety_full_open():
    """input_filter / safety_engine 已就位,可全开避免误关。"""
    assert DEFAULT_ROLLOUT_PCT.get("agent_v1_input_filter") == 100
    assert DEFAULT_ROLLOUT_PCT.get("agent_v1_safety_engine") == 100


def test_default_rollout_pct_thesis_l3_open():
    """R35:L3 thesis debate 全开(自己 + 团队都用真 debate)。"""
    assert DEFAULT_ROLLOUT_PCT["agent_v1_thesis_l3"] == 100


def test_default_rollout_pct_auto_mode_blocked():
    """⚠️ auto 模式真金交易**保持 0**(内测期防误触发)。"""
    assert DEFAULT_ROLLOUT_PCT["agent_v1_auto_mode"] == 0


def test_default_rollout_pct_real_llm_judge_blocked():
    """真 LLM judge 留 W17-W22。"""
    assert DEFAULT_ROLLOUT_PCT["agent_v1_real_llm_judge"] == 0


def test_default_rollout_pct_values_in_range():
    for f, pct in DEFAULT_ROLLOUT_PCT.items():
        assert 0 <= pct <= 100, f"{f}={pct} out of [0,100]"


# ── _bucket determinism ────────────────────────────────────


def test_bucket_in_range_0_99():
    for d in ["dev-1", "dev-2", "uuid-x", "anonymous-99"]:
        for f in ["agent_v1", "agent_v1_thesis_l3"]:
            b = _bucket(d, f)
            assert 0 <= b <= 99


def test_bucket_deterministic_same_inputs():
    """同 device + feature 永远相同。"""
    for _ in range(5):
        assert _bucket("dev-1", "agent_v1") == _bucket("dev-1", "agent_v1")


def test_bucket_different_devices_distribute():
    """不同 device 应分散到不同 bucket(随机性 sanity)。"""
    buckets = [_bucket(f"dev-{i}", "agent_v1") for i in range(100)]
    # 100 个 device 应至少分到 30 个不同 bucket(松约束)
    assert len(set(buckets)) >= 30


def test_bucket_different_features_independent():
    """同 device 不同 feature 应不同 bucket(独立分桶)。"""
    same_count = 0
    for i in range(50):
        b1 = _bucket(f"dev-{i}", "agent_v1")
        b2 = _bucket(f"dev-{i}", "agent_v1_thesis_l3")
        if b1 == b2:
            same_count += 1
    # 50 个 device 同 bucket 应 < 5 (独立分桶随机命中)
    assert same_count < 10, f"feature 不独立?same={same_count}/50"


def test_bucket_empty_device_id_returns_99():
    """无 device_id → 分到 bucket 99(最后才命中,防 anonymous 进 canary)。"""
    assert _bucket("", "agent_v1") == 99
    assert _bucket("", "anything") == 99


# ── is_in_rollout ────────────────────────────────────────────


def test_is_in_rollout_pct_0_never_hits():
    for i in range(20):
        assert is_in_rollout(f"dev-{i}", "agent_v1", rollout_pct=0) is False


def test_is_in_rollout_pct_100_always_hits():
    for i in range(20):
        assert is_in_rollout(f"dev-{i}", "agent_v1", rollout_pct=100) is True


def test_is_in_rollout_uses_default_when_pct_neg1():
    """rollout_pct=-1 → 从 DEFAULT 取。R35:安全 feature 100% 应命中,
    主门 100% 也应命中,auto_mode 0% 不命中。"""
    assert is_in_rollout("dev-1", "agent_v1_input_filter") is True
    assert is_in_rollout("dev-1", "agent_v1") is True
    assert is_in_rollout("dev-1", "agent_v1_auto_mode") is False


def test_is_in_rollout_unknown_feature_treated_as_0():
    """未知 feature 默认 0%,never hits(fail-safe)。"""
    assert is_in_rollout("dev-1", "nonexistent_feature") is False


def test_is_in_rollout_50pct_distribution():
    """50% 大约一半命中(松约束 [40, 60])。"""
    hits = sum(
        1 for i in range(200)
        if is_in_rollout(f"dev-{i}", "agent_v1", rollout_pct=50)
    )
    assert 80 <= hits <= 120, f"50% rollout 命中 {hits}/200,偏差大"


def test_is_in_rollout_5pct_canary_distribution():
    """5% canary:200 个 device 应有 ~10 命中(松 [0, 25])。"""
    hits = sum(
        1 for i in range(200)
        if is_in_rollout(f"dev-{i}", "agent_v1", rollout_pct=5)
    )
    assert 0 <= hits <= 25


def test_is_in_rollout_no_flip_flop_when_pct_increases():
    """rollout_pct 从 5 升到 25 → 原 5% 命中的人应仍命中(不能掉线)。"""
    hit_at_5 = {
        f"dev-{i}" for i in range(500)
        if is_in_rollout(f"dev-{i}", "agent_v1", rollout_pct=5)
    }
    hit_at_25 = {
        f"dev-{i}" for i in range(500)
        if is_in_rollout(f"dev-{i}", "agent_v1", rollout_pct=25)
    }
    assert hit_at_5.issubset(hit_at_25), (
        f"flip-flop:这些 device 在 5% 命中但 25% 没命中: {hit_at_5 - hit_at_25}"
    )


# ── decide(完整 RolloutDecision)──────────────────────────


def test_decide_returns_full_decision():
    d = decide("dev-1", "agent_v1", rollout_pct=50)
    assert isinstance(d, RolloutDecision)
    assert d.feature == "agent_v1"
    assert d.device_id == "dev-1"
    assert d.rollout_pct == 50
    assert 0 <= d.bucket <= 99
    assert d.in_rollout == (d.bucket < 50)


def test_decide_uses_default_when_pct_neg1():
    d = decide("dev-1", "agent_v1_input_filter")
    assert d.rollout_pct == 100
    assert d.in_rollout is True


def test_decide_pct_0_in_rollout_false():
    d = decide("dev-1", "agent_v1", rollout_pct=0)
    assert d.in_rollout is False


# ── get_rollout_pct / list_features ─────────────────────────


def test_get_rollout_pct_known():
    """R35:agent_v1 主门 100,input_filter 100,auto_mode 0。"""
    assert get_rollout_pct("agent_v1") == 100
    assert get_rollout_pct("agent_v1_input_filter") == 100
    assert get_rollout_pct("agent_v1_auto_mode") == 0


def test_get_rollout_pct_unknown_default_0():
    assert get_rollout_pct("totally_fake_feature") == 0


def test_list_features_returns_copy():
    features = list_features()
    assert "agent_v1" in features
    original = get_rollout_pct("agent_v1")
    # mutation 不应影响内部状态
    features["agent_v1"] = 999
    assert get_rollout_pct("agent_v1") == original
