"""
verify_pricing.py — 对照 LiteLLM 社区维护的权威源比对本地 pricing.yaml

LiteLLM 是被广泛使用的 LLM gateway,他们维护一份 model_prices_and_context_window.json
作为业界事实标准(覆盖 Anthropic / OpenAI / Google 等),社区紧跟官方价更新。

跑法:
  cd services/pump-scanner
  python3 scripts/verify_pricing.py

退出码:
  0  本地价跟 LiteLLM 一致
  1  本地价跟 LiteLLM 不一致(打 diff)
  2  网络失败 — 不阻塞,允许离线开发(打 warning)

CI 集成:
  - main 分支 PR 必跑(失败 = block merge)
  - 本地开发 + 改价后必跑

R51 — Anthropic 改价时手工/CI 触发,而非自动同步(避免静默改价)
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

import yaml  # type: ignore

LITELLM_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
TIMEOUT_SEC = 10
TOLERANCE_PCT = 0.01  # 0.01% 容差(浮点 round-off)

# 价格字段映射 (LiteLLM key → 我们 yaml in/out 单价)
# LiteLLM 价是 per token (USD),我们 yaml 是 per 1M tokens
LITELLM_IN_KEY = "input_cost_per_token"
LITELLM_OUT_KEY = "output_cost_per_token"


def load_local() -> dict:
    p = Path(__file__).parent.parent / "agent" / "pricing.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def fetch_litellm() -> dict:
    try:
        with urlopen(LITELLM_URL, timeout=TIMEOUT_SEC) as r:
            return json.loads(r.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError) as e:
        print(f"⚠ verify_pricing: network fail ({e}). Skipping check (exit 2).")
        sys.exit(2)


def main() -> int:
    local = load_local()
    print(f"Local pricing.yaml last_verified={local.get('last_verified')}")

    litellm = fetch_litellm()
    print(f"Fetched {len(litellm)} models from LiteLLM")

    diffs = []
    matched = 0
    skipped = 0

    for model_id, our_price in local.get("models", {}).items():
        ll = litellm.get(model_id)
        if not ll:
            print(f"  ? {model_id:40s} — not in LiteLLM (skipped)")
            skipped += 1
            continue
        ll_in = float(ll.get(LITELLM_IN_KEY, 0)) * 1_000_000  # → per 1M
        ll_out = float(ll.get(LITELLM_OUT_KEY, 0)) * 1_000_000
        our_in = float(our_price["in"])
        our_out = float(our_price["out"])

        in_diff = abs(ll_in - our_in) / max(our_in, 1e-9)
        out_diff = abs(ll_out - our_out) / max(our_out, 1e-9)

        if in_diff > TOLERANCE_PCT or out_diff > TOLERANCE_PCT:
            diffs.append({
                "model": model_id,
                "our": {"in": our_in, "out": our_out},
                "litellm": {"in": ll_in, "out": ll_out},
            })
            print(f"  ✗ {model_id:40s} ours=in${our_in:.4f}/out${our_out:.4f} "
                  f"litellm=in${ll_in:.4f}/out${ll_out:.4f}")
        else:
            matched += 1
            print(f"  ✓ {model_id:40s} in${our_in:.2f}/out${our_out:.2f}")

    print()
    print(f"Result: matched={matched} / diff={len(diffs)} / skipped={skipped}")

    if diffs:
        print()
        print("ACTION REQUIRED: Update agent/pricing.yaml to match LiteLLM,")
        print("then bump last_verified date and commit.")
        print()
        print("Diff details:")
        print(json.dumps(diffs, indent=2))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
