"""
Skill Loader — Progressive Disclosure 加载机制

引用 docs/agent-pm/05-tool-catalog.md §5.4
引用 docs/agent-pm/17-tech-plan.md Phase 2 Skill 层

加载策略:
  Always Loaded(预加载完整 SKILL.md):
    - S01 technical-analysis(Thesis Loop L3)
    - S02 sentiment-analysis(Thesis Loop L3)
    - S03 onchain-analysis(Thesis Loop L3)
    - S07 review-engine(Reflect Loop)
    - S08 thesis-writer(Thesis Loop L2/L3)
  Lazy(只加载 metadata,真用时才 load_full):
    - S04 signal-strategy-builder(共创 chat;按用户请求触发)
    - S05 trade-strategy-builder(共创 chat;按用户请求触发)

每 SKILL.md 格式(对齐 Anthropic Skill spec + 17-tech-plan):
  ---frontmatter---
  skill_id: S08
  name: thesis-writer
  description: ...(用于 Loop 选 Skill 的关键词匹配)
  when_to_use: |
    多行说明触发场景
  tools_required: [calc_risk_metrics, recall_memory, ...]
  sub_skills_allowed: [S01, S02, S03]
  model: claude-sonnet-4-6
  version: v1.0
  failure_fallback:
    on_load_fail: rule_engine
    on_tool_fail: skip_tool_continue
  ---
  # System Prompt 主体(markdown)
  ...

W3 D5+ autonomous-loop 续 17 真实施(替代 W1 占位)。
"""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent

# 永远预加载(Loop 启动时拉完整 prompt + tools)
ALWAYS_LOADED = {"S01", "S02", "S03", "S07", "S08"}
LAZY = {"S04", "S05"}

# Loop → Skills 映射(决定每个 Loop 启动时拉哪些 Skill)
LOOP_TO_SKILLS = {
    "scout": [],                              # 纯规则 0 LLM
    "notify": [],                             # 纯规则 0 LLM
    "thesis_l1": [],                          # 规则化
    "thesis_l2": ["S08"],                     # 单 Sonnet 写 thesis
    "thesis_l3": ["S01", "S02", "S03", "S08"],# 3 路分析 + thesis 合成
    "reflect": ["S07"],                       # 复盘
    "chat": ["S04", "S05", "S08"],            # 共创 / 用户咨询
}


@dataclass
class SkillMeta:
    skill_id: str
    name: str
    description: str
    when_to_use: str = ""
    tools_required: List[str] = field(default_factory=list)
    sub_skills_allowed: List[str] = field(default_factory=list)
    model: str = "claude-haiku-4-5-20251001"
    version: str = "v1.0"
    failure_fallback: Dict[str, str] = field(default_factory=dict)
    full_content: Optional[str] = None  # ALWAYS_LOADED 预加载;LAZY 仅 metadata

    @property
    def is_lazy(self) -> bool:
        return self.skill_id in LAZY

    def to_anthropic_skill_spec(self) -> Dict[str, Any]:
        """生成 Anthropic Messages API 调用时可用的 spec dict。"""
        return {
            "name": self.name,
            "description": self.description,
            "model": self.model,
            "tools": self.tools_required,
        }


# ── frontmatter parser(简易;复用 prompt_loader 思路) ──────


def _parse_skill_md(text: str) -> "tuple[Dict[str, Any], str]":
    """切分 ---frontmatter--- + body。返 (frontmatter dict, body markdown)。"""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_text, body = parts[1], parts[2]
    fm = _parse_yaml_subset(fm_text)
    return fm, body.strip()


def _parse_yaml_subset(text: str) -> Dict[str, Any]:
    """简易 YAML 子集解析(优先用 PyYAML)。"""
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        pass
    out: Dict[str, Any] = {}
    lines = text.splitlines()
    i = 0
    multiline_key: Optional[str] = None
    multiline_buf: List[str] = []
    nested_key: Optional[str] = None
    nested_dict: Dict[str, Any] = {}

    while i < len(lines):
        ln = lines[i]
        if multiline_key and (ln.startswith("  ") or ln.strip() == ""):
            multiline_buf.append(ln[2:] if ln.startswith("  ") else "")
            i += 1
            continue
        if multiline_key:
            out[multiline_key] = "\n".join(multiline_buf).rstrip()
            multiline_key = None
            multiline_buf = []

        # nested dict close
        if nested_key and not (ln.startswith("  ") and ":" in ln):
            out[nested_key] = nested_dict
            nested_key = None
            nested_dict = {}

        if not ln.strip() or ln.strip().startswith("#"):
            i += 1
            continue

        # nested key item(2 空格缩进)
        if ln.startswith("  ") and nested_key and ":" in ln:
            inner = ln[2:].strip()
            ck, cv = inner.split(":", 1)
            nested_dict[ck.strip()] = cv.strip().strip('"').strip("'")
            i += 1
            continue

        m = re.match(r"^(\w+):\s*(.*)$", ln)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "|":
            multiline_key = key
            i += 1
            continue
        if val == "":
            # 可能开始一个 nested dict
            nested_key = key
            nested_dict = {}
            i += 1
            continue
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            out[key] = [s.strip().strip('"').strip("'")
                        for s in inner.split(",") if s.strip()]
        elif val.lower() in ("true", "false"):
            out[key] = (val.lower() == "true")
        else:
            try:
                if "." in val:
                    out[key] = float(val)
                else:
                    out[key] = int(val)
            except ValueError:
                out[key] = val.strip('"').strip("'")
        i += 1
    if multiline_key:
        out[multiline_key] = "\n".join(multiline_buf).rstrip()
    if nested_key:
        out[nested_key] = nested_dict
    return out


# ── SkillLoader ─────────────────────────────────────────────


class SkillLoader:
    """单例;启动时加载 metadata,ALWAYS_LOADED 拉完整 content。"""

    def __init__(self, skills_dir: Optional[Path] = None) -> None:
        self._metas: Dict[str, SkillMeta] = {}
        self._dir = Path(skills_dir) if skills_dir else SKILLS_DIR

    def load_all(self) -> int:
        """扫 agent/skills/Sxx_*/SKILL.md。返加载到的 skill 数。"""
        self._metas = {}
        if not self._dir.exists():
            log.warning("[SkillLoader] dir not found: %s", self._dir)
            return 0

        loaded = 0
        for sub in sorted(self._dir.iterdir()):
            if not sub.is_dir():
                continue
            m = re.match(r"^(S\d{2})_", sub.name)
            if not m:
                continue
            skill_id = m.group(1)
            skill_md = sub / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                text = skill_md.read_text(encoding="utf-8")
                fm, body = _parse_skill_md(text)
            except Exception as e:
                log.warning("[SkillLoader] parse %s failed: %s", skill_id, e)
                continue

            meta = SkillMeta(
                skill_id=fm.get("skill_id", skill_id),
                name=fm.get("name", sub.name),
                description=fm.get("description", "")[:300],
                when_to_use=fm.get("when_to_use", "") or "",
                tools_required=list(fm.get("tools_required", []) or []),
                sub_skills_allowed=list(fm.get("sub_skills_allowed", []) or []),
                model=fm.get("model", "claude-haiku-4-5-20251001"),
                version=fm.get("version", "v1.0"),
                failure_fallback=fm.get("failure_fallback", {}) or {},
                # ALWAYS_LOADED 直接缓存 body
                full_content=body if skill_id in ALWAYS_LOADED else None,
            )
            self._metas[skill_id] = meta
            loaded += 1

        log.info("[SkillLoader] loaded %d skills (always=%d, lazy=%d)",
                 loaded,
                 sum(1 for m in self._metas.values() if not m.is_lazy),
                 sum(1 for m in self._metas.values() if m.is_lazy))
        return loaded

    def list_skills(self) -> List[str]:
        return sorted(self._metas.keys())

    def get_meta(self, skill_id: str) -> Optional[SkillMeta]:
        return self._metas.get(skill_id)

    def load_full(self, skill_id: str) -> Optional[str]:
        """拿完整 SKILL.md content。LAZY 时按需读盘。"""
        meta = self._metas.get(skill_id)
        if meta is None:
            return None
        if meta.full_content is not None:
            return meta.full_content
        # lazy:按需读
        for sub in self._dir.iterdir():
            if sub.is_dir() and sub.name.startswith(f"{skill_id}_"):
                try:
                    text = (sub / "SKILL.md").read_text(encoding="utf-8")
                    _, body = _parse_skill_md(text)
                    meta.full_content = body
                    return body
                except Exception as e:
                    log.warning("[SkillLoader] lazy load %s failed: %s", skill_id, e)
                    return None
        return None

    def skills_for_loop(self, loop: str) -> List[SkillMeta]:
        """Progressive Disclosure:按 Loop 返该 Loop 用得到的 Skills。"""
        skill_ids = LOOP_TO_SKILLS.get(loop, [])
        return [self._metas[sid] for sid in skill_ids if sid in self._metas]

    def loop_system_prompt(self, loop: str) -> str:
        """拼出 Loop 的 system prompt(把 always-loaded skills 的 body 拼起来)。

        Scout/Notify 不调 LLM → 返空字符串。
        """
        if loop in ("scout", "notify", "thesis_l1"):
            return ""
        skills = self.skills_for_loop(loop)
        parts: List[str] = []
        for s in skills:
            content = s.full_content
            if content is None:
                content = self.load_full(s.skill_id)
            if content:
                parts.append(f"# Skill: {s.name}\n\n{content}")
        return "\n\n---\n\n".join(parts)

    def estimated_tokens(self, loop: str) -> int:
        """粗估 system prompt token 数(4 chars ~ 1 token)。"""
        return len(self.loop_system_prompt(loop)) // 4


# ── singleton ────────────────────────────────────────────


_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    global _loader
    if _loader is None:
        _loader = SkillLoader()
        _loader.load_all()
    return _loader


def reset_for_test() -> None:
    global _loader
    _loader = None
