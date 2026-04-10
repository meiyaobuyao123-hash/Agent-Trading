# AVE Cloud Skill Integration

## Overview

This project integrates **AVE Cloud Skills** as a switchable data and trading layer for the AiTrading Pro multi-chain crypto trading agent system.

When `USE_AVE=true`, the entire pipeline — token discovery, risk assessment, real-time pricing, and DEX trade execution — routes through AVE Cloud APIs. When `USE_AVE=false`, the system falls back to its original stack (DexScreener + GoPlus + OKX DEX).

---

## AVE Skills Used

| Skill | Script | Purpose in Our System |
|-------|--------|-----------------------|
| **ave-data-rest** | ave_data_rest.py | Token trending discovery, batch pricing, contract risk/honeypot detection, smart wallet lists |
| **ave-trade-chain-wallet** | ave_trade_rest.py | Self-custody DEX swaps on Solana/BSC/ETH/Base with local private key signing |

### API Endpoints Consumed

#### Data REST (https://data.ave-api.xyz/v2)

| Endpoint | Method | Usage |
|----------|--------|-------|
| `/tokens/trending` | GET | Hot coin discovery — replaces OKX TopList as trending token source |
| `/tokens/{address}-{chain}` | GET | Token detail with real-time price, market cap, volume, holders |
| `/contracts/{address}-{chain}` | GET | Contract security audit — replaces GoPlus for honeypot/tax/risk detection |
| `/address/smart_wallet/list` | GET | Smart money wallet list with PnL and win rate filtering |
| `/tokens` | GET | Token search by keyword |

#### Trade Chain-Wallet (https://bot-api.ave.ai)

| Endpoint | Method | Usage |
|----------|--------|-------|
| `/v1/thirdParty/chainWallet/getAmountOut` | POST | Swap quote (price estimate before execution) |
| `/v1/thirdParty/chainWallet/createSolanaTx` | POST | Generate unsigned Solana transaction data |
| `/v1/thirdParty/chainWallet/createEvmTx` | POST | Generate unsigned EVM transaction data |
| `/v1/thirdParty/chainWallet/sendSignedSolanaTx` | POST | Submit locally-signed Solana transaction |
| `/v1/thirdParty/chainWallet/sendSignedEvmTx` | POST | Submit locally-signed EVM transaction |

---

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                    AiTrading Pro Agent System                  │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ AI Decision  │  │ Risk Manager │  │ Memory & Reflection  │ │
│  │ (L1/L2/L3)  │  │ (15 checks)  │  │ (3-layer learning)   │ │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘ │
│         │                  │                                   │
│  ┌──────v──────────────────v───────────────────────────────┐  │
│  │              USE_AVE Switch (config.py)                  │  │
│  │                                                          │  │
│  │  ┌─── true ───────────────┐  ┌─── false ──────────────┐ │  │
│  │  │                        │  │                         │ │  │
│  │  │  AVE Cloud Skills      │  │  Original Stack         │ │  │
│  │  │  ├─ /tokens/trending   │  │  ├─ OKX TopList         │ │  │
│  │  │  ├─ /contracts/{addr}  │  │  ├─ GoPlus API          │ │  │
│  │  │  ├─ /tokens/{addr}     │  │  ├─ DexScreener         │ │  │
│  │  │  └─ chainWallet swap   │  │  └─ OKX/Jupiter/1inch   │ │  │
│  │  │                        │  │                         │ │  │
│  │  └────────────────────────┘  └─────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Shared Core (unaffected by switch)                      │  │
│  │  ├─ Scoring Engine (M+Q+P = 0-100)                      │  │
│  │  ├─ Signal Pool (pump.fun BC 3-35%)                      │  │
│  │  ├─ Smart Money Tracker (Helius WS + EVM WS)             │  │
│  │  ├─ KOL Sentiment (212 KOLs, resonance detection)        │  │
│  │  ├─ BTC/ETH Indicators (50 metrics, 5 composite scores)  │  │
│  │  ├─ Sim Trader (TP/SL 15%, 4 signal sources)             │  │
│  │  └─ Regime Detector (CUSUM + HMM, 7 market states)       │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

---

## Switch Mechanism

### Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `USE_AVE` | `true` / `false` | `false` | Master switch for AVE Cloud integration |
| `AVE_API_KEY` | string | — | AVE Cloud API key from https://cloud.ave.ai |
| `API_PLAN` | `free` / `normal` / `pro` | `free` | AVE plan tier (affects rate limits) |

### Files Modified

| File | What Changes | Switch Point |
|------|-------------|--------------|
| `config.py` | AVE config constants | — |
| `ave_client.py` | Centralized AVE API client (new file) | — |
| `hot_coin_fetcher.py` | Token pricing + security check | `if USE_AVE:` at function entry |
| `price_feed.py` | Real-time price polling | `if USE_AVE:` in `_poll_dex_prices()` |
| `agent/trade_executor.py` | Trade execution | `if USE_AVE:` in `execute_trade()` |

### Design Principles

1. **Zero impact when OFF**: `USE_AVE=false` (default) — the system runs exactly as before, no AVE code is loaded
2. **Graceful fallback**: If an AVE API call fails, the system logs a warning and falls back to the original provider
3. **Format compatibility**: AVE responses are converted to match existing data formats inside `ave_client.py`, so downstream logic (scoring, signals, sim trading) is completely unaware of the switch
4. **Single client**: All AVE API calls go through `ave_client.py` with built-in 1 RPS rate limiting

---

## Supported Chains

| Chain | Data | Trading | Notes |
|-------|------|---------|-------|
| Solana | Yes | Yes | Primary chain, most tokens |
| BSC | Yes | Yes | PancakeSwap ecosystem |
| Ethereum | Yes | Yes | Uniswap ecosystem |
| Base | Yes | Yes | Aerodrome ecosystem |

---

## Quick Start

```bash
# 1. Set environment variables
export USE_AVE=true
export AVE_API_KEY=your_api_key_here
export API_PLAN=free

# 2. Start the service
cd services/pump-scanner
python main.py

# 3. Verify AVE is active (check logs)
# Should see: [AVE] GET /tokens/trending ...
# Should see: [AVE Trade] buy ... tx=...
```

---

## Rate Limits (Free Plan)

| Metric | Limit |
|--------|-------|
| Requests per second | 1 RPS |
| Data REST | Unlimited |
| Trade Chain-Wallet | Unlimited |
| Data WSS | Not available |
| Proxy Wallet | Not available |

The built-in rate limiter in `ave_client.py` enforces 1 RPS automatically.

---

## License

This integration is built for the **AVE Claw Hackathon 2026**. The AVE Cloud Skill SDK is MIT licensed.
