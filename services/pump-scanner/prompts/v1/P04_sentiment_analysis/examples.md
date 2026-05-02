# P04 Few-shot

## Example 1 (KOL consensus bullish)

**User:** token=TRUMP kol_signals=[{"kol":"@a","sent":0.85},{"kol":"@b","sent":0.78},{"kol":"@c","sent":0.82}] mentions_24h=4200 growth_pct=120 discord_heat=high

**Assistant:** {"direction":"bullish","confidence":0.72,"consistency":"high","hype_warning":false,"points":["3 KOL 同方向看涨 sent>0.75","提及量 +120% 24h","Discord 热度 high","信号一致性强"]}

## Example 2 (hype warning)

**User:** token=NEW kol_signals=[] mentions_24h=8000 growth_pct=350 discord_heat=med

**Assistant:** {"direction":"neutral","confidence":0.3,"consistency":"low","hype_warning":true,"points":["提及量爆涨 +350% 但 0 KOL 跟","典型虚热","建议警惕 pump 风险"]}

## Example 3 (mixed signals)

**User:** token=PEPE kol_signals=[{"kol":"@x","sent":0.6},{"kol":"@y","sent":-0.4}] mentions_24h=1500 growth_pct=20 discord_heat=low

**Assistant:** {"direction":"neutral","confidence":0.35,"consistency":"mixed","hype_warning":false,"points":["KOL 看法分歧","提及量平稳","Discord 热度 low","暂无明确信号"]}
