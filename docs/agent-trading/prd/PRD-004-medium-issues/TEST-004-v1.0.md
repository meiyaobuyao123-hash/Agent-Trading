# TEST-004: 中等问题合集 — 测试用例

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-004 |
| 对应 TECH | TECH-004 |
| 创建日期 | 2026-03-22 |

---

## M-01: trigger_count 原子性

### UT-01: 并发触发计数

```
前置：策略 trigger_count = 0
步骤：并发 10 个 record_trigger(strategy_id) 调用
预期：trigger_count = 10（不丢失）
```

### UT-02: RPC function 存在

```
步骤：Supabase 调用 increment_trigger_count(uuid)
预期：正常执行，trigger_count +1
```

---

## M-02: LLM Parser 重试

### UT-03: 首次成功

```
步骤：正常调用 parse_strategy("监控BTC")
预期：一次成功，返回 StrategySpec
```

### UT-04: 429 重试后成功

```
步骤：模拟前 2 次 RateLimitError，第 3 次成功
预期：等待 5+10=15s 后返回结果
```

### UT-05: 全部失败

```
步骤：模拟 3 次全部 InternalServerError
预期：返回 None，log.error 记录
```

---

## M-03: 配置参数

### UT-06: 默认值

```
步骤：不设 .env 变量，读取 config
预期：SIGNAL_POOL_MIN_SCORE=55, RISK_DAILY_LOSS_LIMIT=50 等默认值
```

### UT-07: 环境变量覆盖

```
步骤：.env 设置 SIGNAL_POOL_MIN_SCORE=60
预期：config.SIGNAL_POOL_MIN_SCORE == 60
```

### UT-08: collector 使用配置

```
步骤：修改 SIGNAL_POOL_MIN_SCORE=70，重启
预期：信号池只接受 score>=70 的代币
```

---

## M-04: btc_eth_indicators 持久化

### UT-09: 5min 写入

```
步骤：启动 BtcEthManager，等待 6 分钟
预期：btc_eth_indicators 表至少有 2 行（BTC+ETH）
```

### UT-10: 写入字段完整

```
步骤：查询最新一行 btc_eth_indicators
预期：price_usd > 0, rsi_14 有值, fear_greed_index 有值
```

---

## M-05: Paper Trading SL/TP

### UT-11: 止盈触发

```
前置：模拟盘 open trade: BTC long entry=$70000 tp=$77000
步骤：当前价格 $77500 → check_exits()
预期：trade 变为 closed, exit_price=$77500, pnl_pct≈+10.7%
```

### UT-12: 止损触发

```
前置：模拟盘 open trade: ETH long entry=$2100 sl=$1890
步骤：当前价格 $1850 → check_exits()
预期：trade 变为 closed, exit_price=$1850, pnl_pct≈-11.9%
```

### UT-13: 价格在 SL/TP 之间

```
前置：trade entry=$70000 sl=$63000 tp=$77000
步骤：当前价格 $72000 → check_exits()
预期：trade 仍为 open，无变化
```

---

## 集成测试

### IT-01: 端到端 Paper Trading 生命周期

```
步骤：
  1. POST /api/btc-eth/portfolio/init {capital: 10000}
  2. Agent 生成 BTC long 信号
  3. Paper engine 自动买入
  4. 价格上涨触达 TP
  5. check_exits 自动平仓
  6. GET /api/btc-eth/portfolio → equity > 10000
预期：完整买入→持有→止盈闭环
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-22 | 初始版本 |
