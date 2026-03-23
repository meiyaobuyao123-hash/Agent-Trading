# PRD-006: 市场 Regime 检测 + 动态风控升级

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-03-23 |
| 所属模块 | Phase 2（交易 Agent M9/M8 升级 + 优化 Agent O7） |
| 优先级 | P0 |
| 状态 | 待审批 |

---

## 一、调研背景

### 1.1 为什么需要 Regime 检测

| 数据 | 来源 |
|------|------|
| 97% 的 AI 交易系统在真实回撤中失败 | 47 系统实测报告 |
| 失败的首要原因是"不能适应市场状态变化" | CoinDesk 2026/02 分析 |
| CUSUM + Triple Barrier 在 BTC/ETH 上"即使扣除手续费仍持续正收益" | Springer 2025 论文 |
| HMM 在检测 BTC 牛熊转换上优于传统模型 | ResearchGate 2024 |
| CUSUM 能在传统趋势指标反应之前检测到结构性变化 | LuxAlgo/TradingView |
| ATR 动态仓位比固定百分比减少 25% 回撤 | LuxAlgo 2025 研究 |

### 1.2 技术路线对比

| 方案 | 检测速度 | 准确度 | 复杂度 | 成本 | 选择 |
|------|---------|--------|--------|------|------|
| **CUSUM 统计检测** | 实时（每根K线） | 中（只知道"变了"） | 低 | $0 | ✅ 第一阶段 |
| **HMM 隐马尔可夫** | 分钟级 | 高（状态+概率） | 中 | $0（hmmlearn） | ✅ 第二阶段 |
| **LLM 解释** | 秒级（调用后） | 高（原因分析） | 低 | ~$0.01/次 | ✅ 触发后 |
| **Random Forest/GBM** | 分钟级 | 高 | 高（需训练数据） | $0 | ❌ 数据不足 |
| **强化学习** | 慢（需训练） | 不确定 | 极高 | $0 | ❌ 过度工程 |

**最终方案：三阶段混合检测**
```
Stage 1: CUSUM 统计检测（实时，每 5min）
  → 检测"市场发生了变化"（快但不知道变成什么）

Stage 2: HMM 状态分类（每 30min）
  → 分类当前处于哪种 regime（慢但准确）

Stage 3: LLM 解释（仅 regime 切换时触发）
  → 解释"为什么切换了"+ "策略应如何调整"
```

### 1.3 Regime 状态定义

基于调研（HMM 论文 + LuxAlgo + Syntium），定义 7 种市场状态：

| Regime | 特征 | 策略影响 |
|--------|------|---------|
| **TRENDING_UP** | 价格持续上涨，MA 多头排列，成交量放大 | 正常做多，放宽止盈 |
| **TRENDING_DOWN** | 价格持续下跌，MA 空头排列 | 只做空或观望，收紧止损 |
| **RANGING** | 价格在区间震荡，ATR 低 | 高抛低吸，缩小仓位 |
| **HIGH_VOLATILITY** | ATR > 均值 2 倍，价格剧烈波动 | 仓位减半，止损放宽（避免假穿） |
| **BREAKOUT** | 价格突破关键位，成交量暴增 | 追踪突破方向，快进快出 |
| **CRISIS** | BTC 15min 跌 > 5% 或资金费率极端 | 清仓所有持仓，暂停新交易 |
| **RECOVERY** | 从 CRISIS/TRENDING_DOWN 转入，成交量温和放大 | 小仓位试探性买入 |

---

## 二、需求概述

### 交易 Agent 侧

**M9 Regime 检测器**：实时检测市场状态，驱动策略和风控调整

**M8 风控升级**：从 15 项静态检查 → 动态风控（Regime 感知 + ATR 仓位 + 时间衰减止损）

### 优化 Agent 侧

**O7 Regime 审计工具**：评估交易 Agent 是否及时适应了市场变化

---

## 三、详细需求

### 3.1 M9 Regime 检测器

#### Stage 1: CUSUM 统计检测

```
输入：BTC 1h K线的 log-returns
频率：每 5 分钟（每根新 K线或价格更新时）
算法：
  1. 计算最近 N 根 K线的 log-return 均值和标准差
  2. 累积偏差：S_t = max(0, S_{t-1} + (x_t - μ - k))  （上偏）
                S_t = min(0, S_{t-1} + (x_t - μ + k))  （下偏）
  3. 超过阈值 h → 发出"变化信号"

参数：
  N = 24（24 根 1h K线 = 1 天基线）
  k = 0.5σ（灵敏度，σ 为标准差）
  h = 5σ（阈值，避免假信号）

输出：
  change_detected: bool
  direction: "up" | "down" | "none"
  magnitude: float（累积偏差值）
```

#### Stage 2: HMM 状态分类

```
输入：最近 7 天的多维特征
  - BTC 1h returns（价格变化率）
  - BTC 1h volume_change（成交量变化率）
  - ATR_14 / MA_ATR_14（标准化波动率）
  - funding_rate（资金费率）

频率：每 30 分钟
算法：GaussianHMM（hmmlearn 库，Python 标准包）
状态数：4（对应 TRENDING_UP / TRENDING_DOWN / RANGING / HIGH_VOLATILITY）

训练：
  - 用最近 30 天历史数据初始化（无监督聚类）
  - 每天 UTC 04:00 自动重训练（滑动窗口）
  - 不需要标注数据（HMM 无监督学习）

输出：
  current_state: str（7 种之一）
  state_probability: float（当前状态的置信度 0-1）
  transition_prob: dict（转移到其他状态的概率）
  持续时间：当前状态已持续多少小时
```

#### Stage 3: LLM 解释（仅切换时触发）

```
触发条件：HMM 状态从 A 切换到 B（且置信度 > 0.7）
调用：Claude Haiku（低成本，只做文字解释）

Prompt：
  "市场状态从 {old_state} 切换为 {new_state}。
   当前数据：BTC ${price} 24h涨幅{change}%，ATR={atr}，
   资金费率={funding}，恐慌指数={fgi}。
   请用 1-2 句话解释原因，并建议策略调整方向。"

输出：
  explanation: str（"BTC 从震荡转为上涨趋势，24h 放量突破 $72K 阻力位"）
  strategy_adjustment: str（"建议提高多头仓位至 60%，放宽止盈空间"）
```

#### Regime 变化事件发布

```python
# 状态切换时发布到 EventBus
event_bus.publish("market.regime_change", {
    "old_regime": "RANGING",
    "new_regime": "TRENDING_UP",
    "confidence": 0.85,
    "explanation": "...",
    "strategy_adjustment": "...",
    "timestamp": "2026-03-23T14:00:00Z",
})

# 订阅方：
# - risk_manager: 动态调整风控参数
# - event_listener: 作为策略触发事件
# - position_monitor: CRISIS 模式立即止损
# - memory/working_memory: 记录到短期记忆
```

### 3.2 M8 风控动态升级

#### 3.2.1 Regime 感知风控参数

```python
# 根据 regime 动态调整风控参数
REGIME_RISK_PARAMS = {
    "TRENDING_UP": {
        "max_position_pct": 1.0,      # 正常仓位
        "stop_loss_multiplier": 1.0,   # 正常止损
        "take_profit_multiplier": 1.5, # 放宽止盈
        "new_trades_allowed": True,
    },
    "TRENDING_DOWN": {
        "max_position_pct": 0.3,       # 仓位缩至 30%
        "stop_loss_multiplier": 0.7,   # 收紧止损
        "take_profit_multiplier": 0.8, # 收紧止盈
        "new_trades_allowed": False,   # 不开新多单
    },
    "RANGING": {
        "max_position_pct": 0.5,       # 仓位减半
        "stop_loss_multiplier": 0.8,   # 稍收紧
        "take_profit_multiplier": 0.8,
        "new_trades_allowed": True,
    },
    "HIGH_VOLATILITY": {
        "max_position_pct": 0.5,       # 仓位减半
        "stop_loss_multiplier": 1.5,   # 放宽止损（避免假穿）
        "take_profit_multiplier": 1.0,
        "new_trades_allowed": True,    # 可以但仓位小
    },
    "CRISIS": {
        "max_position_pct": 0.0,       # 不开新仓
        "stop_loss_multiplier": 0.5,   # 立即收紧所有止损
        "new_trades_allowed": False,
        "force_close_all": True,       # 清仓所有持仓
    },
    "BREAKOUT": {
        "max_position_pct": 0.8,
        "stop_loss_multiplier": 1.2,   # 稍放宽（突破回测正常）
        "take_profit_multiplier": 2.0, # 大幅放宽止盈
        "new_trades_allowed": True,
    },
    "RECOVERY": {
        "max_position_pct": 0.3,       # 小仓位试探
        "stop_loss_multiplier": 0.8,
        "new_trades_allowed": True,
    },
}
```

#### 3.2.2 ATR 动态仓位（替代固定仓位）

```
当前：max_position_usd = $100（固定）
改为：
  base_position = $100
  atr_ratio = current_ATR / avg_ATR_30d
  regime_mult = REGIME_RISK_PARAMS[regime]["max_position_pct"]

  dynamic_position = base_position / atr_ratio * regime_mult

  示例：
    正常波动(atr_ratio=1.0) + TRENDING_UP(mult=1.0) → $100
    高波动(atr_ratio=2.0) + HIGH_VOLATILITY(mult=0.5) → $100/2*0.5 = $25
    低波动(atr_ratio=0.5) + TRENDING_UP(mult=1.0) → $100/0.5*1.0 = $200（上限 cap）
```

#### 3.2.3 ATR 动态止损（替代固定百分比）

```
当前：stop_loss = entry_price × (1 - stop_loss_pct)（固定 30%）
改为：
  atr_14 = 最近 14 根 K线的 ATR
  multiplier = 2.0 × REGIME_RISK_PARAMS[regime]["stop_loss_multiplier"]

  stop_loss = entry_price - (atr_14 * multiplier)

  示例（BTC entry=$70,000）：
    ATR=$2,000 + TRENDING_UP(mult=1.0) → SL = $70K - ($2K×2×1.0) = $66K（-5.7%）
    ATR=$5,000 + HIGH_VOLATILITY(mult=1.5) → SL = $70K - ($5K×2×1.5) = $55K（-21.4%）
    ATR=$2,000 + CRISIS(mult=0.5) → SL = $70K - ($2K×2×0.5) = $68K（-2.9%）
```

#### 3.2.4 时间衰减止损（MEME 专用）

```
MEME 币持仓越久越危险（调研数据：持仓>8h 亏损概率从 35% 升至 62%）

实现：
  hold_hours = (now - entry_time).total_seconds() / 3600

  if token_type == "meme":
      if hold_hours > 12:
          stop_loss *= 0.7    # 收紧 30%
      elif hold_hours > 8:
          stop_loss *= 0.8    # 收紧 20%
      elif hold_hours > 4:
          stop_loss *= 0.9    # 收紧 10%
```

#### 3.2.5 CRISIS 模式自动清仓

```
触发条件（任一）：
  1. BTC 15min 跌 > 5%
  2. 全网 1h 爆仓 > $500M
  3. 资金费率 < -0.1%（极端空头）

执行：
  1. regime 切换为 CRISIS
  2. 立即收紧所有持仓止损至 entry_price × 0.97（-3%）
  3. 暂停所有新交易
  4. 发送紧急推送通知
  5. 写入 agent_risk_events
  6. 恢复条件：BTC 稳定 1h 无进一步下跌 + 恐慌指数回升
```

### 3.3 O7 Regime 审计工具

```python
def tool_read_regime_history(days: int = 14) -> dict:
    """优化 Agent 调用此工具评估 Regime 检测效果"""

    return {
        "period_days": 14,

        # Regime 切换历史
        "transitions": [
            {
                "from": "RANGING", "to": "TRENDING_UP",
                "timestamp": "2026-03-20T14:00:00Z",
                "confidence": 0.85,
                "btc_price_at_switch": 72000,
                "btc_price_24h_later": 75500,  # +4.9%
                "was_timely": True,  # 切换后价格继续往预期方向走
            },
            # ...
        ],

        # 各 regime 下的交易表现
        "performance_by_regime": {
            "TRENDING_UP": {
                "hours_in_regime": 120,
                "trades": 25,
                "win_rate": 0.72,
                "avg_pnl": 4.2,
            },
            "RANGING": {
                "hours_in_regime": 80,
                "trades": 15,
                "win_rate": 0.47,
                "avg_pnl": 0.3,
            },
            "HIGH_VOLATILITY": {
                "hours_in_regime": 30,
                "trades": 8,
                "win_rate": 0.38,
                "avg_pnl": -2.1,
            },
        },

        # 检测延迟评估
        "avg_detection_delay_minutes": 25,  # 从实际拐点到检测到的平均延迟

        # 误报率
        "false_transitions": 2,  # 切换后又快速切回（<2h）
        "total_transitions": 12,
        "false_rate": 0.167,

        # 优化建议
        "insights": [
            "HIGH_VOLATILITY 下交易表现差（胜率 38%），建议 regime=HV 时暂停交易",
            "TRENDING_UP 时胜率最高（72%），当前 regime 参数已合理",
            "检测延迟 25min 可接受，CUSUM 阈值无需调整",
        ],
    }
```

---

## 四、数据库设计

### 新增表：agent_regime_history

```sql
CREATE TABLE IF NOT EXISTS agent_regime_history (
    id BIGSERIAL PRIMARY KEY,
    regime TEXT NOT NULL,
    confidence NUMERIC,
    btc_price NUMERIC,
    atr_14 NUMERIC,
    funding_rate NUMERIC,
    fear_greed INT,
    hmm_state_probs JSONB,        -- 各状态概率分布
    cusum_up NUMERIC,              -- CUSUM 上偏累积值
    cusum_down NUMERIC,            -- CUSUM 下偏累积值
    explanation TEXT,               -- LLM 解释（仅切换时有值）
    is_transition BOOLEAN DEFAULT FALSE,
    previous_regime TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_regime_ts ON agent_regime_history(created_at DESC);
CREATE INDEX idx_regime_transition ON agent_regime_history(is_transition, created_at DESC);
```

### 存储预估

```
每 30min 写入 1 条（regime 快照）→ 48 条/天 × 0.5KB = 24KB/天
保留 30 天：~720KB/月
```

---

## 五、技术影响

| 文件 | 操作 | 说明 |
|------|------|------|
| `agent/regime_detector.py` | **新建** | CUSUM + HMM + LLM 三阶段检测 |
| `agent/risk_manager.py` | 修改 | Regime 感知参数 + ATR 仓位 + ATR 止损 + 时间衰减 + CRISIS |
| `agent/position_monitor.py` | 修改 | CRISIS 模式自动收紧止损 |
| `agent/event_listener.py` | 修改 | 订阅 regime_change 事件 |
| `agent/memory/working_memory.py` | 修改 | Regime 变化写入短期记忆 |
| `optimizer_tools.py` | 修改 | 新增 tool_read_regime_history |
| `optimizer_agent.py` | 修改 | TOOL_DEFINITIONS + TOOL_MAP +1 |
| `main.py` | 修改 | 注册 regime 检测定时任务 |
| `config.py` | 修改 | REGIME_RISK_PARAMS + ATR 配置 |
| `api/routes_agent.py` | 修改 | 新增 /api/agent/regime 端点 |
| `migrations/029_regime_history.sql` | **新建** | 1 张表 |

---

## 六、依赖

```
新增 Python 包：hmmlearn（HMM 实现，pip install hmmlearn）
  - 轻量级，纯 Python + NumPy，无 GPU 要求
  - MIT 许可证

数据源依赖：
  - BTC 1h K线：已有（Binance WS）
  - ATR_14：已有（btc_eth indicator_engine 计算）
  - 资金费率：已有（Binance REST 每 30min）
  - 恐慌指数：已有（Alternative.me 每 4h）

不需要额外数据源或 API。
```

---

## 七、Claude API 成本

| 操作 | 模型 | 频率 | 单次成本 | 月成本 |
|------|------|------|---------|--------|
| LLM Regime 解释 | Haiku | ~2 次/天（仅切换时） | ~$0.001 | ~$0.06 |
| **总新增** | | | | **~$0.06/月** |

注：CUSUM 和 HMM 都是本地计算，零 API 成本。只有 regime 切换时的 LLM 解释需要 Claude。

---

## 八、验收标准

### M9 Regime 检测器
- [ ] CUSUM 每 5min 运行，检测到价格结构变化时触发信号
- [ ] HMM 每 30min 分类，输出 7 种状态之一 + 置信度
- [ ] 状态切换时 LLM 生成解释 + 策略建议
- [ ] Regime 变化通过 EventBus 广播
- [ ] agent_regime_history 每 30min 有新记录
- [ ] 每天 UTC 04:00 HMM 自动重训练

### M8 动态风控
- [ ] CRISIS 模式：BTC 15min 跌 >5% 时自动触发，收紧所有止损至 -3%
- [ ] ATR 仓位：高波动时自动缩小仓位（atr_ratio=2 → 仓位减半）
- [ ] ATR 止损：动态计算止损价（不再固定百分比）
- [ ] 时间衰减：MEME 持仓 >8h 自动收紧止损 20%
- [ ] Regime 参数：TRENDING_DOWN 时不开新多单
- [ ] 所有动态参数可被优化 Agent 通过提案修改

### O7 Regime 审计
- [ ] 优化 Agent 可读取 regime 切换历史
- [ ] 可读取各 regime 下的交易表现对比
- [ ] 可评估检测延迟和误报率

---

## 九、风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| HMM 状态数选择不当 | 中 | 中 | 从 4 状态开始，优化 Agent 后续可调整 |
| CUSUM 假信号频繁 | 中 | 低 | 阈值 h=5σ 较保守；HMM 做第二确认 |
| CRISIS 误触发 | 低 | 高 | 需多条件同时满足（不只看价格） |
| hmmlearn 服务器安装问题 | 低 | 中 | pip install hmmlearn 通常无问题，fallback 到纯 CUSUM |
| HMM 重训练耗时 | 低 | 低 | 30 天 × 24 = 720 个数据点，训练 <1s |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-23 | 初始版本 |
