# P14 Few-shot

## Example 1 (strong bear)

**User:** token=NEW chain=BSC thesis_draft={"direction":"bullish","conviction":0.55} bull_arguments=["KOL 提及量上升","技术指标 RSI 35 超卖反弹"] evidence={"tech":"RSI 35","sent":"hype_warning=true","onchain":"top10=72% liq=$8k"} regime=NORMAL round=1

**Assistant:** {"role":"bear","round":1,"arguments":["onchain top10=72% 高度集中 + 流动性仅 $8k → rug 风险高","sent.hype_warning=true 表明无 KOL 跟,只有量爆涨","RSI 超卖在小盘币中常常是单边下跌而非反弹"],"strength":0.8,"key_evidence_used":["onchain","sentiment","technical"],"concedes":"Bull 提及量数据是对的,但解读方向错了"}

## Example 2 (weak bear concedes)

**User:** token=TRUMP chain=SOL thesis_draft={"direction":"bullish","conviction":0.7} bull_arguments=["3 KOL 同方向","sm 净流 +$80k","MA 金叉"] evidence={"tech":"MACD 上穿","sent":"3 KOL sent>0.75","onchain":"top10=45% liq=$120k"} regime=TRENDING_UP round=1

**Assistant:** {"role":"bear","round":1,"arguments":["TRENDING_UP 末期容易追高被套","KOL 推单背后可能有未披露利益(无法证实)"],"strength":0.35,"key_evidence_used":["sentiment"],"concedes":"Bull 的 3 路一致 + onchain 数据确实较强"}

## Example 3 (round 2 escalate)

**User:** token=PEPE chain=ETH thesis_draft={"direction":"bullish","conviction":0.55} bull_arguments=["突破前高+regime trending up"] evidence={"tech":"BB 上轨","sent":"hype 持续 7d","onchain":"top10=48%"} regime=TRENDING_UP round=2

**Assistant:** {"role":"bear","round":2,"arguments":["BB 上轨触及通常意味着短期 mean reversion","hype 持续 7d 已经体现在价格里,继续追风险高"],"strength":0.55,"key_evidence_used":["technical","sentiment"],"concedes":"top10=48% 健康分散是事实"}

## Example 4 (low liquidity rug warning)

**User:** token=SCAM chain=BSC thesis_draft={"direction":"bullish","conviction":0.5} bull_arguments=["新币早期狙击"] evidence={"tech":"K 线少于 6h","sent":"无 KOL","onchain":"top10=88% liq=$3k holder=12"} regime=NORMAL round=1

**Assistant:** {"role":"bear","round":1,"arguments":["liquidity 仅 $3k 极易被砸穿","top10=88% 单一钱包控盘明显","holder=12 缺乏真实社区基础"],"strength":0.85,"key_evidence_used":["onchain"],"concedes":"早期狙击思路本身没错,但这个 token 数据全黑"}

## Example 5 (CRISIS regime — escalate bearish)

**User:** token=WETH chain=ETH thesis_draft={"direction":"bullish","conviction":0.45} bull_arguments=["超卖反弹"] evidence={"tech":"RSI 28","sent":"恐慌","onchain":"sm 净流出"} regime=CRISIS round=1

**Assistant:** {"role":"bear","round":1,"arguments":["CRISIS regime 下超卖可继续超卖,接刀风险极大","smart money 净流出说明机构在退出"],"strength":0.75,"key_evidence_used":["onchain"],"concedes":"RSI 28 确实极端,但下跌中段也常见这个值"}
