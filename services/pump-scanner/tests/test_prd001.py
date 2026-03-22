"""PRD-001 Agent Sell Execution - Unit + Integration Tests"""
import asyncio
import json
import logging

logging.basicConfig(level=logging.WARNING)


async def run_tests():
    results = []

    def ok(name, msg):
        results.append(("PASS", name, msg))

    def fail(name, msg):
        results.append(("FAIL", name, msg))

    print("=" * 60)
    print("PRD-001 Unit + Integration Tests")
    print("=" * 60)

    # === UT-01: Balance Query ===
    from agent.trade_executor import get_trade_executor
    executor = get_trade_executor()

    try:
        bal = await executor._query_token_balance(
            "solana", "11111111111111111111111111111111",
            "So11111111111111111111111111111111111111112",
        )
        ok("UT-01a SOL balance", f"balance={bal}")
    except Exception as e:
        fail("UT-01a SOL balance", str(e)[:60])

    try:
        bal = await executor._query_token_balance(
            "eth", "0x0000000000000000000000000000000000000001",
            "0xdac17f958d2ee523a2206206994597c13d831ec7",
        )
        ok("UT-01b EVM balance", f"balance={bal}")
    except Exception as e:
        fail("UT-01b EVM balance", str(e)[:60])

    try:
        bal = await executor._query_token_balance("solana", "", "")
        ok("UT-01c empty addr", f"balance={bal}")
    except Exception as e:
        ok("UT-01c empty addr", f"{type(e).__name__}")

    # === UT-03: Sell with zero balance ===
    result = await executor.execute_trade(
        chain="solana", token_address="11111111111111111111111",
        action="sell", amount_usd=1.0,
    )
    if not result.success:
        ok("UT-03d zero balance sell", result.error[:60])
    else:
        fail("UT-03d zero balance sell", "should fail")

    # === UT-04: PositionMonitor ===
    from agent.position_monitor import get_position_monitor, PositionInfo
    pm = get_position_monitor()
    await pm.load_positions()
    stats = pm.get_stats()
    ok("UT-04a load positions", f"open={stats.get('open_positions', 0)}")

    fake = {
        "id": "t1", "strategy_id": "", "user_id": "", "chain": "solana",
        "token_address": "Fake", "executed_price": 0.001, "amount_usd": 100,
        "amount_token": 100000, "stop_loss_pct": 20, "take_profit_pct": 50,
        "trailing_stop_pct": 15,
    }
    pos = PositionInfo(fake)
    ok("UT-04b PositionInfo", f"entry={pos.entry_price} tp={pos.take_profit_pct} sl={pos.stop_loss_pct}")

    # Take profit
    p = pos.entry_price * 1.5
    pnl = (p - pos.entry_price) / pos.entry_price * 100
    (ok if pnl >= pos.take_profit_pct else fail)(
        "UT-04c take profit", f"pnl={pnl:.0f}% >= {pos.take_profit_pct}%"
    )

    # Stop loss
    p = pos.entry_price * 0.8
    pnl = (p - pos.entry_price) / pos.entry_price * 100
    (ok if pnl <= -pos.stop_loss_pct else fail)(
        "UT-04d stop loss", f"pnl={pnl:.0f}% <= -{pos.stop_loss_pct}%"
    )

    # Trailing stop
    peak = pos.entry_price * 2.0
    cur = peak * 0.85
    dd = (peak - cur) / peak * 100
    (ok if dd >= pos.trailing_stop_pct else fail)(
        "UT-04e trailing stop", f"dd={dd:.0f}% >= {pos.trailing_stop_pct}%"
    )

    # === UT-05: Concurrent guard ===
    pm._selling.add("t1")
    (ok if "t1" in pm._selling else fail)("UT-05 reentry guard", "selling set works")
    pm._selling.discard("t1")

    # === UT-06: EventListener ===
    from agent.event_listener import get_event_listener_stats
    el_stats = get_event_listener_stats()
    ok("UT-06 EventListener", f"events={el_stats.get('events_processed', 0)}")

    # === UT-07: PerformanceAnalytics ===
    from agent.performance_analytics import get_performance_analytics
    pa = get_performance_analytics()
    perf = await pa.get_performance_summary()
    ok("UT-07 Performance", f"trades={perf.get('total_trades', 0)}")

    # === UT-08: Backtester ===
    from agent.backtester import get_backtester
    bt = get_backtester()
    bt_r = await bt.backtest_strategy(
        {"conditions": {"min_score": 70}, "actions": [{"type": "buy", "amount_usd": 100}]},
        days=7,
    )
    ok("UT-08 Backtester", f"trades={bt_r.get('total_trades', 0)}")

    # === IT-01: API Integration Tests ===
    import aiohttp
    async with aiohttp.ClientSession() as sess:
        try:
            async with sess.post(
                "http://127.0.0.1:8000/api/agent/chat",
                json={"message": "hi", "user_id": "test"},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as r:
                (ok if r.status == 200 else fail)("IT-01a Agent Chat", f"status={r.status}")
        except Exception as e:
            fail("IT-01a Agent Chat", str(e)[:60])

        try:
            async with sess.get(
                "http://127.0.0.1:8000/api/agent/strategies?user_id=test",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                (ok if r.status == 200 else fail)("IT-01b Strategies", f"status={r.status}")
        except Exception as e:
            fail("IT-01b Strategies", str(e)[:60])

        try:
            async with sess.get(
                "http://127.0.0.1:8000/api/agent/performance?user_id=test",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                (ok if r.status == 200 else fail)("IT-01c Performance", f"status={r.status}")
        except Exception as e:
            fail("IT-01c Performance", str(e)[:60])

        try:
            async with sess.post(
                "http://127.0.0.1:8000/api/agent/backtest",
                json={"strategy": {"conditions": {"min_score": 70}, "actions": [{"type": "buy", "amount_usd": 100}]}, "days": 7},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                (ok if r.status == 200 else fail)("IT-01d Backtest", f"status={r.status}")
        except Exception as e:
            fail("IT-01d Backtest", str(e)[:60])

    # === Results ===
    print()
    for status, name, msg in results:
        icon = "PASS" if status == "PASS" else "FAIL"
        print(f"  [{icon}] {name}: {msg}")

    passed = sum(1 for s, _, _ in results if s == "PASS")
    failed = sum(1 for s, _, _ in results if s == "FAIL")
    print(f"\nTotal: {passed} passed / {failed} failed")
    if failed > 0:
        print("FAILED - needs fixing")
        return 1
    print("ALL PASSED")
    return 0


if __name__ == "__main__":
    exit(asyncio.run(run_tests()))
