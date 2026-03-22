# TECH-004: 中等问题合集 — 技术方案

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-004 |
| 创建日期 | 2026-03-22 |

---

## M-01: trigger_count TOCTOU 修复

### 当前代码

```python
# agent/strategy_manager.py:245-253
# RPC fallback: read → +1 → write（竞态）
res = db.table("strategies").select("trigger_count").eq("id", sid).execute()
count = res.data[0]["trigger_count"]
db.table("strategies").update({"trigger_count": count + 1}).eq("id", sid).execute()
```

### 修复方案

在 Supabase Dashboard 创建 RPC function：

```sql
CREATE OR REPLACE FUNCTION increment_trigger_count(strategy_id UUID)
RETURNS void AS $$
BEGIN
    UPDATE strategies
    SET trigger_count = trigger_count + 1,
        last_triggered = NOW()
    WHERE id = strategy_id;
END;
$$ LANGUAGE plpgsql;
```

Python 调用：

```python
db.rpc("increment_trigger_count", {"strategy_id": str(sid)}).execute()
```

**影响**: `agent/strategy_manager.py` 一处修改

---

## M-02: LLM Parser 重试

### 修复方案

```python
# agent/llm_parser.py parse_strategy() 方法

MAX_RETRIES = 3
RETRY_DELAYS = [5, 10, 20]  # 秒

async def parse_strategy(self, user_message: str, context: dict = None) -> Optional[dict]:
    for attempt in range(MAX_RETRIES):
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._system_prompt,
                tools=self._tools,
                messages=[{"role": "user", "content": user_message}],
            )
            return self._extract_strategy(response)
        except (anthropic.RateLimitError, anthropic.InternalServerError) as e:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                log.warning(f"LLM Parser retry {attempt+1}: {e}, wait {delay}s")
                await asyncio.sleep(delay)
            else:
                log.error(f"LLM Parser all {MAX_RETRIES} retries failed: {e}")
                return None
        except Exception as e:
            log.error(f"LLM Parser unexpected error: {e}")
            return None
```

**影响**: `agent/llm_parser.py` 一处修改

---

## M-03: 硬编码参数提取

### 修复方案

在 `config.py` 末尾新增：

```python
# ── Agent 配置 ─────────────────────────────────────────────
SIGNAL_POOL_MIN_SCORE = int(os.getenv("SIGNAL_POOL_MIN_SCORE", "55"))
SIGNAL_POOL_BC_MIN = float(os.getenv("SIGNAL_POOL_BC_MIN", "3"))
SIGNAL_POOL_BC_MAX = float(os.getenv("SIGNAL_POOL_BC_MAX", "35"))
AGENT_MONTHLY_QUOTA = int(os.getenv("AGENT_MONTHLY_QUOTA", "20"))

# ── 风控配置 ─────────────────────────────────────────────
RISK_DAILY_LOSS_LIMIT = float(os.getenv("RISK_DAILY_LOSS_LIMIT", "50"))
RISK_WEEKLY_LOSS_LIMIT = float(os.getenv("RISK_WEEKLY_LOSS_LIMIT", "200"))
RISK_MAX_POSITION_USD = float(os.getenv("RISK_MAX_POSITION_USD", "100"))
RISK_MAX_DRAWDOWN_PCT = float(os.getenv("RISK_MAX_DRAWDOWN_PCT", "20"))
RISK_BTC_CRISIS_PCT = float(os.getenv("RISK_BTC_CRISIS_PCT", "3"))
RISK_TRAILING_STOP_ACTIVATION = float(os.getenv("RISK_TRAILING_STOP_ACTIVATION", "15"))

# ── BTC/ETH 信号配置 ─────────────────────────────────────
SIGNAL_COOLDOWN_HOURS = int(os.getenv("SIGNAL_COOLDOWN_HOURS", "4"))
DEPTH_IMBALANCE_THRESHOLD = float(os.getenv("DEPTH_IMBALANCE_THRESHOLD", "0.3"))
```

**影响**:
- `config.py` 新增 ~15 行
- `collector.py` 引用 `SIGNAL_POOL_MIN_SCORE` 等
- `agent/risk_manager.py` 引用 `RISK_*` 常量
- `agent/routes_agent.py` 引用 `AGENT_MONTHLY_QUOTA`
- `btc_eth/analysis/signal_generator.py` 引用 `SIGNAL_COOLDOWN_HOURS`

---

## M-04: btc_eth_indicators 表为空

### 排查步骤

1. 检查 `btc_eth/manager.py` 中 `_persist_indicators` 是否在 `start()` 中被 `asyncio.create_task()`
2. 检查 `btc_eth/storage.py` `save_indicators()` 是否有 try/except 吞异常
3. 检查列名是否与 migration 025 一致

### 可能修复

```python
# btc_eth/manager.py start() 中确保有：
asyncio.create_task(self._persist_loop())

async def _persist_loop(self):
    """每 5 分钟持久化指标到 DB"""
    while True:
        try:
            await asyncio.sleep(300)  # 5min
            for asset in ["BTC", "ETH"]:
                snapshot = self.indicator_engine.get_snapshot(asset)
                if snapshot and snapshot.get("price_usd", 0) > 0:
                    save_indicators(asset, snapshot)
                    log.info(f"[BtcEth] 指标持久化: {asset} price=${snapshot['price_usd']}")
        except Exception as e:
            log.error(f"[BtcEth] 指标持久化失败: {e}")
```

**影响**: `btc_eth/manager.py` + `btc_eth/storage.py`

---

## M-05: Paper Trading SL/TP 检查

### 修复方案

在 `btc_eth/manager.py` 的 signal tracking loop 中加入：

```python
# _track_signals 循环中（已有）
async def _track_signals(self):
    while True:
        await asyncio.sleep(60)  # 每分钟检查
        try:
            prices = {
                "BTC": self.indicator_engine.get_price("BTC"),
                "ETH": self.indicator_engine.get_price("ETH"),
            }
            # 已有：信号价格追踪（1h/4h/12h/24h/72h）
            await self._update_signal_prices(prices)

            # 新增：模拟盘止盈止损检查
            from btc_eth.paper_trading.engine import paper_engine
            await paper_engine.check_exits(prices)
        except Exception as e:
            log.error(f"[BtcEth] Signal tracking error: {e}")
```

`check_exits` 实现：

```python
async def check_exits(self, current_prices: dict):
    """检查所有 open 的模拟交易，触发 SL/TP"""
    db = get_db()
    open_trades = db.table("btc_eth_paper_trades") \
        .select("*").eq("status", "open").execute()

    for trade in (open_trades.data or []):
        asset = trade["asset"]
        price = current_prices.get(asset, 0)
        if price <= 0:
            continue

        entry = trade["entry_price"]
        sl = trade.get("stop_loss", 0)
        tp = trade.get("take_profit", 0)
        side = trade["side"]

        hit_tp = (side == "long" and tp > 0 and price >= tp) or \
                 (side == "short" and tp > 0 and price <= tp)
        hit_sl = (side == "long" and sl > 0 and price <= sl) or \
                 (side == "short" and sl > 0 and price >= sl)

        if hit_tp or hit_sl:
            pnl_pct = ((price - entry) / entry * 100) if side == "long" else ((entry - price) / entry * 100)
            pnl_usd = trade["amount_usd"] * pnl_pct / 100

            db.table("btc_eth_paper_trades").update({
                "status": "closed",
                "exit_price": price,
                "pnl_pct": round(pnl_pct, 2),
                "pnl_usd": round(pnl_usd, 2),
                "closed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", trade["id"]).execute()

            # 更新 portfolio equity
            ...
```

**影响**: `btc_eth/manager.py` + `btc_eth/paper_trading/engine.py`

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-22 | 初始版本 |
