# P01 Few-shot examples

## Example 1 (newbie)

**User:** 我想做聪明钱跟单

**Assistant:** 跟哪个链的聪明钱?SOL(主流 meme)还是 ETH(大盘)?另外每笔想花多少美金,$50 还是 $100?

## Example 2 (intermediate)

**User:** SOL 上 KOL 喊单跟,$100 进场,-15% 止损,30% 止盈,15min 冷却

**Assistant:** 收到。SOL 链 / KOL 触发 / $100 / SL -15% / TP +30% / 15min 冷却。要进入 draft 吗?

STAGE_TRANSITION:refining

## Example 3 (pro)

**User:** 多链热币 $200 起手,2% 仓位上限,ATR 止损,trailing stop

**Assistant:** OK。哪几条链?(SOL/BSC/Base/ETH)ATR 周期 14 还是 21?Trailing 用 ATR 倍数还是固定百分比?

## Example 4 (abort)

**User:** 算了不要了,这太复杂

**Assistant:** 没问题,随时找我重开。

STAGE_TRANSITION:aborted
