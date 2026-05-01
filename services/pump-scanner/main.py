"""
pump-scanner 入口

启动：
  pip install -r requirements.txt
  cp .env.example .env   # 填入 Supabase 密钥
  python main.py

调度任务（所有时间均 UTC）：
  01:00  创建者成功率更新（creator_stats_updater）
  02:00  热币日榜 Top20 生成（hot_coin_job）
  每1h   结果回填（outcome_labeler）
  每10m  热币增量扫描（hot_coin_job，增量模式 ~30s/轮）
  每5s   OKX 热币市场数据刷新+打分（hot_coin_job）
  每1s   推荐代币表现追踪（performance_tracker 常驻协程）
  每6h   聪明钱钱包更新（smart_wallet_updater）
  每30m  KOL 推文采集
  每30m  KOL 推文分析
  每1h   KOL 共振信号检测
  每24h  KOL 准确率评估
  每30s  Agent 策略监控

FastAPI API Server (port 8000):
  /api/agent/chat        POST  对话创建策略
  /api/agent/strategies  GET   策略列表
  /api/agent/alerts      GET   告警列表
  /docs                  GET   API 文档
"""

import asyncio
import logging
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from collector import PumpScanner
from outcome_labeler import run_outcome_labeler
from smart_wallet_updater import run_smart_wallet_updater
from smart_wallet_seed import initialize_smart_wallets
from creator_stats_updater import run_creator_stats_updater
from hot_coin_job import run_hot_coin_scan, run_hot_daily_picks, run_hot_price_refresh
from performance_tracker import run_performance_loop

# KOL 系统
from kol_job import (
    run_kol_collect,
    run_kol_analyze,
    run_kol_signal_detect,
    run_kol_accuracy_eval,
    initialize_kol_accounts,
)

# Agent 系统
from agent.monitor_job import run_agent_monitor
from agent.event_bus import get_event_bus

# 聪明钱多链追踪（实时：SOL WS ~400ms + EVM OKX 5s）
from smart_money_tracker import get_tracker

# ML 自动重训
from ml_trainer import auto_retrain_if_needed
from ml_config import ML_RETRAIN_INTERVAL_HOURS, USE_ML_SCORING

# 内盘数据报表
from pump_report_job import run_pump_report

# AI Optimizer Agent（每3天自动优化推荐算法）
from governor import run_governor

# 实时价格订阅（Binance WS + DexScreener WS）
from price_feed import price_feed

# 热币实时管理器（PriceFeed 回调 → 打分 → 进出榜单）
from hot_coin_manager import hot_coin_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

# 是否启动 FastAPI（通过环境变量控制）
ENABLE_API = os.getenv("ENABLE_API", "true").lower() == "true"
API_PORT = int(os.getenv("API_PORT", "8000"))


async def main():
    scanner = PumpScanner()

    # 注册全局引用，供 API 路由访问
    from scanner_ref import set_scanner
    set_scanner(scanner)
    scheduler = AsyncIOScheduler()

    # ══════════════════════════════════════════════════════════
    # 原有定时任务
    # ══════════════════════════════════════════════════════════

    # ── 创建者成功率更新（UTC 01:00）────────────────────────
    scheduler.add_job(
        run_creator_stats_updater,
        trigger=CronTrigger(hour=1, minute=0, timezone="UTC"),
        id="creator_stats",
        name="创建者成功率更新",
        misfire_grace_time=600,
    )

    # ── 结果回填（每1小时）──────────────────────────────────
    scheduler.add_job(
        run_outcome_labeler,
        trigger="interval",
        hours=1,
        id="outcome_labeler",
        name="结果回填器",
        misfire_grace_time=300,
    )

    # ── 聪明钱钱包更新（每6小时）────────────────────────────
    scheduler.add_job(
        run_smart_wallet_updater,
        trigger="interval",
        hours=2,
        id="smart_wallet",
        name="聪明钱v3评估",
        misfire_grace_time=600,
    )

    # ── 聪明钱地址挖掘（每天 UTC 04:00）───────────────────────
    from smart_wallet_miner import run_smart_wallet_miner
    scheduler.add_job(
        run_smart_wallet_miner,
        trigger="cron",
        hour=4, minute=0,
        id="smart_wallet_miner",
        name="聪明钱地址挖掘",
        misfire_grace_time=3600,
    )

    # ── 自有数据聪明钱挖掘（每 6h，从 smart_money_txns 发现活跃地址）─
    from txns_wallet_miner import run_txns_wallet_miner
    scheduler.add_job(
        run_txns_wallet_miner,
        trigger="interval",
        hours=6,
        id="txns_wallet_miner",
        name="自有数据聪明钱挖掘(6h)",
        misfire_grace_time=3600,
    )

    # ── Dune Analytics 聪明钱导入（已停用 2026-04-16：免费额度耗尽）──
    # 替代方案：DEX WS 全量 swap 事件 → 内存计数未知地址 → dex_address_stats
    # → txns_wallet_miner 每 6h 从 dex_address_stats 晋升 watching
    # from dune_wallet_importer import run_dune_wallet_import
    # scheduler.add_job(
    #     run_dune_wallet_import,
    #     trigger="cron",
    #     day="*/3",
    #     hour=5, minute=0,
    #     id="dune_wallet_import",
    #     name="Dune聪明钱导入(3天)",
    #     misfire_grace_time=7200,
    # )

    # ── 数据库清理（每 6 小时）─────────────────────────────
    from db_cleanup import run_db_cleanup
    scheduler.add_job(
        run_db_cleanup,
        trigger="interval",
        hours=6,
        id="db_cleanup",
        name="DB数据清理",
        misfire_grace_time=3600,
    )

    # ── 热币增量扫描（每10分钟）─────────────────────────────
    # 增量模式：已入库代币复用安全/社交数据，仅新代币走 GoPlus/Helius/DexScreener
    # 多时间帧 OKX toplist 发现，耗时 ~60-90s
    scheduler.add_job(
        run_hot_coin_scan,
        trigger="interval",
        minutes=10,
        id="hot_coin_scan",
        name="热币增量扫描",
        misfire_grace_time=120,
        max_instances=1,
    )

    # ── 市场数据刷新（每30秒）─────────────────────────────
    # DexScreener 批量按地址刷新（返回 5m/1h/6h/24h 完整多时间帧数据）
    # 单轮耗时：DexScreener 4链 ≈ 10-20s + 打分 ≈ 0.1s + DB写 ≈ 0.5s
    # max_instances=2 允许与 scan 并行，避免 scan 阻塞 refresh
    scheduler.add_job(
        run_hot_price_refresh,
        trigger="interval",
        seconds=30,
        id="hot_price_refresh",
        name="热币市场数据刷新",
        misfire_grace_time=15,
        max_instances=2,
    )

    # ── 热币日榜生成（每天 UTC 02:00）───────────────────────
    scheduler.add_job(
        run_hot_daily_picks,
        trigger=CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="hot_daily_picks",
        name="热币日榜 Top20",
        misfire_grace_time=600,
    )

    # ── 表现追踪（1秒常驻协程，不走 APScheduler）─────────────
    # 由 asyncio.create_task() 在 scheduler.start() 后启动
    # hot 代币: 直调 OKX API（1s循环）  pump 代币: pump.fun API
    # 内存缓存 daily_highs → 每 30s 批量落盘 DB

    # ══════════════════════════════════════════════════════════
    # KOL 系统定时任务
    # ══════════════════════════════════════════════════════════

    # ── KOL 推文采集（每30分钟）────────────────────────────
    scheduler.add_job(
        run_kol_collect,
        trigger="interval",
        minutes=30,
        id="kol_collect",
        name="KOL 推文采集",
        misfire_grace_time=300,
    )

    # ── KOL 推文分析（每30分钟）────────────────────────────
    scheduler.add_job(
        run_kol_analyze,
        trigger="interval",
        minutes=30,
        id="kol_analyze",
        name="KOL 推文分析",
        misfire_grace_time=300,
    )

    # ── KOL 共振信号检测（每1小时）─────────────────────────
    scheduler.add_job(
        run_kol_signal_detect,
        trigger="interval",
        hours=1,
        id="kol_signal_detect",
        name="KOL 共振信号检测",
        misfire_grace_time=300,
    )

    # ── KOL 准确率评估（每天 UTC 03:00）────────────────────
    scheduler.add_job(
        run_kol_accuracy_eval,
        trigger=CronTrigger(hour=3, minute=0, timezone="UTC"),
        id="kol_accuracy_eval",
        name="KOL 准确率评估",
        misfire_grace_time=600,
    )

    # ══════════════════════════════════════════════════════════
    # Agent 系统定时任务
    # ══════════════════════════════════════════════════════════

    # ── Agent 策略监控（每30秒）─────────────────────────────
    scheduler.add_job(
        run_agent_monitor,
        trigger="interval",
        seconds=30,
        id="agent_monitor",
        name="Agent 策略监控",
        misfire_grace_time=10,
    )

    # ── PRD-008: 模拟盘 SL/TP 检查（每30秒）─────────────────
    from agent.paper_engine import run_paper_check_exits, run_paper_check_reminders
    scheduler.add_job(
        run_paper_check_exits,
        trigger="interval",
        seconds=30,
        id="paper_check_exits",
        name="Paper 模拟盘 SL/TP 检查",
        misfire_grace_time=10,
        max_instances=1,
    )

    # ── PRD-008: 模拟盘提醒（每1小时）────────────────────────
    scheduler.add_job(
        run_paper_check_reminders,
        trigger="interval",
        hours=1,
        id="paper_check_reminders",
        name="Paper 3天提醒 + 7天暂停",
        misfire_grace_time=300,
        max_instances=1,
    )

    # ── PRD-008: AI 主动推荐扫描（每4小时）───────────────────
    from agent.proactive_scanner import run_proactive_scan
    scheduler.add_job(
        run_proactive_scan,
        trigger="interval",
        hours=4,
        id="proactive_scan",
        name="AI 主动推荐扫描",
        misfire_grace_time=600,
        max_instances=1,
    )

    # ── PRD-005: 每日反思（UTC 20:00）──────────────────────
    from agent.memory.cron_tasks import run_daily_reflection, backfill_risk_events
    scheduler.add_job(
        run_daily_reflection,
        trigger=CronTrigger(hour=20, minute=0, timezone="UTC"),
        id="daily_reflection",
        name="Agent 每日反思",
        misfire_grace_time=600,
        max_instances=1,
    )

    # ── PRD-005: 风控事件回填（每 6h）──────────────────────
    scheduler.add_job(
        backfill_risk_events,
        trigger="interval",
        hours=6,
        id="risk_events_backfill",
        name="风控事件价格回填",
        misfire_grace_time=3600,
        max_instances=1,
    )


    # ══════════════════════════════════════════════════════════
    # 内盘数据报表
    # ══════════════════════════════════════════════════════════

    # ── 内盘每日报表（UTC 00:30）────────
    scheduler.add_job(
        run_pump_report,
        trigger=CronTrigger(hour=0, minute=30, timezone="UTC"),
        id="pump_report",
        name="内盘每日报表",
        misfire_grace_time=600,
    )

    # ══════════════════════════════════════════════════════════
    # AI Optimizer Agent（每3天自动优化）
    # ══════════════════════════════════════════════════════════

    scheduler.add_job(
        run_governor,
        trigger=CronTrigger(day="*/3", hour=3, minute=0, timezone="UTC"),
        id="optimizer_governor",
        name="AI 优化 Agent（每3天）",
        misfire_grace_time=3600,
        max_instances=1,
    )

    # ══════════════════════════════════════════════════════════
    # ML 自动重训
    # ══════════════════════════════════════════════════════════

    # ── XGBoost 自动重训（默认每周一次）─────────────────────
    # 检查新增标注样本数，够多则自动重训模型
    if USE_ML_SCORING:
        scheduler.add_job(
            auto_retrain_if_needed,
            trigger="interval",
            hours=ML_RETRAIN_INTERVAL_HOURS,
            id="ml_retrain",
            name="XGBoost 自动重训",
            misfire_grace_time=3600,
            max_instances=1,
        )

    # ── DB 写入缓冲刷新（每10秒）──────────────────────
    from database import flush_trade_buffer, flush_snapshot_buffer

    def _flush_all_buffers():
        flush_trade_buffer()
        flush_snapshot_buffer()

    scheduler.add_job(
        _flush_all_buffers,
        trigger="interval",
        seconds=10,
        id="db_buffer_flush",
        name="DB缓冲刷新(10s)",
        misfire_grace_time=5,
        max_instances=1,
    )

    scheduler.start()

    # ── W3 D3: SafetyEngine 启动恢复 + DB 持久化挂载 ──────────────
    # 引用 docs/agent-pm/17-tech-plan.md Phase 0
    # 失败不阻断 Agent 启动(safety 自身故障 → 退化为内存模式)
    try:
        from agent.safety_engine import get_safety_engine
        from agent.global_state_persister import attach_to_engine
        _safety = get_safety_engine()
        attach_to_engine(_safety)  # 注入 persister + 从 PG 恢复 _active_breakers
        log.info(
            "[Safety] engine ready: HR=%d CB=%d C=%d state=%s",
            len(_safety.hard_rules),
            len(_safety.circuit_breakers),
            len(_safety.constitutional),
            _safety.get_global_state(),
        )
    except Exception as e:
        log.warning("[Safety] startup failed (non-fatal): %s", e)

    log.info(
        "定时任务已启动:\n"
        "  ── 原有任务 ──\n"
        "  每日 UTC 01:00 → creator_stats\n"
        "  每日 UTC 02:00 → hot_daily_picks\n"
        "  每1小时        → outcome_labeler\n"
        "  每10分钟       → hot_coin_scan (OKX+GeckoTerminal 双源发现)\n"
        "  每30秒         → hot_price_refresh (DexScreener 全量刷新+打分+退出)\n"
        "  毫秒级         → hot_coin_manager (PriceFeed 回调→实时打分→进出榜)\n"
        "  每6小时        → smart_wallet_updater\n"
        "  ── KOL 系统 ──\n"
        "  每30分钟       → kol_collect\n"
        "  每30分钟       → kol_analyze\n"
        "  每1小时        → kol_signal_detect\n"
        "  每日 UTC 03:00 → kol_accuracy_eval\n"
        "  ── Agent 系统 ──\n"
        "  每30秒         → agent_monitor\n"
        "  每30秒         → paper_check_exits (模拟盘 SL/TP 检查)\n"
        "  每1小时        → paper_check_reminders (3天提醒 + 7天暂停)\n"
        "  每4小时        → proactive_scan (AI 主动推荐)\n"
        "  每日 UTC 20:00 → daily_reflection (Agent 记忆反思)\n"
        "  每6小时        → risk_events_backfill (风控事件价格回填)\n"
        "  常驻 WS        → smart_money_tracker (SOL ~400ms / EVM OKX 5s)\n"
        "  ── 数据报表 ──\n"
        "  每日 UTC 00:30 → pump_report (内盘漏斗报表)\n"
        "  ── AI Optimizer ──\n"
        "  每3天 UTC 03:00 → optimizer_governor (AI 自动优化推荐算法)\n"
        "  ── ML 系统 ──\n"
        f"  每{ML_RETRAIN_INTERVAL_HOURS}小时      → ml_retrain (XGBoost 自动重训)"
        f" {'[已启用]' if USE_ML_SCORING else '[未启用，USE_ML_SCORING=0]'}\n"
        "  ── 常驻协程 ──\n"
        "  1秒循环        → performance_loop (OKX+pump.fun 秒级追踪)\n"
        "  常驻           → price_feed (Binance WS SOL/ETH/BNB/BTC + DexScreener WS 热币pair)"
    )

    # 初始化种子数据
    await initialize_kol_accounts()
    initialize_smart_wallets()

    # 启动表现追踪常驻协程（1秒循环）
    asyncio.create_task(run_performance_loop())
    log.info("表现追踪协程已启动 (1s loop)")

    # 初始化热币管理器（从 DB 加载活跃热币）
    hot_coin_manager.load_from_db()

    # 注册 PriceFeed 回调 → 热币实时打分
    price_feed.on_price_update(hot_coin_manager.on_price_update)

    # 注册 PriceFeed 回调 → 模拟盘止盈止损
    from hot_sim_trader import get_sim_trader
    sim_trader = get_sim_trader()
    sim_trader.init_from_db()
    price_feed.on_price_update(sim_trader.on_price_update)
    log.info("sim_trader 已注册 PriceFeed 回调 (open=%d)", len(sim_trader._open_positions))

    # 注册 PriceFeed 回调 → 表现追踪实时价格
    from performance_tracker import on_price_update_for_performance
    price_feed.on_price_update(on_price_update_for_performance)

    # 将已加载的活跃热币注册到 PriceFeed
    for token in hot_coin_manager.get_active_tokens():
        price_feed.register_token(
            address=token.get("address", ""),
            chain=token.get("chain", ""),
            pair_address=token.get("pair_address", ""),
            source="hot_coin",
        )

    # 启动实时价格订阅（Binance WS: SOL/ETH/BNB/BTC + DexScreener WS: 热币 pair）
    asyncio.create_task(price_feed.start())
    log.info("price_feed 已启动 (Binance WS + DexScreener WS)")

    # 启动热币管理器 pending flush 协程
    asyncio.create_task(hot_coin_manager.flush_pending())
    log.info("hot_coin_manager 已启动 (PriceFeed 回调 → 实时打分 → 进出榜单)")

    # 启动聪明钱实时追踪（SOL Helius WS ~400ms + EVM OKX API 5s轮询）
    _sm_tracker = await get_tracker()
    asyncio.create_task(_sm_tracker.start())
    log.info("smart_money_tracker 已启动 (SOL DEX Monitor + EVM DEX Monitor + OKX 补充轮询)")

    # 启动事件总线
    event_bus = get_event_bus()
    asyncio.create_task(event_bus.start())
    log.info("EventBus started")

    # 启动 Agent 事件驱动监听（毫秒级策略评估）
    try:
        from agent.event_listener import start_event_listener
        asyncio.create_task(start_event_listener())
        log.info("Agent EventListener started (event-driven strategy evaluation)")
    except Exception as e:
        log.warning(f"Agent EventListener 启动失败: {e}")

    # 启动 BTC/ETH 投资 Agent 模块
    try:
        from btc_eth.manager import BtcEthManager
        from api.routes_btc_eth import set_manager as set_btc_eth_manager
        btc_eth_manager = BtcEthManager()
        asyncio.create_task(btc_eth_manager.start())
        set_btc_eth_manager(btc_eth_manager)
        log.info("BTC/ETH Investment Agent started")
    except Exception as e:
        log.warning(f"BTC/ETH 模块启动失败: {e}")

    # ══════════════════════════════════════════════════════════
    # PRD-006: Regime 检测器
    # ══════════════════════════════════════════════════════════
    try:
        from agent.regime_detector import get_regime_detector
        regime_detector = get_regime_detector()

        # 启动时加载历史特征（避免冷启动 12h 空白）
        asyncio.create_task(regime_detector.load_historical_features())

        # EventBus 订阅（数据管道：kline_close → CUSUM + HMM）
        event_bus.subscribe("btc_eth.kline_close", regime_detector.on_kline_close)
        event_bus.subscribe("btc_eth.indicator_update", regime_detector.on_indicator_update)

        # CRISIS 清仓订阅
        async def _on_crisis_for_positions(event_data):
            data = event_data.get("data", event_data) if isinstance(event_data, dict) else event_data
            if hasattr(data, "data"):
                data = data.data
            if isinstance(data, dict) and data.get("new_regime") == "CRISIS":
                from agent.position_monitor import get_position_monitor
                closed = await get_position_monitor().execute_crisis_close_all()
                log.warning("[CRISIS] Auto-closed %d positions", closed)

        event_bus.subscribe("market.regime_change", _on_crisis_for_positions)

        # CRISIS 检测（每 1 分钟）
        scheduler.add_job(
            regime_detector.check_crisis,
            trigger="interval",
            minutes=1,
            id="crisis_check",
            name="CRISIS Check (1min)",
            misfire_grace_time=30,
            max_instances=1,
        )

        # HMM 定时分类（每 30 分钟 — BTC/SOL/ETH）
        async def _hmm_periodic():
            for asset in ("BTC", "SOL", "ETH"):
                await regime_detector.update_hmm(asset)

        scheduler.add_job(
            _hmm_periodic,
            trigger="interval",
            minutes=30,
            id="hmm_periodic",
            name="HMM 30min (BTC/SOL/ETH)",
            misfire_grace_time=60,
            max_instances=1,
        )

        # Regime 快照（每 30 分钟）
        scheduler.add_job(
            regime_detector.save_periodic_snapshot,
            trigger="interval",
            minutes=30,
            id="regime_snapshot",
            name="Regime Snapshot (30min)",
            misfire_grace_time=60,
            max_instances=1,
        )

        # HMM 每日重训练（UTC 04:00）
        scheduler.add_job(
            regime_detector.retrain_hmm,
            trigger=CronTrigger(hour=4, minute=0, timezone="UTC"),
            id="hmm_retrain",
            name="HMM Daily Retrain",
            misfire_grace_time=3600,
            max_instances=1,
        )

        log.info("PRD-006 Regime Detector started (CUSUM event-driven + HMM 30min + CRISIS 1min)")
    except Exception as e:
        log.warning(f"PRD-006 Regime Detector 启动失败: {e}")

    # ── pump signal pool dump loop ────────────────────────────
    # 把 scanner._signal_pool 每 60s 写 /tmp/pump_signal_pool.json
    # 让独立 api 进程(api_server.py)能读到实时信号(IPC 文件方式)
    # 引用 docs/runbook/pump-scanner-api.service
    async def _dump_signal_pool_loop():
        import json
        from datetime import datetime, timezone
        while True:
            try:
                from scanner_ref import get_scanner
                _sc = get_scanner()
                if _sc is not None:
                    sigs = _sc.get_signals()
                    is_hist = bool(sigs and sigs[0].get("is_history"))
                    with open("/tmp/pump_signal_pool.json", "w") as f:
                        json.dump({
                            "signals": sigs,
                            "is_history": is_hist,
                            "ts": datetime.now(timezone.utc).isoformat(),
                        }, f, default=str)
            except Exception as _e:
                log.warning(f"signal_pool dump 失败: {_e}")
            await asyncio.sleep(60)
    asyncio.create_task(_dump_signal_pool_loop())
    log.info("signal pool dump loop 已启动 (每 60s 写 /tmp/pump_signal_pool.json)")

    # 启动 FastAPI（如果启用）
    if ENABLE_API:
        from api.app import start_api_server
        api_task = asyncio.create_task(start_api_server(port=API_PORT))
        log.info(f"FastAPI server starting on port {API_PORT}")
        # 修复(2026-05-01):给 uvicorn task 完整 grace period 让 socket bind 完成
        # 否则 await scanner.run() 进入后 SmartMoneyTracker/EventBus/etc. 持续抢占
        # event loop,uvicorn task 永远拿不到 socket bind 时机,导致 8000 不 LISTEN
        # 详见 docs/memory/pitfalls.md "pump-scanner systemd 重启 8000 不 LISTEN"
        # 注意:必须用 asyncio.open_connection(异步)探测;
        #   不能用 socket.create_connection(同步会阻塞整个 event loop)
        for _ in range(20):  # 最多等 10s,每 0.5s 让 event loop 调度一次
            await asyncio.sleep(0.5)
            if api_task.done():  # uvicorn 早期 fail-fast(端口冲突等)立即抛
                api_task.result()
                break
            try:
                _r, _w = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", API_PORT),
                    timeout=0.3,
                )
                _w.close()
                try:
                    await _w.wait_closed()
                except Exception:
                    pass
                log.info(f"FastAPI on port {API_PORT} ready")
                break
            except (OSError, ConnectionRefusedError, asyncio.TimeoutError):
                continue
        else:
            log.warning(f"FastAPI on port {API_PORT} not ready after 10s grace period")

    # 启动实时采集（阻塞主协程）
    await scanner.run()


if __name__ == "__main__":
    asyncio.run(main())
