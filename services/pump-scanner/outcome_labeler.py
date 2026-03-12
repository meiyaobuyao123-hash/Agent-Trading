"""
结果回填器

每隔 1 小时运行一次：
  - 找出创建超过 72h、还没打标签的代币
  - 判断是否毕业、涨幅倍数
  - 写入 token_outcomes 表（ML 训练标签）

价格来源：
  1. pump.fun REST API → ath_market_cap（历史最高市值）
  2. 毕业进度 complete 字段

peak_multiplier 计算方法：
  peak_multiplier = ath_mc_sol / rec_mc_sol
  其中 rec_mc_sol（推荐时市值）的获取优先级：
    1. daily_picks.market_cap_sol — 代币被选入每日推荐时的市值
    2. token_snapshots.market_cap_sol — 最后一次快照的市值（距推荐最近）
    3. pump_tokens.initial_mc_sol — 代币创建时初始市值（最终兜底）
  这样 peak_multiplier 反映的是「推荐后涨了多少」，而不是「从创建到历史最高涨了多少」
"""

import logging
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

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

    # ── 批量预取推荐时市值 ──────────────────────────────────────
    # 避免 N+1 查询：一次性拉取所有待标签代币的 daily_picks 和最新 snapshot
    mints = [t["mint"] for t in to_label[:BATCH_SIZE]]
    rec_mc_map = _build_rec_mc_map(db, mints)

    async with aiohttp.ClientSession() as session:
        for token in to_label[:BATCH_SIZE]:
            await _label_token(db, session, token, rec_mc_map)

    log.info("✅ 结果回填完成")


def _build_rec_mc_map(db, mints: List[str]) -> Dict[str, float]:
    """
    为一批代币构建「推荐时市值」映射表。

    优先级（从高到低）：
      1. daily_picks.market_cap_sol  — 代币入选每日推荐时记录的市值
      2. token_snapshots 中最新一条的 market_cap_sol — 距推荐时间最近的快照
    返回 {mint: market_cap_sol}，只包含查到值的代币；查不到的不在 dict 中。
    """
    rec_mc: Dict[str, float] = {}

    # ── 来源 1: daily_picks（推荐时市值，最可靠） ──
    try:
        picks_res = (
            db.table("daily_picks")
            .select("mint, market_cap_sol")
            .in_("mint", mints)
            .order("pick_date", desc=True)
            .execute()
        )
        for row in picks_res.data:
            mint = row["mint"]
            mc = row.get("market_cap_sol")
            # 只取第一次出现（最近的推荐日期，因为已按 pick_date DESC 排序）
            if mint not in rec_mc and mc is not None and float(mc) > 0:
                rec_mc[mint] = float(mc)
    except Exception as e:
        log.warning(f"查询 daily_picks 市值失败: {e}")

    # ── 来源 2: token_snapshots（最新快照市值，补充 daily_picks 缺失的） ──
    missing = [m for m in mints if m not in rec_mc]
    if missing:
        try:
            snap_res = (
                db.table("token_snapshots")
                .select("mint, market_cap_sol")
                .in_("mint", missing)
                .order("snapshot_at", desc=True)
                .execute()
            )
            for row in snap_res.data:
                mint = row["mint"]
                mc = row.get("market_cap_sol")
                if mint not in rec_mc and mc is not None and float(mc) > 0:
                    rec_mc[mint] = float(mc)
        except Exception as e:
            log.warning(f"查询 token_snapshots 市值失败: {e}")

    return rec_mc


async def _label_token(db, session, token: dict, rec_mc_map: Dict[str, float]):
    mint = token["mint"]

    # 拉取最新详情（含 ath_market_cap）
    detail = await _fetch_detail(session, mint)
    if not detail:
        # 拉不到就用已有字段
        detail = token

    did_graduate = bool(detail.get("complete", False))

    # ── ATH 市值（历史最高，来自 pump.fun API） ──
    ath_mc_sol = float(detail.get("ath_market_cap") or detail.get("athMarketCap") or 0)

    # ── 推荐时市值（rec_mc_sol）fallback 链 ──
    # 优先级:
    #   1. rec_mc_map (daily_picks → token_snapshots 已预取)
    #   2. pump_tokens.initial_mc_sol (代币创建时市值，最终兜底)
    #   3. detail.marketCapSol (pump API 返回的当前市值，极端兜底)
    #   4. 1 (避免除零)
    rec_mc_sol = rec_mc_map.get(mint)  # type: Optional[float]
    if rec_mc_sol is None or rec_mc_sol <= 0:
        # fallback: 代币创建时初始市值
        rec_mc_sol = float(token.get("initial_mc_sol") or 0)
    if rec_mc_sol <= 0:
        # fallback: pump API 返回的当前市值
        rec_mc_sol = float(detail.get("marketCapSol") or 0)
    if rec_mc_sol <= 0:
        # 最终兜底，避免除零
        rec_mc_sol = 1.0
        log.warning(f"  [{mint[:8]}] 无法获取推荐时市值，使用兜底值 1")

    # 毕业时长
    hours_to_graduate = None  # type: Optional[float]
    if did_graduate and token.get("graduated_at") and token.get("created_at"):
        try:
            grad = datetime.fromisoformat(token["graduated_at"].replace("Z", "+00:00"))
            created = datetime.fromisoformat(token["created_at"].replace("Z", "+00:00"))
            hours_to_graduate = (grad - created).total_seconds() / 3600
        except Exception:
            pass

    # ── 峰值倍数（推荐后涨幅） ──
    # peak_multiplier = ATH市值 / 推荐时市值
    # 衡量的是：从我们推荐这个代币开始，它最高涨了多少倍
    peak_multiplier = None  # type: Optional[float]
    if ath_mc_sol > 0 and rec_mc_sol > 0:
        peak_multiplier = round(ath_mc_sol / rec_mc_sol, 2)

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
            f"推荐时MC={rec_mc_sol:.1f}  "
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
