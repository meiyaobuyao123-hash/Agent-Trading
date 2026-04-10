# AiTrading Pro

> AI-Powered Multi-Chain Crypto Trading Agent -- From Signal Discovery to Autonomous Execution

AiTrading Pro is a production-grade, end-to-end AI trading system that monitors **4 blockchains** (Solana, BSC, Ethereum, Base) in real time, detects trading signals from **5 independent sources**, makes autonomous buy/sell decisions through a **3-level AI engine**, and executes trades on-chain via DEX aggregators. The entire data pipeline, risk assessment layer, and trade execution infrastructure are built on top of **AVE Cloud Skills** (`ave-data-rest` + `ave-trade-chain-wallet`).

**Live Portal**: [http://43.156.207.26](http://43.156.207.26)  
**iOS App**: AiTrading Pro (App Store)

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Module 1: Multi-Chain Hot Coin Scanner](#module-1-multi-chain-hot-coin-scanner)
3. [Module 2: Pump.fun Inner Market Monitor](#module-2-pumpfun-inner-market-monitor)
4. [Module 3: Smart Money Tracker](#module-3-smart-money-tracker)
5. [Module 4: KOL Sentiment Engine](#module-4-kol-sentiment-engine)
6. [Module 5: BTC/ETH Investment Agent](#module-5-btceth-investment-agent)
7. [AI Decision Engine](#ai-decision-engine)
8. [Execution Layer](#execution-layer)
9. [Strategy Templates](#strategy-templates)
10. [AVE Cloud Skill Integration](#ave-cloud-skill-integration)
11. [Project Structure](#project-structure)
12. [Tech Stack](#tech-stack)
13. [Environment Variables](#environment-variables)
14. [Quick Start](#quick-start)
15. [License](#license)

---

## System Architecture

```
 ┌──────────────────────────────────────────────────────────────────────────────────────────┐
 │                                   CLIENT LAYER                                           │
 │                                                                                          │
 │   ┌────────────────────────────┐          ┌────────────────────────────┐                 │
 │   │   Flutter Mobile App       │          │   Next.js Admin Portal     │                 │
 │   │   iOS / Android            │          │   Hot / Pump / Agent /     │                 │
 │   │   4 languages (zh/en/ja/ko)│          │   Optimizer / Smart Money  │                 │
 │   │   Real-time signal feed    │          │   Performance dashboards   │                 │
 │   └────────────┬───────────────┘          └─────────────┬──────────────┘                 │
 │                │                                        │                                │
 └────────────────┼────────────────────────────────────────┼────────────────────────────────┘
                  │               REST + WebSocket          │
                  v                                        v
 ┌──────────────────────────────────────────────────────────────────────────────────────────┐
 │                               FastAPI + WebSocket API Layer                              │
 │                          20+ endpoints, geo-block (CN IP), auth                          │
 └────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                              │
 ┌────────────────────────────────────────────v─────────────────────────────────────────────┐
 │                              SIGNAL DETECTION LAYER (5 Sources)                          │
 │                                                                                          │
 │  ┌──────────────┐ ┌───────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────────┐  │
 │  │  Hot Coins    │ │  Pump.fun     │ │ Smart Money  │ │   KOL    │ │   BTC / ETH      │  │
 │  │  4-chain      │ │  3-stage      │ │ 15K+ wallets │ │  212     │ │   50 indicators  │  │
 │  │  100-pt score │ │  pipeline     │ │ SOL ~400ms   │ │  KOLs    │ │   13 collectors  │  │
 │  │  12 sub-dims  │ │  BC 3-35%     │ │ EVM 5s poll  │ │  4 tiers │ │   5 composites   │  │
 │  │  M+Q+P+K      │ │  7 dims+bonus │ │ v3 5-dim     │ │          │ │                  │  │
 │  └──────┬────────┘ └──────┬────────┘ └──────┬───────┘ └────┬─────┘ └────────┬─────────┘  │
 │         │                 │                 │              │                │             │
 │         └─────────────────┴────────┬────────┴──────────────┴────────────────┘             │
 │                                    v                                                     │
 │                    ┌───────────────────────────────────┐                                  │
 │                    │    EventBus (Millisecond Latency)  │                                  │
 │                    │    Pub/Sub: signal.new, price.*,   │                                  │
 │                    │    smart_money.buy, kol.mention    │                                  │
 │                    └───────────────┬───────────────────┘                                  │
 └────────────────────────────────────┼─────────────────────────────────────────────────────┘
                                      │
 ┌────────────────────────────────────v─────────────────────────────────────────────────────┐
 │                              AI DECISION ENGINE                                          │
 │                                                                                          │
 │  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
 │  │  L1: Rule Engine ── Pure condition tree (AND/OR recursive) ── $0, instant         │  │
 │  │  L2: Fast Eval ──── Claude Sonnet single-call evaluation ── ~$0.003/call          │  │
 │  │  L3: Multi-Role ─── 3 Analysts (Haiku) + Bull/Bear 5-round debate (Sonnet)       │  │
 │  │                      + Facilitator arbitration ── ~$0.015/call                     │  │
 │  └────────────────────────────────────────────────────────────────────────────────────┘  │
 │                                                                                          │
 │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────────────────┐   │
 │  │  3-Layer Memory   │  │  Regime Detector  │  │  Risk Manager (15 checks)           │   │
 │  │  Working (24h)    │  │  CUSUM + HMM +    │  │  Position / Loss / Frequency /      │   │
 │  │  Episodic (14-30d)│  │  Rule Overlay     │  │  Token Safety / BTC Crash /         │   │
 │  │  Semantic (50 max)│  │  7 states         │  │  Chain Concentration + Breaker      │   │
 │  └──────────────────┘  └──────────────────┘  └──────────────────────────────────────┘   │
 └────────────────────────────────────┬─────────────────────────────────────────────────────┘
                                      │
 ┌────────────────────────────────────v─────────────────────────────────────────────────────┐
 │                              EXECUTION LAYER                                             │
 │                                                                                          │
 │  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
 │  │                     AVE Cloud Skills Infrastructure                                │  │
 │  │                                                                                    │  │
 │  │  ave-data-rest:          /tokens/trending     /contracts/{addr}   /tokens/price    │  │
 │  │                          /address/smart_wallet/list                                │  │
 │  │  ave-trade-chain-wallet: getAmountOut  createSolanaTx  sendSignedSolanaTx          │  │
 │  │                          createEvmTx   sendSignedEvmTx                             │  │
 │  └────────────────────────────────────────────────────────────────────────────────────┘  │
 │                                                                                          │
 │  ┌─────────────────────────┐  ┌──────────────────────────────────────────────────────┐  │
 │  │  Paper Trading Engine   │  │  Position Monitor                                    │  │
 │  │  Sim TP/SL 15%          │  │  Trailing stop, time-decay (MEME), CRISIS liquidate  │  │
 │  │  4 signal sources       │  │  EventBus price events + 30s DB poll                 │  │
 │  └─────────────────────────┘  └──────────────────────────────────────────────────────┘  │
 └──────────────────────────────────────────────────────────────────────────────────────────┘
```

**End-to-End Data Flow**:

```
Signal Sources (5) ──> EventBus (ms) ──> AI Decision (L1/L2/L3)
     │                                        │
     │                                  Memory + Regime + Risk
     │                                        │
     │                                   DecisionAgent
     │                                        │
     v                                        v
  Discovery ──────────────────────────> Execution (AVE)
                                              │
                                        Position Monitor
                                              │
                                        Reflection + Memory Update
```

---

## Module 1: Multi-Chain Hot Coin Scanner

Real-time trending token discovery across **Solana, BSC, Ethereum, Base**.

### Discovery Layer

Runs every **10 minutes** with two parallel data sources:

| Source | Endpoint | Coverage |
|--------|----------|----------|
| AVE Trending | `/tokens/trending` | 4 chains, multiple timeframes (5m/1h/4h/24h) |
| GeckoTerminal | `trending_pools` + `new_pools` | 4 chains, ~542 candidates per cycle |

Results are deduplicated and merged before entering the filter pipeline.

### Hard Filter (6 Gates)

Every candidate must pass all 6 gates or be rejected:

| # | Gate | Condition | Rationale |
|---|------|-----------|-----------|
| 1 | Token Age | 3 to 90 days | Too new = rug risk; too old = stale |
| 2 | Liquidity | $30,000 to $5,000,000 | Too thin = slippage; too deep = whale territory |
| 3 | Market Cap | $200,000 to $50,000,000 | Sweet spot for 10x potential |
| 4 | Volume 24h | >= $15,000 | Dead tokens filtered |
| 5 | Tax Rate | Buy tax < 10%, Sell tax < 10% | Honeypot protection |
| 6 | GoPlus Risk | No critical flags | Contract security |

### Scoring Model (0-100 Points)

**Total = M (Momentum, 50pts) + Q (Quality, 30pts) + P (Potential, 20pts)**

When KOL data is available, dimensions are reweighted:
**M (45pts) + Q (27pts) + P (18pts) + K (10pts) = 100**

#### M -- Momentum (50 points)

| Sub-Dimension | Max | Full Score Condition | Formula |
|---------------|-----|---------------------|---------|
| M1: Price Change 1h | 10 | >= +10% | Linear [0%, 10%] mapped to [0, 10]; drops beyond -5% incur mild penalty (0.3x) |
| M2: Price Change 24h | 10 | +30% to +300% | Linear [0%, 30%] mapped to [0, 10]; > 300% penalized as abnormal pump |
| M3: Volume Acceleration | 12 | 1h vol >= 3x avg hourly | `vol_1h / (vol_24h / 24)` linearly mapped [1x, 3x] to [0, 12] |
| M4: Buy Pressure | 10 | Buy ratio >= 75% | `buys_1h / (buys_1h + sells_1h)` linearly mapped [50%, 75%] to [0, 10]; 24h data as fallback (cap 7) |
| M5: Momentum Freshness | 8 | 1h accel >= 5x avg hourly | `pc_1h / (pc_24h / 24)` ratio >= 5 means breakout in progress; ratio < 1 penalized |

#### Q -- Quality (30 points)

| Sub-Dimension | Max | Full Score Condition | Formula |
|---------------|-----|---------------------|---------|
| Q1: Holder Count | 10 | >= 1,000 holders | Linear [150, 1000] mapped to [0, 10]; < 150 gets neutral 3 |
| Q2: Social Presence | 6 | Twitter(3) + Telegram(2) + Website(1) | Binary check per channel |
| Q3: Security Audit | 8 | No GoPlus flags, open-source, tax < 5% | Starts at 8; -4 for GoPlus risk, -2 for closed source, -2 for high tax |
| Q4: Holder Distribution | 6 | Top-10 concentration < 20% | `(1 - top10_pct)` linearly mapped [0.20, 0.80] to [0, 6] |

#### P -- Potential (20 points)

| Sub-Dimension | Max | Full Score Condition | Formula |
|---------------|-----|---------------------|---------|
| P1: Market Cap Position | 10 | Market cap at $200K floor | `1 - log10(mc / 200K) / log10(50M / 200K)` scaled to [0, 10]; lower mcap = higher score |
| P2: Token Age Sweet Spot | 4 | 7 to 30 days | Full 4 in [7, 30]; < 7 ramps from 3d; > 30 decays to 90d |
| P3: Multi-Timeframe Resonance | 6 | Present in all 4 timeframes | 4 TF hits = 6; 3 = 4; 2 = 2; 1 = 0 |

#### K -- KOL Dimension (10 points, when active)

| Sub-Dimension | Max | Condition |
|---------------|-----|-----------|
| K1: Mention Count | 4 | Number of unique KOLs mentioning token in 24h window |
| K2: Quality Weighted | 3 | Tier-weighted KOL quality (mega > large > medium > small) |
| K3: Sentiment Consensus | 3 | Uniformity of positive sentiment across mentions |

### Recommendation Grades

| Grade | Score Range | Action |
|-------|------------|--------|
| **strong** | >= 72 | High-priority signal, eligible for sim trade |
| **normal** | >= 50 | Listed on hot board |
| **skip** | < 50 | Rejected |

### Entry Condition

`score >= 50` AND no GoPlus critical risk flags.

### Exit Rules (any one triggers removal)

| # | Rule | Threshold |
|---|------|-----------|
| 1 | Low Score Streak | score < 35 for 3 consecutive evaluations |
| 2 | Pump-and-Dump | 24h change > 200% AND 1h change < -5% |
| 3 | Volume Drought | 1h volume < 10% of 24h average hourly volume |
| 4 | Sell Pressure Crush | Buy ratio < 35% |
| 5 | Disappearance | Not seen in discovery source for 5 consecutive scans |

Exited tokens continue to be tracked for 3 additional days to evaluate exit timing accuracy.

---

## Module 2: Pump.fun Inner Market Monitor

3-stage pipeline for Solana pump.fun tokens with bonding curve progress between 3% and 35%.

### Three-Stage Pipeline

```
Stage 1: WebSocket Full Capture
  PumpPortal WS ──> all new token creates ──> write to DB (pump_tokens)
  Zero-latency, zero-discard

       │ token mint created
       v

Stage 2: Trade Tracking (In-Memory)
  Subscribe to trade events per mint
  Track up to 20,000 tokens in memory (LRU eviction by age)
  Accumulate: buyer count, seller count, buy/sell volume, BC progress

       │ buyers >= 3 AND BC >= 2%
       v

Stage 3: On-Demand Enrichment
  REST detail fetch (delayed 5 seconds for data settlement)
  Concurrency semaphore: 20 parallel requests
  Enrichment cooldown: per-token rate limit
  Full feature extraction + scoring + signal pool check
```

### Hard Filter (4 Gates)

| # | Gate | Condition |
|---|------|-----------|
| 1 | Bonding Curve | 3% <= BC <= 35% |
| 2 | Unique Buyers | >= 3 |
| 3 | Not Graduated | Token still on inner market |
| 4 | Feature Completeness | Core fields populated after enrichment |

### Scoring Model (0-100 Points, 7 Dimensions + Bonus)

| Dimension | Weight | Calculation |
|-----------|--------|-------------|
| Buy/Sell Ratio | 25% | `buy_sell_ratio_vol` mapped linearly [1.0, 5.0] to [0, 25] |
| Smart Money Participation | 20% | Tier-weighted: elite(3x) + verified(1.5x) + watching(1x); normalized to 15pts + net SOL inflow up to 5pts |
| Inflow Acceleration | 15% | `inflow_acceleration >= 0.5` = full 15; linear [0, 0.5] below |
| Creator History | 15% | New creator = neutral 8; returning creator = `success_rate * 15` |
| Buyer Diversity | 10% | `unique_buyers` mapped linearly [10, 50] to [0, 10] |
| Social Completeness | 10% | Presence of Twitter, Telegram, website weighted similarly to Q2 |
| Progress Speed | 5% | Rate of bonding curve advancement |
| **Bonus** | varies | Smart money whale entry, KOL mention coincidence, volume spike |

### Signal Pool

- **Entry**: score >= 55 AND BC between 3% and 35%
- **Auto Sim Buy**: triggered on signal pool entry
- **Exit from Pool**: 30 minutes with no new trades, OR token age > 3 hours
- Recommendation tiers: strong >= 75, normal >= 55, skip < 55

---

## Module 3: Smart Money Tracker

**15,000+ wallet addresses** monitored in real time across 4 chains.

### Data Sources

**Solana -- Helius WebSocket (~400ms latency)**

Subscribes to `accountSubscribe` for 6 DEX program addresses:

| # | DEX Program | Purpose |
|---|-------------|---------|
| 1 | Raydium AMM | Largest SOL DEX |
| 2 | Jupiter Aggregator | Multi-hop routing |
| 3 | Pump.fun Bonding Curve | Inner market trades |
| 4 | Orca Whirlpool | Concentrated liquidity |
| 5 | Meteora DLMM | Dynamic liquidity |
| 6 | Raydium CLMM | Concentrated liquidity variant |

**EVM -- WebSocket `eth_subscribe` (BSC / ETH / Base)**

Subscribes to `logs` with Swap event topic:

```
Topic: 0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822
```

OKX Web3 Wallet API (`web3.okx.com`) used for transaction detail enrichment at 5-second polling intervals (average 2.5s detection latency, 20 req/s capacity).

### Wallet Supply Pipeline (3 Layers)

| Layer | Source | Volume |
|-------|--------|--------|
| 1 | Self-mined: `smart_wallet_miner.py` scans graduated token early buyers | ~12+ addresses/cycle |
| 2 | Hot Coin Top Holders: top 10 holders of tokens that achieve D3 >= 20% gain | Continuous |
| 3 | Dune Analytics: 4-chain queries (SOL #6850812, ETH #6858638, BSC #6858633, Base #6858622) | 17,307 candidates, ~15K imported |

### Heat Score Formula

```
heat_score = SUM(tier_weight[wallet_tier] * 1) + concentration_bonus

tier_weight:
  elite    = 5
  verified = 3
  watching = 1

concentration_bonus: applied when multiple wallets converge on same token in short window
```

### Signal Strength Levels

| Level | Condition | Action |
|-------|-----------|--------|
| **Strong** | heat >= 30 AND unique_buyers >= 5 | L2/L3 AI evaluation |
| **Medium** | heat >= 15 AND unique_buyers >= 3 | Sim buy triggered |
| **Weak** | heat >= 5 AND unique_buyers >= 1 | Watchlist only |

### v3 Five-Dimension Evaluation System

Every tracked wallet is periodically scored across 5 dimensions (total 100 points):

| Dimension | Weight | Metric |
|-----------|--------|--------|
| Win Rate | 25 | Percentage of profitable trades in last 14 days |
| PnL | 25 | Cumulative profit/loss ratio |
| Trade Volume | 20 | Average trade size in USD |
| Activity | 15 | Trades per week |
| Freshness | 15 | Recency of last trade (time decay) |

**Tier Thresholds**:

| Tier | Min Score | Behavior |
|------|-----------|----------|
| **elite** | >= 75 | Highest signal weight, priority monitoring |
| **verified** | >= 55 | Standard tracking |
| **watching** | >= 35 | Observation only |
| **blacklisted** | < 30 | Excluded from scoring |

- Evaluation cycle: every 2 hours
- Real-time bot detection (abnormal patterns auto-flag)
- 14-day degradation if inactive, 28-day removal if no trades

---

## Module 4: KOL Sentiment Engine

**212 KOLs** tracked, classified into 4 tiers.

### KOL Tiers and Weights

| Tier | Follower Range | Signal Weight |
|------|---------------|---------------|
| **mega** | > 500K followers | 4x |
| **large** | 100K - 500K | 3x |
| **medium** | 20K - 100K | 2x |
| **small** | 5K - 20K | 1x |

### Resonance Condition

**3+ KOLs** mention the same token within a 24-hour window. Resonance triggers elevated signal processing.

### Signal Strength Calculation (0-10 points)

| Dimension | Max | Calculation |
|-----------|-----|-------------|
| Quantity (K1) | 3 | Number of unique KOL mentions, capped |
| Quality (K2) | 3 | Tier-weighted average of mentioning KOLs |
| Sentiment (K3) | 2 | Average sentiment polarity (positive/negative/neutral) |
| Reach (K4) | 2 | Aggregate follower reach of mentioning KOLs |

**Push threshold**: signal_strength >= 5.0

### Integration into Hot Coin Scoring

The K dimension (10 points) is injected into the Hot Coin scoring model, reweighting the base dimensions:

| Dimension | Without KOL | With KOL |
|-----------|------------|----------|
| M (Momentum) | 50 | 45 |
| Q (Quality) | 30 | 27 |
| P (Potential) | 20 | 18 |
| K (KOL) | 0 | 10 |
| **Total** | **100** | **100** |

---

## Module 5: BTC/ETH Investment Agent

**50 indicators**, **5 composite scores**, powered by **13 free data collectors**.

### 13 Data Collectors

| # | Collector | Data Type | Source |
|---|-----------|-----------|--------|
| 1 | Binance WebSocket | Real-time price + trades | `wss://stream.binance.com` |
| 2 | Binance REST | Klines, order book, funding | `api.binance.com` |
| 3 | OKX REST | Funding rate, open interest | `okx.com` |
| 4 | CryptoPanic | News sentiment | `cryptopanic.com` |
| 5 | DeFiLlama | TVL, protocol flows | `api.llama.fi` |
| 6 | Blockchain.com (REST) | On-chain metrics (netflow, active addr) | `api.blockchain.info` |
| 7 | TwelveData | Macro indicators (DXY, SPX) | `twelvedata.com` |
| 8 | LunarCrush | Social metrics, Galaxy Score | `lunarcrush.com` |
| 9 | Coinalyze | Futures aggregates (OI, liquidations) | `coinalyze.net` |
| 10 | Mempool | BTC mempool stats, fee estimates | `mempool.space` |
| 11 | Alternative.me | Fear & Greed Index | `alternative.me` |
| 12 | Dune Analytics | On-chain analytics | `dune.com` |
| 13 | OKX REST (market) | Additional market depth | `okx.com` |

Coverage rate: 93-95% of indicator requirements met with free-tier API access.

### 5 Composite Scores (0-100 each)

| Score | Weight Components | Description |
|-------|------------------|-------------|
| **Momentum** | RSI(25%) + MACD(20%) + Price MA crossover(20%) + Volume trend(20%) + ATR expansion(15%) | Technical trend strength |
| **Sentiment** | Fear & Greed Index(30%) + News sentiment(25%) + Social volume(20%) + Funding rate(15%) + Long/Short ratio(10%) | Market emotion aggregate |
| **On-Chain** | Active addresses(25%) + Netflow(25%) + Exchange reserves(20%) + Whale movements(15%) + NVT ratio(15%) | Blockchain activity health |
| **Macro** | DXY inverse(30%) + SPX correlation(20%) + ETF flows(20%) + Bond yields(15%) + Gold correlation(15%) | External environment |
| **Risk** | Volatility percentile(25%) + Max drawdown(20%) + Liquidation cascades(20%) + Correlation breakdown(20%) + Black swan probability(15%) | Downside exposure |

### Technical Indicators (Computed Locally)

RSI (14-period), MACD (12/26/9), Bollinger Bands (20, 2-sigma), ATR (14-period), Moving Averages (7/25/99 EMA + 200 SMA), Support/Resistance levels (pivot point method).

### Signal Trigger Conditions

| Signal | Condition |
|--------|-----------|
| Oversold | RSI <= 30 AND sentiment score < 30 |
| Overbought | RSI >= 70 AND sentiment score > 70 |
| Extreme Funding | abs(funding_rate) > 0.1% for 3+ periods |
| Whale Accumulation | Exchange netflow < -5000 BTC (24h) |
| Macro Divergence | DXY drops > 1% while BTC flat |

---

## AI Decision Engine

### Three-Level Architecture

```
Signal Event Arrives (via EventBus)
        │
        v
   L1: Rule Engine
   Pure condition tree (AND/OR recursive evaluation)
   Cost: $0, Latency: < 1ms
   Pass conditions: all rules in strategy conditions tree evaluate true
        │
        │  Passes L1 threshold
        v
   L2: Fast Evaluation
   Single Claude Sonnet call with context injection
   Cost: ~$0.003/call
   Inputs: token data + working memory (last 10 events) + regime state
   Output: {action, confidence, reasoning}
        │
        │  Confidence >= 0.6 (buy) or >= 0.5 (sell) AND amount > $50
        v
   L3: Multi-Role Debate
   3 Analyst reports (Claude Haiku) + Bull/Bear debate (Claude Sonnet)
   Cost: ~$0.015/call
   Full pipeline described below
```

### L3 Multi-Role Debate Flow (5 Rounds)

```
Round 1: 3 Analyst Reports (Parallel, Claude Haiku)
  ├── Technical Analyst: RSI, MACD, support/resistance, volume profile
  ├── Sentiment Analyst: KOL mentions, news tone, social volume, FGI
  └── On-Chain Analyst: smart money flow, holder changes, whale activity

Round 2: Bull R1 (Claude Sonnet)
  Input: 3 analyst reports + memory context
  Output: 3 arguments for buying

Round 3: Bear R1 (Claude Sonnet)
  Input: 3 analyst reports + Bull R1 arguments
  Output: 3 counter-arguments against buying

Round 4: Bull R2 (Claude Sonnet)
  Input: Bear R1 arguments
  Output: 2-3 rebuttals + new evidence

Round 5: Bear R2 (Claude Sonnet)
  Input: Bull R2 response
  Output: 2-3 final counter-points

Facilitator (Claude Sonnet)
  Input: full debate log
  Output: {winner, confidence, action, risk, reasoning}
```

### DecisionAgent Final Checks

The `DecisionAgent` takes the Facilitator's conclusion and applies:

1. **Confidence gate**: Buy requires >= 0.6 confidence; Sell requires >= 0.5
2. **Regime adjustment**: Position multiplier scaled by current market state
3. **Memory rules**: Semantic memory rules checked for contradictions
4. **Existing position check**: Prevents duplicate buys on same token
5. **Final output**: `{action, confidence, reason, position_multiplier, skipped_reason}`

### Three-Layer Memory System

| Layer | Storage | Max Size | TTL | Injection |
|-------|---------|----------|-----|-----------|
| **Working Memory** | In-memory deque | 200 events | 24h sliding window | Last 10 events injected into every L2/L3 prompt |
| **Episodic Memory** | Supabase `agent_memory` | 200 records | trade_review: 14d, market_pattern: 30d, risk_lesson: 30d | Top 3 by relevance score injected per decision |
| **Semantic Memory** | Supabase `agent_memory` | 50 active rules | Stale after 30 days unmatched | Top 10 by relevance injected per decision |

**Episodic Relevance Scoring**: trigger_source(+3) > chain(+2) = regime(+2) = mcap_bucket(+2) > pnl(+1). 30-second cache.

**Semantic Rule Lifecycle**:
- **Promotion**: 3+ reflection appearances AND >= 5 trade samples AND compliance win-rate leads by >= 15 percentage points
- **Deprecation**: Compliance win-rate < 40% (with >= 10 samples) OR 30 days with no match
- Refresh: every 5 minutes from DB

**Reflection Schedule**:
- Daily reflection at UTC 20:00
- Emergency reflection triggered on -25% portfolio loss in single day

### Regime Detector

Three-stage hybrid detection across multiple assets (BTC, SOL, ETH):

**Stage 1: CUSUM Change-Point Detection (Event-Driven)**

| Parameter | BTC | SOL | ETH |
|-----------|-----|-----|-----|
| h threshold | 3 sigma | 2.5 sigma | 3 sigma |
| k factor | Configurable via `CUSUM_K_FACTOR` | Same | Same |
| Window | `CUSUM_WINDOW` (configurable) | Same | Same |

Detects structural price change using cumulative sum of log-returns. Triggers HMM re-classification.

**Stage 2: HMM State Classification (Every 30 min + CUSUM trigger)**

Feature vector: `[1h_returns, volume_change, ATR_14/MA_ATR_14, funding_rate]`
StandardScaler normalization, 4-state Gaussian HMM, score_samples probability, label calibration.
Minimum 48 samples (2 days) required for HMM training. Rule engine used as baseline when HMM data is insufficient.

**Stage 3: LLM Narrative (On regime change only)**

Claude generates human-readable explanation of why the regime changed and what strategy adjustments are recommended.

**7 Regime States + Position Multiplier Table**

| State | Source | Position Multiplier | Description |
|-------|--------|-------------------|-------------|
| TRENDING_UP | HMM | 1.2x | Sustained upward momentum |
| BREAKOUT | Rule overlay | 1.5x | Sharp move above resistance with volume |
| RANGING | HMM | 0.8x | Sideways consolidation |
| HIGH_VOLATILITY | HMM | 0.5x | Elevated ATR, unclear direction |
| TRENDING_DOWN | HMM | 0.3x | Sustained downward pressure |
| CRISIS | Rule overlay (1min) | 0.0x | Auto-close all positions, block all new buys |
| RECOVERY | Rule overlay | 0.6x | Bounce from crisis, cautious re-entry |

CRISIS detection runs independently on a 1-minute rule engine (does not wait for HMM cycle).

### Risk Manager (15 Checks)

| # | Check | Threshold | Action on Fail |
|---|-------|-----------|----------------|
| 1 | Max Position Size | Configurable via `RISK_MAX_POSITION_USD` | Block |
| 2 | Portfolio Concentration | Single position < 10% of portfolio | Block |
| 3 | Open Position Count | <= 20 positions | Block |
| 4 | Per-Trade Loss Limit | Stop-loss at 30% | Warn |
| 5 | Daily Loss Limit | Configurable via `RISK_DAILY_LOSS_LIMIT` | Block + Circuit Breaker |
| 6 | Weekly Loss Limit | Configurable via `RISK_WEEKLY_LOSS_LIMIT` | Block + Circuit Breaker |
| 7 | Max Drawdown | Configurable via `RISK_MAX_DRAWDOWN_PCT` | Block + Circuit Breaker |
| 8 | Hourly Trade Frequency | <= 5 trades/hour | Block |
| 9 | Daily Trade Frequency | <= 20 trades/day | Block |
| 10 | Minimum Trade Interval | >= 60 seconds between trades | Block |
| 11 | Minimum Liquidity | >= $10,000 pool liquidity | Block |
| 12 | Buy Tax | < 10% | Block |
| 13 | Sell Tax | < 10% | Block |
| 14 | BTC Market Crash | BTC drops > threshold in short window | Block all altcoin buys |
| 15 | Chain Concentration | Max exposure per chain | Warn |

**Circuit Breaker**: Triggered by checks 5/6/7. Cooldown period: 60 minutes. All trading halted until cooldown expires or manual override.

**Honeypot Protection**: Mandatory check via AVE `/contracts/{addr}` endpoint. Block if honeypot flag detected. Top-10 holder concentration must be < 80%.

**Risk Event Logging**: All block and warn events are recorded to `agent_risk_events` table with full context (chain, token, amount, price at event).

---

## Execution Layer

### AVE Cloud Skills API Endpoints

All on-chain data retrieval and trade execution use AVE Cloud Skills as the native infrastructure layer.

| Skill | Base URL | Endpoint | Purpose |
|-------|----------|----------|---------|
| **ave-data-rest** | `data.ave-api.xyz/v2` | `/tokens/trending` | Hot coin discovery (4 chains, multiple timeframes) |
| | | `/contracts/{address}-{chain}` | Honeypot detection, tax rates, GoPlus risk flags |
| | | `/tokens/{address}-{chain}` | Real-time price, market cap, volume, holder data |
| | | `/tokens/price` | Batch price queries |
| | | `/address/smart_wallet/list` | Smart money wallet directory |
| **ave-trade-chain-wallet** | `bot-api.ave.ai` | `chainWallet/getAmountOut` | Swap quote (price impact, route, output amount) |
| | | `chainWallet/createSolanaTx` | Build unsigned Solana swap transaction |
| | | `chainWallet/sendSignedSolanaTx` | Submit signed Solana transaction |
| | | `chainWallet/createEvmTx` | Build unsigned EVM swap transaction |
| | | `chainWallet/sendSignedEvmTx` | Submit signed EVM transaction |

Rate limit: AVE Free plan at 1 RPS with client-side throttle (`asyncio.Lock` + 1-second minimum gap).

### Trade Execution Flow

```
1. Quote Phase
   ├── chainWallet/getAmountOut
   ├── Returns: output amount, price impact, route path
   └── Abort if price impact > 5%

2. Transaction Creation
   ├── chainWallet/createSolanaTx (or createEvmTx)
   └── Returns: unsigned transaction bytes

3. Local Signing
   ├── User's private key signs transaction locally
   └── Key never leaves the backend process

4. Submission
   ├── chainWallet/sendSignedSolanaTx (or sendSignedEvmTx)
   └── Returns: transaction hash

5. Confirmation
   ├── Poll for on-chain confirmation
   └── Record execution in agent_executions table
```

### DEX Routing

| Chain | Primary Router | Secondary |
|-------|---------------|-----------|
| Solana | AVE chainWallet | Jupiter (`jupiter.py`) |
| BSC | AVE chainWallet | 1inch (`oneinch.py`) |
| Ethereum | AVE chainWallet | 1inch (`oneinch.py`) |
| Base | AVE chainWallet | 1inch (`oneinch.py`) |

### Paper Trading Engine

Simulated trading for strategy validation before live deployment.

| Parameter | Value |
|-----------|-------|
| Default TP | 15% |
| Default SL | 15% |
| Signal Sources | pump, hot_coin, smart_money, kol |
| Portfolio Tracking | Full PnL, win rate, Sharpe ratio |
| Storage | `hot_sim_trades` + `agent_paper_trades` tables |

### Position Monitor

Continuously watches all open positions for exit conditions:

| Exit Type | Trigger | Behavior |
|-----------|---------|----------|
| Stop Loss | Price drops >= SL% from entry | Immediate market sell |
| Take Profit | Price rises >= TP% from entry | Immediate market sell |
| Trailing Stop | Price drops 15% from peak (activated after +50% gain) | Market sell at trailing level |
| Time Decay (MEME) | MEME tokens held > configured hours with no profit growth | Gradual position reduction |
| CRISIS Liquidation | Regime enters CRISIS state | Close all positions immediately |

Event sources: EventBus price events (millisecond latency) + 30-second DB poll as safety net.

---

## Strategy Templates

5 preset templates that users can deploy immediately or customize via parameter overrides.

### 1. MEME Sniper (`meme_sniper`)

| Parameter | Value |
|-----------|-------|
| **Description** | Early-stage pump.fun token with smart money entry at BC 5-15% |
| **Trigger** | BC 5-15% AND smart_money_count >= 2 AND score >= 70 |
| **Buy Amount** | $50 |
| **Stop Loss** | 25% |
| **Take Profit** | 100% |
| **Cooldown** | 30 minutes |
| **Chains** | Solana only |

### 2. Hot Breakout (`hot_breakout`)

| Parameter | Value |
|-----------|-------|
| **Description** | High-scoring hot coin with 24h momentum exceeding 30% |
| **Trigger** | hot_score >= 65 AND price_change_24h > 30% AND volume_24h >= $50K |
| **Buy Amount** | $80 |
| **Stop Loss** | 20% |
| **Take Profit** | 80% |
| **Cooldown** | 60 minutes |
| **Chains** | Solana, BSC, Base, Ethereum |

### 3. Smart Money Follow (`smart_money_follow`)

| Parameter | Value |
|-----------|-------|
| **Description** | Follow elite-tier smart wallet buy signals with liquidity check |
| **Trigger** | wallet_tier == "elite" AND action == "buy" AND liquidity > $50K |
| **Buy Amount** | $60 |
| **Stop Loss** | 30% |
| **Take Profit** | 150% |
| **Cooldown** | 30 minutes |
| **Chains** | Solana, BSC, Base, Ethereum |

### 4. KOL Sentiment (`kol_sentiment`)

| Parameter | Value |
|-----------|-------|
| **Description** | Multiple KOLs converge on same token with positive sentiment |
| **Trigger** | mention_count_2h >= 3 AND avg_sentiment > 0.5 AND score > 50 |
| **Buy Amount** | $40 |
| **Stop Loss** | 20% |
| **Take Profit** | 60% |
| **Cooldown** | 120 minutes |
| **Chains** | Solana, BSC, Base, Ethereum |

### 5. Conservative DCA (`conservative_dca`)

| Parameter | Value |
|-----------|-------|
| **Description** | Daily buy when market sentiment is fearful |
| **Trigger** | fear_greed_index < 40 AND cron schedule (daily UTC 10:00) |
| **Buy Amount** | $20 |
| **Stop Loss** | 15% |
| **Take Profit** | 50% |
| **Cooldown** | 1440 minutes (24 hours) |
| **Chains** | Solana |

**Overridable Parameters**: `amount_usd` ($1-$10,000), `stop_loss_pct` (1-100%), `take_profit_pct` (1-10,000%), `cooldown_minutes` (min 5), `chains`.

---

## AVE Cloud Skill Integration

All data querying, risk assessment, and trade execution are powered by **AVE Cloud Skills** as the native infrastructure layer.

| Skill | Package | Capabilities |
|-------|---------|-------------|
| **ave-data-rest** | Token data, contract security, smart wallet lists | Trending tokens, batch pricing, honeypot detection, GoPlus risk, holder data |
| **ave-trade-chain-wallet** | Self-custody DEX swaps | Quote, build TX, sign locally, submit to chain (SOL + EVM) |

The unified client (`ave_client.py`) handles:
- 1 RPS rate limiting with async lock
- Chain name normalization (solana/bsc/base/eth/ethereum)
- Error handling with structured logging
- Session management and connection pooling

See [docs/ave-skill-integration.md](docs/ave-skill-integration.md) for full integration details.

---

## Project Structure

```
services/pump-scanner/                    # Core backend service
  main.py                                 # Entry point: scheduler + event loop startup
  config.py                               # All configuration constants + env var loading
  ave_client.py                           # AVE Cloud API unified client (1 RPS throttle)
  database.py                             # Supabase client + DB helper functions
  
  # ── Signal Source: Hot Coins ──
  hot_coin_manager.py                     # Real-time entry/exit manager with PriceFeed callbacks
  hot_coin_fetcher.py                     # Token discovery (AVE trending + GeckoTerminal)
  hot_coin_job.py                         # Scheduled hot coin refresh job
  hot_scorer.py                           # 100-point scoring model (M+Q+P dimensions)
  hot_sim_trader.py                       # Simulated trader for hot coins (TP/SL 15%)
  gecko_discovery.py                      # GeckoTerminal trending + new_pools discovery
  price_feed.py                           # Unified price service (AVE + Binance WS)
  performance_tracker.py                  # Token performance tracking (D0-D30 daily highs)
  
  # ── Signal Source: Pump.fun ──
  collector.py                            # 3-stage pipeline (WS capture + trade track + enrich)
  features.py                             # Feature extraction + hard filter
  scorer.py                               # Rule-based scoring (7 dimensions + bonus)
  pump_stats.py                           # Pump statistics aggregator
  pump_report_job.py                      # Daily pump report generator
  creator_stats_updater.py                # Creator history tracker
  scanner_ref.py                          # Reference data for scanner
  
  # ── Signal Source: Smart Money ──
  smart_money_tracker.py                  # Multi-chain tracker (Helius WS + OKX Web3 API)
  smart_wallet_miner.py                   # Graduated-token early buyer mining
  smart_wallet_seed.py                    # Initial wallet seed data
  smart_wallet_updater.py                 # v3 five-dimension evaluation updater
  dune_wallet_importer.py                 # Dune Analytics 4-chain wallet importer
  routes_smart_money.py                   # Smart money API routes
  
  # ── Signal Source: KOL ──
  kol_collector.py                        # KOL tweet collector
  kol_analyzer.py                         # Mention analysis + NLP sentiment
  kol_scorer.py                           # K-dimension scoring (10pts, 3 sub-dims)
  kol_signal_detector.py                  # Resonance detection (3+ KOLs)
  kol_config.py                           # KOL tier config + weights
  kol_job.py                              # Scheduled KOL scan job
  kol_seed.py                             # Initial 212 KOL seed data
  
  # ── AI Agent ──
  agent/
    event_bus.py                          # Pub/Sub event bus (millisecond dispatch)
    event_listener.py                     # EventBus subscriber, triggers strategy evaluation
    llm_parser.py                         # Natural language -> strategy JSON (Claude tool use)
    strategy_manager.py                   # Strategy CRUD + lifecycle management
    evaluator.py                          # Condition tree evaluation (AND/OR recursive)
    rule_engine.py                        # L1 pure rule engine
    decision_agent.py                     # Final decision (confidence + regime + memory)
    multi_role_orchestrator.py            # L3 orchestrator (analysts + debate + facilitator)
    debate.py                             # Bull/Bear 5-round debate engine (Sonnet)
    analysts/
      technical.py                        # Technical analysis (RSI, MACD, BB) via Haiku
      sentiment.py                        # Sentiment analysis via Haiku
      onchain.py                          # On-chain analysis via Haiku
    risk_manager.py                       # 15 risk checks + circuit breaker
    risk_reviewer.py                      # Post-trade risk review
    trade_executor.py                     # DEX execution via AVE chainWallet
    dex_router.py                         # Multi-DEX routing orchestrator
    dex/
      jupiter.py                          # Jupiter (Solana) integration
      oneinch.py                          # 1inch (EVM) integration
    paper_engine.py                       # Paper trading engine (sim portfolio)
    position_monitor.py                   # Auto SL/TP/trailing stop monitor
    monitor_job.py                        # 30s position monitor polling job
    memory/
      working_memory.py                   # Short-term: 200-event deque, 24h window
      episodic_memory.py                  # Mid-term: DB-backed, relevance scoring
      semantic_memory.py                  # Long-term: 50 rules, promotion/deprecation
      reflection.py                       # Daily + emergency reflection engine
      cron_tasks.py                       # Memory maintenance scheduled tasks
    regime_detector.py                    # CUSUM + HMM + rule overlay (7 states)
    templates.py                          # 5 preset strategy templates
    backtester.py                         # Historical backtest engine (7-day window)
    proactive_scanner.py                  # AI proactive recommendation scanner
    performance_analytics.py              # Win rate, PnL, max drawdown, Sharpe ratio
    ab_test_manager.py                    # A/B testing for strategy variants
    action_dispatcher.py                  # Action routing (buy/sell/hold dispatch)
    push_service.py                       # Push notification service
    schemas.py                            # Pydantic schemas for agent data models
  
  # ── BTC/ETH Investment ──
  btc_eth/
    manager.py                            # BTC/ETH module orchestrator
    config.py                             # BTC/ETH specific configuration
    storage.py                            # Indicator + signal storage layer
    indicators/                           # Technical indicator computation
    analysis/                             # Cycle analyzer + signal generator + reports
    paper_trading/                        # BTC/ETH paper trading engine
    collectors/
      binance_ws.py                       # Binance WebSocket (real-time price/trades)
      binance_rest.py                     # Binance REST (klines, funding, OI)
      okx_rest.py                         # OKX REST (funding, OI)
      cryptopanic.py                      # CryptoPanic news sentiment
      defilama.py                         # DeFiLlama TVL + protocol flows
      blockchain_onchain.py               # Blockchain.com on-chain metrics (REST)
      twelve_data.py                      # TwelveData macro (DXY, SPX)
      lunarcrush.py                       # LunarCrush social metrics
      coinalyze.py                        # Coinalyze futures aggregates
      mempool.py                          # Mempool.space BTC mempool stats
      alternative_me.py                   # Alternative.me Fear & Greed Index
      dune_onchain.py                     # Dune Analytics on-chain queries
      blockchain_ws.py                    # Blockchain.com WS (disabled: event loop blocking)
  
  # ── Optimizer Agents ──
  optimizer_agent.py                      # Claude Opus AI optimizer (pump + hot alternating)
  optimizer_tools.py                      # Optimizer analysis + backtest tools
  
  # ── Infrastructure ──
  okx_market_client.py                    # OKX market data client
  bitget_market_client.py                 # Bitget market data client
  push_service.py                         # Firebase push notification service
  daily_job.py                            # Daily maintenance jobs
  db_cleanup.py                           # Database cleanup (every 6h)
  governor.py                             # Rate governor / global throttle
  outcome_labeler.py                      # Trade outcome labeling for ML
  backtest.py                             # Standalone backtest runner
  ml_config.py                            # ML scoring configuration
  ml_scorer.py                            # XGBoost ML scorer (pending training)
  ml_trainer.py                           # ML model training pipeline
  backfill_images.py                      # Token image backfill utility
  
  # ── API Layer ──
  api/
    app.py                                # FastAPI application factory
    auth.py                               # Authentication middleware
    geo_middleware.py                      # CN IP geo-blocking middleware
    routes_pump.py                        # Pump.fun signal endpoints
    routes_data.py                        # General data endpoints
    routes_agent.py                       # Agent strategy + execution endpoints
    routes_price.py                       # Price query endpoints
    routes_token.py                       # Token detail endpoints (top holders, fund flow)
    routes_btc_eth.py                     # BTC/ETH dashboard + signals + alerts
    routes_optimizer.py                   # Optimizer agent endpoints
    routes_backtest.py                    # Backtest API endpoints
    routes_risk.py                        # Risk management endpoints
    routes_device.py                      # Device token registration (push)
    routes_webhook.py                     # Webhook endpoints
    routes_smart_money.py                 # (in parent dir) Smart money API
  
  # ── Database ──
  migrations/                             # SQL migration files (007-033)
  data/                                   # Static data files
  tests/                                  # Test suite
  models/                                 # Data models
  requirements.txt                        # Python dependencies

apps/app/                                 # Flutter mobile app (iOS/Android)
  lib/
    screens/                              # All UI screens
    providers/                            # State management (locale, theme)
    services/                             # API service layer
    l10n/                                 # i18n: zh/en/ja/ko (275+ strings)
    models/                               # Data models

apps/portal/                              # Next.js admin portal
  src/
    app/                                  # Pages (hot, pump, agent, optimizer, smart-money)
    components/                           # Shared UI components
```

---

## Tech Stack

| Layer | Technology | Details |
|-------|-----------|---------|
| **Backend** | Python 3.9+, FastAPI, APScheduler, asyncio | 20+ API endpoints, WebSocket support |
| **Database** | Supabase (PostgreSQL) | 30+ tables, row-level security, 6h cleanup cycle |
| **Real-Time Data** | Helius WS, Binance WS, EVM WS (`eth_subscribe`) | Sub-second price feeds |
| **AI Models** | Claude Sonnet 4 (decision, debate), Claude Haiku 4.5 (analysts), Claude Opus 4.6 (optimizer) | Multi-model cost optimization |
| **Data and Trading** | AVE Cloud Skills (`ave-data-rest` + `ave-trade-chain-wallet`) | Token data, contract security, DEX execution |
| **DEX Routing** | AVE chainWallet (primary), Jupiter (SOL), 1inch (EVM) | Multi-path routing |
| **Mobile** | Flutter (iOS/Android) | i18n 4 languages, real-time signal feed |
| **Admin Portal** | Next.js | Performance dashboards, optimizer approval workflow |
| **Deployment** | Ubuntu server, systemd, nginx reverse proxy | Backend :8000, Portal :3000 |
| **Smart Money** | Helius WS (SOL), OKX Web3 API (EVM), Dune Analytics (supply) | 15K+ wallets, v3 evaluation |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AVE_API_KEY` | Yes | AVE Cloud API key from [cloud.ave.ai](https://cloud.ave.ai) |
| `AVE_DATA_BASE` | No | AVE data REST base URL (default: `https://data.ave-api.xyz/v2`) |
| `AVE_TRADE_BASE` | No | AVE trade base URL (default: `https://bot-api.ave.ai`) |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key |
| `ANTHROPIC_API_KEY` | Yes | Claude API key for AI Agent (Sonnet + Haiku + Opus) |
| `HELIUS_API_KEY` | Yes | Helius RPC key for Solana WebSocket + RPC |
| `OKX_API_KEY` | Yes | OKX API key for market data + Web3 wallet API |
| `OKX_SECRET_KEY` | Yes | OKX API secret |
| `OKX_PASSPHRASE` | Yes | OKX API passphrase |
| `DUNE_API_KEY` | No | Dune Analytics API key (for smart wallet import) |
| `GECKO_API_KEY` | No | GeckoTerminal API key (optional, free tier works) |
| `RISK_MAX_POSITION_USD` | No | Max single position size in USD |
| `RISK_DAILY_LOSS_LIMIT` | No | Max daily loss before circuit breaker |
| `RISK_WEEKLY_LOSS_LIMIT` | No | Max weekly loss before circuit breaker |
| `RISK_MAX_DRAWDOWN_PCT` | No | Max portfolio drawdown percentage |
| `CUSUM_H_BTC` | No | CUSUM threshold for BTC (default: 3.0) |
| `CUSUM_H_SOL` | No | CUSUM threshold for SOL (default: 2.5) |
| `CUSUM_H_ETH` | No | CUSUM threshold for ETH (default: 3.0) |
| `CUSUM_K_FACTOR` | No | CUSUM k factor |
| `CUSUM_WINDOW` | No | CUSUM lookback window size |
| `REGIME_SHADOW_MODE` | No | Run regime detector in shadow mode (log only) |
| `USE_ML_SCORING` | No | Enable XGBoost ML scoring (default: 0, rules-based) |

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/meiyaobuyao123-hash/Agent-Trading.git
cd Agent-Trading

# Backend setup
cd services/pump-scanner
pip install -r requirements.txt
cp .env.example .env              # Configure all API keys listed above

# Start the backend (all services launch from main.py)
python main.py

# In another terminal: Portal
cd apps/portal
npm install && npm run build
npm start                          # Serves on :3000

# Flutter app (iOS simulator)
cd apps/app
flutter pub get
flutter run -d <device-id> \
  --dart-define=API_BASE_URL=http://<server-ip> \
  --dart-define=HELIUS_API_KEY=<your-key>
```

---

## License

MIT
