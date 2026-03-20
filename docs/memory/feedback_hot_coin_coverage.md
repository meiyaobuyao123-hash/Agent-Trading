---
name: hot_coin_coverage_decision
description: 热币全量扫描 vs 排行榜方案的评估结论 — 排行榜方案已够用，优先优化打分
type: project
---

热币发现不需要全量链上扫描，排行榜方案（OKX toplist + GeckoTerminal trending）已足够。

**Why:** 真正会暴涨的币必有高成交量+涨幅，必然进入 toplist 排行榜。全量扫描 vs 排行榜在推荐 Top20 上效果差距 ≤5%，但成本 $39+/月 vs 免费。

**How to apply:**
- 不要花钱买 Birdeye/DEXTools 做全量扫描
- 提升推荐质量应优先优化打分算法（M/Q/P 权重、退出时机），而非增加数据源
- 当前覆盖：OKX toplist ~100/链 + GeckoTerminal ~200/链 = ~300 独立候选/链
- 免费方案天花板：OKX + GeckoTerminal + DexScreener，不可能更多了
