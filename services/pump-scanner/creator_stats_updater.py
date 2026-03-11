"""
创建者成功率计算器

逻辑：
  1. 从 pump_tokens 取出所有代币的 creator 地址
  2. 按 creator 分组，统计每个人发了多少币、毕业了多少
  3. 将 creator_prev_tokens / creator_success_rate 写回 pump_tokens

运行时机：每天 UTC 01:00（main.py 调度）
"""

import logging
from typing import Dict, List

from database import get_db

log = logging.getLogger(__name__)


def run_creator_stats_updater():
    log.info("开始更新创建者成功率...")
    db = get_db()

    # 拉取所有代币（mint + creator + complete）
    res = (
        db.table("pump_tokens")
        .select("mint, creator, complete")
        .execute()
    )

    if not res.data:
        log.info("无代币数据，跳过")
        return

    # 按 creator 分组统计
    creator_stats: Dict[str, dict] = {}
    for row in res.data:
        creator = row.get("creator", "")
        if not creator:
            continue
        if creator not in creator_stats:
            creator_stats[creator] = {"total": 0, "graduated": 0, "mints": []}
        creator_stats[creator]["total"] += 1
        creator_stats[creator]["mints"].append(row["mint"])
        if row.get("complete"):
            creator_stats[creator]["graduated"] += 1

    log.info(f"共 {len(creator_stats)} 个创建者地址")

    # 批量更新每个 mint 的 creator_prev_tokens / creator_success_rate
    update_count = 0
    BATCH_SIZE = 50

    for creator, stats in creator_stats.items():
        total   = stats["total"]
        success = stats["graduated"]
        rate    = round(success / total, 4) if total > 0 else 0.0

        mints = stats["mints"]
        # 分批 update
        for i in range(0, len(mints), BATCH_SIZE):
            batch_mints = mints[i:i + BATCH_SIZE]
            try:
                db.table("pump_tokens").update({
                    "creator_prev_tokens":  total,
                    "creator_success_rate": rate,
                }).in_("mint", batch_mints).execute()
                update_count += len(batch_mints)
            except Exception as e:
                log.error(f"更新 creator_stats 失败 ({creator[:8]}): {e}")

    log.info(f"✅ 创建者成功率更新完成，共更新 {update_count} 条记录")


if __name__ == "__main__":
    import logging as _log
    _log.basicConfig(level=_log.INFO)
    run_creator_stats_updater()
