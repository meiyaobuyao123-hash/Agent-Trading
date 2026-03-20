# 工作规则（强制执行）

## 记忆文件更新规则

### 立即更新（不等任务结束）
以下情况发生时，当场更新对应记忆文件：
1. 发现新的 URL / API Key / 凭证
2. API 踩坑（错误端点、错误参数、报错原因）
3. 用户纠正我的事情（纠正 = 旧记忆有误，必须立刻修正 + 告知）
4. 功能状态改变（新完成、废弃、参数变了）
5. 工作原则变更

### 任务完成后更新一次
- 推送代码 / 部署服务器之后
- 用户说"好了""完成""下一个"之后

### 会话结束时追加 sessions-log.md
格式固定，每次必写：
```
## YYYY-MM-DD 会话N
### 做了什么
### 讨论结论（为什么这么选，不是只记"做了什么"）
### 被否定的方案（为什么不选）
```
目的：跨会话保留决策上下文，防止下次会话重走弯路

### 记忆清理规则
- 某模块逻辑被改了 → 删除旧逻辑的记录，只保留新的
- 某结论被推翻了 → 删除旧结论，在 sessions-log.md 的新条目里说明原因
- sessions-log.md 超过300行 → 把3个月前的条目移入 sessions-archive.md

### 会话结束 checklist（每次收尾必查）
```
□ 新增/变更的线上 URL
□ 新增/变更的 API Key 或凭证
□ 发现的踩坑
□ 功能状态变更（已完成/已废弃）
□ 用户纠正我的事项
□ 工作规则变更
```

### MEMORY.md 结构约束
- 保持 <150 行，只放索引和高频核心事实
- 详细内容放 topic 文件，MEMORY.md 用指针引用
- 工作规则必须在顶部

### 双份同步规则（强制）
每次更新记忆文件，必须同时更新两处，内容完全一致：
1. 本地：`~/.claude/projects/.../memory/` 下的 topic 文件
2. 仓库：`/Users/wenruiwei/Desktop/Agent-Trading/CLAUDE.md`

CLAUDE.md 是仓库内的主记忆文件，换设备/换账户后唯一可靠的来源。
- 凭证（API Key、密码）不写入 CLAUDE.md（不能提交到 git），其余全部同步
- 凭证单独维护在本地 credentials.md，换设备后手动同步

---

## 数据源规则

### 必须遵守的数据源优先级
详见 [feedback_data_sources.md](./feedback_data_sources.md)

**EVM 聪明钱**: `web3.okx.com/api/v5/wallet/post-transaction/transactions-by-address`
- ❌ 禁止: Etherscan / BscScan / Basescan 作为主力
- ❌ 禁止: www.okx.com（403）

**SOL 聪明钱**: Helius `accountSubscribe` WebSocket
- ❌ 禁止: REST polling 作为主力

---

## 实现质量规则

### 讨论 → 实现流程
1. **讨论完方案 → 先验证 API 可用**，验证失败立刻告知，不写代码后再发现
2. **实现完成 → grep 验证**关键函数/变量存在，不得只说"已完成"

```bash
# 例：验证 OKX Web3 API 可用
python3 -c "import aiohttp, asyncio; ..."

# 例：grep 验证实现
grep "transactions-by-address\|accountSubscribe" smart_money_tracker.py
```

### 禁止行为
- ❌ 未验证 API 可用性就承诺延迟指标
- ❌ 实现时悄悄换数据源（如用 DexScreener 替代 OKX）但不告知
- ❌ 用函数名掩盖实际数据源（如 `refresh_okx_prices` 内用 DexScreener）
- ❌ 说"已完成"但不提供 grep 验证
- ❌ 告诉用户"做了"但实际没做——没做就说没做，做了必须有证据同步给用户

---

## 聪明钱地址供给规则（永久）

**目标**：维持 2000+ 个经过验证的活跃聪明钱地址库

**三层供给（全免费）**：
1. **自有数据挖掘**（每天 UTC 04:00）：smart_wallet_miner.py，从 token_trades 反推毕业代币早期买家
2. **热币 Top Holders**（实时）：入榜时 Helius/GoPlus 采集 Top 10 → D3涨20%+ 自动晋升
3. **Dune Analytics**（后续，每周）：SQL 查各链 DEX 高胜率交易者

**v3 五维度评估**（每 2h，14天滚动窗口）：
- 维度: 胜率(20) + PNL(20) + 交易规模(20) + 活跃度(20) + 时效性(20) = 100分
- elite≥75（且胜率≥15 PNL≥10）/ verified≥55 / watching≥35 / blacklisted<30
- 降级: 14天无交易降一级，28天无交易移除
- 实时bot检测: 60秒买卖同代币 / >2000笔/14天 → 立即黑名单

**禁止**：
- ❌ 网页爬虫（GMGN/OKX 等，会被封，不合法）
- ❌ 手动拍脑袋编地址
- ❌ 付费 API（Nansen/Arkham/Birdeye，当前免费方案够用）

---

## 用户偏好
- 始终使用中文输出
- 报告要有真实数据，不要粗糙概述
- 不要给时间估计
- 不要过度工程化，只做被要求的改动
