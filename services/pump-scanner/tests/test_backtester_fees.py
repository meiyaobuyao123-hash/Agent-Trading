"""R60 — 回测手续费扣除单测

验证:
1. backtest_strategy 接 risk_params.max_slippage_pct
2. 默认用 DEX_FEE_PCT_SINGLE[chain]
3. net_return < gross_return(扣完手续费更低)
4. fee_assumptions 字段格式正确
5. win 判定切到 net 后,某些 case 从 win 翻 lose
6. max_drawdown_pct=None + status='collecting'(Phase B 未上线)
"""

from unittest.mock import patch, AsyncMock
import pytest
import asyncio


@pytest.mark.asyncio
async def test_fee_default_solana():
    """默认 chain=solana → fee_single_pct=1.0,round_trip=2.0"""
    from agent.backtester import backtest_strategy

    spec = {"name": "test", "conditions": {"hot_coins": {"score_min": 80}}}

    # Mock DB + evaluator + token_performance
    with patch("agent.backtester.get_db") as mock_db, \
         patch("agent.backtester._evaluator") as mock_eval, \
         patch("agent.backtester._get_token_performance",
               new_callable=AsyncMock) as mock_perf, \
         patch("agent.backtester._load_hot_coin_history",
               new_callable=AsyncMock) as mock_hist:

        from agent.schemas import DataEvent

        mock_hist.return_value = [
            DataEvent(
                source="hot_coins",
                data={"score": 90},
                timestamp="2026-05-14T00:00:00Z",
                chain="solana",
                token_address="addr1",
                token_name="TOKEN1",
            )
        ]
        mock_eval.evaluate.return_value = [{"strategy_id": "backtest"}]
        # 触发后涨 10%(D3 涨 10%,够 hot D3 阈值 20% 吗?不够 → loss)
        # gross D3 = 10%, net D3 = (1.10)*(0.98)-1 = 7.8% < 20% → loss
        mock_perf.return_value = {
            "best_pct": 10,
            "daily_highs": {"D3": {"pct": 10}},
            "source": "hot_live",
        }
        mock_db.return_value = None

        result = await backtest_strategy(spec, days=7)

    # 1. fee 假设是 solana 默认
    assert result["fee_assumptions"]["fee_single_pct"] == 1.0
    assert result["fee_assumptions"]["fee_round_trip_pct"] == 2.0
    assert result["fee_assumptions"]["source"] == "default"
    assert result["fee_assumptions"]["chain"] == "solana"

    # 2. max_drawdown 未启用
    assert result["max_drawdown_pct"] is None
    assert result["max_drawdown_status"] == "collecting"

    # 3. trigger_count=1
    assert result["trigger_count"] == 1


@pytest.mark.asyncio
async def test_user_slippage_override():
    """用户 risk_params.max_slippage_pct=0.005 (0.5%) → 覆盖默认 1%"""
    from agent.backtester import backtest_strategy
    from agent.schemas import DataEvent

    spec = {"name": "test", "conditions": {"hot_coins": {"score_min": 80}}}
    user_risk = {"max_slippage_pct": 0.005}  # 0.5%

    with patch("agent.backtester.get_db"), \
         patch("agent.backtester._evaluator") as mock_eval, \
         patch("agent.backtester._get_token_performance",
               new_callable=AsyncMock) as mock_perf, \
         patch("agent.backtester._load_hot_coin_history",
               new_callable=AsyncMock) as mock_hist:

        mock_hist.return_value = [
            DataEvent(
                source="hot_coins", data={}, timestamp="",
                chain="eth", token_address="0xabc", token_name="T",
            )
        ]
        mock_eval.evaluate.return_value = [{"strategy_id": "backtest"}]
        mock_perf.return_value = {
            "best_pct": 5, "daily_highs": {"D3": {"pct": 5}},
            "source": "hot_live",
        }

        result = await backtest_strategy(spec, days=7, risk_params=user_risk)

    assert result["fee_assumptions"]["source"] == "user"
    assert result["fee_assumptions"]["fee_single_pct"] == 0.5
    assert result["fee_assumptions"]["fee_round_trip_pct"] == 1.0


@pytest.mark.asyncio
async def test_net_lt_gross():
    """net 收益 < gross 收益(扣完手续费更低)"""
    from agent.backtester import backtest_strategy
    from agent.schemas import DataEvent

    spec = {"name": "test", "conditions": {"hot_coins": {}}}

    with patch("agent.backtester.get_db"), \
         patch("agent.backtester._evaluator") as mock_eval, \
         patch("agent.backtester._get_token_performance",
               new_callable=AsyncMock) as mock_perf, \
         patch("agent.backtester._load_hot_coin_history",
               new_callable=AsyncMock) as mock_hist:

        mock_hist.return_value = [
            DataEvent(source="hot_coins", data={}, timestamp="",
                      chain="solana", token_address="a", token_name="A")
        ]
        mock_eval.evaluate.return_value = [{"strategy_id": "backtest"}]
        # 触发后涨 50%
        mock_perf.return_value = {
            "best_pct": 50,
            "daily_highs": {"D3": {"pct": 50}},
            "source": "hot_live",
        }

        result = await backtest_strategy(spec, days=7)

    # gross 50%, net = (1.50)*(0.98)-1 = 0.47 = 47%
    assert result["gross_return_pct"] > result["avg_return_pct"]
    assert abs(result["gross_return_pct"] - 50.0) < 0.01
    assert abs(result["avg_return_pct"] - 47.0) < 0.1


@pytest.mark.asyncio
async def test_win_flip_after_fee():
    """临界 case:gross D3 涨 22%(hot 阈值 20% 算 win),扣 2% 后净 19.56% → lose"""
    from agent.backtester import backtest_strategy
    from agent.schemas import DataEvent

    spec = {"name": "test", "conditions": {"hot_coins": {}}}

    with patch("agent.backtester.get_db"), \
         patch("agent.backtester._evaluator") as mock_eval, \
         patch("agent.backtester._get_token_performance",
               new_callable=AsyncMock) as mock_perf, \
         patch("agent.backtester._load_hot_coin_history",
               new_callable=AsyncMock) as mock_hist:

        mock_hist.return_value = [
            DataEvent(source="hot_coins", data={}, timestamp="",
                      chain="solana", token_address="a", token_name="A")
        ]
        mock_eval.evaluate.return_value = [{"strategy_id": "backtest"}]
        # gross D3 = 22% → 在 hot 20% 阈值之上 = gross win
        # net D3 = (1.22)*(0.98)-1 = 0.1956 = 19.56% < 20% → net lose
        mock_perf.return_value = {
            "best_pct": 22,
            "daily_highs": {"D3": {"pct": 22}},
            "source": "hot_live",
        }

        result = await backtest_strategy(spec, days=7)

    assert result["gross_win_rate"] == 1.0       # gross win
    assert result["simulated_win_rate"] == 0.0   # net lose(扣完手续费跌破阈值)
