# P09 Few-shot

## Example 1 (improving)

**User:** week_metrics={"trades":18,"win_rate":0.61,"ev":2.3,"max_win":12,"max_loss":-8} prev_week={"trades":15,"win_rate":0.53,"ev":1.4,"max_win":8,"max_loss":-15} insights=["SOL 聪明钱表现稳"] regime_today=NORMAL regime_avg_week=NORMAL persona=intermediate

**Assistant:** {"headline":"本周明显改善:胜率 53% → 61%,EV +1.4% → +2.3%","body":{"highlights":["SOL 聪明钱跟单 8/10 胜","平均回撤从 -15% 改善到 -8%"],"lowlights":["热币榜单胜率仅 40%,需关注"],"next_week_suggestions":["维持 SOL 聪明钱权重","考虑暂停热币榜单 1 周观察"]},"trend":"improving","regime_alert":""}

## Example 2 (deteriorating + regime)

**User:** week_metrics={"trades":12,"win_rate":0.42,"ev":-1.2,"max_win":5,"max_loss":-22} prev_week={"trades":18,"win_rate":0.55,"ev":1.5,"max_win":10,"max_loss":-12} insights=["BTC 跌破支撑"] regime_today=CRISIS regime_avg_week=NORMAL persona=intermediate

**Assistant:** {"headline":"本周明显走弱:胜率 55% → 42%,EV 转负","body":{"highlights":["最快止损反应快,避免单笔 -50% 级损失"],"lowlights":["EV 从 +1.5% 转 -1.2%,持续问题:CRISIS 切换识别延迟","最大单笔回撤 -22% 接近门槛"],"next_week_suggestions":["CRISIS regime 期间暂停 auto 模式","收紧止损到 -10%"]},"trend":"deteriorating","regime_alert":"今日已切到 CRISIS,警惕系统性风险"}

## Example 3 (stable)

**User:** week_metrics={"trades":10,"win_rate":0.5,"ev":0.3,"max_win":6,"max_loss":-5} prev_week={"trades":11,"win_rate":0.5,"ev":0.4,"max_win":7,"max_loss":-6} insights=[] regime_today=RANGE regime_avg_week=RANGE persona=newbie

**Assistant:** {"headline":"本周平稳:胜率 50%,EV +0.3% 持平上周","body":{"highlights":["回撤可控","RANGE 行情下表现符合预期"],"lowlights":["EV 接近 0,策略未跑出超额"],"next_week_suggestions":["保持观察,RANGE 期间不宜激进"]},"trend":"stable","regime_alert":""}

## Example 4 (zero trades CRISIS week)

**User:** week_metrics={"trades":0,"win_rate":null,"ev":null,"max_win":null,"max_loss":null} prev_week={"trades":15,"win_rate":0.55,"ev":1.5,"max_win":10,"max_loss":-12} insights=["CRISIS regime 全周持续"] regime_today=CRISIS regime_avg_week=CRISIS persona=pro

**Assistant:** {"headline":"本周 0 笔 — CRISIS regime 全周锁仓","body":{"highlights":["HR16 正确拦截所有候选信号","保住资金避免系统性损失"],"lowlights":["机会成本:错过反弹时机"],"next_week_suggestions":["regime 转 RECOVERY 后再放开","期间手动机会保持 manual 模式"]},"trend":"defensive","regime_alert":"CRISIS 已持续 7 天,建议关注宏观信号"}

## Example 5 (regime shift mid-week)

**User:** week_metrics={"trades":22,"win_rate":0.45,"ev":-0.8,"max_win":7,"max_loss":-18} prev_week={"trades":15,"win_rate":0.6,"ev":2.1,"max_win":12,"max_loss":-8} insights=["周三 NORMAL → BREAKOUT 切换后 win rate 跌"] regime_today=BREAKOUT regime_avg_week=NORMAL persona=intermediate

**Assistant:** {"headline":"本周走弱:regime 切 BREAKOUT 后未及时调整","body":{"highlights":["周一周二 NORMAL 期 6/8 胜"],"lowlights":["周三 BREAKOUT 后 5/14 仅 36%","策略对 BREAKOUT 适应不良"],"next_week_suggestions":["BREAKOUT regime 暂停均值回归类策略","加入趋势跟随类信号"]},"trend":"deteriorating","regime_alert":"BREAKOUT 已持续 4 天,关注是否切回 NORMAL"}
