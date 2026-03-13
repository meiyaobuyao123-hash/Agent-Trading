"""
数据采集层

两路并行：
  1. PumpPortal WebSocket → 实时新币 + 交易事件
  2. pump.fun REST API   → 补全代币详情（social links 等）
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

import aiohttp
import websockets

from config import (
    PUMPPORTAL_WS, PUMP_REST, HELIUS_API_KEY,
    ENRICH_DELAY_S, MAX_TRACKED_TOKENS, SNAPSHOT_INTERVAL_S,
)
from features import TokenFeatures, extract_features, hard_filter, to_snapshot_dict, calc_bc_progress
from scorer import score
from database import (
    upsert_token, insert_snapshot, insert_trade,
    get_active_tokens, mark_graduated, get_smart_wallet_tiers,
)
import pump_stats

log = logging.getLogger(__name__)


class PumpScanner:
    def __init__(self):
        # mint → 原始 token_info dict
        self._tokens: Dict[str, dict] = {}
        # mint → 交易列表
        self._trades: Dict[str, list] = {}
        # 待订阅交易的 mint 队列
        self._subscribe_queue: asyncio.Queue = asyncio.Queue()
        # 聪明钱分层字典（从 DB 定期加载）wallet → 'elite'|'verified'|'watching'
        self._smart_wallet_tiers: dict = {}
        # 当前订阅的 mint 集合
        self._subscribed: set[str] = set()

        self._ws_trade: Optional[websockets.WebSocketClientProtocol] = None

    # ──────────────────────────────────────────────────
    # 主入口
    # ──────────────────────────────────────────────────
    async def run(self):
        log.info("PumpScanner 启动")
        # 启动时立即加载一次聪明钱数据
        await self._reload_smart_wallets()
        await asyncio.gather(
            self._listen_new_tokens(),
            self._listen_trades(),
            self._snapshot_loop(),
            self._smart_wallet_reload_loop(),
        )

    # ──────────────────────────────────────────────────
    # 聪明钱分层加载（每30分钟刷新一次）
    # ──────────────────────────────────────────────────
    async def _reload_smart_wallets(self):
        """从 DB 加载最新聪明钱分级数据"""
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
        """每30分钟刷新一次聪明钱分级"""
        RELOAD_INTERVAL_S = 30 * 60
        while True:
            await asyncio.sleep(RELOAD_INTERVAL_S)
            await self._reload_smart_wallets()

    # ──────────────────────────────────────────────────
    # WebSocket 1：监听新币创建
    # ──────────────────────────────────────────────────
    async def _listen_new_tokens(self):
        while True:
            try:
                async with websockets.connect(PUMPPORTAL_WS) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    log.info("已订阅 newToken 事件")
                    async for raw in ws:
                        await self._on_new_token(json.loads(raw))
            except Exception as e:
                pump_stats.incr("ws_new_reconnects")
                log.warning(f"newToken WS 断开，5s 后重连: {e}")
                await asyncio.sleep(5)

    async def _on_new_token(self, evt: dict):
        if evt.get("txType") != "create":
            return

        mint = evt.get("mint", "")
        if not mint or mint in self._tokens:
            return

        # 上限保护
        if len(self._tokens) >= MAX_TRACKED_TOKENS:
            return

        log.info(f"新币: {evt.get('name','?')} ({mint[:8]}…)")
        pump_stats.incr("ws_creates")

        # 等几秒让 REST API 数据就绪
        await asyncio.sleep(ENRICH_DELAY_S)

        # 拉取完整详情
        detail = await self._fetch_token_detail(mint)

        if detail:
            pump_stats.incr("rest_success")
            # REST 成功：合并 WebSocket 字段
            detail["vSolInBondingCurve"] = evt.get("vSolInBondingCurve", 0)
            detail["marketCapSol"]       = evt.get("marketCapSol", 0)
            detail["initialBuy"]         = evt.get("initialBuy", 0)

            created_at = datetime.fromtimestamp(
                detail.get("created_timestamp", 0) / 1000, tz=timezone.utc
            )

            self._tokens[mint] = {**detail, "_created_at": created_at}
            self._trades[mint] = []

            upsert_token({
                "mint":             mint,
                "name":             detail.get("name"),
                "symbol":           detail.get("symbol"),
                "description":      detail.get("description"),
                "image_uri":        detail.get("image_uri"),
                "creator":          detail.get("creator", ""),
                "created_at":       created_at.isoformat(),
                "twitter":          detail.get("twitter"),
                "telegram":         detail.get("telegram"),
                "website":          detail.get("website"),
                "complete":         detail.get("complete", False),
                "initial_buy_sol":  evt.get("solAmount", 0),
                "initial_mc_sol":   evt.get("marketCapSol", 0),
            })
        else:
            # REST 失败：用 WS 事件数据兜底入库 + 追踪
            pump_stats.incr("rest_fallback")
            log.info(f"  REST 失败，用 WS 数据兜底: {evt.get('name','?')} ({mint[:8]})")
            created_at = datetime.now(timezone.utc)

            ws_detail = {
                "mint": mint,
                "name": evt.get("name", ""),
                "symbol": evt.get("symbol", ""),
                "creator": evt.get("traderPublicKey", ""),
                "vSolInBondingCurve": evt.get("vSolInBondingCurve", 0),
                "marketCapSol": evt.get("marketCapSol", 0),
                "initialBuy": evt.get("initialBuy", 0),
            }

            self._tokens[mint] = {**ws_detail, "_created_at": created_at}
            self._trades[mint] = []

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

        # 通知 trade 监听器订阅该 mint
        await self._subscribe_queue.put(mint)

    # ──────────────────────────────────────────────────
    # WebSocket 2：监听交易事件
    # ──────────────────────────────────────────────────
    async def _listen_trades(self):
        while True:
            try:
                async with websockets.connect(PUMPPORTAL_WS) as ws:
                    self._ws_trade = ws
                    log.info("交易 WS 已连接")

                    # 处理待订阅队列 + 接收消息 并发
                    await asyncio.gather(
                        self._process_subscribe_queue(ws),
                        self._recv_trades(ws),
                    )
            except Exception as e:
                pump_stats.incr("ws_trade_reconnects")
                log.warning(f"trade WS 断开，5s 后重连: {e}")
                self._ws_trade = None
                self._subscribed.clear()
                await asyncio.sleep(5)

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
        async for raw in ws:
            evt = json.loads(raw)
            await self._on_trade(evt)

    async def _on_trade(self, evt: dict):
        mint = evt.get("mint", "")
        tx_type = evt.get("txType", "")

        if tx_type not in ("buy", "sell") or mint not in self._tokens:
            return

        now = datetime.now(timezone.utc)

        # 买入时记录当前BC进度（用于聪明钱入场时机分析）
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
            "bc_progress": bc_at_buy,   # 买单时的BC进度（列名与003 migration一致）
        }

        self._trades[mint].append(trade)
        insert_trade({**trade, "traded_at": now.isoformat()})

        # 更新 vSol（用于进度计算）
        v_sol = evt.get("vSolInBondingCurve")
        if v_sol is not None:
            self._tokens[mint]["vSolInBondingCurve"] = float(v_sol)
            self._tokens[mint]["marketCapSol"] = float(evt.get("marketCapSol", 0))

            # 检测毕业（进度 = 100%）
            progress = calc_bc_progress(float(v_sol))
            if progress >= 100:
                mark_graduated(mint, now.isoformat())
                log.info(f"🎓 毕业: {self._tokens[mint].get('symbol')} ({mint[:8]}…)")
                # 从追踪池移除
                self._tokens.pop(mint, None)
                self._trades.pop(mint, None)

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

        for mint, token_info in list(self._tokens.items()):
            trades = self._trades.get(mint, [])
            created_at = token_info.get("_created_at", datetime.now(timezone.utc))

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

    # ──────────────────────────────────────────────────
    # REST 工具方法
    # ──────────────────────────────────────────────────
    async def _fetch_token_detail(self, mint: str) -> Optional[dict]:
        """
        拉取代币详情，带重试 + DNS 容错。
        尝试顺序：默认 URL → 备用 URL → 最终用 WS 事件数据兜底。
        """
        urls = [
            f"{PUMP_REST}/coins/{mint}",
            f"https://frontend-api-v3.pump.fun/coins/{mint}",
            f"https://frontend-api.pump.fun/coins/{mint}",
        ]
        # 去重
        seen = set()
        unique_urls = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        for url in unique_urls:
            for attempt in range(2):  # 每个 URL 最多重试 1 次
                try:
                    async with aiohttp.ClientSession() as s:
                        async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                            if r.status == 200:
                                return await r.json()
                            elif r.status == 429:
                                await asyncio.sleep(2)  # 限速，等一下再试
                                continue
                except Exception as e:
                    if attempt == 0:
                        await asyncio.sleep(1)
                        continue
                    # 最后一次失败才 log
                    log.debug(f"fetch_token_detail {mint[:8]} {url[:30]}…: {e}")
                break  # 非限速错误不重试同一 URL

        log.warning(f"fetch_token_detail {mint[:8]} 全部失败")
        return None
