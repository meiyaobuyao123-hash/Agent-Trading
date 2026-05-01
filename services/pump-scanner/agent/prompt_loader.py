"""
Prompt Loader — 18 个 P 的版本化 + A/B 灰度加载
引用 docs/agent-pm/07-prompt-library.md
引用 docs/agent-pm/17-tech-plan.md Phase 2
引用 migration 038_prompt_versions.sql

加载策略:
  - 启动时从 prompts/v1/Pxx/ 目录加载所有 prompt 文件 + frontmatter
  - 同步 prompt_versions 表(如果 DB 缺则插入,初版 status='draft')
  - 运行时按 device_id 分桶: hash(device_id) % 100 < rollout_pct → 走该版本
  - Canary 5% → Beta 25% → GA 100% 渐进
  - cache_breakpoints 按 frontmatter 拼到 system prompt

状态:🔴 v0.1 占位(W7-W12 实施)
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import logging

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "v1"


@dataclass
class PromptSpec:
    prompt_id: str           # 'P01' ... 'P18'
    version: str             # 'v1.0'
    content: str
    frontmatter: dict
    examples: list[dict]     # few-shot
    status: str              # 'draft' | 'canary' | 'beta' | 'ga' | 'retired'
    rollout_pct: int


class PromptLoader:
    """单例;启动时从磁盘 + DB 加载;运行时按 device_id 分桶。"""

    def __init__(self) -> None:
        self._prompts: dict[str, list[PromptSpec]] = {}  # prompt_id → [versions]

    async def load_all(self) -> None:
        # TODO: 扫描 prompts/v1/P01..P18/{prompt.md, examples.md, frontmatter.yaml}
        # TODO: 与 prompt_versions 表同步
        log.info("[PromptLoader] TODO: load all 18 prompts from %s", PROMPTS_DIR)

    def select_version(self, prompt_id: str, device_id: str) -> PromptSpec | None:
        """按 hash(device_id) % 100 分桶,选当前 active 版本。
        多版本并存时选 rollout 命中且 promoted_at 最新的。
        """
        versions = self._prompts.get(prompt_id, [])
        if not versions:
            return None
        bucket = self._bucket(device_id)
        # TODO: 实施分桶选择逻辑
        return versions[0]

    def render(self, prompt_id: str, device_id: str, vars: dict) -> str:
        """渲染指定 prompt(按 device 分桶选版本)。"""
        spec = self.select_version(prompt_id, device_id)
        if spec is None:
            raise KeyError(f"prompt {prompt_id} not loaded")
        # TODO: 模板变量替换 + cache_breakpoints 拼接
        return spec.content

    @staticmethod
    def _bucket(device_id: str) -> int:
        """hash(device_id) % 100 → 0..99"""
        h = hashlib.sha1(device_id.encode()).hexdigest()
        return int(h[:8], 16) % 100


_loader: PromptLoader | None = None


def get_prompt_loader() -> PromptLoader:
    global _loader
    if _loader is None:
        _loader = PromptLoader()
    return _loader
