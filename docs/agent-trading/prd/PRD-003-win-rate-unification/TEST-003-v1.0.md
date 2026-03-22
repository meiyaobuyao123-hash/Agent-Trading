# TEST-003: 胜率定义统一 — 测试用例

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-003 |
| 对应 TECH | TECH-003 |
| 创建日期 | 2026-03-22 |

---

## 一、单元测试

### UT-01: Pump 命中判定

| 输入 | D3 涨幅 | graduated | 预期 |
|------|---------|-----------|------|
| 代币 A | 35% | False | ✅ hit（D3≥30%） |
| 代币 B | 25% | False | ❌ miss |
| 代币 C | 10% | True | ✅ hit（毕业） |
| 代币 D | 0% | False | ❌ miss |

### UT-02: Hot 命中判定

| 输入 | D3 涨幅 | 预期 |
|------|---------|------|
| 代币 E | 22% | ✅ hit（D3≥20%） |
| 代币 F | 15% | ❌ miss |
| 代币 G | -5% | ❌ miss |

### UT-03: Backtester 与 Optimizer 一致性

```
前置：同一组 token_performance 数据
调用：
  - optimizer_tools.tool_read_metrics(days=7) → hit_rate_A
  - backtester.backtest_strategy(pump_strategy, days=7) → win_rate_B
预期：hit_rate_A 和 win_rate_B 的计算口径一致（同一代币在两处判定结果相同）
```

### UT-04: Performance Analytics 双指标

```
前置：策略有 10 笔交易，其中 6 笔实际盈利，7 笔 D3≥30%
调用：get_strategy_performance(strategy_id)
预期：
  actual_win_rate = 60%（6/10）
  theoretical_win_rate = 70%（7/10）
  两个指标都有值且不同
```

---

## 二、集成测试

### IT-01: Optimizer 使用新口径

```
步骤：手动触发 POST /api/optimizer/trigger?mode=pump
预期：运行日志中 hit_rate 使用 D3≥30%+graduated 口径
```

### IT-02: Portal 标注正确

```
步骤：访问 /pump、/hot、/btc-eth 页面
预期：命中率旁边有括号标注具体定义
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-22 | 初始版本 |
