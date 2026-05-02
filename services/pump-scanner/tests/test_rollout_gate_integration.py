"""
rollout_gate 接入主流程的集成测试 — W3 D5+ autonomous-loop 续 34

跑法:python3 -m pytest tests/test_rollout_gate_integration.py -v
覆盖:
  - thesis_loop._select_level 接 agent_v1_thesis_l3 gate
  - notify_loop.process 接 agent_v1_auto_mode gate
  - rollout_gate fail-safe(import 抛错时保守降级)
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.loops.thesis_loop import ThesisLoop  # noqa: E402
from agent.loops.notify_loop import NotifyLoop  # noqa: E402


# ── thesis_loop._select_level rollout 集成 ────────────────────


class TestThesisL3Gate:

    def setup_method(self):
        self.loop = ThesisLoop()

    def test_explicit_L3_downgrades_to_L2_when_gate_off(self):
        """default agent_v1_thesis_l3=0 → 任何 device 都不命中 → L3 → L2。"""
        assert self.loop._select_level("L3", 100, 80, device_id="any-dev") == "L2"

    def test_auto_high_score_downgrades_to_L2(self):
        """auto level + score 高(原本应选 L3)→ gate 0% → 走 L2。"""
        # score=80 > L2_max_score=70 → 原本会选 L3
        result = self.loop._select_level("auto", 100, 80, device_id="dev-1")
        assert result == "L2"

    def test_explicit_L1_unaffected_by_gate(self):
        assert self.loop._select_level("L1", 100, 80, device_id="dev-1") == "L1"

    def test_explicit_L2_unaffected_by_gate(self):
        assert self.loop._select_level("L2", 100, 80, device_id="dev-1") == "L2"

    def test_auto_low_position_low_score_returns_L1(self):
        """L1 路径不受 L3 gate 影响。"""
        assert self.loop._select_level("auto", 5, 30, device_id="dev-1") == "L1"

    def test_L3_gate_open_lets_device_through(self):
        """模拟 gate=100% 时,L3 应 stay L3。"""
        with patch("agent.rollout_gate.is_in_rollout", return_value=True):
            assert self.loop._select_level("L3", 100, 80, device_id="dev-1") == "L3"

    def test_L3_gate_partial_rollout_some_devices_in(self):
        """50% rollout — 有些 device 命中(返 L3),有些不命中(返 L2)。"""
        # 用真 gate(50%):500 device 应有部分命中
        l3_count = 0
        l2_count = 0
        for i in range(200):
            with patch("agent.rollout_gate.DEFAULT_ROLLOUT_PCT", {"agent_v1_thesis_l3": 50}):
                result = self.loop._select_level("L3", 100, 80, device_id=f"dev-{i}")
            if result == "L3":
                l3_count += 1
            else:
                l2_count += 1
        # 50% 应大致一半一半(松约束 [60, 140] 即可)
        assert 60 <= l3_count <= 140, f"50% gate L3 命中 {l3_count}/200,偏差大"
        assert l3_count + l2_count == 200

    def test_L3_gate_fail_safe_to_L2_on_import_error(self):
        """rollout_gate 抛错 → 保守降级 L2(不允许 L3 漏)。"""
        with patch("agent.rollout_gate.is_in_rollout", side_effect=RuntimeError("boom")):
            assert self.loop._select_level("L3", 100, 80, device_id="dev-1") == "L2"

    def test_L3_empty_device_id_downgrades(self):
        """无 device_id → bucket=99,任何 < 99% rollout 都不命中 → L2。"""
        # default 0% → 0 命中
        assert self.loop._select_level("L3", 100, 80, device_id="") == "L2"

    def test_L3_gate_keeps_explicit_L3_when_in_rollout(self):
        """显式 requested=L3 + gate 命中 → L3 不降级。"""
        with patch("agent.rollout_gate.is_in_rollout", return_value=True):
            assert self.loop._select_level("L3", 100, 80, device_id="lucky") == "L3"


# ── notify_loop.process auto_mode rollout 集成 ────────────────


class TestNotifyAutoModeGate:

    def setup_method(self):
        self.loop = NotifyLoop()

    def _make_event(self, user_id="dev-1"):
        return {
            "strategy_id": "s-1",
            "user_id": user_id,
            "strategy_name": "test",
            "matched_token": "0xabc",
            "matched_chain": "SOL",
            "trigger_context": {"score": 80},
        }

    @pytest.mark.asyncio
    async def test_auto_mode_downgrades_to_notify_when_gate_off(self):
        """default agent_v1_auto_mode=0 → 任何 device 都不命中 → auto → notify。"""
        # 不实际跑完整 process(safety/risk 会失败),只验 mode 降级逻辑
        # 通过 mock 内部来观测 mode 是否被改写
        with patch.object(
            self.loop, "_safety_pre_check",
            return_value=(True, "ok", {})
        ), patch.object(
            self.loop, "_risk_check",
            new=AsyncMock(return_value=(True, "ok"))
        ), patch.object(
            self.loop, "_calc_position",
            new=AsyncMock(return_value=(100.0, "fixed_pct", "ok"))
        ), patch.object(
            self.loop, "_handle_notify_only",
            new=AsyncMock(return_value="NOTIFY_RESULT")
        ) as mock_notify:
            result = await self.loop.process(
                self._make_event(), mode="auto", dry_run=True,
            )
        # gate 未命中 → 应走 _handle_notify_only(降级为 notify),不是 _handle_auto
        mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_mode_passes_through_when_gate_open(self):
        """gate 100% → auto stay auto → 走 _handle_hitl_pending 或 _handle_auto_direct
        (具体哪个看 HITL 触发,这里不验单一 handler,只验 _handle_notify_only 没被叫)。"""
        with patch("agent.rollout_gate.is_in_rollout", return_value=True), \
             patch.object(self.loop, "_safety_pre_check",
                          return_value=(True, "ok", {})), \
             patch.object(self.loop, "_risk_check",
                          new=AsyncMock(return_value=(True, "ok"))), \
             patch.object(self.loop, "_calc_position",
                          new=AsyncMock(return_value=(100.0, "fixed_pct", "ok"))), \
             patch.object(self.loop, "_handle_notify_only",
                          new=AsyncMock(return_value="NOTIFY_RESULT")) as mock_notify, \
             patch.object(self.loop, "_handle_hitl_pending",
                          new=AsyncMock(return_value="HITL_RESULT")) as mock_hitl, \
             patch.object(self.loop, "_handle_auto_direct",
                          new=AsyncMock(return_value="AUTO_RESULT")) as mock_auto_direct:
            result = await self.loop.process(
                self._make_event(), mode="auto", dry_run=True,
            )
        # gate 命中 → mode 保持 auto → 不应调 _handle_notify_only
        mock_notify.assert_not_called()
        # 应调 hitl 或 auto_direct 其中一个
        assert mock_hitl.called or mock_auto_direct.called

    @pytest.mark.asyncio
    async def test_paper_mode_unaffected_by_auto_gate(self):
        """mode=paper 不受 auto gate 影响。"""
        with patch.object(
            self.loop, "_safety_pre_check", return_value=(True, "ok", {})
        ), patch.object(
            self.loop, "_risk_check", new=AsyncMock(return_value=(True, "ok"))
        ), patch.object(
            self.loop, "_calc_position",
            new=AsyncMock(return_value=(100.0, "fixed_pct", "ok"))
        ), patch.object(
            self.loop, "_handle_paper",
            new=AsyncMock(return_value="PAPER_RESULT")
        ) as mock_paper:
            result = await self.loop.process(
                self._make_event(), mode="paper", dry_run=True,
            )
        mock_paper.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_mode_unaffected_by_auto_gate(self):
        """mode=notify 不受 auto gate 影响。"""
        with patch.object(
            self.loop, "_safety_pre_check", return_value=(True, "ok", {})
        ), patch.object(
            self.loop, "_risk_check", new=AsyncMock(return_value=(True, "ok"))
        ), patch.object(
            self.loop, "_calc_position",
            new=AsyncMock(return_value=(100.0, "fixed_pct", "ok"))
        ), patch.object(
            self.loop, "_handle_notify_only",
            new=AsyncMock(return_value="NOTIFY_RESULT")
        ) as mock_notify:
            result = await self.loop.process(
                self._make_event(), mode="notify", dry_run=True,
            )
        mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_mode_gate_fail_safe_to_notify(self):
        """rollout_gate import 抛错 → 保守降级 notify(不允许 auto 漏)。"""
        with patch("agent.rollout_gate.is_in_rollout",
                   side_effect=RuntimeError("boom")), \
             patch.object(self.loop, "_safety_pre_check",
                          return_value=(True, "ok", {})), \
             patch.object(self.loop, "_risk_check",
                          new=AsyncMock(return_value=(True, "ok"))), \
             patch.object(self.loop, "_calc_position",
                          new=AsyncMock(return_value=(100.0, "fixed_pct", "ok"))), \
             patch.object(self.loop, "_handle_notify_only",
                          new=AsyncMock(return_value="NOTIFY_RESULT")) as mock_notify:
            result = await self.loop.process(
                self._make_event(), mode="auto", dry_run=True,
            )
        mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_mode_gate_empty_user_id_fails_safe(self):
        """user_id 缺失 → bucket=99 → gate 0% 不命中 → notify。"""
        event = self._make_event(user_id="")
        with patch.object(
            self.loop, "_safety_pre_check", return_value=(True, "ok", {})
        ), patch.object(
            self.loop, "_risk_check", new=AsyncMock(return_value=(True, "ok"))
        ), patch.object(
            self.loop, "_calc_position",
            new=AsyncMock(return_value=(100.0, "fixed_pct", "ok"))
        ), patch.object(
            self.loop, "_handle_notify_only",
            new=AsyncMock(return_value="NOTIFY_RESULT")
        ) as mock_notify:
            result = await self.loop.process(event, mode="auto", dry_run=True)
        mock_notify.assert_called_once()
