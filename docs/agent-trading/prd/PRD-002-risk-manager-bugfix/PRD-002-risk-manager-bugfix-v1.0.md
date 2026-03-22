# PRD-002: 风控管理器 Bug 修复

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-03-22 |
| 所属模块 | agent-trading |
| 优先级 | P0（严重） |
| 状态 | 待开发 |

---

## 一、背景

`agent/risk_manager.py` 第 441 行存在逻辑 Bug：**chain_concentration 检查对 float 值调用 `.get("chain")`**，导致该风控检查崩溃或被跳过。

当前 RiskManager 共 15 项检查，其中第 15 项"同链集中度"无法正常工作。

---

## 二、问题详情

### Bug 1: chain_concentration 类型错误

```python
# 当前代码（错误）
for token, value in portfolio.items():
    chain = value.get("chain")  # value 是 float（持仓金额），不是 dict
```

`portfolio` 的结构是 `{token_address: usd_value}`（float），而非 `{token_address: {chain, value}}`。
调用 `.get("chain")` 会抛 `AttributeError: 'float' object has no attribute 'get'`。

### 修复方案

需要从 `strategy_executions` 表查询每笔买入的 chain，而不是从 portfolio 取：

```python
# 修复后
executions = db.table("strategy_executions").select("chain").eq("status", "open").execute()
chain_counts = Counter(e["chain"] for e in executions.data)
for chain, count in chain_counts.items():
    if count > MAX_SAME_CHAIN:
        warnings.append(f"同链集中: {chain} 有 {count} 个持仓")
```

### Bug 2: _btc_samples 未初始化

`risk_manager.py` 第 409 行动态创建 `_btc_samples` 列表，但如果在第一次采样前就调用了市场检查，会报 `AttributeError`。

### 修复方案

在 `__init__` 中初始化：`self._btc_samples = []`

---

## 三、验收标准

- [ ] chain_concentration 检查能正确识别同链 5+ 持仓并发出警告
- [ ] BTC 大盘检查在无历史数据时不崩溃
- [ ] 15 项风控检查全部可用，无异常跳过
- [ ] 单元测试覆盖所有 15 项检查

---

## 四、技术影响

| 文件 | 改动 |
|------|------|
| `agent/risk_manager.py` | 修复 chain_concentration + _btc_samples 初始化 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-22 | 初始版本 |
