# P18 Few-shot

## Example 1 (pro → newbie)

**User:** original_text="BC=30/RSI=35/oversold/sent=0.8/risks:[liq<30k, top10>0.6]"; target_persona=newbie

**Assistant:** Bonding curve 进度 30%(像装到三分之一的箱子),RSI 35 处于超卖区(已经跌得有点深可能要反弹),情绪指数 0.8(社群比较看好)。但要注意两个风险:流动性不到 $30K(进出可能滑点)、前 10 持有人占比超过 60%(集中度高,大户砸盘风险)。

## Example 2 (intermediate → pro)

**User:** original_text="今日 4 笔交易,3 胜 1 平,胜率 75%,EV +2.1%。SOL 链聪明钱跟单 3 笔全胜。"; target_persona=pro

**Assistant:** 今日 4 trades / 3W 1D / WR 75% / EV +2.1% / SOL 聪明钱 3W

## Example 3 (pro → intermediate)

**User:** original_text="thesis: bullish/conviction 0.62/risks=[liquidity_thin, top10_concentration]/SL -15% TP +25%/position 100 USD"; target_persona=intermediate

**Assistant:** 看涨方向,信心度 62%。风险:流动性偏薄、前 10 持有人集中。建议止损 -15%、止盈 +25%,仓位 $100。

## Example 4 (newbie → intermediate)

**User:** original_text="这个币突然涨了好多,我们要不要买?"; target_persona=intermediate

**Assistant:** 这个 token 短期涨幅明显,但需先看:1) 是否有真信号支撑(KOL/链上数据);2) 还是 FOMO 散户进场。建议查看流动性与 top10 集中度再判断。

## Example 5 (pro → newbie 复杂术语)

**User:** original_text="Slippage exceed 5% on Jupiter v6 / pool TVL drop 40% in 1h / oracle drift 0.28% / HR12 armed"; target_persona=newbie

**Assistant:** Jupiter 上你这笔交易"差价"太大(超 5%,简单说就是按这个价买不到这么多)。这个币的"水池"(交易池)1 小时内缩水 40%(很多人卖,池子变小)。价格指标偏离 0.28%(数据可能不准)。系统已经"拉了警报"(HR12),建议暂时别动。
