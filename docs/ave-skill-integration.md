# AVE Cloud Skill Integration — AiTrading Pro

## Project Overview

AiTrading Pro is an AI-powered autonomous crypto trading agent that monitors 4 blockchains in real-time, detects trading signals from 5 independent sources, and makes intelligent buy/sell decisions through a 3-level AI decision engine.

The entire data pipeline and trade execution layer is built on **AVE Cloud Skills**, leveraging AVE's multi-chain data aggregation and self-custody trading infrastructure.

---

## AVE Skills Used

| Skill | Module | Role in System |
|-------|--------|---------------|
| **ave-data-rest** | `ave_client.py` | Token discovery, real-time pricing, contract security audit, smart wallet intelligence |
| **ave-trade-chain-wallet** | `ave_client.py` + `trade_executor.py` | Self-custody DEX swap execution across 4 chains with local private key signing |

---

## How AVE Skills Power Each Module

### 1. Hot Coin Discovery — `/tokens/trending`

Every 10 minutes, the system queries AVE's trending endpoint to discover hot tokens across Solana, BSC, ETH, and Base.

```
AVE /tokens/trending?chain=solana
    ↓ Returns 50 tokens with price, volume, market cap, holders
    ↓
Hard Filter (age 3-90d, liq $30K+, mcap $200K-$50M, vol $15K+)
    ↓
100-Point Scoring: Momentum(50) + Quality(30) + Potential(20)
    ↓
Score >= 50 → Enter hot list → Real-time monitoring
```

**AVE data fields consumed**: `current_price_usd`, `market_cap`, `tvl`, `token_tx_volume_usd_24h`, `holders`, `token_price_change_1h/4h/24h`, `token_buy_tx_count_1h`, `token_sell_tx_count_1h`

### 2. Token Security Audit — `/contracts/{address}-{chain}`

Before any token enters the hot list or triggers a trade, AVE's contract analysis API performs a comprehensive security check.

```
AVE /contracts/{address}-{chain}
    ↓ Returns risk_score, is_honeypot, buy_tax, sell_tax,
    ↓ has_mint_method, has_black_method, holders_detail
    ↓
Risk Assessment:
  - is_honeypot == 1 → BLOCK
  - buy_tax > 10% → BLOCK
  - sell_tax > 10% → BLOCK
  - Top10 holder concentration > 80% → BLOCK
```

### 3. Real-Time Price Feed — `/tokens/{address}-{chain}`

The unified price service polls AVE token detail API every 2 seconds to maintain real-time prices for all monitored tokens.

```
AVE /tokens/{address}-{chain}
    ↓ Returns current_price_usd (real-time)
    ↓
PriceFeed Cache → Callbacks:
  [1] hot_coin_manager → Re-score → Entry/Exit decisions
  [2] sim_trader → TP/SL check (15% threshold)
  [3] performance_tracker → Daily high tracking (D0-D30)
```

This reference-counted architecture ensures tokens continue receiving price updates even after exiting the hot list, as long as any consumer (sim trader, performance tracker) still needs them.

### 4. Smart Money Intelligence — `/address/smart_wallet/list`

AVE's smart wallet API provides a curated list of profitable on-chain wallets, supplementing our own 15,000+ address database mined from on-chain data.

```
AVE /address/smart_wallet/list?chain=solana&limit=100
    ↓ Returns wallet addresses with PnL, win rate filters
    ↓
Merged with internal smart_wallets database
    ↓
Real-time monitoring: Helius WS (SOL) + EVM WS (BSC/ETH/Base)
    ↓
Heat Score calculation → Signal generation → Sim trade trigger
```

### 5. Trade Execution — `chainWallet/*`

When the AI Agent decides to execute a trade, AVE's chain-wallet API handles the DEX aggregation while we maintain full custody of private keys.

```
Step 1: Quote
  POST chainWallet/getAmountOut
  → {estimateOut, decimals}

Step 2: Create Transaction
  POST chainWallet/createSolanaTx (or createEvmTx)
  → {rawTransaction, requestTxId}

Step 3: Local Signing
  Sign with user's private key (solders for SOL, eth_account for EVM)
  → signedTx

Step 4: Submit
  POST chainWallet/sendSignedSolanaTx (or sendSignedEvmTx)
  → {txHash, status}
```

**Self-custody guarantee**: Private keys never leave the server. AVE provides the transaction construction; we sign locally.

---

## System Architecture with AVE Skills

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Signal Detection Layer                         │
│                                                                     │
│  Hot Coins ──── AVE /tokens/trending (4 chains x 50 tokens)        │
│  Pump.fun ──── Solana WebSocket (real-time BC tracking)             │
│  Smart Money ── AVE /smart_wallet/list + Helius WS + EVM WS        │
│  KOL ───────── Twitter monitoring (212 KOLs, resonance detection)  │
│  BTC/ETH ───── Binance WS + 12 free data collectors                │
│                                                                     │
│  Security: AVE /contracts/{addr} for every token before trading     │
│  Pricing: AVE /tokens/{addr} every 2s for all tracked tokens       │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────v───────────────────────────────────┐
│                      AI Decision Engine                              │
│                                                                     │
│  L1 Rule Engine ─────── Condition tree (AND/OR, 9 operators)        │
│  L2 Fast Eval ──────── Claude Sonnet single-call (~2s)              │
│  L3 Multi-Role Debate ── 3 Analysts (Haiku) + Bull/Bear (Sonnet)   │
│                          + Facilitator arbitration                  │
│                                                                     │
│  Memory: Working(24h) → Episodic(14-30d) → Semantic(50 rules)      │
│  Regime: CUSUM + HMM → 7 states → Position multiplier              │
│  Risk: 15 checks → Circuit breaker → CRISIS auto-liquidation       │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────v───────────────────────────────────┐
│                      Execution Layer (AVE)                          │
│                                                                     │
│  AVE chainWallet/getAmountOut ──────── Best price quote             │
│  AVE chainWallet/createSolanaTx ────── Transaction construction     │
│  Local signing (solders / eth_account) ── Self-custody guarantee    │
│  AVE chainWallet/sendSignedSolanaTx ── On-chain broadcast          │
│                                                                     │
│  Chains: Solana, BSC, Ethereum, Base                                │
│  Sim Trading: Paper engine with 1.5% simulated slippage             │
│  Position Monitor: Auto TP/SL + trailing stop + time decay          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints Consumed

### Data REST (`https://data.ave-api.xyz/v2`)

| Endpoint | Method | Rate | Purpose |
|----------|--------|------|---------|
| `/tokens/trending` | GET | Every 10min | Discover trending tokens per chain |
| `/tokens/{addr}-{chain}` | GET | Every 2s per token | Real-time price + market data |
| `/contracts/{addr}-{chain}` | GET | On discovery | Security: honeypot, tax, risk score |
| `/address/smart_wallet/list` | GET | Every 6h | Smart money wallet intelligence |
| `/tokens` | GET | On demand | Token search by keyword |

### Trade Chain-Wallet (`https://bot-api.ave.ai`)

| Endpoint | Method | When | Purpose |
|----------|--------|------|---------|
| `/v1/thirdParty/chainWallet/getAmountOut` | POST | Pre-trade | Swap quote (price estimate) |
| `/v1/thirdParty/chainWallet/createSolanaTx` | POST | Trade | Generate unsigned SOL tx |
| `/v1/thirdParty/chainWallet/createEvmTx` | POST | Trade | Generate unsigned EVM tx |
| `/v1/thirdParty/chainWallet/sendSignedSolanaTx` | POST | Trade | Submit signed SOL tx |
| `/v1/thirdParty/chainWallet/sendSignedEvmTx` | POST | Trade | Submit signed EVM tx |

---

## Key Implementation: `ave_client.py`

All AVE API interactions are centralized in a single client module with built-in rate limiting and format conversion.

```python
class AveClient:
    # Rate limiting: 1 RPS (Free plan)
    # Auto-retry with exponential backoff
    # Response format conversion to match internal data models

    # Data APIs
    async def get_trending(chain, limit=50)       # → List[token_data]
    async def get_token_detail(address, chain)     # → {price, mcap, volume, ...}
    async def check_risk(address, chain)           # → {is_honeypot, buy_tax, sell_tax, ...}
    async def get_smart_wallets(chain, limit=100)  # → List[wallet_data]

    # Trade APIs
    async def get_quote(chain, in_token, out_token, amount, swap_type)
    async def create_solana_tx(in_token, out_token, amount, ...)
    async def create_evm_tx(chain, in_token, out_token, amount, ...)
    async def send_signed_solana_tx(request_tx_id, signed_tx)
    async def send_signed_evm_tx(chain, request_tx_id, signed_tx)
```

---

## Supported Chains

| Chain | Discovery | Pricing | Security | Trading |
|-------|-----------|---------|----------|---------|
| Solana | /tokens/trending | /tokens/{addr} | /contracts/{addr} | createSolanaTx |
| BSC | /tokens/trending | /tokens/{addr} | /contracts/{addr} | createEvmTx |
| Ethereum | /tokens/trending | /tokens/{addr} | /contracts/{addr} | createEvmTx |
| Base | /tokens/trending | /tokens/{addr} | /contracts/{addr} | createEvmTx |

---

## Results & Metrics

### Signal Quality
- Hot coin scoring covers 4 chains with ~200 active tokens at any time
- Smart money tracker monitors 15,000+ wallets with v3 five-dimension evaluation
- KOL resonance detection across 212 monitored accounts

### Trading Performance
- Sim trader processes TP/SL checks every 2 seconds via AVE price feed
- 250+ positions closed within 3 minutes of unified price service deployment
- 4 signal sources (hot/pump/smart_money/btc_eth) with independent sim tracking

### AI Decision Quality
- L3 debate produces structured bull/bear analysis with confidence scores
- Memory system learns from trades: 50 validated semantic rules, daily reflection
- Regime detector adapts position sizing across 7 market states

---

## Environment Setup

```bash
# Required
AVE_API_KEY=your_ave_cloud_api_key
API_PLAN=free

# Application
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_key
ANTHROPIC_API_KEY=your_claude_api_key
HELIUS_API_KEY=your_helius_key

# Start
cd services/pump-scanner
python main.py
```

---

## License

MIT
