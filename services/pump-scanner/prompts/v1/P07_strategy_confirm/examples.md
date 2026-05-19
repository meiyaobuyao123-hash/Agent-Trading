# P07 Few-shot

## Example 1 (confirm)

**User:** spec_name="SOL 聪明钱跟单" user_latest_message="行 保存吧"

**Assistant:** 已保存 SOL 聪明钱跟单(paper 模式)。

STAGE_TRANSITION:saved

## Example 2 (refine)

**User:** spec_name="ETH 大盘信号" user_latest_message="止损改成 -10% 吧"

**Assistant:** 好,回到 refining 调止损。

STAGE_TRANSITION:refining

## Example 3 (abort)

**User:** spec_name="多链热币 v2" user_latest_message="算了不要了"

**Assistant:** 没问题,随时找我重开。

STAGE_TRANSITION:aborted

## Example 4 (rename mid-flow)

**User:** spec_name="多链热币 v2" user_latest_message="改名叫 SOL Pulse 吧"

**Assistant:** 好,改成 SOL Pulse。还要继续保存吗?

STAGE_TRANSITION:refining

## Example 5 (defer to next time)

**User:** spec_name="ETH 大盘信号" user_latest_message="先放着,我晚点再看"

**Assistant:** 好,这份策略先存草稿,你随时回来继续。

STAGE_TRANSITION:draft
