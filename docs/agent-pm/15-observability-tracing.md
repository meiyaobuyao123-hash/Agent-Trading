# 15 Observability & Tracing Spec

> 每次决策的**完整 trace**：prompt / tool_call / tool_result / latency / cost / outcome。
> 没 trace 就没 Eval、没事故复盘、没成本归因。

| 字段 | 值 |
|------|---|
| Status | 🟢 v0.1 Draft |
| Version | v0.1 |
| Owner | 工程 |
| Target Release | v1 MVP - 2026 Q3 |
| Priority | P0（v1 必备 · 11 § T10）|

---

## 0. 文档导读

### 0.1 设计原则

1. **无 trace 无决策**：每个 LLM 调用 / Tool 调用必有 trace
2. **可回放**：trace 足以**重建**决策上下文（input + output + 依赖）
3. **低开销**：trace 采集 < 5% 原始请求时间
4. **可审计**：90 天内任何决策都能调出（180 天 audit log 含合规字段）
5. **统一**：Eval / Cost / Incident / Red Team 用同一套 trace 系统

### 0.2 和其他文档的关系

| 文档 | 关系 |
|------|-----|
| [09 Eval § 12.4](./09-eval-plan.md#124-与-observability-集成) | Eval run 写入同一 trace 系统 |
| [12 Incident § 3.4](./12-incident-response-sop.md#34-investigate找根因) | Incident 调查依赖 trace |
| [13 Cost § 8](./13-cost-budget.md#8-cost-attribution归因) | Cost Attribution 用 trace 数据 |
| [08 Safety § 11.4](./08-safety-policy.md#114-违规日志-schemasecurity_audit_log) | security_audit_log 与 trace 关联 |
| [11 Launch § 10.3 SLI/SLO](./11-launch-criteria-hitl.md#103-sli--slo-量化v02-新增) | SLI 数据从 trace 聚合 |

---

## 1. 技术选型（v1 决策）

### 1.1 选型对比

| 方案 | 优点 | 缺点 |
|------|-----|------|
| **Langfuse**（推荐）| LLM 专用 / OSS 可自托管 / SDK 完善 / Anthropic 集成好 | 需自托管或月费 |
| LangSmith | 商用功能完善 | vendor lock-in / 月费贵 |
| OpenTelemetry + Jaeger | 通用标准 / 开源 | 不专 LLM / Span schema 自定义重 |
| 自建 | 完全可控 | 工程成本高 |

### 1.2 v1 选型决策

- **生产 trace**: **Langfuse self-hosted**（开源版）
  * 部署在自己服务器（无 vendor lock-in）
  * 数据完全在自己手里（合规友好）
  * SDK：`langfuse-python`（后端）+ 移动端不接（成本控制）
- **Metrics**: **Prometheus + Grafana**
- **Logs**: **Loki**（与 Grafana 配套，与 trace 关联）
- **Alerts**: **Grafana Alerting** + PagerDuty / Slack webhook

**为什么不用 OpenTelemetry**：v1 阶段 LLM-specific 字段（prompt version / token / cost）用 OTel 配置重，Langfuse 开箱即用。

**v2 考虑**：DAU > 1K 后评估升级 LangSmith / Datadog（专业运维）。

### 1.3 自托管 Langfuse 配置

```yaml
# docker-compose.yml（v1 单节点）
services:
  langfuse:
    image: langfuse/langfuse:latest
    ports: ["3001:3000"]
    environment:
      DATABASE_URL: postgres://...   # 用项目主 PG
      NEXTAUTH_SECRET: ...
    volumes: ["/data/langfuse:/data"]
```

成本：~$50 / 月（额外 server 资源）。

---

## 2. Trace 数据模型

### 2.1 顶层：Trace

每次"用户请求 / 事件触发 → 完整决策链路"= 1 个 Trace。

```python
@dataclass
class Trace:
    # 基础
    trace_id: str                    # UUID
    agent_version: str               # e.g. "agent-v1.0.3"
    timestamp_start: datetime
    timestamp_end: datetime
    duration_ms: int

    # 上下文
    device_id_hash: str              # hash(device_id) 前 8 位（PII 保护）
    wallet_hash: str | None
    session_id: str
    loop_type: str                   # scout | thesis | notify | reflect

    # 业务
    triggered_by: str                # event_type / user_message_id
    skill_top_level: str | None      # 顶层 Skill（如 thesis_writer）
    user_persona: str
    regime: str

    # 结果
    status: str                      # success | failed | blocked | partial
    error: dict | None               # error_code + message + stack_summary

    # 成本（聚合所有 spans）
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_cache_hit_tokens: int

    # 安全 / 审计
    safety_decisions: list[str]      # 触发的 rule_id 列表
    audit_log_ids: list[str]         # 关联的 security_audit_log 条目

    # Spans（递归 tree）
    spans: list[Span]
```

### 2.2 Span 类型（5 类）

每个 trace 含多个 span 组成 **DAG**（有向无环图，不一定 tree）。

#### 2.2.1 LLM Span

```python
@dataclass
class LLMSpan(Span):
    type: str = "llm_call"
    span_id: str
    parent_id: str | None
    name: str                        # e.g. "S01.technical_analysis"

    # 时间
    timestamp_start: datetime
    duration_ms: int

    # Prompt
    prompt_id: str                   # P01
    prompt_version: str              # 0.2
    skill_id: str | None             # S01
    model: str                       # claude-opus-latest
    temperature: float
    max_tokens: int

    # I/O（核心）
    system_prompt_hash: str          # 完整 system prompt 的 hash（节省存储）
    user_messages: list[dict]        # 实际 messages（脱敏后）
    output: str                      # LLM 输出（含 tool_use）
    finish_reason: str               # stop / max_tokens / tool_use

    # Token 与成本
    input_tokens: int
    output_tokens: int
    cache_hit_tokens: int            # Prompt Caching 命中数
    cost_usd: float

    # 成本透明度
    cost_breakdown: dict             # { "input_no_cache": 0.012, "input_cached": 0.001, "output": 0.018 }

    # Eval 维度（如果是 Eval run 触发）
    is_eval: bool = False
    eval_golden_id: str | None       # 关联 golden case
```

#### 2.2.2 Tool Span

```python
@dataclass
class ToolSpan(Span):
    type: str = "tool_call"
    name: str                        # e.g. "T01.query_market"
    tool_id: str                     # T01
    tool_version: str

    # I/O
    input: dict                      # tool_use input
    output: dict                     # tool_result
    error_code: str | None
    error_message: str | None

    # Side effects
    side_effects: list[str]          # ["db_write:agent_strategies", "external_api:helius"]
    idempotent: bool

    # 性能
    duration_ms: int
    retries: int                     # 重试次数（默认 0）
```

#### 2.2.3 DB Query Span

```python
@dataclass
class DBSpan(Span):
    type: str = "db_query"
    name: str                        # e.g. "select_agent_memory"
    sql_template: str                # 参数化 SQL（不带 PII）
    duration_ms: int
    rows_returned: int
    error: str | None
```

#### 2.2.4 Safety Span

```python
@dataclass
class SafetySpan(Span):
    type: str = "safety_check"
    name: str                        # e.g. "T08.execute_swap.pre_check"
    rules_evaluated: list[str]       # ["HR01", "HR10", "SB01"]
    rules_matched: list[str]         # 命中规则
    decision: str                    # OK | WARN | REVIEW | BLOCK
    audit_log_id: str | None         # 关联 security_audit_log
```

#### 2.2.5 External API Span

```python
@dataclass
class ExternalAPISpan(Span):
    type: str = "external_api"
    name: str                        # "helius_ws" / "okx_dex_quote"
    provider: str
    method: str                      # GET / POST / WS
    url_template: str                # /v1/quote（无 query string）
    status_code: int
    duration_ms: int
    error: str | None
    cost_usd: float | None           # 部分外部 API 有成本
```

### 2.3 关联关系

```
Trace (trace_id = abc123)
├── LLMSpan (S08 thesis_writer)         [parent: trace]
│   ├── LLMSpan (S01 technical)         [parent: thesis_writer]
│   │   ├── ToolSpan (T01 query_market) [parent: S01]
│   │   ├── ToolSpan (T14 calc_indicators)
│   │   └── DBSpan (select klines)
│   ├── LLMSpan (S02 sentiment)         [parent: thesis_writer]
│   ├── LLMSpan (S03 onchain)           [parent: thesis_writer]
│   └── ToolSpan (T04 recall_memory)
├── SafetySpan (T08 pre_check)
└── ToolSpan (T08 execute_swap)
    └── ExternalAPISpan (jupiter_quote)
    └── ExternalAPISpan (rpc_broadcast)
```

---

## 3. Sampling 策略（什么 trace 必采）

| 类型 | 采样率 | 保留期 |
|------|-------|-------|
| **真金 swap (T08)** | **100%**（必采）| 180 天（合规）|
| **HITL 流程** | 100% | 180 天 |
| **Safety violation** | 100% | 180 天 |
| **错误 / 失败 trace** | 100% | 90 天 |
| **L3 thesis（多 Skill）** | 100% | 90 天 |
| **L2 thesis** | 100% v1（DAU 小）/ 50% v2（DAU > 1K）| 90 天 |
| **简单 query (T01-T03)** | 10%（采样）| 30 天 |
| **Eval run** | 100% | 30 天（与 golden 关联）|
| **DEBUG mode（开发环境）** | 100% | 7 天 |

**采样规则**：
- 头部决策（trace 开始时）决定是否采，避免半截 trace
- 失败的 trace **永远 100% 采**（即使采样率 10%）
- 关联 audit log 的 trace 永远 100%

---

## 4. 日志级别

| Level | 用途 | 示例 | 保留 |
|-------|------|------|-----|
| **DEBUG** | 开发调试 | LLM raw response / tool 内部计算 | 7 天 |
| **INFO** | 正常事件 | Skill 启动 / Tool 完成 / 策略触发 | 30 天 |
| **WARN** | 异常但可继续 | 降级 / Cache miss / Helius 重连 | 90 天 |
| **ERROR** | 失败 / 异常 | LLM 超时 / Tool fail / DB 异常 | 180 天 |
| **AUDIT** | 合规审计 | 真金 swap / HITL 决策 / Safety violation | **180 天**（合规）|

**v1 默认 Level**：生产 INFO+，Staging DEBUG+。

---

## 5. Metrics（聚合指标）

### 5.1 Golden Signals（按 SRE 范式）

| Signal | Metric | SLO（11 § 10.3）| 告警 |
|--------|--------|---------------|------|
| **Latency** | `decision_latency_p95` by loop | thesis L2 < 6s / L3 < 18s | P95 > SLO 持续 1h |
| **Traffic** | `requests_per_second` by skill | - | spike > 3× baseline |
| **Errors** | `error_rate` by skill / tool | < 1% | > 3% / 5min |
| **Saturation** | LLM API queue / DB conn pool / Memory queue | < 80% | > 80% / 5min |

### 5.2 业务 Metrics

| Metric | 维度 | 用途 |
|--------|------|------|
| `thesis_count_by_persona` | persona × regime | 用户行为分析 |
| `strategy_active_count` | device | 留存指标 |
| `hitl_response_time_p50` | device | UX 指标 |
| `hitl_approve_rate` | strategy | 信任度 |
| `paper_to_auto_conversion` | device | 漏斗 |
| `nps_score` | weekly | 满意度 |
| `cache_hit_rate` | skill / prompt | Cost 优化（13 § 7.1）|

### 5.3 Cost Metrics（13 引用）

| Metric | 维度 | 告警 |
|--------|------|------|
| `llm_cost_total_usd` | 全平台 | 月 > $1500（CB04 触发）|
| `llm_cost_per_device` | device | device > $1.50/day |
| `llm_cost_per_skill` | skill | 周环比 > 50% |
| `eval_cost_monthly` | - | > $1500 |

### 5.4 Safety Metrics

| Metric | 用途 | 告警 |
|--------|------|------|
| `injection_attempts_blocked` | 监控攻击趋势 | > 100/h |
| `injection_pattern_unique` | 新型攻击发现 | 新模式 → 触发 Red Team |
| `safety_rule_match_count` by rule_id | 哪条规则触发多 | - |
| `circuit_breaker_triggered` by CB id | 熔断频率 | 任意触发 |
| `kill_switch_invocations` | 紧急停止次数 | 任意 → SEV-0 review |

---

## 6. Dashboards（Grafana 面板）

### 6.1 Real-time Dashboard（默认主页）

- **Top row**：Active users / RPS / P95 latency / Cost today（4 大数字）
- **Mid row**：Latency 趋势 / Error rate / LLM Cost 累计
- **Bottom row**：HITL queue / Skill 调用 Top 10 / Recent SEV events

### 6.2 Decision Explorer（trace 检索 UI）

- 按 `trace_id` 直接打开（事故 / Eval review 主入口）
- 按 `device_id_hash` 搜该 device 最近 100 trace
- 按时间窗口 / Skill / 错误类型筛选
- 展示完整 span tree + 每 span 详情（点击展开）
- **跳转**：Langfuse 原生 UI（保留 LLM-specific 视图）

### 6.3 Cost Dashboard（13 § 8.2 引用）

- 见 [13 Cost § 8.2](./13-cost-budget.md#82-dashboard-视图)

### 6.4 Safety Dashboard

- AE01-AE10 当日触发分布
- Circuit Breaker 状态
- Kill Switch history
- Injection 趋势

### 6.5 Eval Dashboard（09 § 12 引用）

- L1-L4 pass rate 30 天趋势
- Judge vs 人工相关性
- Golden 数量增长曲线

### 6.6 Compliance Dashboard

- SEV-0/1/2/3 月度统计
- 多地区 IP 检测分布
- HITL 流程合规指标

---

## 7. 告警规则

### 7.1 告警分级（与 12 Incident § 1 对齐）

| 告警 | 触发条件 | SEV | 渠道 |
|------|---------|-----|------|
| LLM 超时飙升 | P95 latency > 30s 持续 5 min | SEV-2 | Slack |
| Tool error rate > 5% | 5 min 滑窗 | SEV-2 | Slack |
| Tool error rate > 15% | 5 min 滑窗 | SEV-1 | PagerDuty |
| LLM cost > $2/h | 1 hour | SEV-2 | Slack |
| LLM cost > $10/h | 1 hour | SEV-1 | PagerDuty |
| Safety violation（任何 SEV-0 类）| 立即 | **SEV-0** | PagerDuty + 电话 |
| HITL queue size > 50 | 1 min | SEV-2 | Slack |
| HITL pending > 60min（应 expired 没）| 1 个 | SEV-1 | PagerDuty |
| Helius WS 断连 > 2 min | continuous | SEV-2 | Slack |
| KMS 错误率 > 1% | 5 min（CB12）| SEV-1 | PagerDuty |
| Memory write retry queue > 100 | continuous | SEV-2 | Slack |
| Eval pass rate 跌 ≥ 5pp | per PR / nightly | SEV-2 | Slack + Block PR |

### 7.2 告警抑制（避免告警风暴）

- 同类告警 5 min 内合并（窗口聚合）
- 已 ack 的告警 1h 内不重复
- Maintenance window 内静音
- Cascading alerts（如 Helius 断 → 大量 thesis 失败）合并为一条 root cause

---

## 8. 隐私 / 合规

### 8.1 PII 处理（trace 内）

| 字段 | 处理 |
|------|------|
| `device_id` | hash(前 8 位) → `device_id_hash` |
| `wallet_address` | hash(前 8 位) |
| `private_key` / `mnemonic` | **永不写 trace**（log sanitizer regex 拦截）|
| `user_message` 原文 | 写 trace 但用 `<user_input>` 包裹 |
| LLM raw response | 写 trace（DEBUG / 90 天）|
| 金额 / 仓位数据 | 写 trace（30 天）|

### 8.2 用户数据访问

- **用户查自己的 trace**：通过 audit log query API（08 § 11.5），看到的是 `device_id_hash` 视角
- **Admin 查 trace**：可解 hash → device_id（带 audit）
- **导出**：用户可导出 30 天内 trace JSON（脱敏后）

### 8.3 删除请求处理

- 用户主动删除 → 7d 冷却期
- 期满后从 Langfuse + Prometheus 删该 device 数据
- audit log 保留（180d 合规要求，保留 hash 不解）

---

## 9. Trace 生命周期

```
1. 采集（运行时，每次 LLM/Tool 调用）
   └─ 异步发到 Langfuse SDK 队列（不阻塞主流程）
   ↓
2. 传输（5s 内 batch flush）
   └─ HTTP POST → Langfuse server
   ↓
3. 存储（Postgres + S3）
   └─ Trace metadata in PG / 大 payload (LLM raw) in S3
   ↓
4. 查询（Dashboard / API）
   └─ 30 天热数据（PG）+ 90 天冷数据（S3 archive）
   ↓
5. 归档（90 天后冷存）
   └─ 移到 S3 Glacier，仅 Audit / 合规调用
   ↓
6. 删除（依规则 / 用户请求）
   └─ 30 / 90 / 180 天 TTL 自动清理（含 audit）
```

---

## 10. 集成点（如何接入）

### 10.1 后端 Python 集成

```python
from langfuse import Langfuse
from langfuse.decorators import observe

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)

@observe(name="thesis_loop")
async def thesis_loop(token, device_id, ...):
    trace_id = current_trace_id()
    # 自动创建 trace + span tree
    technical = await s01_technical_analysis(token)
    sentiment = await s02_sentiment_analysis(token)
    onchain = await s03_onchain_analysis(token)
    thesis = await s08_thesis_writer(technical, sentiment, onchain)

    # 自动汇总 cost / latency
    return thesis

@observe(name="S01.technical_analysis", as_type="generation")
async def s01_technical_analysis(token):
    indicators = await t14_calc_technical_indicators(...)
    response = await anthropic_client.messages.create(...)  # auto-tracked
    return response
```

### 10.2 自动 instrumentation

- LLM 调用：Anthropic SDK + Langfuse 自动 wrap
- Tool 调用：装饰器 `@observe(name="T01.query_market", as_type="span")`
- DB 查询：psycopg2 wrapper 自动写 DBSpan
- 外部 API：requests / aiohttp 全局 hook

### 10.3 关联到 audit log

- 每个 SafetySpan 写入时 `audit_log_id = security_audit_log.insert(...)`
- 反向查询：从 audit_log_id → trace_id → 完整决策上下文

---

## 11. 性能影响

### 11.1 开销目标

| 操作 | 开销 |
|------|------|
| 创建 trace | < 1ms |
| 添加 span | < 0.5ms |
| Flush to Langfuse（异步） | 不阻塞主流程 |
| 整体请求开销 | < 5%（设计目标）|

### 11.2 优化

- 异步 batch flush（每 5s 或队列 100 条）
- 大 payload（LLM raw output > 10KB）只存 S3 reference
- 采样（§ 3）减少非关键 trace
- 失败时 fail-open（trace 写不进不影响主流程）

---

## 12. 现状 Gap

| # | Gap | 影响 | v1 目标 |
|---|-----|------|--------|
| G1 | Langfuse 未部署 | 无 trace 系统 | v1 启动前 |
| G2 | LLM 调用未接 Langfuse | 无 LLM trace | v1 必接 |
| G3 | Tool 调用 instrumentation 未做 | 无 Tool trace | v1 必做 |
| G4 | Prometheus + Grafana 未部署 | 无 Metrics | v1 必备 |
| G5 | Decision Explorer Dashboard 未建 | 事故难排查 | v1 必备 |
| G6 | Log sanitizer regex（PII / 私钥过滤）未集成 | 隐私风险 | v1 必备 |
| G7 | Audit log → trace 关联未建 | 合规链断 | v1 必备 |
| G8 | S3 archive 未配置 | 90 天后数据丢 | v1.5 |
| G9 | 自动告警规则未配 | 不能 detect | v1 必备 |
| G10 | 用户 trace 查询 API 未建（隐私权利）| 合规 | v1.5 |

---

## 13. 术语表

| 术语 | 含义 |
|------|------|
| Trace | 完整决策链路（含多 span）|
| Span | trace 内的一个操作单元 |
| DAG | Directed Acyclic Graph（spans 拓扑）|
| SLI / SLO | Service Level Indicator / Objective |
| Golden Signals | SRE 4 大信号（Latency / Traffic / Errors / Saturation）|
| Cardinality | metric 维度组合数（高基数 = 性能问题）|
| Sampling | 采样（不全采减少开销）|
| Instrumentation | 代码插桩（手动 / 自动）|

---

## Change Log

- **v0.1 (2026-04-24)**：首版完整填充
  - § 1 **技术选型 v1 决策**：Langfuse self-hosted（生产 trace）+ Prometheus/Grafana（Metrics）+ Loki（Logs）+ Grafana Alerting
  - § 2 **完整 Trace 数据模型**：
    * Trace 顶层 schema（含 PII 处理 / 成本聚合 / safety_decisions / audit 关联）
    * **5 类 Span**：LLM / Tool / DB / Safety / External API（每类完整字段定义）
    * Span DAG 关联示例
  - § 3 **Sampling 策略**：真金/HITL/Safety 100% / L3 100% / 简单查询 10%
  - § 4 5 个日志级别（DEBUG/INFO/WARN/ERROR/AUDIT）+ 保留期
  - § 5 **Metrics 4 类**：
    * Golden Signals（Latency/Traffic/Errors/Saturation）
    * 业务 Metrics（thesis 数 / HITL 响应 / 漏斗）
    * Cost Metrics（对齐 13）
    * **Safety Metrics**（Injection 趋势 / CB / Kill Switch）
  - § 6 **6 个 Dashboard**：Real-time / Decision Explorer / Cost / Safety / Eval / Compliance
  - § 7 **告警规则 12 条** + 告警抑制（避免风暴）
  - § 8 隐私：PII hash / 私钥永不写 / 用户查自己 trace API
  - § 9 Trace 生命周期 6 阶段（采集→传输→存储→查询→归档→删除）
  - § 10 **集成方法**：Langfuse SDK + 装饰器 + 自动 instrumentation
  - § 11 性能开销目标 < 5%
  - § 12 10 条现状 Gap
- v0（2026-04-22）：初始骨架
