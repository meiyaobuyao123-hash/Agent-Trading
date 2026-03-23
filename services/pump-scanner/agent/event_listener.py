"""
事件驱动策略评估 — 毫秒级响应

替代 30s 轮询，通过 EventBus 订阅数据事件，立即评估策略。
30s monitor_job 保留为 fallback。

事件源：
- data.hot_coin_update  ← hot_coin_manager（入榜/打分变动）
- data.pump_snapshot    ← collector（内盘快照）
- data.kol_signal       ← kol_job（KOL 信号）

去重：同一 (source, token_address) 5s 内不重复评估。
策略缓存：30s 刷新，不每次查 DB。

Python 3.9 兼容。
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from agent.schemas import DataEvent
from agent.evaluator import StrategyEvaluator
from agent.strategy_manager import StrategyManager
from agent.action_dispatcher import ActionDispatcher
from agent.event_bus import get_event_bus
from agent.memory import get_memory_manager

log = logging.getLogger(__name__)

# ── 配置 ─────────────────────────────────────────────
DEDUP_TTL_SEC = 5.0          # 同一 (source, token) 去重窗口
STRATEGY_CACHE_TTL = 30.0    # 策略缓存刷新间隔

# ── 全局实例 ─────────────────────────────────────────
_evaluator = StrategyEvaluator()
_strategy_mgr = StrategyManager()
_dispatcher = ActionDispatcher()

# 去重缓存: {(source, token_address): last_eval_time}
_dedup_cache: Dict[tuple, float] = {}

# 策略缓存: {source: (strategies_list, loaded_at)}
_strategy_cache: Dict[str, tuple] = {}

# 统计
_stats = {"event_driven": 0, "deduped": 0, "errors": 0}

# PRD-006: 缓存当前 regime
_cached_regime: Dict[str, str] = {"global": "RANGING", "chain": {}}


async def start_event_listener():
    """启动事件监听，订阅 EventBus 数据事件"""
    bus = get_event_bus()

    bus.subscribe("data.hot_coin_update", _on_hot_coin_event)
    bus.subscribe("data.pump_snapshot", _on_pump_event)
    bus.subscribe("data.kol_signal", _on_kol_event)
    bus.subscribe("data.hot_coin_update", _on_price_for_positions)

    # PRD-006: 订阅 regime_change 事件
    bus.subscribe("market.regime_change", _on_regime_change)

    log.info(
        "Agent EventListener 已启动: 订阅 hot_coin_update / pump_snapshot / kol_signal + 持仓监控 + regime_change"
    )


# ── PRD-006: Regime 注入 ─────────────────────────────

def _inject_regime(data: Dict[str, Any], chain: str = "solana"):
    """注入 regime 信息到 DataEvent 数据"""
    try:
        from agent.regime_detector import get_regime_detector
        detector = get_regime_detector()
        data["_market_regime"] = detector.get_regime()
        data["_chain_regime"] = detector.get_chain_regime(chain)
    except Exception:
        data["_market_regime"] = _cached_regime.get("global", "RANGING")
        data["_chain_regime"] = _cached_regime.get("chain", {}).get(chain, "RANGING")


async def _on_regime_change(event_data: Dict[str, Any]):
    """处理 regime 变化事件 — 更新缓存 + 写入短期记忆"""
    try:
        data = event_data.get("data", event_data)
        new_regime = data.get("new_regime", "")
        old_regime = data.get("old_regime", "")
        asset = data.get("asset", "")

        # 更新缓存
        if asset == "GLOBAL" or not asset:
            _cached_regime["global"] = new_regime
        else:
            _cached_regime["global"] = new_regime  # 简化：任何切换都更新

        # 写入短期记忆
        try:
            get_memory_manager().add_event({
                "type": "regime_change",
                "source": "regime_detector",
                "asset": asset,
                "old_regime": old_regime,
                "new_regime": new_regime,
                "confidence": data.get("confidence", 0),
                "summary": f"Regime {asset}: {old_regime} → {new_regime} (conf={data.get('confidence', 0):.2f})",
            })
        except Exception:
            pass

        log.info("[EventListener] Regime change: %s %s → %s", asset, old_regime, new_regime)
    except Exception as e:
        log.debug("[EventListener] regime_change error: %s", e)


# ── 事件处理器 ───────────────────────────────────────

async def _on_hot_coin_event(event_data: Dict[str, Any]):
    """热币数据变动 → 立即评估策略"""
    try:
        data = event_data.get("data", event_data)
        token_addr = data.get("address", "")
        if not token_addr:
            return

        if _is_deduped("hot_coins", token_addr):
            return

        # PRD-005: 写入短期记忆
        try:
            get_memory_manager().add_event({
                "type": "signal",
                "source": "hot_coin",
                "token": data.get("symbol", token_addr[:8]),
                "chain": data.get("chain", ""),
                "score": data.get("score", 0),
                "price": data.get("price_usd", 0),
                "summary": f"hot_coin {data.get('symbol', token_addr[:8])} score={data.get('score', 0)} ${data.get('price_usd', 0):.6f}",
            })
        except Exception:
            pass

        # PRD-006: 注入 regime 信息
        _inject_regime(data, chain=data.get("chain", "solana"))

        de = DataEvent(
            source="hot_coins",
            data=data,
            timestamp=data.get("entered_at") or "",
            chain=data.get("chain", ""),
            token_address=token_addr,
            token_name=data.get("name", data.get("symbol", "")),
        )
        count = await _process_event_driven([de], "hot_coins")
        if count > 0:
            log.info(
                f"[EventDriven] hot_coin {data.get('symbol', token_addr[:8])} "
                f"→ {count} strategies triggered"
            )
    except Exception as e:
        _stats["errors"] += 1
        log.debug(f"[EventDriven] hot_coin error: {e}")


async def _on_pump_event(event_data: Dict[str, Any]):
    """内盘快照 → 立即评估策略"""
    try:
        data = event_data.get("data", event_data)
        mint = data.get("mint", "")
        if not mint:
            return

        if _is_deduped("pump_tokens", mint):
            return

        # PRD-005: 写入短期记忆
        try:
            get_memory_manager().add_event({
                "type": "signal",
                "source": "pump",
                "token": data.get("symbol", mint[:8]),
                "chain": "solana",
                "score": data.get("score", 0),
                "bc_progress": data.get("bc_progress", 0),
                "summary": f"pump {data.get('symbol', mint[:8])} score={data.get('score', 0)} bc={data.get('bc_progress', 0):.1f}%",
            })
        except Exception:
            pass

        # PRD-006: 注入 regime 信息
        _inject_regime(data, chain="solana")

        de = DataEvent(
            source="pump_tokens",
            data=data,
            timestamp=data.get("snapshot_at") or "",
            chain="solana",
            token_address=mint,
            token_name=data.get("name", data.get("symbol", "")),
        )
        count = await _process_event_driven([de], "pump_tokens")
        if count > 0:
            log.info(
                f"[EventDriven] pump {data.get('symbol', mint[:8])} "
                f"→ {count} strategies triggered"
            )
    except Exception as e:
        _stats["errors"] += 1
        log.debug(f"[EventDriven] pump error: {e}")


async def _on_kol_event(event_data: Dict[str, Any]):
    """KOL 信号 → 立即评估策略"""
    try:
        data = event_data.get("data", event_data)
        token_addr = data.get("token_address", "")
        if not token_addr:
            return

        if _is_deduped("kol_signals", token_addr):
            return

        # PRD-005: 写入短期记忆
        try:
            get_memory_manager().add_event({
                "type": "signal",
                "source": "kol",
                "token": data.get("token_name", token_addr[:8]),
                "chain": data.get("chain", ""),
                "kol_count": data.get("kol_count", 0),
                "signal_strength": data.get("signal_strength", 0),
                "summary": f"kol {data.get('token_name', token_addr[:8])} kols={data.get('kol_count', 0)} strength={data.get('signal_strength', 0)}",
            })
        except Exception:
            pass

        # PRD-006: 注入 regime 信息
        _inject_regime(data, chain=data.get("chain", "solana"))

        de = DataEvent(
            source="kol_signals",
            data=data,
            timestamp=data.get("detected_at") or "",
            chain=data.get("chain", ""),
            token_address=token_addr,
            token_name=data.get("token_name", ""),
        )
        count = await _process_event_driven([de], "kol_signals")
        if count > 0:
            log.info(
                f"[EventDriven] kol {data.get('token_name', token_addr[:8])} "
                f"→ {count} strategies triggered"
            )
    except Exception as e:
        _stats["errors"] += 1
        log.debug(f"[EventDriven] kol error: {e}")


# ── 核心评估（复用 monitor_job 逻辑）───────────────

async def _process_event_driven(
    events: List[DataEvent], source: str
) -> int:
    """事件驱动版策略评估"""
    if not events:
        return 0

    strategies = _get_cached_strategies(source)
    if not strategies:
        return 0

    triggered_count = 0
    for event in events:
        triggered = _evaluator.evaluate(event, strategies)
        for trigger_event in triggered:
            if not _strategy_mgr.check_daily_limit(trigger_event.strategy_id):
                continue

            strategy = _strategy_mgr.get_strategy(trigger_event.strategy_id)
            if not strategy:
                continue

            actions = strategy.get("actions", [])
            await _dispatcher.dispatch(trigger_event, actions)
            _strategy_mgr.record_trigger(trigger_event.strategy_id)

            await get_event_bus().publish("strategy.triggered", {
                "strategy_id": trigger_event.strategy_id,
                "user_id": trigger_event.user_id,
                "strategy_name": trigger_event.strategy_name,
                "token": trigger_event.matched_token,
                "chain": trigger_event.matched_chain,
                "trigger_source": "event_driven",
            })
            triggered_count += 1

    _stats["event_driven"] += triggered_count
    return triggered_count


# ── 辅助 ─────────────────────────────────────────────

def _is_deduped(source: str, token_address: str) -> bool:
    """去重检查：同一 (source, token) 在 TTL 内不重复评估"""
    now = time.time()
    key = (source, token_address.lower())
    last = _dedup_cache.get(key, 0)
    if now - last < DEDUP_TTL_SEC:
        _stats["deduped"] += 1
        return True
    _dedup_cache[key] = now

    # 清理过期条目（每 100 次检查一次）
    if len(_dedup_cache) > 1000:
        cutoff = now - DEDUP_TTL_SEC * 2
        expired = [k for k, v in _dedup_cache.items() if v < cutoff]
        for k in expired:
            del _dedup_cache[k]

    return False


def _get_cached_strategies(source: str) -> list:
    """带缓存的策略加载"""
    now = time.time()
    cached = _strategy_cache.get(source)
    if cached and (now - cached[1]) < STRATEGY_CACHE_TTL:
        return cached[0]

    strategies = _strategy_mgr.get_active_strategies(data_source=source)
    _strategy_cache[source] = (strategies, now)
    return strategies


async def _on_price_for_positions(event_data: Dict[str, Any]):
    """价格变动 → 检查持仓止盈止损"""
    try:
        data = event_data.get("data", event_data)
        token_addr = data.get("address", "")
        chain = data.get("chain", "")
        price = float(data.get("price_usd") or 0)
        if not token_addr or price <= 0:
            return

        from agent.position_monitor import get_position_monitor
        monitor = get_position_monitor()
        await monitor.check_all({f"{chain}:{token_addr}": price, token_addr: price})
    except Exception as e:
        log.debug(f"[PositionMonitor] price event error: {e}")


def get_event_listener_stats() -> dict:
    """获取统计信息"""
    return dict(_stats)
