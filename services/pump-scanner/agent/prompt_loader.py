"""
Prompt Loader — 18 个 P 的版本化 + A/B 灰度加载

引用 docs/agent-pm/07-prompt-library.md
引用 docs/agent-pm/17-tech-plan.md Phase 2
引用 migration 038_prompt_versions.sql

加载策略:
  - 启动时从 prompts/v1/Pxx/ 目录加载所有 prompt 文件 + frontmatter
  - 支持纯磁盘加载(W3 D5+ 真实施)+ DB 同步(留 W7-W12)
  - 运行时按 device_id 分桶: hash(device_id) % 100 命中 rollout_pct → 走该版本
  - Canary 5% → Beta 25% → GA 100% 渐进
  - cache_breakpoints 通过 to_anthropic_messages 时插入

依赖:PyYAML(可选;不装时降级 frontmatter parser 只解析简单 key=value)
"""
from __future__ import annotations
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "v1"


# ── frontmatter parser(避开必装 PyYAML) ─────────────────────

def _parse_frontmatter(text: str) -> Dict[str, Any]:
    """简易 YAML 子集解析 — 支持 key: value / key: [a, b] / 多行 |
    生产用 PyYAML;此降级版只处理 frontmatter 常见 case。
    """
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        pass

    # 降级 parser
    out: Dict[str, Any] = {}
    lines = text.splitlines()
    i = 0
    multiline_key: Optional[str] = None
    multiline_buf: List[str] = []
    while i < len(lines):
        ln = lines[i]
        # 多行延续
        if multiline_key and (ln.startswith("  ") or ln.strip() == ""):
            multiline_buf.append(ln[2:] if ln.startswith("  ") else "")
            i += 1
            continue
        if multiline_key:
            out[multiline_key] = "\n".join(multiline_buf).rstrip()
            multiline_key = None
            multiline_buf = []

        if not ln.strip() or ln.strip().startswith("#"):
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
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            out[key] = [s.strip().strip('"').strip("'") for s in inner.split(",") if s.strip()]
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
    return out


# ── 模板变量替换(简易,避开 jinja 依赖) ───────────────────

_VAR_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def _render_template(text: str, vars: Dict[str, Any]) -> str:
    """{{var}} / {{nested.key}} 替换。未找到的占位符保留(便于上层补)。"""
    def _sub(m: "re.Match[str]") -> str:
        path = m.group(1).split(".")
        cur: Any = vars
        for p in path:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return m.group(0)
        return str(cur) if cur is not None else ""
    return _VAR_RE.sub(_sub, text)


# ── PromptSpec ──────────────────────────────────────────────


@dataclass
class PromptSpec:
    prompt_id: str
    version: str
    content: str
    frontmatter: Dict[str, Any]
    examples: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "draft"        # draft / canary / beta / ga / retired
    rollout_pct: int = 0
    description: str = ""

    @property
    def model(self) -> str:
        return self.frontmatter.get("model", "claude-haiku-4-5-20251001")

    @property
    def temperature(self) -> float:
        return float(self.frontmatter.get("temperature", 0.3))

    @property
    def max_input_tokens(self) -> int:
        return int(self.frontmatter.get("max_input_tokens", 8000))

    @property
    def max_output_tokens(self) -> int:
        return int(self.frontmatter.get("max_output_tokens", 1500))

    def to_anthropic_messages(
        self, device_id: str, user_message: str, vars: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """组装 Anthropic Messages.create 请求 dict(不实际调 API)。

        - system 末尾按 cache_breakpoints 加 cache_control marker
          (Anthropic 推荐:system prompt 末尾加 marker → cache 命中率 80%+)
        - user message 走最简 user role
        - few-shot 例子作为 prefilled assistant + user 对插入(若 examples 非空)
        """
        rendered_system = _render_template(self.content, vars or {})

        messages: List[Dict[str, Any]] = []
        # few-shot:每条 {user_input, assistant_output}
        for ex in self.examples:
            if isinstance(ex, dict) and "user" in ex and "assistant" in ex:
                messages.append({"role": "user", "content": ex["user"]})
                messages.append({"role": "assistant", "content": ex["assistant"]})
        messages.append({"role": "user", "content": user_message})

        # cache_control:system 文本拆成 stable + dynamic 两块,stable 加 cache_control
        # 这里简化:整个 system 当 stable(适合 frontmatter 标 cache_at_end=true)
        cache_at_end = bool(self.frontmatter.get("cache_at_end", True))
        if cache_at_end:
            system_payload = [{
                "type": "text",
                "text": rendered_system,
                "cache_control": {"type": "ephemeral"},
            }]
        else:
            system_payload = rendered_system

        return {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "system": system_payload,
            "messages": messages,
        }


# ── PromptLoader ────────────────────────────────────────────


class PromptLoader:
    """单例;启动时从磁盘 + (可选)DB 加载;运行时按 device_id 分桶选版本。"""

    def __init__(self, prompts_dir: Optional[Path] = None) -> None:
        self._prompts: Dict[str, List[PromptSpec]] = {}  # prompt_id → [versions]
        self._prompts_dir = Path(prompts_dir) if prompts_dir else PROMPTS_DIR

    def load_from_disk(self) -> int:
        """从 prompts/v1/Pxx_*/{prompt.md, examples.md, frontmatter.yaml} 加载。

        Returns: 加载到的 (prompt_id × version) 数量
        """
        self._prompts = {}
        if not self._prompts_dir.exists():
            log.warning("[PromptLoader] dir not found: %s", self._prompts_dir)
            return 0

        loaded = 0
        for sub in sorted(self._prompts_dir.iterdir()):
            if not sub.is_dir():
                continue
            # 期望目录名以 P\d{2}_ 开头
            name_match = re.match(r"^(P\d{2})_", sub.name)
            if not name_match:
                continue
            prompt_id = name_match.group(1)

            fm_path = sub / "frontmatter.yaml"
            prompt_path = sub / "prompt.md"
            examples_path = sub / "examples.md"

            if not (fm_path.exists() and prompt_path.exists()):
                log.debug("[PromptLoader] skip %s (missing prompt.md or frontmatter.yaml)", sub.name)
                continue

            try:
                fm = _parse_frontmatter(fm_path.read_text(encoding="utf-8"))
                content = prompt_path.read_text(encoding="utf-8")
                examples = self._parse_examples_file(
                    examples_path.read_text(encoding="utf-8")
                ) if examples_path.exists() else []
            except Exception as e:
                log.warning("[PromptLoader] failed to load %s: %s", sub.name, e)
                continue

            spec = PromptSpec(
                prompt_id=fm.get("prompt_id", prompt_id),
                version=fm.get("version", "v1.0"),
                content=content,
                frontmatter=fm,
                examples=examples,
                status=fm.get("status", "draft"),
                rollout_pct=int(fm.get("rollout_pct", 0) or 0),
                description=fm.get("description", "") or "",
            )
            self._prompts.setdefault(spec.prompt_id, []).append(spec)
            loaded += 1

        log.info("[PromptLoader] loaded %d prompt versions across %d ids from %s",
                 loaded, len(self._prompts), self._prompts_dir)
        return loaded

    @staticmethod
    def _parse_examples_file(text: str) -> List[Dict[str, str]]:
        """examples.md 格式:
        ## Example 1
        **User:** 用户消息文本
        **Assistant:** 助手回复文本

        支持多个 Example,每个 user/assistant 对。
        """
        examples: List[Dict[str, str]] = []
        cur: Dict[str, str] = {}
        cur_role: Optional[str] = None
        cur_buf: List[str] = []

        def _flush_role():
            nonlocal cur_role, cur_buf
            if cur_role and cur_buf:
                cur[cur_role] = "\n".join(cur_buf).strip()
            cur_role = None
            cur_buf = []

        for ln in text.splitlines():
            if ln.startswith("## "):
                _flush_role()
                if cur:
                    examples.append(cur)
                cur = {}
                continue
            m = re.match(r"^\*\*(User|Assistant):\*\*\s*(.*)$", ln)
            if m:
                _flush_role()
                cur_role = m.group(1).lower()
                rest = m.group(2)
                cur_buf = [rest] if rest else []
                continue
            if cur_role:
                cur_buf.append(ln)
        _flush_role()
        if cur:
            examples.append(cur)
        return examples

    def list_prompts(self) -> List[str]:
        return sorted(self._prompts.keys())

    def get_versions(self, prompt_id: str) -> List[PromptSpec]:
        return list(self._prompts.get(prompt_id, []))

    def select_version(
        self, prompt_id: str, device_id: str,
    ) -> Optional[PromptSpec]:
        """按 hash(device_id) % 100 选 active 版本。

        优先级:
          ga >= rollout_pct 命中(始终选 ga)
          beta >= rollout_pct 命中
          canary >= rollout_pct 命中
          否则 fallback 到 highest version draft(开发模式)

        多个 status 同时存在时,bucket 命中 rollout 范围最大的 status:
          - bucket < 5  → canary 优先
          - bucket < 25 → beta 优先
          - bucket < 100 → ga 优先
        实际策略简化为:取所有 status 中 active 的 versions,选 bucket < rollout_pct 的最高优先级。
        """
        versions = self._prompts.get(prompt_id, [])
        if not versions:
            return None

        bucket = self._bucket(device_id, prompt_id)
        active = [v for v in versions if v.status in ("canary", "beta", "ga")
                  and bucket < v.rollout_pct]

        if active:
            # 优先 ga > beta > canary(rollout_pct 大的优先)
            priority = {"ga": 3, "beta": 2, "canary": 1}
            active.sort(
                key=lambda v: (priority.get(v.status, 0), v.rollout_pct),
                reverse=True,
            )
            return active[0]

        # fallback:开发模式取 draft 最高 version
        drafts = [v for v in versions if v.status == "draft"]
        if drafts:
            drafts.sort(key=lambda v: v.version, reverse=True)
            return drafts[0]
        # 最后 fallback:返第一个
        return versions[0]

    def render(
        self, prompt_id: str, device_id: str,
        vars: Optional[Dict] = None,
    ) -> str:
        spec = self.select_version(prompt_id, device_id)
        if spec is None:
            raise KeyError(f"prompt {prompt_id} not loaded")
        return _render_template(spec.content, vars or {})

    def to_messages_request(
        self, prompt_id: str, device_id: str, user_message: str,
        vars: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        spec = self.select_version(prompt_id, device_id)
        if spec is None:
            raise KeyError(f"prompt {prompt_id} not loaded")
        return spec.to_anthropic_messages(device_id, user_message, vars)

    @staticmethod
    def _bucket(device_id: str, prompt_id: str = "") -> int:
        """hash(device_id + prompt_id) % 100 → 0..99
        加 prompt_id 让不同 prompt 的灰度互相独立(避免命中同一 device 的所有版本)
        """
        h = hashlib.sha1((device_id + ":" + prompt_id).encode()).hexdigest()
        return int(h[:8], 16) % 100


# ── singleton ───────────────────────────────────────────────


_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """返回单例;首次调用时从磁盘加载。"""
    global _loader
    if _loader is None:
        _loader = PromptLoader()
        _loader.load_from_disk()
    return _loader


def reset_loader_for_test() -> None:
    """测试用:重置单例。"""
    global _loader
    _loader = None
