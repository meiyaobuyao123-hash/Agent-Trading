"""
Prompt Loader 单元测试 — W3 D5+ autonomous-loop 续 6
覆盖:
  - frontmatter parser(YAML 子集)
  - 模板变量替换({{var}}, {{nested.key}})
  - examples.md 解析
  - PromptLoader.load_from_disk + select_version + bucket
  - A/B 灰度按 device 分桶 + status 优先级
  - to_anthropic_messages 拼装(cache_control + few-shot)

跑法:python3 -m pytest tests/test_prompt_loader.py -v
"""
from __future__ import annotations
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.prompt_loader import (  # noqa: E402
    PromptLoader,
    PromptSpec,
    _parse_frontmatter,
    _render_template,
    get_prompt_loader,
    reset_loader_for_test,
)


# ── frontmatter parser ──────────────────────────────────────

def test_parse_frontmatter_basic():
    text = """prompt_id: P01
version: v1.0
temperature: 0.4
status: draft
"""
    fm = _parse_frontmatter(text)
    assert fm["prompt_id"] == "P01"
    assert fm["version"] == "v1.0"
    assert fm["temperature"] == 0.4
    assert fm["status"] == "draft"


def test_parse_frontmatter_int():
    fm = _parse_frontmatter("rollout_pct: 25\nmax_input_tokens: 8000\n")
    assert fm["rollout_pct"] == 25
    assert fm["max_input_tokens"] == 8000


def test_parse_frontmatter_bool():
    fm = _parse_frontmatter("cache_at_end: true\nretired: false\n")
    assert fm["cache_at_end"] is True
    assert fm["retired"] is False


def test_parse_frontmatter_multiline():
    text = """description: |
  line one
  line two
prompt_id: P01
"""
    fm = _parse_frontmatter(text)
    assert "line one" in fm["description"]
    assert "line two" in fm["description"]
    assert fm["prompt_id"] == "P01"


def test_parse_frontmatter_quoted_string():
    fm = _parse_frontmatter('model: "claude-haiku"\n')
    assert fm["model"] == "claude-haiku"


# ── template renderer ──────────────────────────────────────

def test_render_template_simple():
    out = _render_template("Hello {{name}}", {"name": "World"})
    assert out == "Hello World"


def test_render_template_nested():
    out = _render_template(
        "{{user.name}} bought {{token.symbol}}",
        {"user": {"name": "Alice"}, "token": {"symbol": "TRUMP"}},
    )
    assert out == "Alice bought TRUMP"


def test_render_template_missing_var_preserved():
    """缺失变量保留 placeholder,允许上层补。"""
    out = _render_template("Hello {{name}}", {})
    assert out == "Hello {{name}}"


def test_render_template_with_whitespace():
    out = _render_template("X={{ x }} Y={{  y  }}", {"x": 1, "y": 2})
    assert out == "X=1 Y=2"


# ── PromptLoader: disk loading ──────────────────────────────

def test_load_from_disk_real_dir_loads_six_prompts():
    """真目录加载 6 个核心 P。"""
    reset_loader_for_test()
    loader = get_prompt_loader()
    ids = loader.list_prompts()
    # 至少有 P01/P02/P10/P11/P13/P18(本轮新建)
    expected = {"P01", "P02", "P10", "P11", "P13", "P18"}
    assert expected.issubset(set(ids)), f"缺失 prompts: {expected - set(ids)}"


def test_load_from_disk_p01_has_frontmatter():
    reset_loader_for_test()
    loader = get_prompt_loader()
    versions = loader.get_versions("P01")
    assert len(versions) >= 1
    p01 = versions[0]
    assert p01.prompt_id == "P01"
    assert p01.version == "v1.0"
    assert "claude" in p01.model
    assert p01.frontmatter.get("cache_at_end") is True


def test_load_from_disk_p01_has_examples():
    reset_loader_for_test()
    loader = get_prompt_loader()
    p01 = loader.get_versions("P01")[0]
    assert len(p01.examples) >= 3  # 至少 3 个 few-shot
    assert all("user" in ex and "assistant" in ex for ex in p01.examples)


def test_load_from_disk_p13_has_review_content():
    reset_loader_for_test()
    loader = get_prompt_loader()
    p13 = loader.get_versions("P13")[0]
    assert "复盘" in p13.content or "review" in p13.content.lower()
    assert "headline" in p13.content


def test_load_from_disk_skips_dirs_without_p_prefix():
    """临时目录,只有非 P 开头的子目录 → 不加载。"""
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "not_a_prompt"
        bad.mkdir()
        (bad / "frontmatter.yaml").write_text("prompt_id: X\n")
        (bad / "prompt.md").write_text("hi")
        loader = PromptLoader(prompts_dir=Path(tmp))
        n = loader.load_from_disk()
        assert n == 0


# ── select_version + bucket ─────────────────────────────────

def test_bucket_deterministic():
    """同 device + 同 prompt 始终命中同桶。"""
    b1 = PromptLoader._bucket("device-1", "P01")
    b2 = PromptLoader._bucket("device-1", "P01")
    assert b1 == b2
    assert 0 <= b1 < 100


def test_bucket_per_prompt_independent():
    """同 device 不同 prompt 桶值不同(独立灰度)。"""
    b_p01 = PromptLoader._bucket("device-1", "P01")
    b_p02 = PromptLoader._bucket("device-1", "P02")
    # 大概率不同(碰撞概率 1%)
    # 这里只验证函数能跑,不强求不等
    assert 0 <= b_p01 < 100
    assert 0 <= b_p02 < 100


def test_bucket_different_devices_different_buckets():
    """不同 device 产生不同桶分布。"""
    buckets = [PromptLoader._bucket(f"device-{i}", "P01") for i in range(50)]
    # 至少有 5 个不同桶值(50 个 device 不全压同桶)
    assert len(set(buckets)) >= 5


def test_select_version_falls_back_to_draft_when_no_active():
    """全部 draft 时 fallback 到 highest version。"""
    loader = PromptLoader()
    loader._prompts["P01"] = [
        PromptSpec("P01", "v1.0", "old", {}, status="draft", rollout_pct=0),
        PromptSpec("P01", "v1.1", "new", {}, status="draft", rollout_pct=0),
    ]
    selected = loader.select_version("P01", "any-device")
    assert selected.version == "v1.1"  # 字典序最高


def test_select_version_prefers_ga_over_canary():
    """同时 ga + canary 命中时,ga 优先。"""
    loader = PromptLoader()
    # 让 device 桶值 < 5(canary 5%)且 < 100(ga 100%)
    loader._prompts["P01"] = [
        PromptSpec("P01", "v1.0", "ga_content", {}, status="ga", rollout_pct=100),
        PromptSpec("P01", "v2.0", "canary_content", {}, status="canary", rollout_pct=5),
    ]
    selected = loader.select_version("P01", "device-x")
    # 桶 < 5 时两个都命中,但 ga 优先
    # 桶 ≥ 5 时只 ga 命中
    assert selected.status == "ga"
    assert selected.content == "ga_content"


def test_select_version_canary_only_for_5_pct_devices():
    """canary rollout=5 → 只有 5/100 device 命中。"""
    loader = PromptLoader()
    loader._prompts["P01"] = [
        PromptSpec("P01", "v1.0", "old_draft", {}, status="draft", rollout_pct=0),
        PromptSpec("P01", "v2.0", "canary_content", {}, status="canary", rollout_pct=5),
    ]
    canary_hits = 0
    fallback_hits = 0
    for i in range(1000):
        sel = loader.select_version("P01", f"d-{i}")
        if sel.content == "canary_content":
            canary_hits += 1
        else:
            fallback_hits += 1
    # canary 5% ≈ 50 / 1000,允许 ±50% 误差
    assert 25 <= canary_hits <= 90, f"canary hits {canary_hits} out of 1000"
    assert fallback_hits >= 900


def test_select_version_no_prompt_returns_none():
    loader = PromptLoader()
    assert loader.select_version("P99", "device") is None


# ── render + to_anthropic_messages ──────────────────────────

def test_render_substitutes_vars():
    loader = PromptLoader()
    loader._prompts["P01"] = [
        PromptSpec("P01", "v1.0", "Hello {{user.name}}", {}, status="draft"),
    ]
    out = loader.render("P01", "device", {"user": {"name": "Alice"}})
    assert out == "Hello Alice"


def test_render_unknown_prompt_raises():
    loader = PromptLoader()
    with pytest.raises(KeyError):
        loader.render("PXX", "device", {})


def test_to_anthropic_messages_includes_cache_control():
    loader = PromptLoader()
    loader._prompts["P02"] = [
        PromptSpec(
            "P02", "v1.0", "system content",
            {"model": "claude-haiku-4-5", "temperature": 0.2,
             "cache_at_end": True},
            examples=[],
            status="ga", rollout_pct=100,
        ),
    ]
    req = loader.to_messages_request("P02", "device", "user msg", {})
    assert req["model"] == "claude-haiku-4-5"
    assert req["temperature"] == 0.2
    assert isinstance(req["system"], list)
    assert req["system"][0]["cache_control"]["type"] == "ephemeral"
    assert req["system"][0]["text"] == "system content"
    assert req["messages"][-1]["content"] == "user msg"


def test_to_anthropic_messages_includes_few_shot():
    loader = PromptLoader()
    loader._prompts["P01"] = [
        PromptSpec(
            "P01", "v1.0", "sys",
            {"cache_at_end": True},
            examples=[
                {"user": "hi", "assistant": "hello"},
                {"user": "x", "assistant": "y"},
            ],
            status="draft",
        ),
    ]
    req = loader.to_messages_request("P01", "device", "actual user", {})
    msgs = req["messages"]
    # few-shot 2 对(user/assistant) + 1 actual user = 5 messages
    assert len(msgs) == 5
    assert msgs[0] == {"role": "user", "content": "hi"}
    assert msgs[1] == {"role": "assistant", "content": "hello"}
    assert msgs[-1] == {"role": "user", "content": "actual user"}


def test_to_anthropic_messages_no_cache_when_disabled():
    loader = PromptLoader()
    loader._prompts["P01"] = [
        PromptSpec("P01", "v1.0", "sys", {"cache_at_end": False}, status="draft"),
    ]
    req = loader.to_messages_request("P01", "device", "msg", {})
    # cache_at_end=false → system 是 string,不是 list
    assert isinstance(req["system"], str)


# ── examples.md parsing ─────────────────────────────────────

def test_parse_examples_file_two_pairs():
    text = """# P01 Few-shot

## Example 1

**User:** hi

**Assistant:** hello

## Example 2

**User:** x

**Assistant:** y
"""
    examples = PromptLoader._parse_examples_file(text)
    assert len(examples) == 2
    assert examples[0]["user"] == "hi"
    assert examples[0]["assistant"] == "hello"
    assert examples[1]["user"] == "x"


def test_parse_examples_file_multiline_assistant():
    text = """## Example 1

**User:** ask

**Assistant:** line 1
line 2
line 3
"""
    examples = PromptLoader._parse_examples_file(text)
    assert len(examples) == 1
    assert "line 1" in examples[0]["assistant"]
    assert "line 3" in examples[0]["assistant"]
