# TEST-002: 风控管理器 Bug 修复 — 测试用例

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.1 |
| 对应 PRD | PRD-002 |
| 对应 TECH | TECH-002 |
| 创建日期 | 2026-03-22 |
| 最后执行 | 2026-03-22 |
| 执行结果 | **11/11 ALL PASSED** |
| 测试脚本 | `services/pump-scanner/tests/test_prd002.py` |

---

## 一、单元测试: chain_concentration Bug 修复

### UT-01: 同链 5+ 持仓触发警告

```
前置：record_trade 模拟 5 个 solana 链的 buy
调用：_check_chain_concentration("solana", "buy")
预期：返回 risk_level="medium"，reason 含 "5 个持仓"
结果：✅ PASS — "solana 链已有 5 个持仓，建议分散"
```

### UT-02: 多链分散不触发

```
前置：sol 2 个 + eth 2 个 + bsc 1 个
调用：_check_chain_concentration("solana", "buy")
预期：passed=True，reason 为空
结果：✅ PASS — no warning for 2 SOL
```

### UT-03: 无持仓不报错

```
前置：RiskManager 刚初始化，无任何持仓
调用：_check_chain_concentration("solana", "buy")
预期：passed=True，不崩溃
结果：✅ PASS — no crash, passed=True
```

### UT-04: sell action 跳过检查

```
前置：有 5 个 SOL 持仓
调用：_check_chain_concentration("solana", "sell")
预期：直接返回 ok（卖出不需要集中度检查）
结果：✅ PASS — correctly skipped
```

---

## 二、单元测试: _btc_samples 初始化 Bug 修复

### UT-05: _btc_samples 在 __init__ 中初始化

```
前置：新建 RiskManager 实例
验证：hasattr(rm, "_btc_samples") and isinstance(rm._btc_samples, list)
预期：True（不再依赖 hasattr 懒初始化）
结果：✅ PASS — type=list, len=0
```

### UT-05b: 冷启动调用 market_regime 不崩溃

```
前置：RiskManager 刚初始化，_btc_samples 为空
调用：_check_market_regime("buy")
预期：passed=True（数据不足不报警），不抛 AttributeError
结果：✅ PASS — no crash on empty samples
```

### UT-06: BTC 4% 下跌逻辑验证

```
前置：oldest_price=70000, current=67200 (-4%)
计算：change_pct = (67200-70000)/70000 = -0.04
预期：change_pct < -0.03 → 应触发 block
结果：✅ PASS — change=-4.0% < -3% => block
```

### UT-06b: BTC samples 10 分钟窗口保留

```
前置：2 个 sample，一个 5 分钟前，一个当前
过滤：保留 now-t < 600 的 samples
预期：2 个都在 10 分钟内，保留 2 个
结果：✅ PASS — 2 samples within 10min window
```

---

## 三、单元测试: _position_chains 追踪

### UT-07: 买入时记录 chain

```
前置：record_trade("token_a", "solana", "buy", 100, 0.001)
      record_trade("token_b", "eth", "buy", 200, 0.001)
验证：_position_chains["token_a"] == "solana"
      _position_chains["token_b"] == "eth"
结果：✅ PASS — correct chain tracking
```

### UT-07b: 卖出时移除 chain 记录

```
前置：接 UT-07，卖出 token_a
调用：record_trade("token_a", "solana", "sell", 100, 0.002)
验证："token_a" not in _position_chains
结果：✅ PASS — removed after sell
```

---

## 四、集成测试

### IT-01: 完整风控检查通过

```
前置：新建 RiskManager，正常环境
调用：check_trade(chain="solana", token="SOL mint", action="buy", amount=50)
预期：所有检查通过，不崩溃
结果：✅ PASS — passed=True reason=
```

---

## 五、测试结果汇总

| 用例 | 类型 | 描述 | 结果 |
|------|------|------|------|
| UT-01 | 单元 | 同链 5+ 触发警告 | ✅ PASS |
| UT-02 | 单元 | 多链分散不触发 | ✅ PASS |
| UT-03 | 单元 | 无持仓不报错 | ✅ PASS |
| UT-04 | 单元 | sell 跳过检查 | ✅ PASS |
| UT-05 | 单元 | _btc_samples 初始化 | ✅ PASS |
| UT-05b | 单元 | 冷启动不崩溃 | ✅ PASS |
| UT-06 | 单元 | BTC 4% drop 逻辑 | ✅ PASS |
| UT-06b | 单元 | samples 窗口保留 | ✅ PASS |
| UT-07 | 单元 | 买入记录 chain | ✅ PASS |
| UT-07b | 单元 | 卖出移除 chain | ✅ PASS |
| IT-01 | 集成 | 完整风控检查 | ✅ PASS |
| **总计** | | **11/11** | **ALL PASSED** |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-22 | 初始版本 |
| v1.1 | 2026-03-22 | 补充实际执行结果，新增 UT-04/UT-06b/UT-07/UT-07b |
