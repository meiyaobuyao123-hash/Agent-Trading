# PRD-006: 市场 Regime 检测 + 动态风控升级

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.1（审查修订版） |
| 创建日期 | 2026-03-23 |
| 修订日期 | 2026-03-23 |
| 所属模块 | Phase 2（交易 Agent M9/M8 升级 + 优化 Agent O7） |
| 优先级 | P0 |
| 状态 | 待审批 |

---

## 一、调研背景

### 1.1 行业数据

| 数据 | 来源 |
|------|------|
| 97% 的 AI 交易系统在真实回撤中失败 | 47 系统实测报告 |
| CUSUM + Triple Barrier 在 BTC/ETH 上"扣除手续费仍持续正收益" | Springer 2025 |
| HMM 在检测 BTC 牛熊转换上优于传统模型 | ResearchGate 2024 |
| CUSUM 能在传统趋势指标反应之前检测到结构性变化 | LuxAlgo/TradingView |
| ATR 动态仓位比固定百分比减少 25% 回撤 | LuxAlgo 2025 |

### 1.2 技术路线

**最终方案：三阶段混合检测 + 多资产**
```
Stage 1: CUSUM（实时，每 5min）→ "市场发生了变化"
Stage 2: HMM（每 30min）→ "当前是什么状态"（fallback：纯规则引擎）
Stage 3: LLM（仅切换时）→ "为什么变了 + 策略建议"
CRISIS: 独立 1min 规则引擎（不等 HMM）
```

---

## 二、Regime 状态定义

### 7 种状态 = HMM(4基础) + 规则引擎(3叠加)（v1.1 修订 Q2）

| Regime | 来源 | 特征 | 策略影响 |
|--------|------|------|---------|
| **TRENDING_UP** | HMM | MA 多头排列，成交量放大 | 正常做多，放宽止盈 |
| **TRENDING_DOWN** | HMM | MA 空头排列 | 只做空或观望，收紧止损 |
| **RANGING** | HMM | 价格区间震荡，ATR 低 | 高抛低吸，缩小仓位 |
| **HIGH_VOLATILITY** | HMM | ATR > 均值 2 倍 | 仓位减半，止损放宽（避免假穿） |
| **BREAKOUT** | 规则叠加 | HMM=UP + 突破 20 日高 + 量>3×均值 | 追踪突破，快进快出 |
| **CRISIS** | 规则叠加 | BTC 15min 跌>5% 或爆仓>$500M | 清仓，暂停交易 |
| **RECOVERY** | 规则叠加 | 从 CRISIS/DOWN 转入，无新低 30min | 小仓位试探 |

---

## 三、M9 Regime 检测器

### 3.1 多资产检测（v1.1 修订 Q1）

```
主 Regime：BTC（大盘方向）
辅 Regime：SOL/USD（SOL 生态，70% 交易在 SOL链）、ETH/USD（EVM 链）

综合判定逻辑：
  BTC=CRISIS → 全局 CRISIS（无条件）
  BTC=TRENDING_UP + SOL=TRENDING_DOWN → SOL 链暂停交易
  BTC=RANGING + SOL=HIGH_VOLATILITY → SOL MEME 减仓
  BTC=TRENDING_DOWN + SOL=TRENDING_UP → SOL 链可交易但仓位减半
```

### 3.2 Stage 1: CUSUM 统计检测

```
输入：BTC/SOL/ETH 1h K线的 log-returns
频率：每 5 分钟
参数（v1.1 修订 Q4）：
  BTC: N=24, k=0.5σ, h_warning=2σ, h_change=3σ
  SOL: N=24, k=0.5σ, h_warning=1.5σ, h_change=2.5σ（SOL 更敏感）

输出：
  change_detected: bool
  warning_detected: bool（v1.1 新增）
  direction: "up" | "down" | "none"
  magnitude: float
```

### 3.3 Stage 2: HMM 状态分类

```
输入：最近 7 天多维特征（BTC/SOL/ETH 各自独立 HMM）
  - 1h returns、volume_change、ATR_14/MA_ATR_14、funding_rate
频率：每 30 分钟
状态数：4（TRENDING_UP/DOWN/RANGING/HIGH_VOLATILITY）

训练后状态标签校准（v1.1 修订 Q3）：
  1. 按每个状态的 return 均值排序
  2. 最高 → TRENDING_UP
  3. 最低 → TRENDING_DOWN
  4. 波动率最高 → HIGH_VOLATILITY
  5. 剩余 → RANGING

Fallback（v1.1 修订 Q8）：
  如果 hmmlearn 安装失败，使用纯规则引擎：
    TRENDING_UP: MA7 > MA25 > MA99 + 24h涨幅>3%
    TRENDING_DOWN: MA7 < MA25 < MA99 + 24h跌幅>3%
    HIGH_VOLATILITY: ATR_14 > 2 × MA_ATR_30
    RANGING: 以上都不满足
```

### 3.4 CRISIS 独立检测（v1.1 修订 Q5）

```
频率：每 1 分钟（不等 HMM 30min）
触发条件（任一）：
  1. BTC 15min 跌 > 5%
  2. 全网 1h 爆仓 > $500M
  3. 资金费率 < -0.1%

恢复条件（v1.1 修订 Q7，全部满足 + 持续 30min）：
  1. BTC 过去 1h 最低价 > 过去 2h 最低价
  2. BTC 15min 涨跌幅 > -1%
  3. 全网 1h 爆仓 < $100M
  4. 以上持续满足 30 分钟
```

### 3.5 Stage 3: LLM 解释

```
触发：HMM 状态切换（置信度 > 0.7）
模型：Claude Haiku（$0.001/次）
用途（v1.1 修订 Q6）：
  1. 写入短期记忆（Agent 决策上下文）
  2. 写入 regime_history（优化 Agent 审计）
  3. 推送给用户（"市场状态变化"通知）
月成本：~$0.06（约 60 次切换/月）
```

### 3.6 EventBus 事件

```python
event_bus.publish("market.regime_change", {
    "asset": "BTC",           # 哪个资产的 regime 变了
    "old_regime": "RANGING",
    "new_regime": "TRENDING_UP",
    "confidence": 0.85,
    "explanation": "BTC 放量突破 $72K 阻力位",
    "strategy_adjustment": "建议提高多头仓位",
})

# 订阅方：risk_manager / event_listener / position_monitor / working_memory
```

---

## 四、M8 风控动态升级

### 4.1 Regime 感知风控参数（v1.1 修订 Q12：移到 config.py）

```python
# config.py — 可被优化 Agent 通过提案修改
REGIME_RISK_PARAMS = {
    "TRENDING_UP":     {"position_pct": 1.0, "sl_mult": 1.0, "tp_mult": 1.5, "new_trades": True,  "force_close": False},
    "TRENDING_DOWN":   {"position_pct": 0.3, "sl_mult": 0.7, "tp_mult": 0.8, "new_trades": False, "force_close": False},
    "RANGING":         {"position_pct": 0.5, "sl_mult": 0.8, "tp_mult": 0.8, "new_trades": True,  "force_close": False},
    "HIGH_VOLATILITY": {"position_pct": 0.5, "sl_mult": 1.5, "tp_mult": 1.0, "new_trades": True,  "force_close": False},
    "BREAKOUT":        {"position_pct": 0.8, "sl_mult": 1.2, "tp_mult": 2.0, "new_trades": True,  "force_close": False},
    "CRISIS":          {"position_pct": 0.0, "sl_mult": 0.5, "tp_mult": 0.0, "new_trades": False, "force_close": True},
    "RECOVERY":        {"position_pct": 0.3, "sl_mult": 0.8, "tp_mult": 1.0, "new_trades": True,  "force_close": False},
}
```

### 4.2 ATR 动态仓位（v1.1 修订 Q9：增加硬上限）

```
dynamic_position = base_position / atr_ratio * regime_mult

硬上限：
  single_max = min(dynamic_position, $200)
  total_max = portfolio_value * 0.5
  daily_buy_max = portfolio_value * 0.3
```

### 4.3 ATR 动态止损

```
stop_loss = entry_price - (ATR_14 × 2.0 × regime_sl_mult)

示例（BTC entry=$70K）：
  ATR=$2K + TRENDING_UP(1.0) → SL=$66K（-5.7%）
  ATR=$5K + HIGH_VOL(1.5)   → SL=$55K（-21.4%）
  ATR=$2K + CRISIS(0.5)     → SL=$68K（-2.9%）
```

### 4.4 时间衰减止损（v1.1 修订 Q10：盈利保护）

```python
if token_type == "meme":
    if hold_hours > 8 and current_pnl > 0:
        # 盈利中 → 用追踪止损替代时间衰减
        stop_loss = max(entry_price, peak_price * 0.85)
    elif hold_hours > 8 and current_pnl < -10:
        # 亏损中 → 收紧止损
        stop_loss *= 0.8
    elif hold_hours > 12:
        # 无论盈亏都收紧
        stop_loss *= 0.7
```

### 4.5 CRISIS 清仓策略（v1.1 修订 Q11）

```
1. 按持仓金额从大到小排序
2. 每笔卖出间隔 3s（避免并发踩踏）
3. 滑点放宽到 5%（优先成交）
4. 失败 → 重试 1 次 → 仍失败记录 pending
5. 总超时 60s
6. 同时推送紧急通知给用户
```

### 4.6 灰度上线方案（v1.1 修订 Q13）

```
Phase A（第 1 周）：Shadow Mode
  → 动态参数计算但不生效
  → 日志记录"如果用动态参数会怎样"
  → 对比静态 vs 动态拦截差异

Phase B（第 2 周）：正式切换
  → 动态参数叠加在静态之上
  → 硬底线永不被覆盖（蜜罐/日亏损/最大回撤）
```

---

## 五、O7 Regime 审计工具

```python
def tool_read_regime_history(days: int = 14) -> dict:
    return {
        "transitions": [...],  # 切换历史+24h后价格对比

        "performance_by_regime": {
            "TRENDING_UP": {"hours": 120, "trades": 25, "win_rate": 0.72, "avg_pnl": 4.2},
            "RANGING": {"hours": 80, "trades": 15, "win_rate": 0.47, "avg_pnl": 0.3},
            ...
        },

        # v1.1 新增 Q14
        "avg_detection_delay_minutes": 25,  # 事后回看法计算
        "detection_method": "对比价格拐点(>5%反转持续>4h) vs regime切换时间",

        # v1.1 新增 Q15
        "false_transitions": 2,
        "false_transition_cost_usd": 15.50,  # 误报造成的实际 PnL 损失
        "false_rate": 0.167,
    }
```

---

## 六、数据库

```sql
CREATE TABLE IF NOT EXISTS agent_regime_history (
    id BIGSERIAL PRIMARY KEY,
    asset TEXT NOT NULL,                -- 'BTC' | 'SOL' | 'ETH'
    regime TEXT NOT NULL,
    confidence NUMERIC,
    btc_price NUMERIC,
    atr_14 NUMERIC,
    funding_rate NUMERIC,
    fear_greed INT,
    hmm_state_probs JSONB,
    cusum_up NUMERIC,
    cusum_down NUMERIC,
    explanation TEXT,
    is_transition BOOLEAN DEFAULT FALSE,
    previous_regime TEXT,
    false_transition BOOLEAN,           -- v1.1 回填
    transition_cost_usd NUMERIC,        -- v1.1 误报代价
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_regime_ts ON agent_regime_history(asset, created_at DESC);
```

存储：48 条/天 × 3 资产 × 0.5KB = 72KB/天 ≈ 2.2MB/月（30 天清理）

---

## 七、技术影响

| 文件 | 操作 |
|------|------|
| `agent/regime_detector.py` | **新建** — CUSUM+HMM+LLM+CRISIS 四模块 |
| `agent/risk_manager.py` | 修改 — Regime 参数+ATR 仓位+ATR 止损+时间衰减+CRISIS |
| `agent/position_monitor.py` | 修改 — CRISIS 收紧止损+清仓序列 |
| `agent/event_listener.py` | 修改 — 订阅 regime_change |
| `agent/memory/working_memory.py` | 修改 — Regime 变化写入 |
| `optimizer_tools.py` | 修改 — +tool_read_regime_history |
| `optimizer_agent.py` | 修改 — TOOL_DEFINITIONS +1 |
| `main.py` | 修改 — 注册 regime 检测任务 |
| `config.py` | 修改 — REGIME_RISK_PARAMS + ATR + CUSUM 参数 |
| `api/routes_agent.py` | 修改 — +/api/agent/regime |
| `migrations/029_regime_history.sql` | **新建** |

依赖：`pip install hmmlearn`（fallback 到纯规则引擎）

---

## 八、成本

| 项目 | 月成本 |
|------|--------|
| CUSUM + HMM 本地计算 | $0 |
| LLM Regime 解释（Haiku ~60 次/月） | $0.06 |
| hmmlearn 包 | $0（开源） |
| **总新增** | **$0.06/月** |

---

## 九、验收标准

- [ ] CUSUM 每 5min 运行，BTC/SOL/ETH 三资产
- [ ] HMM 每 30min 分类，输出 4 基础状态 + 置信度；fallback 规则引擎可用
- [ ] HMM 每日重训练后标签校准正确
- [ ] CRISIS 独立 1min 检测，BTC 15min 跌>5% 时 <60s 触发
- [ ] CRISIS 恢复需 4 条件持续 30min
- [ ] 多资产综合判定：BTC CRISIS → 全局 CRISIS
- [ ] ATR 仓位：高波动自动缩小，有硬上限
- [ ] 时间衰减：盈利中用追踪止损替代
- [ ] CRISIS 清仓：排序+间隔+重试+超时
- [ ] Shadow mode 第 1 周不生效，仅记录对比
- [ ] Regime 参数可被优化 Agent 通过提案修改
- [ ] O7 审计：切换历史+各 regime 表现+检测延迟+误报代价

---

## 十、v1.1 修订记录

| # | 修订 | 原因 |
|---|------|------|
| Q1 | 多资产 Regime（BTC+SOL+ETH） | 只看 BTC 不够，SOL MEME 可能独立行情 |
| Q2 | HMM(4) + 规则(3) = 7 种 | 解决 4 vs 7 矛盾 |
| Q3 | HMM 训练后按 return 校准标签 | 防止状态定义漂移 |
| Q4 | BTC h=3σ，SOL h=2.5σ + warning 级别 | 5σ 太保守 |
| Q5 | CRISIS 独立 1min 检测 | HMM 30min 对闪崩太慢 |
| Q6 | LLM 解释保留（记忆+推送+审计） | 成本极低但三方都需要 |
| Q7 | CRISIS 恢复 4 条件 + 30min 持续 | 原条件太模糊 |
| Q8 | 纯规则引擎作 HMM fallback | hmmlearn 安装可能失败 |
| Q9 | ATR 仓位硬上限（$200/50%/30%） | 低波动时仓位可能无限放大 |
| Q10 | 盈利中用追踪止损替代时间衰减 | 避免强制割在低点 |
| Q11 | CRISIS 清仓：排序+3s间隔+5%滑点 | 防止并发踩踏 |
| Q12 | Regime 参数移到 config.py | 支持优化 Agent 提案修改 |
| Q13 | Shadow mode 灰度 + 硬底线 | 新旧风控安全过渡 |
| Q14 | 检测延迟用事后回看法 | 解决"实际拐点"无法实时知道的问题 |
| Q15 | 误报记录实际 PnL 代价 | 光知道误报率不够，要量化损失 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-23 | 初始版本 |
| v1.1 | 2026-03-23 | 审查修订：15 项优化 |
