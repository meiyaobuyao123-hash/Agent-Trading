"""
Input Filter — 用户输入 / LLM 输出的语义级安全检查

引用 docs/agent-pm/08-safety-policy.md(C1-C5)
引用 docs/agent-pm/17-tech-plan.md Phase 0 / Phase 4 Safety AE
引用 agent/output_filter.py(v0.1 C1 blocklist)— 本模块是 C1 的语义升级补充

W3 D5+ autonomous-loop 续 24 实施(替代 output_filter.py:77-78 的 TODO 占位)。

5 类 attack 检测(对应 docs/agent-pm/08-safety-policy.md AE03/AE04/AE09/AE10):
  - prompt_injection — 试图覆盖 system prompt / 角色互换 / jailbreak DAN
  - hitl_bypass     — "skip approval" / "跳过审批" / 伪 admin 角色
  - regulation_skirt — KYC 规避 / Tornado Cash / mixer / 假身份(SEV-0 critical)
  - implicit_promise — "保证赚 / 必赚 / 稳赚不赔"(C1 regex 漏掉的中文隐式)
  - hype_extended   — 隐喻 hype:rocket/lambo/FOMO/m00n leetspeak

返 FilterResult,与 output_filter.FilterResult 兼容(可被 router 统一聚合):
  passed=True 时无任何 violation;passed=False 时 violations 列表标 attack class。

设计思路:
  - 所有 regex 写 case-insensitive,支持 ASCII + 中文 unicode
  - 命中即返 passed=False(零容忍),不做软警告
  - sanitized_text 把命中段替换为 [BLOCKED:类名](便于 audit log 排查)
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re
import logging
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)


# ── attack class regex ───────────────────────────────────────

# AE03 prompt_injection
PROMPT_INJECTION_REGEX = re.compile(
    r"(ignore\s+(?:all\s+)?(?:prior|previous)\s+(?:instructions?|prompts?)"
    r"|forget\s+(?:all\s+)?(?:rules?|instructions?|prompts?)"
    r"|disregard\s+(?:all\s+)?(?:prior|previous)"
    r"|override\s+(?:all\s+)?(?:safety|prior|rules?)"
    r"|bypass\s+(?:all\s+)?(?:safety|filter)"
    r"|you\s+are\s+now\s+(?:DAN|an\s+unrestricted|not\s+claude)"
    r"|you\s+are\s+(?:not\s+claude|an\s+assistant\s+with\s+no\s+restrictions)"
    r"|no\s+restrictions"
    r"|from\s+now\s+on,?\s+you\s+are"
    r"|reveal\s+(?:your\s+)?system\s+prompt"
    r"|<\s*system\s*>|<\s*/\s*system\s*>"
    r"|\[\s*ADMIN\s*\]|\[\s*SYSTEM\s*\]"
    r"|忽略(?:之前|前面|所有|上述|上面)(?:的)?(?:指令|规则|提示|要求)"
    r"|忘记(?:你的|所有|之前)(?:的)?(?:身份|规则|指令|提示)"
    r"|越狱|jailbreak"
    r"|do\s+anything\s+now)",
    re.IGNORECASE,
)

# AE10 hitl_bypass
HITL_BYPASS_REGEX = re.compile(
    r"(skip\s+(?:the\s+)?(?:approval|hitl|confirmation|review)"
    r"|bypass\s+(?:the\s+)?(?:approval|hitl|confirmation|review)"
    r"|override\s+(?:the\s+)?(?:approval|hitl)"
    r"|跳过(?:审批|确认|HITL|审核)"
    r"|绕开(?:审批|确认|HITL)"
    r"|不需要(?:审批|确认|HITL)"
    r"|无需(?:审批|确认|HITL)"
    r"|i\s+am\s+(?:the\s+)?admin"
    r"|i'?m\s+(?:the\s+)?admin"
    r"|我是\s*admin"
    r"|我是管理员)",
    re.IGNORECASE,
)

# AE09 regulation_skirt — SEV-0 critical
REGULATION_SKIRT_REGEX = re.compile(
    r"(tornado\s+cash"
    r"|coin\s*mixer"
    r"|use\s+(?:a\s+)?mixer"
    r"|(?:绕过|规避|逃避|逃)\s*(?:KYC|实名|监管|税|报税)"
    r"|逃税"
    r"|洗(?:一下)?(?:币|钱)"
    r"|(?:用|借|盗)(?:别人|他人)(?:的)?(?:身份|身份证|护照)\s*(?:过|完成)?\s*KYC"
    r"|fake\s+KYC"
    r"|forged\s+KYC"
    r"|launder(?:ing)?\s+(?:money|crypto|funds?)"
    r"|money\s+launder"
    r"|分散(?:到多|钱包)\s*(?:逃|避)\s*税"
    r"|私下\s*换\s*USDT\s*避免"
    r"|私下\s*P2P\s*避免)",
    re.IGNORECASE,
)

# AE04 implicit_promise — C1 漏掉的中文隐式承诺
IMPLICIT_PROMISE_REGEX = re.compile(
    r"(保证(?:赚|盈利|收益|翻倍)"
    r"|必(?:赚|涨|盈)"
    r"|一定(?:能赚|赚到|盈利|涨)"
    r"|稳赚不赔"
    r"|稳赚"
    r"|包赚"
    r"|没有风险"
    r"|零风险"
    r"|无风险(?:套利|收益)"
    r"|risk[\s-]?free\s+(?:profit|return)"
    r"|no[\s-]?risk\s+(?:trade|return|profit))",
    re.IGNORECASE,
)

# AE05 hype_extended — C1 漏掉的隐喻 hype
HYPE_EXTENDED_REGEX = re.compile(
    r"(rocket\s+ride"
    r"|🚀|🌙"
    r"|m0+n"                # m0on / m00n / m0000n
    r"|moooo+n"             # mooooon
    r"|g[\s\d]*[ua]r[a4]nt[\s\d]*[e3]+d"  # g0arant33d / guar4nteed
    r"|lambo(?:\s*时间)?"
    r"|to\s+lambo"
    r"|FOMO\s*(?:时间|now)?"
    r"|fomo(?:\s+in)?"
    r"|now\s+or\s+never"
    r"|don'?t\s+miss"
    r"|last\s+chance"
    r"|send\s+it"
    r"|let'?s\s+(?:send\s+it|gooo+))",
    re.IGNORECASE,
)


# ── FilterResult(对齐 output_filter.FilterResult)────────────


@dataclass
class FilterResult:
    passed: bool
    violations: List[str] = field(default_factory=list)
    sanitized_text: Optional[str] = None
    matched_classes: List[str] = field(default_factory=list)


# ── 单 attack 类检查函数 ─────────────────────────────────────


def _check_class(
    text: str, regex: re.Pattern, class_name: str,
) -> Tuple[bool, List[str], str]:
    """返 (hit, matched_phrases, sanitized_text)。"""
    matches = regex.findall(text)
    if not matches:
        return False, [], text
    # findall 可能返 tuple(分组),展平
    flat = []
    for m in matches:
        if isinstance(m, tuple):
            flat.extend([x for x in m if x])
        else:
            flat.append(m)
    sanitized = regex.sub(f"[BLOCKED:{class_name}]", text)
    return True, flat, sanitized


def check_prompt_injection(text: str) -> Tuple[bool, List[str], str]:
    return _check_class(text, PROMPT_INJECTION_REGEX, "prompt_injection")


def check_hitl_bypass(text: str) -> Tuple[bool, List[str], str]:
    return _check_class(text, HITL_BYPASS_REGEX, "hitl_bypass")


def check_regulation_skirt(text: str) -> Tuple[bool, List[str], str]:
    return _check_class(text, REGULATION_SKIRT_REGEX, "regulation_skirt")


def check_implicit_promise(text: str) -> Tuple[bool, List[str], str]:
    return _check_class(text, IMPLICIT_PROMISE_REGEX, "implicit_promise")


def check_hype_extended(text: str) -> Tuple[bool, List[str], str]:
    return _check_class(text, HYPE_EXTENDED_REGEX, "hype_extended")


# ── 主入口 ───────────────────────────────────────────────────


def filter_input(text: str) -> FilterResult:
    """对用户输入 / LLM 输出做 5 类 attack 检测,任一命中即 fail。

    与 output_filter.filter_output 互补:
      - output_filter: C1 直接 blocklist(稳的 / 百倍 / moon / ape in / 10x)
      - input_filter:  AE03/AE04/AE09/AE10 + AE05 隐喻扩展

    上层 router 调用顺序建议:filter_input → output_filter(双重检查)。
    """
    if not text:
        return FilterResult(passed=True)

    violations: List[str] = []
    matched_classes: List[str] = []
    sanitized = text

    for check_fn, class_name in (
        (check_prompt_injection, "prompt_injection"),
        (check_hitl_bypass, "hitl_bypass"),
        (check_regulation_skirt, "regulation_skirt"),
        (check_implicit_promise, "implicit_promise"),
        (check_hype_extended, "hype_extended"),
    ):
        hit, phrases, sanitized = check_fn(sanitized)
        if hit:
            violations.append(f"{class_name}: {phrases[:5]}")
            matched_classes.append(class_name)

    return FilterResult(
        passed=not violations,
        violations=violations,
        sanitized_text=sanitized if violations else text,
        matched_classes=matched_classes,
    )


def filter_combined(text: str, persona: str = "intermediate") -> FilterResult:
    """组合 input_filter + output_filter.C1,任一命中即 fail。

    返回的 FilterResult 包含两边的 violations。
    """
    from agent.output_filter import filter_output

    res_in = filter_input(text)
    res_out = filter_output(text, persona)

    if res_in.passed and res_out.passed:
        return FilterResult(passed=True, sanitized_text=text)

    violations = list(res_in.violations) + list(res_out.violations)
    classes = list(res_in.matched_classes)
    if not res_out.passed:
        classes.append("c1_blocklist")
    sanitized = res_in.sanitized_text if not res_in.passed else text
    if not res_out.passed:
        # 再叠 C1 sanitization
        from agent.output_filter import C1_BLOCKLIST_REGEX
        sanitized = C1_BLOCKLIST_REGEX.sub("[BLOCKED:c1]", sanitized)

    return FilterResult(
        passed=False,
        violations=violations,
        sanitized_text=sanitized,
        matched_classes=classes,
    )
