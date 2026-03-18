"""
热币实时管理器 — 进出榜单 + 毫秒级打分联动

核心设计：
  PriceFeed 毫秒级价格变动 → 回调 → 重新打分 → 进出榜单判定 → 节流写 DB

  ┌─────────────────────────────────────────────────────────────────┐
  │ 发现层（每10min）                                              │
  │   OKX toplist + GeckoTerminal trending/new_pools               │
  │   → 去重 → 硬过滤 → 打分 → score ≥ 50 入榜                    │
  ├─────────────────────────────────────────────────────────────────┤
  │ 刷新层（毫秒级 PriceFeed + 30s DexScreener 全量）              │
  │   价格变动 → 重新打分 → 退出判定                               │
  ├─────────────────────────────────────────────────────────────────┤
  │ 退出条件（任一触发即退出）                                      │
  │   ① score < 35 连续 3 次                                       │
  │   ② 24h 涨幅 > 200% 且 1h 涨幅 < -5%（冲高回落）              │
  │   ③ 1h 成交量 < 24h 均值的 10%（流动性枯竭）                   │
  │   ④ 买压 < 35%（卖压碾压）                                     │
  │   ⑤ 连续 5 轮发现扫描不再出现（热度消退）                       │
  └─────────────────────────────────────────────────────────────────┘

Python 3.9 兼容。
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from hot_scorer import score_hot_coin, HotScoreResult
from database import get_db

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────

ENTRY_SCORE_MIN = 50          # 入榜最低分
EXIT_SCORE_THRESHOLD = 35     # 连续低于此分退出
EXIT_LOW_SCORE_COUNT = 3      # 连续低分次数
EXIT_PUMP_DUMP_24H = 200      # 24h涨幅超过此值
EXIT_PUMP_DUMP_1H = -5        # 且 1h 涨幅低于此值 → 冲高回落
EXIT_VOL_RATIO = 0.10         # 1h量 < 24h均值的 10% → 枯竭
EXIT_BUY_RATIO = 0.35         # 买压 < 35% → 卖压碾压
EXIT_MISS_COUNT = 5           # 连续 N 轮不出现在发现源
DB_THROTTLE_INTERVAL = 5.0    # DB 写入节流间隔（秒）


class HotCoinManager:
    """热币实时管理器"""

    def __init__(self) -> None:
        # 当前活跃热币 {address_lower: coin_data}
        self._active: Dict[str, dict] = {}

        # 连续低分计数 {address_lower: count}
        self._low_score_count: Dict[str, int] = {}

        # 发现源未命中计数 {address_lower: count}
        self._miss_count: Dict[str, int] = {}

        # DB 写入节流
        self._last_db_write: Dict[str, float] = {}
        self._pending_writes: Dict[str, dict] = {}
        self._flush_task: Optional[asyncio.Task] = None

        # 统计
        self._total_entries = 0
        self._total_exits = 0

    # ═══════════════════════════════════════════════════════════
    # 初始化：从 DB 加载当前活跃热币
    # ═══════════════════════════════════════════════════════════

    def load_from_db(self) -> None:
        """启动时从 hot_coins 表加载活跃代币到内存"""
        try:
            db = get_db()
            res = (
                db.table("hot_coins")
                .select("*")
                .gte("score", ENTRY_SCORE_MIN)
                .eq("goplus_risk", False)
                .execute()
            )
            for row in (res.data or []):
                addr = row["address"].lower()
                self._active[addr] = row
                self._low_score_count[addr] = 0
                self._miss_count[addr] = 0

            log.info(f"[HotCoinManager] 从 DB 加载 {len(self._active)} 个活跃热币")
        except Exception as e:
            log.error(f"[HotCoinManager] 加载失败: {e}")

    # ═══════════════════════════════════════════════════════════
    # PriceFeed 回调：毫秒级价格变动 → 重新打分
    # ═══════════════════════════════════════════════════════════

    def on_price_update(self, address: str, price: float) -> None:
        """
        PriceFeed 回调入口。
        收到价格变动后，更新内存中的价格并重新打分。
        """
        addr = address.lower()
        if addr not in self._active:
            return

        coin = self._active[addr]
        old_price = coin.get("price_usd", 0)
        if old_price <= 0 or price <= 0:
            return

        # 更新价格
        coin["price_usd"] = price

        # 根据价格变化更新涨幅（近似）
        if old_price > 0:
            pct_change = (price - old_price) / old_price * 100
            # 累积到 1h 涨幅（粗略，精确值由 30s DexScreener 刷新覆盖）
            old_1h = coin.get("price_change_1h") or 0
            coin["price_change_1h"] = old_1h + pct_change

        # 重新打分
        result = score_hot_coin(coin)
        coin["score"] = result.total
        coin["score_m"] = result.score_m
        coin["score_q"] = result.score_q
        coin["score_p"] = result.score_p
        coin["score_detail"] = result.detail
        coin["recommendation"] = result.recommendation

        # 退出判定
        should_exit, reason = self._check_exit(addr, coin, result)
        if should_exit:
            self._exit_token(addr, reason)
            return

        # 重置低分计数（如果分数回升）
        if result.total >= EXIT_SCORE_THRESHOLD:
            self._low_score_count[addr] = 0

        # 节流写 DB
        self._schedule_db_write(addr, coin)

    # ═══════════════════════════════════════════════════════════
    # 发现层回调：OKX/GeckoTerminal 扫描结果
    # ═══════════════════════════════════════════════════════════

    def on_discovery_result(self, candidates: List[dict]) -> None:
        """
        发现层（每10min）扫描结果回调。
        新代币尝试入榜，已入榜代币重置 miss_count。
        """
        discovered_addrs: Set[str] = set()

        for coin in candidates:
            addr = coin["address"].lower()
            discovered_addrs.add(addr)

            if addr in self._active:
                # 已入榜：重置未命中计数，更新市场数据
                self._miss_count[addr] = 0
                self._update_market_data(addr, coin)
            else:
                # 新候选：尝试入榜
                result = score_hot_coin(coin)
                if result.total >= ENTRY_SCORE_MIN and not coin.get("goplus_risk"):
                    self._enter_token(addr, coin, result)

        # 更新未命中计数
        for addr in list(self._active.keys()):
            if addr not in discovered_addrs:
                self._miss_count[addr] = self._miss_count.get(addr, 0) + 1

    def _update_market_data(self, addr: str, new_data: dict) -> None:
        """用发现层的完整数据更新内存（涵盖多时间帧）"""
        coin = self._active[addr]
        # 更新多时间帧数据（发现层有完整的 5m/1h/4h/24h）
        for key in [
            "volume_5m_usd", "volume_1h_usd", "volume_4h_usd", "volume_24h_usd",
            "price_change_5m", "price_change_1h", "price_change_4h", "price_change_24h",
            "buys_1h", "sells_1h", "buys_24h", "sells_24h",
            "market_cap_usd", "liquidity_usd", "holder_count",
            "timeframe_hits",
        ]:
            if key in new_data and new_data[key]:
                coin[key] = new_data[key]

    # ═══════════════════════════════════════════════════════════
    # DexScreener 30s 全量刷新回调
    # ═══════════════════════════════════════════════════════════

    def on_full_refresh(self, updated_rows: List[dict]) -> None:
        """
        30s DexScreener 全量刷新回调。
        更新完整多时间帧数据 → 重新打分 → 退出判定。
        """
        for row in updated_rows:
            addr = row["address"].lower()
            if addr not in self._active:
                # 可能是首次通过全量刷新打分入榜
                result = score_hot_coin(row)
                if result.total >= ENTRY_SCORE_MIN and not row.get("goplus_risk"):
                    self._enter_token(addr, row, result)
                continue

            # 更新内存中的完整数据
            coin = self._active[addr]
            coin.update(row)

            # 重新打分
            result = score_hot_coin(coin)
            coin["score"] = result.total
            coin["score_m"] = result.score_m
            coin["score_q"] = result.score_q
            coin["score_p"] = result.score_p
            coin["score_detail"] = result.detail
            coin["recommendation"] = result.recommendation

            # 退出判定
            should_exit, reason = self._check_exit(addr, coin, result)
            if should_exit:
                self._exit_token(addr, reason)
            elif result.total >= EXIT_SCORE_THRESHOLD:
                self._low_score_count[addr] = 0

            self._schedule_db_write(addr, coin)

    # ═══════════════════════════════════════════════════════════
    # 入榜 / 退出
    # ═══════════════════════════════════════════════════════════

    def _enter_token(self, addr: str, coin: dict, result: HotScoreResult) -> None:
        """代币入榜"""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        today_str = now.strftime("%Y-%m-%d")
        discovery_price = coin.get("price_usd", 0)

        coin["score"] = result.total
        coin["score_m"] = result.score_m
        coin["score_q"] = result.score_q
        coin["score_p"] = result.score_p
        coin["score_detail"] = result.detail
        coin["recommendation"] = result.recommendation
        coin["entered_at"] = now_iso
        coin["discovery_price"] = discovery_price
        coin["discovery_date"] = today_str

        self._active[addr] = coin
        self._low_score_count[addr] = 0
        self._miss_count[addr] = 0
        self._total_entries += 1

        # 注册到 PriceFeed
        from price_feed import price_feed
        chain = coin.get("chain", "")
        price_feed.register_token(addr, chain, coin.get("pair_address", ""))

        sym = coin.get("symbol", addr[:8])
        log.info(
            f"[HotCoin] ✅ 入榜 {sym} ({chain}) "
            f"score={result.total} M={result.score_m} Q={result.score_q} P={result.score_p} "
            f"price=${discovery_price:.8f}"
        )

        # 立即写 hot_coins DB
        self._write_to_db(addr, coin)

        # 写入 token_performance 追踪（发现瞬间价格）
        if discovery_price > 0:
            self._write_performance_entry(coin, today_str, discovery_price, result)

    def _exit_token(self, addr: str, reason: str) -> None:
        """代币退出榜单"""
        coin = self._active.pop(addr, None)
        self._low_score_count.pop(addr, None)
        self._miss_count.pop(addr, None)
        self._pending_writes.pop(addr, None)
        self._total_exits += 1

        if coin:
            sym = coin.get("symbol", addr[:8])
            chain = coin.get("chain", "?")
            score = coin.get("score", 0)
            exit_price = coin.get("price_usd", 0)
            discovery_price = coin.get("discovery_price", 0)
            exit_pct = ((exit_price / discovery_price) - 1) * 100 if discovery_price > 0 else 0
            log.info(
                f"[HotCoin] ❌ 退出 {sym} ({chain}) score={score} "
                f"exit_price=${exit_price:.8f} exit_pct={exit_pct:+.1f}% 原因: {reason}"
            )

            # 从 hot_coins 表删除
            try:
                get_db().table("hot_coins").delete().eq(
                    "address", coin.get("address", addr)
                ).execute()
            except Exception as e:
                log.error(f"[HotCoin] 退出删除 DB 失败: {e}")

            # 更新 token_performance：标记退出 + 记录退出原因和价格
            discovery_date = coin.get("discovery_date", "")
            if discovery_date:
                try:
                    now_iso = datetime.now(timezone.utc).isoformat()
                    get_db().table("token_performance").update({
                        "is_active": False,
                        "updated_at": now_iso,
                        "snapshot_data": {
                            **(coin.get("snapshot_data") or {}),
                            "exit_reason": reason,
                            "exit_price": exit_price,
                            "exit_pct": round(exit_pct, 2),
                            "exit_at": now_iso,
                            "exit_score": score,
                        },
                    }).eq("source", "hot_live").eq(
                        "pick_date", discovery_date
                    ).eq("chain", chain).eq(
                        "address", coin.get("address", addr)
                    ).execute()
                except Exception as e:
                    log.debug(f"[HotCoin] 退出更新 performance 失败: {e}")

    # ═══════════════════════════════════════════════════════════
    # 退出判定
    # ═══════════════════════════════════════════════════════════

    def _check_exit(self, addr: str, coin: dict, result: HotScoreResult) -> tuple:
        """
        检查是否应该退出。返回 (should_exit, reason)。
        """
        # ① 连续低分
        if result.total < EXIT_SCORE_THRESHOLD:
            self._low_score_count[addr] = self._low_score_count.get(addr, 0) + 1
            if self._low_score_count[addr] >= EXIT_LOW_SCORE_COUNT:
                return True, f"连续 {EXIT_LOW_SCORE_COUNT} 次 score<{EXIT_SCORE_THRESHOLD} (当前{result.total})"

        # ② 冲高回落（24h 大涨但 1h 已跌）
        pc_24h = coin.get("price_change_24h") or 0
        pc_1h = coin.get("price_change_1h") or 0
        if pc_24h > EXIT_PUMP_DUMP_24H and pc_1h < EXIT_PUMP_DUMP_1H:
            return True, f"冲高回落 24h={pc_24h:+.0f}% 1h={pc_1h:+.1f}%"

        # ③ 成交量枯竭
        vol_1h = coin.get("volume_1h_usd") or 0
        vol_24h = coin.get("volume_24h_usd") or 1
        avg_1h = vol_24h / 24
        if avg_1h > 100 and vol_1h < avg_1h * EXIT_VOL_RATIO:
            return True, f"成交量枯竭 1h=${vol_1h:,.0f} < 24h均值${avg_1h:,.0f}的{EXIT_VOL_RATIO:.0%}"

        # ④ 卖压碾压
        buys_1h = coin.get("buys_1h") or 0
        sells_1h = coin.get("sells_1h") or 0
        total_1h = buys_1h + sells_1h
        if total_1h >= 20:  # 至少 20 笔才判断
            buy_ratio = buys_1h / total_1h
            if buy_ratio < EXIT_BUY_RATIO:
                return True, f"卖压碾压 买占{buy_ratio:.0%} (买{buys_1h}/卖{sells_1h})"

        # ⑤ 发现源连续未命中
        miss = self._miss_count.get(addr, 0)
        if miss >= EXIT_MISS_COUNT:
            return True, f"连续 {miss} 轮不在发现源"

        return False, ""

    # ═══════════════════════════════════════════════════════════
    # 表现追踪：入榜时写入 token_performance
    # ═══════════════════════════════════════════════════════════

    def _write_performance_entry(
        self, coin: dict, pick_date: str, discovery_price: float, result: HotScoreResult
    ) -> None:
        """入榜时写入 token_performance，记录发现瞬间价格"""
        try:
            row = {
                "source": "hot_live",
                "pick_date": pick_date,
                "chain": coin.get("chain", ""),
                "address": coin.get("address", ""),
                "symbol": coin.get("symbol", ""),
                "name": coin.get("name", ""),
                "rank": None,
                "score": result.total,
                "price_at_pick": discovery_price,
                "denomination": "usd",
                "daily_highs": {
                    "D0": {
                        "high": round(discovery_price, 10),
                        "pct": 0.0,
                        "at": datetime.now(timezone.utc).isoformat(),
                    }
                },
                "best_price": discovery_price,
                "best_pct": 0.0,
                "best_day": 0,
                "is_active": True,
                "tracking_days": 0,
                "snapshot_data": {
                    "price_usd": discovery_price,
                    "market_cap_usd": coin.get("market_cap_usd"),
                    "liquidity_usd": coin.get("liquidity_usd"),
                    "volume_24h_usd": coin.get("volume_24h_usd"),
                    "score_m": result.score_m,
                    "score_q": result.score_q,
                    "score_p": result.score_p,
                    "recommendation": result.recommendation,
                    "data_source": coin.get("data_source", ""),
                    "entered_at": coin.get("entered_at", ""),
                },
            }
            get_db().table("token_performance").upsert(
                row, on_conflict="source,pick_date,chain,address"
            ).execute()
            log.debug(f"[HotCoin] 追踪记录写入: {coin.get('symbol')} price=${discovery_price:.8f}")
        except Exception as e:
            log.error(f"[HotCoin] 追踪记录写入失败: {e}")

    # ═══════════════════════════════════════════════════════════
    # 漏斗统计
    # ═══════════════════════════════════════════════════════════

    def record_funnel(
        self, discovered: int, after_hard_filter: int,
        entered: int, exited: int,
    ) -> None:
        """记录每轮扫描的漏斗数据"""
        now_iso = datetime.now(timezone.utc).isoformat()
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            row = {
                "report_date": today_str,
                "source": "hot",
                "discovered": discovered,
                "after_hard_filter": after_hard_filter,
                "entered": entered,
                "exited": exited,
                "active": len(self._active),
                "recorded_at": now_iso,
            }
            # 追加到漏斗统计（不 upsert，每轮一条）
            get_db().table("hot_funnel_stats").insert(row).execute()
        except Exception as e:
            # 表不存在时静默失败（需要创建迁移）
            log.debug(f"[HotCoin] 漏斗统计写入失败（表可能不存在）: {e}")

    # ═══════════════════════════════════════════════════════════
    # DB 写入（节流）
    # ═══════════════════════════════════════════════════════════

    def _schedule_db_write(self, addr: str, coin: dict) -> None:
        """节流写入：同一代币最多每 5s 写一次 DB"""
        now = time.time()
        last = self._last_db_write.get(addr, 0)
        if now - last >= DB_THROTTLE_INTERVAL:
            self._write_to_db(addr, coin)
        else:
            self._pending_writes[addr] = coin

    def _write_to_db(self, addr: str, coin: dict) -> None:
        """立即写一条到 DB"""
        self._last_db_write[addr] = time.time()
        try:
            now_str = datetime.now(timezone.utc).isoformat()
            row = {
                "chain": coin.get("chain", ""),
                "address": coin.get("address", addr),
                "name": coin.get("name"),
                "symbol": coin.get("symbol"),
                "pair_address": coin.get("pair_address"),
                "dex_id": coin.get("dex_id"),
                "price_usd": coin.get("price_usd"),
                "market_cap_usd": coin.get("market_cap_usd"),
                "liquidity_usd": coin.get("liquidity_usd"),
                "volume_24h_usd": coin.get("volume_24h_usd"),
                "volume_1h_usd": coin.get("volume_1h_usd"),
                "volume_5m_usd": coin.get("volume_5m_usd"),
                "volume_4h_usd": coin.get("volume_4h_usd"),
                "price_change_1h": coin.get("price_change_1h"),
                "price_change_6h": coin.get("price_change_6h"),
                "price_change_24h": coin.get("price_change_24h"),
                "price_change_5m": coin.get("price_change_5m"),
                "price_change_4h": coin.get("price_change_4h"),
                "buys_1h": coin.get("buys_1h"),
                "sells_1h": coin.get("sells_1h"),
                "buys_24h": coin.get("buys_24h"),
                "sells_24h": coin.get("sells_24h"),
                "score": coin.get("score"),
                "score_m": coin.get("score_m"),
                "score_q": coin.get("score_q"),
                "score_p": coin.get("score_p"),
                "score_detail": coin.get("score_detail"),
                "recommendation": coin.get("recommendation"),
                "scanned_at": now_str,
                "pair_created_at": coin.get("pair_created_at"),
                "age_days": coin.get("age_days"),
                "holder_count": coin.get("holder_count"),
                "top10_holder_pct": coin.get("top10_holder_pct"),
                "top1_holder_pct": coin.get("top1_holder_pct"),
                "is_honeypot": coin.get("is_honeypot", False),
                "is_open_source": coin.get("is_open_source", True),
                "buy_tax": coin.get("buy_tax", 0.0),
                "sell_tax": coin.get("sell_tax", 0.0),
                "goplus_risk": coin.get("goplus_risk", False),
                "has_twitter": coin.get("has_twitter", False),
                "has_telegram": coin.get("has_telegram", False),
                "has_website": coin.get("has_website", False),
                "image_url": coin.get("image_url") or coin.get("token_logo_url", ""),
                "circ_supply": coin.get("circ_supply"),
                "token_logo_url": coin.get("token_logo_url", ""),
            }
            get_db().table("hot_coins").upsert(
                row, on_conflict="chain,address"
            ).execute()
        except Exception as e:
            log.debug(f"[HotCoin] DB write {addr[:8]}: {e}")

    async def flush_pending(self) -> None:
        """定期刷新 pending 写入（由 main 调度）"""
        while True:
            await asyncio.sleep(DB_THROTTLE_INTERVAL)
            if self._pending_writes:
                batch = dict(self._pending_writes)
                self._pending_writes.clear()
                for addr, coin in batch.items():
                    self._write_to_db(addr, coin)

    # ═══════════════════════════════════════════════════════════
    # 对外查询
    # ═══════════════════════════════════════════════════════════

    def get_active_count(self) -> int:
        return len(self._active)

    def get_active_tokens(self) -> List[dict]:
        return list(self._active.values())

    def get_stats(self) -> dict:
        return {
            "active": len(self._active),
            "total_entries": self._total_entries,
            "total_exits": self._total_exits,
            "by_chain": self._count_by_chain(),
        }

    def _count_by_chain(self) -> dict:
        chains: Dict[str, int] = {}
        for coin in self._active.values():
            c = coin.get("chain", "?")
            chains[c] = chains.get(c, 0) + 1
        return chains


# 全局单例
hot_coin_manager = HotCoinManager()
