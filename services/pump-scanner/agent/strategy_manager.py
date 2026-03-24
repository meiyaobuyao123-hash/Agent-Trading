"""
策略管理器 — CRUD + Cooldown 管理

提供策略的创建、读取、更新、删除，
以及冷却时间管理和触发计数。

Python 3.9 兼容。
"""
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

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
            query = (
                get_db()
                .table("agent_strategies")
                .select("*")
                .eq("status", "active")
            )

            if data_source:
                query = query.contains("data_sources", [data_source])

            result = query.execute()
            return result.data or []
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

    def go_live(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        将策略从 paper 切换到 live 模式

        前提：策略必须是 active + paper 模式。

        Returns:
            更新后的策略记录，失败返回 None
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

        result = self.update_strategy(strategy_id, {"mode": "live"})
        if result:
            log.info("Strategy %s switched to LIVE mode", strategy_id)
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
