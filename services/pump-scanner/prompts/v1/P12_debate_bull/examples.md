# P12 Few-shot

## Example 1 (strong bull)

**User:** token=TRUMP chain=SOL thesis_draft={"direction":"bullish","conviction":0.6} evidence={"tech":"MA20 上穿 MA50","sent":"3 KOL 同方向","onchain":"sm 净流 +$80k"} regime=NORMAL round=1

**Assistant:** {"role":"bull","round":1,"arguments":["3 KOL 同时间点看涨概率小于偶然","smart money 净流 + KOL 一致性 → 信号互证","MA 金叉是低频但可靠的趋势确认"],"strength":0.75,"key_evidence_used":["sentiment","onchain","technical"]}

## Example 2 (weak bull)

**User:** token=NEW chain=BSC thesis_draft={"direction":"neutral","conviction":0.4} evidence={"tech":"RSI 52 中性","sent":"提及量增长但无 KOL","onchain":"流动性 $15k 偏薄"} regime=RANGE round=1

**Assistant:** {"role":"bull","round":1,"arguments":["提及量上升至少代表关注度","RANGE 行情下小盘可能突然异动"],"strength":0.35,"key_evidence_used":["sentiment"]}

## Example 3 (round 2 reinforcement)

**User:** token=PEPE chain=ETH thesis_draft={"direction":"bullish","conviction":0.55} evidence={"tech":"突破前高","sent":"hype 持续","onchain":"top10=48% 健康"} regime=TRENDING_UP round=2

**Assistant:** {"role":"bull","round":2,"arguments":["TRENDING_UP regime 下突破前高更可信","top10 健康分散意味着上行空间更大"],"strength":0.7,"key_evidence_used":["technical","onchain"]}

## Example 4 (CRISIS regime — 仍要诚实低 strength)

**User:** token=BONK chain=SOL thesis_draft={"direction":"bullish","conviction":0.4} evidence={"tech":"超卖反弹信号","sent":"无 KOL","onchain":"smart money 小额买入"} regime=CRISIS round=1

**Assistant:** {"role":"bull","round":1,"arguments":["超卖区域反弹概率高于继续下杀","smart money 在 CRISIS 仍买入显示底部信号"],"strength":0.3,"key_evidence_used":["technical","onchain"]}

## Example 5 (data thin — 承认论据弱)

**User:** token=NEW chain=BSC thesis_draft={"direction":"neutral","conviction":0.5} evidence={"tech":"K 线少于 24h","sent":"无","onchain":"holder=80"} regime=NORMAL round=1

**Assistant:** {"role":"bull","round":1,"arguments":["holder 数 80 显示已有早期社区"],"strength":0.25,"key_evidence_used":["onchain"]}
