# PRD-005: 记忆与反思系统 + 优化 Agent 表现审计工具

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.1（审查修订版） |
| 创建日期 | 2026-03-23 |
| 修订日期 | 2026-03-23 |
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

### 两者分工（v1.1 明确）

```
反思机制（M13）= "交易员的日记"
  → 即时、感性、基于近期经验
  → 输出：战术级规则（"今天这类信号不要追"）
  → 频率：每天
  → 作用：影响下一次交易决策

优化 Agent（O4/O5）= "基金经理的审计"
  → 系统、理性、基于长期数据
  → 输出：策略级调整（"聪明钱跟单策略的止损从 30% 收紧到 20%"）
  → 频率：每 3 天
  → 作用：修改系统参数/规则
```

---

## 三、详细需求

### 3.1 M12 记忆系统

#### 三层记忆架构

```
短期记忆（Working Memory）
  内容：最近 24h 的信号/交易/价格异动/风控事件
  存储：内存（Python deque）
  生命周期：24h 滑动窗口（v1.1 修订：不再每日清零）
  容量：最近 200 条事件
  注入方式：每次 Agent 决策前，取最近 10 条注入 prompt

中期记忆（Episodic Memory）
  内容：近期交易复盘（买卖配对 + 盈亏 + 原因分析）
  存储：Supabase agent_memory 表（type=episodic）
  生命周期：按 category 不同窗口（v1.1 修订）
    - trade_review（交易复盘）: 14 天
    - market_pattern（市场模式）: 30 天
    - risk_lesson（风控教训）: 30 天
  容量：最多 200 条
  注入方式：按相关性检索 Top 3 条（v1.1 修订：从 5 减至 3）

长期记忆（Semantic Memory）
  内容：从中期记忆提炼的稳定规则（结构化格式）
  存储：Supabase agent_memory 表（type=semantic）
  生命周期：永久（除非被优化 Agent 标记过期或统计验证失败）
  容量：最多 50 条活跃规则
  注入方式：按相关性取 Top 10 注入 prompt（v1.1 修订：不再全量注入）
  缓存：启动时加载到内存，每 5 分钟刷新（v1.1 新增：避免频繁查 DB）
```

#### Token 成本控制（v1.1 新增）

```
每次决策注入的记忆量：
  短期 10 条 × ~30 tokens = 300 tokens
  中期 3 条 × ~80 tokens = 240 tokens
  长期 10 条 × ~50 tokens = 500 tokens
  总计 ~1,040 tokens/次

月成本估算：
  每天 50 次决策 × 1,040 tokens = 52K tokens/天
  月: 1.56M tokens × Sonnet $3/1M input = $4.68/月
```

#### 记忆写入时机

| 事件 | 写入层 | 内容 |
|------|--------|------|
| 策略触发 | 短期 | 触发时间+代币+原因+价格 |
| 交易执行 | 短期 | 买入/卖出+金额+价格+滑点 |
| 止盈/止损触发 | 短期+中期 | 入场→出场完整配对+盈亏+持仓时长+退出原因 |
| 风控拦截 | 短期 | 被拦截的交易+拦截原因 |
| 手动卖出/策略到期 | 短期+中期 | 完整交易闭环（v1.1 新增） |
| 反思生成（M13） | 中期→长期 | 规则提炼 |

#### 短期→中期晋升条件（v1.1 新增）

```
写入中期记忆的条件（满足任一）：
  1. 交易完成闭环（有买有卖，不管盈亏）
  2. 风控拦截事件（block 或 warn）
  3. 单笔盈亏绝对值 > 10%

不写入中期的：
  - 只触发了信号但没执行的
  - 正常的价格更新事件
  - 被 dedup 过滤的重复事件
```

#### 记忆检索逻辑（v1.1 修订：增强相关性评分）

```python
def get_relevant_memories(chain, token_address, trigger_source, market_cap_usd, market_regime):
    """检索与当前决策相关的记忆"""

    # 1. 短期：最近 10 条（24h 滑动窗口，按时间倒序）
    short_term = self._working_memory.get_recent(10)

    # 2. 中期：按相关性排序 Top 3
    #    v1.1 增强评分公式：
    #    score = 0
    #    if same_chain: +2
    #    if same_regime: +2
    #    if same_trigger_source: +3      ← 最重要！同类信号经验最相关
    #    if similar_mcap_range: +2       ← 同规模代币经验更可迁移
    #    if abs(pnl_pct) > 20: +1        ← 大盈大亏经验更值得记
    episodic = self._episodic.search(
        chain=chain, trigger_source=trigger_source,
        mcap_range=_mcap_bucket(market_cap_usd),
        regime=market_regime, limit=3
    )

    # 3. 长期：按相关性取 Top 10（v1.1 修订：不再全量注入）
    semantic = self._semantic_cache.get_relevant(
        chain=chain, trigger_source=trigger_source, limit=10
    )

    return short_term, episodic, semantic
```

#### Prompt 注入格式

```
【短期记忆（最近24h事件）】
- 14:32 买入 SOL/BONK $100 @ $0.00023（聪明钱跟单触发）
- 15:10 BONK 涨 12%，当前 +$12
- 15:45 风控拦截 SOL/MYRO：流动性不足 $8K

【近期经验（相关交易复盘）】
- 3天前买入 SOL/WIF 跟聪明钱：+35%（持仓6h），entry时RSI=45 regime=TRENDING_UP
- 5天前买入 SOL/PEPE 追涨：-18%（止损），entry时RSI=72 regime=HIGH_VOLATILITY

【交易规则（已验证）】
- Rule: rsi>65 AND regime=HIGH_VOLATILITY → skip_buy（遵守胜率72% vs 违反28%，样本12笔）
- Rule: trigger=smart_money_elite AND liquidity>50000 → buy（均值+28%，样本8笔）
- Rule: hold_duration>8h AND token_type=meme → sell（超8h亏损率62%，样本15笔）
```

### 3.2 M13 反思机制

#### 触发条件（v1.1 修订）

```
条件 1: 累计 10 笔新交易完成（买入+卖出配对）
条件 2: 每日 UTC 20:00 定时复盘（不管有没有 10 笔）
条件 3: 单笔亏损 > 25% 且金额 > $30 → 紧急反思（v1.1 修订：从15%提高到25%）
冷却: 每日最多 2 次紧急反思（v1.1 新增）
```

#### 反思流程

```
Step 1: 收集数据
  → 最近 10 笔配对交易（或当日交易）
  → 每笔的入场原因、出场原因、盈亏、持仓时长、市场 regime、trigger_source

Step 2: 调用 Claude 分析（Sonnet，v1.1 修订：从 Haiku 升级）
  Prompt: "你是一个交易复盘专家。以下是最近 10 笔交易记录：
    [交易数据]
    请分析并输出 JSON 格式：
    {
      "winning_pattern": "赢钱交易的共同特征",
      "losing_pattern": "亏钱交易的共同原因",
      "new_rules": [
        {
          "condition": "rsi > 65 AND regime = HIGH_VOLATILITY",
          "action": "skip_buy",
          "confidence": 0.75,
          "evidence": "近 10 笔中 3 笔违反此条件，均亏 >15%"
        }
      ],
      "deprecated_rules": ["rule_id_1"],
      "summary": "一句话总结"
    }"

Step 3: 解析输出（v1.1 修订：结构化规则，不再是自由文本）
  → new_rules 写入 episodic memory（structured_data 存 condition/action JSON）
  → 晋升检查：同一 condition 在 3 次反思中出现 → 候选
  → 候选还需满足统计门槛（v1.1 新增，见下方）

Step 4: 更新统计
  → 记录反思次数、新增规则数、废弃规则数
  → 写入 agent_memory 供优化 Agent 读取
```

#### 规则生命周期（v1.1 修订：增加统计验证）

```
新规则诞生（episodic）
  → 连续 3 次反思出现相同 condition
  → 且样本量 ≥ 5 笔交易验证（v1.1 新增）
  → 且遵守胜率 > 违反胜率至少 15 个百分点（v1.1 新增）
  → 满足以上全部 → 晋升 semantic

semantic 规则维护
  → 每次交易前检查：当前交易是否匹配某条规则的 condition
  → 匹配则记录"遵守/违反" + 后续盈亏
  → 遵守胜率 > 60% → 保持
  → 遵守胜率 < 40%（且样本 ≥ 10）→ 废弃
  → 30 天未匹配到 → 标记待审查（优化 Agent 决定）

示例：
  Rule "rsi>65 AND regime=HIGH_VOLATILITY → skip_buy"
  遵守：8 笔，胜率 75%（赢 6 亏 2）
  违反：4 笔，胜率 25%（赢 1 亏 3）
  差距 50% > 15% → 晋升 ✅
```

#### 规则合规检查（v1.1 新增）

```
在 action_dispatcher._handle_trade() 执行前：
  1. 加载所有 active semantic 规则（从内存缓存）
  2. 用 rule.condition 与当前交易上下文匹配
  3. 如果匹配到规则：
     - 规则说 skip_buy 但要 buy → 记录 violate，发出 warning（不 block）
     - 规则说 skip_buy 且没 buy → 记录 comply
  4. 交易结束后回填盈亏到 comply_win/lose 或 violate_win/lose
  注：规则只 warn 不 block（建议性质，不强制）
```

### 3.3 O4 Agent 表现分析工具

```python
def tool_read_agent_performance(days: int = 7) -> dict:
    """优化 Agent 调用此工具了解交易 Agent 表现"""

    return {
        "period_days": 7,
        "total_trades": 45,
        "paired_trades": 32,
        "open_positions": 13,

        # 胜率
        "actual_win_rate": 0.625,
        "theoretical_win_rate": 0.58,

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
        "win_loss_ratio": 1.8,

        # 按链分析
        "by_chain": {
            "solana": {"trades": 28, "win_rate": 0.68, "avg_pnl": 3.2},
            "eth": {"trades": 10, "win_rate": 0.50, "avg_pnl": 1.5},
            "bsc": {"trades": 7, "win_rate": 0.43, "avg_pnl": -0.8},
        },

        # 按策略类型分析（v1.1：自动推断标签）
        # 推断逻辑：conditions 含 smart_money → smart_money_follow
        #           conditions 含 kol → kol_mention
        #           data_sources 含 hot_coins → hot_breakout
        #           data_sources 含 pump_tokens → pump_early
        "by_strategy_type": {
            "smart_money_follow": {"trades": 15, "win_rate": 0.73, "avg_pnl": 4.1},
            "hot_coin_breakout": {"trades": 12, "win_rate": 0.58, "avg_pnl": 2.3},
            "kol_mention": {"trades": 8, "win_rate": 0.50, "avg_pnl": 1.0},
            "pump_early": {"trades": 10, "win_rate": 0.40, "avg_pnl": -0.5},
        },

        # 按时段分析
        "by_hour": {
            "00-06": {"trades": 5, "win_rate": 0.40},
            "06-12": {"trades": 12, "win_rate": 0.67},
            "12-18": {"trades": 18, "win_rate": 0.72},
            "18-24": {"trades": 10, "win_rate": 0.50},
        },

        # 按持仓时长分析（v1.1：用 exited_at - created_at 实时计算）
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
            "rule_compliance_rate": 0.78,
            "compliance_win_rate": 0.72,
            "violation_win_rate": 0.31,
        },
    }
```

### 3.4 O5 风控审计工具

```python
def tool_read_risk_events(days: int = 7) -> dict:
    """优化 Agent 调用此工具评估风控是否合理"""

    return {
        "period_days": 7,

        # 拦截统计（v1.1：只记录 block + warn，不记录 pass）
        "total_blocked": 23,
        "total_warned": 15,

        # 拦截后代币实际表现（v1.1 增强：多时间窗口+最大回撤）
        "blocked_token_performance": {
            "actually_profitable_24h": 5,
            "actually_dropped_24h": 14,
            "no_data": 4,
            "max_drawdown_exceeded_20pct": 11,  # v1.1 新增：即使24h涨了但中间暴跌>20%
        },

        # v1.1 新增判定逻辑：
        # was_correct = True 如果 max_drawdown_24h > 20%（即使最终涨了，中间会被止损）
        # was_correct = False 如果 min_price 始终高于事件价（完全不应该拦截）
        "block_accuracy": 0.652,  # (14+11重叠后去重)/23
        "missed_opportunity_rate": 0.174,  # 确实不应该拦截的

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

#### 风控回填逻辑（v1.1 新增详细设计）

```
回填数据源（优先级）：
  1. hot_coins 表（代币仍在榜）→ 直接取最新 price
  2. DexScreener API（代币还有交易）→ REST 查询
  3. 无法获取 → 标记 price=0, was_correct=True（归零=正确不买）

回填字段（v1.1 增强）：
  - token_price_1h_later
  - token_price_4h_later
  - token_price_24h_later
  - token_min_price_24h    ← 24h 内最低价
  - token_max_drawdown_24h ← 最大回撤
  - was_correct            ← 综合判定

回填频率：每 6h 扫描未回填的 risk_events
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
    structured_data JSONB,          -- 结构化数据（condition/action JSON，交易配对等）
    importance NUMERIC DEFAULT 0,   -- 重要性评分（0-10）
    chain TEXT,                     -- 关联链
    token_type TEXT,                -- 'meme' | 'hot' | 'btc_eth'
    trigger_source TEXT,            -- 'smart_money' | 'kol' | 'hot_score' | 'pump_score'
    mcap_bucket TEXT,               -- '<100K' | '100K-1M' | '1M-10M' | '>10M'
    market_regime TEXT,             -- 'trending_up' | 'ranging' | 'high_volatility' 等
    usage_count INT DEFAULT 0,      -- 被检索使用次数
    comply_win INT DEFAULT 0,       -- 遵守规则时赢
    comply_lose INT DEFAULT 0,      -- 遵守规则时输
    violate_win INT DEFAULT 0,      -- 违反规则时赢
    violate_lose INT DEFAULT 0,     -- 违反规则时输
    source_reflection_id UUID,      -- 产生该记忆的反思 ID
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ
);
CREATE INDEX idx_memory_type ON agent_memory(type, is_active);
CREATE INDEX idx_memory_source ON agent_memory(trigger_source);

-- 风控拦截记录（v1.1：只记录 block + warn，不记录 pass）
CREATE TABLE IF NOT EXISTS agent_risk_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action TEXT NOT NULL,                -- 'block' | 'warn'（不记录 pass）
    reason TEXT NOT NULL,
    chain TEXT,
    token_address TEXT,
    token_symbol TEXT,
    amount_usd NUMERIC,
    risk_data JSONB,                     -- 触发时的风控数据快照
    token_price_at_event NUMERIC,
    token_price_1h_later NUMERIC,        -- v1.1 新增
    token_price_4h_later NUMERIC,        -- v1.1 新增
    token_price_24h_later NUMERIC,
    token_min_price_24h NUMERIC,         -- v1.1 新增
    token_max_drawdown_24h NUMERIC,      -- v1.1 新增
    was_correct BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_risk_events_action ON agent_risk_events(action, created_at DESC);
```

### 存储预估（v1.1 修正）

```
agent_memory: 30 条/天 × 0.5KB = 15KB/天 × 30 = 0.45MB/月
agent_risk_events: 35 条/天（只 block+warn）× 1.5KB = 52KB/天 × 30 = 1.6MB/月
总计: ~2MB/月（30 天自动清理 risk_events）
```

---

## 五、技术影响

| 文件 | 操作 | 说明 |
|------|------|------|
| `agent/memory/working_memory.py` | **新建** | 短期记忆（deque + 24h 滑动窗口） |
| `agent/memory/episodic_memory.py` | **新建** | 中期记忆（DB CRUD + 增强相关性检索） |
| `agent/memory/semantic_memory.py` | **新建** | 长期记忆（规则管理+统计验证+内存缓存） |
| `agent/memory/reflection.py` | **新建** | 反思引擎（Claude Sonnet 分析，结构化输出） |
| `agent/memory/__init__.py` | **新建** | MemoryManager 统一接口 |
| `agent/event_listener.py` | 修改 | 每次触发后写入短期记忆 |
| `agent/action_dispatcher.py` | 修改 | 交易完成后写入短期+中期；执行前检查规则合规 |
| `agent/position_monitor.py` | 修改 | 止盈止损后写入中期记忆 |
| `agent/risk_manager.py` | 修改 | block/warn 后写入 agent_risk_events（不记录 pass） |
| `agent/strategy_manager.py` | 修改 | create_strategy 自动推断 strategy_type 标签 |
| `agent/llm_parser.py` | 修改 | system prompt 注入记忆上下文 |
| `optimizer_tools.py` | 修改 | 新增 tool_read_agent_performance + tool_read_risk_events |
| `optimizer_agent.py` | 修改 | TOOL_DEFINITIONS + TOOL_MAP 新增 2 个工具 |
| `main.py` | 修改 | 注册反思定时任务 + risk_events 回填任务 |
| `api/routes_agent.py` | 修改 | 新增 /api/agent/memory 端点 |
| `db_cleanup.py` | 修改 | 新增 agent_risk_events 30 天清理 |
| `migrations/028_agent_memory.sql` | **新建** | 2 张表 |

---

## 六、Claude API 成本

| 操作 | 模型 | 频率 | 单次成本 | 月成本 |
|------|------|------|---------|--------|
| 反思分析 | Sonnet（v1.1 修订） | ~30 次/月 | ~$0.01 | ~$0.30 |
| 记忆注入（增加 prompt） | Sonnet | 每次决策 +1K tokens | +$0.003 | ~$4.68 |
| **总新增** | | | | **~$5/月** |

---

## 七、验收标准

### M12 记忆系统
- [ ] 短期记忆：24h 滑动窗口，交易触发后 1s 内写入
- [ ] 中期记忆：交易闭环后自动生成复盘记录
- [ ] 长期记忆：活跃规则 ≤ 50 条，按相关性取 Top 10 注入 prompt
- [ ] 记忆检索：trigger_source + chain + mcap_bucket + regime 多维相关性评分
- [ ] 自动清理：trade_review 14 天 / market_pattern + risk_lesson 30 天
- [ ] 性能：Semantic 规则内存缓存 5min 刷新，Episodic 缓存 30s

### M13 反思机制
- [ ] 每 10 笔交易自动触发反思
- [ ] 每日 UTC 20:00 定时反思
- [ ] 紧急反思：亏损 >25% 且金额 >$30，每日最多 2 次
- [ ] 反思输出结构化 JSON（condition/action/confidence/evidence）
- [ ] 晋升条件：3 次出现 + ≥5 笔验证 + 遵守胜率领先 ≥15%
- [ ] 废弃条件：遵守胜率 <40%（样本≥10）或 30 天未匹配

### O4 Agent 表现分析
- [ ] 按链/策略类型/时段/持仓时长 4 个维度分析
- [ ] strategy_type 自动推断（smart_money/kol/hot/pump/custom）
- [ ] 记忆系统效果统计（compliance_rate + compliance_win_rate）

### O5 风控审计
- [ ] 只记录 block + warn 事件（不记录 pass）
- [ ] 6h 定时回填：1h/4h/24h 价格 + 最低价 + 最大回撤
- [ ] was_correct 综合判定（考虑最大回撤，不只看 24h 终点价）
- [ ] 按拦截原因分组统计准确率
- [ ] 30 天自动清理

---

## 八、风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 记忆 prompt 过长超 token | 低 | 高 | 严格限制：短期10+中期3+长期10 ≈ 1K tokens |
| 反思生成过拟合规则 | 中 | 中 | 3 次验证 + ≥5 笔样本 + 15% 胜率差门槛 |
| 规则合规检查增加延迟 | 低 | 低 | 规则从内存缓存读取，<1ms |
| 风控回填延迟 | 低 | 低 | 6h 定时任务，不影响实时风控 |
| Supabase 存储增加 | 低 | 低 | ~2MB/月 + 30 天清理 |
| Sonnet 反思成本 | 低 | 低 | ~$0.30/月（30 次 × $0.01） |

---

## 九、v1.1 修订记录

| # | 修订 | 原因 |
|---|------|------|
| Q1 | 短期记忆改为 24h 滑动窗口 | 每日清零会丢失跨日上下文 |
| Q2 | Semantic Top 10 + 短期 10 + 中期 3 | 控制 token 成本从 $15.75→$4.68/月 |
| Q3 | 相关性增加 trigger_source + mcap_bucket | 同类信号经验最相关 |
| Q4 | 明确短期→中期晋升条件 | 避免过多无用记忆写入 |
| Q5 | 按 category 不同过期窗口 | 交易复盘 14 天，风控教训 30 天 |
| Q6 | Semantic 内存缓存 5min + Episodic 缓存 30s | 避免高频场景 DB 瓶颈 |
| Q7 | 反思用 Sonnet 不用 Haiku | 复杂交易模式分析需要更强推理 |
| Q8 | 规则结构化输出 condition/action JSON | 解决"同一规则不同措辞"匹配问题 |
| Q9 | 紧急反思阈值 25% + 金额 >$30 + 每日上限 2 | 避免 MEME 高波动频繁触发 |
| Q10 | 晋升需 ≥5 笔 + 胜率差 ≥15% | 避免过拟合 |
| Q11 | 明确反思 vs 优化 Agent 分工 | 日记 vs 审计，战术 vs 策略 |
| Q12 | strategy_type 自动推断 | 解决无分类标签问题 |
| Q13 | 交易前检查规则合规 + 回填盈亏 | 实现 compliance_rate 统计 |
| Q14 | hold_duration 实时计算 | 不需新增 DB 字段 |
| Q15 | was_correct 看最大回撤不只看终点 | 更准确的风控评估 |
| Q16 | 回填数据源优先级 + 归零处理 | 解决代币下架查不到价格问题 |
| Q17 | 只记录 block+warn + 30 天清理 | 存储从 7MB→2MB/月 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-23 | 初始版本 |
| v1.1 | 2026-03-23 | 审查修订：17 项优化（成本/性能/准确性/分工） |
