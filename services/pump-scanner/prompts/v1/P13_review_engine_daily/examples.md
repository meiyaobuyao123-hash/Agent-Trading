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

## Example 4 (single huge win dominates)

**User:** metrics={"trade_count":3,"win_rate":0.33,"ev_pct":4.2}; insights=[{"type":"win_pattern","text":"PEPE +28% 单笔贡献全天 EV"}]; regime=NORMAL

**Assistant:** {"headline":"今日 3 笔 — 1 胜 2 负,EV 全靠 PEPE 一笔 +28%","body":"今日 3 笔交易,只有 PEPE 那一笔大赚 +28%,其余 2 笔小亏总共 -3%。EV +4.2% 看着好但严重依赖单一标的,数据可读性差。\n\n注意:风险集中在 ETH MEME 类,若明日类似信号再来需更严格筛选(避免依赖运气)。\n\n下一步:把单笔 amount 从 $50 调到 $30,降低运气依赖。","tone":"cautionary"}

## Example 5 (paper-only test day)

**User:** metrics={"trade_count":8,"win_rate":0.5,"ev_pct":0.4,"mode_breakdown":{"paper":8,"live":0}}; insights=[{"type":"calibration","text":"新策略 paper 测试中"}]; regime=RANGING

**Assistant:** {"headline":"今日 8 笔 paper — 测试新策略,胜率 50%","body":"今日全 paper 模式,8 笔 4 胜 4 负,EV +0.4% 接近水平线。RANGING 行情下符合预期,新策略校准中。\n\n继续观察 7 天再评估是否升级 notify。\n\n下一步:不变,持续 paper 跑数据。","tone":"neutral"}
