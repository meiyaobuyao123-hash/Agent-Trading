"""
1inch v6 API — EVM 链最优 DEX 聚合器

PRD-009: 多 DEX 执行路由
- 需要 API Key（可选，未配置则跳过）
- Base URL: https://api.1inch.dev/swap/v6.0
- 支持 ETH/BSC/Base
- EVM 地址需 EIP-55 checksum

Python 3.9 兼容。
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import aiohttp

log = logging.getLogger(__name__)

ONEINCH_BASE = "https://api.1inch.dev/swap/v6.0"

# chain name → 1inch chain ID
CHAIN_ID_MAP = {
    "eth": 1,
    "bsc": 56,
    "base": 8453,
}


def _to_checksum(address: str) -> str:
    """EIP-55 checksum 转换（v1.1 Q8）"""
    try:
        from eth_utils import to_checksum_address
        return to_checksum_address(address)
    except ImportError:
        # 如果 eth_utils 未安装，原样返回
        log.warning("eth_utils not installed, skipping checksum conversion")
        return address
    except Exception:
        return address


@dataclass
class OneInchQuote:
    """1inch 报价结果"""
    dex: str = "oneinch"
    from_token: str = ""
    to_token: str = ""
    from_amount: str = "0"
    to_amount: str = "0"
    estimated_gas: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def success(self) -> bool:
        return self.error == "" and int(self.to_amount) > 0


class OneInchDex:
    """1inch v6 REST API 客户端"""

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._api_key = os.getenv("ONEINCH_API_KEY", "")
        self._session = session
        self._owns_session = session is None

    @property
    def available(self) -> bool:
        """v1.1 Q9: Key 未配置则不可用，不阻塞"""
        return bool(self._api_key)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self):
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

    # ── 获取报价 ─────────────────────────────────────────────

    async def get_quote(
        self,
        chain_id: int,
        from_token: str,
        to_token: str,
        amount: str,
    ) -> OneInchQuote:
        """
        获取 1inch 报价

        Args:
            chain_id: 链 ID (1=ETH, 56=BSC, 8453=Base)
            from_token: 源代币地址 (EVM, 自动 checksum)
            to_token: 目标代币地址 (EVM, 自动 checksum)
            amount: 输入数量（最小单位, wei）

        Returns:
            OneInchQuote
        """
        if not self._api_key:
            return OneInchQuote(error="1inch API key not configured")

        try:
            # EIP-55 checksum (v1.1 Q8)
            from_token = _to_checksum(from_token)
            to_token = _to_checksum(to_token)

            session = await self._get_session()
            url = f"{ONEINCH_BASE}/{chain_id}/quote"
            params = {
                "src": from_token,
                "dst": to_token,
                "amount": str(amount),
            }

            async with session.get(
                url,
                params=params,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return OneInchQuote(error=f"HTTP {resp.status}: {text[:200]}")

                data = await resp.json()

            if "error" in data:
                return OneInchQuote(error=data.get("description", data["error"]))

            return OneInchQuote(
                from_token=from_token,
                to_token=to_token,
                from_amount=str(data.get("fromAmount", amount)),
                to_amount=str(data.get("toAmount", "0")),
                estimated_gas=int(data.get("gas", 0)),
                raw=data,
            )

        except Exception as e:
            log.warning(f"1inch quote error: {e}")
            return OneInchQuote(error=str(e))

    # ── 获取 swap 交易 ──────────────────────────────────────

    async def get_swap(
        self,
        chain_id: int,
        from_token: str,
        to_token: str,
        amount: str,
        from_address: str,
        slippage: float = 1.0,
    ) -> Dict[str, Any]:
        """
        获取 1inch swap 交易数据

        Args:
            chain_id: 链 ID
            from_token: 源代币地址
            to_token: 目标代币地址
            amount: 输入数量（wei）
            from_address: 发送者地址
            slippage: 滑点百分比 (1.0 = 1%)

        Returns:
            {"tx": {"to": ..., "data": ..., "value": ..., "gas": ...}} 或 {"error": ...}
        """
        if not self._api_key:
            return {"error": "1inch API key not configured"}

        try:
            # EIP-55 checksum
            from_token = _to_checksum(from_token)
            to_token = _to_checksum(to_token)
            from_address = _to_checksum(from_address)

            session = await self._get_session()
            url = f"{ONEINCH_BASE}/{chain_id}/swap"
            params = {
                "src": from_token,
                "dst": to_token,
                "amount": str(amount),
                "from": from_address,
                "slippage": str(slippage),
                "disableEstimate": "true",
            }

            async with session.get(
                url,
                params=params,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return {"error": f"HTTP {resp.status}: {text[:200]}"}

                data = await resp.json()

            if "error" in data:
                return {"error": data.get("description", data["error"])}

            return data

        except Exception as e:
            log.warning(f"1inch swap error: {e}")
            return {"error": str(e)}


# ── 全局单例 ──────────────────────────────────────────────────

_instance: Optional[OneInchDex] = None


def get_oneinch_dex() -> OneInchDex:
    global _instance
    if _instance is None:
        _instance = OneInchDex()
    return _instance
