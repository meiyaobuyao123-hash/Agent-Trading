# TECH-002: 风控管理器 Bug 修复 — 技术方案

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-002 |
| 创建日期 | 2026-03-22 |

---

## 一、Bug 1: chain_concentration 类型错误

### 当前代码（错误）

```python
# agent/risk_manager.py 约第 441 行
def _check_chain_concentration(self, chain: str) -> List[str]:
    warnings = []
    portfolio = self._portfolio  # {token_address: usd_value (float)}
    for token, value in portfolio.items():
        chain = value.get("chain")  # ❌ value 是 float，没有 .get()
```

### 修复方案

```python
def _check_chain_concentration(self, chain: str) -> List[str]:
    """检查同一条链的持仓集中度"""
    warnings = []
    try:
        # 从 strategy_executions 查询 open 持仓的链分布
        db = get_db()
        res = db.table("strategy_executions").select("chain") \
            .eq("status", "open").execute()
        chain_counts = {}
        for e in (res.data or []):
            c = e.get("chain", "unknown")
            chain_counts[c] = chain_counts.get(c, 0) + 1

        MAX_SAME_CHAIN = 5
        for c, count in chain_counts.items():
            if count >= MAX_SAME_CHAIN:
                warnings.append(
                    f"同链集中风险: {c} 链有 {count} 个持仓（上限 {MAX_SAME_CHAIN}）"
                )
    except Exception as e:
        log.warning(f"chain_concentration check error: {e}")
    return warnings
```

### 影响范围

仅 `agent/risk_manager.py` 一个函数，不影响其他风控检查。

---

## 二、Bug 2: _btc_samples 未初始化

### 当前代码（错误）

```python
# agent/risk_manager.py 约第 409 行
def _check_market_regime(self) -> List[str]:
    # 某处动态创建 self._btc_samples
    # 但如果在第一次采样前就调用此方法，self._btc_samples 不存在
```

### 修复方案

```python
class RiskManager:
    def __init__(self, ...):
        ...
        self._btc_samples = []  # ← 添加初始化
        self._btc_last_sample_time = 0
```

### 影响范围

仅 `__init__` 添加一行，零副作用。

---

## 三、测试要点

详见 `TEST-002-v1.0.md`

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-22 | 初始版本 |
