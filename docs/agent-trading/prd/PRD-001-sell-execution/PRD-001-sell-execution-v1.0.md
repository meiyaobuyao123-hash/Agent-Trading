# PRD-001: Agent 卖出执行功能

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-03-22 |
| 所属模块 | agent-trading |
| 优先级 | P0（严重） |
| 状态 | 待开发 |

---

## 一、背景

当前 Agent 交易执行器（`agent/trade_executor.py`）**只实现了买入（buy），卖出（sell）功能未实现**（第 228 行返回 "not yet implemented"）。

这意味着：
- 用户的策略可以自动买入代币，但**无法自动卖出**
- 止盈止损虽然在 risk_manager 中计算，但**无法触发卖出执行**
- 用户资金一旦买入就被锁定，必须手动到链上操作才能退出

这是**最严重的功能缺失**，直接影响用户资金安全。

---

## 二、目标

1. 实现 Agent 自动卖出（sell）功能，支持 SOL + EVM 四链
2. 支持止盈（take profit）自动触发卖出
3. 支持止损（stop loss）自动触发卖出
4. 支持追踪止损（trailing stop）
5. 支持用户手动触发卖出（通过 Agent 对话或 API）

---

## 三、功能需求

### 3.1 卖出执行

| 需求 | 详情 |
|------|------|
| 触发方式 | 止盈/止损/追踪止损/手动指令 |
| 支持链 | SOL、ETH、BSC、Base |
| 卖出方式 | OKX DEX Aggregator v6（与买入同一 API） |
| 卖出对象 | 持仓代币 → 换成 USDC/SOL/ETH |
| 滑点控制 | 默认 1%，可配置 |
| 部分卖出 | 支持（如"卖出 50% 持仓"） |

### 3.2 持仓查询

卖出前需要知道当前持仓量。方式：
- SOL: Helius `getTokenAccountsByOwner` → 查 SPL 代币余额
- EVM: OKX Wallet API `token-balances` 或直接查 ERC20 `balanceOf`

### 3.3 止盈止损自动执行

| 类型 | 触发条件 | 执行 |
|------|---------|------|
| 止盈 | 当前价格 ≥ 入场价 × (1 + take_profit_pct) | 全仓卖出 |
| 止损 | 当前价格 ≤ 入场价 × (1 - stop_loss_pct) | 全仓卖出 |
| 追踪止损 | 最高价回落 ≥ trailing_stop_pct | 全仓卖出 |

监控频率：event_listener 事件触发 + monitor_job 30s fallback

### 3.4 卖出记录

```json
{
  "strategy_id": "uuid",
  "execution_id": "uuid",
  "action": "sell",
  "chain": "solana",
  "token_address": "...",
  "amount_token": 1000000,
  "amount_usd": 150.00,
  "entry_price": 0.00010,
  "exit_price": 0.00015,
  "pnl_usd": 50.00,
  "pnl_pct": 50.0,
  "trigger": "take_profit",
  "tx_hash": "...",
  "status": "success"
}
```

---

## 四、技术影响

| 文件 | 改动 |
|------|------|
| `agent/trade_executor.py` | 实现 sell 逻辑：查余额 → OKX swap → 签名 → 广播 |
| `agent/monitor_job.py` | 增加持仓监控：检查止盈止损条件 |
| `agent/event_listener.py` | 增加价格事件订阅 → 触发止盈止损 |
| `agent/risk_manager.py` | 卖出后更新 portfolio 状态 |
| `agent/performance_analytics.py` | 记录完整买卖配对 PnL |

---

## 五、验收标准

- [ ] 用户创建"自动买入 + 止盈 50% + 止损 20%"策略
- [ ] Agent 自动买入后，价格涨 50% 触发止盈卖出
- [ ] 卖出交易在链上确认，execution 记录完整
- [ ] PnL 正确计算并展示
- [ ] 价格跌 20% 触发止损，同样完整执行
- [ ] SOL 和 EVM 各至少测试一笔

---

## 六、风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 滑点导致实际卖出价低于预期 | 高 | 中 | 设置最大滑点保护 |
| 代币流动性不足无法卖出 | 中 | 高 | 检查流动性，不足时告警而非强制卖 |
| OKX DEX 不支持该代币卖出 | 低 | 高 | fallback 到 Jupiter/Raydium 直连 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-22 | 初始版本 |
