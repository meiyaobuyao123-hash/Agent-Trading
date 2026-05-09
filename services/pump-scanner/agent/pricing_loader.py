"""
R52 — 动态价格加载器

为什么:
  pricing.yaml 写死,Anthropic 涨价/跌价后我们手动改才能跟上 → 期间用错价(贵了客户骂,
  便宜了我们贴钱)。这个 loader 每 6h 从 LiteLLM(社区维护的 200+ 模型权威价格表)拉一次
  最新价,本地 dict 缓存,文件持久化兜底,yaml 最后兜底。

数据源:
  https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
  - 无需 API key
  - LiteLLM 通常在 Anthropic 改价后几小时内同步
  - JSON 内每个模型有 input_cost_per_token / output_cost_per_token(USD per 1 token)

使用:
  from agent.pricing_loader import get_price, refresh_pricing

  # calc_cost 调用方
  p = get_price("claude-sonnet-4-20250514")  # → {"in": 3.0, "out": 15.0} or None
  if p is None:
      raise UnknownModelError(...)  # 不"瞎算"

  # main.py cron 调用方(6h 一次)
  await refresh_pricing()  # 拉 LiteLLM,失败静默,retain 旧值

模型 ID 归一化:
  我们代码混用 "claude-sonnet-4-20250514"(API 老格式)和 "claude-sonnet-4-6"(LiteLLM 格式)
  loader 内部维护 alias 映射:strip 日期后缀 + 加 anthropic/ 前缀去 LiteLLM 查
  alias 表见 _MODEL_ALIASES。

并发安全:
  - module-level dict + threading.Lock
  - get_price 是 lock-free 读(GIL 保护 dict 读)
  - refresh_pricing 写时持锁

失败行为:
  - LiteLLM 网络失败 → 保留旧值(进程内 cache)+ 写日志
  - 进程重启 → 从 pricing_cache.json 读,失败再 fallback yaml
  - 未知模型 → get_price 返 None(caller 必须处理,不 fallback 到 sonnet 价"瞎算")

Python 3.9 兼容。
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

# ── 数据源 ──────────────────────────────────────────────────
LITELLM_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)
LITELLM_FETCH_TIMEOUT_S = 10
CACHE_FILE = Path(__file__).parent / "pricing_cache.json"

# ── 模型 ID 归一化:把项目里五花八门的 ID 映射到 LiteLLM 标准 ID ──
# 项目代码里出现的 ID(键)→ LiteLLM JSON 里的 key(值)
# LiteLLM 直接用 claude-* 开头,无 "anthropic/" 前缀
# (用 anthropic/* 前缀的是 LiteLLM 内的另一组旧 key,没维护新模型)
_MODEL_ALIASES: Dict[str, str] = {
    # ─── Sonnet 4 / 4.5 / 4.6(都是 $3/$15)─────
    "claude-sonnet-4-20250514":   "claude-sonnet-4-5",
    "claude-sonnet-4-5":          "claude-sonnet-4-5",
    "claude-sonnet-4-6":          "claude-sonnet-4-6",  # LiteLLM 有这个 key
    "claude-sonnet-4-6-20251022": "claude-sonnet-4-6",
    # ─── Haiku 4.5($1/$5 per MTok — 注意不是 $0.25)─────
    "claude-haiku-4-5":           "claude-haiku-4-5",
    "claude-haiku-4-5-20251001":  "claude-haiku-4-5-20251001",
    # ─── Opus 4.1($15/$75)/ 4.5+ 降到 $5/$25 ─────
    # R52:项目里历史代码混用 4-1 / 4-6 / 4-7,都映射到对应真模型
    # 升级路径:用 4-7(最新 + 便宜 3 倍 vs 4-1)
    "claude-opus-4-1":            "claude-opus-4-1",         # $15/$75
    "claude-opus-4-5":            "claude-opus-4-5",         # $5/$25
    "claude-opus-4-6":            "claude-opus-4-6",         # $5/$25
    "claude-opus-4-7":            "claude-opus-4-7",         # $5/$25,推荐用这个
    "claude-opus-4-6-20251022":   "claude-opus-4-6",
    # ─── Claude 3.5 / 3 legacy ─────
    "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022":  "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229":     "claude-3-opus-20240229",
}

# ── 进程内 cache ─────────────────────────────────────────────
# {model_id: {"in": $/MTok, "out": $/MTok}}
_prices: Dict[str, Dict[str, float]] = {}
_last_refresh_ts: float = 0
_last_source: str = "init"  # "litellm" | "cache_file" | "yaml" | "init"
_lock = threading.Lock()


def _normalize(model: str) -> str:
    """模型 ID 归一化:返 LiteLLM JSON 里的 key。"""
    if not model:
        return ""
    if model in _MODEL_ALIASES:
        return _MODEL_ALIASES[model]
    # 自动 strip 日期后缀 "-YYYYMMDD"(8 位数字)
    parts = model.rsplit("-", 1)
    if len(parts) == 2 and len(parts[1]) == 8 and parts[1].isdigit():
        base = parts[0]
        if base in _MODEL_ALIASES:
            return _MODEL_ALIASES[base]
        return f"anthropic/{base}"
    # 直接加前缀试一次
    if not model.startswith("anthropic/"):
        return f"anthropic/{model}"
    return model


def _parse_litellm(raw: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """LiteLLM JSON → {alias_id: {"in": $/MTok, "out": $/MTok}}。

    LiteLLM 里 input_cost_per_token = USD per 1 token(很小,如 3e-6)。
    我们代码 LLM_PRICES 用 USD per 1M token(如 3.0)→ 乘以 1_000_000。
    """
    out: Dict[str, Dict[str, float]] = {}
    for our_id, litellm_id in _MODEL_ALIASES.items():
        entry = raw.get(litellm_id)
        if not entry:
            continue
        in_per_tok = entry.get("input_cost_per_token")
        out_per_tok = entry.get("output_cost_per_token")
        if in_per_tok is None or out_per_tok is None:
            continue
        try:
            out[our_id] = {
                "in": float(in_per_tok) * 1_000_000,
                "out": float(out_per_tok) * 1_000_000,
            }
        except (TypeError, ValueError) as e:
            log.warning("[pricing] parse fail for %s: %s", litellm_id, e)
            continue
    return out


def _fetch_litellm() -> Optional[Dict[str, Dict[str, float]]]:
    """同步拉 LiteLLM JSON;失败返 None。"""
    try:
        import urllib.request

        req = urllib.request.Request(
            LITELLM_URL,
            headers={"User-Agent": "Agent-Trading/pricing-loader"},
        )
        with urllib.request.urlopen(req, timeout=LITELLM_FETCH_TIMEOUT_S) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        parsed = _parse_litellm(raw)
        if not parsed:
            log.warning("[pricing] LiteLLM returned empty after parse")
            return None
        log.info("[pricing] LiteLLM fetched %d models", len(parsed))
        return parsed
    except Exception as e:
        log.warning("[pricing] LiteLLM fetch failed: %s", e)
        return None


def _load_cache_file() -> Optional[Dict[str, Dict[str, float]]]:
    """从 pricing_cache.json 读上次 LiteLLM 拉的结果。"""
    try:
        if not CACHE_FILE.exists():
            return None
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        prices = data.get("prices") or {}
        if not isinstance(prices, dict) or not prices:
            return None
        # 简单 sanity check
        for k, v in prices.items():
            if not isinstance(v, dict) or "in" not in v or "out" not in v:
                return None
        log.info("[pricing] loaded %d models from cache file", len(prices))
        return prices
    except Exception as e:
        log.warning("[pricing] cache file load failed: %s", e)
        return None


def _save_cache_file(prices: Dict[str, Dict[str, float]]) -> None:
    """把当前 prices 写到 pricing_cache.json。"""
    try:
        CACHE_FILE.write_text(
            json.dumps({
                "prices": prices,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        log.warning("[pricing] cache file save failed: %s", e)


def _load_yaml_fallback() -> Dict[str, Dict[str, float]]:
    """最后兜底:pricing.yaml(防 LiteLLM + 文件都失败)。"""
    try:
        import yaml  # type: ignore

        p = Path(__file__).parent / "pricing.yaml"
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        models = data.get("models") or {}
        out = {}
        for mid, v in models.items():
            if isinstance(v, dict) and "in" in v and "out" in v:
                out[mid] = {"in": float(v["in"]), "out": float(v["out"])}
        log.info("[pricing] yaml fallback loaded %d models", len(out))
        return out
    except Exception as e:
        log.error("[pricing] yaml fallback failed (last resort gone): %s", e)
        return {}


# ── Public API ──────────────────────────────────────────────

def get_price(model: str) -> Optional[Dict[str, float]]:
    """查模型价格。

    返 {"in": $/MTok, "out": $/MTok} 或 None(未知模型)。
    Caller 必须处理 None — 不 fallback 到默认价"瞎算"。
    """
    if not model:
        return None
    if not _prices:
        # 首次调用前没初始化 → 初始化(同步,不阻塞太久)
        _ensure_initialized()
    p = _prices.get(model)
    if p:
        return p
    # 试归一化后的 ID 反查(给 alias 表找原 key)
    norm = _normalize(model)
    for our_id, litellm_id in _MODEL_ALIASES.items():
        if litellm_id == norm and our_id in _prices:
            return _prices[our_id]
    return None


def get_status() -> Dict[str, Any]:
    """返当前价格 cache 状态(给 admin / debug 用)。"""
    return {
        "models_loaded": len(_prices),
        "last_refresh_ts": _last_refresh_ts,
        "last_refresh_iso": (
            datetime.fromtimestamp(_last_refresh_ts, tz=timezone.utc).isoformat()
            if _last_refresh_ts > 0 else None
        ),
        "last_source": _last_source,
        "stale_seconds": (
            int(time.time() - _last_refresh_ts) if _last_refresh_ts > 0 else None
        ),
    }


def refresh_pricing(force: bool = False) -> bool:
    """主动刷新价格表(从 LiteLLM 拉最新)。

    Args:
        force: True 时无视 cache 立刻拉

    Returns:
        True 表示拉到新值并更新,False 表示用旧值(或 cache 文件)。
    """
    global _prices, _last_refresh_ts, _last_source

    new = _fetch_litellm()
    if new is None:
        # LiteLLM 失败 — 决策(已确认):**继续**(用旧值)
        log.warning(
            "[pricing] refresh failed, retain existing %d models (last_source=%s)",
            len(_prices), _last_source,
        )
        return False

    with _lock:
        _prices = new
        _last_refresh_ts = time.time()
        _last_source = "litellm"
    _save_cache_file(new)
    log.info("[pricing] refreshed: %d models from LiteLLM", len(new))
    return True


def _ensure_initialized() -> None:
    """进程启动后第一次访问 get_price 时调一次。

    顺序:LiteLLM → cache file → yaml。
    """
    global _prices, _last_refresh_ts, _last_source
    with _lock:
        if _prices:
            return  # 已初始化(被另一线程抢先)

        # 1) 先试 cache file(快,2-3ms)
        cached = _load_cache_file()
        if cached:
            _prices = cached
            _last_refresh_ts = time.time()
            _last_source = "cache_file"
            log.info("[pricing] init from cache file (%d models)", len(cached))
            return

        # 2) cache 没 → 试 LiteLLM(同步,~1-3s,启动时只跑一次可接受)
        new = _fetch_litellm()
        if new:
            _prices = new
            _last_refresh_ts = time.time()
            _last_source = "litellm"
            _save_cache_file(new)
            log.info("[pricing] init from LiteLLM (%d models)", len(new))
            return

        # 3) 都失败 → yaml 兜底
        yaml_p = _load_yaml_fallback()
        _prices = yaml_p
        _last_refresh_ts = time.time()
        _last_source = "yaml"
        log.warning("[pricing] init fell back to yaml (%d models)", len(yaml_p))


# 进程导入时触发首次初始化(失败也不抛 — get_price 会再试)
try:
    _ensure_initialized()
except Exception as e:
    log.error("[pricing] import-time init failed (will retry on first get_price): %s", e)
