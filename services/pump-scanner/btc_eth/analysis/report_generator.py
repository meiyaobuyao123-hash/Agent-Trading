"""每日周期报告生成器 — Claude 综合分析"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from btc_eth.analysis.cycle_analyzer import CycleAnalyzer
from btc_eth.analysis.prompts import REPORT_SYSTEM_PROMPT
from btc_eth.config import BTCETH_CLAUDE_API_KEY, BTCETH_CLAUDE_MODEL
from btc_eth import storage

log = logging.getLogger(__name__)


class ReportGenerator:
    """每日投资策略报告"""

    def __init__(self):
        self._cycle_analyzer = CycleAnalyzer()

    async def generate(self, asset: str, snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成每日报告"""
        api_key = BTCETH_CLAUDE_API_KEY
        if not api_key:
            log.warning("[Report] 无 Claude API Key，跳过报告生成")
            return None

        try:
            from anthropic import Anthropic

            data_summary = CycleAnalyzer._build_data_summary(asset, snapshot)

            client = Anthropic(api_key=api_key)
            response = client.messages.create(
                model=BTCETH_CLAUDE_MODEL,
                max_tokens=2000,
                system=REPORT_SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"为 {asset} 生成今日投资策略报告。\n\n当前市场数据：\n{data_summary}"
                }]
            )

            text = response.content[0].text
            if "{" not in text:
                log.warning("[Report] Claude 输出无 JSON")
                return None

            json_str = text[text.index("{"):text.rindex("}") + 1]
            result = json.loads(json_str)

            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            report = {
                "asset": asset,
                "report_date": today,
                "cycle_phase": result.get("cycle_phase", "recovery"),
                "cycle_confidence": result.get("cycle_confidence", 50),
                "direction": result.get("direction", "neutral"),
                "position_allocation": result.get("position_allocation"),
                "key_levels": result.get("key_levels"),
                "risk_factors": result.get("risk_factors"),
                "indicator_snapshot": {k: v for k, v in snapshot.items() if not str(k).startswith("_")},
                "reasoning": result.get("reasoning", text),
            }

            # 保存到 DB
            storage.save_report(report)
            log.info("[Report] %s 周期报告已生成: %s (置信度 %d)",
                     asset, report["cycle_phase"], report["cycle_confidence"])

            return report

        except Exception as e:
            log.error("[Report] 报告生成失败: %s", e)
            return None
