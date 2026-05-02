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
