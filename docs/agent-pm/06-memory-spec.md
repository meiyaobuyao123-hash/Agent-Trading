# 06 Memory Spec（Agent 记忆系统）

> 定义 Agent 的 4 层记忆：写什么、留多久、谁读、怎么遗忘、怎么晋升。
> 是 **S04 / S07 / T04** 的底层支撑，也是 Agent "记得住用户" 的硬核依据。

| 字段 | 值 |
|------|---|
| Status | 🟢 v0.1 Draft |
| Version | v0.1 |
| Owner | 产品负责人 |
| Target Release | v1 MVP - 2026 Q3 |

---

## 0. 为什么要有记忆系统

### 0.1 没有记忆 vs 有记忆

| 场景 | 无记忆 Agent | 有记忆 Agent |
|------|-------------|-------------|
| 用户反复亏同一类币 | 每次都重新分析，不会"变聪明" | 第 3 次触发时主动警告"你过去 2 次这类币都亏了" |
| 用户"不喜欢某类风险" | 每次都要重复告诉 Agent | Agent 自动避开 |
| 辅助复盘 | 只能看当日数据 | 可以发现"周五胜率系统性偏低"的长期规律 |
| Thesis 生成 | 每次从零 | 引用"过去类似情况"（Vision 核心原则）|

### 0.2 与 Vision / PRD 的映射

- Vision **产品原则 4 "沉淀用户判断框架"** → 通过 Semantic Memory 落地
- Vision **原则 5 "记得住"** → Episodic + Semantic 共同实现
- PRD **§ 2 Thesis 必引用历史类似案例** → T04 recall_memory 查 Episodic
- PRD **§ 7 规则采纳** → T11 approve_rule 写 Semantic
- PRD **§ 3.2.1 共创流程 Stage ②** → S04 读取 Episodic 作为澄清依据

---

## 1. Memory Layers Overview（4 层记忆）

| Layer | 存什么 | TTL | 存储介质 | 读取时机 | 写入时机 |
|-------|-------|-----|---------|---------|---------|
| **Working** 工作记忆 | 当前 session 上下文（chat 历史 / draft 策略）| 单次会话 | 进程内 + Redis（v1+）| 所有 Skill | 每轮对话 |
| **Episodic** 情景记忆 | 单次"事件-决策-结果"经历 | 14-30 天 | Postgres `agent_memory` (type=episodic) | T04 recall_memory → S01/S03/S07/S08 | 每次 thesis / trade 闭仓 |
| **Semantic** 语义记忆 | 从 Episodic 提炼的**活跃规则** | 30 天无匹配废弃 | Postgres `agent_memory` (type=semantic) | L2/L3 thesis 生成时注入 prompt | T11 approve_rule（用户采纳）/ 自动晋升（见 § 4.3）|
| **Reflection** 反思记忆 | S07 反思生成的**规则草稿**（待晋升）| 7 天 / 直到被采纳或晋升 | Postgres `agent_memory` (type=reflection) | 只给 S07 自己用（做重复性检测）| S07 每次反思 |

### 1.1 层级关系图

```
┌──────────────────────────────────────────────────────────────┐
│ Working Memory（会话级 / 短期）                              │
│ Chat 上下文 / S04 共创中的 draft / 临时计算结果              │
│ 寿命：单次会话，关闭 APP 即丢（Redis 兜底 30min）            │
└──────────────────────────────────────────────────────────────┘
                              │
                              │ 会话结束 / 关键决策产生
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ Episodic Memory（情景 / 中期）                               │
│ "2026-04-20 BULL regime, TRUMP 聪明钱跟单策略触发, +48%"     │
│ 寿命：14-30 天，按相关性评分检索                             │
└──────────────────────────────────────────────────────────────┘
                              │
                              │ 周 / 月反思（S07）提炼
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ Reflection Memory（反思草稿 / 待晋升）                       │
│ "用户周五决策胜率偏低，建议周五暂停"（提议 → 待确认）        │
│ 寿命：7 天或直到用户采纳 / 自动晋升                          │
└──────────────────────────────────────────────────────────────┘
                              │
                              │ 用户采纳 T11 或 自动晋升规则
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ Semantic Memory（语义规则 / 长期）                           │
│ "周五不交易 SOL 链" / "LP < $100K 不建仓"                    │
│ 寿命：30 天无匹配废弃；每次 L2/L3 thesis 注入 prompt         │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Working Memory（工作记忆）

### 2.1 Purpose

维护**当前会话**的上下文，让 Agent 在多轮对话中保持连贯。

### 2.2 存储内容

| 数据 | 示例 | TTL |
|------|------|-----|
| Chat 历史（user + assistant messages）| `[{role: "user", ...}, ...]` | 会话结束即失效（Redis 30min 兜底）|
| S04 共创中的 draft_strategy | `{name: "xxx", conditions: AND(...)}` | 同上 |
| S05 共创中的 draft_trade_strategy | - | 同上 |
| Current thesis draft（生成中） | - | 生成结束即并入 Episodic |
| Temporary calculations（T14/T15 输出缓存）| - | 单次 tool 调用 |

### 2.3 Schema（`conversation_states` 表，v1 新建）

```sql
CREATE TABLE conversation_states (
  conversation_id UUID PRIMARY KEY,
  device_id UUID NOT NULL,
  state_type TEXT NOT NULL,             -- 'chat' | 'strategy_co_creation' | 'trade_co_creation'
  messages JSONB,                        -- chat 历史（最近 20 条）
  draft_data JSONB,                      -- draft_strategy / draft_trade_strategy
  current_stage TEXT,                    -- 'clarifying' | 'refining' | 'confirming'
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 minutes'
);
CREATE INDEX idx_conversation_device_active ON conversation_states(device_id)
  WHERE expires_at > NOW();
```

### 2.4 读写规则

- **读**：每次 Chat / Skill 调用开始时，按 `conversation_id` 拉取完整 state
- **写**：每轮对话结束或 draft 更新时写入（upsert）
- **续期**：每次访问 `expires_at = now + 30min`
- **清理**：cron 每小时清理 `expires_at < now`

### 2.5 Eviction Policy

- 会话**结束时**（用户明确退出 / 30min 无活动）→ Redis 自动过期
- Chat messages 超 20 条 → 保留最近 15 条 + 滚动 summary（可选，v2）
- draft 超过 7 天未 save → 标记 `abandoned=true`，清理

### 2.6 隐私

- Working Memory **不跨 device** 共享（即使同 wallet）
- 用户卸载 APP → device_id 即弃用，Redis TTL 过期

---

## 3. Episodic Memory（情景记忆）⭐

### 3.1 Purpose

存储用户的**"发生了什么 - 做了什么 - 结果如何"** 三元组，供未来相似场景检索参考。

### 3.2 Schema

对应现有 `agent_memory` 表（type='episodic'）：

```sql
CREATE TABLE agent_memory (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID NOT NULL,
  wallet_address TEXT,                   -- 可选，绑定 wallet 后填
  type TEXT NOT NULL CHECK (type IN ('episodic', 'semantic', 'reflection')),
  category TEXT NOT NULL,                -- 'trade_outcome' | 'market_pattern' | 'risk_lesson' | 'user_preference'
  content TEXT NOT NULL,                 -- 自然语言描述
  structured_data JSONB,                 -- 结构化字段（见下）
  importance INTEGER DEFAULT 5,          -- 1-10
  -- 索引字段（支持启发式相关性评分）
  chain TEXT,
  token_type TEXT,                       -- 'meme' | 'bluechip' | 'stablecoin' | 'newpump' | ...
  trigger_source TEXT,                   -- 'hot' | 'smart_money' | 'pump' | 'kol' | 'user_manual'
  mcap_bucket TEXT,                      -- '<10k' | '10k-100k' | '100k-1m' | '1m-10m' | '10m+'
  regime TEXT,                           -- 'BULL' | 'SIDEWAYS' | 'CRISIS'
  -- 时间与生命周期
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_matched_at TIMESTAMPTZ,           -- 最近被 T04 检索命中的时间
  match_count INTEGER DEFAULT 0,         -- 命中次数
  expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 days'
);
CREATE INDEX idx_memory_device_type ON agent_memory(device_id, type) WHERE expires_at > NOW();
CREATE INDEX idx_memory_relevance ON agent_memory(device_id, chain, trigger_source, regime) WHERE expires_at > NOW();
```

### 3.3 Episodic 的 `structured_data` 示例

```json
// 类型 1: 交易闭仓经历
{
  "trade_id": "uuid",
  "strategy_id": "uuid",
  "token": { "chain": "solana", "address": "...", "symbol": "TRUMP" },
  "entry_price_usd": 1.15,
  "exit_price_usd": 1.72,
  "pnl_pct": 49.6,
  "exit_reason": "take_profit",
  "duration_hours": 18,
  "thesis_id_at_entry": "uuid",
  "lessons_from_llm": "在 BULL regime 下聪明钱跟单策略表现好，应减少过早止盈"
}

// 类型 2: 市场模式
{
  "pattern_type": "bc_early_rug",
  "observed_count": 3,
  "description": "pump.fun BC < 5% 时 KOL 喊单代币，3 次中 2 次归零"
}

// 类型 3: 用户偏好
{
  "preference_type": "risk_aversion",
  "observations": ["拒绝过 5 次 auto 授权申请", "更偏好 notify_only"],
  "inferred_persona_hint": "conservative_intermediate"
}
```

### 3.4 写入时机（Write Patterns）

| 事件 | 写入内容 | category | importance |
|------|---------|---------|-----------|
| 交易闭仓（paper / auto）| trade outcome + 当时 thesis 引用 | `trade_outcome` | `min(pnl_pct / 10 + 5, 10)` |
| 用户主动拒绝 thesis | 当时 thesis + 拒绝原因 | `user_preference` | 5 |
| 策略连续亏 3 笔（触发熔断）| 策略 snapshot + 亏损模式 | `risk_lesson` | 8 |
| Thesis 生成 + 采纳（用户点"有用"）| thesis + 市场状态 | `market_pattern` | 6 |
| 异常事件（rug / 蜜罐命中）| 事件 + 被保护的决策 | `risk_lesson` | 9 |
| 用户手动退出仓位（覆盖止损）| 仓位 + 退出原因 | `user_preference` | 6 |

**不写入**：
- ❌ 普通查询行情（避免噪音）
- ❌ 未闭仓的中间状态
- ❌ Agent 自己产生的内部日志

### 3.5 检索算法（T04 recall_memory 启发式评分）

v1 使用**规则化评分**（不用 embedding，简单可解释）：

```python
def relevance_score(memory, situation):
    score = 0
    # 精确匹配加分（关键维度）
    if memory.trigger_source == situation.trigger_source: score += 3
    if memory.chain == situation.chain:                    score += 2
    if memory.regime == situation.regime:                  score += 2
    if memory.token_type == situation.token_type:          score += 2
    if memory.mcap_bucket == situation.mcap_bucket:        score += 1
    # 重要性和新鲜度加成
    score += memory.importance / 10                        # 0-1 贡献
    score += freshness_bonus(memory.created_at)            # 最近 7d +1 / 7-14d +0.5 / >14d +0
    # 返回 Top K
    return score

def freshness_bonus(ts):
    age_days = (now - ts).days
    if age_days < 7: return 1.0
    if age_days < 14: return 0.5
    return 0
```

**v2 考虑**：
- 若启发式召回率 < 60% → 升级到 embedding（Voyage AI / OpenAI 小模型，~$0.0001/次）
- 混合（starting with heuristic, embedding only on tie-break）

### 3.6 索引策略

- 主索引：`(device_id, type, expires_at)`
- 相关性索引：`(device_id, chain, trigger_source, regime)`
- 未来 embedding：`embedding VECTOR(768)` + pgvector 扩展

### 3.7 Eviction（淘汰）

| 规则 | 行为 |
|------|------|
| `expires_at < now` | 每日 cron 清理（保留 match_count > 5 的 14 天）|
| 同 device `type=episodic` > 500 条 | 保留最高 importance 的 400 条 + 最近 100 条 |
| wallet 绑定转移 | 保留（见 § 6 跨设备）|

---

## 4. Semantic Memory（语义记忆 / 活跃规则）⭐ 产品价值核心

### 4.1 Purpose

用户**采纳**或 **自动晋升** 的**通用规则**，每次 L2/L3 thesis 生成时注入 prompt。

这是 **"Agent 变成懂我的专家"** 的唯一落地机制。

### 4.2 Schema（同 `agent_memory`，type='semantic'）

```json
{
  "id": "uuid",
  "device_id": "...",
  "type": "semantic",
  "category": "trading_rule | filter | preference | market_wisdom",
  "content": "周五不交易 SOL 链",
  "structured_data": {
    "rule_type": "temporal_filter",
    "condition": { "weekday": 5, "chain": "solana" },
    "action": "skip_signal",
    "source": "user_approved | auto_promoted",
    "evidence": {
      "sample_size": 12,
      "win_rate_delta_vs_other_days": -0.28,
      "from_reflection_id": "uuid"
    }
  },
  "importance": 8,
  "last_matched_at": "...",
  "match_count": 23,
  "expires_at": "..."
}
```

### 4.3 规则晋升机制（Reflection → Semantic）

两条晋升路径：

| 路径 | 条件 | 触发者 |
|------|------|-------|
| **A. 手动晋升** | 用户点"采纳"（T11 approve_rule）| 用户 |
| **B. 自动晋升** | 连续 **3 次反思提出同条规则** **AND** ≥ **5 笔样本** **AND** 胜率领先 **≥ 15pp** | S07 review-engine |

自动晋升的安全网：
- ❌ 自动晋升后首次匹配必须走 **Shadow Mode**（只记录不生效）7 天
- ❌ Shadow 期间若实际表现差于预期 → 降级回 Reflection
- ✅ Shadow 通过 7 天 → 正式激活，用户可事后撤销

### 4.4 活跃规则上限

- 单 device `type=semantic` 硬限 **50 条活跃**
- 满时：新规则要替换旧规则，按 `importance × recency × match_count` 加权排序，最低的被挤出（移到 `archived_rules` 表保留 90 天）

### 4.5 冲突解决

| 冲突类型 | 解决规则 |
|---------|---------|
| 两条规则条件互斥（e.g. "周五不交易" vs "周五必买 SOL"）| 保留 `importance` 更高的；若相同，保留 `match_count` 更高的 |
| 新晋升规则与旧规则重叠 > 80% | 合并（保留新版的 evidence）|
| 用户手动规则 vs 自动晋升规则 | **用户规则永远胜出**（即使自动晋升数据更漂亮）|

### 4.6 注入 prompt 的策略

- **Thesis Loop L2/L3** 开头，把 `importance ≥ 6` 且命中当前 situation 的 Top 10 规则注入 system prompt
- 每条规则前加标识 `[user_rule]` 或 `[auto_rule]`，供 LLM 区分可信度
- 单次注入 token 预算 ≤ 2K

### 4.7 Decay / 废弃

- 规则**最近 30 天未被匹配** → 标记 `dormant`，再 30 天 → 废弃（移到 archive）
- 规则**命中 5 次但未产生明显收益差** → S07 反思时主动提议废弃（需用户确认）

---

## 5. Reflection Memory（反思草稿）

### 5.1 Purpose

S07 review-engine 每次生成的 **rule_proposals[]** 暂存于此，等待晋升。

### 5.2 Schema（同 `agent_memory`，type='reflection'）

```json
{
  "id": "uuid",
  "device_id": "...",
  "type": "reflection",
  "category": "proposed_rule",
  "content": "周五决策胜率偏低，建议周五暂停 SOL 链交易",
  "structured_data": {
    "proposal_id": "uuid",
    "generated_by_review_id": "uuid",
    "evidence_trade_ids": ["...", "..."],
    "sample_size": 12,
    "win_rate_delta": -0.28,
    "propose_count_so_far": 2,
    "user_rejected_count": 0
  },
  "importance": 7,
  "expires_at": "..."  // 默认 7 天
}
```

### 5.3 Reflection 的生命周期

```
S07 生成 proposal
     ↓
type='reflection' 写入（TTL 7 天）
     ↓
三条分支：
  ├── 用户采纳（T11） → 升级为 type='semantic' + TTL 续 30 天
  ├── 用户拒绝 ≥ 3 次 同类 → 丢弃 + 7 天 mute 该类规则
  └── 未被用户操作 7 天 + 连续 3 次反思重复提出 + § 4.3 条件满足
       → 自动晋升（Shadow Mode）→ 7 天通过 → 正式 semantic
```

### 5.4 反思节奏（触发时机）

| 触发 | 频率 | 范围 |
|------|------|------|
| 日复盘 | 每日 UTC 23:55 | 当日交易 |
| 周复盘 | 每周日 23:55 | 近 7 天 |
| 月复盘 | 每月 1 日 00:00 | 近 30 天 |
| 累计 10 笔闭仓 | 实时 | 近 10 笔 |
| 紧急（单笔 PnL < -25%）| 实时 | 该笔 + 相关历史 |

### 5.5 重复检测

S07 每次生成新 proposal 前，查询已有 reflection：
- 如果存在 `structured_data.condition` 相似（JSON diff < 20%）的 proposal → `propose_count_so_far += 1`
- 达到 3 次 + § 4.3 其他条件 → 启动自动晋升

---

## 6. 跨设备 / 跨 Wallet 同步

### 6.1 Identity 与 Memory 归属（对齐 [03 PRD § 0.6](./03-prd.md#06-identity-model身份模型--无注册账户)）

| 场景 | Memory 归属 |
|------|------------|
| device 未绑定 wallet | Memory 属 `device_id`（本机唯一）|
| device 绑定 wallet A | Memory 属 **wallet A + device_id**（双主键索引）|
| 新 device（同 wallet A）| 可拉取 wallet A 下的 Memory（**非强制**，用户可选）|
| wallet A 解绑 | 原 Memory 保留在 device_id 下，**不同步给新 wallet** |
| wallet A → wallet B 切换 | 原 Memory 不迁移（策略、仓位均归 wallet A）|

### 6.2 同步流程（可选，用户主动）

```
新 device 首启
  → connect wallet A + 签名
  → APP 询问 "检测到你在其他设备有 X 条策略记忆，要同步吗？"
  → 用户同意
  → 后台拉取 wallet A 下的 Semantic Memory（不拉 Episodic，保护隐私）
  → 写入新 device
```

**只同步 Semantic**（用户的规则库），**不同步 Episodic**（历史具体交易）—— Episodic 属于当时的 device 记忆，保持独立。

### 6.3 Wallet 切换时的数据隔离

- wallet A 绑定下生成的 Semantic Memory ≠ wallet B 的 Semantic Memory
- 同一 device 换 wallet → Memory **不跨 wallet 混合**
- 保护用户"不同 wallet 做不同策略"的隐私诉求

---

## 7. 跨层读写矩阵

| Skill / Tool | Working | Episodic | Semantic | Reflection |
|-------------|---------|----------|----------|------------|
| **Chat 入口** | R/W | - | - | - |
| **S01 technical-analysis** | R | - | - | - |
| **S02 sentiment-analysis** | R | - | - | - |
| **S03 onchain-analysis** | R | - | - | - |
| **S04 signal-strategy-builder** | **R/W** | R (via T04) | R (prompt 注入) | - |
| **S05 trade-strategy-builder** | R/W | R | R | - |
| **S07 review-engine** | - | **R/W** (写新 episode) | R | **W** (写 proposal) |
| **S08 thesis-writer** | R | R (via T04) | R (prompt 注入) | - |
| **T04 recall_memory** | - | **R** | **R** | - |
| **T11 approve_rule** | - | - | **W** (从 reflection → semantic) | R |
| **真金闭仓 hook** | - | **W** | - | - |
| **Shadow Mode 验证** | - | R | **R/W** (降级) | R/W |

---

## 8. 隐私与合规

### 8.1 用户对 Memory 的控制权

| 操作 | UI 入口 | 生效 |
|------|---------|------|
| **查看** 所有 Semantic 规则 | Profile → 我的规则 | 实时 |
| **编辑** 规则文本（不改 evidence）| 同上 → 编辑 | 实时 |
| **禁用** 某条规则 | 同上 → 关闭开关 | 实时（标 `disabled=true`，不删）|
| **删除** 单条 Memory | 同上 → 删除 | 立即软删（7d 冷却期）|
| **清空全部 Memory** | Profile → 隐私 → 重置记忆 | 7d 冷却期，期间可撤销 |
| **导出 Memory**（Wallet signed）| Profile → 导出数据 | JSON 格式，含全部层 |

### 8.2 与其他 device / wallet 的隔离

- 严禁**任何** Memory 跨 device_id 泄漏（除 § 6 用户主动同步）
- Memory **不出现在** 其他用户的 thesis 里（即使匿名化）
- v1 不做"跨用户学习"（v2 考虑差分隐私聚合）

### 8.3 审计与合规

- 所有 Memory 写入 **audit log**（180d 保留）
- 用户数据删除请求 SLA：**7d 冷却 + 30d 内彻底清除**（GDPR-like）
- 监管调取：仅 wallet_address + 非 PII 统计数据

### 8.4 LLM 调用时的脱敏

- 注入 Semantic 到 prompt 时，**不带** device_id / wallet_address
- recall_memory 的 output 不含原始 PII
- 长 content 截断（> 200 字的 Memory 先用 hash 表示）

---

## 9. 性能与扩展

### 9.1 存储估算（100 DAU v1）

| Layer | 单 device 条数上限 | 单条大小 | 100 DAU 总量 |
|-------|------------------|---------|-------------|
| Working | 10 个活跃 conversation | 5 KB | ~5 MB |
| Episodic | 500 | 1 KB | ~50 MB |
| Semantic | 50 | 0.5 KB | ~2.5 MB |
| Reflection | 20 | 0.5 KB | ~1 MB |

总计 < 100 MB，完全可承受。1K DAU ≈ 1 GB 仍远低于 Postgres 单表合理上限。

### 9.2 检索 Latency 目标

| 操作 | P95 目标 |
|------|---------|
| T04 recall_memory（启发式 Top 3）| < 200 ms |
| Semantic 规则注入到 prompt | < 50 ms |
| Reflection 重复检测 | < 300 ms |

### 9.3 缓存策略

- **Semantic（活跃规则）**：进程内 LRU 缓存 5min TTL，命中率目标 > 90%
- **Episodic**：不缓存（每次新查询）
- **Working**：Redis 为主，进程内 tier-1 缓存 1min

### 9.4 多实例共享

- Postgres 为 single source of truth
- 进程间**无需**同步 Working Memory（每个 session 绑定单实例）
- v2 若分片：按 `device_id` hash 分 shard，单 device 不跨 shard

---

## 10. Eval（记忆系统的质量测试）

### 10.1 Eval 维度

| 维度 | 测什么 | 方法 | 通过门槛 |
|------|-------|------|---------|
| **召回准确性** | T04 返回的相关案例真的相关吗？ | 100 条 situation 人工标注 ground truth → 计算 Top 3 precision | P@3 ≥ 0.7 |
| **召回覆盖率** | 应该被 recall 的历史案例是否被找到？ | 同上 → Top 3 recall | R@3 ≥ 0.6 |
| **规则有用性** | 采纳的 Semantic 规则真的改善决策吗？ | 采纳后 30 天 vs 前 30 天策略胜率对比 | 胜率提升 ≥ +3pp |
| **冲突检测** | 规则冲突时是否正确解决？ | 50 条人造冲突对 | 100% 正确 |
| **隐私隔离** | Memory 是否跨 device 泄漏？ | 渗透测试 | 0 次泄漏 |
| **晋升准确性** | 自动晋升的规则真的比 Reflection 阶段表现好？ | Shadow Mode 数据 | 晋升后 30d 表现 ≥ Shadow 期预期 |

### 10.2 Golden Set

- T04 recall_memory：100 条 (situation → expected memories) 对
- 规则冲突：50 条
- 晋升决策：30 条历史 proposal → 人工判断应否晋升

详见 [09 Eval Plan](./09-eval-plan.md)。

---

## 11. 现状 vs 本 Spec 的 Gap

基于 [04 Agent Spec § 13](./04-agent-spec.md#13-现状-vs-本-spec-的-gap) 的 G4 Memory gap：

| Gap | 现状 | v1 目标 |
|-----|------|---------|
| G1 Memory 只在进程内内存 | `memory/semantic_memory.py` 用 5min 进程缓存 + DB | 改为 Redis + DB，重启不丢 |
| G2 T04 recall_memory 不存在 | 直接读 DB + 手写 relevance 评分 | 封装为 Tool，统一 API |
| G3 自动晋升机制未完整 | 代码里有骨架，缺 Shadow Mode 安全网 | 实现 § 4.3 B 路径 + 7d Shadow |
| G4 用户规则控制 UI 缺 | 无 | § 8.1 6 项 UI 入口 |
| G5 跨设备同步未做 | device 绑死 | § 6 可选同步 |
| G6 Reflection 重复检测 | 无 | § 5.5 实现 |
| G7 Eval 套件未建 | 0 | § 10.2 Golden Set 搭建 |
| G8 Semantic 上限未强制 | 代码注释 50 条但无硬限 | 硬限 + 替换逻辑 |
| G9 审计 log 未完整 | 部分 | 全量写入 180d 保留 |

---

## 12. 术语对照表

| 本文档 | 等价概念 | 备注 |
|-------|---------|------|
| Working Memory | Conversation State / Session State | 会话级 |
| Episodic Memory | Episode / Experience | 情景级（具体事件）|
| Semantic Memory | Rule / Wisdom | 规则级（抽象规则）|
| Reflection Memory | Proposal / Hypothesis | 待验证的草稿规则 |
| Relevance Score | Similarity | 相关性评分 |
| Promotion | Graduation | 规则晋升 |
| Shadow Mode | Dry-run / Silent Mode | 只记录不生效 |
| Decay | Forgetting / TTL | 衰减遗忘 |

---

## Change Log

- **v0.1 (2026-04-24)**：首版完整填充
  - § 0 为什么要记忆 + 映射到 Vision / PRD
  - § 1 4 层记忆总览（Working / Episodic / Semantic / Reflection）+ 层级关系图
  - § 2 Working：schema (conversation_states 表) + 读写规则 + eviction
  - § 3 Episodic：schema (agent_memory) + structured_data 3 类示例 + 写入时机表 + **启发式相关性评分**（v1 不用 embedding）+ 索引
  - § 4 Semantic ⭐：晋升机制（手动 T11 + 自动 3 次 + Shadow Mode）+ 冲突解决 + prompt 注入
  - § 5 Reflection：生命周期（用户采纳 / 拒绝 / 自动晋升）+ 重复检测
  - § 6 跨 device / wallet 同步：只同步 Semantic 不同步 Episodic + wallet 切换隔离
  - § 7 跨层读写矩阵（Skill/Tool × Layer）
  - § 8 隐私与合规：用户 6 项控制权 + 跨用户隔离 + LLM 脱敏
  - § 9 性能（100 MB @ 100 DAU）+ 缓存策略
  - § 10 Eval：召回准确性 / 覆盖率 / 规则有用性 / 隐私隔离
  - § 11 现状 vs Spec 的 9 条 Gap
  - § 12 术语对照
- v0（2026-04-22）：初始骨架
