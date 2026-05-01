"""
KMS Client — 托管钱包 / API key 的 KMS 封装
引用 docs/agent-pm/17-tech-plan.md Phase 0
引用 migration 034_kms_migration.sql

替换:
  - L1 灾难漏洞:env 明文 ANTHROPIC_API_KEY / OKX_KEY / HELIUS_KEY → KMS 拉取
  - L2 灾难漏洞:agent_strategies.private_key / mnemonic 明文 → KMS 签名(私钥不落地)

支持 provider:aws-kms / gcp-kms / azure-kv / local-dev(开发)

状态:🔴 v0.1 占位(W1-W3 实施;阻塞 launch)
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import logging

log = logging.getLogger(__name__)


@dataclass
class KMSAlias:
    alias: str
    provider: str
    external_key_id: str
    is_active: bool


class KMSProvider(ABC):
    """KMS provider 抽象;每个云厂商一个实现。"""

    @abstractmethod
    async def get_secret(self, external_key_id: str) -> bytes:
        """从 KMS 取明文 secret(短期内存中持有,不落 DB / log)。"""

    @abstractmethod
    async def sign(self, external_key_id: str, message: bytes) -> bytes:
        """KMS 签名(私钥不出 KMS)。"""

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """KMS 可用性检查;影响 CB12。"""


class AwsKmsProvider(KMSProvider):
    async def get_secret(self, external_key_id: str) -> bytes:
        # TODO: boto3 KMS GenerateDataKey / Secrets Manager
        raise NotImplementedError("AwsKmsProvider Phase 0 W3 实施")

    async def sign(self, external_key_id: str, message: bytes) -> bytes:
        # TODO: boto3 KMS Sign(只支持非对称 key)
        raise NotImplementedError("AwsKmsProvider Phase 0 W3 实施")

    async def health(self) -> dict[str, Any]:
        return {"provider": "aws-kms", "available": False, "todo": "W3 实施"}


class LocalDevProvider(KMSProvider):
    """开发模式:从本机环境变量读取(仅本机,不上服务器)。"""

    async def get_secret(self, external_key_id: str) -> bytes:
        import os
        v = os.environ.get(external_key_id)
        if v is None:
            raise KeyError(f"local-dev KMS: env {external_key_id} not set")
        return v.encode()

    async def sign(self, external_key_id: str, message: bytes) -> bytes:
        raise NotImplementedError("local-dev 不做签名;真金交易必须走 aws-kms")

    async def health(self) -> dict[str, Any]:
        return {"provider": "local-dev", "available": True}


class KMSClient:
    """单例;启动时按 provider 配置初始化。"""

    def __init__(self) -> None:
        self._provider_cache: dict[str, KMSProvider] = {}
        self._alias_cache: dict[str, KMSAlias] = {}

    async def get_secret_by_alias(self, alias: str) -> bytes:
        """按别名取 secret;不缓存,每次都拉(KMS 自身有缓存层)。"""
        a = await self._resolve_alias(alias)
        provider = self._get_provider(a.provider)
        secret = await provider.get_secret(a.external_key_id)
        # TODO: 写 security_audit_log event_type='kms_use'
        return secret

    async def sign_by_alias(self, alias: str, message: bytes) -> bytes:
        """按别名签名(私钥不出 KMS)。"""
        a = await self._resolve_alias(alias)
        provider = self._get_provider(a.provider)
        return await provider.sign(a.external_key_id, message)

    async def health(self) -> dict[str, Any]:
        results = {}
        for name, provider in self._provider_cache.items():
            try:
                results[name] = await provider.health()
            except Exception as e:
                results[name] = {"available": False, "error": str(e)}
        return results

    async def _resolve_alias(self, alias: str) -> KMSAlias:
        # TODO: 从 kms_key_aliases 表查;读缓存 5min TTL
        raise NotImplementedError("Phase 0 W3 实施")

    def _get_provider(self, name: str) -> KMSProvider:
        if name not in self._provider_cache:
            if name == "aws-kms":
                self._provider_cache[name] = AwsKmsProvider()
            elif name == "local-dev":
                self._provider_cache[name] = LocalDevProvider()
            else:
                raise ValueError(f"unknown kms provider: {name}")
        return self._provider_cache[name]


_client: KMSClient | None = None


def get_kms_client() -> KMSClient:
    global _client
    if _client is None:
        _client = KMSClient()
    return _client
