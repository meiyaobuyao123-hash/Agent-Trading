# PRD-004: 中等问题合集修复

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-03-22 |
| 所属模块 | agent-trading / btc-eth-investment |
| 优先级 | P1（中等） |
| 状态 | 待开发 |

---

## 问题清单

### M-01: trigger_count TOCTOU 竞态条件

**文件**: `agent/strategy_manager.py:245-253`

**问题**: RPC `increment_trigger_count` 失败时，fallback 用 read-modify-write 模式。并发触发同一策略时会丢失计数。

**修复方案**:
- 改用 Supabase RPC 原子操作（服务端 SQL function）
- 或改用乐观锁（带 version 字段的 upsert）

```sql
-- Supabase RPC function
CREATE OR REPLACE FUNCTION increment_trigger(sid UUID)
RETURNS void AS $$
  UPDATE strategies SET trigger_count = trigger_count + 1 WHERE id = sid;
$$ LANGUAGE sql;
```

**验收**: 并发 10 次触发后，trigger_count 准确等于 10

---

### M-02: LLM Parser 无重试逻辑

**文件**: `agent/llm_parser.py`

**问题**: Claude API 调用无 retry。网络抖动、429 限流、5xx 错误直接返回 None，用户看到"策略创建失败"。

**修复方案**:
```python
for attempt in range(3):
    try:
        response = client.messages.create(...)
        return parse_response(response)
    except (RateLimitError, InternalServerError) as e:
        await asyncio.sleep(2 ** attempt * 5)
    except Exception as e:
        log.error(f"LLM Parser error: {e}")
        break
return None
```

**验收**: 模拟 API 超时，第 2 次重试成功返回策略

---

### M-03: 硬编码参数提取到 config

**问题**: 大量业务参数散落在代码各处，修改需要改代码重启。

| 参数 | 当前位置 | 当前值 | 应移至 |
|------|---------|--------|--------|
| 信号池门槛 | collector.py | score ≥ 55 | config.py SIGNAL_POOL_MIN_SCORE |
| BC 范围 | collector.py | 3%-35% | config.py SIGNAL_POOL_BC_RANGE |
| 月度 API 配额 | routes_agent.py:144 | 20 | config.py AGENT_MONTHLY_QUOTA |
| 风控日亏损上限 | risk_manager.py | $50 | config.py RISK_DAILY_LOSS_LIMIT |
| 风控周亏损上限 | risk_manager.py | $200 | config.py RISK_WEEKLY_LOSS_LIMIT |
| 最大仓位 | risk_manager.py | $100 | config.py RISK_MAX_POSITION_USD |
| BTC 危机阈值 | risk_manager.py:423 | 10min跌3% | config.py BTC_CRISIS_PCT |
| 追踪止损激活 | risk_manager.py | 15% | config.py TRAILING_STOP_ACTIVATION |
| 信号冷却时间 | signal_generator.py | 4h | config.py SIGNAL_COOLDOWN_HOURS |
| 深度失衡阈值 | signal_generator.py | 0.3 | config.py DEPTH_IMBALANCE_THRESHOLD |

**修复方案**: 统一移至 `config.py`，从环境变量读取，支持热更新。

**验收**: 修改 .env 中的参数值，重启后生效

---

### M-04: btc_eth_indicators 表为空

**文件**: `btc_eth/storage.py` + `btc_eth/manager.py`

**问题**: 后端 API 返回内存中的指标数据（正常），但 `btc_eth_indicators` 表始终为空（`_persist_indicators` 未生效）。

**可能原因**:
1. `_persist_indicators` 循环未启动
2. 写入时列名不匹配
3. 写入异常被静默吞掉

**修复方案**:
1. 检查 manager.py 中 `_persist_indicators` 是否在 `start()` 中被 `create_task`
2. 添加写入日志（成功/失败都记录）
3. 验证列名与 migration 025 一致

**验收**: 部署后 5 分钟内 btc_eth_indicators 有 2 行数据（BTC+ETH）

---

### M-05: Paper Trading 止盈止损未主动检查

**文件**: `btc_eth/paper_trading/engine.py`

**问题**: `check_exits()` 方法存在但未被定时调用。模拟盘交易开仓后，止盈止损条件不会被检查。

**修复方案**:
- 在 `btc_eth/manager.py` 的 `_track_signals` 循环中加入 `paper_engine.check_exits(current_prices)`
- 每次价格更新时检查所有 open 的模拟盘持仓

**验收**: 模拟盘买入后，价格触达 TP/SL 时自动平仓并记录 PnL

---

## 优先级排序

| 序号 | 问题 | 优先级 | 预估工作量 |
|------|------|--------|-----------|
| 1 | M-03 硬编码参数 | 高 | 2h |
| 2 | M-02 LLM Parser 重试 | 高 | 1h |
| 3 | M-04 indicators 表为空 | 高 | 1h |
| 4 | M-05 Paper Trading SL/TP | 中 | 2h |
| 5 | M-01 TOCTOU 竞态 | 中 | 1h |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-22 | 初始版本 |
