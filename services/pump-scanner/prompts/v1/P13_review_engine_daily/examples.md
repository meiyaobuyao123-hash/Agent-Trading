# P13 Few-shot

## Example 1 (good day)

**User:** metrics={"trade_count":4,"win_rate":0.75,"ev_pct":2.1}; insights=[{"type":"win_pattern","text":"SOL 跟单 3 笔全胜"}]; regime=BREAKOUT

**Assistant:** {"headline":"📈 今日 4 笔 — 胜率 75%,EV +2.1%","body":"今日 4 笔交易,3 胜 1 平,平均超额收益 +2.1%,夏普 1.8。\n\n核心模式是 SOL 链聪明钱跟单,3 笔全胜印证 BREAKOUT regime 下 elite 信号优势。失手的 1 笔是 EVM RANGING 期,信号强度本就一般。\n\n下一步:明天若 regime 仍 BREAKOUT,可考虑把 SOL 单笔从 $50 调到 $80 试试。","tone":"celebratory"}

## Example 2 (zero trades day)

**User:** metrics={"trade_count":0}; insights=[]; regime=CRISIS

**Assistant:** {"headline":"今日静默 — CRISIS 期保守观察","body":"Agent 今日全程未触发交易。CRISIS regime 下 HR16 全局禁开仓,所有候选信号被拦截。\n\n\n\n下一步:CRISIS 修复至 RECOVERY 后再开放,通常需 2-3 天。期间若你有手动想进的标的,记得切回 manual 模式。","tone":"cautionary"}

## Example 3 (mixed day)

**User:** metrics={"trade_count":6,"win_rate":0.33,"ev_pct":-1.2,"max_drawdown_pct":-8}; insights=[{"type":"loss_pattern","text":"BC<5% + 4h+ 持仓全亏 (n=3)"}]

**Assistant:** {"headline":"今日 6 笔 — 胜率 33%,EV -1.2%","body":"今日表现不佳。6 笔 2 胜 4 负,EV -1.2%,最大回撤 -8%。\n\n规律明显:BC<5% 进场 + 持仓 > 4h 的 3 笔全亏。这跟前两周观察一致 — 短时间内 BC 起不来的 token 大概率是死币。\n\n下一步:把策略 cooldown 从 15min 拉到 30min,避免连续触发同类小盘 token。","tone":"cautionary"}
