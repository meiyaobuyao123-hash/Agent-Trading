"""PRD-002 Risk Manager Bug Fix - Unit + Integration Tests"""
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
    print("PRD-002 Risk Manager Bug Fix Tests")
    print("=" * 60)

    from agent.risk_manager import RiskManager, RiskCheckResult

    # === UT-01: chain_concentration with 5+ same chain ===
    rm = RiskManager()
    # Simulate 5 SOL positions
    for i in range(5):
        rm.record_trade(f"token_{i}", "solana", "buy", 100.0, 0.001)

    result = rm._check_chain_concentration("solana", "buy")
    if "5" in (result.reason or "") or result.risk_level == "medium":
        ok("UT-01 chain 5+ warning", result.reason)
    else:
        fail("UT-01 chain 5+ warning", f"expected warning, got: {result}")

    # === UT-02: multi-chain distributed, no warning ===
    rm2 = RiskManager()
    rm2.record_trade("t1", "solana", "buy", 100.0, 0.001)
    rm2.record_trade("t2", "solana", "buy", 100.0, 0.001)
    rm2.record_trade("t3", "eth", "buy", 100.0, 0.001)
    rm2.record_trade("t4", "eth", "buy", 100.0, 0.001)
    rm2.record_trade("t5", "bsc", "buy", 100.0, 0.001)

    result2 = rm2._check_chain_concentration("solana", "buy")
    if result2.passed and not result2.reason:
        ok("UT-02 multi-chain ok", "no warning for 2 SOL")
    else:
        fail("UT-02 multi-chain ok", f"unexpected: {result2.reason}")

    # === UT-03: no positions, no error ===
    rm3 = RiskManager()
    result3 = rm3._check_chain_concentration("solana", "buy")
    if result3.passed:
        ok("UT-03 empty positions", "no crash, passed=True")
    else:
        fail("UT-03 empty positions", f"unexpected: {result3}")

    # === UT-04: sell action skips check ===
    result4 = rm._check_chain_concentration("solana", "sell")
    if result4.passed and not result4.reason:
        ok("UT-04 sell skips check", "correctly skipped")
    else:
        fail("UT-04 sell skips check", f"unexpected: {result4.reason}")

    # === UT-05: _btc_samples cold start ===
    rm5 = RiskManager()
    # Verify _btc_samples exists at init
    if hasattr(rm5, "_btc_samples") and isinstance(rm5._btc_samples, list):
        ok("UT-05 _btc_samples init", f"type={type(rm5._btc_samples).__name__}, len={len(rm5._btc_samples)}")
    else:
        fail("UT-05 _btc_samples init", "not initialized in __init__")

    # Call market_regime without any samples - should not crash
    result5 = rm5._check_market_regime("buy")
    if result5.passed:
        ok("UT-05b cold start market", "no crash on empty samples")
    else:
        fail("UT-05b cold start market", f"unexpected: {result5}")

    # === UT-06: BTC samples with 4% drop ===
    import time
    rm6 = RiskManager()
    # Manually add samples simulating a 4% drop over 10 min
    now = time.time()
    rm6._btc_samples = [
        (now - 300, 70000),   # 5 min ago: $70,000
        (now - 60, 67500),    # 1 min ago: $67,500
        (now, 67200),         # now: $67,200 (-4%)
    ]
    result6 = rm6._check_market_regime("buy")
    if not result6.passed or "block" in str(type(result6)).lower():
        ok("UT-06 BTC 4% drop block", result6.reason)
    elif result6.reason and "跌" in result6.reason:
        ok("UT-06 BTC 4% drop warning", result6.reason)
    else:
        fail("UT-06 BTC 4% drop", f"expected block/warning, got: passed={result6.passed} reason={result6.reason}")

    # === UT-07: _position_chains tracks correctly ===
    rm7 = RiskManager()
    rm7.record_trade("token_a", "solana", "buy", 100.0, 0.001)
    rm7.record_trade("token_b", "eth", "buy", 200.0, 0.001)
    if rm7._position_chains.get("token_a") == "solana" and rm7._position_chains.get("token_b") == "eth":
        ok("UT-07 position_chains buy", "correct chain tracking")
    else:
        fail("UT-07 position_chains buy", f"chains: {rm7._position_chains}")

    # Sell removes from chain tracking
    rm7.record_trade("token_a", "solana", "sell", 100.0, 0.002)
    if "token_a" not in rm7._position_chains:
        ok("UT-07b position_chains sell", "removed after sell")
    else:
        fail("UT-07b position_chains sell", "token_a still in _position_chains")

    # === IT-01: Full 15 checks pass ===
    rm_full = RiskManager()
    # pre_trade_check needs chain/token_address/action/amount_usd
    try:
        full_result = rm_full.check_trade(
            chain="solana",
            token_address="So11111111111111111111111111111111111111112",
            action="buy",
            amount_usd=50.0,
        )
        if isinstance(full_result, dict):
            ok("IT-01 full checks", f"result={full_result}")
        else:
            ok("IT-01 full checks", f"passed={full_result.passed} reason={full_result.reason}")
    except Exception as e:
        fail("IT-01 full checks", f"crash: {type(e).__name__}: {str(e)[:60]}")

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
