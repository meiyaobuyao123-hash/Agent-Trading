"""风险预警生成器 — 事件驱动"""
import logging
import time
from typing import Dict, Any, Optional, List

from btc_eth import storage

log = logging.getLogger(__name__)


class AlertGenerator:
    """事件驱动风险预警"""

    def __init__(self):
        self._last_alert = {}  # type: Dict[str, float]  # alert_type -> timestamp
        self._cooldown = 3600  # 同类预警 1 小时冷却

    def check_alerts(self, asset: str, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检查是否需要发出风险预警"""
        alerts = []

        # 1. 资金费率极端
        funding = snapshot.get("funding_rate", 0)
        if abs(funding) > 0.03 and self._check_cooldown("funding_extreme"):
            alerts.append({
                "asset": asset,
                "severity": "warning",
                "alert_type": "funding_extreme",
                "title": f"资金费率极端: {funding:.4f}",
                "message": f"{asset} 资金费率达到 {funding:.4f}，{'多头' if funding > 0 else '空头'}极度拥挤，短期反转风险高",
                "data_snapshot": {"funding_rate": funding},
            })

        # 2. 大额爆仓
        liq = snapshot.get("liquidation_24h_usd", 0)
        if liq > 5e8 and self._check_cooldown("liq_cascade"):  # > 5 亿美元
            alerts.append({
                "asset": asset,
                "severity": "critical",
                "alert_type": "liq_cascade",
                "title": f"大规模爆仓: ${liq / 1e6:.0f}M",
                "message": f"24h 爆仓金额达 ${liq / 1e6:.0f}M，市场可能处于极端波动中",
                "data_snapshot": {"liquidation_24h_usd": liq},
            })

        # 3. 恐慌指数极端
        fgi = snapshot.get("fear_greed_index", 50)
        if fgi <= 10 and self._check_cooldown("extreme_fear"):
            alerts.append({
                "asset": asset,
                "severity": "info",
                "alert_type": "extreme_fear",
                "title": f"极度恐慌: FGI={fgi}",
                "message": f"恐慌贪婪指数仅 {fgi}，历史上极度恐慌往往是买入机会",
                "data_snapshot": {"fear_greed_index": fgi},
            })
        elif fgi >= 90 and self._check_cooldown("extreme_greed"):
            alerts.append({
                "asset": asset,
                "severity": "warning",
                "alert_type": "extreme_greed",
                "title": f"极度贪婪: FGI={fgi}",
                "message": f"恐慌贪婪指数高达 {fgi}，市场过热，注意风险",
                "data_snapshot": {"fear_greed_index": fgi},
            })

        # 4. 深度失衡严重
        depth_imb = snapshot.get("depth_imbalance", 0)
        if abs(depth_imb) > 0.5 and self._check_cooldown("depth_imbalance"):
            direction = "买单" if depth_imb > 0 else "卖单"
            alerts.append({
                "asset": asset,
                "severity": "info",
                "alert_type": "depth_imbalance",
                "title": f"订单簿严重失衡: {direction}占优",
                "message": f"{asset} 订单簿{direction}远多于对手方 (imbalance={depth_imb:.2f})，短期可能向{direction}方向突破",
                "data_snapshot": {"depth_imbalance": depth_imb},
            })

        # 保存预警
        for alert in alerts:
            storage.save_alert(alert)
            self._last_alert[alert["alert_type"]] = time.time()
            log.info("[Alert] %s: %s", alert["severity"].upper(), alert["title"])

        return alerts

    def on_whale_tx(self, whale_tx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """鲸鱼大额转账预警"""
        if whale_tx.get("btc_amount", 0) < 200:
            return None
        if not self._check_cooldown("whale_move"):
            return None

        direction = whale_tx.get("direction", "transfer")
        btc = whale_tx.get("btc_amount", 0)

        alert = {
            "asset": "BTC",
            "severity": "warning" if btc > 500 else "info",
            "alert_type": "whale_move",
            "title": f"🐋 大额转账: {btc:.0f} BTC ({direction})",
            "message": f"检测到 {btc:.0f} BTC 大额转账 ({direction})。{'转入交易所可能意味着抛压' if direction == 'exchange_inflow' else '转出交易所可能意味着囤积'}",
            "data_snapshot": whale_tx,
        }

        storage.save_alert(alert)
        self._last_alert["whale_move"] = time.time()
        log.info("[Alert] 🐋 %s: %.0f BTC %s", alert["severity"], btc, direction)
        return alert

    def _check_cooldown(self, alert_type: str) -> bool:
        last = self._last_alert.get(alert_type, 0)
        return (time.time() - last) > self._cooldown
