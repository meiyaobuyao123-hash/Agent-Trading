"""
Rollout Gate — 灰度发布的运行时分桶判定

引用 docs/runbook/beta-rollout.md(5% → 25% → 100% 三阶段)
引用 agent/prompt_loader.py(同 bucket 算法,独立空间)

设计:
  is_in_rollout(device_id, feature, rollout_pct) → bool
    - 算法:bucket = sha1(device_id + ":" + feature) % 100
    - 命中:bucket < rollout_pct
    - 同 device_id + feature 永远稳定(deterministic):
        rollout_pct 升 → 旧用户继续命中 + 多新用户加入
        rollout_pct 降 → 部分用户保持命中(优先保留低 bucket)
    - 不同 feature 独立分桶(避免同一组 device 命中所有 feature)

  get_rollout_pct(feature) → int(0-100)
    - 当前默认 hardcoded(W7+ 真上线后可挪到 DB 让 admin 改)
    - 关键 feature:
      - agent_v1                       — 全 Agent v1 流量门
      - agent_v1_thesis_l3             — L3 thesis debate(贵)
      - agent_v1_auto_mode             — auto 模式真金交易
      - agent_v1_kms_signing           — KMS 签名
      - agent_v1_real_llm_judge        — 真 LLM judge(W17-W22)

  使用者(call site)样例:
    if is_in_rollout(device_id, "agent_v1"):
        # 走 Agent v1 路径
    else:
        # 走旧路径 / fallback

实操:
  灰度推进:get_rollout_pct 改 5 → 25 → 100;旧路径在 100% 后才能删
  紧急 rollback:get_rollout_pct 改回 0(代码改 + 重启)
  细粒度:不同 feature 独立切换(thesis_l3 100% 之前 auto_mode 可能仍 25%)

测试:
  - 同 device + feature 永远稳定
  - rollout_pct=0 → 任何 device 都不命中
  - rollout_pct=100 → 任何 device 都命中
  - 升 rollout_pct 后旧命中仍命中(no flip-flop)
"""
from __future__ import annotations
import hashlib
import logging
from dataclasses import dataclass
from typing import Dict

log = logging.getLogger(__name__)


# ── feature → 当前 rollout_pct 配置 ──────────────────────────
#
# 改这里推进灰度。任何 PR 改这里需:
#   1. 当前 eval all_hard_gates=✓
#   2. 上一阶段跑满最短观察期(5%≥1w / 25%≥2w)
#   3. ops/PM/safety 三方确认 + sign-off
# 见 docs/runbook/beta-rollout.md §3 推进流程。
DEFAULT_ROLLOUT_PCT: Dict[str, int] = {
    # 主门(R35:全开,内部团队试用)
    "agent_v1": 100,               # 整体 Agent v1 流量

    # 子 feature 独立 gate
    "agent_v1_thesis_l3": 100,     # L3 thesis debate 全开(自己 + 团队都用真 debate)
    "agent_v1_l3_debate_full": 100,
    "agent_v1_auto_mode": 0,       # ⚠️ 真金交易保持 0 — 内部测试期防误触发
                                    #    (后续手动测稳后,改 100 或单独给某些 device 开)
    "agent_v1_real_llm_judge": 0,  # 真 LLM judge(W17-W22 后接通)

    # 安全相关(input_filter / safety_engine 100%)
    "agent_v1_input_filter": 100,  # SEV-0 真覆盖
    "agent_v1_safety_engine": 100, # 30 HR + 13 CB + 5 C 全开
}


@dataclass
class RolloutDecision:
    in_rollout: bool
    bucket: int          # 0-99
    rollout_pct: int     # 0-100
    feature: str
    device_id: str       # echo(便于 audit log)


def _bucket(device_id: str, feature: str) -> int:
    """deterministic bucket 0-99,同 device + feature 永远相同。"""
    if not device_id:
        # 无 device_id → 分到 bucket 99(最后才命中)
        # 避免没 device_id 的 anonymous 流量提前进 5% canary
        return 99
    h = hashlib.sha1((device_id + ":" + feature).encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 100


def is_in_rollout(
    device_id: str, feature: str,
    rollout_pct: int = -1,
) -> bool:
    """快速判定。rollout_pct=-1 时从 DEFAULT_ROLLOUT_PCT 取。"""
    if rollout_pct < 0:
        rollout_pct = DEFAULT_ROLLOUT_PCT.get(feature, 0)
    if rollout_pct <= 0:
        return False
    if rollout_pct >= 100:
        return True
    return _bucket(device_id, feature) < rollout_pct


def decide(
    device_id: str, feature: str,
    rollout_pct: int = -1,
) -> RolloutDecision:
    """完整决策(含 bucket 数,便于 audit)。"""
    if rollout_pct < 0:
        rollout_pct = DEFAULT_ROLLOUT_PCT.get(feature, 0)
    bucket = _bucket(device_id, feature)
    if rollout_pct <= 0:
        in_rollout = False
    elif rollout_pct >= 100:
        in_rollout = True
    else:
        in_rollout = bucket < rollout_pct
    return RolloutDecision(
        in_rollout=in_rollout, bucket=bucket,
        rollout_pct=rollout_pct, feature=feature, device_id=device_id,
    )


def get_rollout_pct(feature: str) -> int:
    """当前 rollout_pct(W7+ 可挪 DB,目前 hardcoded)。"""
    return DEFAULT_ROLLOUT_PCT.get(feature, 0)


def list_features() -> Dict[str, int]:
    """所有 feature + 当前 pct(给 admin dashboard / audit log)。"""
    return dict(DEFAULT_ROLLOUT_PCT)
