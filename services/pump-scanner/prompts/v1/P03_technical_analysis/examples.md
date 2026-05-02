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
