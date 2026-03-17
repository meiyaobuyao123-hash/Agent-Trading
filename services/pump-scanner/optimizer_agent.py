"""
Self-Optimizing Agent — 自动分析监控数据 + 优化推荐算法

使用 Claude Opus 4.6 作为推理引擎，配合专用工具集，
自主完成：读取数据 → 分析问题 → 回测验证 → 提交方案。

触发方式：Governor 每3天调用一次 run_optimization()
方案审批：写入 DB 后由用户在 Portal 审批

注意：这里的"好推荐"不是简单的"是否毕业"，而是基于实际价格涨幅。
pump.fun 代币毕业只意味着 BC 完成，毕业后可能暴涨也可能归零。
真正的好推荐 = 推荐时买入后价格涨幅 >= 50%。
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import anthropic

from database import get_db
from optimizer_tools import TOOL_DEFINITIONS, TOOL_MAP

log = logging.getLogger(__name__)

# 配置
OPTIMIZER_API_KEY = os.getenv("OPTIMIZER_API_KEY", "")
OPTIMIZER_MODEL = "claude-opus-4-6"

# 量化目标（Agent 需要达成的指标）
TARGETS = {
    "hit_rate_7d": 0.20,     # 7天命中率 >= 20%（推荐的代币中涨>=50%的比例）
    "recall_7d": 0.15,       # 7天召回率 >= 15%（所有涨>=50%的代币中我们推荐了多少）
    "f1_7d": 0.17,           # F1 >= 0.17（precision 和 recall 的调和平均）
}

SYSTEM_PROMPT = """你是 pump.fun 代币推荐系统的量化优化 Agent。

## 你的目标
从 pump.fun 全量发射的代币里，及时找出有涨幅潜力但还没涨起来的代币。

## 量化指标
- **命中率 (precision/hit_rate)**: 推荐的代币中，后来价格涨幅 >= 50% 的比例。目标 >= 20%
- **召回率 (recall)**: 所有涨幅 >= 50% 的代币中，我们提前推荐了多少。目标 >= 15%
- **F1 Score**: precision 和 recall 的调和平均。目标 >= 0.17

## 重要理解
- "好代币" = 价格涨幅 >= 50% 或 毕业（BC完成）。不能只看毕业。
- pump.fun 代币毕业只意味着 bonding curve 收到了 85 SOL，毕业后在 DEX 上可能暴涨也可能归零。
- 价格涨幅是用 market_cap_sol 的变化来衡量的。
- 每天有 3000-50000 个新代币发射，只有极少数（<1%）会涨。

## 评分系统概览
7个维度打分（总分100）：
1. 买卖比(25分): 资金流向，买入SOL/卖出SOL
2. 聪明钱(20分): 分层加权（elite/verified/watching）
3. 流入加速(15分): 最近5min vs 之前的流入对比
4. Creator历史(15分): 创建者过去代币的成功率
5. 买家分散度(10分): unique_buyers 数量
6. Social完整度(10分): Twitter/TG/Website
7. 进度速度(5分): BC进度增速
+ 大单奖励(5分bonus)

信号池门槛: score >= 55 且 BC 进度在 3-35%

## 你可以做什么
1. 读取监控数据，了解当前表现
2. 读取评分代码和配置，理解当前逻辑
3. 查询历史代币数据，分析什么特征与"涨"相关
4. 用新参数回测，验证改善效果
5. 提交优化方案（需用户审批）

## 工作流程
1. 先用 read_metrics 了解当前状态
2. 用 query_tokens 分析命中/漏掉的代币特征差异
3. 提出假设（比如"social权重太高给了虚假信号"）
4. 用 backtest 验证假设
5. 如果回测改善，用 propose_change 提交方案
6. 如果回测没改善，尝试其他假设

## 规则
- 每次参数变动不超过原值的 30%
- 提交方案前必须回测
- 回测 F1 必须优于当前才能提交
- 用中文输出分析过程
- 保持诚实：如果数据不足无法优化，直接说明"""


def run_optimization() -> dict:
    """
    主入口：运行一次优化 Agent。
    返回 {run_id, status, proposals_count, ...}
    """
    if not OPTIMIZER_API_KEY:
        log.warning("OPTIMIZER_API_KEY 未配置，跳过优化")
        return {"status": "skipped", "reason": "no_api_key"}

    db = get_db()

    # 1. 创建运行记录
    run = db.table("optimization_runs").insert({
        "status": "running",
        "metrics_snapshot": {},
        "conversation": [],
    }).execute()
    run_id = run.data[0]["id"]
    log.info(f"🤖 Optimizer Agent 启动 — run_id={run_id}")

    client = anthropic.Anthropic(api_key=OPTIMIZER_API_KEY)

    # 2. 初始消息：告知当前指标和目标
    initial_msg = (
        f"当前是 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}。\n"
        f"优化运行 ID: {run_id}\n\n"
        f"量化目标:\n"
        f"- 命中率 (precision) >= {TARGETS['hit_rate_7d']*100:.0f}%\n"
        f"- 召回率 (recall) >= {TARGETS['recall_7d']*100:.0f}%\n"
        f"- F1 Score >= {TARGETS['f1_7d']}\n\n"
        f"请开始分析：\n"
        f"1. 先用 read_metrics 了解当前7天和14天的表现\n"
        f"2. 然后决定下一步分析方向"
    )

    messages = [{"role": "user", "content": initial_msg}]
    conversation_log = [{"role": "user", "content": initial_msg, "timestamp": _now()}]

    total_input_tokens = 0
    total_output_tokens = 0
    max_turns = 20  # 最多20轮对话
    proposals_count = 0

    try:
        for turn in range(max_turns):
            log.info(f"🤖 Optimizer turn {turn+1}/{max_turns}")

            # 带重试的 API 调用（处理 429/500 等临时错误）
            for attempt in range(3):
                try:
                    response = client.messages.create(
                        model=OPTIMIZER_MODEL,
                        max_tokens=4096,
                        system=SYSTEM_PROMPT,
                        tools=TOOL_DEFINITIONS,
                        messages=messages,
                    )
                    break
                except anthropic.RateLimitError as e:
                    if attempt < 2:
                        wait = 30 * (attempt + 1)
                        log.warning(f"🤖 API 429 限速，等待 {wait}s 后重试...")
                        time.sleep(wait)
                    else:
                        raise
                except anthropic.InternalServerError as e:
                    if attempt < 2:
                        wait = 10 * (attempt + 1)
                        log.warning(f"🤖 API 500 错误，等待 {wait}s 后重试...")
                        time.sleep(wait)
                    else:
                        raise

            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            # 记录 assistant 回复
            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                    conversation_log.append({
                        "role": "assistant",
                        "content": block.text,
                        "timestamp": _now(),
                    })
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
                    conversation_log.append({
                        "role": "assistant",
                        "tool_call": block.name,
                        "input": block.input,
                        "timestamp": _now(),
                    })

            messages.append({"role": "assistant", "content": response.content})

            # 如果 Agent 完成了（没有 tool_use）
            if response.stop_reason == "end_turn":
                final_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text += block.text
                log.info(f"🤖 Optimizer 完成分析")
                break

            # 处理 tool calls
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

                        log.info(f"🔧 调用工具: {tool_name}({json.dumps(tool_input, ensure_ascii=False)[:100]})")

                        try:
                            # 特殊处理：propose_change 需要注入 run_id
                            if tool_name == "propose_change":
                                tool_input["run_id"] = run_id

                            handler = TOOL_MAP.get(tool_name)
                            if handler:
                                result = handler(tool_input)
                                proposals_count += 1 if tool_name == "propose_change" else 0
                            else:
                                result = {"error": f"未知工具: {tool_name}"}

                            result_json = json.dumps(result, ensure_ascii=False, default=str)
                            # 截断过长的结果（避免触发 rate limit）
                            if len(result_json) > 15000:
                                result_json = result_json[:15000] + "...(truncated)"

                        except Exception as e:
                            log.error(f"工具 {tool_name} 执行失败: {e}")
                            result_json = json.dumps({"error": str(e)})

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_json,
                        })

                        conversation_log.append({
                            "role": "tool",
                            "tool": tool_name,
                            "result_preview": result_json[:500],
                            "timestamp": _now(),
                        })

                messages.append({"role": "user", "content": tool_results})

        # 3. 计算费用（Opus 4.6 定价估算）
        cost = (total_input_tokens / 1_000_000) * 15 + (total_output_tokens / 1_000_000) * 75

        # 4. 提取最终分析文本
        analysis_text = ""
        for entry in reversed(conversation_log):
            if entry["role"] == "assistant" and "content" in entry:
                analysis_text = entry["content"]
                break

        # 5. 更新运行记录
        db.table("optimization_runs").update({
            "status": "completed",
            "conversation": conversation_log,
            "analysis": analysis_text,
            "tokens_used": total_input_tokens + total_output_tokens,
            "cost_usd": round(cost, 4),
            "completed_at": _now(),
        }).eq("id", run_id).execute()

        log.info(
            f"🤖 Optimizer 完成 — run_id={run_id}, "
            f"turns={turn+1}, proposals={proposals_count}, "
            f"tokens={total_input_tokens+total_output_tokens}, "
            f"cost=${cost:.4f}"
        )

        return {
            "run_id": run_id,
            "status": "completed",
            "turns": turn + 1,
            "proposals_count": proposals_count,
            "tokens_used": total_input_tokens + total_output_tokens,
            "cost_usd": round(cost, 4),
        }

    except Exception as e:
        log.error(f"🤖 Optimizer 异常: {e}", exc_info=True)

        # 标记失败
        db.table("optimization_runs").update({
            "status": "failed",
            "conversation": conversation_log,
            "analysis": f"运行失败: {str(e)}",
            "tokens_used": total_input_tokens + total_output_tokens,
            "completed_at": _now(),
        }).eq("id", run_id).execute()

        return {
            "run_id": run_id,
            "status": "failed",
            "error": str(e),
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ══════════════════════════════════════════════════════
# 审批执行：用户在 Portal approve 后调用
# ══════════════════════════════════════════════════════

def apply_proposal(proposal_id: int) -> dict:
    """
    应用一个已批准的优化方案。
    修改 config.py 和/或 scorer.py 的参数。
    """
    db = get_db()

    res = db.table("optimization_proposals") \
        .select("*") \
        .eq("id", proposal_id) \
        .single() \
        .execute()
    proposal = res.data

    if not proposal:
        return {"error": "方案不存在"}
    if proposal["status"] != "approved":
        return {"error": f"方案状态为 {proposal['status']}，不是 approved"}

    changes = proposal.get("changes") or []
    base_dir = os.path.dirname(os.path.abspath(__file__))

    applied = []
    for change in changes:
        file_name = change.get("file", "")
        param = change.get("param", "")
        new_val = change.get("new")

        if file_name == "config.py":
            _apply_config_change(base_dir, param, new_val)
            applied.append(f"config.py: {param} = {new_val}")
        elif file_name == "scorer.py":
            # 评分权重变更需要特殊处理
            applied.append(f"scorer.py: {param} 权重调整为 {new_val} (需重启生效)")

    # 更新方案状态
    db.table("optimization_proposals").update({
        "status": "applied",
        "applied_at": _now(),
    }).eq("id", proposal_id).execute()

    log.info(f"✅ 方案 #{proposal_id} 已应用: {applied}")

    return {
        "proposal_id": proposal_id,
        "status": "applied",
        "changes_applied": applied,
        "message": "方案已应用，需要重启服务才能生效",
    }


def _apply_config_change(base_dir: str, param: str, new_val):
    """修改 config.py 中的参数值"""
    config_path = os.path.join(base_dir, "config.py")

    with open(config_path, "r") as f:
        lines = f.readlines()

    updated = False
    for i, line in enumerate(lines):
        # 匹配 PARAM_NAME = value 格式
        stripped = line.strip()
        if stripped.startswith(param) and "=" in stripped:
            parts = stripped.split("=", 1)
            if parts[0].strip() == param:
                # 保留注释
                comment = ""
                if "#" in parts[1]:
                    val_part, comment = parts[1].rsplit("#", 1)
                    comment = f"  # {comment.strip()}"

                # 格式化新值
                if isinstance(new_val, float):
                    new_line = f"{param:<25s}= {new_val}{comment}\n"
                elif isinstance(new_val, int):
                    new_line = f"{param:<25s}= {new_val}{comment}\n"
                else:
                    new_line = f"{param:<25s}= {new_val}{comment}\n"

                lines[i] = new_line
                updated = True
                break

    if updated:
        with open(config_path, "w") as f:
            f.writelines(lines)
        log.info(f"📝 config.py 已更新: {param} = {new_val}")
    else:
        log.warning(f"⚠️ config.py 中未找到参数: {param}")
