# PRD-005: 记忆与反思系统 + 优化 Agent 表现审计工具

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-03-23 |
| 所属模块 | Phase 1（交易 Agent M12/M13 + 优化 Agent O4/O5） |
| 优先级 | P0 |
| 状态 | 待审批 |

---

## 一、调研背景

### 1.1 行业研究数据

| 论文/产品 | 核心发现 | 数据支撑 |
|-----------|---------|---------|
| **FinMem**（IEEE 发表） | 三层记忆（工作/情景/语义）一致性提升最大 | 6 个月回测，累计收益最高且一致性最好 |
| **CryptoTrade**（EMNLP 2024） | 反思机制在多种加密货币和市场条件下均优于基线 | BTC/ETH/SOL 等多币种验证 |
| **LLM_trader** | 语义规则系统：每 10 笔交易提炼规则存入向量库 | 5 连胜才生成正面规则避免过拟合 |
| **47 系统实测报告** | 97% 的系统失败是因为不能从错误中学习 | $11,400 亏损，仅 3% 存活 |

### 1.2 技术路线选择

| 方案 | 存储方式 | 优点 | 缺点 | 选择 |
|------|---------|------|------|------|
| **向量数据库**（Pinecone/Chroma） | 语义嵌入 | 模糊检索好 | 需额外服务，成本高 | ❌ |
| **结构化 DB**（Supabase） | JSON + 关键字 | 已有基础设施，零成本 | 语义检索弱 | ✅ |
| **混合方案** | DB + 本地嵌入 | 两者兼得 | 复杂度高 | ❌（后续可升级） |

**选择理由**：我们的记忆内容是结构化的（交易记录+反思规则+市场状态），不需要语义模糊检索。用 Supabase JSON 列 + 关键字匹配足够，零额外成本。

---

## 二、需求概述

### 交易 Agent 侧（M12 + M13）

**M12 记忆系统**：让 Agent 记住过去的交易经验，决策时参考历史

**M13 反思机制**：定期复盘交易胜败，提炼可复用的交易规则

### 优化 Agent 侧（O4 + O5）

**O4 Agent 表现分析工具**：让优化 Agent 能读取交易 Agent 的实际表现数据

**O5 风控审计工具**：让优化 Agent 能评估风控拦截是否合理

---

## 三、详细需求

### 3.1 M12 记忆系统

#### 三层记忆架构

```
短期记忆（Working Memory）
  内容：当日信号/交易/价格异动/风控事件
  存储：内存（Python dict）
  生命周期：每日 UTC 00:00 清零
  容量：最近 100 条事件
  注入方式：每次 Agent 决策前，最近 20 条注入 prompt

中期记忆（Episodic Memory）
  内容：近 14 天交易复盘（买卖配对 + 盈亏 + 原因分析）
  存储：Supabase agent_memory 表（type=episodic）
  生命周期：14 天滚动窗口，超期自动清理
  容量：最多 200 条
  注入方式：检索与当前代币/链/市场状态相关的 Top 5 条

长期记忆（Semantic Memory）
  内容：从中期记忆提炼的稳定规则
  存储：Supabase agent_memory 表（type=semantic）
  生命周期：永久（除非被优化 Agent 标记过期）
  容量：最多 50 条活跃规则
  注入方式：全部注入 system prompt（50 条 × 1 行 ≈ 2K tokens）
```

#### 记忆写入时机

| 事件 | 写入层 | 内容 |
|------|--------|------|
| 策略触发 | 短期 | 触发时间+代币+原因+价格 |
| 交易执行 | 短期 | 买入/卖出+金额+价格+滑点 |
| 止盈/止损触发 | 短期+中期 | 入场→出场完整配对+盈亏+持仓时长+退出原因 |
| 风控拦截 | 短期 | 被拦截的交易+拦截原因+代币后续实际走势（24h 后回填） |
| 反思生成（M13） | 中期→长期 | 规则提炼 |

#### 记忆检索逻辑

```python
def get_relevant_memories(chain, token_address, market_regime):
    """检索与当前决策相关的记忆"""

    # 1. 短期：最近 20 条（按时间倒序）
    short_term = self._working_memory[-20:]

    # 2. 中期：按相关性排序 Top 5
    #    相关性 = 同链(+3) + 同类代币(+2) + 同 regime(+2) + 盈亏绝对值(+1~3)
    episodic = db.table("agent_memory").select("*") \
        .eq("type", "episodic").eq("is_active", True) \
        .order("importance", desc=True).limit(20).execute()
    # 按相关性打分后取 Top 5

    # 3. 长期：全部活跃规则
    semantic = db.table("agent_memory").select("*") \
        .eq("type", "semantic").eq("is_active", True).execute()

    return short_term, episodic[:5], semantic
```

#### 注入 prompt 格式

```
【短期记忆（今日事件）】
- 14:32 买入 SOL/BONK $100 @ $0.00023（聪明钱跟单触发）
- 15:10 BONK 涨 12%，当前 +$12
- 15:45 风控拦截 SOL/MYRO：流动性不足 $8K

【近期经验（相关交易复盘）】
- 3天前买入 SOL/WIF 跟聪明钱：+35%（持仓6h），entry时RSI=45 regime=TRENDING_UP
- 5天前买入 SOL/PEPE 追涨：-18%（止损），entry时RSI=72 regime=HIGH_VOLATILITY
- 7天前买入 ETH/SHIB 热币榜：+8%（手动卖出），流动性充足$500K

【交易规则（已验证的长期经验）】
- Rule #1: RSI>65 且 regime=HIGH_VOLATILITY 时不做多（近30天验证：遵守=胜率72%，违反=胜率28%）
- Rule #2: 聪明钱 elite 钱包买入 + 流动性>$50K 的代币跟单胜率最高（均值+28%）
- Rule #3: 持仓超过 8h 的 MEME 币应该卖出（超过 8h 后亏损概率从 35% 升至 62%）
```

### 3.2 M13 反思机制

#### 触发条件

```
条件 1: 累计 10 笔新交易完成（买入+卖出配对）
条件 2: 每日 UTC 20:00 定时复盘（不管有没有 10 笔）
条件 3: 单笔亏损 > 15% 立即触发紧急反思
```

#### 反思流程

```
Step 1: 收集数据
  → 最近 10 笔配对交易（或当日交易）
  → 每笔的入场原因、出场原因、盈亏、持仓时长、市场 regime

Step 2: 调用 Claude 分析（Haiku，低成本）
  Prompt: "你是一个交易复盘专家。以下是最近 10 笔交易记录：
    [交易数据]
    请分析：
    1. 哪些交易赚钱了？共同特征是什么？
    2. 哪些交易亏钱了？共同原因是什么？
    3. 提炼 1-3 条可复用的交易规则（格式：条件 → 动作）
    4. 哪些旧规则应该被修改或废弃？"

Step 3: 解析输出
  → 新规则写入 episodic memory
  → 如果某条规则连续 3 次反思都被提到 → 晋升到 semantic memory
  → 如果某条 semantic 规则在最近 5 次反思中都未提到 → 标记过期

Step 4: 更新统计
  → 记录反思次数、新增规则数、废弃规则数
  → 写入 agent_memory_stats 供优化 Agent 读取
```

#### 规则生命周期

```
新规则诞生（episodic）
  → 连续 3 次反思出现 → 晋升 semantic
  → 5 次反思未出现 → 过期删除

semantic 规则
  → 每次使用后记录"遵守/违反"+"盈亏结果"
  → 遵守胜率 > 60% → 保持
  → 遵守胜率 < 40% → 废弃
  → 30 天未使用 → 标记待审查（优化 Agent 决定保留/废弃）
```

### 3.3 O4 Agent 表现分析工具

#### 功能

```python
def tool_read_agent_performance(days: int = 7) -> dict:
    """优化 Agent 调用此工具了解交易 Agent 表现"""

    return {
        # 总览
        "period_days": 7,
        "total_trades": 45,
        "paired_trades": 32,  # 有买有卖的配对
        "open_positions": 13,

        # 胜率
        "actual_win_rate": 0.625,     # 实际买卖盈利
        "theoretical_win_rate": 0.58, # D3 涨幅理论命中

        # PNL
        "total_invested_usd": 3200,
        "total_returned_usd": 3680,
        "realized_pnl_usd": 480,
        "unrealized_pnl_usd": 120,
        "avg_pnl_per_trade_pct": 2.8,
        "best_trade_pct": 45.2,
        "worst_trade_pct": -22.1,

        # 风险
        "max_drawdown_pct": 8.5,
        "sharpe_ratio": 1.42,
        "win_loss_ratio": 1.8,   # 平均盈利 / 平均亏损

        # 按维度分析
        "by_chain": {
            "solana": {"trades": 28, "win_rate": 0.68, "avg_pnl": 3.2},
            "eth": {"trades": 10, "win_rate": 0.50, "avg_pnl": 1.5},
            "bsc": {"trades": 7, "win_rate": 0.43, "avg_pnl": -0.8},
        },
        "by_strategy_type": {
            "smart_money_follow": {"trades": 15, "win_rate": 0.73, "avg_pnl": 4.1},
            "hot_coin_breakout": {"trades": 12, "win_rate": 0.58, "avg_pnl": 2.3},
            "kol_mention": {"trades": 8, "win_rate": 0.50, "avg_pnl": 1.0},
            "pump_early": {"trades": 10, "win_rate": 0.40, "avg_pnl": -0.5},
        },
        "by_hour": {
            "00-06": {"trades": 5, "win_rate": 0.40},
            "06-12": {"trades": 12, "win_rate": 0.67},
            "12-18": {"trades": 18, "win_rate": 0.72},
            "18-24": {"trades": 10, "win_rate": 0.50},
        },
        "by_hold_duration": {
            "0-1h": {"trades": 8, "win_rate": 0.75, "avg_pnl": 5.2},
            "1-4h": {"trades": 15, "win_rate": 0.67, "avg_pnl": 3.1},
            "4-12h": {"trades": 12, "win_rate": 0.50, "avg_pnl": 0.8},
            "12h+": {"trades": 10, "win_rate": 0.30, "avg_pnl": -2.5},
        },

        # 记忆系统效果
        "memory_stats": {
            "total_reflections": 8,
            "active_semantic_rules": 12,
            "rule_compliance_rate": 0.78,  # 遵守规则的比例
            "compliance_win_rate": 0.72,   # 遵守时的胜率
            "violation_win_rate": 0.31,    # 违反时的胜率
        },
    }
```

### 3.4 O5 风控审计工具

#### 功能

```python
def tool_read_risk_events(days: int = 7) -> dict:
    """优化 Agent 调用此工具评估风控是否合理"""

    return {
        "period_days": 7,

        # 拦截统计
        "total_blocked": 23,
        "total_warned": 15,
        "total_passed": 120,

        # 拦截后代币实际表现（24h 后回填）
        "blocked_token_performance": {
            "actually_went_up_20pct": 5,   # 被拦截但实际涨了 20%+
            "actually_went_down": 14,       # 被拦截且实际跌了（正确拦截）
            "no_significant_move": 4,       # 没大变化
        },
        "block_accuracy": 0.609,  # 14/23 = 正确拦截率
        "missed_opportunity_rate": 0.217,  # 5/23 = 错误拦截率

        # 放行后实际表现
        "passed_token_performance": {
            "profitable": 75,
            "losing": 45,
        },
        "pass_accuracy": 0.625,  # 75/120

        # 按拦截原因分析
        "by_block_reason": {
            "liquidity_too_low": {"count": 8, "correct": 7, "accuracy": 0.875},
            "position_limit": {"count": 5, "correct": 3, "accuracy": 0.60},
            "daily_loss_limit": {"count": 4, "correct": 4, "accuracy": 1.0},
            "honeypot": {"count": 3, "correct": 3, "accuracy": 1.0},
            "btc_crisis": {"count": 2, "correct": 1, "accuracy": 0.50},
            "chain_concentration": {"count": 1, "correct": 0, "accuracy": 0.0},
        },

        # 优化建议数据
        "potential_improvements": [
            "chain_concentration 拦截准确率 0%，建议放宽或移除",
            "btc_crisis 阈值可能过敏感（50% 误拦截），建议从 3% 调至 5%",
            "liquidity 检查效果最好（87.5% 准确），建议保持",
        ],
    }
```

---

## 四、数据库设计

### 新增表：agent_memory

```sql
CREATE TABLE IF NOT EXISTS agent_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL,             -- 'episodic' | 'semantic'
    category TEXT NOT NULL,         -- 'trade_review' | 'rule' | 'market_pattern' | 'risk_lesson'
    content TEXT NOT NULL,          -- 自然语言描述
    structured_data JSONB,          -- 结构化数据（交易配对/条件/统计）
    importance NUMERIC DEFAULT 0,   -- 重要性评分（0-10）
    chain TEXT,                     -- 关联链（可空）
    token_type TEXT,                -- 'meme' | 'hot' | 'btc_eth'（可空）
    market_regime TEXT,             -- 关联 regime（可空）
    usage_count INT DEFAULT 0,      -- 被检索使用次数
    comply_win INT DEFAULT 0,       -- 遵守规则时赢的次数
    comply_lose INT DEFAULT 0,      -- 遵守规则时输的次数
    violate_win INT DEFAULT 0,      -- 违反规则时赢的次数
    violate_lose INT DEFAULT 0,     -- 违反规则时输的次数
    source_reflection_id UUID,      -- 产生该记忆的反思 ID
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ,         -- episodic 14天后过期
    last_used_at TIMESTAMPTZ
);
CREATE INDEX idx_memory_type ON agent_memory(type, is_active);
CREATE INDEX idx_memory_category ON agent_memory(category);

-- 风控拦截记录（供 O5 审计）
CREATE TABLE IF NOT EXISTS agent_risk_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action TEXT NOT NULL,           -- 'block' | 'warn' | 'pass'
    reason TEXT NOT NULL,           -- 拦截原因
    chain TEXT,
    token_address TEXT,
    token_symbol TEXT,
    amount_usd NUMERIC,
    risk_data JSONB,               -- 触发时的风控数据快照
    token_price_at_event NUMERIC,  -- 事件时价格
    token_price_24h_later NUMERIC, -- 24h 后价格（回填）
    token_pct_24h NUMERIC,         -- 24h 后涨跌幅（回填）
    was_correct BOOLEAN,           -- 拦截是否正确（回填）
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_risk_events_action ON agent_risk_events(action, created_at DESC);
```

---

## 五、技术影响

| 文件 | 操作 | 说明 |
|------|------|------|
| `agent/memory/working_memory.py` | **新建** | 短期记忆（内存 dict + 100 条上限） |
| `agent/memory/episodic_memory.py` | **新建** | 中期记忆（DB CRUD + 相关性检索） |
| `agent/memory/semantic_memory.py` | **新建** | 长期记忆（规则管理 + 生命周期） |
| `agent/memory/reflection.py` | **新建** | 反思引擎（Claude Haiku 分析） |
| `agent/memory/__init__.py` | **新建** | MemoryManager 统一接口 |
| `agent/event_listener.py` | 修改 | 每次触发后写入短期记忆 |
| `agent/action_dispatcher.py` | 修改 | 交易完成后写入短期+中期记忆 |
| `agent/position_monitor.py` | 修改 | 止盈止损后写入中期记忆 |
| `agent/risk_manager.py` | 修改 | 拦截/放行后写入 agent_risk_events |
| `agent/llm_parser.py` | 修改 | system prompt 注入记忆上下文 |
| `optimizer_tools.py` | 修改 | 新增 tool_read_agent_performance + tool_read_risk_events |
| `optimizer_agent.py` | 修改 | TOOL_DEFINITIONS + TOOL_MAP 新增 2 个工具 |
| `main.py` | 修改 | 注册反思定时任务（每日 UTC 20:00） |
| `api/routes_agent.py` | 修改 | 新增 /api/agent/memory 端点 |
| `migrations/028_agent_memory.sql` | **新建** | 2 张表 |

---

## 六、Claude API 成本

| 操作 | 模型 | 频率 | 单次成本 | 月成本 |
|------|------|------|---------|--------|
| 反思分析 | Haiku | 每日 1 次 + 每 10 笔 | ~$0.002 | ~$0.12 |
| 记忆注入（增加 prompt 长度） | Sonnet | 每次决策 | +$0.001 | ~$1.5 |
| **总新增** | | | | **~$1.6/月** |

---

## 七、验收标准

### M12 记忆系统
- [ ] 短期记忆：交易触发后 1s 内写入，Agent 下次决策时可见
- [ ] 中期记忆：止盈止损后自动生成交易复盘记录
- [ ] 长期记忆：活跃规则 ≤ 50 条，全部注入 prompt
- [ ] 记忆检索：按相关性返回 Top 5 中期记忆
- [ ] 14 天自动清理：过期 episodic 记忆被删除

### M13 反思机制
- [ ] 每 10 笔交易自动触发反思
- [ ] 每日 UTC 20:00 定时反思
- [ ] 单笔亏损 > 15% 立即触发紧急反思
- [ ] 反思输出 1-3 条新规则
- [ ] 连续 3 次出现的规则自动晋升 semantic
- [ ] 5 次未出现的规则自动过期

### O4 Agent 表现分析
- [ ] 优化 Agent 可通过工具读取按链/策略/时段/持仓时长维度的表现
- [ ] 数据与 agent_executions 实际数据一致

### O5 风控审计
- [ ] 风控拦截后 24h 自动回填代币实际涨跌
- [ ] 优化 Agent 可读取拦截准确率
- [ ] 按拦截原因分组统计

---

## 八、风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 记忆 prompt 过长导致 Claude 超 token | 中 | 高 | 严格限制：短期 20 条 + 中期 5 条 + 长期 50 条 ≈ 3K tokens |
| 反思生成错误规则 | 中 | 中 | 规则需 3 次验证才晋升；有遵守/违反胜率统计 |
| 风控回填延迟 | 低 | 低 | 24h 定时任务回填，不影响实时风控 |
| Supabase 存储增加 | 低 | 低 | agent_memory 预计每月 <1MB |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-23 | 初始版本 |
