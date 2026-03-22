# TECH-001: Agent 卖出执行 — 技术方案

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-001-sell-execution-v1.0 |
| 创建日期 | 2026-03-22 |

---

## 一、现有代码分析

### 1.1 买入流程（已实现，参考）

```
agent/trade_executor.py → execute_trade()
  ├─ 1. resolve_wallet(): 获取钱包地址 + 私钥
  ├─ 2. determine_tokens(): fromToken=USDC, toToken=目标代币
  ├─ 3. get_swap_data(): OKX DEX v6 /swap 接口
  ├─ 4. sign_tx(): SOL(solders) / EVM(eth_account)
  ├─ 5. broadcast_tx(): RPC sendTransaction
  └─ 6. record_execution(): 写入 strategy_executions 表
```

### 1.2 卖出与买入的差异

| 步骤 | 买入 | 卖出 |
|------|------|------|
| fromToken | USDC/SOL/ETH（稳定币） | **目标代币** |
| toToken | 目标代币 | USDC/SOL/ETH |
| 金额 | 用户指定 USD 金额 | **需查链上余额** |
| approve | 不需要（原生币/USDC已授权） | **EVM 需 approve（首次）** |
| 滑点风险 | 中 | **高（小币流动性差）** |

---

## 二、技术方案

### 2.1 整体架构

```
卖出触发源：
  ├─ 止盈（price >= entry × (1 + tp_pct)）
  ├─ 止损（price <= entry × (1 - sl_pct)）
  ├─ 追踪止损（price <= peak × (1 - trail_pct)）
  └─ 手动指令（用户 chat "卖出 XXX"）
       ↓
  PositionMonitor（新模块）
       ↓
  trade_executor.execute_sell()
       ↓
  ┌─ query_balance()    # 查链上代币余额
  ├─ approve_if_needed() # EVM 首次需 approve
  ├─ get_swap_data()     # OKX DEX swap（反向）
  ├─ sign_tx()           # 签名
  ├─ broadcast_tx()      # 广播
  └─ record_sell()       # 记录 + 计算 PnL
```

### 2.2 新增文件

| 文件 | 职责 |
|------|------|
| `agent/position_monitor.py` | **新建** — 持仓监控，检查 SL/TP/Trailing |
| `agent/trade_executor.py` | **修改** — 新增 `execute_sell()` + `query_balance()` + `approve_if_needed()` |
| `agent/event_listener.py` | **修改** — 订阅价格事件触发 SL/TP |
| `agent/monitor_job.py` | **修改** — 30s fallback 增加持仓检查 |

### 2.3 持仓余额查询

#### SOL（Helius RPC）

```python
async def query_sol_token_balance(wallet: str, token_mint: str) -> float:
    """查询 SOL 链上 SPL 代币余额"""
    payload = {
        "jsonrpc": "2.0", "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet,
            {"mint": token_mint},
            {"encoding": "jsonParsed"}
        ]
    }
    # response.result.value[0].account.data.parsed.info.tokenAmount.uiAmount
```

#### EVM（RPC `eth_call`）

```python
async def query_evm_token_balance(wallet: str, token_address: str, rpc_url: str) -> int:
    """查询 ERC20 代币余额"""
    # balanceOf(address) selector = 0x70a08231
    data = "0x70a08231" + wallet[2:].zfill(64)
    result = await rpc_call("eth_call", [{"to": token_address, "data": data}, "latest"])
    return int(result, 16)
```

### 2.4 EVM Approve（首次卖出需要）

```python
async def approve_if_needed(wallet: str, token: str, spender: str, private_key: str, rpc_url: str):
    """检查 allowance，不足则发 approve 交易"""
    # allowance(owner, spender) selector = 0xdd62ed3e
    allowance = await query_allowance(wallet, token, spender, rpc_url)
    if allowance < REQUIRED_AMOUNT:
        # approve(spender, MAX_UINT256) selector = 0x095ea7b3
        tx = build_approve_tx(token, spender, MAX_UINT256)
        signed = sign_evm_tx(tx, private_key)
        await broadcast_tx(signed, rpc_url)
```

### 2.5 卖出执行

```python
async def execute_sell(
    chain: str,
    token_address: str,
    sell_pct: float = 1.0,  # 卖出比例，1.0 = 全仓
    wallet: str = None,
    private_key: str = None,
    slippage_pct: float = 1.0,
) -> dict:
    """执行卖出"""
    # 1. 查余额
    balance = await query_balance(chain, wallet, token_address)
    sell_amount = int(balance * sell_pct)
    if sell_amount <= 0:
        return {"status": "error", "message": "余额不足"}

    # 2. EVM 需 approve
    if chain != "solana":
        spender = OKX_DEX_ROUTER[chain]
        await approve_if_needed(wallet, token_address, spender, private_key, RPC_URLS[chain])

    # 3. OKX DEX swap（反向：代币→USDC）
    quote_token = QUOTE_TOKENS[chain]  # USDC/USDT
    swap_data = await get_swap_data(
        chain=chain,
        from_token=token_address,
        to_token=quote_token,
        amount=str(sell_amount),
        slippage=slippage_pct,
        user_address=wallet,
    )

    # 4. 签名 + 广播
    if chain == "solana":
        tx_hash = await sign_and_broadcast_sol(swap_data, private_key)
    else:
        tx_hash = await sign_and_broadcast_evm(swap_data, private_key, chain)

    # 5. 记录
    return {
        "status": "success",
        "tx_hash": tx_hash,
        "amount_sold": sell_amount,
        "chain": chain,
    }
```

### 2.6 持仓监控器

```python
# agent/position_monitor.py

class PositionMonitor:
    """监控所有 open 持仓，检查 SL/TP/Trailing"""

    def __init__(self):
        self._positions = {}  # {execution_id: PositionInfo}
        self._peak_prices = {}  # {execution_id: peak_price} for trailing stop

    async def check_all(self, current_prices: dict):
        """检查所有持仓的止盈止损"""
        for exec_id, pos in list(self._positions.items()):
            price = current_prices.get(f"{pos.chain}:{pos.token_address}")
            if price is None:
                continue

            # 更新峰值（追踪止损用）
            peak = self._peak_prices.get(exec_id, pos.entry_price)
            if price > peak:
                self._peak_prices[exec_id] = price
                peak = price

            # 止盈检查
            if pos.take_profit_pct and price >= pos.entry_price * (1 + pos.take_profit_pct / 100):
                await self._execute_exit(exec_id, pos, price, "take_profit")

            # 止损检查
            elif pos.stop_loss_pct and price <= pos.entry_price * (1 - pos.stop_loss_pct / 100):
                await self._execute_exit(exec_id, pos, price, "stop_loss")

            # 追踪止损检查
            elif pos.trailing_stop_pct and price <= peak * (1 - pos.trailing_stop_pct / 100):
                await self._execute_exit(exec_id, pos, price, "trailing_stop")

    async def _execute_exit(self, exec_id, pos, price, trigger):
        """执行退出"""
        from agent.trade_executor import TradeExecutor
        executor = TradeExecutor()
        result = await executor.execute_sell(
            chain=pos.chain,
            token_address=pos.token_address,
            wallet=pos.wallet,
            private_key=pos.private_key,
        )
        # 记录 PnL
        pnl_pct = (price - pos.entry_price) / pos.entry_price * 100
        # 更新 strategy_executions 表
        ...
```

### 2.7 数据库改动

```sql
-- strategy_executions 表增加卖出字段（如果没有）
ALTER TABLE strategy_executions
    ADD COLUMN IF NOT EXISTS exit_price NUMERIC,
    ADD COLUMN IF NOT EXISTS exit_tx_hash TEXT,
    ADD COLUMN IF NOT EXISTS pnl_usd NUMERIC,
    ADD COLUMN IF NOT EXISTS pnl_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS exit_trigger TEXT,  -- take_profit/stop_loss/trailing_stop/manual
    ADD COLUMN IF NOT EXISTS exited_at TIMESTAMPTZ;
```

---

## 三、集成点

```
EventBus "data.hot_coin_update" / "data.pump_snapshot"
    ↓
event_listener.py → 检查策略条件
    ↓（如果有 open 持仓匹配当前代币）
position_monitor.check_all(current_prices)
    ↓（触发 SL/TP）
trade_executor.execute_sell()
    ↓
record to strategy_executions + performance_analytics
```

---

## 四、错误处理

| 场景 | 处理 |
|------|------|
| 余额为 0 | 返回 error，标记持仓为 "balance_zero" |
| OKX swap 报错 | 重试 2 次，仍失败则发告警不卖 |
| 签名失败 | 记录错误，不重试（私钥问题） |
| 广播超时 | 重试 1 次，仍失败查链上确认 |
| 滑点超限 | 取消交易，5 分钟后重试 |
| approve 失败 | 记录错误，告警用户手动处理 |

---

## 五、测试要点

详见 `TEST-001-v1.0.md`

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-22 | 初始版本 |
