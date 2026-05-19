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

## Example 4 (single mega-KOL, low mentions)

**User:** token=DOGE kol_signals=[{"kol":"@elonmusk","sent":0.95}] mentions_24h=80 growth_pct=10 discord_heat=low

**Assistant:** {"direction":"bullish","confidence":0.55,"consistency":"single_source","hype_warning":false,"points":["仅 1 KOL 但权重极高","提及量基数小,可能尚未扩散","Discord 未形成共振","需确认是否单源信号"]}

## Example 5 (bearish consensus, declining mentions)

**User:** token=SHIB kol_signals=[{"kol":"@a","sent":-0.7},{"kol":"@b","sent":-0.65},{"kol":"@c","sent":-0.55}] mentions_24h=2200 growth_pct=-45 discord_heat=low

**Assistant:** {"direction":"bearish","confidence":0.68,"consistency":"high","hype_warning":false,"points":["3 KOL 同方向看空 sent<-0.5","提及量持续下滑 -45%","Discord 转冷","卖压共识形成"]}
