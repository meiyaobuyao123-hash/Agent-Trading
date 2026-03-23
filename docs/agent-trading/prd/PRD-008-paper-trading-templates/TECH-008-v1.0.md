# TECH-008: Agent 模拟盘 + 策略模板 + AI 主动推荐 — 技术方案

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-008 v1.1 |
| 创建日期 | 2026-03-24 |

---

## 一、文件结构

```
services/pump-scanner/
├── agent/
│   ├── paper_engine.py              # 新建：模拟交易引擎（开仓/平仓/SL-TP检查）
│   ├── templates.py                 # 新建：5 个策略模板定义
│   └── proactive_scanner.py         # 新建：AI 主动推荐扫描器
├── api/routes_agent.py              # 修改：+6 个端点
├── main.py                          # 修改：+proactive_scanner 定时任务
└── migrations/031_agent_paper_trades.sql
```

---

## 二、paper_engine.py

```python
"""Agent 策略模拟盘引擎
- 策略创建默认 paper 模式
- 信号触发时用实时价格模拟交易（不调 DEX）
- 扣除 1.5% 模拟滑点（v1.1 Q3）
- 每 30s 检查 SL/TP（v1.1 Q1）
- 3 天后推送切换提醒（v1.1 Q2）
"""

SIMULATED_SLIPPAGE = 0.015  # 1.5% 模拟滑点
PAPER_DEFAULT_DAYS = 3
PAPER_MAX_IDLE_DAYS = 7     # 7 天无操作自动暂停

class PaperEngine:
    async def open_position(self, strategy_id, token, chain, price, amount_usd, sl_pct, tp_pct):
        """模拟开仓 — 扣除模拟滑点"""
        simulated_price = price * (1 + SIMULATED_SLIPPAGE)  # 买入滑点
        # 写入 agent_paper_trades(status=open)

    async def check_exits(self, current_prices):
        """每 30s 检查所有 open 的模拟持仓"""
        # 查 agent_paper_trades(status=open)
        # 检查 SL/TP → 模拟平仓

    async def check_reminders(self):
        """检查 3 天到期提醒 + 7 天暂停"""
        # 策略 mode=paper 且 created_at > 3天 → 推送提醒
        # 策略 mode=paper 且 created_at > 7天 且未操作 → 暂停
```

---

## 三、templates.py

```python
STRATEGY_TEMPLATES = {
    "meme_sniper": {
        "name": "MEME 早期狙击",
        "description": "pump.fun 代币 BC 5-15% + 聪明钱≥2 + score≥70",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"data_source": "pump_tokens", "field": "bc_progress", "operator": ">=", "value": 5},
                {"data_source": "pump_tokens", "field": "bc_progress", "operator": "<=", "value": 15},
                {"data_source": "pump_tokens", "field": "smart_money_count", "operator": ">=", "value": 2},
                {"data_source": "pump_tokens", "field": "score", "operator": ">=", "value": 70},
            ]
        },
        "actions": [{"type": "buy", "amount_usd": 50}],
        "filters": {"chains": ["solana"]},
        "risk_params": {"stop_loss_pct": 25, "take_profit_pct": 100},
        "cooldown_minutes": 30,
    },
    "hot_breakout": {...},
    "smart_money_follow": {...},
    "kol_sentiment": {...},
    "conservative_dca": {...},
}

def create_from_template(template_id, user_id, override=None):
    """从模板创建策略（v1.1 Q4: 支持参数覆盖）"""
    template = STRATEGY_TEMPLATES[template_id].copy()
    if override:
        if "amount_usd" in override:
            template["actions"][0]["amount_usd"] = override["amount_usd"]
        if "stop_loss_pct" in override:
            template["risk_params"]["stop_loss_pct"] = override["stop_loss_pct"]
        # ... 其他可覆盖参数
    template["mode"] = "paper"  # 默认模拟盘
    return strategy_manager.create_strategy(template, user_id)
```

---

## 四、proactive_scanner.py

```python
"""AI 主动推荐扫描器 — 每 4h 发现高价值机会推送给用户"""

MAX_DAILY_RECOMMENDATIONS = 5
RECOMMENDATION_COOLDOWN_24H = set()  # 24h 内已推荐的代币

async def scan_opportunities():
    """v1.1 Q5: 推荐前 5 项质量过滤"""
    opportunities = []

    # 1. 聪明钱集中买入
    signals = db.table("smart_money_signals").select("*") \
        .gte("elite_buy_count", 2).gte("detected_at", cutoff_2h).execute()
    for sig in signals.data:
        if _passes_quality_filter(sig) and not _conflicts_with_user_strategies(sig):
            opportunities.append(sig)

    # 2. 热币 score 飙升
    # 3. KOL 共振

    # 推送 Top N
    for opp in opportunities[:MAX_DAILY_RECOMMENDATIONS]:
        push_recommendation(opp)

def _passes_quality_filter(token_data):
    """v1.1 Q5: 5 项质量过滤"""
    return (
        token_data.get("score", 0) >= 50 and
        token_data.get("liquidity_usd", 0) >= 30000 and
        not token_data.get("goplus_risk", False) and
        token_data.get("volume_24h_usd", 0) >= 10000
    )

def _conflicts_with_user_strategies(token_data):
    """v1.1 Q7: 检查已有策略冲突"""
    # 查用户活跃策略的 data_sources
    # 如果已有 smart_money 类型策略 → 不推荐聪明钱信号
```

---

## 五、API 端点

| Method | Path | 说明 |
|--------|------|------|
| GET | /api/agent/paper-trades | 模拟交易记录 |
| GET | /api/agent/paper-stats/{strategy_id} | 模拟盘统计 |
| POST | /api/agent/strategies/{id}/go-live | 切换到实盘 |
| GET | /api/agent/templates | 模板列表 |
| POST | /api/agent/templates/{id}/create | 从模板创建（支持 override） |
| GET | /api/agent/compare/{strategy_id} | 模拟盘 vs 实盘对比（v1.1 Q6） |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-24 | 初始版本（含 v1.1 审查修订） |
