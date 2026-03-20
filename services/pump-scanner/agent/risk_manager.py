"""
风控引擎 — 交易前风险检查 + 止损止盈 + 熔断器

功能：
1. 仓位限制（单笔 / 组合占比 / 持仓数）
2. 亏损限制（单笔 / 日 / 周 / 最大回撤）
3. 频率限制（小时 / 日 / 最小间隔）
4. 代币安全检查（流动性 / 税率 / 持有人 / 集中度 / 蜜罐）
5. 熔断器（触发后自动暂停 + 冷却）
6. 止损 / 止盈 / 追踪止损

Python 3.9 兼容。
"""
import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    """风控参数配置"""
    max_position_usd: float = 100.0
    max_portfolio_pct: float = 0.10
    max_open_positions: int = 20
    max_loss_per_trade_pct: float = 0.30
    max_daily_loss_usd: float = 50.0
    max_weekly_loss_usd: float = 200.0
    max_drawdown_pct: float = 0.20
    max_trades_per_hour: int = 5
    max_trades_per_day: int = 20
    min_trade_interval_sec: int = 60
    min_liquidity_usd: float = 10000.0
    max_buy_tax_pct: float = 0.10
    max_sell_tax_pct: float = 0.10
    min_holder_count: int = 50
    max_top10_concentration: float = 0.80
    block_honeypot: bool = True
    circuit_breaker_enabled: bool = True
    circuit_breaker_cooldown_min: int = 60
    default_stop_loss_pct: float = 0.30
    default_take_profit_pct: float = 1.00
    trailing_stop_pct: float = 0.15
    trailing_stop_activation: float = 0.50


@dataclass
class RiskCheckResult:
    """风控检查结果"""
    passed: bool
    reason: str = ""
    risk_level: str = "low"

    @staticmethod
    def ok() -> "RiskCheckResult":
        return RiskCheckResult(passed=True, reason="", risk_level="low")

    @staticmethod
    def warn(reason: str) -> "RiskCheckResult":
        return RiskCheckResult(passed=True, reason=reason, risk_level="medium")

    @staticmethod
    def block(reason: str) -> "RiskCheckResult":
        return RiskCheckResult(passed=False, reason=reason, risk_level="blocked")


@dataclass
class TradeRecord:
    """交易记录（内存）"""
    token_address: str
    chain: str
    action: str
    amount_usd: float
    price: float
    pnl_usd: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class RiskManager:
    """风控管理器"""

    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()
        self._trade_history: deque = deque(maxlen=10000)
        self._daily_pnl: float = 0.0
        self._weekly_pnl: float = 0.0
        self._daily_trade_count: int = 0
        self._last_daily_reset: datetime = datetime.utcnow()
        self._last_weekly_reset: datetime = datetime.utcnow()
        self._open_positions: Dict[str, float] = {}
        self._portfolio_value: float = 1000.0
        self._peak_portfolio: float = 1000.0
        self._circuit_breaker_active: bool = False
        self._circuit_breaker_until: Optional[datetime] = None
        self._circuit_breaker_reason: str = ""
        self._blacklist: set = set()
        self._recent_trade_times: deque = deque(maxlen=100)
        log.info(
            f"RiskManager initialized: max_position=${self.config.max_position_usd}, "
            f"max_daily_loss=${self.config.max_daily_loss_usd}, "
            f"max_positions={self.config.max_open_positions}"
        )

    def check_trade(
        self, token_address: str, chain: str, action: str,
        amount_usd: float, token_data: Optional[Dict[str, Any]] = None,
    ) -> RiskCheckResult:
        """综合交易前检查"""
        self._maybe_reset_counters()
        token_data = token_data or {}
        checks = [
            ("circuit_breaker", self._check_circuit_breaker),
            ("velocity", lambda: self._check_velocity()),
            ("daily_loss", lambda: self._check_daily_loss()),
            ("weekly_loss", lambda: self._check_weekly_loss()),
            ("drawdown", lambda: self._check_drawdown()),
            ("position_size", lambda: self._check_position_size(amount_usd)),
            ("position_count", lambda: self._check_position_count(token_address, action)),
            ("blacklist", lambda: self._check_blacklist(token_address)),
            ("liquidity", lambda: self._check_liquidity(token_data)),
            ("tax", lambda: self._check_tax(token_data)),
            ("holders", lambda: self._check_holders(token_data)),
            ("concentration", lambda: self._check_concentration(token_data)),
            ("honeypot", lambda: self._check_honeypot(token_data)),
            ("market_regime", lambda: self._check_market_regime(action)),
            ("chain_concentration", lambda: self._check_chain_concentration(chain, action)),
        ]
        warnings: List[str] = []
        for name, check_fn in checks:
            try:
                result = check_fn()
                if not result.passed:
                    log.warning(f"Risk BLOCKED [{name}]: {result.reason} (token={token_address[:10]})")
                    return result
                if result.reason:
                    warnings.append(f"[{name}] {result.reason}")
            except Exception as e:
                log.error(f"Risk check error [{name}]: {e}")
        if warnings:
            return RiskCheckResult(passed=True, reason="; ".join(warnings), risk_level="medium")
        return RiskCheckResult.ok()

    def _check_circuit_breaker(self) -> RiskCheckResult:
        if not self._circuit_breaker_active:
            return RiskCheckResult.ok()
        if self._circuit_breaker_until and datetime.utcnow() >= self._circuit_breaker_until:
            self._circuit_breaker_active = False
            self._circuit_breaker_until = None
            log.info("Circuit breaker auto-deactivated")
            return RiskCheckResult.ok()
        remaining = ""
        if self._circuit_breaker_until:
            delta = self._circuit_breaker_until - datetime.utcnow()
            remaining = f", cooldown {int(delta.total_seconds() / 60)} min"
        return RiskCheckResult.block(f"Circuit breaker active: {self._circuit_breaker_reason}{remaining}")

    def _check_velocity(self) -> RiskCheckResult:
        now = time.time()
        if self._recent_trade_times:
            elapsed = now - self._recent_trade_times[-1]
            if elapsed < self.config.min_trade_interval_sec:
                return RiskCheckResult.block(f"Trade interval too short ({int(elapsed)}s < {self.config.min_trade_interval_sec}s)")
        hour_ago = now - 3600
        hourly = sum(1 for t in self._recent_trade_times if t > hour_ago)
        if hourly >= self.config.max_trades_per_hour:
            return RiskCheckResult.block(f"Hourly limit reached ({hourly}/{self.config.max_trades_per_hour})")
        if self._daily_trade_count >= self.config.max_trades_per_day:
            return RiskCheckResult.block(f"Daily limit reached ({self._daily_trade_count}/{self.config.max_trades_per_day})")
        return RiskCheckResult.ok()

    def _check_daily_loss(self) -> RiskCheckResult:
        if self._daily_pnl <= -self.config.max_daily_loss_usd:
            self._trigger_circuit_breaker("Daily loss limit reached")
            return RiskCheckResult.block(f"Daily loss limit (${abs(self._daily_pnl):.2f} >= ${self.config.max_daily_loss_usd})")
        if self._daily_pnl <= -(self.config.max_daily_loss_usd * 0.8):
            return RiskCheckResult.warn(f"Approaching daily loss limit (${abs(self._daily_pnl):.2f} / ${self.config.max_daily_loss_usd})")
        return RiskCheckResult.ok()

    def _check_weekly_loss(self) -> RiskCheckResult:
        if self._weekly_pnl <= -self.config.max_weekly_loss_usd:
            self._trigger_circuit_breaker("Weekly loss limit reached")
            return RiskCheckResult.block(f"Weekly loss limit (${abs(self._weekly_pnl):.2f} >= ${self.config.max_weekly_loss_usd})")
        return RiskCheckResult.ok()

    def _check_drawdown(self) -> RiskCheckResult:
        if self._peak_portfolio <= 0:
            return RiskCheckResult.ok()
        dd = (self._peak_portfolio - self._portfolio_value) / self._peak_portfolio
        if dd >= self.config.max_drawdown_pct:
            self._trigger_circuit_breaker(f"Max drawdown ({dd:.1%})")
            return RiskCheckResult.block(f"Max drawdown ({dd:.1%} >= {self.config.max_drawdown_pct:.0%})")
        return RiskCheckResult.ok()

    def _check_position_size(self, amount_usd: float) -> RiskCheckResult:
        if amount_usd > self.config.max_position_usd:
            return RiskCheckResult.block(f"Position too large (${amount_usd:.2f} > ${self.config.max_position_usd})")
        if self._portfolio_value > 0:
            pct = amount_usd / self._portfolio_value
            if pct > self.config.max_portfolio_pct:
                return RiskCheckResult.block(f"Portfolio pct too high ({pct:.1%} > {self.config.max_portfolio_pct:.0%})")
        return RiskCheckResult.ok()

    def _check_position_count(self, token_address: str, action: str) -> RiskCheckResult:
        if action == "sell" or token_address in self._open_positions:
            return RiskCheckResult.ok()
        if len(self._open_positions) >= self.config.max_open_positions:
            return RiskCheckResult.block(f"Max positions ({len(self._open_positions)}/{self.config.max_open_positions})")
        return RiskCheckResult.ok()

    def _check_blacklist(self, token_address: str) -> RiskCheckResult:
        if token_address in self._blacklist:
            return RiskCheckResult.block(f"Token blacklisted: {token_address[:10]}...")
        return RiskCheckResult.ok()

    def _check_liquidity(self, td: Dict[str, Any]) -> RiskCheckResult:
        liq = td.get("liquidity_usd", 0)
        if liq and liq < self.config.min_liquidity_usd:
            return RiskCheckResult.block(f"Low liquidity (${liq:,.0f} < ${self.config.min_liquidity_usd:,.0f})")
        return RiskCheckResult.ok()

    def _check_tax(self, td: Dict[str, Any]) -> RiskCheckResult:
        bt = td.get("buy_tax_rate", 0) or 0
        st = td.get("sell_tax_rate", 0) or 0
        if bt > self.config.max_buy_tax_pct:
            return RiskCheckResult.block(f"Buy tax too high ({bt:.1%} > {self.config.max_buy_tax_pct:.0%})")
        if st > self.config.max_sell_tax_pct:
            return RiskCheckResult.block(f"Sell tax too high ({st:.1%} > {self.config.max_sell_tax_pct:.0%})")
        return RiskCheckResult.ok()

    def _check_holders(self, td: Dict[str, Any]) -> RiskCheckResult:
        h = td.get("holder_count", 0)
        if h and h < self.config.min_holder_count:
            return RiskCheckResult.block(f"Too few holders ({h} < {self.config.min_holder_count})")
        return RiskCheckResult.ok()

    def _check_concentration(self, td: Dict[str, Any]) -> RiskCheckResult:
        c = td.get("top10_holder_pct", 0)
        if c and c > self.config.max_top10_concentration:
            return RiskCheckResult.block(f"Top10 too concentrated ({c:.1%} > {self.config.max_top10_concentration:.0%})")
        return RiskCheckResult.ok()

    def _check_honeypot(self, td: Dict[str, Any]) -> RiskCheckResult:
        if not self.config.block_honeypot:
            return RiskCheckResult.ok()
        if td.get("is_honeypot", False):
            return RiskCheckResult.block("Honeypot detected")
        return RiskCheckResult.ok()

    def calculate_stop_loss(self, entry_price: float, custom_pct: Optional[float] = None) -> float:
        pct = custom_pct if custom_pct is not None else self.config.default_stop_loss_pct
        return entry_price * (1.0 - pct)

    def calculate_take_profit(self, entry_price: float, custom_pct: Optional[float] = None) -> float:
        pct = custom_pct if custom_pct is not None else self.config.default_take_profit_pct
        return entry_price * (1.0 + pct)

    def should_trailing_stop(
        self, entry_price: float, current_price: float, peak_price: float,
        custom_activation: Optional[float] = None, custom_trail_pct: Optional[float] = None,
    ) -> Tuple[bool, str]:
        activation = custom_activation or self.config.trailing_stop_activation
        trail_pct = custom_trail_pct or self.config.trailing_stop_pct
        gain = (peak_price - entry_price) / entry_price if entry_price > 0 else 0
        if gain < activation:
            return False, ""
        ts_price = peak_price * (1.0 - trail_pct)
        if current_price <= ts_price:
            return True, f"Trailing stop: ${current_price:.6f} <= ${ts_price:.6f} (peak ${peak_price:.6f})"
        return False, ""

    def record_trade(
        self, token_address: str, chain: str, action: str,
        amount_usd: float, price: float, pnl_usd: float = 0.0,
    ):
        record = TradeRecord(token_address=token_address, chain=chain, action=action,
                             amount_usd=amount_usd, price=price, pnl_usd=pnl_usd)
        self._trade_history.append(record)
        self._recent_trade_times.append(record.timestamp)
        self._daily_trade_count += 1
        if action == "buy":
            self._open_positions[token_address] = self._open_positions.get(token_address, 0.0) + amount_usd
        elif action == "sell" and token_address in self._open_positions:
            rem = self._open_positions[token_address] - amount_usd
            if rem <= 0:
                del self._open_positions[token_address]
            else:
                self._open_positions[token_address] = rem
        if pnl_usd != 0:
            self._daily_pnl += pnl_usd
            self._weekly_pnl += pnl_usd
            self._portfolio_value += pnl_usd
            if self._portfolio_value > self._peak_portfolio:
                self._peak_portfolio = self._portfolio_value
        log.info(f"Trade: {action} ${amount_usd:.2f} {token_address[:10]}... PnL=${pnl_usd:.2f}")

    def _trigger_circuit_breaker(self, reason: str):
        if not self.config.circuit_breaker_enabled or self._circuit_breaker_active:
            return
        self._circuit_breaker_active = True
        self._circuit_breaker_until = datetime.utcnow() + timedelta(minutes=self.config.circuit_breaker_cooldown_min)
        self._circuit_breaker_reason = reason
        log.critical(f"CIRCUIT BREAKER: {reason}, until {self._circuit_breaker_until.isoformat()}")
        self._create_circuit_breaker_alert(reason)

    def _create_circuit_breaker_alert(self, reason: str):
        try:
            from database import get_db
            get_db().table("agent_alerts").insert({
                "user_id": "system", "strategy_id": "risk_manager",
                "trigger_context": {"type": "circuit_breaker", "reason": reason,
                                    "daily_pnl": self._daily_pnl, "weekly_pnl": self._weekly_pnl,
                                    "portfolio_value": self._portfolio_value,
                                    "open_positions": len(self._open_positions)},
                "title": "Circuit Breaker Triggered",
                "message": f"Trading auto-paused: {reason}",
                "severity": "critical", "is_read": False, "is_pushed": False,
            }).execute()
        except Exception as e:
            log.error(f"Failed to create circuit breaker alert: {e}")

    def deactivate_circuit_breaker(self):
        self._circuit_breaker_active = False
        self._circuit_breaker_until = None
        self._circuit_breaker_reason = ""
        log.info("Circuit breaker manually deactivated")

    def _maybe_reset_counters(self):
        now = datetime.utcnow()
        if (now - self._last_daily_reset).total_seconds() >= 86400:
            self.reset_daily_pnl()
            self._last_daily_reset = now
        if (now - self._last_weekly_reset).total_seconds() >= 604800:
            self._weekly_pnl = 0.0
            self._last_weekly_reset = now

    def reset_daily_pnl(self):
        self._daily_pnl = 0.0
        self._daily_trade_count = 0

    def add_to_blacklist(self, token_address: str):
        self._blacklist.add(token_address)

    def remove_from_blacklist(self, token_address: str):
        self._blacklist.discard(token_address)

    def set_portfolio_value(self, value: float):
        self._portfolio_value = value
        if value > self._peak_portfolio:
            self._peak_portfolio = value

    def get_risk_summary(self) -> Dict[str, Any]:
        dd = 0.0
        if self._peak_portfolio > 0:
            dd = (self._peak_portfolio - self._portfolio_value) / self._peak_portfolio
        return {
            "portfolio_value": round(self._portfolio_value, 2),
            "peak_portfolio": round(self._peak_portfolio, 2),
            "drawdown_pct": round(dd, 4),
            "daily_pnl": round(self._daily_pnl, 2),
            "weekly_pnl": round(self._weekly_pnl, 2),
            "daily_trade_count": self._daily_trade_count,
            "open_positions": len(self._open_positions),
            "open_position_tokens": list(self._open_positions.keys()),
            "circuit_breaker": {
                "active": self._circuit_breaker_active,
                "reason": self._circuit_breaker_reason,
                "until": self._circuit_breaker_until.isoformat() if self._circuit_breaker_until else None,
            },
            "blacklist_count": len(self._blacklist),
            "config": {
                "max_position_usd": self.config.max_position_usd,
                "max_portfolio_pct": self.config.max_portfolio_pct,
                "max_open_positions": self.config.max_open_positions,
                "max_daily_loss_usd": self.config.max_daily_loss_usd,
                "max_weekly_loss_usd": self.config.max_weekly_loss_usd,
                "max_drawdown_pct": self.config.max_drawdown_pct,
                "max_trades_per_hour": self.config.max_trades_per_hour,
                "max_trades_per_day": self.config.max_trades_per_day,
                "default_stop_loss_pct": self.config.default_stop_loss_pct,
                "default_take_profit_pct": self.config.default_take_profit_pct,
                "trailing_stop_pct": self.config.trailing_stop_pct,
            },
        }


    # ── 新增风控检查 ─────────────────────────────────────

    def _check_market_regime(self, action: str) -> RiskCheckResult:
        """BTC 大盘检测：10 分钟跌 > 3% 时 block 买入"""
        if action != "buy":
            return RiskCheckResult.ok()
        try:
            from price_feed import price_feed
            btc_price = price_feed.get_major_price("BTC")
            if not btc_price:
                return RiskCheckResult.ok()

            # 采样 BTC 价格
            import time
            now = time.time()
            if not hasattr(self, "_btc_samples"):
                self._btc_samples = []
            self._btc_samples.append((now, btc_price))
            # 保留 10 分钟内的采样
            self._btc_samples = [(t, p) for t, p in self._btc_samples if now - t < 600]

            if len(self._btc_samples) < 2:
                return RiskCheckResult.ok()

            oldest_price = self._btc_samples[0][1]
            if oldest_price <= 0:
                return RiskCheckResult.ok()

            change_pct = (btc_price - oldest_price) / oldest_price
            if change_pct < -0.03:
                return RiskCheckResult.block(
                    f"BTC 10min 跌 {change_pct*100:.1f}%，暂停买入"
                )
            if change_pct < -0.015:
                return RiskCheckResult(
                    passed=True,
                    reason=f"BTC 10min 跌 {change_pct*100:.1f}%，建议减仓",
                    risk_level="medium",
                )
        except Exception:
            pass
        return RiskCheckResult.ok()

    def _check_chain_concentration(self, chain: str, action: str) -> RiskCheckResult:
        """同链持仓集中度检查：同一链 > 5 个持仓时警告"""
        if action != "buy":
            return RiskCheckResult.ok()
        same_chain = sum(
            1 for pos in self._open_positions.values()
            if pos.get("chain") == chain
        )
        if same_chain >= 5:
            return RiskCheckResult(
                passed=True,
                reason=f"{chain} 链已有 {same_chain} 个持仓，建议分散",
                risk_level="medium",
            )
        return RiskCheckResult.ok()


_risk_manager: Optional[RiskManager] = None


def get_risk_manager() -> RiskManager:
    """获取全局 RiskManager 单例"""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
    return _risk_manager
