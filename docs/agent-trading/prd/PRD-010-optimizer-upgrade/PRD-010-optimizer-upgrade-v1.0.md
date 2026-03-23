# PRD-010: 优化 Agent 全链路升级

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-03-23 |
| 所属模块 | Phase 6（优化 Agent O1/O9/O10） |
| 优先级 | P2 |
| 状态 | 待审批 |

---

## 一、调研背景

**现状**：优化 Agent 只优化 scorer 参数（权重/阈值），不能优化 Agent 决策层、风控层、记忆层。

**目标**：从"Scorer Optimizer"升级为"全链路 Optimizer"，覆盖 5 个优化维度。

---

## 二、三个模块

### O1 调度器升级

**现状**：每 3 天 pump/hot 交替

**升级**：
```
三模块轮转：
  Day 0: pump scorer 优化
  Day 3: hot scorer 优化
  Day 6: Agent 全链路优化 ← 新增
  Day 9: pump（循环）

紧急触发（任一条件）：
  - Agent 最近 7 天胜率 < 40% → 立即触发 Agent 优化
  - 最大回撤 > 10% → 立即触发
  - Regime 切换后 48h → 触发适应性检查
```

### O9 提案类型扩展

**现状**：只有 `type: "param"`（修改 config.py 参数）

**升级**：5 种提案类型

| 类型 | 目标 | 审批后动作 |
|------|------|-----------|
| `scorer_param` | scorer 权重/阈值 | 自动 apply 到 config.py |
| `risk_param` | 风控参数（SL/TP/仓位/Regime 参数） | 自动 apply 到 config.py |
| `agent_config` | Agent 配置（辩论轮数/分析师权重/冷却时间） | 自动 apply |
| `memory_rule` | 新增/修改/废弃 semantic 规则 | 写入 agent_memory 表 |
| `monitoring` | 监控口径（命中定义/追踪窗口） | 自动 apply 到 config.py |

### O10 A/B 测试

**方案**：
```
1. 优化 Agent 提出两个方案（A + B）
2. 审批后系统将新信号随机分配：
   50% 用方案 A 参数
   50% 用方案 B 参数
3. 7 天后自动统计两组表现
4. 优化 Agent 读取 A/B 结果
5. 推荐获胜方案 → 全量应用

实现：
  - agent_ab_tests 表记录测试配置
  - 策略触发时根据 random() 决定用 A 或 B 参数
  - 7 天后自动关闭测试 + 统计结果
```

**DB 新增**：
```sql
CREATE TABLE agent_ab_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id_a UUID,
    proposal_id_b UUID,
    config_a JSONB NOT NULL,
    config_b JSONB NOT NULL,
    status TEXT DEFAULT 'running',     -- running/completed/cancelled
    results_a JSONB,                   -- {trades, win_rate, pnl, sharpe}
    results_b JSONB,
    winner TEXT,                       -- 'a'/'b'/null
    started_at TIMESTAMPTZ DEFAULT now(),
    ends_at TIMESTAMPTZ,               -- started_at + 7 days
    completed_at TIMESTAMPTZ
);
```

---

## 三、Optimizer System Prompt 升级

```
现在：
  "你是推荐算法优化专家，目标 hit_rate/recall/F1"

升级后：
  "你是交易系统全链路优化专家。你可以优化：
   1. 信号发现（scorer 权重/阈值）
   2. Agent 决策（分析师权重/辩论轮数/触发阈值）
   3. 风控参数（止损/止盈/仓位/Regime 参数）
   4. 记忆规则（新增/废弃 semantic 规则）
   5. 监控口径（命中定义/追踪窗口）

   优化目标：
   - Agent 策略胜率 ≥ 55%
   - 盈亏比 ≥ 1.5:1
   - 最大回撤 ≤ 15%
   - 夏普率 ≥ 1.5

   工具：
   - read_metrics / read_agent_performance / read_risk_events
   - read_agent_memory / read_regime_history
   - backtest / backtest_agent_strategy
   - propose_change（5 种类型）
   - propose_ab_test（双方案并行测试）

   规则：
   - 先诊断再优化（找到最薄弱环节）
   - 必须回测验证
   - 每次最多改 2 个维度（避免过度调整）
   - A/B 测试优于直接修改（更可靠）"
```

---

## 四、新增工具

```python
# O8 全链路回测（Phase 5 完成后可用）
def tool_backtest_agent_strategy(strategy_spec, days=7):
    """模拟完整决策链路：信号→分析→辩论→决策→风控→执行"""
    ...

# A/B 测试
def tool_propose_ab_test(config_a, config_b, duration_days=7):
    """提交 A/B 测试提案"""
    ...

def tool_read_ab_results(test_id):
    """读取 A/B 测试结果"""
    ...
```

---

## 五、技术影响

| 文件 | 操作 |
|------|------|
| `governor.py` | 修改 — 三模块轮转 + 紧急触发 |
| `optimizer_agent.py` | 修改 — 新 system prompt + Agent 优化模式 |
| `optimizer_tools.py` | 修改 — +3 工具（backtest_agent / propose_ab / read_ab） |
| `agent/ab_test_manager.py` | **新建** — A/B 测试管理 |
| `api/routes_optimizer.py` | 修改 — +A/B 测试端点 |
| `migrations/032_ab_tests.sql` | **新建** |
| Portal `/tuning` | 修改 — 展示 5 种提案类型 + A/B 测试结果 |

---

## 六、成本

| 项目 | 月成本 |
|------|--------|
| Agent 优化轮次（每 9 天 1 次，Opus） | ~$2 |
| A/B 测试（纯计算，无 API） | $0 |
| **总新增** | **~$2/月** |

---

## 七、验收标准

- [ ] Governor 三模块轮转：pump→hot→agent→pump
- [ ] 紧急触发：胜率<40% 或回撤>10% 时立即优化
- [ ] 5 种提案类型：scorer/risk/agent/memory/monitoring
- [ ] 审批后自动 apply 到对应配置
- [ ] A/B 测试：双方案 50/50 分流，7 天后自动统计
- [ ] 优化 Agent 可读取 A/B 结果并推荐获胜方案
- [ ] Portal /tuning 展示 5 种提案 + A/B 测试

---

## 八、v1.1 审查修订

| # | 修订 | 原因 |
|---|------|------|
| Q13 | A/B 按信号分流（非按策略）+ 最低样本 20 笔 + <20 延长到 14 天 | 样本太少统计无意义 |
| Q14 | 紧急优化后下次正常轮次跳过（冷却） | 避免连续优化导致参数震荡 |
| Q15 | memory_rule 提案保护：不超 3 条/软删除/审批展示 | 防止废弃关键规则 |
| Q16 | 5 种提案 apply 统一接口 APPLY_HANDLERS[type](changes) | 每种 apply 逻辑不同需要统一调度 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-23 | 初始版本 |
| v1.1 | 2026-03-24 | 审查修订：4 项优化 |
