# P10 Few-shot examples

## Example 1 (clean approve)

**User:** thesis: {direction: long, conviction: 0.78, evidence:[a,b,c,d]}; portfolio_pct_in_chain: 12; recent_trades_24h: 3; regime: BREAKOUT; liquidity: 250000; top10: 0.45

**Assistant:** {"verdict":"approve","downgrade_to":null,"reason":"软风险全部 OK","soft_flags":[]}

## Example 2 (one flag + low conviction → downgrade)

**User:** thesis: {direction: long, conviction: 0.55, evidence:[a,b]}; portfolio_pct_in_chain: 15; recent_trades_24h: 2; regime: BREAKOUT; liquidity: 25000; top10: 0.50

**Assistant:** {"verdict":"downgrade","downgrade_to":"notify","reason":"low_liquidity 25k<30k 且 conviction 0.55 不到阈值,降级 notify 不直接 auto","soft_flags":["low_liquidity"]}

## Example 3 (two flags → veto)

**User:** thesis: {direction: long, conviction: 0.72}; portfolio_pct_in_chain: 40; recent_trades_24h: 9; regime: BREAKOUT; liquidity: 150000

**Assistant:** {"verdict":"veto","downgrade_to":null,"reason":"集中度 40% + 24h 9 笔过度交易,叠加风险拒绝执行","soft_flags":["concentration_high","recent_overtrade"]}
