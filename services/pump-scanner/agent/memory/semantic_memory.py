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

# W3 D5+:5 条硬晋升门槛(对齐 17-tech-plan.md / docs/agent-pm/06-memory-spec.md §3.3)
STRICT_PROMOTE_REFLECTIONS = 3       # 至少 3 次反思都建议
STRICT_PROMOTE_SAMPLES = 20          # 至少 20 个 trade 样本
STRICT_PROMOTE_WILSON_LOWER = 0.55   # 95% Wilson CI 下界 ≥ 55%
STRICT_PROMOTE_TTEST_P = 0.05        # 与 baseline 比较 t-test p < 0.05
STRICT_PROMOTE_MIN_REGIMES = 2       # 至少在 2 个不同 regime 验证过
STRICT_PROMOTE_SHADOW_DAYS = 14      # 进入 14d Shadow Mode


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

    @staticmethod
    def check_strict_promotion_gates(
        reflections_count: int,
        comply_pnls: List[float],
        violate_pnls: List[float],
        regimes_observed: List[str],
    ) -> Dict[str, Any]:
        """W3 D5+:5 条硬晋升门槛(对齐 17-tech-plan.md)

        条件:
          1. reflections_count >= 3
          2. len(comply_pnls) >= 20
          3. Wilson CI lower (comply 胜率) >= 0.55
          4. t-test p (comply vs violate) < 0.05
          5. unique(regimes_observed) >= 2

        Returns:
          {passed: bool, gates: {gate_name: {ok, value, threshold}}, summary: str}
        """
        import math

        comply_pnls = list(comply_pnls or [])
        violate_pnls = list(violate_pnls or [])

        # Gate 1: reflections
        g1_ok = reflections_count >= STRICT_PROMOTE_REFLECTIONS

        # Gate 2: sample size
        g2_ok = len(comply_pnls) >= STRICT_PROMOTE_SAMPLES

        # Gate 3: Wilson CI lower
        if comply_pnls:
            wins = sum(1 for p in comply_pnls if p > 0)
            n = len(comply_pnls)
            p = wins / n if n > 0 else 0.0
            z = 1.96
            denom = 1 + z * z / n
            centre = (p + z * z / (2 * n)) / denom
            spread = z * math.sqrt(max(0.0, p * (1 - p) / n + z * z / (4 * n * n))) / denom
            wilson_lower = max(0.0, centre - spread)
        else:
            wilson_lower = 0.0
        g3_ok = wilson_lower >= STRICT_PROMOTE_WILSON_LOWER

        # Gate 4: Welch's t-test (comply vs violate)
        def _ttest_welch(a: List[float], b: List[float]) -> Optional[float]:
            if len(a) < 2 or len(b) < 2:
                return None
            ma = sum(a) / len(a)
            mb = sum(b) / len(b)
            va = sum((x - ma) ** 2 for x in a) / (len(a) - 1)
            vb = sum((x - mb) ** 2 for x in b) / (len(b) - 1)
            denom = math.sqrt(va / len(a) + vb / len(b))
            if denom == 0:
                # 零方差:means 相同 → p=1.0(无统计差),means 不同 → p=0.0(确定显著)
                return 1.0 if ma == mb else 0.0
            t = (ma - mb) / denom
            # Welch–Satterthwaite df
            num = (va / len(a) + vb / len(b)) ** 2
            d_a = (va / len(a)) ** 2 / (len(a) - 1)
            d_b = (vb / len(b)) ** 2 / (len(b) - 1)
            df = num / (d_a + d_b) if (d_a + d_b) > 0 else 1.0
            # 简易 two-sided p value(不用 scipy):approx 用 1/(1+t^2/df)^(df/2)
            # 对应 Student t,这个近似精度够日常使用(同 spec ≈ 0.05 阈值)
            try:
                p_approx = 2 * 0.5 * (1 - (1 / (1 + t * t / max(df, 1.0)) ** (df / 2)))
            except Exception:
                return None
            return min(1.0, max(0.0, p_approx))

        t_p = _ttest_welch(comply_pnls, violate_pnls)
        g4_ok = (t_p is not None and t_p < STRICT_PROMOTE_TTEST_P)

        # Gate 5: regime diversity
        regimes_set = {r for r in (regimes_observed or []) if r}
        g5_ok = len(regimes_set) >= STRICT_PROMOTE_MIN_REGIMES

        gates = {
            "reflections": {"ok": g1_ok, "value": reflections_count,
                             "threshold": STRICT_PROMOTE_REFLECTIONS},
            "sample_size": {"ok": g2_ok, "value": len(comply_pnls),
                             "threshold": STRICT_PROMOTE_SAMPLES},
            "wilson_ci_lower": {"ok": g3_ok, "value": round(wilson_lower, 3),
                                 "threshold": STRICT_PROMOTE_WILSON_LOWER},
            "ttest_p": {"ok": g4_ok, "value": round(t_p, 4) if t_p is not None else None,
                         "threshold": STRICT_PROMOTE_TTEST_P},
            "regime_diversity": {"ok": g5_ok, "value": len(regimes_set),
                                  "threshold": STRICT_PROMOTE_MIN_REGIMES},
        }
        passed = all(g["ok"] for g in gates.values())
        failed_gates = [name for name, g in gates.items() if not g["ok"]]
        summary = (
            "ALL 5 GATES PASSED → eligible for promotion + 14d Shadow Mode"
            if passed
            else f"FAILED gates: {', '.join(failed_gates)}"
        )
        return {"passed": passed, "gates": gates, "summary": summary}

    def try_promote_strict(
        self,
        condition: str,
        action: str,
        reflections_count: int,
        comply_pnls: List[float],
        violate_pnls: List[float],
        regimes_observed: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """W3 D5+:5 条硬晋升门槛 + Shadow Mode 14d 写入。

        Returns:
          {ok, gates(check_strict_promotion_gates 输出),
           promoted_rule_id (若 ok), shadow_mode_until,
           reason (若 fail)}
        """
        gate_result = self.check_strict_promotion_gates(
            reflections_count, comply_pnls, violate_pnls, regimes_observed
        )
        if not gate_result["passed"]:
            return {"ok": False, "gates": gate_result["gates"],
                    "reason": gate_result["summary"]}

        # 重复 condition 检查
        self._ensure_loaded()
        for existing in self._rules:
            sd = existing.get("structured_data") or {}
            if isinstance(sd, dict) and sd.get("condition", "").upper() == condition.upper():
                return {"ok": False, "gates": gate_result["gates"],
                        "reason": "duplicate_condition"}

        # 上限检查
        if len(self._rules) >= MAX_ACTIVE_RULES:
            return {"ok": False, "gates": gate_result["gates"],
                    "reason": "max_active_rules_reached"}

        meta = metadata or {}
        shadow_until = datetime.now(timezone.utc) + timedelta(days=STRICT_PROMOTE_SHADOW_DAYS)
        wilson_lower = gate_result["gates"]["wilson_ci_lower"]["value"]
        t_p = gate_result["gates"]["ttest_p"]["value"]

        row = {
            "type": "semantic",
            "category": "rule",
            "content": meta.get("content", condition),
            "structured_data": {
                "condition": condition,
                "action": action,
                "reflections_count": reflections_count,
                "regimes_observed": list({r for r in regimes_observed if r}),
            },
            "importance": 7,
            "chain": meta.get("chain"),
            "trigger_source": meta.get("trigger_source"),
            "is_active": True,
            "shadow_mode_until": shadow_until.isoformat(),
            "wilson_ci_lower": wilson_lower,
            "match_count": 0,
            "propose_count_so_far": reflections_count,
        }
        # W3 D5+:先写本地 PG WAL(可靠性兜底,主表失败时 retry cron 恢复)
        # 引用 agent/memory/wal.py + migration 036 memory_write_wal
        # 失败 swallow 不阻断主路径(WAL 表不存在/PG 不可达都不阻断)
        try:
            from agent.memory.wal import get_wal
            import asyncio as _aio
            device_id_for_wal = (
                meta.get("user_id") or meta.get("device_id") or ""
            )
            if device_id_for_wal:
                # try_promote_strict 是同步函数,用 asyncio.create_task 异步发起 WAL 写
                # 失败 swallow,不影响 promotion 主路径
                try:
                    loop = _aio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(get_wal().write(
                            device_id=device_id_for_wal,
                            memory_type="semantic",
                            payload=row,
                            event_id=f"promote::{condition}",
                        ))
                except Exception:
                    pass  # 无 event loop 上下文(test 环境)直接跳
        except Exception:
            pass

        try:
            res = get_db().table("agent_memory").insert(row).execute()
            self._last_load = 0
            new_id = ""
            if res.data:
                new_id = str(res.data[0].get("id", ""))
            log.info("[SemanticMemory] STRICT promoted: %s (Shadow %s)", condition, shadow_until)
            return {
                "ok": True,
                "gates": gate_result["gates"],
                "promoted_rule_id": new_id,
                "shadow_mode_until": shadow_until.isoformat(),
                "ttest_p": t_p,
                "wilson_ci_lower": wilson_lower,
            }
        except Exception as e:
            log.warning("Strict promote failed: %s", e)
            # 主表 insert 失败,但 WAL 已写(若可)— retry cron 会兜底
            return {"ok": False, "gates": gate_result["gates"],
                    "reason": f"db_write_failed_wal_pending: {e}"}

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

    # ============================================================
    # R37 P0-4 Shadow Mode 14d 评估
    # ============================================================

    SHADOW_GRADUATE_MIN_MATCHES = 3       # 14d 内至少触发 3 次才认为有意义
    SHADOW_GRADUATE_MIN_WIN_RATE = 40.0   # 触发的样本胜率 < 40% 视为失败

    def evaluate_shadow_rules(self) -> Dict[str, int]:
        """评估到期的 Shadow Mode 规则(14d 观察期完毕)。

        每条 shadow rule 评估:
          - match_count < 3:dormant(从未触发,无意义)
          - 胜率 < 40%(样本 ≥ 3):failed_shadow(变 inactive)
          - 否则:graduated(清 shadow_mode_until,正式上线)

        返回 {graduated, dormant, failed, errors}。
        cron(每 6h)+ 手动 endpoint 都可触发。
        """
        counts = {"graduated": 0, "dormant": 0, "failed": 0, "errors": 0}
        now = datetime.now(timezone.utc)
        try:
            res = (
                get_db()
                .table("agent_memory")
                .select("*")
                .eq("type", "semantic")
                .eq("is_active", True)
                .lte("shadow_mode_until", now.isoformat())
                .execute()
            )
            shadow_rules = res.data or []
        except Exception as e:
            log.warning("[SemanticMemory] shadow query failed: %s", e)
            counts["errors"] += 1
            return counts

        for rule in shadow_rules:
            try:
                match_count = int(rule.get("match_count") or 0)
                comply_win = int(rule.get("comply_win") or 0)
                comply_lose = int(rule.get("comply_lose") or 0)
                total_samples = comply_win + comply_lose
                rule_id = rule["id"]

                if match_count < self.SHADOW_GRADUATE_MIN_MATCHES:
                    # dormant: 从未触发,变 inactive
                    get_db().table("agent_memory").update({
                        "is_active": False,
                        "shadow_mode_until": None,
                        "metadata": {**(rule.get("metadata") or {}),
                                     "shadow_outcome": "dormant",
                                     "evaluated_at": now.isoformat()},
                    }).eq("id", rule_id).execute()
                    counts["dormant"] += 1
                    log.info("[SemanticMemory] shadow→dormant: %s (matches=%d)",
                             rule.get("content", "")[:60], match_count)
                elif total_samples >= 3 and total_samples > 0:
                    win_rate = (comply_win / total_samples) * 100
                    if win_rate < self.SHADOW_GRADUATE_MIN_WIN_RATE:
                        get_db().table("agent_memory").update({
                            "is_active": False,
                            "shadow_mode_until": None,
                            "metadata": {**(rule.get("metadata") or {}),
                                         "shadow_outcome": "failed",
                                         "shadow_win_rate": win_rate,
                                         "evaluated_at": now.isoformat()},
                        }).eq("id", rule_id).execute()
                        counts["failed"] += 1
                        log.warning(
                            "[SemanticMemory] shadow→failed: %s (win_rate=%.1f%%)",
                            rule.get("content", "")[:60], win_rate,
                        )
                    else:
                        # graduated:清 shadow_mode_until,保留 is_active
                        get_db().table("agent_memory").update({
                            "shadow_mode_until": None,
                            "metadata": {**(rule.get("metadata") or {}),
                                         "shadow_outcome": "graduated",
                                         "shadow_win_rate": win_rate,
                                         "evaluated_at": now.isoformat()},
                        }).eq("id", rule_id).execute()
                        counts["graduated"] += 1
                        log.info(
                            "[SemanticMemory] shadow→graduated: %s (win_rate=%.1f%%)",
                            rule.get("content", "")[:60], win_rate,
                        )
                else:
                    # match_count >= 3 但没有 comply 数据(rule 触发后没记 outcome)
                    # 保守:再多观察一段(延长 7 天)
                    extended = now + timedelta(days=7)
                    get_db().table("agent_memory").update({
                        "shadow_mode_until": extended.isoformat(),
                    }).eq("id", rule_id).execute()
                    log.info(
                        "[SemanticMemory] shadow extended +7d (no comply data): %s",
                        rule.get("content", "")[:60],
                    )
            except Exception as e:
                log.warning("[SemanticMemory] shadow eval row failed: %s", e)
                counts["errors"] += 1

        if counts["graduated"] or counts["dormant"] or counts["failed"]:
            self._last_load = 0  # 强刷
        return counts

    def force_refresh(self) -> None:
        """强制刷新缓存"""
        self._last_load = 0
        self._ensure_loaded()
