# P06 Few-shot

## Example 1 (decent stats)

**User:** spec_name="SOL 聪明钱跟单" chain=SOL trigger=smart_money backtest={"trade_count_30d":18,"win_rate":0.61,"avg_pnl_pct":3.2,"max_dd":-12,"sharpe":1.4,"warnings":[]} persona=intermediate

**Assistant:** 过去 30d 模拟:18 笔触发,胜率 61%,平均盈亏 +3.2%,最大回撤 -12%,Sharpe 1.4。样本可观,要保存为 paper 起步吗?

STAGE_TRANSITION:confirming

## Example 2 (low sample)

**User:** spec_name="ETH 大盘信号" chain=ETH trigger=btc_signal backtest={"trade_count_30d":2,"win_rate":1.0,"avg_pnl_pct":4,"max_dd":-3,"sharpe":2,"warnings":["sample_size_low"]} persona=newbie

**Assistant:** 过去 30d 只触发 2 笔,样本太少不可靠 — 数字别当真。建议放宽条件试试,或先保存为 paper 慢慢收集数据。

STAGE_TRANSITION:confirming

## Example 3 (zero trades)

**User:** spec_name="超严格策略" chain=BSC trigger=hot_coin backtest={"trade_count_30d":0,"win_rate":null,"avg_pnl_pct":null,"max_dd":null,"sharpe":null,"warnings":["zero_triggers"]} persona=intermediate

**Assistant:** 过去 30d 0 笔触发,条件太严格了。回去调一下阈值再试?

STAGE_TRANSITION:refining

## Example 4 (high return but huge drawdown)

**User:** spec_name="ETH MEME 激进" chain=ETH trigger=hot_coin backtest={"trade_count_30d":24,"win_rate":0.42,"avg_pnl_pct":8.5,"max_dd":-45,"sharpe":0.8,"warnings":["high_drawdown"]} persona=intermediate

**Assistant:** 过去 30d 模拟:24 笔,胜率 42%,但平均盈亏 +8.5%(高 R)。问题是最大回撤 -45% 太深 — 实盘可能扛不住。建议把止损收紧或先 paper 跑一段时间观察。

STAGE_TRANSITION:refining

## Example 5 (rare trigger high sharpe)

**User:** spec_name="月度 BTC 反转" chain=BTC trigger=technical backtest={"trade_count_30d":3,"win_rate":1.0,"avg_pnl_pct":12,"max_dd":-4,"sharpe":3.2,"warnings":["sample_size_low"]} persona=pro

**Assistant:** 30d 仅 3 笔但 3 胜,Sharpe 3.2 数据漂亮 — 但样本极少(月级触发)。建议保存为 paper 长期观察 6 个月,够 18 笔再升级。

STAGE_TRANSITION:confirming
