# TECH-010: 优化 Agent 全链路升级 — 技术方案

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-010 v1.1 |
| 创建日期 | 2026-03-24 |

---

## 一、文件结构

```
services/pump-scanner/
├── governor.py                      # 修改：三模块轮转 + 紧急触发 + 冷却
├── optimizer_agent.py               # 修改：新 system prompt + Agent 优化模式
├── optimizer_tools.py               # 修改：+3 工具 + 5 种提案 apply
├── agent/ab_test_manager.py         # 新建：A/B 测试管理
├── api/routes_optimizer.py          # 修改：+A/B 测试端点
├── migrations/032_ab_tests.sql      # 新建
└── apps/portal/.../tuning           # 修改：展示 5 种提案 + A/B
```

---

## 二、governor.py 三模块轮转

```python
async def run_governor():
    """v1.1: 三模块轮转 + 紧急触发"""
    day_of_year = datetime.utcnow().timetuple().tm_yday

    # 紧急触发检查（v1.1 Q14: 紧急后冷却）
    if _check_emergency_trigger():
        if not _is_in_cooldown():
            mode = "agent"
            _set_cooldown(days=6)  # 紧急后跳过下次正常轮
        else:
            log.info("[Governor] Emergency skipped: in cooldown")
            return

    # 正常轮转：0=pump, 3=hot, 6=agent
    elif day_of_year % 9 < 3:
        mode = "pump"
    elif day_of_year % 9 < 6:
        mode = "hot"
    else:
        mode = "agent"

    # 检查冷却（紧急优化后跳过正常轮）
    if _is_in_cooldown() and mode != "agent":
        log.info("[Governor] Skipping %s: post-emergency cooldown", mode)
        return

    await run_optimization(mode)

def _check_emergency_trigger():
    """胜率<40% 或 回撤>10% → 紧急"""
    from agent.performance_analytics import get_strategy_performance
    # 查最近 7 天所有策略平均胜率
    # 查最近 7 天最大回撤
    return win_rate < 0.40 or max_drawdown > 10
```

---

## 三、5 种提案 apply 统一接口（v1.1 Q16）

```python
# optimizer_tools.py

APPLY_HANDLERS = {
    "scorer_param": _apply_scorer,
    "risk_param": _apply_risk,
    "agent_config": _apply_agent_config,
    "memory_rule": _apply_memory_rule,
    "monitoring": _apply_monitoring,
}

def apply_proposal(proposal):
    """统一 apply 入口"""
    ptype = proposal.get("type", "scorer_param")
    handler = APPLY_HANDLERS.get(ptype)
    if not handler:
        raise ValueError(f"Unknown proposal type: {ptype}")
    return handler(proposal["changes"])

def _apply_scorer(changes):
    """修改 config.py scorer 参数"""
    # 已有逻辑

def _apply_risk(changes):
    """修改 config.py RISK_* / REGIME_RISK_PARAMS"""
    import config
    for key, value in changes.items():
        if hasattr(config, key):
            setattr(config, key, value)

def _apply_agent_config(changes):
    """修改 Agent 配置（辩论轮数/冷却时间等）"""
    import config
    for key, value in changes.items():
        if hasattr(config, key):
            setattr(config, key, value)

def _apply_memory_rule(changes):
    """v1.1 Q15: 操作 agent_memory 表（保护机制）"""
    db = get_db()
    new_rules = changes.get("add_rules", [])
    deprecate_ids = changes.get("deprecate_rule_ids", [])

    # 保护：不超过 3 条废弃
    if len(deprecate_ids) > 3:
        raise ValueError("Cannot deprecate >3 rules at once")

    # 废弃 = 软删除（is_active=False，可恢复）
    for rule_id in deprecate_ids:
        db.table("agent_memory").update({"is_active": False}).eq("id", rule_id).execute()

    # 新增规则 importance=5（中等）
    for rule in new_rules:
        rule["importance"] = min(rule.get("importance", 5), 5)
        rule["type"] = "semantic"
        rule["is_active"] = True
        db.table("agent_memory").insert(rule).execute()

def _apply_monitoring(changes):
    """修改监控口径"""
    import config
    for key, value in changes.items():
        if hasattr(config, key):
            setattr(config, key, value)
```

---

## 四、ab_test_manager.py

```python
"""A/B 测试管理器"""

class ABTestManager:
    async def create_test(self, config_a, config_b, duration_days=7):
        """创建 A/B 测试"""
        row = {
            "config_a": config_a,
            "config_b": config_b,
            "status": "running",
            "ends_at": (datetime.utcnow() + timedelta(days=duration_days)).isoformat(),
        }
        res = db.table("agent_ab_tests").insert(row).execute()
        return res.data[0]["id"]

    def get_group(self, test_id) -> str:
        """v1.1 Q13: 按信号随机分流"""
        import random
        return "a" if random.random() < 0.5 else "b"

    def get_config_for_group(self, test_id, group) -> dict:
        """获取对应组的配置"""
        test = db.table("agent_ab_tests").select("*").eq("id", test_id).execute()
        if test.data:
            return test.data[0][f"config_{group}"]
        return {}

    async def check_completion(self):
        """检查到期测试 + 统计结果"""
        running = db.table("agent_ab_tests").select("*").eq("status", "running") \
            .lte("ends_at", datetime.utcnow().isoformat()).execute()

        for test in (running.data or []):
            test_id = test["id"]
            # 统计 A 组和 B 组表现
            a_trades = db.table("agent_executions").select("*") \
                .eq("ab_test_id", test_id).eq("ab_group", "a").execute()
            b_trades = db.table("agent_executions").select("*") \
                .eq("ab_test_id", test_id).eq("ab_group", "b").execute()

            # v1.1 Q13: 样本不足延长
            total = len(a_trades.data or []) + len(b_trades.data or [])
            if total < 20:
                # 延长 7 天
                new_end = (datetime.utcnow() + timedelta(days=7)).isoformat()
                db.table("agent_ab_tests").update({"ends_at": new_end}).eq("id", test_id).execute()
                continue

            results_a = _calc_group_stats(a_trades.data)
            results_b = _calc_group_stats(b_trades.data)
            winner = "a" if results_a["sharpe"] > results_b["sharpe"] else "b"

            db.table("agent_ab_tests").update({
                "status": "completed",
                "results_a": results_a,
                "results_b": results_b,
                "winner": winner,
                "completed_at": datetime.utcnow().isoformat(),
            }).eq("id", test_id).execute()
```

---

## 五、Optimizer System Prompt

```python
AGENT_OPTIMIZER_SYSTEM_PROMPT = """
你是交易系统全链路优化专家。你可以优化 5 个维度：
1. 信号发现（scorer 权重/阈值）— propose_change type=scorer_param
2. Agent 决策（分析师权重/辩论轮数/触发阈值）— type=agent_config
3. 风控参数（止损/止盈/仓位/Regime 参数）— type=risk_param
4. 记忆规则（新增/废弃 semantic 规则）— type=memory_rule
5. 监控口径（命中定义/追踪窗口）— type=monitoring

优化目标：
- Agent 策略胜率 ≥ 55%
- 盈亏比 ≥ 1.5:1
- 最大回撤 ≤ 15%
- 夏普率 ≥ 1.5

工作流程：
1. read_agent_performance → 了解当前表现
2. read_risk_events → 风控是否合理
3. read_agent_memory → 记忆规则有效性
4. read_regime_history → 市场适应性
5. 找到最薄弱环节
6. backtest 验证改动
7. propose_change（每次最多改 2 个维度）

规则：
- A/B 测试优于直接修改
- memory_rule 一次最多废弃 3 条
- 必须回测验证后才能提交
"""
```

---

## 六、Migration SQL

```sql
CREATE TABLE IF NOT EXISTS agent_ab_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id_a UUID,
    proposal_id_b UUID,
    config_a JSONB NOT NULL,
    config_b JSONB NOT NULL,
    status TEXT DEFAULT 'running',
    results_a JSONB,
    results_b JSONB,
    winner TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    ends_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_ab_status ON agent_ab_tests(status);

-- agent_executions 新增 A/B 字段
ALTER TABLE agent_executions
    ADD COLUMN IF NOT EXISTS ab_test_id UUID,
    ADD COLUMN IF NOT EXISTS ab_group TEXT;
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-24 | 初始版本（含 v1.1 审查修订） |
