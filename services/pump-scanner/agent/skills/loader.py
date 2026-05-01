"""
Skill Loader — Progressive Disclosure 加载机制
引用 docs/agent-pm/05-tool-catalog.md §5.4

加载策略:
  Always Loaded(预加载完整 SKILL.md 全文 + tool schemas):
    - S08 thesis-writer (Thesis Loop)
    - S01/S02/S03 (Thesis Loop L3)
    - S07 review-engine (Reflect Loop)
  Lazy(只加载 name + description,触发时再 load_skill 拿全文):
    - S04 signal-strategy-builder
    - S05 trade-strategy-builder

Loop 预算(approx tokens):
  Scout Loop:        < 2K   (纯规则,无 Skill)
  Thesis Loop L2:    ~5K    (S08)
  Thesis Loop L3:    ~12K   (S01+S02+S03+S08+debate/review prompts)
  Notify Loop:       ~3K    (无 Skill)
  Reflect Loop:      ~6K    (S07)
  Chat:              ~8K    (所有 lazy metadata + S08)

状态:🔴 v0.1 占位(W7-W12 实施)
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import logging

log = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent

ALWAYS_LOADED = {"S01", "S02", "S03", "S07", "S08"}
LAZY = {"S04", "S05"}


@dataclass
class SkillMeta:
    skill_id: str        # 'S01' ... 'S08'
    name: str            # 'technical-analysis' ...
    description: str     # 强关键词描述(progressive disclosure matching 用)
    when_to_use: str
    tools_required: list[str]
    sub_skills_allowed: list[str]
    model: str           # 'claude-opus-latest'
    version: str
    failure_fallback: dict


class SkillLoader:
    def __init__(self) -> None:
        self._metas: dict[str, SkillMeta] = {}
        self._full_content: dict[str, str] = {}  # 仅 ALWAYS_LOADED 预加载完整

    async def load_all(self) -> None:
        # TODO: 扫描 agent/skills/<name>/SKILL.md frontmatter
        log.info("[SkillLoader] TODO: load all skills from %s", SKILLS_DIR)

    def get_loop_system_prompt(self, loop: str) -> str:
        """按 Loop 名拼装预加载的 system prompt。
        Scout/Notify 不返回 Skill prompt(0 LLM)。
        """
        if loop in ("scout", "notify"):
            return ""
        # TODO: 实施 Loop 与 Skills 映射 + always-loaded 拼接
        return ""

    async def load_skill_full(self, skill_id: str) -> str:
        """Lazy 加载完整 SKILL.md(失败 → SKILL_LOAD_FAILED → orchestration 走 failure_fallback)。"""
        if skill_id in self._full_content:
            return self._full_content[skill_id]
        # TODO: 从磁盘读 + 缓存
        raise NotImplementedError(f"load_skill_full({skill_id}) W7-W12 实施")


_loader: SkillLoader | None = None


def get_skill_loader() -> SkillLoader:
    global _loader
    if _loader is None:
        _loader = SkillLoader()
    return _loader
