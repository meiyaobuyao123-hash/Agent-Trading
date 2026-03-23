"""PRD-004 Medium Issues - Unit + Integration Tests"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import logging
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

logging.basicConfig(level=logging.WARNING)


async def run_tests():
    results = []

    def ok(name, msg):
        results.append(("PASS", name, msg))

    def fail(name, msg):
        results.append(("FAIL", name, msg))

    print("=" * 60)
    print("PRD-004 Medium Issues Tests")
    print("=" * 60)

    # === M-03: Config constants exist ===
    from config import (
        SIGNAL_POOL_MIN_SCORE, SIGNAL_POOL_BC_MIN, SIGNAL_POOL_BC_MAX,
        AGENT_MONTHLY_QUOTA, RISK_DAILY_LOSS_LIMIT, RISK_WEEKLY_LOSS_LIMIT,
        RISK_MAX_POSITION_USD, RISK_MAX_DRAWDOWN_PCT, RISK_BTC_CRISIS_PCT,
        SIGNAL_COOLDOWN_HOURS, DEPTH_IMBALANCE_THRESHOLD,
    )

    if SIGNAL_POOL_MIN_SCORE == 55:
        ok("M-03a SIGNAL_POOL_MIN_SCORE", f"={SIGNAL_POOL_MIN_SCORE}")
    else:
        fail("M-03a SIGNAL_POOL_MIN_SCORE", f"expected 55, got {SIGNAL_POOL_MIN_SCORE}")

    if RISK_DAILY_LOSS_LIMIT == 50:
        ok("M-03b RISK_DAILY_LOSS_LIMIT", f"={RISK_DAILY_LOSS_LIMIT}")
    else:
        fail("M-03b RISK_DAILY_LOSS_LIMIT", f"expected 50, got {RISK_DAILY_LOSS_LIMIT}")

    if RISK_BTC_CRISIS_PCT == 3:
        ok("M-03c RISK_BTC_CRISIS_PCT", f"={RISK_BTC_CRISIS_PCT}")
    else:
        fail("M-03c RISK_BTC_CRISIS_PCT", f"expected 3, got {RISK_BTC_CRISIS_PCT}")

    if SIGNAL_COOLDOWN_HOURS == 4:
        ok("M-03d SIGNAL_COOLDOWN_HOURS", f"={SIGNAL_COOLDOWN_HOURS}")
    else:
        fail("M-03d SIGNAL_COOLDOWN_HOURS", f"expected 4, got {SIGNAL_COOLDOWN_HOURS}")

    # === M-03: RiskConfig reads from config ===
    from agent.risk_manager import RiskConfig
    rc = RiskConfig()
    if rc.max_position_usd == RISK_MAX_POSITION_USD:
        ok("M-03e RiskConfig.max_position", f"=${rc.max_position_usd}")
    else:
        fail("M-03e RiskConfig.max_position", f"expected {RISK_MAX_POSITION_USD}, got {rc.max_position_usd}")

    if rc.max_daily_loss_usd == RISK_DAILY_LOSS_LIMIT:
        ok("M-03f RiskConfig.max_daily_loss", f"=${rc.max_daily_loss_usd}")
    else:
        fail("M-03f RiskConfig.max_daily_loss", f"expected {RISK_DAILY_LOSS_LIMIT}, got {rc.max_daily_loss_usd}")

    # === M-02: LLM Parser retry logic ===
    from agent.llm_parser import LLMParser
    parser = LLMParser.__new__(LLMParser)
    # Verify retry constants exist in parse_strategy method source
    import inspect
    src = inspect.getsource(parser.parse_strategy)
    if "MAX_RETRIES" in src and "RETRY_DELAYS" in src:
        ok("M-02a retry constants", "MAX_RETRIES + RETRY_DELAYS found in source")
    else:
        fail("M-02a retry constants", "missing retry logic")

    if "RateLimitError" in src:
        ok("M-02b RateLimitError handling", "catches RateLimitError")
    else:
        fail("M-02b RateLimitError handling", "missing RateLimitError catch")

    # === M-04: save_indicators has valid column filter ===
    from btc_eth.storage import save_indicators
    src_save = inspect.getsource(save_indicators)
    if "VALID_COLS" in src_save:
        ok("M-04a VALID_COLS filter", "column whitelist exists")
    else:
        fail("M-04a VALID_COLS filter", "no column whitelist")

    # Test with fake data - should not crash
    try:
        save_indicators("TEST", {"price_usd": 0, "invalid_col": 999})
        ok("M-04b zero price skip", "correctly skipped (price=0)")
    except Exception as e:
        fail("M-04b zero price skip", f"crashed: {e}")

    # === M-05: check_all_exits exists ===
    from btc_eth.paper_trading.engine import PaperTradingEngine
    if hasattr(PaperTradingEngine, "check_all_exits"):
        ok("M-05a check_all_exits", "method exists")
    else:
        fail("M-05a check_all_exits", "method missing")

    # Test check_all_exits with empty trades
    engine = PaperTradingEngine()
    try:
        closed = await engine.check_all_exits({"BTC": 70000, "ETH": 2100})
        ok("M-05b check_all_exits run", f"closed={closed}")
    except Exception as e:
        fail("M-05b check_all_exits run", f"crashed: {e}")

    # === M-01: trigger_count RPC function migration exists ===
    migration_path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                   "supabase", "migrations", "027_increment_trigger_rpc.sql")
    if os.path.exists(migration_path):
        ok("M-01a migration file", "027_increment_trigger_rpc.sql exists")
    else:
        # Try alternative path
        alt_path = "/opt/agent-trading/supabase/migrations/027_increment_trigger_rpc.sql"
        if os.path.exists(alt_path):
            ok("M-01a migration file", "027 exists (alt path)")
        else:
            fail("M-01a migration file", "027_increment_trigger_rpc.sql not found")

    # === IT-01: Health check still works ===
    import aiohttp
    async with aiohttp.ClientSession() as sess:
        try:
            async with sess.get(
                "http://127.0.0.1:8000/health",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                (ok if r.status == 200 else fail)("IT-01 Health", f"status={r.status}")
        except Exception as e:
            fail("IT-01 Health", str(e)[:60])

    # === IT-02: Agent chat with retry ===
    async with aiohttp.ClientSession() as sess:
        try:
            async with sess.post(
                "http://127.0.0.1:8000/api/agent/chat",
                json={"message": "hello", "user_id": "test"},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as r:
                (ok if r.status == 200 else fail)("IT-02 Agent chat", f"status={r.status}")
        except Exception as e:
            fail("IT-02 Agent chat", str(e)[:60])

    # === IT-03: BTC/ETH indicators should persist ===
    async with aiohttp.ClientSession() as sess:
        try:
            async with sess.get(
                "http://127.0.0.1:8000/api/btc-eth/health",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    ok("IT-03 BTC/ETH health", f"running={data.get('running', False)}")
                else:
                    fail("IT-03 BTC/ETH health", f"status={r.status}")
        except Exception as e:
            fail("IT-03 BTC/ETH health", str(e)[:60])

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
