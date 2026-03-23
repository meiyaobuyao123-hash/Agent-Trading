# PRD-007: 多角色 Agent 架构升级

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-03-23 |
| 所属模块 | Phase 3（交易 Agent M5/M6/M7 + 优化 Agent O6） |
| 优先级 | P0 |
| 状态 | 待审批 |

---

## 一、调研背景

### 1.1 行业研究数据

| 论文/产品 | 核心发现 | 数据支撑 |
|-----------|---------|---------|
| **TradingAgents**（ICML 2025） | 7 角色多 Agent 框架，夏普率 5.60 | AAPL 3 月 +26%，超越 Buy&Hold 14% |
| **TradingGroup**（arXiv 2025/08） | 自反思+数据合成多 Agent | FINSABER 回测超越所有 LLM 基线 |
| **Moon Dev** | 48+ 专业 Agent 协作交易 | Hyperliquid + Solana + Asterdex |
| **单 Agent 对照** | LLM 单 Agent 交易 | 夏普率 ~1.5，仅 TradingAgents 的 27% |

### 1.2 关键结论

**1. 多角色 vs 单 Agent 性能差距**
```
TradingAgents 夏普率 5.60 vs 买入持有 ~1.5 → 3.7 倍提升
TradingAgents 3 月收益 +26% vs 单 Agent ~+12% → 2.2 倍
关键原因：牛熊辩论减少单一偏见，风控独立审查防止冲动交易
```

**2. 最优辩论轮数**
```
TradingAgents 推荐：3-5 轮
< 3 轮：辩论不充分，论点未展开
> 5 轮：成本上升但质量提升边际递减
我们选择：3 轮（成本敏感，MEME 市场决策不需要太深辩论）
```

**3. 风控 Agent 必须有"否决权"**
```
TradingAgents: "Risk Manager became the linchpin, vetoing trades that exceeded
               acceptable risk levels, even if other agents signaled green"
关键：风控不是建议，是独立审查+强制否决
```

**4. 模型选择策略**
```
TradingAgents 区分 quick-thinking vs deep-thinking：
  分析师（数据检索）→ 快速模型（Haiku/Sonnet）
  辩论+决策 → 深度模型（Sonnet/Opus）
  风控审查 → 快速模型（Sonnet，速度>深度）
我们选择：
  分析师 → Haiku（$0.25/1M tokens，并行 3 个仍便宜）
  辩论+决策 → Sonnet（$3/1M，质量好够用）
  风控 → 规则引擎 + Sonnet 审查（混合方案）
```

**5. 成本控制**
```
并行 3 个 Haiku 分析师 ≈ 1 个 Sonnet 的 25% 成本
辩论 3 轮 × Sonnet ≈ $0.009/次
总成本每次策略触发：~$0.015
每天 50 次触发：$0.75/天 ≈ $22.5/月
vs 当前单 Agent 每次 $0.003 → 贵 5 倍，但性能提升 2-3 倍
```

### 1.3 技术路线选择

| 方案 | 角色数 | 辩论轮数 | 月成本 | 选择 |
|------|--------|---------|--------|------|
| 照搬 TradingAgents（7 角色） | 7 | 3-5 | ~$60/月 | ❌ 太贵 |
| 精简版（3 分析+辩论+决策+风控） | 6 | 3 | ~$22/月 | ✅ |
| 最小版（1 分析+风控） | 2 | 0 | ~$8/月 | ❌ 无辩论，效果有限 |

---

## 二、架构设计

### 当前 vs 目标

```
当前（单 Agent）：
  用户输入 → Claude Sonnet → StrategySpec → 执行
  问题：单一视角，无辩论，无独立风控审查

目标（6 角色）：
  用户输入 → 策略解析 Agent (Sonnet)
                    ↓
  策略触发 → ┌─ 技术分析 Agent (Haiku)  ──┐
             ├─ 情绪分析 Agent (Haiku)  ──┤ 并行，~1s
             └─ 链上分析 Agent (Haiku)  ──┘
                    ↓ 3 份报告
             辩论 Agent (Sonnet)
             ├─ 看多视角 → 论点
             ├─ 看空视角 → 反驳
             └─ 3 轮对话 → 结论
                    ↓
             决策 Agent (Sonnet)
             └─ 综合辩论结论 + 记忆 → 买/卖/持有
                    ↓
             风控 Agent (规则+Sonnet)
             └─ 独立审查，可否决（veto power）
```

### 6 个角色定义

| 角色 | 模型 | 输入 | 输出 | 调用时机 |
|------|------|------|------|---------|
| **策略解析** | Sonnet | 用户自然语言 | StrategySpec JSON | 用户创建策略时 |
| **技术分析师** | Haiku | RSI/MACD/MA/ATR/支撑阻力 | 技术面报告（100字） | 策略触发时 |
| **情绪分析师** | Haiku | 恐慌指数/资金费率/多空比/新闻/聪明钱 | 情绪面报告（100字） | 策略触发时 |
| **链上分析师** | Haiku | 交易所流入/大额转账/持仓分布/活跃地址 | 链上报告（100字） | 策略触发时 |
| **辩论+决策** | Sonnet | 3 份报告 + 记忆上下文 | 买/卖/持有 + 理由 + 置信度 | 分析完成后 |
| **风控审查** | 规则引擎+Sonnet | 决策结果 + 持仓状态 + Regime | 通过/否决/调整 | 决策完成后 |

---

## 三、详细需求

### 3.1 M5 三个分析师（并行执行）

#### 技术分析师

```
System Prompt:
  "你是一个加密货币技术分析专家。基于以下技术指标数据，
   用 3-5 个要点总结当前技术面状况和交易方向。
   输出 JSON: {direction: 'bullish'|'bearish'|'neutral', confidence: 0-1, points: [...], key_level: ...}"

输入数据（从 indicator_engine / hot_coins / token_data 获取）：
  - RSI_14, MACD, MA7/25/99 关系
  - 布林带位置, ATR_14
  - 支撑/阻力位
  - 成交量变化趋势
  - 价格相对 MA 的位置

输出格式：
  {
    "direction": "bullish",
    "confidence": 0.72,
    "points": [
      "RSI=42 中性偏低，有反弹空间",
      "价格站上 MA25，MA7 金叉 MA25",
      "成交量 4h 放大 2.3 倍，突破确认"
    ],
    "key_level": {"support": 0.00015, "resistance": 0.00025}
  }
```

#### 情绪分析师

```
System Prompt:
  "你是一个加密市场情绪分析专家。基于以下情绪和资金数据，
   用 3-5 个要点总结当前市场情绪和聪明钱动向。"

输入数据：
  - 恐慌贪婪指数
  - 资金费率（Binance + OKX）
  - 大户多空比 / 散户多空比
  - 聪明钱买卖信号（smart_money_signals）
  - CryptoPanic 新闻情绪
  - LunarCrush 社交热度
  - KOL 提及（kol_signals）

输出格式：
  {
    "direction": "bullish",
    "confidence": 0.65,
    "points": [
      "恐慌指数=35（恐慌区），历史上此区域反弹概率 68%",
      "3 个 elite 聪明钱钱包在过去 2h 买入该代币",
      "资金费率-0.002%，空头拥挤，有轧空可能"
    ],
    "smart_money_signal": "strong_buy"
  }
```

#### 链上分析师

```
System Prompt:
  "你是一个区块链链上数据分析专家。基于以下链上数据，
   用 3-5 个要点总结链上活动和资金流向。"

输入数据：
  - 代币 holder 分布（Top10 集中度）
  - 代币交易量趋势
  - 代币流动性变化
  - 如果是热币：入榜以来涨幅/退出风险
  - 如果是 pump：BC 进度/买卖比

输出格式：
  {
    "direction": "neutral",
    "confidence": 0.55,
    "points": [
      "Top10 持仓 45%，中等集中度",
      "24h 新增 holder 120 个，增长趋势正常",
      "流动性 $85K，中等偏低，大单可能滑点较大"
    ],
    "risk_flag": "medium_liquidity"
  }
```

#### 并行执行设计

```python
async def run_analysis(token_data, market_data, memory_context):
    """3 个分析师并行执行"""
    technical, sentiment, onchain = await asyncio.gather(
        technical_analyst.analyze(token_data, market_data),
        sentiment_analyst.analyze(token_data, market_data),
        onchain_analyst.analyze(token_data),
        return_exceptions=True,
    )
    # 任何一个失败不影响其他（降级处理）
    reports = {
        "technical": technical if not isinstance(technical, Exception) else {"direction": "neutral", "confidence": 0.3},
        "sentiment": sentiment if not isinstance(sentiment, Exception) else {"direction": "neutral", "confidence": 0.3},
        "onchain": onchain if not isinstance(onchain, Exception) else {"direction": "neutral", "confidence": 0.3},
    }
    return reports
```

### 3.2 M6 牛熊辩论（3 轮）

```
辩论 Prompt 模板：

Round 1 — 看多视角：
  "基于以下 3 位分析师的报告，请从看多的角度论证为什么应该买入。
   技术面：{technical_report}
   情绪面：{sentiment_report}
   链上面：{onchain_report}
   历史记忆：{memory_context}
   用 3 个论点说明买入理由。"

Round 1 — 看空视角：
  "基于相同的分析报告，请从看空的角度反驳以上看多论点并说明风险。
   看多论点：{bull_arguments}
   用 3 个论点说明不应买入的理由。"

Round 2 — 看多回应：
  "看空提出了以下风险：{bear_arguments}
   请回应这些风险，并补充新的看多证据。"

Round 2 — 看空回应：
  "看多回应如下：{bull_response}
   请指出其论点的弱点，并补充看空证据。"

Round 3 — Facilitator 总结：
  "以下是看多和看空各 2 轮辩论的完整记录：
   {full_debate_log}

   请作为中立裁判总结：
   1. 哪方论点更有说服力？
   2. 综合胜率评估（0-1）
   3. 最大风险是什么？
   4. 建议动作（buy/sell/hold）及置信度

   输出 JSON: {winner, confidence, action, risk, reasoning}"
```

#### 辩论实现

```python
async def run_debate(reports, memory_context):
    """3 轮辩论 — 全部用 Sonnet"""

    # Round 1
    bull_r1 = await _call_claude(BULL_PROMPT_R1.format(...), model="sonnet")
    bear_r1 = await _call_claude(BEAR_PROMPT_R1.format(bull=bull_r1), model="sonnet")

    # Round 2
    bull_r2 = await _call_claude(BULL_PROMPT_R2.format(bear=bear_r1), model="sonnet")
    bear_r2 = await _call_claude(BEAR_PROMPT_R2.format(bull=bull_r2), model="sonnet")

    # Round 3 — Facilitator
    full_log = f"Bull R1: {bull_r1}\nBear R1: {bear_r1}\nBull R2: {bull_r2}\nBear R2: {bear_r2}"
    conclusion = await _call_claude(FACILITATOR_PROMPT.format(debate=full_log), model="sonnet")

    return {
        "debate_log": full_log,
        "conclusion": conclusion,  # {winner, confidence, action, risk, reasoning}
    }
```

### 3.3 M7 交易决策

```
决策 Agent 不独立调用 LLM，而是使用辩论的 Facilitator 结论。

决策逻辑：
  如果 conclusion.action == "buy" 且 confidence >= 0.6：
    → 提交买入请求到风控
  如果 conclusion.action == "sell" 且 confidence >= 0.5：
    → 提交卖出请求到风控
  如果 conclusion.action == "hold" 或 confidence < 0.5：
    → 不交易，记录到短期记忆

决策还需考虑：
  - 记忆系统的规则合规检查（Phase 1 M13）
  - 当前 Regime（Phase 2 M9）
  - 持仓状态（已有同代币持仓？）
```

### 3.4 风控 Agent（独立审查 + 否决权）

```
风控 Agent = 现有 risk_manager 15 项规则检查 + Sonnet AI 审查

流程：
  1. 规则引擎检查（15 项 + Regime 动态）→ 硬性 block/pass
  2. 如果规则引擎 pass → Sonnet AI 审查（可选，高额交易触发）

AI 审查触发条件：
  - 交易金额 > $50
  - 当前 Regime 为 HIGH_VOLATILITY 或 RECOVERY
  - 辩论 confidence < 0.7（低置信度决策需要额外审查）

AI 审查 Prompt：
  "你是独立风控审查官。以下交易即将执行：
   {trade_details}
   当前持仓：{portfolio}
   市场状态：{regime}
   辩论结论：{debate_conclusion}

   你只能回答：APPROVE（通过）/ REJECT（否决）/ REDUCE（减仓执行）
   如果 REJECT 或 REDUCE，说明理由。
   你的职责是保护资金安全，不受交易机会的诱惑。"
```

### 3.5 O6 记忆审计工具

```python
def tool_read_agent_memory(days: int = 14) -> dict:
    """优化 Agent 评估记忆系统效果"""
    return {
        "total_reflections": 15,
        "active_semantic_rules": 12,
        "rule_compliance_rate": 0.78,
        "compliance_win_rate": 0.72,
        "violation_win_rate": 0.31,
        "most_effective_rules": [...],
        "most_violated_rules": [...],
        "stale_rules_count": 3,  # 30天未使用
        "debate_stats": {
            "total_debates": 120,
            "bull_win_rate": 0.58,  # 看多赢的比例
            "avg_rounds": 3.0,
            "avg_confidence": 0.67,
            "debate_accuracy": 0.63,  # 辩论结论 vs 实际盈亏
        },
    }
```

---

## 四、何时启用多角色（不是所有触发都跑辩论）

```
成本控制：不是每次策略触发都启动 6 个角色

分级触发：
  Level 1 — 快速评估（所有触发）：
    → 规则引擎评估条件是否满足 → 不满足直接跳过
    → 成本：$0

  Level 2 — 单 Agent 评估（满足基本条件的）：
    → 策略条件满足 + score >= 阈值
    → 快速判断是否值得深入分析
    → 成本：~$0.003（Sonnet 一次调用）

  Level 3 — 多角色全流程（高价值交易）：
    → 交易金额 > $30
    → 或代币 score > 70
    → 或涉及新未知代币（记忆中无历史）
    → 3 分析师并行 + 3 轮辩论 + 风控审查
    → 成本：~$0.015

预估每天分布：
  Level 1: ~200 次 → $0
  Level 2: ~50 次 → $0.15
  Level 3: ~15 次 → $0.225
  总计：$0.375/天 ≈ $11.25/月（比之前估的 $22.5 少一半）
```

---

## 五、数据库设计

### 新增表：agent_debates

```sql
CREATE TABLE IF NOT EXISTS agent_debates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID,
    token_address TEXT,
    chain TEXT,
    trigger_source TEXT,

    -- 分析师报告
    technical_report JSONB,
    sentiment_report JSONB,
    onchain_report JSONB,

    -- 辩论记录
    debate_log TEXT,
    debate_rounds INT DEFAULT 3,

    -- 结论
    conclusion_action TEXT,     -- buy/sell/hold
    conclusion_confidence NUMERIC,
    conclusion_winner TEXT,     -- bull/bear
    conclusion_risk TEXT,
    conclusion_reasoning TEXT,

    -- 风控审查
    risk_review TEXT,           -- APPROVE/REJECT/REDUCE
    risk_review_reason TEXT,

    -- 最终结果
    final_action TEXT,          -- buy/sell/hold/blocked
    actual_pnl_pct NUMERIC,    -- 回填

    -- 评估
    debate_level INT,           -- 1/2/3
    total_tokens_used INT,
    total_cost_usd NUMERIC,

    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_debates_token ON agent_debates(token_address, created_at DESC);
```

---

## 六、技术影响

| 文件 | 操作 | 说明 |
|------|------|------|
| `agent/analysts/__init__.py` | **新建** | 分析师模块 |
| `agent/analysts/technical.py` | **新建** | 技术分析师（Haiku） |
| `agent/analysts/sentiment.py` | **新建** | 情绪分析师（Haiku） |
| `agent/analysts/onchain.py` | **新建** | 链上分析师（Haiku） |
| `agent/debate.py` | **新建** | 辩论引擎（3 轮 Sonnet） |
| `agent/decision_agent.py` | **新建** | 决策 Agent（结论→动作） |
| `agent/risk_reviewer.py` | **新建** | AI 风控审查（Sonnet，高额触发） |
| `agent/multi_role_orchestrator.py` | **新建** | 编排器（分级触发 + 并行协调） |
| `agent/event_listener.py` | 修改 | 策略触发后调用 orchestrator |
| `agent/monitor_job.py` | 修改 | 同上 |
| `optimizer_tools.py` | 修改 | +tool_read_agent_memory(含 debate_stats) |
| `api/routes_agent.py` | 修改 | +/api/agent/debates 端点 |
| `migrations/030_agent_debates.sql` | **新建** | debates 表 |

---

## 七、Claude API 成本

| 角色 | 模型 | 每次 tokens | 每次成本 | 日频次 | 月成本 |
|------|------|-----------|---------|--------|--------|
| 技术分析师 | Haiku | ~800 | $0.0002 | 15 | $0.09 |
| 情绪分析师 | Haiku | ~800 | $0.0002 | 15 | $0.09 |
| 链上分析师 | Haiku | ~800 | $0.0002 | 15 | $0.09 |
| 辩论 4 轮(2多+2空) | Sonnet | ~4000 | $0.012 | 15 | $5.40 |
| Facilitator | Sonnet | ~1500 | $0.0045 | 15 | $2.03 |
| 风控 AI 审查 | Sonnet | ~1000 | $0.003 | 5 | $0.45 |
| Level 2 快速评估 | Sonnet | ~500 | $0.0015 | 50 | $2.25 |
| **总新增** | | | | | **~$10.4/月** |

---

## 八、验收标准

### M5 分析师
- [ ] 3 个分析师并行执行，总耗时 < 2s
- [ ] 单个分析师失败不影响其他（降级为 neutral）
- [ ] 输出结构化 JSON（direction/confidence/points）
- [ ] 数据来源正确（技术=indicator，情绪=聪明钱+新闻，链上=holder+流动性）

### M6 辩论
- [ ] 3 轮辩论完整（Bull R1→Bear R1→Bull R2→Bear R2→Facilitator）
- [ ] Facilitator 输出结构化结论（action/confidence/risk/reasoning）
- [ ] 辩论记录写入 agent_debates 表
- [ ] confidence < 0.5 → 不执行交易

### M7 决策
- [ ] 结合辩论结论 + 记忆规则 + Regime → 最终动作
- [ ] 分级触发：Level 1/2/3 正确分流

### 风控 AI 审查
- [ ] 高额交易（>$50）触发 AI 审查
- [ ] REJECT → 交易不执行，记录原因
- [ ] REDUCE → 仓位减半执行
- [ ] 风控 Agent 有独立否决权（不受其他 Agent 影响）

### O6 记忆审计
- [ ] 优化 Agent 可读取辩论统计（多空胜率/准确率/平均置信度）
- [ ] 可评估记忆规则有效性

---

## 九、风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 辩论耗时过长导致错过行情 | 中 | 中 | Level 1/2 快速通道；辩论总超时 15s |
| Haiku 分析质量不够 | 中 | 中 | 数据充足时 Haiku 足够；fallback 到规则引擎 |
| 多轮 API 调用增加延迟 | 中 | 低 | 分析师并行；辩论串行但每轮 <3s |
| 辩论结论和实际涨跌不符 | 高 | 中 | 记录到 debates 表回填 PnL，优化 Agent 持续改进 |
| AI 风控被"说服"放行 | 低 | 高 | 规则引擎硬底线永不覆盖；AI 只做增量审查 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-23 | 初始版本 |
