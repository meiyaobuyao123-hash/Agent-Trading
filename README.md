# AiTrading Pro

> AI-Powered Multi-Chain Crypto Trading Agent — From Signal Discovery to Autonomous Execution

AiTrading Pro is a full-stack AI trading system that monitors 4 blockchains in real-time, detects trading signals from 5 independent sources, makes autonomous buy/sell decisions through a 3-level AI engine, and executes trades on-chain via DEX aggregators — all powered by [AVE Cloud Skills](https://github.com/AveCloud/ave-cloud-skill).

**Live Demo**: http://43.156.207.26 (Portal)  |  iOS App: AiTrading Pro (App Store)

---

## System Architecture

```
                        ┌────────────────────────────────┐
                        │        Flutter Mobile App       │
                        │   (iOS/Android, 4 languages)    │
                        └───────────────┬────────────────┘
                                        │
                        ┌───────────────v────────────────┐
                        │      FastAPI + WebSocket        │
                        │      (Real-time API Layer)      │
                        └───────────────┬────────────────┘
                                        │
┌─────────────────────────────────────────────────────────────────────┐
│                    Signal Detection Layer                            │
│                                                                     │
│  ┌─────────────┐ ┌───────────┐ ┌────────────┐ ┌─────┐ ┌────────┐  │
│  │  Hot Coins   │ │ Pump.fun  │ │Smart Money │ │ KOL │ │BTC/ETH │  │
│  │  4-chain     │ │ 3-stage   │ │ 15K+       │ │ 212 │ │ 50     │  │
│  │  100-pt      │ │ pipeline  │ │ wallets    │ │ KOLs│ │ metrics│  │
│  │  scoring     │ │ BC 3-35%  │ │ ~400ms     │ │     │ │        │  │
│  └──────┬───────┘ └─────┬─────┘ └─────┬──────┘ └──┬──┘ └───┬────┘  │
│         └───────────────┼─────────────┼───────────┼────────┘        │
│                         v             v           v                  │
│              ┌─────────────────────────────────────────┐            │
│              │        Event Bus (Millisecond)           │            │
│              └──────────────────┬──────────────────────┘            │
└─────────────────────────────────┼───────────────────────────────────┘
                                  │
┌─────────────────────────────────v───────────────────────────────────┐
│                     AI Decision Engine                               │
│                                                                     │
│  L1: Rule Engine ──────── Pure conditions ($0, instant)             │
│  L2: Fast Eval ────────── Claude Sonnet single-call ($0.003)        │
│  L3: Multi-Role Debate ── 3 Analysts + Bull/Bear 4 rounds ($0.015) │
│                                                                     │
│  + 3-Layer Memory (short/episodic/semantic) with daily reflection   │
│  + 7-State Regime Detector (CUSUM + HMM + rule overlay)            │
│  + 15-Check Risk Manager with circuit breaker                      │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────v───────────────────────────────────┐
│                     Execution Layer                                  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              AVE Cloud Skills (ave-data-rest +               │   │
│  │              ave-trade-chain-wallet)                         │   │
│  │                                                             │   │
│  │  Data:  /tokens/trending  /contracts/{addr}  /tokens/price  │   │
│  │  Trade: chainWallet/createSolanaTx + sendSignedSolanaTx     │   │
│  │  Smart: /address/smart_wallet/list                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Paper Engine (sim trading) ──── TP/SL 15%, 4 signal sources       │
│  Position Monitor ──────────── Trailing stop, time-decay (MEME)    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Modules

### 1. Multi-Chain Hot Coin Scanner

Real-time trending token discovery across **Solana, BSC, ETH, Base**.

- **Discovery**: AVE `/tokens/trending` + GeckoTerminal new_pools (every 10 min)
- **Hard Filter**: age 3-90d, liquidity $30K-$5M, mcap $200K-$50M, vol $15K+, tax <10%
- **Scoring (0-100)**: Momentum(50) + Quality(30) + Potential(20)
  - M: 1h/24h price change, volume acceleration, buy pressure, freshness
  - Q: holder count, social presence, security audit, holder distribution
  - P: market cap position (log scale), token age sweet spot, multi-timeframe resonance
- **Entry**: score >= 50, no GoPlus risk
- **Exit**: 5 rules (low score x3, pump-dump, volume dry, sell pressure, missed scan x5)

### 2. Pump.fun Inner Market Monitor

3-stage pipeline for Solana pump.fun tokens (BC 3-35%).

- **Stage 1**: WebSocket full capture (all new tokens)
- **Stage 2**: Trade tracking (up to 20K tokens in memory)
- **Stage 3**: On-demand enrichment (buyers >= 3, BC >= 2%)
- **Signal Pool**: score >= 55, auto-buy sim trader on entry
- **Scoring (0-100)**: buy/sell ratio(25%), smart money(20%), inflow acceleration(15%), creator history(15%), buyer diversity(10%), social(10%), speed(5%) + bonus

### 3. Smart Money Tracker

15,000+ wallet addresses monitored in real-time.

- **SOL**: Helius WebSocket (~400ms latency), 6 DEX programs (Raydium, Jupiter, Pump.fun, Orca, Meteora)
- **EVM**: WebSocket eth_subscribe for Swap events (BSC/ETH/Base)
- **Heat Score**: tier-weighted (elite x5, verified x3, watching x1) + concentration bonus
- **Signal**: heat >= 15, unique_buyers >= 3 triggers sim buy
- **v3 Evaluation**: 5 dimensions (win rate, PnL, volume, activity, freshness)

### 4. KOL Sentiment Engine

212 KOLs monitored, 4 tiers (mega >500K, large 100K-500K, medium 20K-100K, small 5K-20K).

- **Resonance**: 3+ KOLs mention same token in 24h
- **Signal Strength (0-10)**: quantity(3) + quality(3) + sentiment(2) + reach(2)
- **Push threshold**: signal_strength >= 5.0

### 5. BTC/ETH Investment Agent

50 indicators, 5 composite scores, 13 free data collectors.

- **Indicators**: price, volume, futures (funding/OI), sentiment (FGI/news), on-chain (netflow/active addresses), macro (DXY/ETF), technical (RSI/MACD/BB/ATR)
- **Composite Scores (0-100)**: momentum, sentiment, on-chain, macro, risk
- **Signals**: RSI <= 30 oversold, RSI >= 70 overbought, extreme funding rate

### 6. AI Trading Agent

Natural language strategy creation with autonomous execution.

- **Chat Interface**: User describes strategy in plain language -> Claude Sonnet generates executable JSON (tool use, multi-turn)
- **3-Level Decision**:
  - L1: Pure rule engine (conditions tree, AND/OR recursive) — $0
  - L2: Single Claude Sonnet evaluation — $0.003
  - L3: 3 Analysts (Technical/Sentiment/Onchain via Haiku) + Bull/Bear debate (4 rounds Sonnet) + Facilitator arbitration — $0.015
- **Memory System**:
  - Working (24h buffer, 200 events)
  - Episodic (14-30 day trade reviews, relevance scoring)
  - Semantic (50 validated rules, promotion/deprecation lifecycle)
  - Daily reflection at UTC 20:00, emergency reflection on -25% loss
- **Regime Detector**: CUSUM event-driven + HMM 30-min classification + rule overlay
  - 7 states: TRENDING_UP, BREAKOUT, RANGING, HIGH_VOLATILITY, TRENDING_DOWN, CRISIS, RECOVERY
  - CRISIS: auto close all positions, 0% new buys
- **Risk Manager**: 15 checks (position limit, daily/weekly loss, drawdown, frequency, token safety, BTC crash, chain concentration), circuit breaker (60 min cooldown)
- **5 Strategy Templates**: MEME sniper, hot breakout, smart money follow, KOL sentiment, conservative DCA

---

## AVE Cloud Skill Integration

All data querying, risk assessment, and trade execution are powered by **AVE Cloud Skills**.

| Skill | API Endpoint | Purpose |
|-------|-------------|---------|
| **ave-data-rest** | `data.ave-api.xyz/v2` | Token trending, batch pricing, contract security, smart wallet list |
| **ave-trade-chain-wallet** | `bot-api.ave.ai` | Self-custody DEX swaps (SOL/BSC/ETH/Base) with local signing |

**Key API Endpoints**:
- `/tokens/trending` — Hot coin discovery
- `/contracts/{addr}-{chain}` — Honeypot/tax/risk detection
- `/tokens/{addr}-{chain}` — Real-time price + market data
- `/address/smart_wallet/list` — Smart money wallet list
- `chainWallet/getAmountOut` — Swap quote
- `chainWallet/createSolanaTx` + `sendSignedSolanaTx` — On-chain execution

See [docs/ave-skill-integration.md](docs/ave-skill-integration.md) for full integration details.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9+, FastAPI, APScheduler, asyncio |
| Database | Supabase (PostgreSQL) + in-memory caches |
| Real-time | Helius WS, Binance WS, EVM WS (eth_subscribe) |
| AI | Claude Sonnet 4 / Haiku 4.5 (decision, debate, reflection) |
| Data & Trading | **AVE Cloud Skills** (data-rest + trade-chain-wallet) |
| DEX Routing | AVE chainWallet, Jupiter (SOL), 1inch (EVM) |
| Mobile | Flutter (iOS/Android), i18n (zh/en/ja/ko) |
| Portal | Next.js admin dashboard |

---

## Project Structure

```
services/pump-scanner/          # Core backend service
  main.py                       # Entry: scheduler + event loop
  config.py                     # All configuration + AVE switch
  ave_client.py                 # AVE Cloud API unified client
  collector.py                  # Pump.fun 3-stage pipeline
  hot_coin_manager.py           # Hot coin entry/exit with PriceFeed
  hot_coin_fetcher.py           # Token discovery (AVE trending)
  hot_scorer.py                 # 100-point scoring model (M+Q+P)
  price_feed.py                 # Unified price service (AVE + Binance WS)
  smart_money_tracker.py        # Multi-chain smart money monitor
  hot_sim_trader.py             # Sim trader (TP/SL 15%)
  performance_tracker.py        # Token performance tracking (D0-D30)
  agent/
    llm_parser.py               # Natural language -> strategy JSON
    strategy_manager.py         # Strategy CRUD + lifecycle
    evaluator.py                # Condition tree evaluation
    decision_agent.py           # Final decision (confidence + regime)
    debate.py                   # Bull-bear 4-round debate
    analysts/                   # Technical / Sentiment / Onchain (Haiku)
    risk_manager.py             # 15 risk checks + circuit breaker
    trade_executor.py           # DEX execution (AVE chainWallet)
    paper_engine.py             # Paper trading engine
    position_monitor.py         # Auto SL/TP/trailing stop
    memory/                     # 3-layer memory + reflection
    regime_detector.py          # CUSUM + HMM market state
    templates.py                # 5 preset strategy templates
    backtester.py               # Historical backtest engine
    proactive_scanner.py        # AI proactive recommendations
  btc_eth/                      # BTC/ETH investment module (13 collectors)
  api/                          # FastAPI routes (20+ endpoints)

apps/app/                       # Flutter mobile app (iOS/Android)
apps/portal/                    # Next.js admin portal

docs/
  ave-skill-integration.md      # AVE Skill integration documentation
```

---

## Quick Start

```bash
cd services/pump-scanner
pip install -r requirements.txt
cp .env.example .env            # Configure API keys
python main.py                  # Start all services
```

**Environment Variables**:
| Variable | Required | Description |
|----------|----------|-------------|
| `AVE_API_KEY` | Yes | AVE Cloud API key from https://cloud.ave.ai |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key |
| `ANTHROPIC_API_KEY` | Yes | Claude API key for AI Agent |
| `HELIUS_API_KEY` | Yes | Helius RPC for Solana |

---

## License

MIT
