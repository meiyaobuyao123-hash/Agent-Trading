"""
AI 主动推荐扫描器 (PRD-008 M17)

每 4h 主动扫描市场，发现高价值机会推送给用户：
  1. 聪明钱集中买入（elite 钱包 >= 2 买入同一代币）
  2. 热币 score 飙升（1h 内从 <50 升至 >70）
  3. KOL 共振（2h 内 >= 3 KOL 提及）

推送限制：
  - 每日最多 5 条主动推荐
  - 同一代币 24h 内不重复推荐

质量过滤 (v1.1 Q5)：
  - score >= 50
  - liquidity >= $30K
  - 无 GoPlus 风险标记
  - volume >= $10K

冲突检查 (v1.1 Q7)：
  - 检查用户已有策略是否覆盖该信号源

Python 3.9 兼容。
"""
import logging
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timedelta, timezone

from database import get_db

log = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────
MAX_DAILY_RECOMMENDATIONS = 5
COOLDOWN_HOURS = 24
SCAN_INTERVAL_HOURS = 4

# 内存中的 24h 冷却集合 {token_address: last_recommended_at}
_cooldown_cache: Dict[str, datetime] = {}


class ProactiveScanner:
    """AI 主动推荐扫描器"""

    async def scan_opportunities(self) -> List[Dict[str, Any]]:
        """
        主扫描入口 — 每 4h 调用一次

        发现高价值机会 → 写入 agent_recommendations → 推送告警
        """
        now = datetime.now(timezone.utc)
        opportunities: List[Dict[str, Any]] = []

        # 检查今日已推荐数
        daily_count = await self._get_daily_recommendation_count()
        if daily_count >= MAX_DAILY_RECOMMENDATIONS:
            log.info(
                "Proactive scanner: daily limit reached (%d/%d)",
                daily_count, MAX_DAILY_RECOMMENDATIONS,
            )
            return []

        remaining = MAX_DAILY_RECOMMENDATIONS - daily_count

        # ── 1. 聪明钱集中买入 ────────────────────────────────
        sm_opps = await self._scan_smart_money_signals(now)
        opportunities.extend(sm_opps)

        # ── 2. 热币 score 飙升 ───────────────────────────────
        hot_opps = await self._scan_hot_coin_spikes(now)
        opportunities.extend(hot_opps)

        # ── 3. KOL 共振 ─────────────────────────────────────
        kol_opps = await self._scan_kol_resonance(now)
        opportunities.extend(kol_opps)

        # 去重（同一代币只保留最高分的）
        seen: Dict[str, Dict[str, Any]] = {}
        for opp in opportunities:
            addr = opp.get("token_address", "")
            if addr not in seen or opp.get("score", 0) > seen[addr].get("score", 0):
                seen[addr] = opp
        unique_opps = list(seen.values())

        # 质量过滤 + 冲突检查 + 冷却检查
        filtered: List[Dict[str, Any]] = []
        for opp in unique_opps:
            if not self._passes_quality_filter(opp):
                continue
            if self._is_in_cooldown(opp.get("token_address", "")):
                continue
            if await self._conflicts_with_user_strategies(opp):
                continue
            filtered.append(opp)

        # 取 Top N
        filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
        to_push = filtered[:remaining]

        # 写入 DB + 推送
        for opp in to_push:
            await self._save_and_notify(opp)

        if to_push:
            log.info(
                "Proactive scanner: pushed %d recommendations (from %d candidates)",
                len(to_push), len(opportunities),
            )

        return to_push

    # ── 聪明钱信号扫描 ───────────────────────────────────────

    async def _scan_smart_money_signals(
        self, now: datetime
    ) -> List[Dict[str, Any]]:
        """检查 elite 钱包集中买入（2h 内 >= 2 买同一代币）"""
        cutoff = (now - timedelta(hours=2)).isoformat()
        results: List[Dict[str, Any]] = []

        try:
            res = (
                get_db()
                .table("smart_money_txns")
                .select("token_address, token_symbol, chain, wallet_address")
                .eq("action", "buy")
                .gte("created_at", cutoff)
                .execute()
            )
            txns = res.data or []
        except Exception as e:
            log.error("Proactive scan smart_money error: %s", e)
            return []

        # 按代币分组计数
        token_buys: Dict[str, Dict[str, Any]] = {}
        for tx in txns:
            addr = tx.get("token_address", "")
            if addr not in token_buys:
                token_buys[addr] = {
                    "token_address": addr,
                    "token_symbol": tx.get("token_symbol", ""),
                    "chain": tx.get("chain", ""),
                    "wallets": set(),
                    "source_type": "smart_money",
                }
            token_buys[addr]["wallets"].add(tx.get("wallet_address", ""))

        for addr, info in token_buys.items():
            if len(info["wallets"]) >= 2:
                results.append({
                    "token_address": addr,
                    "token_symbol": info.get("token_symbol", ""),
                    "chain": info.get("chain", ""),
                    "source_type": "smart_money",
                    "score": min(len(info["wallets"]) * 25, 100),
                    "reason": f"{len(info['wallets'])} 个聪明钱钱包在 2h 内买入",
                    "context": {
                        "elite_buy_count": len(info["wallets"]),
                    },
                })

        return results

    # ── 热币飙升扫描 ─────────────────────────────────────────

    async def _scan_hot_coin_spikes(
        self, now: datetime
    ) -> List[Dict[str, Any]]:
        """检查 hot score 从 <50 飙升到 >70（1h 内）"""
        results: List[Dict[str, Any]] = []

        try:
            # 查询当前 score > 70 的活跃热币
            res = (
                get_db()
                .table("hot_coins")
                .select("address, symbol, chain, score, price_change_24h, volume_24h_usd, liquidity_usd")
                .gte("score", 70)
                .eq("status", "active")
                .execute()
            )
            hot_coins = res.data or []
        except Exception as e:
            log.error("Proactive scan hot_coins error: %s", e)
            return []

        for coin in hot_coins:
            # 检查是否最近 1h 内从低分飙升
            # 简化：score >= 70 + 24h 涨幅 > 20% 视为飙升
            change_24h = float(coin.get("price_change_24h") or 0)
            if change_24h > 20:
                results.append({
                    "token_address": coin.get("address", ""),
                    "token_symbol": coin.get("symbol", ""),
                    "chain": coin.get("chain", ""),
                    "source_type": "hot_spike",
                    "score": float(coin.get("score") or 0),
                    "liquidity_usd": float(coin.get("liquidity_usd") or 0),
                    "volume_24h_usd": float(coin.get("volume_24h_usd") or 0),
                    "reason": f"Hot score={coin.get('score')}, 24h 涨幅 {change_24h:.1f}%",
                    "context": {
                        "hot_score": float(coin.get("score") or 0),
                        "price_change_24h": change_24h,
                    },
                })

        return results

    # ── KOL 共振扫描 ─────────────────────────────────────────

    async def _scan_kol_resonance(
        self, now: datetime
    ) -> List[Dict[str, Any]]:
        """检查 2h 内 >= 3 KOL 提及同一代币"""
        cutoff = (now - timedelta(hours=2)).isoformat()
        results: List[Dict[str, Any]] = []

        try:
            res = (
                get_db()
                .table("kol_signals")
                .select("token_address, token_symbol, chain, kol_count, avg_sentiment, signal_strength")
                .gte("detected_at", cutoff)
                .gte("kol_count", 3)
                .execute()
            )
            signals = res.data or []
        except Exception as e:
            log.error("Proactive scan kol_signals error: %s", e)
            return []

        for sig in signals:
            sentiment = float(sig.get("avg_sentiment") or 0)
            if sentiment > 0.3:  # 正面情绪
                results.append({
                    "token_address": sig.get("token_address", ""),
                    "token_symbol": sig.get("token_symbol", ""),
                    "chain": sig.get("chain", ""),
                    "source_type": "kol_resonance",
                    "score": float(sig.get("signal_strength") or 50),
                    "reason": f"{sig.get('kol_count')} KOL 在 2h 内提及，情绪={sentiment:.2f}",
                    "context": {
                        "kol_count": sig.get("kol_count"),
                        "avg_sentiment": sentiment,
                        "signal_strength": sig.get("signal_strength"),
                    },
                })

        return results

    # ── 质量过滤 (v1.1 Q5) ───────────────────────────────────

    def _passes_quality_filter(self, opp: Dict[str, Any]) -> bool:
        """
        5 项质量过滤：
          1. score >= 50
          2. liquidity >= $30K
          3. 无 GoPlus 风险标记
          4. volume >= $10K
          5. 非黑名单代币
        """
        score = float(opp.get("score") or 0)
        if score < 50:
            return False

        liquidity = float(opp.get("liquidity_usd") or 0)
        if liquidity > 0 and liquidity < 30000:
            return False

        if opp.get("goplus_risk", False):
            return False

        volume = float(opp.get("volume_24h_usd") or 0)
        if volume > 0 and volume < 10000:
            return False

        return True

    # ── 冷却检查 ─────────────────────────────────────────────

    def _is_in_cooldown(self, token_address: str) -> bool:
        """同一代币 24h 内不重复推荐"""
        global _cooldown_cache
        now = datetime.now(timezone.utc)

        # 清理过期缓存
        expired = [
            k for k, v in _cooldown_cache.items()
            if (now - v).total_seconds() > COOLDOWN_HOURS * 3600
        ]
        for k in expired:
            del _cooldown_cache[k]

        return token_address.lower() in _cooldown_cache

    # ── 冲突检查 (v1.1 Q7) ──────────────────────────────────

    async def _conflicts_with_user_strategies(
        self, opp: Dict[str, Any]
    ) -> bool:
        """检查用户是否已有覆盖该信号源的活跃策略"""
        source_type = opp.get("source_type", "")

        # 信号源 → 对应的 data_source 名
        source_mapping = {
            "smart_money": "smart_money_signals",
            "hot_spike": "hot_coins",
            "kol_resonance": "kol_mentions",
        }
        data_source = source_mapping.get(source_type, "")
        if not data_source:
            return False

        try:
            res = (
                get_db()
                .table("agent_strategies")
                .select("id", count="exact")
                .eq("status", "active")
                .contains("data_sources", [data_source])
                .execute()
            )
            return (res.count or 0) > 0
        except Exception as e:
            log.error("Proactive conflict check error: %s", e)
            return False

    # ── 今日已推荐数 ─────────────────────────────────────────

    async def _get_daily_recommendation_count(self) -> int:
        """获取今日已推荐数量"""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()

        try:
            res = (
                get_db()
                .table("agent_recommendations")
                .select("id", count="exact")
                .gte("created_at", today_start)
                .execute()
            )
            return res.count or 0
        except Exception as e:
            log.error("Proactive daily count error: %s", e)
            return 0

    # ── 保存并推送 ───────────────────────────────────────────

    async def _save_and_notify(self, opp: Dict[str, Any]) -> None:
        """保存推荐到 DB + 发送告警"""
        global _cooldown_cache
        token_address = opp.get("token_address", "")

        # 写入 agent_recommendations
        try:
            get_db().table("agent_recommendations").insert({
                "token_address": token_address,
                "token_symbol": opp.get("token_symbol", ""),
                "chain": opp.get("chain", ""),
                "source_type": opp.get("source_type", ""),
                "score": opp.get("score"),
                "reason": opp.get("reason", ""),
                "context": opp.get("context", {}),
                "status": "pending",
            }).execute()
        except Exception as e:
            log.error("Proactive save recommendation error: %s", e)
            return

        # 更新冷却缓存
        _cooldown_cache[token_address.lower()] = datetime.now(timezone.utc)

        # 写入告警（通知用户）
        try:
            title = f"AI 发现机会: {opp.get('token_symbol', 'Unknown')}"
            message = opp.get("reason", "发现高价值机会")

            get_db().table("agent_alerts").insert({
                "title": title,
                "message": message,
                "severity": "info",
                "is_read": False,
                "is_pushed": False,
                "trigger_context": {
                    "type": "proactive_recommendation",
                    "source_type": opp.get("source_type"),
                    "token_address": token_address,
                    "chain": opp.get("chain"),
                    "score": opp.get("score"),
                },
            }).execute()
        except Exception as e:
            log.error("Proactive alert error: %s", e)

        log.info(
            "Proactive recommendation: %s %s (source=%s, score=%s)",
            opp.get("chain"), opp.get("token_symbol"),
            opp.get("source_type"), opp.get("score"),
        )


# ── 全局单例 ──────────────────────────────────────────────────

_scanner: Optional[ProactiveScanner] = None


def get_proactive_scanner() -> ProactiveScanner:
    global _scanner
    if _scanner is None:
        _scanner = ProactiveScanner()
    return _scanner


# ── 定时任务入口 ──────────────────────────────────────────────

async def run_proactive_scan():
    """定时任务：每 4h 扫描一次"""
    scanner = get_proactive_scanner()
    await scanner.scan_opportunities()
