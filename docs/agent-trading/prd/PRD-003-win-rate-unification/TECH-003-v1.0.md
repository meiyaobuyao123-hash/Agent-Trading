# TECH-003: 胜率定义统一 — 技术方案

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-003 |
| 创建日期 | 2026-03-22 |

---

## 一、当前不一致清单

| 位置 | 文件 | 行号 | 当前定义 | 改为 |
|------|------|------|---------|------|
| Pump Optimizer | `optimizer_tools.py` tool_read_metrics | ~80 | best_pct >= 50% 或 graduated | D3 ≥ 30% 或 graduated |
| Hot Optimizer | `optimizer_tools.py` tool_read_hot_metrics | ~250 | D3 ≥ 20% | D3 ≥ 20%（保持） |
| Strategy Backtester | `agent/backtester.py` | ~180 | best_pct >= 20% | 改为与对应场景一致 |
| Performance Analytics | `agent/performance_analytics.py` | ~95 | sell_avg > buy_avg | 保持（这是实际 PnL） |

---

## 二、统一方案

### 2.1 定义常量

```python
# config.py 新增

# 胜率定义（各场景）
WIN_RATE_PUMP_D3_PCT = 30       # Pump 内盘：D3 涨幅 ≥ 30% 算 hit
WIN_RATE_HOT_D3_PCT = 20        # 热币：D3 涨幅 ≥ 20% 算 hit
WIN_RATE_BTCETH_PNL_PCT = 2     # BTC/ETH：PnL ≥ 2% 算 hit
WIN_RATE_AGENT_BREAK_EVEN = True # Agent 策略：不亏就算 win
```

### 2.2 改动清单

#### optimizer_tools.py — tool_read_metrics

```python
# 当前
hit = best_pct >= 50 or graduated
# 改为
from config import WIN_RATE_PUMP_D3_PCT
d3_pct = daily_highs.get("D3", {}).get("pct", 0) if isinstance(daily_highs.get("D3"), dict) else 0
hit = d3_pct >= WIN_RATE_PUMP_D3_PCT or graduated
```

#### agent/backtester.py — 胜率计算

```python
# 当前
win = best_pct >= 20
# 改为
from config import WIN_RATE_PUMP_D3_PCT, WIN_RATE_HOT_D3_PCT

def _is_win(self, source: str, perf: dict) -> bool:
    d3 = perf.get("daily_highs", {}).get("D3", {})
    d3_pct = d3.get("pct", 0) if isinstance(d3, dict) else 0
    if source in ("pump", "pump_live"):
        return d3_pct >= WIN_RATE_PUMP_D3_PCT or perf.get("graduated", False)
    elif source in ("hot", "hot_live"):
        return d3_pct >= WIN_RATE_HOT_D3_PCT
    else:
        return perf.get("best_pct", 0) >= 0  # 不亏就算 win
```

#### agent/performance_analytics.py — 双指标

```python
# 新增 theoretical_win_rate
def get_strategy_performance(strategy_id, days=30):
    ...
    return {
        "actual_win_rate": actual_wins / total,      # 实际买卖盈利
        "theoretical_win_rate": theo_wins / total,    # D3 涨幅理论命中
        "total_trades": total,
        ...
    }
```

---

## 三、Portal 展示改动

```
/pump 页面：
  命中率: 45.2%（D3涨幅≥30%或毕业）← 标注定义

/hot 页面：
  命中率: 38.5%（D3涨幅≥20%）← 标注定义

/btc-eth 页面：
  胜率: 62.0%（信号 PnL≥0）← 标注定义
```

---

## 四、历史数据迁移

无需迁移。token_performance 表已有 `daily_highs` 和 `best_pct`，只需在查询时用新定义重算。

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-22 | 初始版本 |
