"""
回归测试:2026-06 Agent 审计修复批次。
覆盖本批已修的、可纯逻辑验证的真 bug。
重依赖(anthropic/supabase)路径的修复(notify_loop/wal/global_state/proactive)
在 conftest 完整依赖装好后由各自模块测试 + 服务器 CI 覆盖。
"""
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Fix 1: rule_engine 空条件树必须 fail-closed(返 False,不再无条件触发)──
def test_empty_condition_node_returns_false():
    from agent.rule_engine import evaluate_conditions
    from agent.schemas import ConditionNode

    # 空 rules 的 AND 节点
    node = ConditionNode(operator="AND", rules=[])
    assert evaluate_conditions(node, {"score": 99}) is False, \
        "空条件树必须返回 False(永不触发),否则 buy 动作会对每个事件无条件下单"

    # 空 rules 的 OR 节点同理
    node_or = ConditionNode(operator="OR", rules=[])
    assert evaluate_conditions(node_or, {"score": 99}) is False


def test_nonempty_condition_still_works():
    """确认修复没破坏正常条件求值。"""
    from agent.rule_engine import evaluate_conditions
    from agent.schemas import ConditionNode, ConditionRule

    rule = ConditionRule(data_source="pump_tokens", field="score",
                         operator=">=", value=70)
    node = ConditionNode(operator="AND", rules=[rule])
    assert evaluate_conditions(node, {"pump_tokens.score": 80}) is True
    assert evaluate_conditions(node, {"pump_tokens.score": 50}) is False


# ── Fix 2: position_monitor._hold_seconds 不再恒为 0 ──
def test_hold_seconds_computed_from_created_at():
    from agent.position_monitor import _hold_seconds

    # 空/非法 → 0
    assert _hold_seconds("") == 0.0
    assert _hold_seconds(None) == 0.0
    assert _hold_seconds("garbage") == 0.0

    # 1 小时前 → ≈3600s(允许少量误差)
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    held = _hold_seconds(one_hour_ago)
    assert 3590 <= held <= 3700, f"持仓 1h 应约 3600s,实际 {held}"

    # Z 后缀也能解析
    z_form = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    held_z = _hold_seconds(z_form)
    assert 590 <= held_z <= 700


# ── Fix 9: paper_engine 写入前归一化 sl/tp 单位(防 ratio 仓卡死)──
def test_paper_normalize_pct_unit():
    from agent.paper_engine import _normalize_pct_unit

    # ratio 误存 → ×100
    assert _normalize_pct_unit(0.1) == 10.0
    assert _normalize_pct_unit(0.3) == 30.0
    assert _normalize_pct_unit(0.25) == 25.0
    # 正常 percent 不动
    assert _normalize_pct_unit(10) == 10.0
    assert _normalize_pct_unit(30) == 30.0
    assert _normalize_pct_unit(90) == 90.0
    # 无效/<=0 → 默认 25
    assert _normalize_pct_unit(0) == 25.0
    assert _normalize_pct_unit(-5) == 25.0
    assert _normalize_pct_unit(None) == 25.0
    assert _normalize_pct_unit("garbage") == 25.0
    # 归一化后必定 >=1(不会再被 paper check 循环跳过)
    for v in [0.01, 0.1, 0.5, 0.99]:
        assert _normalize_pct_unit(v) >= 1.0


# ── Fix 10: L2 健壮 JSON 解析(防模型加前言/markdown → 静默 hold 丢信号)──
def test_l2_safe_json_parse():
    from agent.multi_role_orchestrator import _safe_json_parse

    # 纯 JSON
    assert _safe_json_parse('{"action":"buy","confidence":0.8}')["action"] == "buy"
    # 带前言
    assert _safe_json_parse('好的,我的判断:{"action":"sell","confidence":0.6}')["action"] == "sell"
    # markdown 围栏
    assert _safe_json_parse('```json\n{"action":"hold"}\n```')["action"] == "hold"
    # 多行 + 尾注
    assert _safe_json_parse('结论\n{"action": "buy",\n "confidence": 0.9}\n以上')["action"] == "buy"
    # 真无法解析 → None
    assert _safe_json_parse("完全没有 json") is None
    assert _safe_json_parse("") is None


if __name__ == "__main__":
    test_empty_condition_node_returns_false()
    test_nonempty_condition_still_works()
    test_hold_seconds_computed_from_created_at()
    test_paper_normalize_pct_unit()
    test_l2_safe_json_parse()
    print("ALL PASS")
