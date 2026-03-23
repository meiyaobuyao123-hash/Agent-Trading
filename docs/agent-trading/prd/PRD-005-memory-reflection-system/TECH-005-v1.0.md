# TECH-005: 记忆与反思系统 — 技术方案

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-005 v1.1 |
| 创建日期 | 2026-03-23 |

---

## 一、文件结构

```
services/pump-scanner/
├── agent/
│   ├── memory/                          # 新增目录
│   │   ├── __init__.py                  # MemoryManager 统一接口
│   │   ├── working_memory.py            # 短期记忆（内存 deque，24h 滑动窗口）
│   │   ├── episodic_memory.py           # 中期记忆（DB CRUD + 相关性检索）
│   │   ├── semantic_memory.py           # 长期记忆（规则管理 + 统计验证 + 缓存）
│   │   └── reflection.py               # 反思引擎（Claude Sonnet 结构化输出）
│   ├── event_listener.py               # 修改：写入短期记忆
│   ├── action_dispatcher.py            # 修改：写入记忆 + 规则合规检查
│   ├── position_monitor.py             # 修改：止盈止损后写入中期
│   ├── risk_manager.py                 # 修改：block/warn 写入 risk_events
│   ├── strategy_manager.py             # 修改：自动推断 strategy_type
│   └── llm_parser.py                   # 修改：prompt 注入记忆
├── optimizer_tools.py                   # 修改：+2 个工具
├── optimizer_agent.py                   # 修改：TOOL_DEFINITIONS +2
├── main.py                              # 修改：注册反思 + 回填任务
├── db_cleanup.py                        # 修改：risk_events 30天清理
└── supabase/migrations/
    └── 028_agent_memory.sql             # 新增：2 张表
```

---

## 二、核心模块实现

### 2.1 working_memory.py

```python
"""短期记忆 — 24h 滑动窗口，内存存储"""
import time
from collections import deque
from typing import List, Dict, Any

MAX_ITEMS = 200
WINDOW_SEC = 86400  # 24h

class WorkingMemory:
    def __init__(self):
        self._events: deque = deque(maxlen=MAX_ITEMS)

    def add(self, event: Dict[str, Any]) -> None:
        event["_ts"] = time.time()
        self._events.append(event)

    def get_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        now = time.time()
        # 过滤 24h 内 + 取最近 n 条
        valid = [e for e in self._events if now - e.get("_ts", 0) < WINDOW_SEC]
        return list(valid)[-n:]

    def size(self) -> int:
        return len(self._events)
```

### 2.2 episodic_memory.py

```python
"""中期记忆 — DB 存储，相关性检索"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from database import get_db

log = logging.getLogger(__name__)

# 不同 category 的过期天数
EXPIRY_DAYS = {
    "trade_review": 14,
    "market_pattern": 30,
    "risk_lesson": 30,
}

class EpisodicMemory:
    def __init__(self):
        self._cache: List[Dict] = []
        self._cache_ts: float = 0
        self._cache_ttl: float = 30.0  # 30s 缓存

    def add(self, memory: Dict[str, Any]) -> Optional[str]:
        """写入一条中期记忆"""
        category = memory.get("category", "trade_review")
        expiry_days = EXPIRY_DAYS.get(category, 14)
        row = {
            "type": "episodic",
            "category": category,
            "content": memory.get("content", ""),
            "structured_data": memory.get("structured_data"),
            "importance": memory.get("importance", 5),
            "chain": memory.get("chain"),
            "token_type": memory.get("token_type"),
            "trigger_source": memory.get("trigger_source"),
            "mcap_bucket": memory.get("mcap_bucket"),
            "market_regime": memory.get("market_regime"),
            "is_active": True,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=expiry_days)).isoformat(),
        }
        try:
            res = get_db().table("agent_memory").insert(row).execute()
            return res.data[0]["id"] if res.data else None
        except Exception as e:
            log.warning("Episodic write failed: %s", e)
            return None

    def search(self, chain: str = None, trigger_source: str = None,
               mcap_bucket: str = None, regime: str = None,
               limit: int = 3) -> List[Dict[str, Any]]:
        """按相关性检索 Top N"""
        import time as _t
        now = _t.time()
        if now - self._cache_ts < self._cache_ttl and self._cache:
            candidates = self._cache
        else:
            try:
                res = get_db().table("agent_memory").select("*") \
                    .eq("type", "episodic").eq("is_active", True) \
                    .order("created_at", desc=True).limit(100).execute()
                candidates = res.data or []
                self._cache = candidates
                self._cache_ts = now
            except Exception as e:
                log.warning("Episodic search failed: %s", e)
                return []

        # 相关性打分
        scored = []
        for m in candidates:
            score = 0
            if chain and m.get("chain") == chain:
                score += 2
            if regime and m.get("market_regime") == regime:
                score += 2
            if trigger_source and m.get("trigger_source") == trigger_source:
                score += 3  # 最重要
            if mcap_bucket and m.get("mcap_bucket") == mcap_bucket:
                score += 2
            sd = m.get("structured_data") or {}
            if abs(sd.get("pnl_pct", 0)) > 20:
                score += 1
            scored.append((score, m))

        scored.sort(key=lambda x: (-x[0], x[1].get("created_at", "")))
        return [m for _, m in scored[:limit]]

    def cleanup_expired(self) -> int:
        """清理过期记忆"""
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            res = get_db().table("agent_memory").delete() \
                .eq("type", "episodic").lt("expires_at", now_iso).execute()
            return len(res.data) if res.data else 0
        except Exception:
            return 0
```

### 2.3 semantic_memory.py

```python
"""长期记忆 — 规则管理 + 统计验证 + 内存缓存"""
import logging
import time
from typing import List, Dict, Any, Optional
from database import get_db

log = logging.getLogger(__name__)

CACHE_TTL = 300  # 5min 缓存刷新
MAX_ACTIVE_RULES = 50
PROMOTE_THRESHOLD_APPEARANCES = 3
PROMOTE_THRESHOLD_SAMPLES = 5
PROMOTE_THRESHOLD_WIN_DIFF = 15  # 遵守胜率 - 违反胜率 >= 15%
DEPRECATE_WIN_RATE = 40  # 遵守胜率 < 40% 废弃
DEPRECATE_SAMPLES = 10

class SemanticMemory:
    def __init__(self):
        self._rules: List[Dict] = []
        self._last_load: float = 0

    def _ensure_loaded(self):
        now = time.time()
        if now - self._last_load < CACHE_TTL and self._rules:
            return
        try:
            res = get_db().table("agent_memory").select("*") \
                .eq("type", "semantic").eq("is_active", True) \
                .order("importance", desc=True).limit(MAX_ACTIVE_RULES).execute()
            self._rules = res.data or []
            self._last_load = now
        except Exception as e:
            log.warning("Semantic load failed: %s", e)

    def get_relevant(self, chain: str = None, trigger_source: str = None,
                     limit: int = 10) -> List[Dict[str, Any]]:
        """按相关性取 Top N 规则"""
        self._ensure_loaded()
        scored = []
        for r in self._rules:
            score = r.get("importance", 0)
            if chain and r.get("chain") == chain:
                score += 2
            if trigger_source and r.get("trigger_source") == trigger_source:
                score += 3
            scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:limit]]

    def check_compliance(self, trade_context: Dict) -> List[Dict]:
        """检查当前交易是否违反规则，返回匹配的规则"""
        self._ensure_loaded()
        matched = []
        for rule in self._rules:
            sd = rule.get("structured_data") or {}
            condition = sd.get("condition", "")
            action = sd.get("action", "")
            if not condition or not action:
                continue
            if self._matches_condition(condition, trade_context):
                matched.append({"rule_id": rule["id"], "condition": condition,
                                "action": action, "content": rule.get("content", "")})
        return matched

    def _matches_condition(self, condition: str, ctx: Dict) -> bool:
        """简单条件匹配（支持 AND 组合）"""
        # condition 格式："rsi > 65 AND regime = HIGH_VOLATILITY"
        parts = [p.strip() for p in condition.upper().split(" AND ")]
        for part in parts:
            for op in [">=", "<=", ">", "<", "="]:
                if op in part:
                    field, val = part.split(op, 1)
                    field = field.strip().lower()
                    val = val.strip().strip("'\"")
                    ctx_val = str(ctx.get(field, "")).upper()
                    try:
                        if op == ">" and not (float(ctx_val) > float(val)):
                            return False
                        elif op == ">=" and not (float(ctx_val) >= float(val)):
                            return False
                        elif op == "<" and not (float(ctx_val) < float(val)):
                            return False
                        elif op == "<=" and not (float(ctx_val) <= float(val)):
                            return False
                        elif op == "=" and ctx_val != val:
                            return False
                    except (ValueError, TypeError):
                        if op == "=" and ctx_val != val:
                            return False
                    break
        return True

    def record_compliance(self, rule_id: str, complied: bool, won: bool) -> None:
        """记录遵守/违反 + 盈亏"""
        field = f"{'comply' if complied else 'violate'}_{'win' if won else 'lose'}"
        try:
            # 原子递增
            from database import get_db
            rule = get_db().table("agent_memory").select(field).eq("id", rule_id).execute()
            if rule.data:
                get_db().table("agent_memory").update({
                    field: (rule.data[0].get(field, 0) or 0) + 1,
                    "last_used_at": "now()",
                    "usage_count": (rule.data[0].get("usage_count", 0) or 0) + 1,
                }).eq("id", rule_id).execute()
        except Exception as e:
            log.debug("Compliance record failed: %s", e)

    def try_promote(self, condition: str, appearances: int,
                    comply_win: int, comply_lose: int,
                    violate_win: int, violate_lose: int,
                    metadata: Dict) -> bool:
        """尝试将 episodic 规则晋升为 semantic"""
        total_comply = comply_win + comply_lose
        total_violate = violate_win + violate_lose
        total_samples = total_comply + total_violate

        if appearances < PROMOTE_THRESHOLD_APPEARANCES:
            return False
        if total_samples < PROMOTE_THRESHOLD_SAMPLES:
            return False

        comply_wr = comply_win / total_comply * 100 if total_comply > 0 else 0
        violate_wr = violate_win / total_violate * 100 if total_violate > 0 else 0

        if comply_wr - violate_wr < PROMOTE_THRESHOLD_WIN_DIFF:
            return False

        # 晋升！
        row = {
            "type": "semantic",
            "category": "rule",
            "content": metadata.get("content", condition),
            "structured_data": {"condition": condition, "action": metadata.get("action", "skip_buy"),
                                "confidence": metadata.get("confidence", 0.5),
                                "evidence": metadata.get("evidence", "")},
            "importance": 7,
            "chain": metadata.get("chain"),
            "trigger_source": metadata.get("trigger_source"),
            "comply_win": comply_win, "comply_lose": comply_lose,
            "violate_win": violate_win, "violate_lose": violate_lose,
            "is_active": True,
        }
        try:
            get_db().table("agent_memory").insert(row).execute()
            self._last_load = 0  # 强制刷新缓存
            log.info("[Semantic] Rule promoted: %s", condition)
            return True
        except Exception as e:
            log.warning("Promote failed: %s", e)
            return False

    def deprecate_stale(self) -> int:
        """废弃失效规则"""
        self._ensure_loaded()
        deprecated = 0
        for rule in self._rules:
            cw = rule.get("comply_win", 0) or 0
            cl = rule.get("comply_lose", 0) or 0
            total = cw + cl
            if total >= DEPRECATE_SAMPLES:
                wr = cw / total * 100
                if wr < DEPRECATE_WIN_RATE:
                    try:
                        get_db().table("agent_memory").update({"is_active": False}) \
                            .eq("id", rule["id"]).execute()
                        deprecated += 1
                        log.info("[Semantic] Rule deprecated (wr=%.0f%%): %s",
                                 wr, rule.get("content", "")[:50])
                    except Exception:
                        pass
        if deprecated:
            self._last_load = 0
        return deprecated
```

### 2.4 reflection.py

```python
"""反思引擎 — Claude Sonnet 结构化分析"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

log = logging.getLogger(__name__)

REFLECTION_MODEL = "claude-sonnet-4-20250514"
MAX_EMERGENCY_PER_DAY = 2
EMERGENCY_LOSS_PCT = 25
EMERGENCY_LOSS_MIN_USD = 30

REFLECTION_PROMPT = """你是一个加密货币交易复盘专家。分析以下交易记录，输出 JSON：

交易记录：
{trades_json}

当前活跃规则：
{active_rules}

请输出严格 JSON 格式（不要 markdown）：
{{
  "winning_pattern": "赢钱交易的共同特征（1-2句话）",
  "losing_pattern": "亏钱交易的共同原因（1-2句话）",
  "new_rules": [
    {{
      "condition": "field op value AND field op value",
      "action": "skip_buy | reduce_position | tighten_stop",
      "confidence": 0.5-1.0,
      "evidence": "基于哪些交易得出的"
    }}
  ],
  "deprecated_rule_ids": ["rule_id_1"],
  "summary": "一句话总结"
}}

规则：
- condition 格式必须是 "field op value"，field 用小写（如 rsi, regime, trigger_source, hold_hours）
- op 只能用 > >= < <= =
- 最多输出 3 条 new_rules
- 只在有充分证据时才输出 deprecated_rule_ids"""


class ReflectionEngine:
    def __init__(self):
        self._emergency_count_today: int = 0
        self._last_reset_date: str = ""
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")

    async def run_reflection(self, trades: List[Dict], active_rules: List[Dict],
                              is_emergency: bool = False) -> Optional[Dict]:
        """执行一次反思"""
        if not self._api_key:
            log.warning("No API key for reflection")
            return None

        # 紧急反思冷却
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            self._emergency_count_today = 0
            self._last_reset_date = today

        if is_emergency:
            if self._emergency_count_today >= MAX_EMERGENCY_PER_DAY:
                log.info("Emergency reflection skipped: daily limit reached")
                return None
            self._emergency_count_today += 1

        # 构造 prompt
        trades_text = json.dumps(trades[:10], ensure_ascii=False, indent=2, default=str)
        rules_text = json.dumps(
            [{"id": r.get("id", ""), "content": r.get("content", ""),
              "condition": (r.get("structured_data") or {}).get("condition", "")}
             for r in active_rules[:20]],
            ensure_ascii=False, indent=2
        )
        prompt = REFLECTION_PROMPT.format(trades_json=trades_text, active_rules=rules_text)

        # 调用 Claude
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self._api_key)
            response = await asyncio.to_thread(
                client.messages.create,
                model=REFLECTION_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            # 清理可能的 markdown 包裹
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(text)
            log.info("[Reflection] Done: %d new rules, summary: %s",
                     len(result.get("new_rules", [])), result.get("summary", "")[:60])
            return result
        except json.JSONDecodeError as e:
            log.warning("Reflection JSON parse failed: %s", e)
            return None
        except Exception as e:
            log.error("Reflection failed: %s", e)
            return None

    def should_emergency_reflect(self, pnl_pct: float, amount_usd: float) -> bool:
        """判断是否需要紧急反思"""
        return (pnl_pct <= -EMERGENCY_LOSS_PCT and
                amount_usd >= EMERGENCY_LOSS_MIN_USD)
```

### 2.5 memory/__init__.py

```python
"""MemoryManager — 统一接口"""
import logging
from typing import Dict, Any, List, Optional

from .working_memory import WorkingMemory
from .episodic_memory import EpisodicMemory
from .semantic_memory import SemanticMemory
from .reflection import ReflectionEngine

log = logging.getLogger(__name__)


class MemoryManager:
    def __init__(self):
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.reflection = ReflectionEngine()

    def add_event(self, event: Dict[str, Any]) -> None:
        """写入短期记忆"""
        self.working.add(event)

    def add_trade_review(self, review: Dict[str, Any]) -> Optional[str]:
        """写入中期记忆（交易复盘）"""
        review["category"] = review.get("category", "trade_review")
        return self.episodic.add(review)

    def get_context_for_decision(self, chain: str, token_address: str,
                                  trigger_source: str, market_cap_usd: float,
                                  market_regime: str) -> Dict[str, Any]:
        """获取决策上下文（注入 prompt 用）"""
        mcap_bucket = _mcap_bucket(market_cap_usd)
        return {
            "short_term": self.working.get_recent(10),
            "episodic": self.episodic.search(
                chain=chain, trigger_source=trigger_source,
                mcap_bucket=mcap_bucket, regime=market_regime, limit=3
            ),
            "semantic": self.semantic.get_relevant(
                chain=chain, trigger_source=trigger_source, limit=10
            ),
        }

    def check_rules(self, trade_context: Dict) -> List[Dict]:
        """检查交易是否违反规则"""
        return self.semantic.check_compliance(trade_context)

    def format_for_prompt(self, context: Dict) -> str:
        """将记忆格式化为 prompt 文本"""
        lines = []

        # 短期
        st = context.get("short_term", [])
        if st:
            lines.append("【短期记忆（最近24h事件）】")
            for e in st:
                lines.append(f"- {e.get('summary', str(e)[:80])}")

        # 中期
        ep = context.get("episodic", [])
        if ep:
            lines.append("\n【近期经验（相关交易复盘）】")
            for m in ep:
                lines.append(f"- {m.get('content', '')[:100]}")

        # 长期
        sem = context.get("semantic", [])
        if sem:
            lines.append("\n【交易规则（已验证）】")
            for r in sem:
                sd = r.get("structured_data") or {}
                cw = r.get("comply_win", 0) or 0
                cl = r.get("comply_lose", 0) or 0
                total = cw + cl
                wr = f"{cw/total*100:.0f}%" if total > 0 else "N/A"
                lines.append(f"- Rule: {sd.get('condition','')} → {sd.get('action','')}（遵守胜率{wr}，样本{total}笔）")

        return "\n".join(lines)


def _mcap_bucket(mcap: float) -> str:
    if mcap < 100_000:
        return "<100K"
    elif mcap < 1_000_000:
        return "100K-1M"
    elif mcap < 10_000_000:
        return "1M-10M"
    else:
        return ">10M"


# 全局单例
_manager: Optional[MemoryManager] = None

def get_memory_manager() -> MemoryManager:
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager
```

---

## 三、现有模块修改

### 3.1 event_listener.py — 写入短期记忆

```python
# 在 _on_hot_coin_event / _on_pump_event / _on_kol_event 中添加：
from agent.memory import get_memory_manager

def _on_hot_coin_event(event):
    memory = get_memory_manager()
    memory.add_event({
        "type": "signal",
        "source": "hot_coin",
        "token": event.data.get("symbol", ""),
        "chain": event.data.get("chain", ""),
        "score": event.data.get("score", 0),
        "price": event.data.get("price_usd", 0),
        "summary": f"{event.data.get('symbol','')} score={event.data.get('score',0)} ${event.data.get('price_usd',0):.6f}",
    })
    # ... 原有逻辑
```

### 3.2 action_dispatcher.py — 写入记忆 + 规则合规检查

```python
# _handle_trade() 中，风控检查前加规则合规检查：

async def _handle_trade(self, event, action, risk_params):
    memory = get_memory_manager()

    # 规则合规检查（warn only，不 block）
    trade_ctx = {
        "chain": event.chain,
        "trigger_source": event.source,
        "rsi": event.data.get("rsi", 50),
        "regime": event.data.get("market_regime", "unknown"),
        # ... 其他字段
    }
    violations = memory.check_rules(trade_ctx)
    for v in violations:
        log.warning("[Memory] Rule violation: %s → %s", v["condition"], v["action"])
        memory.add_event({"type": "rule_violation", "rule": v["condition"],
                          "token": event.token_name, "summary": f"违反规则: {v['condition']}"})

    # ... 原有风控检查 + 执行逻辑 ...

    # 交易完成后写入记忆
    if result.success:
        memory.add_event({
            "type": "trade",
            "action": action_type,
            "token": event.token_name,
            "chain": event.chain,
            "amount_usd": amount_usd,
            "price": result.price,
            "summary": f"{'买入' if action_type=='buy' else '卖出'} {event.token_name} ${amount_usd:.0f}",
        })
```

### 3.3 position_monitor.py — 止盈止损后写入中期

```python
# _execute_exit() 成功后：

memory = get_memory_manager()
memory.add_trade_review({
    "content": f"{pos.token_address[:10]} {trigger}: entry=${pos.entry_price:.6f} exit=${exit_price:.6f} pnl={pnl_pct:+.1f}%",
    "structured_data": {
        "token": pos.token_address,
        "chain": pos.chain,
        "entry_price": pos.entry_price,
        "exit_price": exit_price,
        "pnl_pct": pnl_pct,
        "hold_seconds": (datetime.now(timezone.utc) - created_at).total_seconds(),
        "exit_trigger": trigger,
    },
    "chain": pos.chain,
    "importance": min(10, abs(pnl_pct) / 5),  # 盈亏越大越重要
    "trigger_source": "position_monitor",
})

# 紧急反思检查
if memory.reflection.should_emergency_reflect(pnl_pct, pos.amount_usd):
    asyncio.create_task(_trigger_emergency_reflection())
```

### 3.4 risk_manager.py — 写入 risk_events

```python
# check_trade() 中，每次 block 或 warn 时：

def _record_risk_event(self, action: str, reason: str, chain: str,
                        token_address: str, token_symbol: str,
                        amount_usd: float, risk_data: dict):
    try:
        get_db().table("agent_risk_events").insert({
            "action": action,  # 'block' | 'warn'
            "reason": reason,
            "chain": chain,
            "token_address": token_address,
            "token_symbol": token_symbol,
            "amount_usd": amount_usd,
            "risk_data": risk_data,
            "token_price_at_event": risk_data.get("price_usd", 0),
        }).execute()
    except Exception as e:
        log.debug("Risk event record failed: %s", e)
```

### 3.5 strategy_manager.py — 自动推断 strategy_type

```python
# create_strategy() 中新增：

def _infer_strategy_type(self, conditions: dict, data_sources: list) -> str:
    cond_str = json.dumps(conditions).lower()
    if "smart_money" in cond_str:
        return "smart_money_follow"
    if "kol" in cond_str or "kol_mentions" in str(data_sources):
        return "kol_mention"
    if "hot_coins" in str(data_sources):
        if "price_change" in cond_str:
            return "hot_breakout"
        return "hot_score"
    if "pump_tokens" in str(data_sources):
        return "pump_early"
    return "custom"
```

### 3.6 optimizer_tools.py — 新增 2 个工具

```python
# 新增 tool_read_agent_performance() 和 tool_read_risk_events()
# 完整实现参考 PRD-005 3.3 和 3.4 节的返回格式
# 在 HOT_TOOL_DEFINITIONS 和 TOOL_MAP 中注册
```

---

## 四、定时任务注册（main.py）

```python
# 每日 UTC 20:00 反思
scheduler.add_job(run_daily_reflection, CronTrigger(hour=20, minute=0, timezone="UTC"),
                  name="Daily Reflection", max_instances=1)

# 每 6h 回填 risk_events 的 24h 价格
scheduler.add_job(backfill_risk_events, IntervalTrigger(hours=6),
                  name="Risk Events Backfill", max_instances=1)
```

---

## 五、Migration SQL

见 PRD-005 四、数据库设计（2 张表 + 索引）

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-23 | 初始版本 |
