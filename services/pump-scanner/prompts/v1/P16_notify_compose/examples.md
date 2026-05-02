# P16 Few-shot

## Example 1 (high conviction normal)

**User:** token=TRUMP chain=SOL thesis={"direction":"bullish","conviction":0.72,"summary":"3 路一致看涨"} trigger="smart_money 净流 +$80k" amount_usd=100 regime=NORMAL persona=intermediate

**Assistant:** {"title":"TRUMP 触发:聪明钱跟单","body":"3 路一致看涨,信心 72%。Smart money 净流 +$80k 触发,建议买入 $100。","urgency":"med","category":"strategy_triggered"}

## Example 2 (low conviction warning)

**User:** token=NEW chain=BSC thesis={"direction":"hold","conviction":0.42,"summary":"分歧大"} trigger="hot_coin score=78" amount_usd=50 regime=NORMAL persona=newbie

**Assistant:** {"title":"NEW 触发(低置信度)","body":"信心仅 42%,信号有分歧。仅供参考,不建议跟。$50 约一顿外卖钱,即便买入也请控制仓位。","urgency":"low","category":"strategy_triggered"}

## Example 3 (CRISIS)

**User:** token=PEPE chain=ETH thesis={"direction":"hold","conviction":0.3,"summary":"宏观转弱"} trigger="kol_signal" amount_usd=0 regime=CRISIS persona=pro

**Assistant:** {"title":"PEPE signal blocked (CRISIS)","body":"PEPE / kol bullish but regime=CRISIS, conviction capped 0.3 → hold. 宏观风险高,建议暂停 auto。","urgency":"high","category":"strategy_triggered"}
