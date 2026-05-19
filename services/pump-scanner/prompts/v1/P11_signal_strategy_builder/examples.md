# P11 Few-shot

## Example 1

**User:** chain=SOL, trigger=smart_money, amount_usd=100, stop_loss_pct=-15, take_profit_pct=30, cooldown_min=15, name="SOL 聪明钱跟单"

**Assistant:** {"name":"SOL 聪明钱跟单","description":"SOL 链 elite≥75 聪明钱信号触发,$100 买入,-15% 止损 +30% 止盈","conditions":{"rules":[{"data_source":"smart_money","field":"elite_score","op":">=","value":75},{"data_source":"smart_money","field":"chain","op":"=","value":"SOL"}]},"actions":[{"type":"paper_buy","params":{"amount_usd":100}}],"filters":{"chains":["SOL"],"min_liquidity_usd":30000,"max_holder_top10_pct":0.6},"risk_params":{"stop_loss_pct":-15,"take_profit_pct":30,"max_position_usd":100,"trailing_stop_atr":null},"cooldown_minutes":15,"mode":"paper"}

## Example 2 (missing inputs)

**User:** chain=ETH, name="未命名"

**Assistant:** {"error":"missing","missing_fields":["trigger","amount_usd","stop_loss_pct","take_profit_pct","cooldown_min"]}

## Example 3 (multi-chain hot coins, persona=pro)

**User:** chain=SOL,BSC,Base, trigger=hot_coin, amount_usd=200, stop_loss_pct=-12, take_profit_pct=25, cooldown_min=10, persona=pro, name="多链热币榜单 v2"

**Assistant:** {"name":"多链热币榜单 v2","description":"SOL/BSC/Base 三链热币 score≥80 触发,$200 买入,-12% 止损 +25% 止盈,10min 冷却","conditions":{"rules":[{"data_source":"hot_coins","field":"score","op":">=","value":80}]},"actions":[{"type":"paper_buy","params":{"amount_usd":200}}],"filters":{"chains":["SOL","BSC","Base"],"min_liquidity_usd":50000,"max_holder_top10_pct":0.55},"risk_params":{"stop_loss_pct":-12,"take_profit_pct":25,"max_position_usd":200,"trailing_stop_atr":null},"cooldown_minutes":10,"mode":"paper"}

## Example 4 (KOL trigger)

**User:** chain=ETH, trigger=kol_signal, amount_usd=80, stop_loss_pct=-12, take_profit_pct=20, cooldown_min=20, name="ETH KOL 跟单"

**Assistant:** {"name":"ETH KOL 跟单","description":"ETH 链 KOL sentiment≥0.7 触发,$80 买入,-12% 止损 +20% 止盈,20min 冷却","conditions":{"rules":[{"data_source":"kol_sentiment","field":"avg_sent","op":">=","value":0.7},{"data_source":"kol_sentiment","field":"chain","op":"=","value":"ETH"}]},"actions":[{"type":"paper_buy","params":{"amount_usd":80}}],"filters":{"chains":["ETH"],"min_liquidity_usd":50000,"max_holder_top10_pct":0.55},"risk_params":{"stop_loss_pct":-12,"take_profit_pct":20,"max_position_usd":80,"trailing_stop_atr":null},"cooldown_minutes":20,"mode":"paper"}

## Example 5 (technical RSI + MACD)

**User:** chain=BSC, trigger=technical, indicators=[rsi<30, macd_cross=golden], amount_usd=120, stop_loss_pct=-10, take_profit_pct=22, cooldown_min=30, name="BSC 超卖反弹"

**Assistant:** {"name":"BSC 超卖反弹","description":"BSC 链 RSI<30 + MACD 金叉触发,$120 买入,-10% 止损 +22% 止盈,30min 冷却","conditions":{"rules":[{"data_source":"technical","field":"rsi","op":"<","value":30},{"data_source":"technical","field":"macd_cross","op":"=","value":"golden"}]},"actions":[{"type":"paper_buy","params":{"amount_usd":120}}],"filters":{"chains":["BSC"],"min_liquidity_usd":40000,"max_holder_top10_pct":0.6},"risk_params":{"stop_loss_pct":-10,"take_profit_pct":22,"max_position_usd":120,"trailing_stop_atr":null},"cooldown_minutes":30,"mode":"paper"}
