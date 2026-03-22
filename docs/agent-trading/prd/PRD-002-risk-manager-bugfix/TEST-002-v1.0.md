# TEST-002: 风控管理器 Bug 修复 — 测试用例

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-002 |
| 对应 TECH | TECH-002 |
| 创建日期 | 2026-03-22 |

---

## 一、Bug 1 测试: chain_concentration

### UT-01: 同链 5+ 持仓触发警告

```
前置：strategy_executions 中有 5 个 solana 链的 open 持仓
调用：_check_chain_concentration("solana")
预期：返回 ["同链集中风险: solana 链有 5 个持仓（上限 5）"]
```

### UT-02: 多链分散不触发

```
前置：sol 2 个 + eth 2 个 + bsc 1 个 open 持仓
调用：_check_chain_concentration("solana")
预期：返回空列表
```

### UT-03: 无持仓不报错

```
前置：strategy_executions 无 open 记录
调用：_check_chain_concentration("solana")
预期：返回空列表，不崩溃
```

### UT-04: DB 查询失败降级

```
前置：模拟 DB 连接超时
调用：_check_chain_concentration("solana")
预期：返回空列表，log.warning 记录错误
```

---

## 二、Bug 2 测试: _btc_samples 初始化

### UT-05: 冷启动调用 market_regime

```
前置：RiskManager 刚初始化，未采样过 BTC 价格
调用：_check_market_regime()
预期：返回空列表（数据不足不报警），不抛 AttributeError
```

### UT-06: 正常采样后检查

```
前置：_btc_samples 有 10 个 5min 采样点，最新价跌 4%
调用：_check_market_regime()
预期：返回 ["BTC 大盘异动: 10min 下跌 4.0%，暂停买入"]
```

---

## 三、集成测试

### IT-01: 完整 15 项风控全通过

```
前置：正常环境，无异常条件
调用：risk_manager.pre_trade_check(trade_params)
预期：15 项检查全部通过，返回 approved=True
```

### IT-02: chain_concentration 阻止交易

```
前置：已有 5 个 SOL 链 open 持仓
调用：买入第 6 个 SOL 链代币
预期：风控返回 warning，trade 仍可执行但附带警告
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-22 | 初始版本 |
