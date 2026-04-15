"""
热币模拟盘 — 入榜即买，实时止盈止损

两种模式并行运行：
  repeat: 每次入榜都买 $10（同币可重复买）
  unique: 每币只买一次

止盈止损 15%，用 PriceFeed 实时价格判断。
数据存 Supabase hot_sim_trades 表。

Python 3.9 兼容。
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Set

from database import get_db

log = logging.getLogger(__name__)

BUY_AMOUNT_DEFAULT = 10.0
BUY_AMOUNT_BTC = 50.0
BUY_AMOUNT_ETH = 20.0

# 风报配置从 config.py 读取（支持环境变量覆盖，调整无需改代码）
from config import (
    SIM_BAD_HOURS_UTC,
    SIM_CHAIN_WEIGHTS,
    SIM_TP_SL_BY_CHAIN,
    SIM_TP_DEFAULT,
    SIM_SL_DEFAULT,
    SIM_SCORE_THRESHOLDS,
)

# 兼容别名（避免其他文件引用断）
TP_PCT_DEFAULT = SIM_TP_DEFAULT
SL_PCT_DEFAULT = SIM_SL_DEFAULT


def _get_buy_amount(source: str, symbol: str) -> float:
    """按资产类型返回下单金额"""
    if source == "btc_eth":
        if symbol.upper() == "BTC":
            return BUY_AMOUNT_BTC
        elif symbol.upper() == "ETH":
            return BUY_AMOUNT_ETH
    return BUY_AMOUNT_DEFAULT


def _get_tp_sl(chain: str, source: str) -> tuple:
    """按链和信号源返回 (tp_pct, sl_pct)"""
    if source == "btc_eth":
        return SIM_TP_SL_BY_CHAIN.get("btc_eth", (SIM_TP_DEFAULT, SIM_SL_DEFAULT))
    c = (chain or "").lower()
    return SIM_TP_SL_BY_CHAIN.get(c, (SIM_TP_DEFAULT, SIM_SL_DEFAULT))


def _is_bad_hour() -> bool:
    """判断当前 UTC 小时是否在垃圾时段"""
    return datetime.now(timezone.utc).hour in SIM_BAD_HOURS_UTC


def _addr_hash_ratio(address: str) -> float:
    """把地址哈希映射到 [0, 1)，用于确定性过滤（同地址永远返回同值）"""
    if not address:
        return 0.5
    # 用 MD5 保证跨进程一致（Python 内置 hash() 每次重启变）
    import hashlib
    h = hashlib.md5(address.lower().encode()).hexdigest()
    return (int(h[:8], 16) % 10000) / 10000.0


def _pass_chain_filter(chain: str, source: str, address: str) -> bool:
    """按链权重确定性过滤（基于地址哈希，同地址永远返回同结果）"""
    if source == "btc_eth":
        return True
    w = SIM_CHAIN_WEIGHTS.get((chain or "").lower(), 1.0)
    if w >= 1.0:
        return True
    return _addr_hash_ratio(address) < w


def _pass_score_filter(score: float, source: str, address: str) -> bool:
    """按 source 和地址哈希的 score 质量过滤

    阈值表结构：{source: {"ranges": [(low, high, weight), ...]}}
    - weight >= 1.0 必过
    - weight < 1.0 用 hash(addr) 确定性概率过滤
    """
    cfg = SIM_SCORE_THRESHOLDS.get(source) or SIM_SCORE_THRESHOLDS.get("hot")
    if not cfg:
        return True

    ranges = cfg.get("ranges") or []
    for low, high, weight in ranges:
        if low <= score < high:
            if weight >= 1.0:
                return True
            return _addr_hash_ratio(address) < weight

    # 所有范围都不匹配 → 不入场（默认拒绝）
    return False


# ── 过滤统计计数器（每 5 分钟输出一次）────────────────────
class _FilterStats:
    """入场过滤统计"""
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.bad_hour = 0
        self.bad_chain = 0
        self.bad_score = 0
        self.last_log = 0.0
        self.window_sec = 300  # 5 分钟

    def record(self, passed: bool, reason: str = ""):
        self.total += 1
        if passed:
            self.passed += 1
        elif reason == "hour":
            self.bad_hour += 1
        elif reason == "chain":
            self.bad_chain += 1
        elif reason == "score":
            self.bad_score += 1

    def maybe_log(self):
        now = time.time()
        if now - self.last_log < self.window_sec:
            return
        if self.total == 0:
            self.last_log = now
            return
        pass_rate = self.passed / self.total * 100
        log.info(
            "[HotSim] 过滤统计(5min): 总=%d 通过=%d (%.1f%%) bad_hour=%d bad_chain=%d bad_score=%d",
            self.total, self.passed, pass_rate,
            self.bad_hour, self.bad_chain, self.bad_score,
        )
        # 重置窗口
        self.total = self.passed = self.bad_hour = self.bad_chain = self.bad_score = 0
        self.last_log = now


_filter_stats = _FilterStats()


class HotSimTrader:
    def __init__(self):
        # unique 模式已买过的 token（chain:address）
        self._bought_unique: Set[str] = set()
        # 所有 open 仓位 {id: {entry_price, chain, address, symbol, mode}}
        self._open_positions: Dict[str, dict] = {}
        self._initialized = False
        self._price_update_count = 0
        self._price_match_count = 0
        self._last_stats_log = 0.0

    def init_from_db(self):
        """启动时从 DB 加载已有数据"""
        if self._initialized:
            return
        try:
            db = get_db()
            # 加载 unique 已买过的
            res = db.table("hot_sim_trades").select("chain, address").eq("mode", "unique").execute()
            for r in (res.data or []):
                self._bought_unique.add(f"{r['chain']}:{r['address']}")

            # 加载 open 仓位
            res2 = db.table("hot_sim_trades").select("*").eq("status", "open").execute()
            for r in (res2.data or []):
                self._open_positions[r["id"]] = r

            # 为所有 open 仓位注册 PriceFeed（确保退榜代币仍收价格）
            registered = set()
            for pos in self._open_positions.values():
                addr = pos.get("address", "")
                chain = pos.get("chain", "")
                if addr and addr.lower() not in registered:
                    try:
                        from price_feed import price_feed
                        price_feed.register_token(addr, chain, source="sim_trader")
                        registered.add(addr.lower())
                    except Exception:
                        pass

            log.info("[HotSim] 初始化: unique已买=%d, open仓位=%d, 注册PriceFeed=%d",
                     len(self._bought_unique), len(self._open_positions), len(registered))
            self._initialized = True
        except Exception as e:
            log.warning("[HotSim] 初始化失败: %s", e)

    def on_token_enter(self, address: str, chain: str, symbol: str,
                       price: float, score: float, source: str = "hot"):
        """信号触发时调用 — 自动模拟买入（支持多信号源）"""
        if price <= 0:
            return

        # ── 入场过滤（按顺序：时段→链→score，任一失败即跳过）──
        # 用确定性过滤（hash(address)）保证同地址结果一致
        if _is_bad_hour():
            _filter_stats.record(False, "hour")
            _filter_stats.maybe_log()
            log.info("[HotSim] %s 过滤:垃圾时段 UTC=%d", symbol, datetime.now(timezone.utc).hour)
            return

        if not _pass_chain_filter(chain, source, address):
            _filter_stats.record(False, "chain")
            _filter_stats.maybe_log()
            log.info("[HotSim] %s 过滤:链权重 chain=%s", symbol, chain)
            return

        if not _pass_score_filter(score, source, address):
            _filter_stats.record(False, "score")
            _filter_stats.maybe_log()
            log.info("[HotSim] %s 过滤:score %.1f (source=%s)", symbol, score, source)
            return

        _filter_stats.record(True)
        _filter_stats.maybe_log()

        self.init_from_db()
        now_iso = datetime.now(timezone.utc).isoformat()
        db = get_db()
        amount = _get_buy_amount(source, symbol)
        tp_pct, sl_pct = _get_tp_sl(chain, source)

        base_row = {
            "chain": chain,
            "address": address,
            "symbol": symbol or "?",
            "entry_price": price,
            "amount_usd": amount,
            "tp_pct": tp_pct,
            "sl_pct": sl_pct,
            "tp_price": round(price * (1 + tp_pct / 100), 12),
            "sl_price": round(price * (1 - sl_pct / 100), 12),
            "score_at_entry": score,
            "source": source,
            "status": "open",
            "entered_at": now_iso,
        }

        # 注册到 PriceFeed（确保退榜后也能收到价格更新）
        addr_lower = address.lower()
        has_existing = any(
            p.get("address", "").lower() == addr_lower
            for p in self._open_positions.values()
        )
        if not has_existing:
            try:
                from price_feed import price_feed
                price_feed.register_token(address, chain, source="sim_trader")
            except Exception as e:
                log.debug("[HotSim] register_token: %s", e)

        # mode=repeat: 每次都买
        try:
            row_repeat = {**base_row, "mode": "repeat"}
            res = db.table("hot_sim_trades").insert(row_repeat).execute()
            if res.data:
                self._open_positions[res.data[0]["id"]] = res.data[0]
        except Exception as e:
            log.debug("[Sim] repeat insert: %s", e)

        # mode=unique: 只买一次（BTC/ETH 跳过 unique，只有 2 个币没意义）
        if source == "btc_eth":
            return

        key = f"{source}:{chain}:{address}"
        # 原子化：先占位，写入失败回滚。防止两个信号源（hot + smart_money）
        # 并发触发同代币时穿过检查、双重插入。
        if key in self._bought_unique:
            return
        self._bought_unique.add(key)
        try:
            row_unique = {**base_row, "mode": "unique"}
            res = db.table("hot_sim_trades").insert(row_unique).execute()
            if res.data:
                self._open_positions[res.data[0]["id"]] = res.data[0]
        except Exception as e:
            # 失败回滚占位，允许下次重试
            self._bought_unique.discard(key)
            log.debug("[HotSim] unique insert: %s", e)

    def on_price_update(self, address: str, price: float):
        """价格更新时检查止盈止损"""
        if price <= 0:
            return
        self.init_from_db()

        self._price_update_count += 1
        now = time.time()
        matched = False

        to_close = []
        for pid, pos in self._open_positions.items():
            if pos.get("address", "").lower() != address.lower():
                continue

            matched = True
            tp = float(pos.get("tp_price", 0))
            sl = float(pos.get("sl_price", 0))
            # 显式检查 None，避免 0 或 False 被 `or` 替换成默认值
            _tp_raw = pos.get("tp_pct")
            _sl_raw = pos.get("sl_pct")
            if _tp_raw is None:
                log.warning("[HotSim] pid=%s 缺 tp_pct，用默认 %.1f", pid, TP_PCT_DEFAULT)
                tp_pct_row = TP_PCT_DEFAULT
            else:
                tp_pct_row = float(_tp_raw)
            if _sl_raw is None:
                log.warning("[HotSim] pid=%s 缺 sl_pct，用默认 %.1f", pid, SL_PCT_DEFAULT)
                sl_pct_row = SL_PCT_DEFAULT
            else:
                sl_pct_row = float(_sl_raw)

            if tp > 0 and price >= tp:
                to_close.append((pid, "tp", price, tp_pct_row))
            elif sl > 0 and price <= sl:
                to_close.append((pid, "sl", price, -sl_pct_row))

        if matched:
            self._price_match_count += 1

        # 每 60s 输出统计
        if now - self._last_stats_log > 60:
            log.info("[HotSim] 价格统计: %d 次更新, %d 次匹配仓位, open=%d",
                     self._price_update_count, self._price_match_count,
                     len(self._open_positions))
            self._price_update_count = 0
            self._price_match_count = 0
            self._last_stats_log = now

        for pid, reason, exit_price, pnl_pct in to_close:
            self._close_position(pid, reason, exit_price, pnl_pct)

    def _close_position(self, pid: str, reason: str, exit_price: float, pnl_pct: float):
        """平仓"""
        pos_amount = float(self._open_positions.get(pid, {}).get("amount_usd", BUY_AMOUNT_DEFAULT))
        pnl_usd = round(pos_amount * pnl_pct / 100, 2)
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            get_db().table("hot_sim_trades").update({
                "status": reason,
                "exit_price": exit_price,
                "pnl_pct": round(pnl_pct, 2),
                "pnl_usd": pnl_usd,
                "exited_at": now_iso,
            }).eq("id", pid).execute()
        except Exception as e:
            log.debug("[HotSim] close: %s", e)

        pos = self._open_positions.pop(pid, None)
        if pos:
            sym = pos.get("symbol", "?")
            mode = pos.get("mode", "?")
            log.info("[HotSim] %s %s %s: %s exit=$%.8f pnl=%+.1f%% ($%+.2f)",
                     mode, reason.upper(), sym, pos.get("chain", ""), exit_price, pnl_pct, pnl_usd)

            # 该地址无更多 open 仓位 → 取消 PriceFeed 追踪
            addr = pos.get("address", "")
            if addr:
                still_open = any(
                    p.get("address", "").lower() == addr.lower()
                    for p in self._open_positions.values()
                )
                if not still_open:
                    try:
                        from price_feed import price_feed
                        price_feed.unregister_token(addr, source="sim_trader")
                    except Exception:
                        pass


# 全局单例
_sim_trader = None

def get_sim_trader() -> HotSimTrader:
    global _sim_trader
    if _sim_trader is None:
        _sim_trader = HotSimTrader()
    return _sim_trader
