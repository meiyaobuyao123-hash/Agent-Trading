# AiTrading Agent v1 — 团队内测指南

> 给团队成员:**这是一个内测版,不要用真钱玩**(auto 模式已禁,paper 模式安全)
> 上线时间:2026-05-01;后端:http://43.156.207.26;Flutter App 见下方"安装"

---

## 1. 安装 App(三选一)

### iOS Ad-hoc(推荐)

1. 打开 IPA 链接(由项目负责人发到群里 / 邮件)
2. 设置 → 通用 → VPN 与设备管理 → **信任** 企业证书
3. 桌面找到 "AiTrading" 图标,打开

### Android APK

1. 下载 APK 文件
2. 设置 → 安全 → **允许未知来源**
3. 打开 APK → 安装

### iOS 模拟器(开发者模式,本地跑)

如果你是开发者:
```bash
cd /path/to/Agent-Trading/apps/app
flutter run -d <simulator_id> \
  --dart-define=API_BASE_URL=http://43.156.207.26 \
  --dart-define=HELIUS_API_KEY=<get from team lead>
```

---

## 2. 试什么(7 个核心功能)

### 2.1 Chat Tab — Thesis 分析

- 进 **Chat Tab**(底部 tab 之一)
- 输入 **"分析 TRUMP"** 或者 **"BTC 现在能买吗"**
- Agent 会拉真链上数据 + smart money 净流量 + 技术指标 → 输出 **Thesis 卡片**
- 卡片含:方向(看涨/看空/观望)/ 信心度 / 入场/止损/止盈价位 / 风险列表 / 证据来源

### 2.2 Chat Tab — 共创策略 7 阶段

- 在 Chat 里输入 **"我想做聪明钱跟单"**
- Agent 会引导你 7 个阶段:idle → clarifying → refining → dry_run → confirming → saved
- 每个阶段 Agent 会问你 1-2 个具体问题(链 / 金额 / 止损止盈 / cooldown)
- 最终确认后,策略会保存到 Strategies Tab

### 2.3 Strategies Tab — 策略管理

- 看你创建的策略列表(默认 paper 模式 = 模拟盘,不真出钱)
- 点策略详情可看历史触发 / 模式晋升进度(paper → notify → auto)
- **不要试 auto 模式**(我们后台已 0 概率开启,即便你点也不会真买)

### 2.4 推送通知

- 启动后会要求**通知权限**,允许它
- 当你的策略触发时会推送
- 内测期可去 Strategy 详情页 "手动触发"测试推送

### 2.5 Insight Tab — 复盘报告

- 进 **Insight Tab**(底部 tab)
- 看每日 / 每周 / 每月复盘报告(基于你的真实交易数据)
- 含 metrics:胜率 / EV / Sharpe / 最大回撤
- 含 Agent 提议的规则(可点采纳 / 拒绝)

### 2.6 Insight Tab → 记忆管理

- 进 Insight Tab → 点 "管理我的记忆"
- 看 Agent 学到的规则(active / shadow_mode 14d 观察期 / dormant)
- 可以禁用 / 删除某条规则

### 2.7 HITL 审批(人在环)

- 当 auto 策略触发(暂未开)时会推送审批请求
- 你点开看 thesis + 风险卡 + 金额,选 approve / reject
- 5 分钟超时自动 reject

---

## 3. 不要做这些(暂未开放)

- ❌ **真金交易**(auto 模式)— 我们硬保 `agent_v1_auto_mode = 0`,即便你界面点也不会执行
- ❌ 邀请外部人员(还没有公开)
- ❌ 把 IPA / APK 分享给团队外的人

---

## 4. Bug 反馈(关键!)

| 严重度 | 例子 | 反馈方式 |
|--------|------|---------|
| 🔴 P0 | crash / 无法启动 / 假装真金交易 | 立即 @ 项目负责人 |
| 🟠 P1 | 推送收不到 / thesis 数据明显错 / 共创卡死 | 微信群截图 + 描述 |
| 🟡 P2 | UI 体验问题 / 文案不通顺 / 颜色奇怪 | 微信群文字描述 |
| 🟢 P3 | 建议 / 想要的功能 | 微信群讨论 |

**截图必带**:
- 你做了什么
- 期望看到什么
- 实际看到什么
- 截图 / 录屏

---

## 5. 数据隐私

- 内测期数据存在我们服务器(43.156.207.26 + Supabase)
- 不会公开 / 不会分享给第三方
- 测试结束(预计 ~2-4 周)后会清掉

---

## 6. 已知不完美的地方(诚实说明)

| 现象 | 原因 | 何时修 |
|------|------|------|
| Agent 第一次回复有时慢(5-10s)| LLM cold start + 拉真链上数据 | 上线后 1 周加 cache |
| 推送可能延迟几秒 | FCM 队列 | 正常,不算 bug |
| Insight 复盘报告对新装用户是空 | 没历史数据 | 跑几天有交易后就有了 |
| L3 thesis debate 偶尔超时 | 多 LLM 调用 + 5 轮辩论 | 已 5 级降级,会 fallback L2 |
| auto 模式按钮可点但不执行 | 灰度门 0%(故意的)| 等 KMS / 1 周稳定后真开 |

---

## 7. 给项目负责人的快速 health check

```bash
# 看后端跑没跑
curl http://43.156.207.26/api/health

# 看 8000 LISTEN
ssh ubuntu@43.156.207.26 "sudo netstat -tnlp | grep 8000"

# 看日志
ssh ubuntu@43.156.207.26 "journalctl -u pump-scanner-api -n 50"

# Kill switch(紧急关 Agent v1)
curl -X POST http://43.156.207.26/api/admin/agent/kill-switch
```

---

## 8. 联系

- 项目负责人:Wen Ruiwei
- 微信群:(由 owner 拉群)
- 文档:
  - 总览:`docs/agent-pm/eval-summary.md`
  - 灰度推进:`docs/runbook/beta-rollout.md`
  - 部署:`docs/runbook/agent-v1-prod-deploy.md`
  - eval / triage:`docs/runbook/eval-runbook.md`

---

**祝玩得开心,认真反馈,别用真钱 🙏**
