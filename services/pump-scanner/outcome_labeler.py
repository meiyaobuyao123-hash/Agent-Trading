"""
结果回填器

每隔 1 小时运行一次：
  - 找出创建超过 72h、还没打标签的代币
  - 判断是否毕业、涨幅倍数
  - 写入 token_outcomes 表（ML 训练标签）

价格来源：
  1. pump.fun REST API → ath_market_cap（历史最高市值）
  2. 毕业进度 complete 字段
"""

import logging
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Optional

from database import get_db
from config import PUMP_REST

log = logging.getLogger(__name__)

LABEL_DELAY_HOURS = 72   # 代币创建多久后打标签
BATCH_SIZE        = 50   # 每次处理多少个


async def run_outcome_labeler():
    log.info("开始结果回填...")
    db = get_db()

    # 找出 72h 前创建、未标签的代币
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=LABEL_DELAY_HOURS)).isoformat()

    already_labeled = {
        r["mint"] for r in db.table("token_outcomes").select("mint").execute().data
    }

    res = (
        db.table("pump_tokens")
        .select("mint, symbol, created_at, complete, graduated_at, initial_mc_sol")
        .lt("created_at", cutoff)
        .execute()
    )

    to_label = [r for r in res.data if r["mint"] not in already_labeled]
    log.info(f"待标签代币: {len(to_label)} 个")

    if not to_label:
        return

    async with aiohttp.ClientSession() as session:
        for token in to_label[:BATCH_SIZE]:
            await _label_token(db, session, token)

    log.info("✅ 结果回填完成")


async def _label_token(db, session, token: dict):
    mint = token["mint"]

    # 拉取最新详情（含 ath_market_cap）
    detail = await _fetch_detail(session, mint)
    if not detail:
        # 拉不到就用已有字段
        detail = token

    did_graduate   = bool(detail.get("complete", False))
    initial_mc_sol = float(token.get("initial_mc_sol") or detail.get("marketCapSol") or 1)
    ath_mc_sol     = float(detail.get("ath_market_cap") or detail.get("athMarketCap") or 0)

    # 毕业时长
    hours_to_graduate = None
    if did_graduate and token.get("graduated_at") and token.get("created_at"):
        try:
            grad = datetime.fromisoformat(token["graduated_at"].replace("Z", "+00:00"))
            created = datetime.fromisoformat(token["created_at"].replace("Z", "+00:00"))
            hours_to_graduate = (grad - created).total_seconds() / 3600
        except Exception:
            pass

    # 峰值倍数（相对初始市值）
    peak_multiplier = None
    if ath_mc_sol > 0 and initial_mc_sol > 0:
        peak_multiplier = round(ath_mc_sol / initial_mc_sol, 2)

    # 涨幅标签
    label_graduate = did_graduate
    label_2x  = peak_multiplier is not None and peak_multiplier >= 2.0
    label_10x = peak_multiplier is not None and peak_multiplier >= 10.0

    outcome = {
        "mint":               mint,
        "labeled_at":         datetime.now(timezone.utc).isoformat(),
        "did_graduate":       did_graduate,
        "hours_to_graduate":  hours_to_graduate,
        "peak_multiplier":    peak_multiplier,
        "label_graduate":     label_graduate,
        "label_2x":           label_2x,
        "label_10x":          label_10x,
    }

    try:
        db.table("token_outcomes").upsert(outcome, on_conflict="mint").execute()
        sym = detail.get("symbol", mint[:6])
        log.info(
            f"  [{sym}] 毕业={'✅' if did_graduate else '❌'}  "
            f"峰值={peak_multiplier}x  "
            f"2x={'✅' if label_2x else '❌'}  "
            f"10x={'✅' if label_10x else '❌'}"
        )
    except Exception as e:
        log.error(f"写入 token_outcomes 失败 {mint[:8]}: {e}")


async def _fetch_detail(session: aiohttp.ClientSession, mint: str) -> Optional[dict]:
    try:
        async with session.get(
            f"{PUMP_REST}/coins/{mint}",
            timeout=aiohttp.ClientTimeout(total=8)
        ) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        log.warning(f"fetch detail {mint[:8]} 失败: {e}")
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_outcome_labeler())
