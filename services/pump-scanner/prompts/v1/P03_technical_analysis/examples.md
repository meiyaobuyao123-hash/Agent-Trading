# P03 Few-shot

## Example 1 (oversold reversal)

**User:** chain=SOL token=TRUMP regime=NORMAL indicators={"rsi":32,"macd":-0.05,"ma20":0.95,"ma50":1.05,"bb_lower":0.92,"atr":0.03} last_price=0.94

**Assistant:** {"direction":"neutral","confidence":0.45,"key_level":{"support":0.92,"resistance":1.05},"points":["RSI 32 进入超卖","MACD 仍负但收窄","触及 BB 下轨可能反弹","MA20<MA50 趋势仍弱"]}

## Example 2 (trend up)

**User:** chain=ETH token=PEPE regime=TRENDING_UP indicators={"rsi":58,"macd":0.012,"ma20":0.0008,"ma50":0.0007,"bb_upper":0.00085,"atr":0.00003} last_price=0.00082

**Assistant:** {"direction":"bullish","confidence":0.62,"key_level":{"support":0.00078,"resistance":0.00085},"points":["MACD 正且扩大","MA20 上穿 MA50 形成金叉","RSI 58 健康上行","逼近 BB 上轨需观察"]}

## Example 3 (data insufficient)

**User:** chain=BSC token=NEW indicators={"rsi":null,"macd":null,"ma20":null} last_price=0.001

**Assistant:** {"direction":"neutral","confidence":0.2,"key_level":{"support":0,"resistance":0},"points":["数据不足,K 线少于 14 根","技术分析暂不可靠"]}

## Example 4 (overbought + death cross — bearish)

**User:** chain=BSC token=CAKE regime=NORMAL indicators={"rsi":78,"macd":-0.05,"ma20":2.10,"ma50":2.12,"ma_cross":"death_just_now","atr":0.08} last_price=2.08

**Assistant:** {"direction":"bearish","confidence":0.7,"key_level":{"support":2.00,"resistance":2.15},"points":["RSI 78 极度超买","MA20 刚跌破 MA50 形成死叉","MACD 转负","可能回测 MA50 支撑"]}

## Example 5 (CRISIS regime forces conservative)

**User:** chain=ETH token=WETH regime=CRISIS indicators={"rsi":40,"macd":-0.02,"ma20":2400,"ma50":2500,"atr":120} last_price=2380

**Assistant:** {"direction":"neutral","confidence":0.3,"key_level":{"support":2300,"resistance":2500},"points":["CRISIS 期间技术信号置信度低","RSI 40 偏弱但未超卖","MA20<MA50 空头排列","建议观望不参与"]}
