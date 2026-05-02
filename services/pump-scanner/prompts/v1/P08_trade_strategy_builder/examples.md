# P08 Few-shot

## Example 1 (paper → notify approve)

**User:** strategy_id=s-1 current_mode=paper target_mode=notify paper_perf={"closed_trades":42,"win_rate":0.59,"avg_pnl_pct":2.1,"max_dd":-14,"days_active":35} user_message="想升级到 notify"

**Assistant:** {"verdict":"approve","target_mode":"notify","reasons":["closed=42 >= 30","avg_pnl_pct=2.1% >= 1%","跑了 35d >= 30d","max_dd=-14% 可控"],"suggested_amount_usd":100,"suggested_max_position_pct":5,"warnings":[]}

## Example 2 (paper → auto reject low sample)

**User:** strategy_id=s-2 current_mode=paper target_mode=auto paper_perf={"closed_trades":12,"win_rate":0.66,"avg_pnl_pct":3.5,"max_dd":-8,"days_active":18} user_message="切到 auto"

**Assistant:** {"verdict":"reject","target_mode":"auto","reasons":["closed=12 < 30 笔","跑了 18d < 30d","样本不够支持 auto"],"suggested_amount_usd":0,"suggested_max_position_pct":0,"warnings":["再跑 18 笔 + 12 天到 30/30 门槛"]}

## Example 3 (notify → auto approve)

**User:** strategy_id=s-3 current_mode=notify target_mode=auto paper_perf={"closed_trades":68,"win_rate":0.62,"avg_pnl_pct":1.8,"max_dd":-22,"days_active":62,"notify_user_approval_rate":0.85} user_message="跑得不错切 auto"

**Assistant:** {"verdict":"approve","target_mode":"auto","reasons":["notify 触发 68 笔 >= 30","用户确认率 85% >= 80%","max_dd=-22% >= -25%"],"suggested_amount_usd":100,"suggested_max_position_pct":5,"warnings":["首次切 auto 必走 HITL 确认","保留随时切回 notify 的权利"]}
