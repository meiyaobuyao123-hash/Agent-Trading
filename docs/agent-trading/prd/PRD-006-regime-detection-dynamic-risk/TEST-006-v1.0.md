# TEST-006: 市场 Regime 检测 + 动态风控 — 测试用例

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-006 v1.1 |
| 对应 TECH | TECH-006 v1.1 |
| 创建日期 | 2026-03-23 |

---

## 一、CUSUM 检测 — 单元测试

### UT-01: CUSUM 基础变化检测

| 用例 | 输入 | 预期 |
|------|------|------|
| 正常波动不报警 | 24 根 return ~N(0, 0.01) | change=False, warning=False |
| 上行结构变化 | 24 根正常 + 5 根 return=+0.05 | change=True, direction="up" |
| 下行结构变化 | 24 根正常 + 5 根 return=-0.05 | change=True, direction="down" |
| 警告级别 | 24 根正常 + 3 根 return=+0.03 | warning=True, change=False |
| 数据不足 | <24 根 | change=False（静默） |
| 变化后重置 | 触发 change 后下一根正常 | s_up 和 s_down 重置为 0 |

### UT-02: CUSUM 多资产阈值差异

```
BTC h=3σ: 需要更大偏差才触发（大盘波动大是常态）
SOL h=2.5σ: 更敏感（SOL 波动模式和 BTC 不同）
ETH h=3.0σ: 与 BTC 一致

验证：同样的 return 序列，SOL 先于 BTC 触发
```

---

## 二、HMM 分类 — 单元测试

### UT-03: HMM 训练 + 标签校准

```
前置：生成 200 条模拟数据
  - 前 50 条：return~N(+0.005, 0.01)（模拟牛市）
  - 中 50 条：return~N(-0.005, 0.01)（模拟熊市）
  - 后 50 条：return~N(0, 0.005)（模拟震荡）
  - 最后 50 条：return~N(0, 0.03)（模拟高波动）

调用：hmm.train(features)
预期：
  - 返回 True
  - label_map 中包含 TRENDING_UP/DOWN/RANGING/HIGH_VOLATILITY
  - TRENDING_UP 对应 return 均值最高的状态
  - HIGH_VOLATILITY 对应波动率最高的状态
```

### UT-04: HMM 分类输出格式

```
调用：hmm.classify(features)
预期：
  - regime: str（4 种之一）
  - confidence: float 0-1
  - state_probs: dict（4 个状态的概率分布，和 ≈ 1.0）
  - method: "hmm"
```

### UT-05: HMM 特征归一化

```
输入：未归一化 [return=0.001, vol_change=0.5, atr_ratio=0.03, funding=0.0001]
验证：
  - train() 后 scaler.mean_ 有 4 个值
  - classify() 前自动 transform
  - 不同量纲的特征对 HMM 贡献均衡
```

### UT-06: HMM fallback 到规则引擎

```
前置：hmmlearn 不可用（模拟 ImportError）
调用：hmm.classify(features)
预期：
  - method="rule_fallback"
  - regime 仍然有值（根据 MA/ATR 规则判定）
  - confidence=0.6（固定）
```

### UT-07: HMM 数据不足时降级

```
前置：feature_buffer 只有 20 条（< HMM_MIN_SAMPLES=48）
调用：hmm.train(features)
预期：返回 False，不崩溃
调用：hmm.classify(features)
预期：fallback 到规则引擎
```

### UT-08: score_samples 替代 predict_proba

```
验证：GaussianHMM 调用 score_samples 返回 (logprob, posteriors)
  - posteriors.shape = (n_samples, n_states)
  - posteriors[-1] 各元素 >= 0 且和 ≈ 1.0
  - argmax(posteriors[-1]) 与 predict()[-1] 一致
```

### UT-09: asyncio.to_thread 不阻塞

```
测试：并发调用 update_hmm + 一个 asyncio.sleep(0.01)
预期：sleep 不被 HMM 计算阻塞（两者近乎同时完成）
```

---

## 三、CRISIS 检测 — 单元测试

### UT-10: CRISIS 触发条件

| 用例 | btc_price 序列 | liquidation | funding | 预期 |
|------|---------------|-------------|---------|------|
| BTC 15min 跌 6% | [70000→65800] | 0 | 0 | just_entered=True |
| 爆仓超标 | [70000→70000] | 600M | 0 | just_entered=True |
| 资金费率极端 | [70000→70000] | 0 | -0.002 | just_entered=True |
| 正常波动 | [70000→69000](-1.4%) | 100M | -0.0005 | is_crisis=False |
| 多条件叠加 | [70000→66000] | 600M | -0.002 | just_entered=True（首个触发） |

### UT-11: CRISIS 恢复条件

```
前置：已进入 CRISIS
步骤：
  1. 模拟 BTC 价格稳定（15 个 1min 数据点无新低）
  2. 15min 波动 < 1%
  3. 持续 30 分钟

预期（30min 前）：is_crisis=True, just_recovered=False
预期（30min 后）：is_crisis=False, just_recovered=True
```

### UT-12: CRISIS 恢复中断

```
前置：CRISIS 恢复已持续 20 分钟
步骤：突然 BTC 又跌（新低）
预期：recovery_start 重置，需要重新等 30 分钟
```

---

## 四、综合判定 — 单元测试

### UT-13: 全局 Regime 综合逻辑

| BTC | SOL | ETH | 预期 global | 预期 chain_solana |
|-----|-----|-----|------------|------------------|
| TRENDING_UP | TRENDING_UP | RANGING | TRENDING_UP | TRENDING_UP |
| TRENDING_UP | TRENDING_DOWN | RANGING | RANGING | TRENDING_DOWN |
| TRENDING_DOWN | TRENDING_DOWN | TRENDING_DOWN | TRENDING_DOWN | TRENDING_DOWN |
| RANGING | HIGH_VOLATILITY | RANGING | HIGH_VOLATILITY | HIGH_VOLATILITY |
| TRENDING_UP | RANGING | TRENDING_UP | TRENDING_UP | RANGING |

### UT-14: BREAKOUT 叠加判定

```
前置：HMM BTC = TRENDING_UP，CUSUM s_up > 0（活跃上行信号）
调用：get_regime()
预期：返回 "BREAKOUT"
```

### UT-15: CRISIS 覆盖一切

```
前置：HMM BTC = TRENDING_UP，但 crisis.is_crisis = True
调用：get_regime()
预期：返回 "CRISIS"（不管 HMM 结果）
```

---

## 五、数据管道 — 单元测试

### UT-16: on_kline_close 数据流

```
调用：on_kline_close("BTC", close=70000, volume=1000, prev_close=69500, prev_volume=900)
预期：
  - feature_buffer["BTC"] 新增 1 条 [log_return, vol_change, atr_ratio, funding]
  - CUSUM 收到新 return
  - 如果 CUSUM change=True → update_hmm 被调用
```

### UT-17: on_indicator_update 缓存

```
调用：on_indicator_update("BTC", {"atr_14": 2000, "price_usd": 70000, "funding_rate": 0.0005, ...})
预期：
  - indicator_cache["BTC"]["atr_ratio"] = 2000/70000
  - indicator_cache["BTC"]["funding_rate"] = 0.0005
```

### UT-18: 启动加载历史数据

```
前置：btc_eth_indicators 表有 200 条 BTC 数据
调用：load_historical_features()
预期：
  - feature_buffer["BTC"] 有 ~200 条
  - feature_buffer["SOL"] 从 BTC 复制初始化
  - retrain_hmm 被调用
  - HMM 可以立即分类（不用等 12h）
```

---

## 六、动态风控 — 单元测试

### UT-19: Regime 感知风控参数

| Regime | action=buy | 预期 |
|--------|-----------|------|
| TRENDING_UP | buy $100 | passed=True（正常仓位） |
| TRENDING_DOWN | buy $100 | blocked（不允许新买入） |
| CRISIS | buy $100 | blocked（强制清仓） |
| HIGH_VOLATILITY | buy $100 | passed + warning（仓位调整 50%） |

### UT-20: Shadow Mode

```
前置：REGIME_SHADOW_MODE=true
调用：check_trade(action="buy", regime="TRENDING_DOWN")
预期：
  - 返回 passed=True（Shadow 不拦截）
  - 日志包含 "[SHADOW]" 关键字
  - 记录"如果不是 Shadow 会 block"

前置：REGIME_SHADOW_MODE=false
调用：check_trade(action="buy", regime="TRENDING_DOWN")
预期：返回 blocked
```

### UT-21: ATR 动态仓位

| base_usd | atr_14 | avg_atr_30d | regime | 预期 position |
|----------|--------|-------------|--------|--------------|
| $100 | 2000 | 2000 | TRENDING_UP(1.0) | $100 |
| $100 | 4000 | 2000 | HIGH_VOL(0.5) | $25 |
| $100 | 1000 | 2000 | TRENDING_UP(1.0) | $200（cap） |
| $100 | 500 | 2000 | TRENDING_UP(1.0) | $200（cap） |
| $100 | 2000 | 2000 | CRISIS(0.0) | $0 |

### UT-22: ATR 动态止损

| entry | atr_14 | regime | side | 预期 SL |
|-------|--------|--------|------|---------|
| $70K | $2K | TRENDING_UP(sl=1.0) | long | $66K |
| $70K | $5K | HIGH_VOL(sl=1.5) | long | $55K |
| $70K | $2K | CRISIS(sl=0.5) | long | $68K |
| $70K | $2K | TRENDING_UP(sl=1.0) | short | $74K |

### UT-23: 时间衰减止损

| hold_hours | current_pnl | token_type | 预期行为 |
|-----------|-------------|------------|---------|
| 6h | +20% | meme | 不变（<8h） |
| 9h | +20% | meme | 追踪止损 max(entry, peak×0.85) |
| 9h | -15% | meme | 收紧 ×0.8 |
| 13h | +5% | meme | 收紧 ×0.7 |
| 9h | +20% | hot | 不变（非 meme 不衰减） |

---

## 七、CRISIS 清仓 — 单元测试

### UT-24: 清仓排序和间隔

```
前置：5 个持仓 [$200, $50, $150, $80, $120]
调用：execute_crisis_close_all()
预期：
  - 卖出顺序：$200 → $150 → $120 → $80 → $50
  - 每笔间隔 ~3s
  - 总耗时 ~15s
```

### UT-25: 清仓失败重试

```
前置：第 2 笔卖出模拟失败
预期：
  - 重试 1 次
  - 仍失败 → 记录 pending，继续下一笔
  - 不影响其余持仓的清仓
```

### UT-26: 清仓超时

```
前置：20 个持仓
预期：
  - 最多卖出 15 笔（60s 超时 ÷ 3s 间隔 ≈ 20，但有执行时间）
  - 剩余持仓 log 记录"超时未清仓"
```

---

## 八、O7 Regime 审计 — 单元测试

### UT-27: tool_read_regime_history 基础

```
前置：agent_regime_history 有 30 条记录（含 5 次 transition）
调用：tool_read_regime_history(days=14)
预期：
  - transitions 有 5 条
  - performance_by_regime 按 regime 分组
  - false_transitions 有统计
```

### UT-28: 检测延迟计算

```
前置：实际拐点（价格反转 >5% 持续 >4h）在 T=100
      regime transition 记录时间在 T=125
预期：detection_delay = 25 分钟
```

### UT-29: 误报代价计算

```
前置：误切换为 CRISIS → 清仓 3 个持仓 → BTC 随后涨 5%
预期：
  - false_transition = True
  - transition_cost_usd = 3 × avg_position × 5% ≈ $X
```

---

## 九、集成测试

### IT-01: 完整数据管道

```
步骤：
  1. Binance WS 推送新 BTC kline
  2. EventBus "kline.close" 触发
  3. regime_detector.on_kline_close 被调用
  4. CUSUM 处理 + feature_buffer 追加
  5. 如果 CUSUM 检测到变化 → HMM 分类
预期：从 WS 推送到 regime 判定 < 1s
```

### IT-02: Regime 切换 → 风控调整

```
步骤：
  1. 模拟 regime 从 TRENDING_UP → TRENDING_DOWN
  2. EventBus 发布 regime_change
  3. risk_manager 接收事件
  4. 下一笔 buy 请求被 block
预期：切换后 30s 内新买入被阻止
```

### IT-03: CRISIS → 自动清仓

```
步骤：
  1. 模拟 BTC 15min 跌 6%
  2. crisis_detector 触发 CRISIS
  3. EventBus 发布 regime_change(CRISIS)
  4. position_monitor 接收 → execute_crisis_close_all
预期：
  - CRISIS 检测 < 60s
  - 清仓开始 < 5s（EventBus 传播）
  - 所有持仓被清
```

### IT-04: Shadow Mode 全链路

```
前置：REGIME_SHADOW_MODE=true
步骤：
  1. Regime 切换为 TRENDING_DOWN
  2. 用户触发 buy 策略
  3. 风控检查
预期：
  - 日志有 "[SHADOW]" 记录
  - 买入不被阻止（Shadow 不生效）
  - 可对比"如果生效会怎样"
```

### IT-05: API 端点

```
GET /api/agent/regime
预期：
  - status=200
  - global_regime: str
  - per_asset: {BTC, SOL, ETH}
  - chain_regime: {solana, eth, bsc, base}
  - is_crisis: bool
  - hmm_available: {BTC: bool, ...}

GET /api/agent/regime/history?days=7
预期：
  - status=200
  - 返回 regime 快照列表（每 30min 一条）
```

### IT-06: 优化 Agent 读取 Regime 数据

```
步骤：
  1. 确保 agent_regime_history 有数据
  2. 触发优化 Agent
  3. Agent 调用 tool_read_regime_history
预期：返回 transitions + performance_by_regime + false_rate
```

---

## 十、性能测试

| 指标 | 目标 |
|------|------|
| CUSUM 单次计算 | < 1ms |
| HMM classify（200 条特征） | < 50ms |
| HMM train（720 条特征） | < 2s |
| CRISIS check | < 1ms |
| 全局 regime 综合判定 | < 1ms |
| on_kline_close 端到端 | < 100ms（含 CUSUM + feature add） |
| CRISIS → EventBus → 清仓开始 | < 5s |
| 启动历史加载 + HMM 训练 | < 10s |
| 每 30min DB 快照写入 | < 100ms |

---

## 十一、边界测试

### ET-01: 服务重启后恢复

```
步骤：重启 pump-scanner
预期：
  - load_historical_features 从 DB 加载
  - HMM 立即可用（不用等 12h）
  - regime 状态正确
```

### ET-02: hmmlearn 不可用

```
前置：pip uninstall hmmlearn
预期：
  - 规则引擎 fallback 正常工作
  - 所有 regime 功能可用（精度略降）
  - 无 crash
```

### ET-03: Binance WS 断连

```
前置：Binance WS 断开 10 分钟
预期：
  - CUSUM 无新数据但不崩溃
  - HMM 用最后已知特征（stale but safe）
  - CRISIS 检测继续（从 indicator_cache 读）
```

### ET-04: 极端数据

```
输入：return = +0.5（单根 K线涨 50%，MEME 常见）
预期：CUSUM 立即触发 change，HMM 可能分类为 HIGH_VOLATILITY
不应：crash、NaN、overflow
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-23 | 初始版本：29 单元 + 6 集成 + 10 性能 + 4 边界 |
