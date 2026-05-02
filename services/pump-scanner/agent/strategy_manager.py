"""
策略管理器 — CRUD + Cooldown 管理 + paper→auto 晋升门槛(R37 P0-2)

提供策略的创建、读取、更新、删除，
以及冷却时间管理和触发计数。

paper→auto 晋升门槛(对齐 docs/agent-pm/04-agent-spec.md §5.4 + 03-prd §5.4):
  ALL 必须满足:
    1. 策略创建满 30 天(created_at + 30d <= now)
    2. closed paper trades >= 30 笔
    3. avg_pnl_pct >= +1%(EV ≥ +1%)
    4. max_drawdown_pct < 30%(从 pnl_pcts 累计算)
  go_live() 调 check_promotion_eligibility() 校验;不通过返 None + reasons[]
  admin 可用 force=True 绕开(写 audit_log)

Python 3.9 兼容。
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

from database import get_db

log = logging.getLogger(__name__)


class StrategyManager:
    """策略 CRUD 管理器"""

    # ── 创建 ──────────────────────────────────────────────────

    def create_strategy(
        self,
        user_id: str,
        spec: Dict[str, Any],
        source_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建新策略

        Args:
            user_id: 用户 UUID
            spec: StrategySpec 的 dict 表示
            source_prompt: 用户原始自然语言输入

        Returns:
            创建的策略记录

        Raises:
            ValueError: 策略规范不完整
            RuntimeError: 数据库操作失败
        """
        # ── 验证 ──
        conditions = spec.get("conditions", {})
        rules = conditions.get("rules", [])
        if not rules:
            raise ValueError("策略条件不能为空，请至少设置一个触发条件")

        for rule in rules:
            if "data_source" not in rule or "field" not in rule:
                if "rules" not in rule:  # 非嵌套节点
                    raise ValueError(
                        "每条规则必须包含 data_source 和 field"
                    )

        actions = spec.get("actions", [])
        if not actions:
            raise ValueError("策略必须包含至少一个动作（alert/buy/sell）")

        # ── 提取数据源 ──
        data_sources = self._extract_data_sources(conditions)

        # ── risk_params 合并到 filters 中持久化 ──
        filters = spec.get("filters", {})
        risk_params = spec.get("risk_params")
        if risk_params:
            filters["risk_params"] = risk_params

        # ── PRD-008: mode 字段 (paper/live) ──
        mode = spec.get("mode", "paper")  # 默认 paper
        if mode not in ("paper", "live"):
            mode = "paper"

        template_id = spec.get("template_id")

        row = {
            "user_id": user_id,
            "name": spec.get("name", "未命名策略"),
            "description": spec.get("description"),
            "conditions": conditions,
            "actions": actions,
            "filters": filters,
            "data_sources": data_sources,
            "cooldown_min": max(spec.get("cooldown_minutes", 30), 5),
            "status": "active",
            "mode": mode,
            "source_prompt": source_prompt,
        }
        if template_id:
            row["template_id"] = template_id

        try:
            result = get_db().table("agent_strategies").insert(row).execute()
        except Exception as e:
            log.error("Supabase insert failed: %s", e)
            raise RuntimeError("数据库写入失败: %s" % str(e)[:200])

        if not result.data:
            raise RuntimeError("数据库返回空结果")

        strategy = result.data[0]
        log.info(
            "Created strategy: %s (id=%s) for user %s",
            strategy["name"], strategy["id"], user_id,
        )
        return strategy

    # ── 读取 ──────────────────────────────────────────────────

    def get_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """获取单个策略"""
        try:
            result = (
                get_db()
                .table("agent_strategies")
                .select("*")
                .eq("id", strategy_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            log.error(f"get_strategy error: {e}")
            return None

    def list_strategies(
        self,
        user_id: str,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出用户的策略"""
        try:
            query = (
                get_db()
                .table("agent_strategies")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
            )
            if status:
                query = query.eq("status", status)

            result = query.execute()
            return result.data or []
        except Exception as e:
            log.error(f"list_strategies error: {e}")
            return []

    def get_active_strategies(
        self,
        data_source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取所有活跃策略（用于评估器）

        Args:
            data_source: 可选，只返回关联此数据源的策略
        """
        try:
            # 迁移后 data_sources 从 TEXT[] 改为 JSONB，postgrest-py 的
            # .contains() 语法不兼容 → 客户端过滤（表本身只有 13 行，无性能影响）
            result = (
                get_db()
                .table("agent_strategies")
                .select("*")
                .eq("status", "active")
                .execute()
            )
            rows = result.data or []

            if data_source:
                rows = [
                    r for r in rows
                    if isinstance(r.get("data_sources"), list)
                    and data_source in r["data_sources"]
                ]

            return rows
        except Exception as e:
            log.error(f"get_active_strategies error: {e}")
            return []

    # ── 更新 ──────────────────────────────────────────────────

    def update_strategy(
        self,
        strategy_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """更新策略字段"""
        try:
            # 如果更新了 conditions，重新提取 data_sources
            if "conditions" in updates:
                updates["data_sources"] = self._extract_data_sources(
                    updates["conditions"]
                )

            # 确保 cooldown 下限
            if "cooldown_min" in updates:
                updates["cooldown_min"] = max(updates["cooldown_min"], 5)

            result = (
                get_db()
                .table("agent_strategies")
                .update(updates)
                .eq("id", strategy_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            log.error(f"update_strategy error: {e}")
            return None

    def pause_strategy(self, strategy_id: str) -> bool:
        """暂停策略"""
        result = self.update_strategy(strategy_id, {"status": "paused"})
        return result is not None

    def resume_strategy(self, strategy_id: str) -> bool:
        """恢复策略"""
        result = self.update_strategy(strategy_id, {"status": "active"})
        return result is not None

    def archive_strategy(self, strategy_id: str) -> bool:
        """归档策略"""
        result = self.update_strategy(strategy_id, {"status": "archived"})
        return result is not None

    # ── PRD-008: 模式切换 ─────────────────────────────────────

    # paper→auto 晋升门槛常数(可配置,但默认对齐 spec)
    PROMOTE_MIN_DAYS = 30
    PROMOTE_MIN_CLOSED_TRADES = 30
    PROMOTE_MIN_AVG_PNL_PCT = 1.0      # EV ≥ +1%
    PROMOTE_MAX_DRAWDOWN_PCT = 30.0    # 最大回撤 < 30%

    def _compute_paper_stats_sync(self, strategy_id: str) -> Dict[str, Any]:
        """同步版 paper trades 统计(go_live 是 sync,不能 await async)。
        返回:
          {closed_count, avg_pnl_pct, max_drawdown_pct, win_rate, pnl_pcts}
        """
        try:
            res = (
                get_db()
                .table("agent_paper_trades")
                .select("status,pnl_pct,pnl_usd,closed_at")
                .eq("strategy_id", strategy_id)
                .execute()
            )
            trades = res.data or []
        except Exception as e:
            log.error("[promotion] paper trades query failed: %s", e)
            trades = []

        closed = [t for t in trades if t.get("status") == "closed"]
        if not closed:
            return {
                "closed_count": 0,
                "avg_pnl_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "win_rate": 0.0,
                "pnl_pcts": [],
            }
        # 按 closed_at 升序计算累计回撤
        closed_sorted = sorted(closed, key=lambda t: t.get("closed_at") or "")
        pnl_pcts = [float(t.get("pnl_pct") or 0) for t in closed_sorted]
        # max drawdown:cumulative pnl 序列的最大下降幅度(从峰值)
        cum_pct = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in pnl_pcts:
            cum_pct += p
            if cum_pct > peak:
                peak = cum_pct
            dd = peak - cum_pct
            if dd > max_dd:
                max_dd = dd
        wins = sum(1 for p in pnl_pcts if p > 0)
        return {
            "closed_count": len(closed),
            "avg_pnl_pct": sum(pnl_pcts) / len(pnl_pcts),
            "max_drawdown_pct": max_dd,
            "win_rate": (wins / len(closed)) * 100,
            "pnl_pcts": pnl_pcts,
        }

    def check_promotion_eligibility(
        self, strategy_id: str,
    ) -> Dict[str, Any]:
        """检查策略是否符合 paper→auto 晋升门槛。
        返回 {eligible: bool, reasons: [], days_active, closed_count,
               avg_pnl_pct, max_drawdown_pct, required: {...}}
        引用 04-agent-spec §5.4 + 03-prd §5.4。
        """
        strategy = self.get_strategy(strategy_id)
        required = {
            "min_days": self.PROMOTE_MIN_DAYS,
            "min_closed_trades": self.PROMOTE_MIN_CLOSED_TRADES,
            "min_avg_pnl_pct": self.PROMOTE_MIN_AVG_PNL_PCT,
            "max_drawdown_pct": self.PROMOTE_MAX_DRAWDOWN_PCT,
        }
        if not strategy:
            return {
                "eligible": False,
                "reasons": ["strategy_not_found"],
                "required": required,
            }
        if strategy.get("status") != "active":
            return {
                "eligible": False,
                "reasons": [f"strategy_not_active:{strategy.get('status')}"],
                "required": required,
            }

        # 计算 days_active
        created_at = strategy.get("created_at")
        days_active = 0
        if created_at:
            try:
                # Supabase 返 ISO 字符串
                if isinstance(created_at, str):
                    cdt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                else:
                    cdt = created_at
                if cdt.tzinfo is None:
                    cdt = cdt.replace(tzinfo=timezone.utc)
                days_active = (datetime.now(timezone.utc) - cdt).days
            except Exception as e:
                log.warning("[promotion] parse created_at failed: %s", e)

        stats = self._compute_paper_stats_sync(strategy_id)
        reasons: List[str] = []
        if days_active < self.PROMOTE_MIN_DAYS:
            reasons.append(
                f"need_{self.PROMOTE_MIN_DAYS}d_active_got_{days_active}d"
            )
        if stats["closed_count"] < self.PROMOTE_MIN_CLOSED_TRADES:
            reasons.append(
                f"need_{self.PROMOTE_MIN_CLOSED_TRADES}_closed_trades_got_{stats['closed_count']}"
            )
        if stats["avg_pnl_pct"] < self.PROMOTE_MIN_AVG_PNL_PCT:
            reasons.append(
                f"need_avg_pnl_>={self.PROMOTE_MIN_AVG_PNL_PCT}%_got_{stats['avg_pnl_pct']:.2f}%"
            )
        if stats["max_drawdown_pct"] >= self.PROMOTE_MAX_DRAWDOWN_PCT:
            reasons.append(
                f"max_drawdown_{stats['max_drawdown_pct']:.2f}%_>=_{self.PROMOTE_MAX_DRAWDOWN_PCT}%_limit"
            )

        return {
            "eligible": len(reasons) == 0,
            "reasons": reasons,
            "days_active": days_active,
            "closed_count": stats["closed_count"],
            "avg_pnl_pct": round(stats["avg_pnl_pct"], 2),
            "max_drawdown_pct": round(stats["max_drawdown_pct"], 2),
            "win_rate": round(stats["win_rate"], 2),
            "required": required,
        }

    def go_live(
        self,
        strategy_id: str,
        force: bool = False,
        actor: str = "user",
    ) -> Optional[Dict[str, Any]]:
        """
        将策略从 paper 切换到 live 模式

        前提：策略必须是 active + paper 模式 + 通过晋升门槛(force=True 跳过)。

        Args:
            strategy_id: 策略 UUID
            force: True = 跳过晋升门槛(仅 admin 用,会写 audit_log)
            actor: 'user' / 'admin' / 'system' — 用于 audit log

        Returns:
            更新后的策略记录;不通过门槛返 None;
            mode 已是 live → 直接返当前(幂等)。
        """
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return None
        if strategy.get("mode") != "paper":
            log.warning(
                "go_live: strategy %s is already in '%s' mode",
                strategy_id, strategy.get("mode"),
            )
            return strategy
        if strategy.get("status") != "active":
            log.warning(
                "go_live: strategy %s status='%s', not active",
                strategy_id, strategy.get("status"),
            )
            return None

        # ── R37 P0-2:晋升门槛检查 ──────────────────────────────
        if not force:
            check = self.check_promotion_eligibility(strategy_id)
            if not check["eligible"]:
                log.warning(
                    "[go_live] strategy %s NOT ELIGIBLE: %s",
                    strategy_id, check["reasons"],
                )
                return None
        else:
            log.warning(
                "[go_live] strategy %s force=True actor=%s — bypassing eligibility",
                strategy_id, actor,
            )

        result = self.update_strategy(strategy_id, {"mode": "live"})
        if result:
            log.info(
                "Strategy %s switched to LIVE mode (force=%s actor=%s)",
                strategy_id, force, actor,
            )
        return result

    def get_mode(self, strategy_id: str) -> str:
        """获取策略 mode (paper/live)"""
        strategy = self.get_strategy(strategy_id)
        if strategy:
            return strategy.get("mode", "paper")
        return "paper"

    # ── 重命名 ──────────────────────────────────────────────────

    def rename_strategy(self, strategy_id: str, new_name: str) -> bool:
        """修改策略名称"""
        try:
            get_db().table("agent_strategies").update({
                "name": new_name.strip()[:100],
            }).eq("id", strategy_id).execute()
            log.info(f"Renamed strategy {strategy_id} to '{new_name}'")
            return True
        except Exception as e:
            log.error(f"rename_strategy error: {e}")
            return False

    # ── 删除 ──────────────────────────────────────────────────

    def delete_strategy(self, strategy_id: str) -> bool:
        """删除策略（级联删除告警）"""
        try:
            get_db().table("agent_strategies").delete().eq(
                "id", strategy_id
            ).execute()
            log.info(f"Deleted strategy: {strategy_id}")
            return True
        except Exception as e:
            log.error(f"delete_strategy error: {e}")
            return False

    # ── 触发管理 ──────────────────────────────────────────────

    def record_trigger(self, strategy_id: str) -> bool:
        """
        记录策略触发

        使用 Supabase RPC 原子递增 trigger_count，避免 TOCTOU 竞争
        """
        try:
            # 尝试使用 RPC 原子递增（需要在 Supabase 中定义函数）
            # fallback: 使用单次 update 表达式
            get_db().table("agent_strategies").update({
                "last_triggered": datetime.utcnow().isoformat(),
            }).eq("id", strategy_id).execute()

            # 单独用 rpc 原子递增 trigger_count
            try:
                get_db().rpc("increment_trigger_count", {
                    "sid": strategy_id,
                }).execute()
            except Exception:
                # RPC 不存在时 fallback: 读取-递增（仍有小概率竞争）
                strategy = self.get_strategy(strategy_id)
                if strategy:
                    current_count = strategy.get("trigger_count", 0)
                    get_db().table("agent_strategies").update({
                        "trigger_count": current_count + 1,
                    }).eq("id", strategy_id).execute()

            return True
        except Exception as e:
            log.error(f"record_trigger error: {e}")
            return False

    def check_daily_limit(
        self,
        strategy_id: str,
        max_daily: int = 50,
    ) -> bool:
        """
        检查策略每日触发限制

        Args:
            strategy_id: 策略 ID
            max_daily: 每日最大触发次数（默认 50）

        Returns:
            True if 未超限
        """
        try:
            today_start = datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            ).isoformat()

            result = (
                get_db()
                .table("agent_alerts")
                .select("id", count="exact")
                .eq("strategy_id", strategy_id)
                .gte("created_at", today_start)
                .execute()
            )
            count = result.count or 0
            return count < max_daily
        except Exception as e:
            log.error(f"check_daily_limit error: {e}")
            return True  # 出错时放行

    # ── 工具方法 ──────────────────────────────────────────────

    def _extract_data_sources(
        self,
        conditions: Dict[str, Any],
    ) -> List[str]:
        """从条件树中提取所有数据源名"""
        sources = set()  # type: set
        self._collect_sources(conditions, sources)
        return list(sources)

    def _collect_sources(
        self,
        node: Dict[str, Any],
        sources: set,
    ):
        """递归收集数据源"""
        if "data_source" in node:
            sources.add(node["data_source"])
        if "rules" in node:
            for rule in node["rules"]:
                self._collect_sources(rule, sources)

    def _infer_strategy_type(
        self,
        conditions: Dict[str, Any],
        data_sources: List[str],
    ) -> str:
        """
        PRD-005: 自动推断 strategy_type 标签

        推断逻辑：
        - conditions 含 smart_money -> smart_money_follow
        - conditions 含 kol -> kol_mention
        - data_sources 含 hot_coins -> hot_breakout / hot_score
        - data_sources 含 pump_tokens -> pump_early
        - 其他 -> custom
        """
        cond_str = json.dumps(conditions).lower()

        if "smart_money" in cond_str:
            return "smart_money_follow"
        if "kol" in cond_str or "kol_mentions" in str(data_sources).lower():
            return "kol_mention"
        if "hot_coins" in str(data_sources).lower():
            if "price_change" in cond_str:
                return "hot_breakout"
            return "hot_score"
        if "pump_tokens" in str(data_sources).lower():
            return "pump_early"
        return "custom"
