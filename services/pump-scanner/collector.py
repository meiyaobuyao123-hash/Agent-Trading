"""
数据采集层 — 三阶段架构

阶段1: WS 全量捕获 → 零延迟直接写 DB（pump_tokens），不丢弃任何币
阶段2: WS trade 订阅 → 内存追踪活跃交易，累积买家/进度数据
阶段3: 按需 enrich → 初筛通过（buyers>=3 且 bc>=2%）后才拉 REST 详情
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Set

import aiohttp
import websockets

from config import (
    PUMPPORTAL_WS, PUMP_REST,
    ENRICH_DELAY_S, SNAPSHOT_INTERVAL_S,
    MAX_TRADE_TRACKED, TRADE_EVICT_AGE_H, TRADE_DEAD_AGE_H,
    ENRICH_MIN_BUYERS, ENRICH_MIN_BC_PCT,
    ENRICH_CONCURRENCY, ENRICH_COOLDOWN_S,
    BC_MIN_PCT, BC_MAX_PCT,
)
from features import TokenFeatures, extract_features, hard_filter, to_snapshot_dict, calc_bc_progress
from scorer import score
from database import (
    upsert_token, insert_snapshot, insert_trade,
    get_active_tokens, mark_graduated, get_smart_wallet_tiers,
)
import pump_stats
import push_service

# ── 实时信号池配置 ──
SIGNAL_MIN_SCORE     = 55       # 进入信号池最低分
SIGNAL_DEAD_NO_TRADE = 1800     # 30min 无交易 → 移出信号池
SIGNAL_MAX_AGE_H     = 3        # 超过3小时 → 移出信号池

log = logging.getLogger(__name__)


class PumpScanner:
    def __init__(self):
        # ── 阶段1：全量捕获 ──
        # 只记录已见过的 mint（去重用），不存详情
        self._seen_mints: Set[str] = set()

        # ── 阶段2：交易追踪（内存）──
        # mint → 轻量 token_info（WS 字段 + _created_at）
        self._tokens: Dict[str, dict] = {}
        # mint → 交易列表
        self._trades: Dict[str, list] = {}

        # ── 阶段3：按需 enrich ──
        # 已完成 enrich 的 mint 集合（避免重复拉取）
        self._enriched: Set[str] = set()
        # enrich 并发信号量
        self._enrich_sem: asyncio.Semaphore = asyncio.Semaphore(ENRICH_CONCURRENCY)
        # enrich 队列
        self._enrich_queue: asyncio.Queue = asyncio.Queue()

        # ── WS 订阅管理 ──
        self._subscribe_queue: asyncio.Queue = asyncio.Queue()
        self._subscribed: Set[str] = set()
        self._ws_trade: Optional[websockets.WebSocketClientProtocol] = None

        # ── 聪明钱分层 ──
        self._smart_wallet_tiers: dict = {}

        # ── 实时推送去重 ──
        self._pushed: Set[tuple] = set()

        # ── 实时信号池（内存）──
        # mint → {mint, symbol, name, score, recommendation, bc_progress,
        #         market_cap_sol, score_detail, image_uri, twitter, telegram, website,
        #         unique_buyers, age_minutes, entered_at, last_trade_at}
        self._signal_pool: Dict[str, dict] = {}

        # ── 最近退池信号（供 API 空池时回退展示"近期信号回顾"）──
        from collections import deque
        self._recent_signals: deque = deque(maxlen=100)

    # ──────────────────────────────────────────────────
    # 实时信号池 — 供 API 读取
    # ──────────────────────────────────────────────────
    def _archive_signal(self, mint: str, reason: str) -> None:
        """退池时记录到 _recent_signals，供空池回退展示"""
        sig = self._signal_pool.get(mint)
        if not sig:
            return
        now = datetime.now(timezone.utc)
        entered = sig.get("entered_at", now)
        self._recent_signals.append({
            "mint": sig.get("mint", mint),
            "symbol": sig.get("symbol", ""),
            "name": sig.get("name", ""),
            "score": sig.get("score", 0),
            "recommendation": sig.get("recommendation", ""),
            "bc_progress": sig.get("bc_progress", 0),
            "market_cap_sol": sig.get("market_cap_sol", 0),
            "unique_buyers": sig.get("unique_buyers", 0),
            "image_uri": sig.get("image_uri", ""),
            "twitter": sig.get("twitter"),
            "telegram": sig.get("telegram"),
            "website": sig.get("website"),
            "entered_at": entered.isoformat() if isinstance(entered, datetime) else str(entered),
            "last_trade_at": (sig.get("last_trade_at") or entered).isoformat()
                if isinstance(sig.get("last_trade_at", entered), datetime)
                else str(sig.get("last_trade_at", entered)),
            "exited_at": now.isoformat(),
            "exit_reason": reason,
            "age_minutes": round((now - entered).total_seconds() / 60, 1)
                if isinstance(entered, datetime) else 0,
            "is_history": True,
        })

    def get_signals(self) -> list:
        """返回当前信号池快照（按分数降序）。
        空池时回退展示最近 1h 退池信号（is_history=True）。
        """
        now = datetime.now(timezone.utc)
        signals = []
        for mint, sig in list(self._signal_pool.items()):
            # 再次检查是否过期
            entered = sig.get("entered_at", now)
            age_h = (now - entered).total_seconds() / 3600
            if age_h > SIGNAL_MAX_AGE_H:
                self._archive_signal(mint, "timeout")
                self._signal_pool.pop(mint, None)
                continue
            # 检查是否死币（30min 无交易）
            last_trade = sig.get("last_trade_at", entered)
            if (now - last_trade).total_seconds() > SIGNAL_DEAD_NO_TRADE:
                self._archive_signal(mint, "no_trade")
                self._signal_pool.pop(mint, None)
                continue
            signals.append({
                **sig,
                "entered_at": sig["entered_at"].isoformat(),
                "last_trade_at": (sig.get("last_trade_at") or sig["entered_at"]).isoformat(),
                "age_minutes": round((now - entered).total_seconds() / 60, 1),
            })
        signals.sort(key=lambda x: x.get("score", 0), reverse=True)

        if signals:
            return signals

        # ── 空池回退：最近 1h 退池信号 ──
        cutoff = (now - timedelta(hours=1)).isoformat()
        history = []
        for sig in reversed(self._recent_signals):
            exited = sig.get("exited_at", "")
            if exited and exited >= cutoff:
                history.append(sig)
            if len(history) >= 20:
                break
        return history

    # ──────────────────────────────────────────────────
    # 主入口
    # ──────────────────────────────────────────────────
    async def run(self):
        log.info("PumpScanner 启动（三阶段架构）")
        await self._reload_smart_wallets()
        await asyncio.gather(
            self._listen_new_tokens(),       # 阶段1：全量捕获
            self._listen_trades(),           # 阶段2：交易追踪
            self._enrich_worker(),           # 阶段3：按需 enrich
            self._snapshot_loop(),           # 定时评估
            self._smart_wallet_reload_loop(),
        )

    # ──────────────────────────────────────────────────
    # 聪明钱分层加载
    # ──────────────────────────────────────────────────
    async def _reload_smart_wallets(self):
        try:
            tiers = get_smart_wallet_tiers()
            self._smart_wallet_tiers = tiers
            counts = {"elite": 0, "verified": 0, "watching": 0}
            for t in tiers.values():
                if t in counts:
                    counts[t] += 1
            log.info(
                f"聪明钱库已加载: 精英={counts['elite']} "
                f"验证={counts['verified']} 观察={counts['watching']}"
            )
        except Exception as e:
            log.warning(f"加载聪明钱数据失败: {e}")

    async def _smart_wallet_reload_loop(self):
        RELOAD_INTERVAL_S = 30 * 60
        while True:
            await asyncio.sleep(RELOAD_INTERVAL_S)
            await self._reload_smart_wallets()

    # ──────────────────────────────────────────────────
    # 阶段1：WS 全量捕获（零延迟，不丢弃）
    # ──────────────────────────────────────────────────
    async def _listen_new_tokens(self):
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(
                    PUMPPORTAL_WS,
                    ping_interval=30,
                    ping_timeout=15,
                    close_timeout=5,
                ) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    log.info("已订阅 newToken 事件")
                    backoff = 1.0
                    # 读消息超时 15s：pumpportal 高峰每秒多条 create，
                    # 15s 无消息基本是僵死连接，更短的超时能缩小数据丢失窗口
                    # 抛异常让外层 except 统一处理（计数、退避、日志同一路径）
                    while True:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
                        except asyncio.TimeoutError:
                            raise ConnectionError("newToken WS 15s 无消息，判定僵死")
                        await self._on_new_token(json.loads(raw))
            except Exception as e:
                pump_stats.incr("ws_new_reconnects")
                # 指数退避：1 → 2 → 4 → 8 → max 15s，减小首次断开丢数据
                log.warning(f"newToken WS 断开，{backoff:.1f}s 后重连: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 15)

    async def _on_new_token(self, evt: dict):
        if evt.get("txType") != "create":
            return

        mint = evt.get("mint", "")
        if not mint or mint in self._seen_mints:
            return

        # 全量计数（漏斗第一层）
        pump_stats.incr("ws_creates")
        self._seen_mints.add(mint)

        created_at = datetime.now(timezone.utc)

        # ── 阶段1核心：立即写 DB，不等 REST，不 sleep ──
        upsert_token({
            "mint":             mint,
            "name":             evt.get("name", ""),
            "symbol":           evt.get("symbol", ""),
            "description":      "",
            "image_uri":        evt.get("uri", ""),
            "creator":          evt.get("traderPublicKey", ""),
            "created_at":       created_at.isoformat(),
            "twitter":          None,
            "telegram":         None,
            "website":          None,
            "complete":         False,
            "initial_buy_sol":  evt.get("solAmount", 0),
            "initial_mc_sol":   evt.get("marketCapSol", 0),
        })

        # ── 阶段2：加入内存交易追踪（有容量保护但远大于旧上限）──
        if len(self._tokens) < MAX_TRADE_TRACKED:
            self._tokens[mint] = {
                "mint": mint,
                "name": evt.get("name", ""),
                "symbol": evt.get("symbol", ""),
                "creator": evt.get("traderPublicKey", ""),
                "vSolInBondingCurve": evt.get("vSolInBondingCurve", 0),
                "marketCapSol": evt.get("marketCapSol", 0),
                "initialBuy": evt.get("initialBuy", 0),
                "_created_at": created_at,
            }
            self._trades[mint] = []
            # 订阅交易
            await self._subscribe_queue.put(mint)
        else:
            pump_stats.incr("trade_track_full")

        log.debug(f"新币: {evt.get('name','?')} ({mint[:8]}…) 追踪={len(self._tokens)}")

    # ──────────────────────────────────────────────────
    # 阶段2：WS 交易监听
    # ──────────────────────────────────────────────────
    async def _listen_trades(self):
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(
                    PUMPPORTAL_WS,
                    ping_interval=30,
                    ping_timeout=15,
                    close_timeout=5,
                    max_size=2**20,
                ) as ws:
                    self._ws_trade = ws
                    log.info("交易 WS 已连接")
                    backoff = 1.0
                    await asyncio.gather(
                        self._process_subscribe_queue(ws),
                        self._recv_trades(ws),
                    )
            except Exception as e:
                pump_stats.incr("ws_trade_reconnects")
                # 指数退避：1 → 2 → 4 → 8 → max 15s
                log.warning(f"trade WS 断开，{backoff:.1f}s 后重连: {e}")
                self._ws_trade = None
                self._subscribed.clear()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 15)

    async def _process_subscribe_queue(self, ws):
        while True:
            mint = await self._subscribe_queue.get()
            if mint not in self._subscribed:
                await ws.send(json.dumps({
                    "method": "subscribeTokenTrade",
                    "keys": [mint],
                }))
                self._subscribed.add(mint)

    async def _recv_trades(self, ws):
        # 60s 无消息 → 判定僵死连接，抛异常触发外层 reconnect
        # trade WS 只推订阅代币的交易，阈值比 newToken 宽松
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=60.0)
            except asyncio.TimeoutError:
                raise ConnectionError("trade WS 60s 无消息，判定僵死")
            evt = json.loads(raw)
            await self._on_trade(evt)

    async def _on_trade(self, evt: dict):
        mint = evt.get("mint", "")
        tx_type = evt.get("txType", "")

        if tx_type not in ("buy", "sell") or mint not in self._tokens:
            return

        now = datetime.now(timezone.utc)

        bc_at_buy = None
        if tx_type == "buy":
            cur_v_sol = float(
                evt.get("vSolInBondingCurve")
                or self._tokens[mint].get("vSolInBondingCurve", 0)
            )
            bc_at_buy = calc_bc_progress(cur_v_sol)

        trade = {
            "mint":        mint,
            "tx_sig":      evt.get("signature"),
            "trader":      evt.get("traderPublicKey", ""),
            "tx_type":     tx_type,
            "sol_amount":  float(evt.get("solAmount", 0)),
            "token_amount": float(evt.get("tokenAmount", 0)),
            "traded_at":   now,
            "bc_progress": bc_at_buy,
        }

        self._trades[mint].append(trade)
        # 只存信号池代币 + 毕业代币的交易到 DB（节省 Supabase 存储 95%+）
        # 内存追踪（self._trades）仍然覆盖全部代币
        token_info = self._tokens.get(mint, {})
        is_in_signal_pool = mint in self._signal_pool
        is_graduated = token_info.get("complete", False)
        if is_in_signal_pool or is_graduated:
            insert_trade({**trade, "traded_at": now.isoformat()})

        # ── 聪明钱入场检测 ──
        if tx_type == "buy":
            trader = evt.get("traderPublicKey", "")
            wallet_tier = self._smart_wallet_tiers.get(trader)
            if wallet_tier and (mint, "smart_money") not in self._pushed:
                sol_amount = float(evt.get("solAmount", 0))
                if sol_amount >= 1.0:
                    symbol = self._tokens[mint].get("symbol", mint[:8])
                    bc_now = bc_at_buy or 0.0
                    asyncio.ensure_future(
                        push_service.push_smart_money(
                            mint=mint,
                            symbol=symbol,
                            wallet_tier=wallet_tier,
                            net_sol=sol_amount,
                            bc_progress=bc_now,
                        )
                    )
                    self._pushed.add((mint, "smart_money"))
                    log.info(
                        f"[推送] 聪明钱入场: {symbol} tier={wallet_tier} "
                        f"sol={sol_amount:.2f}"
                    )

        # 更新 vSol
        v_sol = evt.get("vSolInBondingCurve")
        if v_sol is not None:
            self._tokens[mint]["vSolInBondingCurve"] = float(v_sol)
            self._tokens[mint]["marketCapSol"] = float(evt.get("marketCapSol", 0))

            progress = calc_bc_progress(float(v_sol))
            if progress >= 100:
                mark_graduated(mint, now.isoformat())
                symbol = self._tokens[mint].get("symbol", mint[:8])
                log.info(f"🎓 毕业: {symbol} ({mint[:8]}…)")
                # 毕业 → 移出信号池
                if mint in self._signal_pool:
                    self._archive_signal(mint, "graduated")
                    self._signal_pool.pop(mint, None)
                    pump_stats.incr("signal_exited")

                if (mint, "graduated") not in self._pushed:
                    asyncio.ensure_future(
                        push_service.push_graduated(mint=mint, symbol=symbol)
                    )
                    self._pushed.add((mint, "graduated"))

                self._tokens.pop(mint, None)
                self._trades.pop(mint, None)

    # ──────────────────────────────────────────────────
    # 阶段3：按需 enrich 工作池
    # ──────────────────────────────────────────────────
    async def _enrich_worker(self):
        """持续消费 enrich 队列，并发拉取 REST 详情"""
        while True:
            mint = await self._enrich_queue.get()
            if mint in self._enriched:
                continue
            asyncio.ensure_future(self._do_enrich(mint))

    async def _do_enrich(self, mint: str):
        """单个代币的 REST enrich"""
        async with self._enrich_sem:
            await asyncio.sleep(ENRICH_DELAY_S)
            detail = await self._fetch_token_detail(mint)

            if detail:
                pump_stats.incr("enrich_success")
                self._enriched.add(mint)

                # 合并 REST 详情到内存（代币可能已被淘汰，但 DB 更新仍有价值）
                token = self._tokens.get(mint)
                if token:
                    token["name"] = detail.get("name") or token.get("name", "")
                    token["symbol"] = detail.get("symbol") or token.get("symbol", "")
                    token["twitter"] = detail.get("twitter")
                    token["telegram"] = detail.get("telegram")
                    token["website"] = detail.get("website")
                    token["description"] = detail.get("description")
                    token["image_uri"] = detail.get("image_uri")
                    token["creator"] = detail.get("creator") or token.get("creator", "")
                    # 用 REST 的 created_timestamp 修正创建时间
                    ts = detail.get("created_timestamp")
                    if ts:
                        token["_created_at"] = datetime.fromtimestamp(
                            ts / 1000, tz=timezone.utc
                        )

                # 同步更新 DB（补全 social 等字段）
                created_at = None
                ts = detail.get("created_timestamp")
                if ts:
                    created_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()

                upsert_token({
                    "mint":        mint,
                    "name":        detail.get("name"),
                    "symbol":      detail.get("symbol"),
                    "description": detail.get("description"),
                    "image_uri":   detail.get("image_uri"),
                    "creator":     detail.get("creator", ""),
                    "twitter":     detail.get("twitter"),
                    "telegram":    detail.get("telegram"),
                    "website":     detail.get("website"),
                    **({"created_at": created_at} if created_at else {}),
                })

                log.debug(f"[enrich] 成功: {detail.get('symbol','?')} ({mint[:8]}…)")
            else:
                pump_stats.incr("enrich_fail")
                log.debug(f"[enrich] 失败: {mint[:8]}…")

            await asyncio.sleep(ENRICH_COOLDOWN_S)

    # ──────────────────────────────────────────────────
    # 定时快照循环（每分钟）
    # ──────────────────────────────────────────────────
    async def _snapshot_loop(self):
        while True:
            await asyncio.sleep(SNAPSHOT_INTERVAL_S)
            await self._take_snapshots()

    async def _take_snapshots(self):
        if not self._tokens:
            return

        now = datetime.now(timezone.utc)
        evicted = 0

        for mint, token_info in list(self._tokens.items()):
            created_at = token_info.get("_created_at", now)
            age_hours = (now - created_at).total_seconds() / 3600
            trades = self._trades.get(mint, [])

            # ── 淘汰：超过 N 小时未毕业 ──
            if age_hours > TRADE_EVICT_AGE_H:
                self._tokens.pop(mint, None)
                self._trades.pop(mint, None)
                if mint in self._signal_pool:
                    self._archive_signal(mint, "timeout")
                    self._signal_pool.pop(mint, None)
                    pump_stats.incr("signal_exited")
                evicted += 1
                continue

            # ── 淘汰：超过 N 小时且30min无交易或零交易 → 死币 ──
            if age_hours > TRADE_DEAD_AGE_H:
                should_evict = False
                if not trades:
                    # 无任何交易，超时直接淘汰
                    should_evict = True
                else:
                    last_trade_time = max(
                        t.get("traded_at", created_at) if isinstance(t.get("traded_at"), datetime)
                        else created_at
                        for t in trades
                    )
                    if (now - last_trade_time).total_seconds() > 1800:
                        should_evict = True
                if should_evict:
                    self._tokens.pop(mint, None)
                    self._trades.pop(mint, None)
                    if mint in self._signal_pool:
                        self._archive_signal(mint, "no_trade")
                        self._signal_pool.pop(mint, None)
                        pump_stats.incr("signal_exited")
                    evicted += 1
                    continue

            # ── 阶段3触发：初筛通过 → 加入 enrich 队列 ──
            unique_buyers = len({t["trader"] for t in trades if t["tx_type"] == "buy"})
            v_sol = float(token_info.get("vSolInBondingCurve", 0))
            bc_progress = calc_bc_progress(v_sol)

            if (
                mint not in self._enriched
                and unique_buyers >= ENRICH_MIN_BUYERS
                and bc_progress >= ENRICH_MIN_BC_PCT
            ):
                pump_stats.incr("enrich_triggered")
                await self._enrich_queue.put(mint)

            # ── 特征提取 + 评分（无论是否 enrich 完成）──
            f: TokenFeatures = extract_features(
                token_info=token_info,
                trades=trades,
                smart_wallet_tiers=self._smart_wallet_tiers,
                created_at=created_at,
            )

            passed, reason = hard_filter(f)
            if not passed:
                pump_stats.incr("hard_filter_fail")
                log.debug(
                    f"[过滤] {f.symbol}({mint[:6]}…) 被拒: {reason} "
                    f"(buyers={f.unique_buyers} ratio={f.buy_sell_ratio_count:.2f} "
                    f"bc={f.bc_progress:.1f}%)"
                )
                continue

            pump_stats.incr("hard_filter_pass")
            snap = to_snapshot_dict(f, f.age_minutes)
            insert_snapshot(snap)
            pump_stats.incr("snapshots_written")

            result = score(f)
            log.debug(
                f"{f.symbol}({mint[:6]}…) BC={f.bc_progress:.1f}% "
                f"分={result.total} [{result.recommendation}]"
            )

            # 事件驱动：通知 Agent 策略评估（bc >= 3% 且过了硬过滤的）
            if bc_progress >= 3:
                try:
                    from agent.event_bus import get_event_bus
                    await get_event_bus().publish("data.pump_snapshot", {
                        "mint": mint,
                        "symbol": f.symbol,
                        "name": f.name,
                        "score": result.total,
                        "recommendation": result.recommendation,
                        "bc_progress": bc_progress,
                        "market_cap_sol": f.market_cap_sol,
                        "unique_buyers": f.unique_buyers,
                        "buy_sell_ratio": f.buy_sell_ratio_count,
                        "smart_money_count": f.smart_money_buy_count,
                        "dev_sold_pct": f.dev_sold_pct,
                        "snapshot_at": now.isoformat(),
                    })
                except Exception:
                    pass

            # ── 实时信号池维护 ──
            in_bc_window = BC_MIN_PCT <= f.bc_progress <= BC_MAX_PCT
            if result.total >= SIGNAL_MIN_SCORE and in_bc_window and result.recommendation != "skip":
                last_trade_at = now
                if trades:
                    last_t = max(
                        (t.get("traded_at", now) if isinstance(t.get("traded_at"), datetime) else now)
                        for t in trades
                    )
                    last_trade_at = last_t

                if mint not in self._signal_pool:
                    self._signal_pool[mint] = {
                        "mint": mint,
                        "symbol": f.symbol,
                        "name": f.name,
                        "entered_at": now,
                    }
                    pump_stats.incr("signal_entered")
                    # 模拟盘：信号池入池触发买入
                    # pump.fun 代币 total supply 固定 10 亿（如果 f 没有这个字段用默认值）
                    try:
                        from hot_sim_trader import get_sim_trader
                        from price_feed import price_feed
                        _sol_usd = price_feed.get_major_price("SOL") or 150
                        _mc_usd = (f.market_cap_sol or 0) * _sol_usd
                        # pump.fun 代币 supply 固定 1_000_000_000
                        _supply = getattr(f, 'total_supply', None)
                        if _supply is None or _supply <= 0:
                            _supply = 1_000_000_000
                        _price = _mc_usd / _supply if _supply > 0 else 0
                        # pump.fun 代币 supply=10亿，BC 3-35% 对应 MC $5K-$25K，
                        # price $0.000005-$0.000025。原 $0.0001 门槛 = 要求 MC >= $100K
                        # （pump.fun 毕业都才 $68K）→ 所有内盘代币永远触发不了。
                        # 改成 price > 0（bc_progress 3-35% 已做了活跃过滤）
                        if _price > 0:
                            get_sim_trader().on_token_enter(
                                address=mint, chain="solana", symbol=f.symbol,
                                price=_price, score=result.total, source="pump")
                            log.info("[pump sim] %s 入池触发买入 price=$%.8f mc=$%.0f",
                                     f.symbol, _price, _mc_usd)
                        else:
                            log.info("[pump sim] %s 价格为 0 跳过 mc_sol=%s",
                                     f.symbol, f.market_cap_sol)
                    except Exception as e:
                        log.warning("[pump sim] 触发失败 %s: %s", f.symbol, e)
                    log.info(
                        f"[信号池+] {f.symbol}({mint[:6]}…) "
                        f"score={result.total:.0f} bc={f.bc_progress:.1f}%"
                    )
                # 更新实时数据
                self._signal_pool[mint].update({
                    "score": round(result.total, 1),
                    "recommendation": result.recommendation,
                    "bc_progress": round(f.bc_progress, 1),
                    "market_cap_sol": round(f.market_cap_sol, 2),
                    "score_detail": result.detail,
                    "unique_buyers": f.unique_buyers,
                    "image_uri": token_info.get("image_uri"),
                    "twitter": token_info.get("twitter"),
                    "telegram": token_info.get("telegram"),
                    "website": token_info.get("website"),
                    "last_trade_at": last_trade_at,
                })
            else:
                # 不再满足条件 → 移出信号池
                if mint in self._signal_pool:
                    exit_reason = "bc_out" if not in_bc_window else "low_score"
                    log.info(
                        f"[信号池-] {f.symbol}({mint[:6]}…) "
                        f"score={result.total:.0f} bc={f.bc_progress:.1f}% "
                        f"reason={exit_reason}"
                    )
                    self._archive_signal(mint, exit_reason)
                    pump_stats.incr("signal_exited")
                    self._signal_pool.pop(mint, None)

            # ── 实时推送检测 ──

            # 1. 高分新币推送
            if result.total >= 70 and (mint, "high_score") not in self._pushed:
                asyncio.ensure_future(
                    push_service.push_high_score(
                        mint=mint,
                        symbol=f.symbol,
                        score=result.total,
                        bc_progress=f.bc_progress,
                    )
                )
                self._pushed.add((mint, "high_score"))
                log.info(
                    f"[推送] 高分新币: {f.symbol} score={result.total:.0f} "
                    f"bc={f.bc_progress:.0f}%"
                )

            # 2. BC 里程碑推送
            for milestone in (30, 60):
                key = (mint, f"bc_{milestone}")
                if f.bc_progress >= milestone and key not in self._pushed:
                    asyncio.ensure_future(
                        push_service.push_bc_milestone(
                            mint=mint,
                            symbol=f.symbol,
                            milestone=milestone,
                            bc_progress=f.bc_progress,
                        )
                    )
                    self._pushed.add(key)
                    log.info(
                        f"[推送] BC 里程碑: {f.symbol} milestone={milestone}% "
                        f"bc={f.bc_progress:.0f}%"
                    )

        if evicted > 0:
            log.info(f"淘汰 {evicted} 个过期代币，当前追踪 {len(self._tokens)} 个")

    # ──────────────────────────────────────────────────
    # REST 工具方法
    # ──────────────────────────────────────────────────
    async def _fetch_token_detail(self, mint: str) -> Optional[dict]:
        urls = [
            f"{PUMP_REST}/coins/{mint}",
            f"https://frontend-api-v3.pump.fun/coins/{mint}",
            f"https://frontend-api.pump.fun/coins/{mint}",
        ]
        seen = set()
        unique_urls = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        for url in unique_urls:
            for attempt in range(2):
                try:
                    async with aiohttp.ClientSession() as s:
                        async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                            if r.status == 200:
                                return await r.json()
                            elif r.status == 429:
                                await asyncio.sleep(2)
                                continue
                except Exception as e:
                    if attempt == 0:
                        await asyncio.sleep(1)
                        continue
                    log.debug(f"fetch_token_detail {mint[:8]} {url[:30]}…: {e}")
                break

        log.warning(f"fetch_token_detail {mint[:8]} 全部失败")
        return None
