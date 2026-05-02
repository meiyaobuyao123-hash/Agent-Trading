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
