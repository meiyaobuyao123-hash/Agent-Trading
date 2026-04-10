# AiTrading Pro

AI-driven multi-chain crypto trading agent with real-time signal detection, smart money tracking, and autonomous trade execution.

## Features

- **Multi-chain Hot Coin Scanner** — Real-time trending token discovery across Solana, BSC, ETH, Base with 100-point scoring (Momentum + Quality + Potential)
- **Pump.fun Monitor** — 3-stage pipeline: WS capture -> trade tracking -> enrichment -> signal pool (BC 3-35%, score >= 55)
- **Smart Money Tracker** — 15,000+ wallet addresses, Helius WS (SOL ~400ms) + EVM DEX event monitoring, v3 five-dimension evaluation
- **KOL Sentiment** — 212 KOLs monitored, resonance signal detection (3+ KOLs mentioning same token in 24h)
- **BTC/ETH Investment Agent** — 50 indicators, 5 composite scores (momentum/sentiment/onchain/macro/risk), cycle analysis
- **AI Trading Agent** — 3-level decision engine (L1 rules / L2 fast eval / L3 bull-bear debate), memory-driven self-learning
- **Risk Management** — 15 risk checks, 7-state Regime detector (CUSUM+HMM), circuit breaker, trailing stop-loss
- **Sim Trader** — Paper trading with 15% TP/SL across 4 signal sources (hot/pump/smart_money/btc_eth)

## Architecture

```
Signal Sources          AI Decision           Execution
--------------         -----------           ---------
Hot Coins       ─┐
Pump.fun        ─┤     L1: Rules ($0)        Paper Engine
Smart Money     ─┼──>  L2: Fast AI ($0.003)  OKX DEX
KOL Sentiment   ─┤     L3: Debate ($0.015)   Jupiter / 1inch
BTC/ETH         ─┘     + Memory + Regime     AVE Cloud (switch)
```

## AVE Cloud Skill Integration

This project integrates [AVE Cloud Skills](https://github.com/AveCloud/ave-cloud-skill) as a switchable data and trading layer for the **AVE Claw Hackathon 2026**.

### AVE Skills Used

| Skill | Purpose |
|-------|---------|
| **ave-data-rest** | Token trending, pricing, contract risk detection, smart wallet lists |
| **ave-trade-chain-wallet** | Self-custody DEX swaps on Solana/BSC/ETH/Base |

### Switch Mechanism

```bash
# AVE mode (hackathon demo)
USE_AVE=true AVE_API_KEY=your_key python main.py

# Original mode (production, default)
python main.py
```

`USE_AVE=true`: entire pipeline routes through AVE Cloud API
`USE_AVE=false` (default): uses DexScreener + GoPlus + OKX DEX

See [docs/ave-skill-integration.md](docs/ave-skill-integration.md) for full integration details.

## Tech Stack

- **Backend**: Python 3.9+, FastAPI, APScheduler, asyncio
- **Data**: Supabase (PostgreSQL), in-memory caches
- **Real-time**: Helius WS, Binance WS, EVM WS (eth_subscribe)
- **AI**: Claude Sonnet/Haiku (decision, debate, reflection)
- **Trading**: OKX DEX Aggregator, Jupiter (SOL), 1inch (EVM), AVE Cloud
- **Mobile**: Flutter (iOS/Android), i18n (zh/en/ja/ko)
- **Portal**: Next.js admin dashboard

## Quick Start

```bash
cd services/pump-scanner
pip install -r requirements.txt
cp .env.example .env  # fill in API keys
python main.py
```

## Project Structure

```
services/pump-scanner/     # Core backend
  main.py                  # Entry point, scheduler
  config.py                # All configuration
  ave_client.py            # AVE Cloud API client (hackathon switch)
  collector.py             # Pump.fun 3-stage pipeline
  hot_coin_manager.py      # Hot coin entry/exit management
  hot_coin_fetcher.py      # OKX + GeckoTerminal discovery
  hot_scorer.py            # 100-point scoring model
  price_feed.py            # Unified real-time price service
  smart_money_tracker.py   # Multi-chain smart money monitor
  hot_sim_trader.py        # Sim trader (TP/SL engine)
  performance_tracker.py   # Token performance tracking
  agent/                   # AI Trading Agent
    decision_agent.py      # Final decision (confidence + regime)
    debate.py              # Bull-bear debate engine
    risk_manager.py        # 15 risk checks + circuit breaker
    trade_executor.py      # DEX trade execution
    memory/                # 3-layer memory system
    regime_detector.py     # Market state detection (7 states)
  btc_eth/                 # BTC/ETH investment module
  api/                     # FastAPI routes

apps/app/                  # Flutter mobile app
apps/portal/               # Next.js admin portal

docs/
  ave-skill-integration.md # AVE Skill hackathon docs
```

## License

MIT
