# PRD-008: Agent 模拟盘 + 策略模板 + AI 主动推荐

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-03-23 |
| 所属模块 | Phase 4（交易 Agent M14/M2/M17） |
| 优先级 | P1 |
| 状态 | 待审批 |

---

## 一、调研背景

| 数据 | 来源 |
|------|------|
| Walbi beta 1000 用户创建 9500 个 agent，187K 笔模拟交易 | Walbi 2026/03 |
| 用户痛点 #2："先让我看看它行不行" | 47 系统实测报告 |
| 3Commas/Cryptohopper 策略市场是核心收入来源（$22-129/月） | Bitget 对比 2026 |
| 用户痛点 #5："我不懂技术也能用" | Reddit/Medium 汇总 |

---

## 二、三个模块

### M14 Agent 策略模拟盘

**问题**：当前 MEME/热币 Agent 策略无模拟盘，用户直接真金白银。BTC/ETH 有模拟盘但 Agent 没有。

**方案**：
```
每个策略默认 paper 模式运行 3 天：
  → 策略创建后 status="active", mode="paper"
  → 信号触发时用实时价格模拟交易（不调 OKX DEX）
  → 记录虚拟盈亏到 agent_paper_trades 表
  → 3 天后展示模拟表现：胜率/PNL/最大回撤
  → 用户确认后切换 mode="live"
  → 模拟盘继续运行作为对照组
```

**DB 新增**：
```sql
CREATE TABLE agent_paper_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL,
    user_id UUID,
    chain TEXT,
    token_address TEXT,
    token_symbol TEXT,
    action TEXT NOT NULL,        -- buy/sell
    entry_price NUMERIC NOT NULL,
    exit_price NUMERIC,
    amount_usd NUMERIC NOT NULL,
    pnl_usd NUMERIC,
    pnl_pct NUMERIC,
    trigger_context JSONB,
    status TEXT DEFAULT 'open',  -- open/closed
    created_at TIMESTAMPTZ DEFAULT now(),
    closed_at TIMESTAMPTZ
);
```

**API 新增**：
- `GET /api/agent/paper-trades?strategy_id=X` — 模拟交易记录
- `GET /api/agent/paper-stats?strategy_id=X` — 模拟盘统计
- `POST /api/agent/strategies/{id}/go-live` — 切换到实盘

### M2 策略模板

**问题**：用户必须自己用自然语言描述策略，新手不知道怎么描述。

**方案**：5 个预设模板

| 模板 | 触发条件 | 动作 | 风控 |
|------|---------|------|------|
| MEME 早期狙击 | pump score≥70 + BC 5-15% + 聪明钱≥2 | 买入 $50 | SL 25% TP 100% |
| 热币追涨 | hot score≥65 + 24h涨幅>30% + 量放大 | 买入 $80 | SL 20% TP 80% |
| 聪明钱跟单 | elite 钱包买入信号 + 流动性>$50K | 买入 $60 | SL 30% TP 150% |
| KOL 舆情 | 3+ KOL 提及 + 情绪正面 + score>50 | 买入 $40 | SL 20% TP 60% |
| 保守定投 | 每日 UTC 10:00 + BTC 恐慌指数<40 | 买入 $20 | SL 15% TP 50% |

**实现**：
```python
STRATEGY_TEMPLATES = {
    "meme_sniper": {
        "name": "MEME 早期狙击",
        "description": "在 pump.fun 代币早期阶段（BC 5-15%）发现聪明钱介入的高分代币",
        "conditions": {...},
        "actions": [{"type": "buy", "amount_usd": 50}],
        "filters": {"min_score": 70, "chains": ["solana"]},
        "risk_params": {"stop_loss_pct": 25, "take_profit_pct": 100},
    },
    # ... 其他 4 个
}
```

**API**：
- `GET /api/agent/templates` — 模板列表
- `POST /api/agent/templates/{id}/create` — 从模板创建策略

### M17 AI 主动推荐

**问题**：Agent 被动等用户输入，不主动发现机会。

**方案**：
```
每 4h Agent 主动扫描市场：
  1. 检查聪明钱信号：有无 elite 钱包集中买入
  2. 检查热币异动：有无 score 突然飙升的代币
  3. 检查 KOL 共振：有无多个 KOL 同时提及

  发现高价值机会 → 推送给用户：
    "发现 3 个聪明钱钱包买入 XXX（SOL），score=82。
     是否创建跟单策略？[一键创建] [忽略]"

触发条件（满足任一）：
  - elite 钱包 ≥ 2 个买入同一代币
  - hot coin score 从 <50 升至 >70（1h 内）
  - KOL ≥ 3 个提及同一代币（2h 内）

推送频率限制：
  - 每日最多 5 条主动推荐
  - 同一代币 24h 内不重复推荐
```

---

## 三、技术影响

| 文件 | 操作 |
|------|------|
| `agent/paper_engine.py` | **新建** — 模拟交易引擎 |
| `agent/templates.py` | **新建** — 策略模板定义 |
| `agent/proactive_scanner.py` | **新建** — AI 主动推荐扫描 |
| `agent/action_dispatcher.py` | 修改 — paper mode 分流 |
| `agent/strategy_manager.py` | 修改 — mode 字段支持 |
| `api/routes_agent.py` | 修改 — +6 个端点 |
| `main.py` | 修改 — 注册 proactive_scanner 定时任务 |
| `migrations/031_agent_paper_trades.sql` | **新建** |

---

## 四、成本

| 项目 | 月成本 |
|------|--------|
| 模拟盘（纯计算，无 API） | $0 |
| 策略模板（一次性代码） | $0 |
| AI 主动推荐（Haiku 6次/天） | ~$0.18 |
| **总新增** | **~$0.18/月** |

---

## 五、验收标准

- [ ] 策略创建后默认 paper 模式，3 天后可切 live
- [ ] 模拟盘用实时价格记录虚拟盈亏
- [ ] 5 个策略模板可一键创建
- [ ] AI 每 4h 扫描一次，每日最多 5 条推荐
- [ ] Flutter App 展示模拟盘 vs 实盘对比

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-23 | 初始版本 |
