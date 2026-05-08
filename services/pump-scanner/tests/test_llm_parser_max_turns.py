"""
R47 P8 — MAX_TURNS 5→110 + 命中上限强制汇总 单测

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_llm_parser_max_turns.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestMaxTurnsConstant:
    def test_max_turns_is_110_in_parse_strategy(self):
        """R47 P8 — parse_strategy 的 MAX_TURNS 改成了 110"""
        src = Path(__file__).resolve().parents[1] / "agent" / "llm_parser.py"
        content = src.read_text()
        # 找出 parse_strategy 函数体里的 MAX_TURNS 赋值
        # 简化:全文应不含 "MAX_TURNS = 5" 这种旧值
        assert "MAX_TURNS = 5" not in content, \
            "R47 P8 MAX_TURNS 应已从 5 改成 110(parse_strategy + parse_strategy_stream)"
        assert "MAX_TURNS = 110" in content, "MAX_TURNS = 110 应出现 2 处"

    def test_max_turns_constant_appears_twice(self):
        """parse_strategy + parse_strategy_stream 两处都应改"""
        src = Path(__file__).resolve().parents[1] / "agent" / "llm_parser.py"
        content = src.read_text()
        count = content.count("MAX_TURNS = 110")
        assert count >= 2, f"MAX_TURNS = 110 应在 sync + stream 两处都出现,实际 {count} 处"


class TestForcedSummaryOnLimit:
    def test_parse_strategy_has_forced_summary_block(self):
        """R47 P8 — parse_strategy 必须含 'tools=[]' 强制汇总代码"""
        src = Path(__file__).resolve().parents[1] / "agent" / "llm_parser.py"
        content = src.read_text()
        # 必须含 forced summary 关键 marker
        assert "MAX_TURNS hit" in content or "forcing summary" in content, \
            "命中上限必须 log warning + 强制汇总"
        assert "tools=[]" in content, \
            "强制汇总必须 tools=[] 禁止再调工具"
        # 应有 'turn == MAX_TURNS - 1' 触发条件
        assert "turn == MAX_TURNS - 1" in content


class TestFallbackMessageImproved:
    def test_no_more_unfriendly_apology(self):
        """R47 P8 — 老的'抱歉,我无法理解'文案改成更友好的引导"""
        src = Path(__file__).resolve().parents[1] / "agent" / "llm_parser.py"
        content = src.read_text()
        # 不应再有"抱歉,我无法理解您的策略描述"这种丧的话
        assert "抱歉，我无法理解您的策略描述" not in content
        # 必须有新引导话术
        assert "我没能给出明确建议" in content or "请将问题拆得更具体" in content
