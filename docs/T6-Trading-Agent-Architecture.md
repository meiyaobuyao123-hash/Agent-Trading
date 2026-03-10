# Trading Agent 系统架构设计文档

## 一、系统概述

让用户通过自然语言描述交易策略，系统自动转化为可执行的监控规则，持续匹配实时数据流，触发告警或自动交易。

### 设计原则
- **LLM 负责理解，规则引擎负责执行**：LLM 仅在策略创建时调用
- **事件驱动**：数据变更 → 条件匹配 → 动作触发
- **复用现有架构**：扩展 pump-scanner，不新建服务
- **渐进式交付**：告警 → 监控 → 执行

---

## 二、架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Trading System                      │
│                                                              │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────────┐     │
│  │ Flutter  │──▶│ Agent API    │◀──│ Portal (Web)     │     │
│  │ 对话/策略 │◀──│ (FastAPI)    │──▶│ 策略管理仪表盘    │     │
│  └────┬─────┘   └──────┬───────┘   └──────────────────┘     │
│       │                │                                     │
│  ┌────▼────────────────▼──────────────────────────────┐     │
│  │              Agent Core (Python)                    │     │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────────────┐   │     │
│  │  │LLM Parser│ │Rule Engine│ │Action Dispatcher │   │     │
│  │  │(Claude)  │ │(条件评估)  │ │(告警/执行)       │   │     │
│  │  │NL→JSON   │ │条件树匹配  │ │Push/Webhook     │   │     │
│  │  └────┬─────┘ └─────┬─────┘ │OKX DEX 执行     │   │     │
│  │       │             │       └────────┬─────────┘   │     │
│  │  ┌────▼─────────────▼────────────────▼──────────┐  │     │
│  │  │           Event Bus (asyncio.Queue)           │  │     │
│  │  └──────────────────┬───────────────────────────┘  │     │
│  └─────────────────────┼──────────────────────────────┘     │
│                        │                                     │
│  ┌─────────────────────▼──────────────────────────────┐     │
│  │              Data Layer                             │     │
│  │  pump-scanner │ Hot Coin Scanner │ User Data Sources│     │
│  │       ↓              ↓                 ↓            │     │
│  │              Supabase (PostgreSQL)                   │     │
│  └─────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、核心组件

### 3.1 LLM Parser — 策略解析器

使用 Claude API (claude-sonnet-4-20250514) + Tool Use 将自然语言转为结构化 JSON。

**StrategySpec JSON Schema:**
```json
{
  "name": "3KOL聪明钱联动策略",
  "conditions": {
    "operator": "AND",
    "rules": [
      {
        "data_source": "kol_mentions",
        "field": "mention_count_2h",
        "operator": ">=",
        "value": 3
      },
      {
        "data_source": "pump_tokens",
        "field": "bc_progress",
        "operator": ">",
        "value": 50
      }
    ]
  },
  "actions": [
    {
      "type": "alert",
      "channels": ["push", "app"],
      "message_template": "{{token_name}} 被 {{mention_count}} 个KOL提及"
    }
  ],
  "filters": {
    "chains": ["solana"],
    "min_score": 60
  },
  "cooldown_minutes": 30
}
```

### 可用数据源字段

| data_source | 字段 | 类型 | 说明 |
|-------------|------|------|-----|
| pump_tokens | bc_progress | float | BC 进度 0-100% |
| pump_tokens | score | float | 内盘评分 0-100 |
| pump_tokens | smart_money_count | int | 聪明钱钱包数 |
| hot_coins | score | float | 外盘评分 0-100 |
| hot_coins | price_change_1h | float | 1h 涨幅 % |
| hot_coins | holder_count | int | 持有者数 |
| hot_coins | market_cap_usd | float | 市值 |
| hot_coins | chain | string | 链名 |
| kol_mentions | mention_count_2h | int | 2h内KOL提及次数 |
| custom | (用户定义) | any | 自定义数据源 |

### 3.2 Rule Engine — 规则引擎

纯逻辑运算，CPU 耗时 <1ms。每次数据更新时：
1. 按 data_source 过滤相关策略
2. 递归评估条件树 (AND/OR)
3. 检查 cooldown
4. 触发 → 发射事件

### 3.3 Event Bus — 事件总线

Phase 1-2: asyncio.Queue（零运维）
Phase 3: Redis Pub/Sub（支持交易隔离）

事件类型：
- `data.pump_snapshot` — 内盘快照更新
- `data.hot_coin_update` — 热币扫描更新
- `data.custom_source` — 自定义数据更新
- `strategy.triggered` — 策略触发
- `alert.created` — 告警生成

### 3.4 Action Dispatcher — 动作分发

| 动作 | Phase | 实现 |
|------|-------|------|
| App 通知 | 1 | 写 agent_alerts → Flutter 轮询 |
| Push 推送 | 1 | FCM/APNs |
| Webhook | 2 | HTTP POST |
| OKX DEX | 3 | OKX DEX v6 API |

---

## 四、数据库 Schema

### agent_strategies — 策略主表
```sql
CREATE TABLE agent_strategies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    conditions      JSONB NOT NULL,        -- 条件树
    actions         JSONB NOT NULL DEFAULT '[]',
    filters         JSONB NOT NULL DEFAULT '{}',
    data_sources    TEXT[] NOT NULL DEFAULT '{}',
    cooldown_min    INT NOT NULL DEFAULT 30,
    status          TEXT NOT NULL DEFAULT 'active',
    trigger_count   INT NOT NULL DEFAULT 0,
    last_triggered  TIMESTAMPTZ,
    source_prompt   TEXT,                  -- 用户原始输入
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

### agent_alerts — 告警记录
```sql
CREATE TABLE agent_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    strategy_id     UUID REFERENCES agent_strategies(id),
    trigger_context JSONB NOT NULL,
    token_address   TEXT,
    token_name      TEXT,
    chain           TEXT,
    title           TEXT NOT NULL,
    message         TEXT NOT NULL,
    severity        TEXT DEFAULT 'info',
    is_read         BOOLEAN DEFAULT FALSE,
    is_pushed       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### agent_executions — 交易执行（Phase 3）
```sql
CREATE TABLE agent_executions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    strategy_id     UUID REFERENCES agent_strategies(id),
    chain           TEXT NOT NULL,
    token_address   TEXT NOT NULL,
    action          TEXT NOT NULL,  -- 'buy'|'sell'
    amount_usd      NUMERIC,
    status          TEXT DEFAULT 'pending',
    tx_hash         TEXT,
    executed_price  NUMERIC,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### user_data_sources — 自定义数据源
```sql
CREATE TABLE user_data_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    name            TEXT NOT NULL,
    source_type     TEXT NOT NULL,  -- 'builtin'|'polling'|'webhook'
    endpoint_url    TEXT,
    poll_interval_s INT DEFAULT 300,
    webhook_path    TEXT UNIQUE,
    webhook_secret  TEXT,
    field_mapping   JSONB DEFAULT '{}',
    fields          JSONB DEFAULT '[]',
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

---

## 五、技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 后端 | 扩展 pump-scanner (Python) | 共享数据层，零通信开销 |
| API 层 | FastAPI（嵌入进程） | 与 APScheduler 共存 |
| LLM | Claude Sonnet via Tool Use | 结构化输出可靠，$0.02/次 |
| 实时推送 | Phase 1: Supabase Realtime → Phase 2: FastAPI WS | 渐进复杂度 |
| 事件总线 | asyncio.Queue → Redis | Phase 3 时迁移 |

---

## 六、文件结构

```
services/pump-scanner/
├── agent/                       # 新增子包
│   ├── __init__.py
│   ├── llm_parser.py            # Claude API 策略解析
│   ├── rule_engine.py           # 规则引擎
│   ├── evaluator.py             # 条件评估器
│   ├── event_bus.py             # 事件总线
│   ├── action_dispatcher.py     # 动作分发
│   ├── strategy_manager.py      # 策略 CRUD
│   ├── datasource_poller.py     # 数据源轮询
│   ├── webhook_handler.py       # Webhook 接收
│   ├── trade_executor.py        # OKX DEX 执行（Phase 3）
│   ├── monitor_job.py           # APScheduler 任务
│   └── schemas.py               # Pydantic 模型
├── api/                         # 新增 HTTP 层
│   ├── app.py                   # FastAPI 实例
│   ├── routes_agent.py          # /api/agent/* 路由
│   ├── routes_webhook.py        # /webhook/* 路由
│   ├── ws_handler.py            # WebSocket
│   └── auth.py                  # JWT 验证
```

```
apps/app/lib/
├── screens/agent/
│   ├── chat_tab.dart            # 对话创建策略
│   ├── strategies_tab.dart      # 策略管理
│   └── datasources_tab.dart     # 数据源配置
├── models/
│   ├── agent_strategy.dart
│   ├── agent_alert.dart
│   └── data_source.dart
├── services/
│   ├── agent_api_service.dart
│   └── alert_service.dart
```

---

## 七、API 设计

| 端点 | 方法 | 说明 |
|------|------|------|
| /api/agent/chat | POST | 对话（调 Claude 创建策略） |
| /api/agent/strategies | GET | 策略列表 |
| /api/agent/strategies | POST | 创建策略 |
| /api/agent/strategies/:id | PATCH | 更新策略 |
| /api/agent/alerts | GET | 告警列表 |
| /api/agent/alerts/:id/read | PATCH | 标记已读 |
| /api/agent/datasources | POST | 添加数据源 |
| /webhook/:path | POST | 接收外部 Webhook |
| /ws/alerts/:user_id | WS | 实时告警推送 |

---

## 八、安全与风控

| 风控项 | 限制 |
|--------|------|
| 单用户策略上限 | 20 个 |
| 单策略每日触发 | 50 次 |
| 冷却时间下限 | 5 分钟 |
| 自定义数据源 | 5 个/用户 |
| 单次交易上限 | 1 SOL / $200 |
| 每日交易总额 | 10 SOL / $2000 |

---

## 九、实施阶段

### Phase 1: 策略创建 + 告警（2 周）
- Migration + Event Bus + LLM Parser + Rule Engine
- FastAPI 层 + JWT 认证
- Flutter: 对话 + 策略列表 + 告警

### Phase 2: 监控 + 数据源（2 周）
- 自定义数据源（Polling / Webhook）
- WebSocket 实时推送
- Push 通知（FCM/APNs）
- Portal 策略仪表盘

### Phase 3: 交易执行（3 周）
- OKX DEX v6 SDK 封装
- 风控模块
- 钱包连接（WalletConnect）
- 历史回测

---

## 十、成本估算

| 项目 | 月费用 |
|------|--------|
| Claude API (Sonnet) | ~$30-80 (100用户) |
| Supabase Pro | $25 (已有) |
| 服务器 | $0 增量 |
| **合计** | **~$55-105/月** |

扩展拐点：500 用户时需 Redis + 多 Worker（~$200/月）
