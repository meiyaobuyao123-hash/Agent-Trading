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

# ── 风报配置（基于真实数据校准）────────────────────────────
# 基于 3720 笔交易分析：15%/15% 对称在 48% 胜率下注定亏钱
# SOL: MEME 波动剧烈（平均持仓 4h），让赢家跑
# BSC: 稳定链（平均持仓 25h，胜率 57.6%），小幅非对称即可
# Base/ETH: 中等波动
# BTC/ETH: 主流币，波动小，用较紧的对称
TP_PCT_DEFAULT = 20.0
SL_PCT_DEFAULT = 10.0

# (tp_pct, sl_pct) 按链差异化
_TP_SL_BY_CHAIN = {
    "solana": (40.0, 8.0),    # SOL MEME: 大涨让跑，小亏快割
    "bsc":    (25.0, 12.0),   # BSC: 稳定，略偏正
    "base":   (25.0, 12.0),   # Base: 中等
    "eth":    (20.0, 10.0),   # ETH: 对称偏正
    "ethereum": (20.0, 10.0),
    "btc_eth":  (15.0, 10.0), # BTC/ETH 主流币：较紧
}


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
    # BTC/ETH 源用自己的配置
    if source == "btc_eth":
        return _TP_SL_BY_CHAIN["btc_eth"]
    # 其他源按链区分
    c = (chain or "").lower()
    return _TP_SL_BY_CHAIN.get(c, (TP_PCT_DEFAULT, SL_PCT_DEFAULT))


# ── 时段过滤（基于真实数据）──────────────────────────────
# 历史数据显示 UTC 0 时胜率 24%、18 时胜率 6.7%、10 时胜率 33%、21-22 时胜率 39%
# 这些时段全部过滤，不买入
# （对应北京时间 8 时、凌晨 2 时、18 时、凌晨 5-6 时）
_BAD_HOURS_UTC = {0, 10, 18, 21, 22}


def _is_bad_hour() -> bool:
    """判断当前 UTC 小时是否在垃圾时段"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).hour in _BAD_HOURS_UTC


# ── 链权重（基于真实胜率差异）────────────────────────────
# BSC 胜率 57.6% +$39、SOL 胜率 38.2% -$55
# weight=1.0 完全通过，weight=0.5 随机过滤一半，weight=0 全部过滤
_CHAIN_WEIGHT = {
    "bsc":      1.5,   # 明星链，weight>1 → 全进
    "base":     1.0,   # 中等
    "eth":      1.0,
    "ethereum": 1.0,
    "solana":   0.6,   # 弱链，40% 概率过滤掉
    "btc_eth":  1.0,
}


def _pass_chain_filter(chain: str, source: str) -> bool:
    """按链权重概率性过滤"""
    import random
    if source == "btc_eth":
        return True  # BTC/ETH 不受链权重影响
    w = _CHAIN_WEIGHT.get((chain or "").lower(), 1.0)
    if w >= 1.0:
        return True
    return random.random() < w


def _pass_score_filter(score: float, source: str) -> bool:
    """基于真实数据的 score 质量过滤

    真实数据统计（hot 源，617 笔已平仓）：
      50-60 分: 胜率 47.9% (最差)
      60-70 分: 胜率 50.4% (最好)
      70-80 分: 胜率 44.3% (虚高分，pump-then-dump)
      80+  分: 胜率 50.0%

    结论：50-60 和 70-80 是陷阱区间，要么太弱要么太"虚"
    策略：优先入场 60-70 甜点区；70-80 降低权重
    """
    # BTC/ETH 不用 hot 打分，跳过
    if source == "btc_eth":
        return True

    # pump 源 score 是 pump 自己的 0-100 打分，逻辑类似（保留一致）
    # 50 分以下 hot_coin_manager 已经过滤了，这里只针对 sim 入场

    # 60-70 分直接入场（甜点区）
    if 60 <= score < 70:
        return True

    # 70-80 分降低入场概率（虚高分）
    if 70 <= score < 80:
        import random
        return random.random() < 0.5

    # 80+ 分直接入场
    if score >= 80:
        return True

    # 50-60 分降低入场概率（最差段）
    if 50 <= score < 60:
        import random
        return random.random() < 0.4

    # <50 理论上不会到这（hot_coin_manager ENTRY_SCORE_MIN=50），保险
    return False


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

        # ── 入场过滤 1：时段过滤（基于真实数据的垃圾时段）──
        if _is_bad_hour():
            log.debug("[HotSim] %s 跳过（垃圾时段 UTC=%d）", symbol, datetime.now(timezone.utc).hour)
            return

        # ── 入场过滤 2：链权重过滤（SOL 40% 概率过滤）──
        if not _pass_chain_filter(chain, source):
            log.debug("[HotSim] %s 跳过（链权重过滤 chain=%s）", symbol, chain)
            return

        # ── 入场过滤 3：score 质量过滤（50-60 和 70-80 降权）──
        if not _pass_score_filter(score, source):
            log.debug("[HotSim] %s 跳过（score 质量过滤 score=%.1f）", symbol, score)
            return

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
        if key not in self._bought_unique:
            try:
                row_unique = {**base_row, "mode": "unique"}
                res = db.table("hot_sim_trades").insert(row_unique).execute()
                if res.data:
                    self._open_positions[res.data[0]["id"]] = res.data[0]
                self._bought_unique.add(key)
            except Exception as e:
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
            # 使用仓位自己的 tp_pct/sl_pct（每笔仓位开仓时就确定了）
            tp_pct_row = float(pos.get("tp_pct") or TP_PCT_DEFAULT)
            sl_pct_row = float(pos.get("sl_pct") or SL_PCT_DEFAULT)

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
