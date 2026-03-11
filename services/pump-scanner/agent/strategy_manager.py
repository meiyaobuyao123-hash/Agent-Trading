"""
策略管理器 — CRUD + Cooldown 管理

提供策略的创建、读取、更新、删除，
以及冷却时间管理和触发计数。

Python 3.9 兼容。
"""
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
    ) -> Optional[Dict[str, Any]]:
        """
        创建新策略

        Args:
            user_id: 用户 UUID
            spec: StrategySpec 的 dict 表示
            source_prompt: 用户原始自然语言输入

        Returns:
            创建的策略记录，或 None（失败）
        """
        try:
            # 提取数据源列表
            data_sources = self._extract_data_sources(
                spec.get("conditions", {})
            )

            row = {
                "user_id": user_id,
                "name": spec.get("name", "未命名策略"),
                "description": spec.get("description"),
                "conditions": spec.get("conditions", {}),
                "actions": spec.get("actions", []),
                "filters": spec.get("filters", {}),
                "data_sources": data_sources,
                "cooldown_min": max(spec.get("cooldown_minutes", 30), 5),
                "status": "active",
                "source_prompt": source_prompt,
            }

            result = get_db().table("agent_strategies").insert(row).execute()

            if result.data:
                strategy = result.data[0]
                log.info(
                    f"Created strategy: {strategy['name']} "
                    f"(id={strategy['id']}) for user {user_id}"
                )
                return strategy
            return None

        except Exception as e:
            log.error(f"create_strategy error: {e}")
            return None

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

        更新 trigger_count 和 last_triggered
        """
        try:
            # 先获取当前 trigger_count
            strategy = self.get_strategy(strategy_id)
            if not strategy:
                return False

            current_count = strategy.get("trigger_count", 0)

            get_db().table("agent_strategies").update({
                "trigger_count": current_count + 1,
                "last_triggered": datetime.utcnow().isoformat(),
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
