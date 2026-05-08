# P15 Few-shot

## Example 1 (bull strong)

**User:** token=TRUMP chain=SOL thesis_draft={"direction":"bullish","conviction":0.6} debate=[{"role":"bull","strength":0.75},{"role":"bear","strength":0.35}] regime=NORMAL

**Assistant:** {"role":"facilitator","conclusion":"bull_strong","conviction_adjust":0.05,"final_conviction":0.65,"final_direction":"bullish","final_action":"proceed","summary":"Bull 0.75 > Bear 0.35,论据强度差 0.4 → 调升 conviction +0.05"}

## Example 2 (bear strong reverse)

**User:** token=NEW chain=BSC thesis_draft={"direction":"bullish","conviction":0.55} debate=[{"role":"bull","strength":0.35},{"role":"bear","strength":0.8}] regime=NORMAL

**Assistant:** {"role":"facilitator","conclusion":"bear_strong","conviction_adjust":-0.15,"final_conviction":0.4,"final_direction":"neutral","final_action":"hold","summary":"Bear 0.8 远强于 Bull 0.35,反转 direction → neutral + final_conviction<0.5 强制 hold"}

## Example 3 (CRISIS cap + draw)

**User:** token=PEPE chain=ETH thesis_draft={"direction":"bullish","conviction":0.7} debate=[{"role":"bull","strength":0.65},{"role":"bear","strength":0.55}] regime=CRISIS

**Assistant:** {"role":"facilitator","conclusion":"draw","conviction_adjust":-0.4,"final_conviction":0.3,"final_direction":"hold","final_action":"hold","summary":"Bull/Bear 论据接近,但 CRISIS regime 强制 conviction ≤ 0.3 → hold"}

## Example 4 (close draw — 微调下降)

**User:** token=BONK chain=SOL thesis_draft={"direction":"bullish","conviction":0.6} debate=[{"role":"bull","strength":0.55},{"role":"bear","strength":0.50}] regime=NORMAL

**Assistant:** {"role":"facilitator","conclusion":"draw","conviction_adjust":-0.09,"final_conviction":0.51,"final_direction":"bullish","final_action":"proceed","summary":"双方差距 0.05 < 0.15 平局,conviction × 0.85 微降但仍 ≥ 0.5 可执行"}

## Example 5 (final_conviction 红线 hold)

**User:** token=RISKY chain=BSC thesis_draft={"direction":"bullish","conviction":0.55} debate=[{"role":"bull","strength":0.40},{"role":"bear","strength":0.65}] regime=NORMAL

**Assistant:** {"role":"facilitator","conclusion":"bear_strong","conviction_adjust":-0.10,"final_conviction":0.45,"final_direction":"neutral","final_action":"hold","summary":"Bear 略强,调整后 conviction 0.45 < 0.5 红线 → hold"}
