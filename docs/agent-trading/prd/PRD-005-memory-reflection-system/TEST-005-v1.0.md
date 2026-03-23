# TEST-005: 记忆与反思系统 — 测试用例

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-005 v1.1 |
| 对应 TECH | TECH-005 |
| 创建日期 | 2026-03-23 |

---

## 一、M12 记忆系统 — 单元测试

### UT-01: WorkingMemory 基础操作

| 用例 | 操作 | 预期 |
|------|------|------|
| 添加事件 | add({"type":"signal"}) | size() == 1 |
| 获取最近 N 条 | add 20 条, get_recent(10) | 返回最后 10 条 |
| 24h 滑动窗口 | add 1 条 _ts=25h前, get_recent(10) | 不包含过期事件 |
| 容量上限 | add 250 条 | size() == 200（deque maxlen） |

### UT-02: EpisodicMemory CRUD

| 用例 | 操作 | 预期 |
|------|------|------|
| 写入 | add(trade_review) | 返回 UUID，DB 有记录 |
| 检索 | search(chain="solana") | 返回按相关性排序的结果 |
| 过期清理 | cleanup_expired() | 删除 expires_at < now 的记录 |
| 缓存命中 | 连续 2 次 search（间隔<30s） | 第 2 次不查 DB |

### UT-03: EpisodicMemory 相关性评分

```
前置：写入 5 条记忆，分别为：
  A: chain=solana, trigger_source=smart_money, mcap=500K
  B: chain=solana, trigger_source=kol, mcap=2M
  C: chain=eth, trigger_source=smart_money, mcap=500K
  D: chain=solana, trigger_source=smart_money, mcap=5M, pnl=-30%
  E: chain=bsc, trigger_source=hot_score, mcap=100K

查询：search(chain="solana", trigger_source="smart_money", mcap_bucket="100K-1M")
预期排序：A(score=7) > D(score=6) > C(score=5) > B(score=4) > E(score=0)
返回 Top 3: [A, D, C]
```

### UT-04: SemanticMemory 规则管理

| 用例 | 操作 | 预期 |
|------|------|------|
| 加载缓存 | get_relevant() | 从 DB 加载到内存 |
| 缓存有效 | 5min 内再次调用 | 不查 DB |
| 缓存过期 | 5min 后调用 | 重新查 DB |
| 相关性排序 | get_relevant(chain="solana") | SOL 相关规则排前面 |

### UT-05: SemanticMemory 条件匹配

```
规则 condition: "rsi > 65 AND regime = HIGH_VOLATILITY"

用例 1: ctx={rsi:70, regime:"HIGH_VOLATILITY"} → 匹配 ✅
用例 2: ctx={rsi:60, regime:"HIGH_VOLATILITY"} → 不匹配（rsi<65）
用例 3: ctx={rsi:70, regime:"TRENDING_UP"} → 不匹配（regime 不对）
用例 4: ctx={rsi:70} → 不匹配（缺少 regime）
```

### UT-06: SemanticMemory 规则晋升

```
前置：某条 condition 在 3 次反思中出现
测试：try_promote(condition, appearances=3, comply_win=4, comply_lose=1,
                   violate_win=0, violate_lose=3)
计算：遵守胜率 80%, 违反胜率 0%, 差距 80% > 15%, 样本 8 >= 5
预期：晋升成功，agent_memory 新增 type=semantic 记录
```

### UT-07: SemanticMemory 规则废弃

```
前置：某条 semantic 规则 comply_win=2, comply_lose=8（遵守胜率 20%）
调用：deprecate_stale()
预期：该规则 is_active 改为 False
```

### UT-08: SemanticMemory 合规记录

```
前置：规则 R1 存在
调用：record_compliance("R1", complied=True, won=True)
预期：R1.comply_win += 1, usage_count += 1, last_used_at 更新
```

---

## 二、M13 反思机制 — 单元测试

### UT-09: ReflectionEngine 基础调用

```
输入：10 笔交易记录 + 5 条活跃规则
调用：run_reflection(trades, rules)
预期：
  - 返回 dict，含 winning_pattern, losing_pattern, new_rules, summary
  - new_rules 是 list，每条含 condition/action/confidence/evidence
  - condition 格式正确（"field op value AND ..."）
```

### UT-10: 紧急反思触发判定

| 用例 | pnl_pct | amount_usd | 预期 |
|------|---------|------------|------|
| 大额大亏 | -30% | $50 | True |
| 大额小亏 | -10% | $100 | False（亏损<25%） |
| 小额大亏 | -40% | $20 | False（金额<$30） |
| 刚好边界 | -25% | $30 | True |

### UT-11: 紧急反思每日上限

```
调用 3 次 run_reflection(is_emergency=True)
预期：前 2 次执行，第 3 次跳过（日限 2 次）
次日重置后：第 1 次又可执行
```

### UT-12: 规则结构化输出验证

```
反思输出：
  {"new_rules": [{"condition": "rsi > 65 AND regime = HIGH_VOLATILITY",
                   "action": "skip_buy", "confidence": 0.75}]}
验证：
  - condition 只含允许的 field（rsi/regime/trigger_source/hold_hours/mcap 等）
  - op 只有 > >= < <= =
  - action 只有 skip_buy / reduce_position / tighten_stop
```

---

## 三、O4 Agent 表现分析 — 单元测试

### UT-13: 基础表现统计

```
前置：agent_executions 有 20 笔交易（10 买 + 10 卖配对）
调用：tool_read_agent_performance(days=7)
预期：
  - total_trades = 20
  - paired_trades = 10
  - actual_win_rate = 实际盈利笔数 / 10
  - by_chain 按链分组正确
```

### UT-14: strategy_type 自动推断

| conditions 包含 | data_sources | 预期 type |
|----------------|-------------|-----------|
| smart_money | any | smart_money_follow |
| kol | kol_mentions | kol_mention |
| price_change | hot_coins | hot_breakout |
| bc_progress | pump_tokens | pump_early |
| 其他 | 其他 | custom |

### UT-15: by_hold_duration 计算

```
前置：交易 A created_at=10:00, exited_at=10:30 (30min)
      交易 B created_at=10:00, exited_at=14:00 (4h)
预期：A 在 "0-1h" 桶，B 在 "4-12h" 桶
```

---

## 四、O5 风控审计 — 单元测试

### UT-16: risk_events 写入

```
前置：risk_manager block 一笔交易
预期：agent_risk_events 新增 1 条，action="block"，含 reason + risk_data
```

### UT-17: risk_events 回填

```
前置：risk_event 创建 6h 前，token 仍在 hot_coins
调用：backfill_risk_events()
预期：
  - token_price_1h_later 有值
  - token_price_4h_later 有值
  - token_min_price_24h 有值（如果已过 24h）
  - was_correct 有判定
```

### UT-18: was_correct 判定逻辑

| 场景 | 24h后价格 | 最大回撤 | 预期 |
|------|----------|---------|------|
| 拦截后暴跌 | -30% | -35% | True（正确拦截） |
| 拦截后涨了 | +20% | -2% | False（不应拦截） |
| 拦截后先跌后涨 | +10% | -25% | True（中间回撤>20%会被止损） |
| 拦截后归零 | 无数据 | 无数据 | True（默认正确） |

### UT-19: 按原因分组统计

```
前置：10 条 block events，其中 liquidity=5（4 correct），honeypot=3（3 correct），btc_crisis=2（1 correct）
调用：tool_read_risk_events(days=7)
预期：by_block_reason 正确统计每种原因的 count 和 accuracy
```

---

## 五、集成测试

### IT-01: 完整记忆写入→检索→注入流程

```
步骤：
  1. EventListener 收到 hot_coin_update 事件
  2. 验证短期记忆有新记录
  3. ActionDispatcher 执行买入
  4. 验证短期记忆有 trade 记录
  5. PositionMonitor 触发止盈
  6. 验证中期记忆有 trade_review 记录
  7. 下一次决策时，LLM prompt 包含记忆上下文
预期：记忆从写入到检索到注入全链路通畅
```

### IT-02: 反思→规则生成→晋升→合规检查

```
步骤：
  1. 积累 10 笔交易
  2. 触发反思
  3. 验证 episodic 有新规则
  4. 模拟再触发 2 次反思（同一规则出现 3 次）
  5. 验证规则晋升到 semantic（需满足样本+胜率差条件）
  6. 下一笔交易触发时，合规检查能匹配到该规则
预期：规则从生成到晋升到使用全链路通畅
```

### IT-03: Optimizer 读取 Agent 表现

```
步骤：
  1. 确保有 agent_executions 数据
  2. 调用 /api/optimizer/trigger
  3. 验证 Optimizer Agent 成功调用 tool_read_agent_performance
  4. 返回数据包含 by_chain / by_strategy_type / memory_stats
预期：优化 Agent 能读取交易 Agent 的完整表现数据
```

### IT-04: 风控审计工具

```
步骤：
  1. 确保有 agent_risk_events 数据（含已回填和未回填）
  2. Optimizer Agent 调用 tool_read_risk_events
  3. 返回数据包含 block_accuracy / by_block_reason
预期：优化 Agent 能评估风控效果
```

### IT-05: API 端点

```
GET /api/agent/memory → 返回记忆统计
  预期：status=200，含 working_count / episodic_count / semantic_count

GET /api/agent/memory/rules → 返回活跃规则列表
  预期：status=200，含规则 condition/action/comply_win_rate
```

---

## 六、性能测试

| 指标 | 目标 |
|------|------|
| 短期记忆写入延迟 | < 1ms（内存操作） |
| 中期记忆写入延迟 | < 100ms（DB insert） |
| 记忆检索延迟（有缓存） | < 5ms |
| 记忆检索延迟（无缓存） | < 200ms |
| Semantic 条件匹配 | < 1ms（10 条规则） |
| 反思生成延迟 | < 15s（Claude Sonnet） |
| Prompt 注入增加的 tokens | ~1,000 tokens |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-23 | 初始版本：19 单元测试 + 5 集成测试 + 6 性能指标 |
