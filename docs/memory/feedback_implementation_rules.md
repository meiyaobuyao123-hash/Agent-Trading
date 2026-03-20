---
name: 实现落地工作规则
description: 防止讨论了但代码没按讨论做的强制流程
type: feedback
---

**规则：讨论完 → 实现前必须先验证接口可用，实现后必须 grep 验证**

**Why:** 多次出现"讨论确定方案 → 实现时用了错误数据源"的问题。
例：讨论用 OKX Wallet API，实现后发现需要 accountId 不可用；
例：`refresh_okx_prices` 函数名是 OKX 实际用的 DexScreener。

**How to apply：**

## 第一步：讨论完数据源方案后，必须先跑一个 curl/python 验证

在写任何代码之前，必须先验证 API 接口真实可用：
```bash
# 例：讨论用 OKX Wallet API 前，先测试
python3 -c "import aiohttp, asyncio; ..."
```
如果验证失败 → 立刻告知用户，不得写入代码后再发现。

## 第二步：实现完成后，必须 grep 验证关键实现

不能说"已完成"，必须用 grep 证明代码里真的有：
```bash
grep "OKX_WALLET_BASE\|get_toplist_multi_sort\|accountSubscribe" smart_money_tracker.py
```

## 第三步：每次新会话开始，主动检查上次的 [待验收] 条目

在 MEMORY.md 里标记 [待验收] 的事项，下次会话开始时第一件事是 grep 核对。

## 禁止行为

- ❌ 未验证 API 可用性就承诺某接口的延迟指标
- ❌ 实现时悄悄换数据源（如用 DexScreener 替代 OKX）但不告知用户
- ❌ 用函数名掩盖实际数据源（如 `refresh_okx_prices` 内用 DexScreener）
- ❌ 对用户说"已完成"但不提供 grep 验证结果
