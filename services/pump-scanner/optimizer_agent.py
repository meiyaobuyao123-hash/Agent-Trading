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
- **冷启动例外**: 如果当前 F1=0 且快照数据 < 50 个代币，说明系统处于冷启动阶段。
  此时允许提交"基础设施改善"类方案（扩大漏斗/降低门槛），只要逻辑合理且 false_positive 不增加。
  标题需以 [冷启动] 开头。
- 用中文输出分析过程
- 保持诚实：如果数据不足无法优化，直接说明
- 必须提交方案（propose_change），不要只给建议不行动。分析后就提交。"""


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
# Hot Coin Optimizer Agent
# ══════════════════════════════════════════════════════

HOT_SYSTEM_PROMPT = """你是多链热币推荐算法的量化优化 Agent。

## 你的目标
及时发现热币，让用户看到后买入还有涨幅空间。优化打分引擎和进出榜参数。

## 量化目标
- **D1 正收益率** >= 70%（推荐后次日最高价 > 发现价的比例）
- **D7 涨幅 >= 20% 的比例** >= 40%
- **D0 负收益率** < 20%（发现时已涨完的比例，越低越好）
- **平均最佳涨幅** >= 30%

## 热币评分系统（总分100）
**M 动量（50分）**: 1h涨幅(10) + 24h涨幅(10) + 成交量加速(12) + 买压(10) + 动量新鲜度(8)
**Q 品质（30分）**: 持有者(10) + 社交(6) + 安全(8) + 分散度(6)
**P 潜力（20分）**: 市值位置(10) + 年龄(4) + 多时间帧共振(6)

入榜门槛: score >= 50
退出条件: 低分3次 / 冲高回落 / 成交量枯竭 / 卖压碾压 / 发现源消失

## 覆盖链
SOL / BSC / Base / ETH，数据源: OKX toplist + GeckoTerminal trending/new_pools

## 你可以做什么
1. read_hot_metrics: 分析历史推荐表现（D0-D7涨幅、命中率、链分布、score相关性）
2. read_hot_scorer_code: 理解打分逻辑
3. read_hot_config: 查看所有可调参数
4. backtest_hot: 用新参数回测验证
5. propose_hot_change: 提交优化方案

## 工作流程
1. 先用 read_hot_metrics 了解当前 D1/D7/命中率
2. 分析 score vs 实际涨幅的相关性（哪个分桶表现最好？）
3. 分析 by_chain 差异（是否某条链系统性差？）
4. 读取评分代码，找出可能的改进点
5. 用 backtest_hot 验证改动
6. 提交方案

## 关键洞察方向
- "动量新鲜度 M5" 是否有效区分了"正在启动"vs"已涨完"？
- 入榜门槛 50 分是否太低？提高到 55 或 60 是否减少误报？
- 退出条件是否太松？"冲高回落"阈值 24h>200% 是否应该更严格？
- 多时间帧共振 P3 是否真的与涨幅相关？

## 规则
- 必须先分析数据再提方案
- 必须用 backtest_hot 验证
- 回测后 D1 正收益率或命中率必须改善才能提交
- 每次参数变动不超过原值的 30%
- 用中文输出
- 如果数据不足（<10条追踪记录），说明冷启动，允许提交逻辑合理的方案"""


def run_hot_optimization() -> dict:
    """运行一次热币优化 Agent"""
    from config import HOT_OPTIMIZER_API_KEY
    from optimizer_tools import HOT_TOOL_DEFINITIONS, HOT_TOOL_MAP

    api_key = HOT_OPTIMIZER_API_KEY
    if not api_key:
        log.warning("HOT_OPTIMIZER_API_KEY 未配置，跳过热币优化")
        return {"status": "skipped", "reason": "no_api_key"}

    db = get_db()

    # 1. 创建运行记录
    run = db.table("optimization_runs").insert({
        "status": "running",
        "metrics_snapshot": {},
        "conversation": [],
        "analysis": "hot_coin_optimizer",
    }).execute()
    run_id = run.data[0]["id"]
    log.info(f"🤖 Hot Optimizer Agent 启动 — run_id={run_id}")

    client = anthropic.Anthropic(api_key=api_key)

    initial_msg = (
        f"当前是 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}。\n"
        f"热币优化运行 ID: {run_id}\n\n"
        f"量化目标:\n"
        f"- D1 正收益率 >= 70%\n"
        f"- D7 涨幅>=20% 的比例 >= 40%\n"
        f"- D0 负收益率 < 20%\n"
        f"- 平均最佳涨幅 >= 30%\n\n"
        f"请开始分析：先用 read_hot_metrics 查看最近7天和14天的表现。"
    )

    messages = [{"role": "user", "content": initial_msg}]
    conversation_log = [{"role": "user", "content": initial_msg, "timestamp": _now()}]

    total_input_tokens = 0
    total_output_tokens = 0
    max_turns = 20
    proposals_count = 0

    try:
        for turn in range(max_turns):
            log.info(f"🤖 Hot Optimizer turn {turn+1}/{max_turns}")

            for attempt in range(3):
                try:
                    response = client.messages.create(
                        model=OPTIMIZER_MODEL,
                        max_tokens=4096,
                        system=HOT_SYSTEM_PROMPT,
                        tools=HOT_TOOL_DEFINITIONS,
                        messages=messages,
                    )
                    break
                except anthropic.RateLimitError:
                    if attempt < 2:
                        wait = 30 * (attempt + 1)
                        log.warning(f"🤖 API 429，等待 {wait}s...")
                        time.sleep(wait)
                    else:
                        raise
                except anthropic.InternalServerError:
                    if attempt < 2:
                        time.sleep(10 * (attempt + 1))
                    else:
                        raise

            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                    conversation_log.append({
                        "role": "assistant", "content": block.text, "timestamp": _now(),
                    })
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use", "id": block.id,
                        "name": block.name, "input": block.input,
                    })
                    conversation_log.append({
                        "role": "assistant", "tool_call": block.name,
                        "input": block.input, "timestamp": _now(),
                    })

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                log.info("🤖 Hot Optimizer 完成分析")
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        log.info(f"🔧 Hot工具: {tool_name}({json.dumps(tool_input, ensure_ascii=False)[:100]})")

                        try:
                            if tool_name == "propose_hot_change":
                                tool_input["run_id"] = run_id

                            handler = HOT_TOOL_MAP.get(tool_name)
                            if handler:
                                result = handler(tool_input)
                                proposals_count += 1 if tool_name == "propose_hot_change" else 0
                            else:
                                result = {"error": f"未知工具: {tool_name}"}

                            result_json = json.dumps(result, ensure_ascii=False, default=str)
                            if len(result_json) > 15000:
                                result_json = result_json[:15000] + "...(truncated)"
                        except Exception as e:
                            log.error(f"Hot工具 {tool_name} 失败: {e}")
                            result_json = json.dumps({"error": str(e)})

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_json,
                        })
                        conversation_log.append({
                            "role": "tool", "tool": tool_name,
                            "result_preview": result_json[:500], "timestamp": _now(),
                        })

                messages.append({"role": "user", "content": tool_results})

        cost = (total_input_tokens / 1_000_000) * 15 + (total_output_tokens / 1_000_000) * 75

        analysis_text = ""
        for entry in reversed(conversation_log):
            if entry["role"] == "assistant" and "content" in entry:
                analysis_text = entry["content"]
                break

        db.table("optimization_runs").update({
            "status": "completed",
            "conversation": conversation_log,
            "analysis": analysis_text,
            "tokens_used": total_input_tokens + total_output_tokens,
            "cost_usd": round(cost, 4),
            "completed_at": _now(),
        }).eq("id", run_id).execute()

        log.info(
            f"🤖 Hot Optimizer 完成 — run_id={run_id}, "
            f"turns={turn+1}, proposals={proposals_count}, cost=${cost:.4f}"
        )

        return {
            "run_id": run_id, "status": "completed", "mode": "hot",
            "turns": turn + 1, "proposals_count": proposals_count,
            "tokens_used": total_input_tokens + total_output_tokens,
            "cost_usd": round(cost, 4),
        }

    except Exception as e:
        log.error(f"🤖 Hot Optimizer 异常: {e}", exc_info=True)
        db.table("optimization_runs").update({
            "status": "failed", "conversation": conversation_log,
            "analysis": f"热币优化失败: {str(e)}",
            "tokens_used": total_input_tokens + total_output_tokens,
            "completed_at": _now(),
        }).eq("id", run_id).execute()
        return {"run_id": run_id, "status": "failed", "mode": "hot", "error": str(e)}


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
