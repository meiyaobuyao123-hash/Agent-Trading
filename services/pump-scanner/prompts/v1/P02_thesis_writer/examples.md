# P02 Few-shot examples

## Example 1 (high conviction long)

**User:** technical: RSI 35 oversold + MACD bottom divergence; sentiment: KOL T1 sentiment 0.8; onchain: 3 elite smart money 净流入 24h $200K; regime: BREAKOUT; token: SOL/TRUMP

**Assistant:** {"direction":"long","conviction":0.78,"summary_30w":"BREAKOUT + 聪明钱跟入,中短线机会","entry_zone":{"low":0.092,"high":0.098},"stop_loss":0.082,"target":0.130,"risks":["BREAKOUT 失败回 RANGING 的风险","流动性 < $80K 滑点风险"],"evidence":[{"layer":"technical","text":"RSI 35 + MACD 底背离","weight":0.8},{"layer":"sentiment","text":"KOL T1 sent 0.8","weight":0.7},{"layer":"onchain","text":"3 elite +$200K","weight":0.85}],"level":"L3"}

## Example 2 (low conviction → neutral)

**User:** technical: 横盘 / RSI 50; sentiment: 中性; onchain: 净流出 $30K; regime: RANGING; token: ETH/PEPE

**Assistant:** {"direction":"neutral","conviction":0.35,"summary_30w":"低置信度,信号矛盾,建议观望","entry_zone":null,"stop_loss":null,"target":null,"risks":["信号矛盾,任一方向胜率 < 50%","RANGING regime 多次假突破"],"evidence":[{"layer":"technical","text":"RSI 50 横盘","weight":0.5},{"layer":"onchain","text":"净流出 $30K","weight":0.5}],"level":"L2"}

## Example 3 (CRISIS forced low)

**User:** technical: 强跌破支撑; sentiment: 极度恐慌; onchain: 大额砸盘; regime: CRISIS; token: BTC

**Assistant:** {"direction":"neutral","conviction":0.20,"summary_30w":"CRISIS 期间强制保守,等修复","entry_zone":null,"stop_loss":null,"target":null,"risks":["宏观风险:CRISIS regime","二次破位向下风险","流动性枯竭"],"evidence":[{"layer":"technical","text":"破支撑","weight":0.9},{"layer":"sentiment","text":"恐慌指数极低","weight":0.8},{"layer":"onchain","text":"大额砸盘","weight":0.85}],"level":"L3"}
