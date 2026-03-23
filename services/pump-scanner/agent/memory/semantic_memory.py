"""
长期记忆 — 规则管理 + 统计验证 + 内存缓存

PRD-005 M12:
- 最多 50 条活跃规则
- 按相关性取 Top 10 注入 prompt（不全量注入）
- 启动时加载到内存，每 5 分钟刷新
- 规则晋升：3 次反思出现 + >=5 笔样本 + 遵守胜率领先 >=15%
- 规则废弃：遵守胜率 <40%（样本>=10）或 30 天未匹配

Python 3.9 兼容。
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from database import get_db

log = logging.getLogger(__name__)

CACHE_TTL = 300  # 5min 缓存刷新
MAX_ACTIVE_RULES = 50
PROMOTE_THRESHOLD_APPEARANCES = 3
PROMOTE_THRESHOLD_SAMPLES = 5
PROMOTE_THRESHOLD_WIN_DIFF = 15  # 遵守胜率 - 违反胜率 >= 15 百分点
DEPRECATE_WIN_RATE = 40  # 遵守胜率 < 40% 废弃
DEPRECATE_SAMPLES = 10
STALE_DAYS = 30  # 30 天未匹配 → 标记待审查


class SemanticMemory:
    """长期记忆 — 规则管理 + 统计验证 + 内存缓存"""

    def __init__(self):
        self._rules: List[Dict] = []
        self._last_load: float = 0

    def _ensure_loaded(self) -> None:
        """确保规则已加载（5min 缓存）"""
        now = time.time()
        if now - self._last_load < CACHE_TTL and self._rules:
            return
        try:
            res = (
                get_db()
                .table("agent_memory")
                .select("*")
                .eq("type", "semantic")
                .eq("is_active", True)
                .order("importance", desc=True)
                .limit(MAX_ACTIVE_RULES)
                .execute()
            )
            self._rules = res.data or []
            self._last_load = now
            log.debug("[SemanticMemory] Loaded %d active rules", len(self._rules))
        except Exception as e:
            log.warning("Semantic load failed: %s", e)

    def get_relevant(
        self,
        chain: Optional[str] = None,
        trigger_source: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        按相关性取 Top N 规则

        评分 = importance + chain(+2) + trigger_source(+3)
        """
        self._ensure_loaded()
        scored = []
        for r in self._rules:
            score = float(r.get("importance", 0) or 0)
            if chain and r.get("chain") == chain:
                score += 2
            if trigger_source and r.get("trigger_source") == trigger_source:
                score += 3
            scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:limit]]

    def get_all_active(self) -> List[Dict[str, Any]]:
        """获取所有活跃规则（缓存）"""
        self._ensure_loaded()
        return list(self._rules)

    def check_compliance(self, trade_context: Dict[str, Any]) -> List[Dict]:
        """
        检查当前交易是否违反某些规则

        返回匹配到的规则列表，每项包含:
        - rule_id, condition, action, content
        """
        self._ensure_loaded()
        matched = []
        for rule in self._rules:
            sd = rule.get("structured_data") or {}
            if not isinstance(sd, dict):
                continue
            condition = sd.get("condition", "")
            action = sd.get("action", "")
            if not condition or not action:
                continue
            if self._matches_condition(condition, trade_context):
                matched.append({
                    "rule_id": rule["id"],
                    "condition": condition,
                    "action": action,
                    "content": rule.get("content", ""),
                })
        return matched

    def _matches_condition(self, condition: str, ctx: Dict[str, Any]) -> bool:
        """
        简单条件匹配（支持 AND 组合）

        condition 格式: "field op value AND field op value"
        例如: "rsi > 65 AND regime = HIGH_VOLATILITY"

        op 支持: > >= < <= =
        """
        parts = [p.strip() for p in condition.upper().split(" AND ")]
        for part in parts:
            if not self._matches_single(part, ctx):
                return False
        return True

    def _matches_single(self, part: str, ctx: Dict[str, Any]) -> bool:
        """匹配单个条件"""
        # 尝试不同的运算符（顺序重要：>= 在 > 之前）
        for op in [">=", "<=", ">", "<", "="]:
            if op in part:
                segments = part.split(op, 1)
                if len(segments) != 2:
                    continue
                field = segments[0].strip().lower()
                val = segments[1].strip().strip("'\"")
                ctx_val = ctx.get(field)
                if ctx_val is None:
                    return False
                ctx_str = str(ctx_val).upper()
                try:
                    if op == ">":
                        return float(ctx_str) > float(val)
                    elif op == ">=":
                        return float(ctx_str) >= float(val)
                    elif op == "<":
                        return float(ctx_str) < float(val)
                    elif op == "<=":
                        return float(ctx_str) <= float(val)
                    elif op == "=":
                        return ctx_str == val.upper()
                except (ValueError, TypeError):
                    if op == "=":
                        return ctx_str == val.upper()
                    return False
        return True

    def record_compliance(
        self, rule_id: str, complied: bool, won: bool
    ) -> None:
        """
        记录遵守/违反 + 盈亏

        更新 comply_win/comply_lose/violate_win/violate_lose + usage_count
        """
        field = "comply_win" if complied and won else \
                "comply_lose" if complied and not won else \
                "violate_win" if not complied and won else \
                "violate_lose"
        try:
            db = get_db()
            rule = (
                db.table("agent_memory")
                .select(f"{field}, usage_count")
                .eq("id", rule_id)
                .execute()
            )
            if rule.data:
                current_val = rule.data[0].get(field, 0) or 0
                current_usage = rule.data[0].get("usage_count", 0) or 0
                db.table("agent_memory").update({
                    field: current_val + 1,
                    "usage_count": current_usage + 1,
                    "last_used_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", rule_id).execute()
        except Exception as e:
            log.debug("Compliance record failed: %s", e)

    def try_promote(
        self,
        condition: str,
        appearances: int,
        comply_win: int,
        comply_lose: int,
        violate_win: int,
        violate_lose: int,
        metadata: Dict[str, Any],
    ) -> bool:
        """
        尝试将 episodic 规则晋升为 semantic

        晋升条件（PRD-005 v1.1）：
        - 连续 3 次反思出现相同 condition
        - 样本量 >= 5 笔交易验证
        - 遵守胜率 - 违反胜率 >= 15 百分点
        """
        total_comply = comply_win + comply_lose
        total_violate = violate_win + violate_lose
        total_samples = total_comply + total_violate

        if appearances < PROMOTE_THRESHOLD_APPEARANCES:
            log.debug("Promote skipped: appearances %d < %d", appearances, PROMOTE_THRESHOLD_APPEARANCES)
            return False
        if total_samples < PROMOTE_THRESHOLD_SAMPLES:
            log.debug("Promote skipped: samples %d < %d", total_samples, PROMOTE_THRESHOLD_SAMPLES)
            return False

        comply_wr = (comply_win / total_comply * 100) if total_comply > 0 else 0
        violate_wr = (violate_win / total_violate * 100) if total_violate > 0 else 0

        if comply_wr - violate_wr < PROMOTE_THRESHOLD_WIN_DIFF:
            log.debug(
                "Promote skipped: win diff %.1f%% < %d%%",
                comply_wr - violate_wr, PROMOTE_THRESHOLD_WIN_DIFF,
            )
            return False

        # 检查是否已有相同 condition 的 semantic 规则
        self._ensure_loaded()
        for existing in self._rules:
            sd = existing.get("structured_data") or {}
            if isinstance(sd, dict) and sd.get("condition", "").upper() == condition.upper():
                log.debug("Promote skipped: duplicate condition")
                return False

        # 检查是否达到上限
        if len(self._rules) >= MAX_ACTIVE_RULES:
            log.warning("Promote skipped: max active rules (%d) reached", MAX_ACTIVE_RULES)
            return False

        # 晋升！
        row = {
            "type": "semantic",
            "category": "rule",
            "content": metadata.get("content", condition),
            "structured_data": {
                "condition": condition,
                "action": metadata.get("action", "skip_buy"),
                "confidence": metadata.get("confidence", 0.5),
                "evidence": metadata.get("evidence", ""),
            },
            "importance": 7,
            "chain": metadata.get("chain"),
            "trigger_source": metadata.get("trigger_source"),
            "comply_win": comply_win,
            "comply_lose": comply_lose,
            "violate_win": violate_win,
            "violate_lose": violate_lose,
            "is_active": True,
        }
        try:
            get_db().table("agent_memory").insert(row).execute()
            self._last_load = 0  # 强制刷新缓存
            log.info("[SemanticMemory] Rule promoted: %s", condition)
            return True
        except Exception as e:
            log.warning("Promote failed: %s", e)
            return False

    def deprecate_stale(self) -> int:
        """
        废弃失效规则

        条件（PRD-005 v1.1）：
        - 遵守胜率 < 40%（样本 >= 10）
        - 30 天未匹配 → 标记 is_active=False
        """
        self._ensure_loaded()
        deprecated = 0
        now = datetime.now(timezone.utc)

        for rule in self._rules:
            should_deprecate = False
            reason = ""

            # 条件 1: 遵守胜率 < 40%（样本 >= 10）
            cw = rule.get("comply_win", 0) or 0
            cl = rule.get("comply_lose", 0) or 0
            total = cw + cl
            if total >= DEPRECATE_SAMPLES:
                wr = cw / total * 100
                if wr < DEPRECATE_WIN_RATE:
                    should_deprecate = True
                    reason = f"comply_win_rate={wr:.0f}% < {DEPRECATE_WIN_RATE}%"

            # 条件 2: 30 天未匹配
            if not should_deprecate:
                last_used = rule.get("last_used_at")
                if last_used:
                    try:
                        last_dt = datetime.fromisoformat(
                            str(last_used).replace("Z", "+00:00")
                        )
                        if (now - last_dt).days >= STALE_DAYS:
                            should_deprecate = True
                            reason = f"unused for {(now - last_dt).days} days"
                    except (ValueError, TypeError):
                        pass

            if should_deprecate:
                try:
                    get_db().table("agent_memory").update(
                        {"is_active": False}
                    ).eq("id", rule["id"]).execute()
                    deprecated += 1
                    log.info(
                        "[SemanticMemory] Rule deprecated (%s): %s",
                        reason, rule.get("content", "")[:60],
                    )
                except Exception:
                    pass

        if deprecated:
            self._last_load = 0  # 强制刷新缓存
        return deprecated

    def force_refresh(self) -> None:
        """强制刷新缓存"""
        self._last_load = 0
        self._ensure_loaded()
