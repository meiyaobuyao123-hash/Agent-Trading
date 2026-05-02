"""
Skill Loader 单元测试 — W3 D5+ autonomous-loop 续 17

跑法:python3 -m pytest tests/test_skill_loader.py -v
"""
from __future__ import annotations
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.skills import loader as loader_mod  # noqa: E402
from agent.skills.loader import (  # noqa: E402
    ALWAYS_LOADED,
    LAZY,
    LOOP_TO_SKILLS,
    SkillLoader,
    SkillMeta,
    _parse_skill_md,
    _parse_yaml_subset,
    get_skill_loader,
    reset_for_test,
)


# ── _parse_yaml_subset / _parse_skill_md ────────────────────

def test_parse_yaml_basic():
    text = "name: test\nversion: v1.0\n"
    fm = _parse_yaml_subset(text)
    assert fm["name"] == "test"
    assert fm["version"] == "v1.0"


def test_parse_yaml_list():
    fm = _parse_yaml_subset("tools_required: [a, b, c]\n")
    assert fm["tools_required"] == ["a", "b", "c"]


def test_parse_yaml_multiline():
    text = """name: x
description: |
  line1
  line2
version: v1.0
"""
    fm = _parse_yaml_subset(text)
    assert "line1" in fm["description"]
    assert "line2" in fm["description"]
    assert fm["version"] == "v1.0"


def test_parse_yaml_nested_dict():
    text = """failure_fallback:
  on_load_fail: rule_engine
  on_tool_fail: skip_tool
name: x
"""
    fm = _parse_yaml_subset(text)
    assert fm["failure_fallback"]["on_load_fail"] == "rule_engine"
    assert fm["failure_fallback"]["on_tool_fail"] == "skip_tool"
    assert fm["name"] == "x"


def test_parse_skill_md_split():
    text = """---
name: foo
---

# Body markdown
content here
"""
    fm, body = _parse_skill_md(text)
    assert fm["name"] == "foo"
    assert "# Body markdown" in body
    assert "content here" in body


def test_parse_skill_md_no_frontmatter():
    text = "no fm here"
    fm, body = _parse_skill_md(text)
    assert fm == {}
    assert body == text


# ── load_all on real dir ────────────────────────────────────

def test_load_all_loads_seven_skills():
    """真目录 agent/skills/Sxx_*/SKILL.md 应加载 7 个 skill。"""
    reset_for_test()
    loader = get_skill_loader()
    ids = loader.list_skills()
    expected = {"S01", "S02", "S03", "S04", "S05", "S07", "S08"}
    assert expected.issubset(set(ids)), f"missing: {expected - set(ids)}"


def test_skill_metadata_complete():
    reset_for_test()
    loader = get_skill_loader()
    s08 = loader.get_meta("S08")
    assert s08 is not None
    assert s08.name == "thesis-writer"
    assert "thesis" in s08.description.lower()
    assert "calc_risk_metrics" in s08.tools_required
    assert "sonnet" in s08.model.lower()


def test_always_loaded_have_full_content():
    reset_for_test()
    loader = get_skill_loader()
    for sid in ("S01", "S02", "S03", "S07", "S08"):
        m = loader.get_meta(sid)
        assert m is not None
        assert m.full_content is not None
        assert len(m.full_content) > 100


def test_lazy_skills_no_full_content_initially():
    reset_for_test()
    loader = get_skill_loader()
    for sid in ("S04", "S05"):
        m = loader.get_meta(sid)
        assert m is not None
        assert m.full_content is None  # lazy
        assert m.is_lazy is True


def test_lazy_load_full_on_demand():
    reset_for_test()
    loader = get_skill_loader()
    body = loader.load_full("S04")
    assert body is not None
    assert "StrategySpec" in body or "strategy" in body.lower()
    # 二次加载缓存命中
    cached = loader.get_meta("S04").full_content
    assert cached is not None


# ── load_all on temp dir (skip non-S prefix) ────────────────

def test_load_all_skips_non_s_prefix():
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "not_a_skill"
        bad.mkdir()
        (bad / "SKILL.md").write_text("---\nname: x\n---\nbody")
        l = SkillLoader(skills_dir=Path(tmp))
        n = l.load_all()
        assert n == 0


def test_load_all_skips_dirs_without_skill_md():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "S01_test"
        d.mkdir()
        # no SKILL.md
        l = SkillLoader(skills_dir=Path(tmp))
        n = l.load_all()
        assert n == 0


# ── skills_for_loop / Progressive Disclosure ────────────────

def test_skills_for_loop_thesis_l1_empty():
    reset_for_test()
    loader = get_skill_loader()
    assert loader.skills_for_loop("thesis_l1") == []


def test_skills_for_loop_thesis_l2_only_s08():
    reset_for_test()
    loader = get_skill_loader()
    skills = loader.skills_for_loop("thesis_l2")
    assert len(skills) == 1
    assert skills[0].skill_id == "S08"


def test_skills_for_loop_thesis_l3_four_skills():
    reset_for_test()
    loader = get_skill_loader()
    skills = loader.skills_for_loop("thesis_l3")
    ids = [s.skill_id for s in skills]
    assert ids == ["S01", "S02", "S03", "S08"]


def test_skills_for_loop_chat_includes_lazy():
    reset_for_test()
    loader = get_skill_loader()
    skills = loader.skills_for_loop("chat")
    ids = [s.skill_id for s in skills]
    assert "S04" in ids
    assert "S05" in ids
    assert "S08" in ids


def test_skills_for_loop_unknown_returns_empty():
    reset_for_test()
    loader = get_skill_loader()
    assert loader.skills_for_loop("nonexistent") == []


# ── loop_system_prompt ──────────────────────────────────────

def test_loop_system_prompt_scout_empty():
    reset_for_test()
    loader = get_skill_loader()
    assert loader.loop_system_prompt("scout") == ""


def test_loop_system_prompt_thesis_l2_includes_s08():
    reset_for_test()
    loader = get_skill_loader()
    prompt = loader.loop_system_prompt("thesis_l2")
    assert "thesis-writer" in prompt
    assert "Skill:" in prompt
    assert len(prompt) > 200


def test_loop_system_prompt_thesis_l3_lazy_loads_if_needed():
    reset_for_test()
    loader = get_skill_loader()
    prompt = loader.loop_system_prompt("thesis_l3")
    # L3 含 S01 + S02 + S03 + S08 内容
    assert "technical-analysis" in prompt
    assert "sentiment-analysis" in prompt
    assert "onchain-analysis" in prompt
    assert "thesis-writer" in prompt


def test_loop_system_prompt_chat_includes_lazy_loaded():
    """chat loop 包含 S04(lazy)— loop_system_prompt 应触发 lazy load。"""
    reset_for_test()
    loader = get_skill_loader()
    prompt = loader.loop_system_prompt("chat")
    assert "signal-strategy-builder" in prompt or "trade-strategy-builder" in prompt


def test_estimated_tokens_thesis_l2_in_budget():
    """对齐 17-tech-plan loop 预算:thesis L2 ~5K tokens(允许 ±50%)。"""
    reset_for_test()
    loader = get_skill_loader()
    n = loader.estimated_tokens("thesis_l2")
    assert n > 100  # 至少有内容
    assert n < 8000  # 不爆


# ── to_anthropic_skill_spec ────────────────────────────────

def test_to_anthropic_spec_includes_tools():
    reset_for_test()
    loader = get_skill_loader()
    s08 = loader.get_meta("S08")
    spec = s08.to_anthropic_skill_spec()
    assert spec["name"] == "thesis-writer"
    assert "calc_risk_metrics" in spec["tools"]


# ── ALWAYS_LOADED / LAZY 集合 sanity ────────────────────────

def test_always_loaded_disjoint_lazy():
    assert ALWAYS_LOADED.isdisjoint(LAZY)


def test_loop_to_skills_uses_known_ids():
    """LOOP_TO_SKILLS 的所有 skill_id 都该在 ALWAYS_LOADED 或 LAZY 里。"""
    all_known = ALWAYS_LOADED | LAZY
    for loop, ids in LOOP_TO_SKILLS.items():
        for sid in ids:
            assert sid in all_known, f"loop={loop} unknown skill {sid}"


# ── singleton ──────────────────────────────────────────────

def test_get_skill_loader_singleton():
    reset_for_test()
    a = get_skill_loader()
    b = get_skill_loader()
    assert a is b
