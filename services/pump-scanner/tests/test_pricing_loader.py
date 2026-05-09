"""
R52 — pricing_loader 单测

不依赖外部网络:用 mock urllib.request.urlopen
覆盖:
  - LiteLLM JSON 解析正确(per-token → per-MTok 转换)
  - 模型 ID 归一化(老格式 -20250514 → LiteLLM 标准 ID)
  - Cache file 读写
  - 三层 fallback chain(LiteLLM → cache → yaml → None)
  - 未知模型返 None(不"瞎算")
  - calc_cost UnknownModelError 路径

Python 3.9 兼容。
"""

from __future__ import annotations

import json
import sys
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──────────────────────────────────────────────────────────
# Helper: build minimal LiteLLM-shaped JSON
# ──────────────────────────────────────────────────────────

def _fake_litellm_json() -> dict:
    """LiteLLM 真实结构:每模型有 input_cost_per_token / output_cost_per_token。

    R52 校准:LiteLLM 实际 key 是 claude-* 不是 anthropic/claude-*
    Haiku 4.5 真实价 $1/$5(不是 $0.25)
    Opus 4.7 真实价 $5/$25(L3 推荐用)
    """
    return {
        "claude-sonnet-4-5": {
            "input_cost_per_token": 3e-6,    # = $3 / MTok
            "output_cost_per_token": 15e-6,  # = $15 / MTok
            "max_tokens": 8192,
        },
        "claude-sonnet-4-6": {
            "input_cost_per_token": 3e-6,
            "output_cost_per_token": 15e-6,
        },
        "claude-haiku-4-5": {
            "input_cost_per_token": 1e-6,
            "output_cost_per_token": 5e-6,
        },
        "claude-haiku-4-5-20251001": {
            "input_cost_per_token": 1e-6,
            "output_cost_per_token": 5e-6,
        },
        "claude-opus-4-1": {
            "input_cost_per_token": 15e-6,
            "output_cost_per_token": 75e-6,
        },
        "claude-opus-4-7": {
            "input_cost_per_token": 5e-6,
            "output_cost_per_token": 25e-6,
        },
        # 一个无关模型,确保我们只挑 alias 表里的
        "gpt-4o": {
            "input_cost_per_token": 2.5e-6,
            "output_cost_per_token": 10e-6,
        },
    }


def _mock_urlopen(json_data: dict):
    """构造一个 urllib.request.urlopen 的 mock。"""
    body = json.dumps(json_data).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda self: self
    mock_resp.__exit__ = lambda *a, **kw: False
    cm = MagicMock()
    cm.__enter__ = lambda *a, **kw: mock_resp
    cm.__exit__ = lambda *a, **kw: False
    return cm


# ──────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────


class TestPricingLoaderParse(unittest.TestCase):
    """LiteLLM JSON parse + 单位转换"""

    def setUp(self):
        # 强制重置 module-level state(每个 test 独立)
        import agent.pricing_loader as pl
        pl._prices = {}
        pl._last_refresh_ts = 0
        pl._last_source = "init"

    def test_parse_converts_per_token_to_per_mtok(self):
        from agent.pricing_loader import _parse_litellm
        out = _parse_litellm(_fake_litellm_json())
        # claude-sonnet-4-20250514 应该映射到 claude-sonnet-4-5
        # input_cost_per_token = 3e-6 → in = 3.0 per MTok
        self.assertIn("claude-sonnet-4-20250514", out)
        self.assertAlmostEqual(out["claude-sonnet-4-20250514"]["in"], 3.0, places=4)
        self.assertAlmostEqual(out["claude-sonnet-4-20250514"]["out"], 15.0, places=4)

    def test_parse_includes_opus_47_at_5_per_mtok(self):
        from agent.pricing_loader import _parse_litellm
        out = _parse_litellm(_fake_litellm_json())
        # Opus 4.7 是 $5/$25(便宜版,L3 推荐用)
        self.assertIn("claude-opus-4-7", out)
        self.assertAlmostEqual(out["claude-opus-4-7"]["in"], 5.0, places=4)
        self.assertAlmostEqual(out["claude-opus-4-7"]["out"], 25.0, places=4)

    def test_parse_includes_opus_41_at_15_per_mtok(self):
        from agent.pricing_loader import _parse_litellm
        out = _parse_litellm(_fake_litellm_json())
        # Opus 4.1 是 $15/$75(老版,贵)
        self.assertIn("claude-opus-4-1", out)
        self.assertAlmostEqual(out["claude-opus-4-1"]["in"], 15.0, places=4)

    def test_parse_haiku_is_1_per_mtok_not_quarter(self):
        """R52 校准:Haiku 4.5 是 $1/$5,不是历史 yaml 错写的 $0.25。"""
        from agent.pricing_loader import _parse_litellm
        out = _parse_litellm(_fake_litellm_json())
        self.assertIn("claude-haiku-4-5-20251001", out)
        self.assertAlmostEqual(out["claude-haiku-4-5-20251001"]["in"], 1.0, places=4)
        self.assertAlmostEqual(out["claude-haiku-4-5-20251001"]["out"], 5.0, places=4)

    def test_parse_skips_non_alias_models(self):
        from agent.pricing_loader import _parse_litellm
        out = _parse_litellm(_fake_litellm_json())
        # gpt-4o 不在 alias 表 → 不应该出现
        self.assertNotIn("gpt-4o", out)

    def test_parse_handles_missing_fields(self):
        from agent.pricing_loader import _parse_litellm
        bad = {"anthropic/claude-sonnet-4-5": {"max_tokens": 8192}}  # 没 cost
        out = _parse_litellm(bad)
        self.assertEqual(out, {})


class TestModelIdNormalize(unittest.TestCase):
    """模型 ID 归一化:老格式 / 新格式 / 未知都正确处理"""

    def test_old_format_with_date_suffix(self):
        from agent.pricing_loader import _normalize
        self.assertEqual(
            _normalize("claude-sonnet-4-20250514"),
            "claude-sonnet-4-5",
        )

    def test_haiku_old_format(self):
        from agent.pricing_loader import _normalize
        self.assertEqual(
            _normalize("claude-haiku-4-5-20251001"),
            "claude-haiku-4-5-20251001",
        )

    def test_opus_aliases(self):
        from agent.pricing_loader import _normalize
        # Opus 4.6 / 4.7 是新且便宜 ($5/$25),L3 推荐用
        self.assertEqual(_normalize("claude-opus-4-6"), "claude-opus-4-6")
        self.assertEqual(_normalize("claude-opus-4-7"), "claude-opus-4-7")
        # Opus 4.1 是老贵版 ($15/$75)
        self.assertEqual(_normalize("claude-opus-4-1"), "claude-opus-4-1")

    def test_unknown_model_gets_anthropic_prefix(self):
        from agent.pricing_loader import _normalize
        # 不在 alias 表 + 没日期后缀 → 加 anthropic/ 前缀(可能能查到)
        self.assertEqual(
            _normalize("claude-future-5"),
            "anthropic/claude-future-5",
        )

    def test_empty_returns_empty(self):
        from agent.pricing_loader import _normalize
        self.assertEqual(_normalize(""), "")


class TestRefreshAndFallback(unittest.TestCase):
    """LiteLLM 拉成功 / 失败 / cache file fallback"""

    def setUp(self):
        import agent.pricing_loader as pl
        pl._prices = {}
        pl._last_refresh_ts = 0
        pl._last_source = "init"
        # 重定向 cache 文件到临时位置
        self._tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False)
        self._tmp.close()
        self._original_cache = pl.CACHE_FILE
        pl.CACHE_FILE = Path(self._tmp.name)
        # 删除临时文件,让 cache 状态清空开始
        os.unlink(self._tmp.name)

    def tearDown(self):
        import agent.pricing_loader as pl
        pl.CACHE_FILE = self._original_cache
        # 清理我们写的 cache
        try:
            if Path(self._tmp.name).exists():
                os.unlink(self._tmp.name)
        except Exception:
            pass

    def test_refresh_pulls_from_litellm_and_writes_cache(self):
        import agent.pricing_loader as pl
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_urlopen(_fake_litellm_json())
            ok = pl.refresh_pricing(force=True)
            self.assertTrue(ok)
            self.assertEqual(pl._last_source, "litellm")
            self.assertGreater(len(pl._prices), 0)
            # cache 文件应该存在
            self.assertTrue(pl.CACHE_FILE.exists())
            data = json.loads(pl.CACHE_FILE.read_text())
            self.assertIn("prices", data)
            self.assertIn("claude-sonnet-4-20250514", data["prices"])

    def test_refresh_failure_keeps_old_values(self):
        import agent.pricing_loader as pl
        # 先种入旧值
        pl._prices = {"claude-sonnet-4-6": {"in": 99.0, "out": 99.0}}
        pl._last_source = "yaml"
        # 让 LiteLLM 拉失败
        with patch("urllib.request.urlopen", side_effect=Exception("network down")):
            ok = pl.refresh_pricing(force=True)
            self.assertFalse(ok)
            # 旧值保留
            self.assertEqual(pl._prices["claude-sonnet-4-6"]["in"], 99.0)


class TestGetPriceUnknownReturnsNone(unittest.TestCase):
    """未知模型必须返 None — 不"瞎算"。"""

    def setUp(self):
        import agent.pricing_loader as pl
        pl._prices = {
            "claude-sonnet-4-6": {"in": 3.0, "out": 15.0},
        }
        pl._last_refresh_ts = 999  # 已初始化标记

    def test_known_model_returns_price(self):
        from agent.pricing_loader import get_price
        p = get_price("claude-sonnet-4-6")
        self.assertIsNotNone(p)
        self.assertEqual(p["in"], 3.0)

    def test_unknown_model_returns_none(self):
        from agent.pricing_loader import get_price
        p = get_price("claude-mystery-9000")
        self.assertIsNone(p)

    def test_empty_model_returns_none(self):
        from agent.pricing_loader import get_price
        p = get_price("")
        self.assertIsNone(p)


class TestCalcCostUnknownModelRefuses(unittest.TestCase):
    """credit_service.calc_cost — 未知模型抛 UnknownModelError(R52)"""

    def setUp(self):
        # 强制 pricing_loader 状态:只有 sonnet-4-6
        import agent.pricing_loader as pl
        pl._prices = {
            "claude-sonnet-4-6": {"in": 3.0, "out": 15.0},
        }
        pl._last_refresh_ts = 999

    def test_known_model_calc_cost_works(self):
        # 必须 reset 才不被 init() 时的状态干扰
        import agent.pricing_loader as pl
        pl._prices = {"claude-sonnet-4-6": {"in": 3.0, "out": 15.0}}
        pl._last_refresh_ts = 999
        from agent.credit_service import calc_cost
        # 1000 in + 500 out @ sonnet
        cost = calc_cost("claude-sonnet-4-6", 1000, 500)
        # raw = 1000*3 + 500*15 = 3000 + 7500 = 10500 / 1M * 1.0 = 0.0105
        self.assertAlmostEqual(float(cost), 0.0105, places=5)

    def test_unknown_model_raises(self):
        # pricing_loader 没有 + yaml fallback 也没有这个模型 → 抛
        import agent.pricing_loader as pl
        pl._prices = {"claude-sonnet-4-6": {"in": 3.0, "out": 15.0}}
        pl._last_refresh_ts = 999
        # 暂时清空 yaml fallback(LLM_PRICES 也不能有)
        from agent import credit_service
        original = credit_service.LLM_PRICES
        credit_service.LLM_PRICES = {"claude-sonnet-4-6": {"in": 3.0, "out": 15.0}}
        try:
            from agent.credit_service import calc_cost, UnknownModelError
            with self.assertRaises(UnknownModelError):
                calc_cost("claude-totally-fake-9000", 1000, 500)
        finally:
            credit_service.LLM_PRICES = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
