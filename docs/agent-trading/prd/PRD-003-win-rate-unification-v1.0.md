# PRD-003: 胜率定义统一

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-03-22 |
| 所属模块 | agent-trading |
| 优先级 | P0（严重） |
| 状态 | 待开发 |

---

## 一、背景

系统中三个模块对"胜率"的定义不一致，导致评估结果不可比较，Optimizer 的优化方向可能与实际表现脱节。

| 模块 | "赢"的定义 | 文件 |
|------|-----------|------|
| **Pump Optimizer** | 价格涨 50%+ 或毕业 | `optimizer_tools.py` |
| **Strategy Backtester** | D3 涨 20%+ | `agent/backtester.py` |
| **Performance Analytics** | 卖出均价 > 买入均价 | `agent/performance_analytics.py` |
| **Hot Coin Optimizer** | D3 涨 20%+ | `optimizer_tools.py` (hot) |

---

## 二、问题影响

1. **Optimizer 优化目标与实际表现脱节**：Optimizer 追求 50%+ 涨幅，但 Backtester 用 20%+ 评估，两者可能给出矛盾结论
2. **用户看到的胜率与 Optimizer 看到的不同**：Performance Analytics 用实际买卖价，Optimizer 用理论涨幅
3. **Portal 看板数据混乱**：/pump 和 /hot 的命中率指标定义不同

---

## 三、统一方案

### 3.1 分场景定义

| 场景 | 统一定义 | 理由 |
|------|---------|------|
| **Pump 内盘** | D3 最高价涨幅 ≥ 30% 或毕业 | 30% 是买卖摩擦后仍能获利的最低门槛 |
| **热币外盘** | D3 最高价涨幅 ≥ 20% | 热币生命周期短，20% 已是不错的收益 |
| **Agent 策略** | 实际卖出价 / 买入价 ≥ 1.0（不亏） | 这是用户最关心的：赚没赚 |
| **BTC/ETH** | 实际 PnL ≥ 0 或信号方向正确且涨幅 ≥ 2% | 大盘币波动小，2% 已有意义 |

### 3.2 代码改动

| 文件 | 改动 |
|------|------|
| `optimizer_tools.py` | `tool_read_metrics()` 的 hit 定义改为 D3 ≥ 30% 或毕业 |
| `agent/backtester.py` | `_get_token_performance()` 改用与 Optimizer 一致的定义 |
| `agent/performance_analytics.py` | 新增 `theoretical_win_rate`（D3 涨幅）+ `actual_win_rate`（买卖 PnL），两者都展示 |
| `btc_eth/paper_trading/metrics.py` | 信号胜率用 PnL ≥ 0 |
| Portal `/pump` `/hot` `/btc-eth` | 明确标注胜率定义 |

### 3.3 Portal 展示

```
命中率: 62.5%（D3涨幅≥20%的代币占比）
实盘胜率: 58.3%（实际卖出盈利的比例）— 仅 Agent 策略有
```

两个指标并列，用户清楚知道各自含义。

---

## 四、验收标准

- [ ] Optimizer 和 Backtester 使用相同的 hit 定义
- [ ] Performance Analytics 同时展示理论和实际胜率
- [ ] Portal 各看板标注胜率定义
- [ ] 历史数据按新口径重算一次

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-22 | 初始版本 |
