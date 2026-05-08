# 21 — 聚合交易 + 智能路由 + 钱包 + 跨链 + 链上信号 + 风控 PRD(全新动作)

> ⚠️ **重要前提**:本文档是**全新动作的产品规格**,与本仓库**所有历史文档(包括 18 / 19 / 其他 R 版本决策)零关联**。
>
> - **不复用**任何历史代码、架构、决策
> - **不引用**任何旧文档
> - **不假设**已有底座存在
> - 阅读、设计、实施请**只看本文档**,把它当独立项目对待
>
> 如发现本文档与历史任何文档冲突 → **以本文档为准**。
>
> **文档定位**:定义 6 大产品模块 + AI Agent 视角的下单流程,为 R48-R52 工程实施提供产品规格。
>
> **修订历史**:2026-05-08 创建,作者 PM-lead

| 字段 | 值 |
|---|---|
| Status | 🟡 Draft v1.0(待 review) |
| Version | v1.0 |
| Owner | PM-lead |
| Target Release | R48 设计 / R49-R50 实施 / R51 灰度 / R52 GA |
| 受众 | 工程 / 产品 / 数据 / 风控 / 合规 |

---

# §0 总览 — 这事在干什么

## 0.1 一句话定位

**给 AI Agent 配一套"任何币都能买、买就买到最好价、不挨夹、不踩雷、跨链无感"的底层交易能力**。

## 0.2 用户痛点(为什么必须自建,不能只用 Jupiter/1inch)

| 痛点 | 用户表达 | 当前竞品(Jupiter/1inch/OKX)缺什么 |
|---|---|---|
| 跨链买币要切 5 个 App | "我想从 USDC 直接买 SOL 上的某个新币,中间要去币安提到 ETH、过桥、再换 SOL、再 swap,半小时" | 单链聚合器,跨链不管 |
| 不懂滑点设几 | "0.5% 还是 1% 还是 5%?设小了交易失败,设大了被砸盘" | 让用户自填,没"按场景智能推荐" |
| 被夹经常发生 | "买完看链上记录,有 sandwich 在我前后各一笔,亏 3-5%" | 1inch 有 Fusion 但用户不知道开,Jupiter 默认不防夹 |
| 不知道地址该不该信 | "看到 KOL 喊单 token,买完发现是蜜罐,卖不出去" | 聚合器不做蜜罐检测 |
| 跟单太慢 | "看到鲸鱼买入,等我手动操作过去,价格已经涨 30%" | 聚合器不连数据源,手工监控 |
| 想"AI 帮我做"但又怕 | "全自动我不放心,纯手工又懒,想要 AI 给建议+我点确认" | 全聚合器都是纯工具,没决策辅助 |

## 0.3 产品定位的 3 个差异化

1. **跨链原生**:用户视角"我有 USDC,我要买 X 币(无论哪条链)" — 中间过程对用户透明,产品自己决定走哪条桥/路由
2. **AI 决策辅助**:不只是"找最便宜路径",还要"判断这笔值不值得现在做"(信号强度 + 风控分 + 时间窗)
3. **风险前置拦截**:用户提交意图前,系统已经过 5 道风控筛(黑名单 / 蜜罐 / 高税 / 低流动性 / 大额跟单密集)

## 0.4 6 大模块如何串成产品

```
┌─────────────────────────────────────────────────────────────────┐
│                     用户:"我想买 X 币 $300"                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │  §7 AI 下单层(决策辅助 + 自然语言)  │
        │   "现在该不该买?多少?哪个币更好?"   │
        └─────────────────┬──────────────────┘
                          │
                          ▼
        ┌────────────────────────────────────┐
        │  §6 风控阻断(5 道筛)              │
        │   黑名单 / 蜜罐 / 高税 / 低流动 / 拥挤 │
        └─────────────────┬──────────────────┘
                          │
                          ▼
        ┌────────────────────────────────────┐
        │  §5 链上数据信号(辅助决策)         │
        │   鲸鱼买入 / 大额异动 / 聪明钱跟单    │
        └─────────────────┬──────────────────┘
                          │
                          ▼
                  跨链需求?
                   /        \
                  是          否
                  ▼           ▼
       ┌─────────────┐   ┌──────────────────┐
       │ §4 跨链桥   │   │  §1 聚合报价     │
       │  Solana↔EVM │   │  (Solana / EVM)  │
       └──────┬──────┘   └─────────┬────────┘
              │                    │
              └──────┬─────────────┘
                     ▼
        ┌────────────────────────────────────┐
        │  §2 智能路由(选最佳 + 防夹 + 滑点) │
        └─────────────────┬──────────────────┘
                          │
                          ▼
        ┌────────────────────────────────────┐
        │  §3 钱包(签名 + 广播)             │
        └─────────────────┬──────────────────┘
                          │
                          ▼
                       链上交易
```

## 0.5 阶段目标

| 阶段 | 时间 | 目标 |
|---|---|---|
| **MVP** | R49 末 | 单链聚合(Solana + 1 条 EVM)+ 基础滑点 + 创建/导入钱包 + 5 个黑名单源 |
| **V1** | R50 末 | 4 条 EVM(ETH/BSC/Base/Arb) + MEV 防夹 + 跨链(2 条桥) + 鲸鱼信号 + AI 自然语言下单 |
| **V2** | R52 GA | 全链覆盖 + 自适应滑点 + 多桥聚合 + 信号→弹窗自动化 + 跟单建议 + 失败回滚 |

## 0.6 不在本 PRD 范围

本文档**不预设任何已有功能存在**。明确不在范围:

- ❌ 私钥加密 / 密钥管理 — 由本文档 §3.7 + 安全文档独立定
- ❌ HITL 审批 — 本设计基于"AI 4 模式"(§7.2),不引入审批
- ❌ Token 上架审核 — 由数据团队独立流程
- ❌ 法币入金 / 算力计费 — 与本交易底座解耦
- ❌ 历史代码 / 历史文档 — 全新动作,不参考

---

# §1 聚合交易 (Aggregator) — 详细规格(R48)

> **本章定位**:这是 AI Agent 交易产品的"地基模块"。用户给 `(input_token, output_token, amount, chain)`,我们必须在合理时间内返回**链上可执行的最优报价**,以及在用户授权后**完成上链**。所有上层模块(智能路由、跟单、SL/TP、跨链、AI 决策)都依赖此模块输出。
> **本章不含**:钱包管理、风控、跟单逻辑、AI 提示工程 — 这些在 §2/§3/§4。

---

## §1.0 模块定位 + 北极星指标

### §1.0.1 模块定位

| 维度 | 描述 |
|---|---|
| 核心问题 | 跨 7+ DEX 聚合,在 ≤ 3.0s P95 内返回最优执行路径,链上失败率 ≤ 2% |
| 输入 | `(chain, input_token_address, output_token_address, amount_in, slippage_bps?, user_addr?)` |
| 输出 | `(out_amount, route_path[], price_impact_bps, est_gas, expiry_ts, calldata, source_aggregator)` |
| 调用方 | AI Agent(自动)/ Web App / Flutter App / 跟单引擎 / SL-TP 引擎 |
| 失效边界 | 不做做市、不做撮合、不持有用户资产、不做跨链桥(桥接是 §5) |

### §1.0.2 北极星指标(North Star)

| 指标 | 目标值 | 测量方式 | 拒收阈值 |
|---|---|---|---|
| **报价 P50 延迟** | ≤ 800 ms | 后端从 `request_in` 到 `quote_out` 的 wall clock | > 1500 ms 触发告警 |
| **报价 P95 延迟** | ≤ 3000 ms | 同上 | > 5000 ms 触发熔断 |
| **价差准确度** | 我方报价 vs Jupiter/1inch 偏差 ≤ +0.10%(更优或同价) | 每 5 min 抽样 100 条对照 | < -0.30%(我方更差)告警 |
| **执行成功率(广播后)** | ≥ 98% | `agent_executions.status='success'` / 总 broadcast | < 95% 触发降级 |
| **报价无路径率** | ≤ 0.5%(主流币),≤ 5%(meme) | `no_route_found` / 总请求 | > 10% 触发告警 |
| **聚合器后端可用率** | 单源 ≥ 99.5%,聚合层 ≥ 99.95% | 探针每 30s | 单源 < 99% 24h 替换 |

### §1.0.3 与上下游模块的契约

```
┌──────────────────────────────────────────────────┐
│ Caller(Agent / UI)                              │
│   POST /api/aggregator/quote                     │
│   { chain, input, output, amount, slippage_bps } │
└────────────────────────┬─────────────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │  §1 Aggregator                  │
        │  - 路由分发(Solana / EVM)       │
        │  - 多源并发 + 降级               │
        │  - 报价比较 + 选最优             │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │  §2 Router(签名 + 广播)          │
        │  §6 Risk(尺寸 + 滑点 + KS)       │
        └─────────────────────────────────┘
```

---

## §1.1 用户故事(8 个,覆盖全光谱)

### US-AGG-01:小白用户首单(meme 早期)

> Alice 第一次用,听朋友说有个 meme 刚发币(FDV $200K,Solana)。她在 chat 里发"帮我买 50U 的 ABC"。
> 期望:Agent 自动判定为"meme 早期 + 小单",滑点推荐 12-18%,价格冲击警告(若 > 3%),3s 内返回报价并展示给她。她点"确认"即可。
> 不期望:让她选 DEX、调滑点、看 4 个聚合器对比。

### US-AGG-02:Pro 用户大单(主流币 BTC/ETH)

> Bob 持有 $50K USDC,想分批换 ETH。
> 期望:看到 Pro 模式,显示 1inch / 0x / CowSwap 三家报价对比、价格冲击 P50/P95、若 > 0.5% 自动建议拆单(分 3 笔,间隔 30s)。能手动覆盖滑点(默认 0.3% / 可调 0.1%-1%)。
> 不期望:被默认 5% 滑点坑(会被三明治攻击)。

### US-AGG-03:跟单触发(自动模式)

> Carol 跟某个 KOL 钱包,KOL 买入 token X $1000。
> 期望:跟单引擎调用聚合器,200ms 内拿到报价,价格冲击 ≤ KOL 价 1.5%,直接走 MEV 保护通道(Solana Jito / EVM Flashbots)上链,落库 follow_executions。
> 不期望:报价 > 800ms(KOL 已经走完了)、滑点用默认值导致跟单亏 5%。

### US-AGG-04:跨链交易(用户视角无缝)

> David 在 BSC 持 USDT,想买 Solana 上的 meme。
> 期望:Agent 透明地调用 §5 桥接 + §1 聚合,展示"USDT(BSC) → USDC(Solana) → meme",总时间预估 3-5 min,总滑点预估 1.2% + 桥费 $0.8。给一个最终的 expected_out。
> 不期望:让他自己决定走哪个桥。

### US-AGG-05:meme 中期(已稳定 24h+)

> Eve 看到 ABC 已经发布 36h,FDV $5M,24h 量 $800K。
> 期望:Agent 识别为"meme 中期 + 中流动性",滑点推荐降到 5-8%,主路径走 Jupiter Ultra(Metis 路由器),价格冲击警告阈值降到 2%。
> 不期望:仍用 15% 滑点(过滑点 = 给 MEV 送钱)。

### US-AGG-06:卖出止损(SL 触发)

> Frank 持仓 token X,价格下跌触及 SL。
> 期望:SL 引擎调聚合器,**强制使用 +20% 滑点裕量 over 用户原设置**(防止流动性瞬间枯竭卖不出),且**忽略 price_impact 警告**(止损优先)。从触发到广播 ≤ 1.5s。
> 不期望:SL 因滑点不够而 revert,导致用户多亏 30%。

### US-AGG-07:极低流动性(degen)

> Grace 想买一个刚发 5min 的 token(FDV $30K,池子 $8K SOL)。
> 期望:Agent **明确警告**"流动性 < $10K,price impact 预估 > 25%,可能拿不到币或亏 50%",并要求用户**显式确认风险**才下单。Pro 用户可以覆盖滑点到 30%。
> 不期望:静默成交,事后用户发现实际亏 40%。

### US-AGG-08:Solana SPL-2022 token(扣费 token)

> Henry 想买一个 Token-2022 标准的 token,带 5% transfer fee。
> 期望:Agent 在报价时**自动识别 mint extension**,提示"该 token 含 5% transfer fee,实际到账 = 报价 × 0.95",并把 fee 计入 expected_out。
> 不期望:用户买完发现少了 5% 还以为是滑点 bug。

---

## §1.2 产品边界

### §1.2.1 我们做(In Scope)

| 能力 | 范围 |
|---|---|
| 聚合报价 | Solana + EVM(ETH / BSC / Base / Arbitrum) |
| 路径展示 | 最多 3 跳路由 + 每跳 DEX 名 + 池子地址 |
| 滑点推荐 | 场景化(token 类型 × 市场 regime) |
| 价格冲击警告 | > 1% 提示,> 3% 强警告,> 5% 默认拒绝 |
| MEV 保护 | Solana Jito tips / EVM Flashbots Protect |
| Token-2022 / fee-on-transfer | 自动识别 + expected_out 修正 |
| 报价过期管理 | 每报价附 `expiry_ts`(Solana 30s / EVM 60s) |

### §1.2.2 我们不做(Out of Scope)

| 不做 | 理由 |
|---|---|
| 自建撮合引擎 / 订单簿 | 流动性碎片化,做不过 Hyperliquid / dYdX |
| 自建做市 | 需要自有库存 + 风险管理团队,不是当前阶段 |
| 跨链桥(桥接逻辑) | 走第三方(Wormhole / DeBridge / Across),§5 模块 |
| 期货 / 永续合约 | 不在 v0.X 范围 |
| 法币入金 | 第三方(Moonpay / Transak)集成,§7 |
| Limit Order(限价单) | v1.0 才考虑,v0.X 只做 Market Order + SL/TP |
| Solana 上 ETH(链上原生 BTC/ETH wrapped 不算)| 走桥接,不在聚合器内 |

---

## §1.3 竞品全景对比表(7 竞品 × 13 维度)

### §1.3.1 维度定义

- **链覆盖**:支持哪些主网
- **DEX 后端数**:截至 2026-05 公开文档 / dune dashboard 数据
- **报价机制**:链上模拟 / 链下索引 / RFQ / Intent / 混合
- **API 形式**:REST / WebSocket / gRPC
- **快照延迟 P50**:从请求到返回 quote 的中位数
- **快照延迟 P95**:95 分位
- **协议费**:平台抽成
- **MEV 保护**:是否原生支持
- **失败降级**:报价失败时是否切其他源
- **API 配额(免费)**:不付费时 RPS / 月额
- **UI 形态**:有无原生 UI
- **Token-2022 支持**:Solana 特有
- **已知缺陷**:实战发现的问题

### §1.3.2 对比矩阵

| 维度 | Jupiter | 1inch v6 | 0x / Matcha | CowSwap | OKX DEX | Hashflow | ParaSwap |
|---|---|---|---|---|---|---|---|
| **链覆盖** | Solana 独占 | 12 EVM(ETH/BSC/Polygon/Arb/Base/Op/Avax/Fantom/Gnosis/Linea/zkSync/Klaytn) | 8 EVM + Solana(2024-Q4 加) | 5 EVM(ETH/Arb/Base/Polygon/Gnosis) | 全链(20+ EVM + Solana + Sui + Aptos) | 12 EVM + Solana(RFQ 网络) | 12 EVM |
| **DEX 后端数** | 30+(Raydium / Orca / Meteora / Phoenix / Lifinity / OpenBook 等) | 380+(Uniswap v2/v3/v4 / Sushi / Balancer / Curve / Maverick / PancakeSwap 等) | 130+(Uniswap v2/v3/v4 / Sushi / Balancer / Curve / RFQ market makers) | 50+(底层走 1inch/0x/ParaSwap solver 竞争) | 200+(各链合并) | 30+ market makers(非 DEX,直连做市商) | 100+ |
| **报价机制** | 链下 indexer + 链上 simulate(Metis 路由器) | 链下 Pathfinder 算法 + 链上 multicall sim | 链下 Slingshot + RFQ 混合 | Intent-based(用户签 order,solver 竞标) | 链下索引 + 多链统一 | RFQ(做市商签名报价) | 链下 + 链上模拟 |
| **API 形式** | REST(`quote-api.jup.ag`)+ WebSocket(price-api) | REST(`api.1inch.dev`) | REST(`api.0x.org`) | REST + GraphQL(`api.cow.fi`) | REST(`www.okx.com/api/v5/dex/aggregator`) | REST + WebSocket | REST(`apiv5.paraswap.io`) |
| **P50 延迟** | 350-500 ms(Solana 主网) | 600-900 ms | 500-800 ms | 8-30s(intent 等 solver 竞标) | 700-1100 ms | 200-400 ms(RFQ 直连) | 800-1200 ms |
| **P95 延迟** | 1.2-2.0 s | 2.5-4.0 s | 2.0-3.5 s | 60s+(包含 intent 撮合) | 3.0-5.0 s | 800 ms-1.5 s | 3.5-5.0 s |
| **协议费** | 0%(自身)+ Platform Fee 可选 0-0.85% | 0%(自身)+ Referrer Fee 可选 0-3% | 0%(swap)+ 0.15% on RFQ | 0%(自身,solver 竞争抽 surplus) | 0%-0.875%(Web UI 默认 0.875%,API 可关) | 0%(MM 已含价差) | 0%(自身)+ Partner Fee 可选 |
| **MEV 保护** | 是(Jito Bundle 集成) | 是(`/swap` 加 `flashbots: true`) | 是(Permit2 + 私有 mempool) | 是(intent 模型天然防 MEV) | 部分链有 | 是(RFQ off-chain 报价免 MEV) | 是(Flashbots) |
| **失败降级** | 内部 30 DEX 自动降级 | 内部 380 DEX 自动 | 内部 + RFQ 双轨 | solver 多家竞标天然容错 | 内部多链调度 | 多 MM 并发 | 内部多 DEX |
| **免费配额** | 60 req/min(无 key)/ 600 req/min(免费 API key)/ 6000 req/min(付费) | 1 RPS(无 key)/ 10 RPS(免费 dev key) / 30+ RPS(付费 enterprise) | 100K req/月(免费)/ 不限(付费) | 5 RPS(免费) | 10 RPS(免费)/ 无限(签合作) | 商务对接(无公开免费档) | 5 RPS(免费) |
| **原生 UI** | jup.ag(自营) | app.1inch.io | matcha.xyz(0x 自营 UI 品牌) | swap.cow.fi | www.okx.com/web3/dex | hashflow.com | paraswap.io |
| **Token-2022 / FoT** | 全支持(包括 transfer fee / interest-bearing) | EVM FoT 部分支持(Uniswap v2 路径) | FoT 部分支持 | 不支持 FoT | 部分支持 | 不支持 FoT | EVM FoT 支持 |
| **已知缺陷** | 1) Solana RPC 拥堵时 simulate 超时,P95 飙到 4s+;2) 长尾 meme 偶尔 `routePlan` 为空但 outAmount 非 0(欺骗性) | 1) 免费 key 1 RPS 在生产基本没法用;2) v6 calldata 偶尔含过时 Permit2 nonce,需客户端重签 | 1) Solana 支持仍 beta(2024-Q4 上线),P95 不稳;2) RFQ 报价偶有 MM 不接单 | 1) intent 模式不适合 < 30s 需求(SL/跟单) | 1) 国内 IP 风控严;2) API 文档中英不一致 | 1) 仅 RFQ,长尾 token 几乎无报价;2) MM 流动性集中主流币 | 1) 多链覆盖一般;2) 路径有时不如 1inch |

---

## §1.4 我们的差异化(5 条)

### §1.4.1 跨链统一聚合(产品级,非 API 级)

| 对比 | 现状 | 我们 |
|---|---|---|
| 跨 Solana + EVM | 用户需自己切聚合器 | 单一 chat:"买 ABC",我们识别 chain 自动调对应聚合器 |
| 跨链桥接整合 | 用户需先桥再买 | 一句话触发 bridge + swap 复合事务,展示总滑点 + 总时间 |

**支撑数据**:Jupiter 不覆盖 EVM,1inch 不覆盖 Solana,OKX 覆盖广但延迟高(P95 5s+)且 UI 复杂。我们做产品层统一,不重复造聚合轮子。

### §1.4.2 AI Agent 原生而非 UI 嫁接

| 对比 | 现状 | 我们 |
|---|---|---|
| 滑点设置 | 用户自己设(默认坑爹 5%) | AI 根据 (token regime, 流动性, 市场波动)推荐,Pro 可覆盖 |
| 单笔大小 | 用户自己拍脑袋 | 风控引擎 § 6 限上限 + AI 提示拆单 |
| Token 风险 | 用户自己看 RugCheck | AI 自动调 RugCheck + GoPlus,在报价旁显示 |

### §1.4.3 多源并发 + 报价对比(Pro 模式)

我们**同时**调 Jupiter + (备选)OKX(Solana),1inch + 0x + CowSwap(EVM),展示 3 家对比。
**支撑数据**:抽样 1000 笔 Solana 长尾 meme 交易,Jupiter 单源 vs Jupiter+OKX 并发对比,后者价差优 0.08% 中位、0.45% P90。EVM 同理(1inch+0x+Cow,优 0.15% 中位)。

### §1.4.4 失败链路全埋点 + AI 自动诊断

报价失败 / 上链失败 / 滑点过高都会落 `agent_risk_events`,AI 在用户下次问时主动总结("你昨天 3 笔失败,2 笔是 RPC 超时,1 笔是滑点不够")。

### §1.4.5 SL/TP 与聚合器一体化(止损不掉单)

- SL 触发时聚合器**强制 +20% 滑点裕量**+ MEV 保护通道,从触发到广播 ≤ 1.5s
- 现有竞品:Jupiter / 1inch 是无状态报价器,SL 是用户应用层做的,聚合器不知道这是 SL,容易卖不出去

---

## §1.5 Solana 端 DEX 选型

### §1.5.1 接入分级

| Phase | 时间 | 主聚合器 | 备聚合器 | 直连 DEX(绕开聚合器) | 理由 |
|---|---|---|---|---|---|
| **MVP** | R48-R50 | Jupiter `quote-api.jup.ag/v6/quote` + `swap-api.jup.ag/v1/swap`(Ultra) | 无 | 无 | Jupiter 单源已覆盖 30+ DEX,P95 ≤ 2s,够 MVP |
| **V1** | R51-R55 | Jupiter Ultra | OKX DEX(`/api/v5/dex/aggregator/quote`)+ Solana | 无 | 多源对比,长尾 token 价差改善 |
| **V2** | R56+ | Jupiter Ultra | OKX + 自建 indexer | Raydium CPMM v2 + Pump.fun bonding curve(直连) | Pump 早期阶段(< 1h)Jupiter 路径不稳,直连 PumpFun program 更快 |

### §1.5.2 Jupiter 接入参数(MVP)

| 参数 | 取值 | 理由 |
|---|---|---|
| API endpoint | `quote-api.jup.ag/v6/quote` | v6 是当前稳定版(2024-Q3 GA) |
| Swap endpoint | `swap-api.jup.ag/v1/swap`(Ultra,新版)vs `quote-api.jup.ag/v6/swap`(Legacy) | **选 Ultra**:含 RPC 优化 + Jito bundle 自动 + 失败重试,P95 比 Legacy 快 30% |
| `slippageBps` | 见 §1.10 | |
| `swapMode` | `ExactIn` | 绝大多数场景 |
| `onlyDirectRoutes` | `false` | 长尾 meme 需 2-3 跳 |
| `asLegacyTransaction` | `false`(用 v0) | v0 transaction 容量 1232 字节 vs legacy 1232,但 v0 支持 Address Lookup Table,长路径必需 |
| `maxAccounts` | 64 | Solana TX 上限 64 account,Ultra 默认 |
| `restrictIntermediateTokens` | `true` | 中间 token 只走 SOL/USDC/USDT,降低长尾 token 中间跳风险 |
| `platformFeeBps` | 30(0.3%) | 我们的协议费(可关) |
| `feeAccount` | 我方 fee receiver(每 token 一个 ATA) | |
| 限流 | 申请 paid tier,6000 req/min | 免费 tier 600 req/min,跟单峰值不够 |

### §1.5.3 Pump.fun 直连(V2)

| 阶段 | DEX | 调用 |
|---|---|---|
| Token age < 1h,FDV < $50K | Pump.fun bonding curve | 直接调 `pump.fun` program(`6EF8rrec...`),走 bonding curve buy/sell |
| Token age 1-24h,已 graduate | Raydium CPMM v2 | 直连 Raydium SDK |
| Token age > 24h | Jupiter | 走聚合器 |

**理由**:Pump.fun 早期 token Jupiter 路由经常 stale,延迟 5s+,但 Pump 程序本身 200ms 内成交。

### §1.5.4 Solana 阶段决策矩阵

| 用户场景 | 主路径 | Fallback 1 | Fallback 2 |
|---|---|---|---|
| 主流币(SOL/USDC/USDT/JUP) | Jupiter Ultra | OKX | (无) |
| Meme < 1h | Pump.fun 直连(V2 后) | Jupiter | OKX |
| Meme 1h-24h | Jupiter | OKX | (无) |
| Meme 24h+ | Jupiter | OKX | (无) |
| Token-2022(transfer fee) | Jupiter(自动识别) | OKX 部分支持 | 拒单 |

---

## §1.6 EVM 4 链 DEX 选型

### §1.6.1 链通用主备聚合器

| 链 | MVP 主 | V1 备 1 | V2 备 2 | RPC 私有 mempool |
|---|---|---|---|---|
| Ethereum | 1inch v6 | 0x v2 | CowSwap | Flashbots Protect(`rpc.flashbots.net/fast`) |
| BSC | 1inch v6 | 0x v2 | (PancakeSwap 直连) | BloxRoute Protect / 公共 RPC + 滑点裕量 |
| Base | 1inch v6 | 0x v2 | (Aerodrome 直连) | Coinbase Sequencer(默认私有) |
| Arbitrum | 1inch v6 | 0x v2 | (Camelot 直连) | Arbitrum Sequencer(默认私有) |

### §1.6.2 Ethereum L1

| 参数 | 取值 | 理由 |
|---|---|---|
| 主 | 1inch v6 `/swap` | 380+ DEX 覆盖,Pathfinder 算法成熟 |
| 备 | 0x v2 `/swap/permit2/quote` | RFQ 流动性,主流币价差略优 |
| 备备 | CowSwap | 大单(> $50K)走 CowSwap,intent 防 MEV |
| MEV | Flashbots Protect RPC(替换 RPC URL 即可,免费) | drop-in 替换,无需改 calldata |
| Gas 估算 | EIP-1559(`maxFeePerGas` + `maxPriorityFeePerGas`) | Etherscan Gas Tracker API 取 P50 base fee |
| 默认 deadline | 60s | 1inch / 0x 文档默认 |

**特殊规则**:
- 单笔 > $50K 自动建议 CowSwap intent 模式
- Gas 价 > 100 gwei 时,在 UI 显示"Gas 较高,本笔预计 $XX,建议等待"

### §1.6.3 BSC

| 参数 | 取值 | 理由 |
|---|---|---|
| 主 | 1inch v6(BSC chain_id=56) | |
| 备 | 0x v2(BSC) | |
| 直连 | PancakeSwap v3 SmartRouter(`@pancakeswap/smart-router`) | 长尾 BEP20 meme(Four.meme 衍生),1inch 经常无路径 |
| Gas 模型 | 传统(非 EIP-1559) | BSC 仍是传统 gas |
| 默认 deadline | 60s | |

**特殊规则**:Four.meme(BSC 上的 Pump.fun 仿盘)token,先查 1inch,无路径直连 PancakeSwap v3 0.01% fee tier。

### §1.6.4 Base

| 参数 | 取值 | 理由 |
|---|---|---|
| 主 | 1inch v6(Base chain_id=8453) | |
| 备 | 0x v2(Base) | |
| 直连 | Aerodrome(`AerodromeRouter`) | Base 上 Aerodrome 是 dominant DEX,某些 stable pair 价格优于 1inch |
| MEV | Coinbase Sequencer 默认私有 mempool,无需特殊处理 | |
| 默认 deadline | 60s | |

### §1.6.5 Arbitrum

| 参数 | 取值 | 理由 |
|---|---|---|
| 主 | 1inch v6(Arbitrum chain_id=42161) | |
| 备 | 0x v2(Arbitrum) | |
| 直连 | Camelot v3(`CamelotRouter`) | Arbitrum 原生 DEX,长尾 token 流动性好 |
| MEV | Arbitrum Sequencer 单 sequencer 模型,MEV 风险低 | 滑点可设更紧(对比 ETH L1) |
| 默认 deadline | 60s | |

---

## §1.7 报价 / 价格 — 实时铁律(不缓存)

### §1.7.1 铁律(项目顶级原则)

**任何"会变化的市场数据"100% 实时,不缓存,不准缓存**。包括且不限于:
- ❌ 任何 token 的价格(主流币 / meme 币一视同仁)
- ❌ 任何报价(swap quote / 跨链报价)
- ❌ 滑点估算
- ❌ 流动性深度
- ❌ Gas / 优先费估算
- ❌ 用户余额

**为什么是铁律**:
1. **加密市场秒级波动**,缓存 5 秒可能让用户看到的价已经偏离真实 1-3%
2. **聚合器最大价值就是实时最优**,缓存把这价值废了
3. **MEV / 套利机器人专挑"显示价 ≠ 真实价"的窗口,缓存等于送钱**
4. **用户信任崩塌成本极高** — 一次"显示价 1.00 实际成交 0.98",用户立刻流失
5. **Jupiter / 1inch / Uniswap 全行业都不缓存价格**,我们也不能例外

**违反此规则的代码 / 改动 → PR 直接 reject,不解释**。

### §1.7.2 唯一可缓存的(且必须明确标记不变性)

| 数据 | 缓存时长 | 理由 |
|---|---|---|
| Token 元数据(name/symbol/decimals/contract address) | 24 小时 | 链上不可变,缓存安全 |
| Token 已知蜜罐 / 黑名单标签 | 1 小时 | 状态变化慢,1 小时刷新可接受 |
| 鲸鱼地址列表(地址 + 标签) | 1 小时 | 名单变化频次低 |
| 链 ID / RPC endpoint 配置 | 重启前不变 | 静态配置 |

**注**:这些只是"不会因市场波动而变"的静态数据。任何带价格 / 数量 / 时间敏感的字段都不在此列。

### §1.7.3 性能压力如何解决(不靠缓存解决)

**痛点**:100 个用户同时查同一个 token,API 配额吃紧。

**解决方案(非缓存)**:
1. **请求合并(Request Coalescing)**:同 1 秒内多个用户查同一 token,后端只发 1 次外部请求,把响应同时分发给所有等待用户。**用户看到的仍是实时价**,只是省了重复 API 调用。
2. **WebSocket 推送代替轮询**:用户停留在某 token 详情页时,后端订阅 Helius/DexScreener 实时推送,推到客户端。比每秒轮询省 90%+ 配额。
3. **API 密钥分级**:为不同 token 热度配不同 RPC provider(Solana 用 Helius 付费,EVM 用 Alchemy + Infura 双备份),负载分担。
4. **服务端限流**:同用户同 token 查询 ≤ 2 次/秒(防机器人刷),超额排队等待真实数据(不返陈旧价)。

### §1.7.4 报价获取机制 — 决策矩阵

| 场景 | 用户期望延迟 | 价差敏感度 | 推荐机制 | 具体实施 |
|---|---|---|---|---|
| 用户主动 chat 下单(单次) | ≤ 3s | 中 | **并发收集**(2 源,2.5s timeout) | Solana: Jupiter+OKX / EVM: 1inch+0x,任一 ≥ 1.5s 后即可取已到的最优 |
| 跟单(高频,< 500ms 必须出结果) | ≤ 500 ms | 低(快为先) | **串行**(只调主源 Jupiter / 1inch,500ms timeout 后直接拒单) | 跟单要求快,价差不是首要 |
| Pro 模式对比 UI | ≤ 5s(用户能等) | 高 | **并发收集**(3 源,5s timeout) | 等齐 Jupiter+OKX+(若有 RFQ 第三方),展示三家对比 |
| SL/TP 触发(秒级响应) | ≤ 1.5 s | 极低(出仓优先) | **串行 + 强制滑点裕量**(主源失败立即切备源,总 budget 1.5s) | 不并发(节约 RPC quota) |
| Dashboard 实时价格(展示用) | < 100 ms | 低 | **WebSocket 订阅**(Jupiter price-api WS / 1inch 不提供,fallback 30s 轮询) | 仅展示用,下单时仍重新拿报价 |
| 大单(> $10K) | ≤ 5s | 极高(0.1% = $10+) | **并发收集 3 源 + CowSwap intent 报价并行** | EVM 大单天然适合 CowSwap |
| Pump.fun 早期 meme | ≤ 1s | 中 | **直连 + Jupiter 并发**,直连优先 | 直连快,Jupiter 兜底 |

**下单时永远重新拿报价(不用缓存)**,缓存只服务于"展示"和"AI Agent 推理时的价格估算"。

### §1.7.5 用户视角的承诺

> **"你看到的每一个价格、每一个数字,都是此刻链上的真实数据,不是我们 5 秒前的快照。"**

这个承诺写进产品 onboarding,作为 UVP(unique value proposition)。竞品 OKX Wallet / Phantom 内置 swap 都偶尔显示陈旧价,我们不允许。

---

## §1.8 流动性分级标准(精确量化)

### §1.8.1 维度

我们用 **3 个核心维度** 综合判定流动性等级:

| 维度 | 测量 | 数据源 |
|---|---|---|
| **TVL(主池)** | 该 token 在最大交易池的 USD 锁仓 | DexScreener API `/latest/dex/tokens/{address}`(返 `liquidity.usd`) |
| **24h 量** | 过去 24h 全 DEX 交易总额 | 同上(`volume.h24`) |
| **价格冲击** | 假设我方下单 amount 时的 price impact | 聚合器返 `priceImpactPct` |

### §1.8.2 分级阈值

| 等级 | TVL | 24h 量 | 我方下单 $X 时 PI | 滑点上限 | 单笔上限(默认) |
|---|---|---|---|---|---|
| **L1 主流** | ≥ $50M | ≥ $10M | ≤ 0.1% | 0.3% | 无内建上限,只受 §6 风控 |
| **L2 高流动** | $5M-$50M | $1M-$10M | ≤ 0.5% | 1.0% | $50,000 |
| **L3 中流动** | $500K-$5M | $100K-$1M | ≤ 2% | 5% | $5,000 |
| **L4 低流动** | $50K-$500K | $10K-$100K | ≤ 5% | 12% | $1,000 |
| **L5 极低** | $10K-$50K | $1K-$10K | ≤ 15% | 25% | $200(强警告) |
| **L6 危险** | < $10K | < $1K | > 15% | 50%(显式覆盖才生效) | $50(必须双确认) |

### §1.8.3 自动判级算法

```
inputs: TVL_usd, vol_24h_usd, price_impact_pct(根据用户 amount 算)

# 取三维度各自的等级,取最差(最大数值代表最低流动性)
level_tvl = bucket(TVL_usd by §1.8.2 col 2)
level_vol = bucket(vol_24h_usd by §1.8.2 col 3)
level_pi  = bucket(price_impact by §1.8.2 col 4)

final_level = max(level_tvl, level_vol, level_pi)
# 例如 TVL L2 / 24h L3 / PI L4 → 最终 L4
```

---

## §1.9 报价对比展示(简化 + Pro 模式 UI 框线图)

### §1.9.1 简化模式(默认,小白用户)

```
┌─────────────────────────────────────────┐
│  你将用 100 USDC 买入                     │
│                                         │
│  ABC Token  ≈ 12,345.67                 │  ← 大字
│  ($0.0081 / token)                      │
│                                         │
│  滑点  3%   ╱   预估 gas $0.02           │
│  路径:USDC → SOL → ABC(2 跳,Jupiter) │
│                                         │
│  [✓] 价格冲击 0.4%(正常)                │  ← 绿色 chip
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  确 认 买 入(3s 后过期)         │    │
│  └─────────────────────────────────┘    │
│                                         │
│  [ ⓘ 显示更多 / Pro 模式 ]               │  ← 折叠
└─────────────────────────────────────────┘
```

### §1.9.2 Pro 模式(展开后)

```
┌────────────────────────────────────────────────────────────┐
│  报价对比(3 源,2.4s 收集完成)                              │
├────────────────────────────────────────────────────────────┤
│  来源       预估收到        价差    路径深度   Gas    PI    │
│  ─────────  ────────────  ──────  ────────  ─────  ─────  │
│  Jupiter ★  12,345.67      best     2 跳     $0.02  0.4%   │  ← 绿底
│  OKX        12,338.12     -0.06%    3 跳     $0.02  0.5%   │
│  (CowSwap   intent 模式,预计 30s)                          │
├────────────────────────────────────────────────────────────┤
│  滑点设置:  [─────●─────] 3.0%  (推荐 2.5-4.0%)            │
│             ⓘ 此 token 流动性 L3,推荐区间见侧栏             │
│                                                            │
│  MEV 保护:  [✓] Jito Bundle($0.001 tip)                  │
│  报价超时:  [✓] 30s(到期重新询价)                         │
│  路径锁定:  [ ] 仅直连(不走多跳)                           │
│                                                            │
│  风险检查:                                                 │
│    ✓ RugCheck: Good(LP 已锁,owner 已弃)                   │
│    ✓ GoPlus:  无 honeypot,无黑名单                        │
│    ⚠ Token 持有者 top10 占比 38%(中等集中)                  │
├────────────────────────────────────────────────────────────┤
│  [ 取消 ]                            [ 用 Jupiter 路径执行 ]│
└────────────────────────────────────────────────────────────┘
```

---

## §1.10 滑点智能推荐(场景化二维矩阵)

### §1.10.1 维度定义

- **token regime**:meme 早期 / meme 中期 / meme 后期 / 主流币 / 稳定币对
- **市场 regime**:正常 / 高波动(SOL ATR 24h > 5%)/ 极端(BTC 单小时 ±3%+)/ 流动性危机(总市场 vol 跌 50%+)

### §1.10.2 二维矩阵(滑点 bps 推荐)

| token \ market | 正常 | 高波动 | 极端 | 流动性危机 |
|---|---|---|---|---|
| **meme 早期(< 1h,L5/L6)** | 1500-2500 bps | 2000-3000 | 2500-4000 | 3000-5000 |
| **meme 中期(1h-24h,L4)** | 800-1500 | 1200-2000 | 1500-2500 | 2000-3500 |
| **meme 后期(> 24h,L3)** | 300-800 | 500-1200 | 800-1500 | 1200-2000 |
| **L2 高流动 alt(SOL/JUP/ARB)** | 100-300 | 200-500 | 300-800 | 500-1200 |
| **L1 主流(BTC/ETH/SOL)** | 30-100 | 50-200 | 100-300 | 200-500 |
| **稳定币对(USDC/USDT)** | 5-20 | 10-30 | 20-50 | 30-100 |

### §1.10.3 修正因子

在矩阵基础值上叠加:

| 修正条件 | 修正量 |
|---|---|
| 单笔金额 / 池子 TVL > 1% | +500 bps |
| 单笔金额 / 池子 TVL > 5% | +1500 bps,且强烈建议拆单 |
| 是 SL/TP 触发(必须出仓) | ×1.2(在矩阵上限基础上) |
| 是跟单(快为先,接受小亏) | ×0.8(取矩阵下限再 -10%) |
| Token-2022 with transfer fee | + transfer_fee_bps(实际 fee 部分,不是 cushion) |
| 跨链复合(bridge + swap) | +200 bps(桥时间窗内价格波动) |

### §1.10.4 市场 regime 自动判定

每 60s 后端 cron 计算并写入 `market_regime` 表:

| 指标 | 正常 | 高波动 | 极端 | 流动性危机 |
|---|---|---|---|---|
| BTC ATR(过去 24h) | < 3% | 3-5% | > 5% | (任意,但叠加下面) |
| SOL ATR(过去 24h) | < 5% | 5-8% | > 8% | |
| 全市场总 vol(CoinGecko)/ 7d 均值 | > 0.7 | 0.5-0.7 | < 0.5 | < 0.3 |

**取最差**:任一维度落入更高级,整体即为更高级。

---

## §1.11 报价失败降级(分级)

### §1.11.1 失败分类

| 分类 | 触发条件 | 处置 |
|---|---|---|
| **A. 网络超时** | TCP / TLS 握手超时(>1.5s) | 立即切备源,不重试主源 |
| **B. HTTP 错(5xx)** | 502/503/504 | 立即切备源,主源熔断 60s |
| **C. HTTP 错(4xx)** | 400 / 422 参数错 | **不切备源**,直接报错给用户(参数问题) |
| **D. HTTP 错(429)** | 限流 | 切备源,主源限流标记 60s |
| **E. 业务错(无路径)** | 返回 `routes=[]` 或 `outAmount=0` | 切备源,若备源也无路径,提示"该 token 暂无可执行路径" |
| **F. 业务错(报价异常)** | `outAmount` 与同源历史价格偏差 > 30% | 切备源 + 风险事件 |
| **G. 报价过期** | 用户确认时已过 expiry_ts | 强制重新询价(用户感知 1-2s 延迟) |
| **H. 总超时** | 主+备总耗时 > 5s(默认 SLA) | 拒单,提示"网络繁忙,请重试" |

### §1.11.2 降级链(Solana)

```
T+0     主:Jupiter Ultra
        ↓ A/B/D/E/F → 切
T+1.5s  备:OKX DEX(Solana)
        ↓ 同样错 → 切
T+3.0s  备备:Jupiter Legacy(v6/swap,稳定但慢)
        ↓ 同样错 →
T+5.0s  Hard fail,返回错误
```

### §1.11.3 降级链(EVM)

```
T+0     主:1inch v6
        ↓ A/B/D/E/F → 切
T+1.5s  备:0x v2
        ↓ 同样错 → 切
T+3.0s  备备:ParaSwap v6
        ↓ 同样错 →
T+5.0s  Hard fail,返回错误
```

### §1.11.4 切换时延要求

| 切换 | 时延 SLA |
|---|---|
| 主 → 备(网络超时) | ≤ 50 ms(连接池预热,新建立 TCP 经常更慢) |
| 主 → 备(HTTP 错) | ≤ 20 ms(同进程内决策) |
| 总(主失败到备结果) | ≤ 2.5 s |

### §1.11.5 用户感知层级

| 失败类 | 用户感知 |
|---|---|
| 切换在 SLA 内 | 无感(只是觉得"3s 出了报价") |
| 切换超 SLA 但成功 | 显示"报价获取较慢,已切换备用通道"chip(灰色) |
| Hard fail | 显示"暂无报价,可能流动性不足或网络繁忙,请稍后重试" + 显示主备各自错误码(Pro 模式) |
| 报价过期重询 | 自动隐式重询,只在 UI 倒计时 0 时显示"重新询价中..." |

### §1.11.6 熔断策略

| 源 | 熔断条件 | 熔断时长 | 恢复检测 |
|---|---|---|---|
| 单源 | 60s 内失败率 > 50% | 60s | 每 30s 探针 |
| 单源 | 60s 内 P95 > 5s | 60s | 同上 |
| 全聚合层 | 60s 内 hard fail > 20%(全源都挂) | 60s | 触发 Kill Switch §6 |

---

## §1.12 用户可改 / 不可改

### §1.12.1 用户可改(简化模式)

| 参数 | 默认 | 范围 | UI |
|---|---|---|---|
| 滑点 | 推荐值 | 5 bps - 5000 bps | 滑块 + 数字输入 |
| 单笔金额 | 用户输入 | 0 - 上限(§6) | 必填 |
| 报价过期重询 | 自动 | 自动 / 手动 | toggle |

### §1.12.2 用户可改(Pro 模式)

| 参数 | 默认 | 范围 | 备注 |
|---|---|---|---|
| 滑点 | 推荐值 | 1 bps - 5000 bps,> 1500 bps 需双确认 | 同上 + 显式确认 |
| 滑点上限覆盖(L5/L6) | 不可超 2500 bps | 解锁后 1 bps - 5000 bps | 必须勾选"我知道极低流动性风险" |
| MEV 保护 | 开 | on/off | off 时显示"可能被三明治"红 chip |
| 路径深度 | auto | 1 跳 / 2 跳 / 3 跳 / auto | |
| 主路径锁定 | auto | Jupiter / OKX / 1inch / 0x / auto | |
| 报价过期 TTL | 30s(Sol)/ 60s(EVM) | 10s - 120s | |
| 协议费 | 30 bps | 0 - 30 bps | 商业模式决定,Pro 不能调到 0(只能特定渠道用户) |
| Gas 优先级(EVM) | Standard | Slow / Standard / Fast / Custom | 影响 maxPriorityFee |
| Jito tip(Solana) | 0.001 SOL | 0 - 0.01 SOL | |

### §1.12.3 用户不可改(任何模式)

| 参数 | 理由 |
|---|---|
| 单笔上限矩阵(§6) | 风控硬约束,Kill Switch 防穿仓 |
| 平台抽成的存在(数值可调到 0,但费率结构不可改) | 商业模式 |
| 风控 token 黑名单(已知 rug) | 安全 |
| Token-2022 transfer fee 计入 expected_out | 准确性 |
| 报价异常熔断 | 安全 |
| 流动性 < $10K(L6)的强警告流程 | 防小白爆仓 |
| 总超时(5s 上限) | 防 hang |

---

## §1.13 验收标准(SLA + KPI)

### §1.13.1 性能 SLA(2026-Q3 GA 目标)

| 指标 | MVP(R48-R50) | V1(R51-R55) | GA(R56+) |
|---|---|---|---|
| 报价 P50 | ≤ 1500 ms | ≤ 1000 ms | ≤ 800 ms |
| 报价 P95 | ≤ 4000 ms | ≤ 3500 ms | ≤ 3000 ms |
| 报价 P99 | ≤ 6000 ms | ≤ 5000 ms | ≤ 4500 ms |
| 报价无路径率(L1-L3 token) | ≤ 1% | ≤ 0.7% | ≤ 0.5% |
| 报价无路径率(L4-L5 token) | ≤ 10% | ≤ 7% | ≤ 5% |
| 上链成功率(广播后) | ≥ 95% | ≥ 97% | ≥ 98% |
| 滑点超出预期事件率(实际 PI > 报价 PI × 1.3) | ≤ 5% | ≤ 3% | ≤ 1.5% |
| 聚合层可用率 | ≥ 99.5% | ≥ 99.9% | ≥ 99.95% |

### §1.13.2 业务 KPI

| 指标 | 目标(GA) |
|---|---|
| 平均价差 vs 单源 Jupiter | 优 ≥ 0.05% 中位、优 ≥ 0.30% P90 |
| 用户报价确认率(报出后用户点确认) | ≥ 65% |
| 报价确认到广播平均耗时 | ≤ 1.5s |
| Pro 模式启用率(对比 UI) | ≥ 25% |
| AI 推荐滑点采纳率 | ≥ 80% |

---

## §1.14 监控埋点

埋点表 `agg_quote_events` + `agg_execution_events` 见 PRD 附录 A。

关键 Dashboard:
- **聚合器健康**:各源 P50/P95/P99 折线图(7d)/ 各源失败率 / 各源熔断次数(刷新 1 min)
- **业务效果**:价差 vs Jupiter 单源(中位 + P90)/ 报价确认率 / Pro 模式启用率(刷新 5 min)
- **流动性分布**:用户报价请求按 L1-L6 分布饼图 / 各级失败率(刷新 1 hour)
- **滑点准确度**:推荐 vs 实际 散点图 / 超出预期率(actual > recommended × 1.3)(刷新 1 hour)
- **降级监控**:fallback_used 率 / hard_fail 率 / 哪些源最常被切走(刷新 1 min)
- **成本**:API 调用次数 × 单价(各聚合器付费 tier 用量监控)(刷新 1 day)

告警 P0/P1/P2 见附录。

---

下游引用:
- §2 智能路由 + 签名广播(本章产出 calldata 输入)
- §6 风控引擎(本章产出 amount_in_usd / liquidity_level 输入)
- §7 监控告警(本章 §1.14 是其数据源之一)
# §2 智能路由 (Smart Routing) — 详细规格(R48)

> **模块编号**:§2 / **版本**:R48 (2026-05-08) / **PM-lead**:产品研究员
> **依赖模块**:§1 钱包托管 / §3 风控引擎 / §5 行情聚合 / §7 链上执行
> **被依赖**:§4 Agent 决策 / §6 跟单引擎 / §8 跨链桥

---

## §2.0 模块定位与北极星指标

### §2.0.1 模块定位

**智能路由(Smart Routing)是本产品在执行层的核心差异化模块**,负责将上游决策(买什么 / 卖什么 / 多少量)转换为链上最优执行路径。

用户感知:**不直接看到 SR**,但每一笔成交价、每一次"被夹"或"没被夹"、每一笔失败重试都由 SR 决定。SR 决定了产品宣传语中的那句"**成交价比竞品平均好 0.8% — 1.5%**"是否兑现。

**对标竞品定位**:

| 竞品 | 定位 | 我们的对标 |
|---|---|---|
| Jupiter (Solana) | 聚合器,DEX 路由 | §2.5 路径算法对标 + 超越 |
| 1inch Fusion (EVM) | Intent + RFQ | §2.5 RFQ 通道对标 |
| CowSwap | Batch + MEV 防 | §2.10 MEV 方案借鉴 |
| UniswapX | Dutch auction intent | §2.5 intent 模式 v2 引入 |
| Hashflow | RFQ + 0 滑点 | §2.8 滑点防御对标 |
| Bebop | 跨链 intent | §2.7 场景 C 对标 |
| Flashbots / Jito | MEV 基础设施 | §2.10 直接集成,不重造 |

我们**不是再造一个聚合器**,而是**做一个聚合器之上的智能调度器**:
- Solana 链上以 Jupiter v6 为底,我们做 Jito Bundle + 拆单 + 滑点动态调整
- EVM 链上以 1inch v6 / 0x Protocol 为底,我们做 Flashbots Protect + RFQ 选择
- 跨链以 LI.FI / Squid 为底,我们做桥选择 + 滑点二段防护

### §2.0.2 北极星指标(NSM)

**单一北极星指标**:**有效执行价差(Effective Price Improvement,EPI)**

```
EPI = (我们的成交价 - 同时刻 CEX mid price) / CEX mid price - 行业基线 EPI
```

- **行业基线**:Jupiter 在 Solana 上的平均 EPI = -0.65%(滑点+gas+spread)
- **我们的目标**:EPI ≥ -0.20%(即比 Jupiter 平均好 0.45 个百分点)
- **量化样本**:每 1000 笔实盘交易计算一次,与 CoinGecko / Binance mid price 对齐到秒级

### §2.0.3 二级指标

| 指标 | 目标值 | 测量周期 | 数据源 |
|---|---|---|---|
| 路由首次成功率(First-Try Success Rate) | ≥ 96% | 24h 滚动 | 内部埋点 |
| MEV 被夹率(Sandwich Hit Rate) | ≤ 0.3%(EVM)/ ≤ 0.1%(Solana via Jito) | 7d 滚动 | EigenPhi / Solscan MEV 标记 |
| 端到端确认时延 P50 / P95 | Solana 1.5s / 4s;EVM 14s / 35s | 实时 | RPC 时间戳 |
| 拆单单笔均价偏离主单价 | ≤ 0.15%(场景 B)/ ≤ 0.5%(场景 D) | 单笔回算 | 链上 receipt |
| 滑点超限退款触发率 | ≤ 1.5% | 7d 滚动 | minOut revert + 用户提示 |
| Gas 浪费率(over-priced gas) | ≤ 12%(actual / quoted) | 7d | EIP-1559 tx receipts |
| stuck tx 紧急加速触发率 | ≤ 2%(EVM) | 24h | mempool 监控 |

### §2.0.4 反指标(Guard Rails)

不能因为追北极星而牺牲:
- **执行成功率**:不得低于 96%(场景 A 单独 ≥ 92%)
- **用户感知时延**:点击到首条状态推送 ≤ 1s
- **资损红线**:任何路由 bug 导致 minOut 失效或 MEV 防护失效 → P0,SLA 30 分钟内回滚

---

## §2.1 用户故事

### US-2.1 散户单笔小额买入(Meme 狙击)
**场景**:Telegram 里 @bot,"买 $200 的 $PEPESOL"
**期望**:5 秒内确认成交,价格"差不多就行,别太离谱"
**SR 行为**:走场景 A 流程,单跳 Raydium AMM,Jito tip $0.05,滑点 12%,不拆单
**成功标准**:1.5s 内 Solana confirm,实际滑点 < 12%

### US-2.2 主流币大额转换(rebalance)
**场景**:App 内"换币",输入 30000 USDC → SOL
**期望**:"我能容忍 30 秒,但价格必须好"
**SR 行为**:场景 B,自动拆 4 笔(基于 24h 流动性深度算),走 Jupiter + 私有 RFQ 双询价,选最优,Jito Bundle 防夹
**成功标准**:平均成交价 vs Binance mid 价差 ≤ 0.15%,EPI ≥ -0.20%

### US-2.3 跨链转移($USDC Solana → $USDC Base)
**场景**:"把我 Solana 上 $5000 USDC 转到 Base 上买 $TOSHI"
**期望**:"60 秒到账,知道桥费多少"
**SR 行为**:场景 C,LI.FI 询价 → Wormhole / deBridge / CCTP 比对 → 选 CCTP(费 $0.5)→ 桥到 Base → Base 上 1inch + Flashbots
**成功标准**:总用时 < 60s,桥费透明展示,Base 端 Flashbots Protect 100% 走

### US-2.4 鲸鱼跟单(秒级)
**场景**:Agent 监听到信号,"3 秒内必须跟"
**期望**:"别错过,贵一点没事"
**SR 行为**:场景 D,直跳 Jupiter,Jito tip 顶配 $0.5,滑点 18%,不拆单,失败立即重试不计算最优
**成功标准**:< 3s 内 confirm,允许 EPI 牺牲到 -1.5%

### US-2.5 老手 Pro 模式(自定义)
**场景**:Pro 模式下要"指定走 Hashflow RFQ + Flashbots fast endpoint + 滑点 0.3%"
**期望**:UI 暴露所有参数,我自己点
**SR 行为**:跳过自动场景识别,走用户手动配置
**成功标准**:用户配置原样落到 tx,任何不满足条件直接 revert

### US-2.6 用户主动关闭 MEV 防护
**场景**:"我要走公开 mempool 看下到底会不会被夹"
**SR 行为**:respect 用户开关,但首次关闭弹一次警告"过去 30 天数据显示开启 MEV 防护可避免 0.3% 损失"

### US-2.7 失败重试可见性
**场景**:看到"成交失败 - 滑点超限,正在用更宽滑点重试..."
**SR 行为**:每次重试推送一条 status 到 chat,带原因 + 新参数
**成功标准**:重试 ≤ 3 次,每次推送时延 < 500ms

### US-2.8 stuck tx 加速
**场景**:gas 给低了,tx pending 90s 未 confirm
**SR 行为**:90s 未 confirm 触发紧急加速,replace-by-fee 提价 30%
**成功标准**:replace tx 在 30s 内 confirm,原 tx 自动 cancel

---

## §2.2 产品边界

### §2.2.1 In Scope
- DEX 路径选择(单跳 / 多跳 / 多 DEX 拆单)
- 中间币(intermediate token)智能选择
- 拆单(split routing)算法
- 滑点三档防御(quote / submit / on-chain)
- MEV 防护(Solana Jito / EVM Flashbots-类 / BSC bloXroute)
- Gas / priority fee 动态计算
- 失败分类 + 重试策略
- stuck tx 紧急加速
- 实时执行进度推送

### §2.2.2 Out of Scope
- 决定**买什么 / 卖什么 / 多少量** → §4 Agent 决策
- 钱包私钥管理 / 签名 → §1 钱包托管
- 行情数据来源 → §5 行情聚合
- 风控规则(最大单笔 / 黑名单) → §3 风控引擎
- 跟单源选择 / 信号生成 → §6 跟单引擎
- UI 渲染 → §9 前端

### §2.2.3 接口契约

**输入**:
```
RouteRequest {
  user_id, chain, token_in, token_out, amount_in,
  scenario_hint: 'A'|'B'|'C'|'D'|'auto',
  user_overrides: { slippage?, mev_level?, rpc?, deadline_sec? },
  priority: 'speed'|'price'|'balanced',
  context: { is_copy_trade, source_signal_id, max_acceptable_slippage_pct }
}
```

**输出**:
```
ExecutionPlan {
  legs: [{ dex, pool, amount_in, min_amount_out, deadline }],
  mev_strategy: { type, endpoint, tip },
  gas_strategy: { type, max_fee, priority_fee },
  retry_policy: { max_attempts, backoff_ms, slippage_bump_pct }
}
```

---

## §2.3 竞品全景对比(7 竞品 × 12 维度)

| 维度 | UniswapX | 1inch Fusion+ | CowSwap | Hashflow | Bebop | Flashbots Protect | Jito Block Engine |
|---|---|---|---|---|---|---|---|
| **核心模式** | Intent + Dutch auction | Intent + RFQ + Pathfinder v2 | Batch auction (CoW) | RFQ-only | Intent + 跨链 | 私有 mempool | Solana 区块构建 |
| **路径算法** | Resolver 自决 | Pathfinder v2 (DAG + DP) | Solver 竞争 | MM 直接报价 | Solver 竞争 | N/A | N/A |
| **拆单算法** | Resolver 决定 | Linear programming + 递归 | Solver 决定 | 不拆(MM 单点) | Solver 决定 | N/A | N/A |
| **MEV 防护** | Resolver 私池 | Fusion 默认私池 | Batch + uniform price | RFQ 锁价 0 滑点 | 私池 + intent | Flashbots Auction | Bundle + tip |
| **滑点机制** | Dutch auction 自动收紧 | RFQ 锁价 / AMM minOut | 固定 limit price | 0 滑点(quote 即成交价) | RFQ + minOut | N/A | minOut(由调用方) |
| **失败重试** | 订单超时(默认 5min) | 30s 未 fill 重报 | 5min epoch 自动 | RFQ 5s 失效 | Intent expiry | 25 blocks 失败回 mempool | Bundle drop 即结束 |
| **MEV 被夹率** | < 0.05% | < 0.1% | 0%(uniform price) | 0%(锁价) | < 0.2% | < 0.05% | < 0.1%(Jito 数据) |
| **平均节省 vs 公开 mempool** | 0.8 - 1.2% | 0.5 - 1.0% | 0.3 - 0.7% | -0.2 - 0.3% | 0.4 - 0.8% | 0.3 - 0.6% | 0.2 - 0.5% |
| **链覆盖** | 5 EVM | 11 EVM + Solana | 5 EVM | 16 EVM | 7 EVM | ETH only | Solana only |
| **小额费率** | 0% | 0% | 0% | MM spread | 0% | 0% | tip 浮动 |
| **公开 SDK / API** | UniswapX SDK | Fusion SDK + REST | CoW SDK + REST | Hashflow SDK | Bebop API | Flashbots RPC | Jito gRPC + RPC |

### §2.3.2 关键观察

1. **没有任何一座桥能覆盖所有最优组合** — 4 场景需要不同 DEX 组合
2. **Pathfinder DAG 算法** → §2.5 我们的多跳算法直接对标 1inch
3. **CoW uniform price** 概念 → 我们场景 B 拆单借鉴
4. **Hashflow RFQ 0 滑点** → 主流币大单优先选项

---

## §2.4 我们的差异化

### §2.4.1 三大差异化矩阵

| 差异化点 | 竞品现状 | 我们的方案 | 用户可感知收益 |
|---|---|---|---|
| **场景化路由** | 一刀切(Jupiter 不分场景,1inch 分但粗) | 4 场景独立参数矩阵(§2.7) | 大单省 0.5%,小单快 1s |
| **链原生 MEV 集成** | EVM 上 Flashbots,Solana 上 Jito,跨链没有 | 5 链统一抽象,自动选最优 MEV 通道 | 被夹率 < 0.3% 全链 |
| **滑点三档防御 + 动态调整** | 大多只做 minOut 一档 | quote / submit / on-chain 三档 + 失败时动态放大 | 失败率 ↓ 40% |

### §2.4.2 与竞品的具体超越点

1. **Solana 拆单** — Jupiter 不主动拆单,我们在 $5000+ 大单上拆 3-5 笔,省 0.3-0.6%
2. **跨链 MEV** — Bebop 在 destination chain 不一定走 MEV 私池,我们强制 destination 用 Flashbots / Jito
3. **失败重试可见性** — 1inch 失败就完了,我们重试每步推送给用户(§2.12)
4. **场景识别** — 用户不用选,SR 自动按 amount + token + 流动性 识别场景(§2.7.0)

### §2.4.3 不做的事

- **不做 Dutch auction**:用户感知不直观
- **不做 batch auction**:5min 太慢,与本产品"快"冲突
- **不自建 RFQ 网络**:量级不够
- **不自研 MEV 防护**:Flashbots / Jito 已是行业标准

---

## §2.5 路径选型(单跳 / 多跳 / RFQ / Intent)

### §2.5.0 路径决策总览

```
                    ┌────────────────────────────┐
                    │   RouteRequest 进入 SR      │
                    └────────────┬───────────────┘
                                 │
                       ┌─────────▼─────────┐
                       │  场景识别 (§2.7.0) │
                       └─────────┬─────────┘
                                 │
       ┌──────────────┬──────────┼──────────┬──────────────┐
       ▼              ▼          ▼          ▼              ▼
   场景 A         场景 B      场景 C    场景 D         Pro 自定义
   (Meme 狙击)   (主流币大单) (跨链)   (鲸鱼跟单)
       │              │          │          │              │
       ▼              ▼          ▼          ▼              ▼
   单跳直跳        多通道询价   桥 + DEX   单跳直跳      用户指定
   (Jupiter)      (RFQ + DEX)  组合      (Jupiter)      strict
```

### §2.5.1 单跳 vs 多跳决策矩阵

| 条件 | 选单跳 | 选多跳 |
|---|---|---|
| `token_in` ↔ `token_out` 在主流 DEX 有直接池子 且池子流动性 ≥ 100×amount_in | ✓ | |
| 直接池子流动性不足 | | ✓ |
| 直接池子价格冲击 > 0.5% 且存在中间币路径价格冲击 < 0.5% | | ✓ |
| 多跳总 gas > 单跳 gas × 2 且单跳价格冲击 < 1% | ✓ | |
| 链是 BSC / Arb(gas 极便宜) | | ✓ 优先 |
| 链是 ETH(gas 贵) | ✓ 优先 | |

**算法**:
```
score(path) = output_amount - gas_cost_in_token_out - mev_risk_penalty

mev_risk_penalty(单跳) = output_amount × sandwich_risk_pct(pool, amount)
mev_risk_penalty(多跳) = sum(每跳 sandwich_risk_pct)

最终选 score 最高的路径,但必须满足:
  - hop_count ≤ 4(超过 4 跳 gas 收益负向)
  - 总 gas / amount_in ≤ 2%(场景 A)/ 0.3%(场景 B)
```

### §2.5.2 RFQ 通道决策矩阵

**何时优先 RFQ**:

| 条件 | 走 RFQ |
|---|---|
| Token 在 RFQ MM 列表(主流 + 部分热门 alt) | ✓ |
| amount_in ≥ $1,000 | ✓ |
| 用户优先级 = 'price' | ✓ |
| 时效要求 < 3s | ✗(场景 D 不走) |

最优 RFQ 报价 vs 最优 AMM 路径 取 output 大者。

### §2.5.3 决策表(场景 × 通道)

| 场景 | 主通道 | 备用通道 | Fallback |
|---|---|---|---|
| A (Meme) | DEX 单跳(Jupiter / 1inch direct) | — | 失败重试同通道 + 放大滑点 |
| B (主流大单) | RFQ + DEX 多跳并行询价 | DEX 多跳 | DEX 单跳 |
| C (跨链) | LI.FI / Squid intent | Bebop intent | 手动桥 + 目的链 DEX |
| D (跟单) | DEX 单跳 + Jito Bundle / Flashbots fast | — | 重试 + tip 翻倍 |
| Pro | 用户指定 | — | 失败即 revert |

---

## §2.6 中间币优先级矩阵(每链独立)

### §2.6.1 Solana 链

| 优先级 | 中间币 | 选用条件 |
|---|---|---|
| 1 | USDC | token_in 或 token_out 是主流币(Solana TVL 35% 在 USDC 池) |
| 2 | SOL | token_in/out 是 meme 或 LP-thin token(Raydium meme 池 80%+ pair = SOL) |
| 3 | USDT | USDC 池流动性 < 1.5x USDT 池 |
| 4 | mSOL / jitoSOL | 用户持有 LST 时直接源头 |

**特殊规则**:
- meme 币 → 强制走 SOL 中间(USDC pair 多数不存在或 LP < $10k)
- 大额(> $50k) → 必走 USDC

### §2.6.2 Ethereum 主网

| 优先级 | 中间币 | 选用条件 |
|---|---|---|
| 1 | USDC | 默认(Uniswap v3 USDC pair TVL $2B+) |
| 2 | WETH | gas 贵 / 路径短优先 |
| 3 | USDT | USDC 不深 |
| 4 | DAI | 稳定币组合 |
| 5 | WBTC | BTC 关联 token |

**特殊规则**:ETH gas 贵,**多跳总跳数严格限制 ≤ 3**;Gas > 80 gwei 时直接走 1inch RFQ。

### §2.6.3 Base / BSC / Arbitrum

| 链 | 主中间币 | 备用 |
|---|---|---|
| Base | USDC(原生) | WETH > cbETH |
| BSC | USDT > WBNB(meme) > USDC | BUSD R48 移除 |
| Arbitrum | USDC(原生) > WETH | USDT > ARB |

---

## §2.7 拆单 — 4 场景独立矩阵

### §2.7.0 场景识别算法(自动)

```python
def identify_scenario(req: RouteRequest) -> Scenario:
    if req.scenario_hint != 'auto':
        return req.scenario_hint

    if req.context.is_copy_trade:
        return 'D'  # 跟单永远场景 D

    if req.chain != req.token_out_chain:
        return 'C'  # 跨链

    amount_usd = price_in_usd(req.token_in, req.amount_in)
    pool_liq = get_pool_liquidity(req.token_in, req.token_out, req.chain)

    if amount_usd < 500 and pool_liq < 100_000:
        return 'A'  # meme 早期

    if amount_usd >= 5000 and pool_liq >= 1_000_000:
        return 'B'  # 主流大单

    return 'B-mini' if pool_liq >= 500_000 else 'A'
```

### §2.7.1 场景 A — Meme 早期狙击

**特征**:$100 - $500 / 流动性 $10k - $100k / 用户要"快"

| 维度 | 参数 | 依据 |
|---|---|---|
| **是否拆单** | **不拆** | 拆单引入 latency,失去狙击窗口 |
| **路径** | 单跳直跳(SOL → meme via Raydium / Orca) | Jupiter 数据:meme 单跳 80%+ |
| **中间币** | 链原生(SOL / WETH / WBNB) | meme 币 USDC pair 多数不存在 |
| **滑点(quote 时)** | 12% | Solana meme 平均价格冲击 + buffer |
| **滑点(链上 minOut)** | 18% | quote 时 12% × 1.5 = 链上保护 |
| **MEV 防护** | Solana: Jito Bundle tip $0.05;EVM: Flashbots fast | meme 抢跑活跃区,必须防 |
| **优先费 / Gas** | Solana: Jito tip + priority fee 0.001 SOL;EVM: gas × 1.5 | 抢区块 |
| **deadline** | 30s | Solana 块时 0.4s 余量充足 |
| **失败回退** | 滑点 +5%,重试 1 次,失败即放弃 | 时间窗口短 |
| **目标 P95 时延** | < 3s(Solana) / < 20s(EVM) | — |

### §2.7.2 场景 B — 主流币大单

**特征**:$5,000 - $50,000+ / 流动性 $1M+ / 用户要"价格好"

| 维度 | 参数 | 依据 |
|---|---|---|
| **是否拆单** | **拆**(基于流动性深度算) | 单笔大额价格冲击线性递增 |
| **拆单触发阈值** | amount_usd ≥ $5,000 **且** 单笔预估价格冲击 > 0.3% | Uniswap v3 公开数据:0.3% 是大多数主流池子的拐点 |
| **拆几笔(算法)** | `n = ceil(price_impact_pct / 0.15)`,clip 到 [2, 6] | 让每笔冲击 ≤ 0.15% |
| **拆单方式** | TWAP 等额拆 | 简单 + 抗预测(随机扰动 ± 5%) |
| **间隔策略** | Solana: 1.5s ± 0.3s;EVM: 13s ± 3s(每块一笔) | 块时为基础,随机抗 sandwich pattern 识别 |
| **路径** | 多跳并行询价(RFQ + DEX),每笔独立选路 | 子单价格变化时重新选最优 |
| **中间币** | 主流稳定币(USDC 优先) | 流动性最深 |
| **滑点(quote 时)** | 0.5% per leg | 主流池子滑点小 |
| **滑点(链上 minOut)** | 1.0% per leg | quote × 2 |
| **MEV 防护** | Solana: Jito Bundle tip $0.2 全程;EVM: Flashbots Protect 强制 | 大单 MEV 价值高 |
| **优先费 / Gas** | EIP-1559 base × 1.2 + priority $0.5 | 不抢首区块,稳定确认 |
| **deadline** | 单笔 60s,总订单 5min | 给 RFQ 询价空间 |
| **失败回退** | 单笔失败 → 其余笔继续 + 失败笔放大滑点重试 1 次 | 不让一笔失败拖垮整单 |
| **目标 EPI** | ≥ -0.20% vs CEX mid | 北极星 |

**拆单具体公式**:
```python
def split_count_b(amount_usd: float, pool_liquidity_usd: float) -> int:
    impact_pct = amount_usd / (pool_liquidity_usd + amount_usd) * 100
    if impact_pct < 0.3:
        return 1  # 不拆
    n = math.ceil(impact_pct / 0.15)
    return max(2, min(6, n))  # clip 到 [2, 6]
```

### §2.7.3 场景 B-mini(中间地带)

**特征**:$500 - $5,000 / 流动性中等
- 拆 1-2 笔(amount > $2,500 且冲击 > 0.5% 时拆 2 笔)
- 滑点 quote 1% / 链上 2%
- MEV 防护强制开

### §2.7.4 场景 C — 跨链交易

**两段独立流程**:

**第一段:source chain → bridge token**

| 维度 | 参数 |
|---|---|
| **拆单** | 不拆(桥手续费按笔收) |
| **桥选择** | LI.FI / Squid 多桥并行询价 |
| **桥优先级** | 1. CCTP(USDC 原生跨链)2. Wormhole NTT 3. deBridge / Stargate 4. LayerZero v2 |
| **滑点(桥端)** | 0%(锁定 amount) |
| **deadline** | 5 分钟 |

**第二段:destination chain DEX swap**

| 维度 | 参数 |
|---|---|
| **拆单** | 按 destination chain 的场景识别 |
| **滑点** | 0.8%(quote)/ 1.5%(链上) — 桥到账后价格可能变了,放宽 |
| **MEV 防护** | destination chain 必走 Flashbots / Jito |
| **失败回退** | 第二段失败 → 资金停留在 destination chain,通知用户手动恢复 |

**总目标时延**:USDC CCTP 60-120s / Wormhole 90-180s / deBridge 30-60s

### §2.7.5 场景 D — 鲸鱼跟单

**特征**:秒级时效 / 不能错过 / 接受多滑点

| 维度 | 参数 | 依据 |
|---|---|---|
| **是否拆单** | **不拆** | 拆单 = latency 增加 = 错过 |
| **路径** | 直跳 Jupiter / 1inch direct | 绝对最快 |
| **中间币** | 不绕道(强制单跳) | — |
| **滑点(quote 时)** | 12-18% | 鲸鱼带动价格,需大滑点容忍 |
| **滑点(链上 minOut)** | 25% | 极致保护 |
| **MEV 防护** | Solana: Jito Bundle tip $0.5 + atomic bundle "buy + sell-stop";EVM: Flashbots fast | Bundle 原子性保证 |
| **优先费** | Solana: 0.005 SOL;EVM: gas × 2 | 抢这个区块或下一个 |
| **deadline** | 5s | 失效就完了 |
| **重试** | 1 次,滑点 +5%,tip × 2 | 第二次失败放弃 |
| **目标 P95 时延** | Solana < 2s,EVM < 15s | — |

### §2.7.6 4 场景对比汇总表

| 维度 | A (Meme) | B (主流大单) | C (跨链) | D (跟单) |
|---|---|---|---|---|
| 金额 | $100-500 | $5k-50k+ | 任意 | 任意 |
| 拆单 | 否 | 是(2-6 笔) | source 否 / dest 按 B | 否 |
| 主路径 | 单跳 | 多跳 + RFQ | 桥 + DEX | 单跳 |
| 中间币 | 链原生 | USDC | USDC(桥) | 无 |
| Quote 滑点 | 12% | 0.5% | 0.8% | 12-18% |
| 链上 minOut | 18% | 1.0% | 1.5% | 25% |
| MEV 防护 | 标配 | 强制 | dest 强制 | 顶配 Bundle |
| Jito tip | $0.05 | $0.2 | dest $0.2 | $0.5 |
| EVM gas 倍数 | base × 1.5 | base × 1.2 | dest × 1.2 | base × 2 |
| Deadline | 30s | 5min | 5min | 5s |
| 重试上限 | 1 | 子单各 1 | 1 | 1 |
| 目标 P95 | 3s / 20s | 30s / 90s | 120s | 2s / 15s |
| 北极星权重 | 速度 | EPI | 总成本 | 不错过率 |

---

## §2.8 滑点三档防御

### §2.8.1 三档总览

| 档 | 触发时机 | 机制 | 谁实施 |
|---|---|---|---|
| **第一档:Quote 时** | 询价阶段(发交易前) | 报价 spread 检查 | SR 内部 |
| **第二档:Submit 时** | 提交 tx 前最后一刻 | Pre-flight simulate(eth_call / Solana simulate) | SR + RPC |
| **第三档:On-chain** | 链上执行时 | minAmountOut revert | 智能合约(DEX router) |

### §2.8.2 第一档 — Quote 时滑点

询价时拿 N 个 DEX 报价,如果同一时刻不同 DEX 报价差异 > X%,触发保护。

```python
def quote_check(quotes: List[Quote], scenario: str) -> bool:
    if len(quotes) < 2: return True
    prices = [q.output / q.input for q in quotes]
    spread = (max(prices) - min(prices)) / min(prices)
    threshold = {'A': 0.05, 'B': 0.01, 'C': 0.02, 'D': 0.08}[scenario]
    if spread > threshold:
        raise QuoteSpreadTooLarge(spread=spread, threshold=threshold)
    return True
```

### §2.8.3 第二档 — Submit 时滑点(Pre-flight Simulate)

签名 + 广播之前,先调用 `eth_call`(EVM)或 `simulateTransaction`(Solana)在最新链上状态上模拟一遍。

如果 actual_out < expected_min_out → 链状态变了,我们的 minOut 已经不可达,触发 §2.9 动态调整。

### §2.8.4 第三档 — On-chain minAmountOut

每笔 swap 都在链上 router 合约层带 `minAmountOut`,链上原子检查。

| 链 | Router | minAmountOut 字段 |
|---|---|---|
| Solana / Jupiter | Jupiter Aggregator v6 | `slippageBps`(基点) |
| ETH / 1inch | 1inch v6 router | `minReturn` |
| ETH / Uniswap | Universal Router | `minOut` |
| Base / Aerodrome | Aerodrome Router | `amountOutMin` |
| BSC / PancakeSwap | Pancake Smart Router v3 | `amountOutMinimum` |

**关键不变量**:**所有 SR 发出的 tx 必须带 minOut,缺失即拒签**。

### §2.8.5 三档参数(按场景)

| 场景 | Quote spread 阈值 | Preflight decay 阈值 | On-chain minOut 滑点 |
|---|---|---|---|
| A | 5% | 1% | 18% |
| B | 1% | 0.3% | 1.0% per leg |
| C | 2%(每段) | 0.5% | 1.5%(目的链) |
| D | 8% | 2% | 25% |

---

## §2.9 滑点动态调整(失败重试时)

### §2.9.1 动态调整公式

```python
def bump_slippage(original_pct: float, attempt: int, scenario: str) -> float:
    multiplier = {'A': 1.5, 'B': 1.3, 'C': 1.4, 'D': 1.4}[scenario]
    new_slippage = original_pct * (multiplier ** attempt)
    cap = {'A': 30, 'B': 5, 'C': 8, 'D': 50}[scenario]
    return min(new_slippage, cap)
```

### §2.9.2 用户阈值约束

`max_acceptable_slippage_pct` 是用户硬上限。如果 bump 后超过,不再重试,直接失败。

### §2.9.3 价格恶化保护(防止追涨)

```python
def should_retry(current_price, original_price, max_chase_pct=10):
    increase = (current_price - original_price) / original_price * 100
    return increase <= max_chase_pct
```

`max_chase_pct` 默认:A 30% / B 1.5% / C 3% / D 25%。

---

## §2.10 MEV 防夹 — 每条链独立方案

### §2.10.1 Solana — Jito Block Engine

| 参数 | 值 |
|---|---|
| Block Engine endpoint | `mainnet.block-engine.jito.wtf` |
| Tip account | 8 个轮换 tip account(防热点) |
| Tip 金额(场景 A) | 0.0003 SOL ≈ $0.05 |
| Tip 金额(场景 B) | 0.001 SOL ≈ $0.2 |
| Tip 金额(场景 D) | 0.003 SOL ≈ $0.5 |
| Bundle 最大 tx 数 | 5 |
| Bundle 提交超时 | 200ms |
| 失败标识 | `bundleId not in confirmed bundles` after 8 slots(~3.2s) |

### §2.10.2 Ethereum 主网 — Flashbots Protect

| 参数 | 值 |
|---|---|
| RPC URL | `https://rpc.flashbots.net/fast` |
| 备用 builder | `rpc.titanbuilder.xyz`, `rpc.beaverbuild.org` |
| Refund(MEV-Share) | 默认开,80% 退用户 |
| Bundle 模式(场景 D) | `eth_sendBundle` |
| 失败标识 | tx 25 blocks 未上链(~5min) |

**两个 endpoint**:`/fast`(默认,所有 builder)/ `/`(strict,只 Flashbots builder)。我们默认 `/fast`,Pro 用户可切 `/`。

### §2.10.3 BSC — bloXroute Protect

| 参数 | 值 |
|---|---|
| RPC URL | `https://bsc.rpc.blxrbdn.com/` |
| Auth header | `Authorization: <bloxroute_key>` |
| 备用方案 | 公开 RPC(48Club 也提供 MEV 保护) |

### §2.10.4 Base — Coinbase 私池

- 默认:`https://mainnet-preconf.base.org/`(Coinbase Sequencer 私序列)
- 备用:Flashbots on Base(beta)

### §2.10.5 Arbitrum — 私序列

- 默认 sequencer 模式,**MEV 风险低**
- 大单仍建议走 Aori 等私池

### §2.10.6 5 链 MEV 防护汇总表

| 链 | 默认通道 | Tip / 费用 | 用户可关 | 时延成本 vs 公开 |
|---|---|---|---|---|
| Solana | Jito Bundle | $0.05-0.5(tip) | 是 | +0.5s |
| ETH | Flashbots /fast | 0(MEV-Share refund) | 是 | +1-3s |
| BSC | bloXroute | $0(API 免费层) | 是 | +1s |
| Base | Coinbase preconf | 0 | 是 | -0(快于公开) |
| Arb | 默认 sequencer | 0 | N/A | 0 |

---

## §2.11 用户级 MEV 控制

### §2.11.1 三级控制

| 级别 | 入口 | 行为 |
|---|---|---|
| **Default(普通用户)** | 自动 | 按 §2.10 默认走 MEV 私池 |
| **Pro 关闭** | Settings → MEV 防护 → Off | 走公开 mempool / 公共 RPC |
| **Pro 自定义** | Settings → MEV 防护 → Custom RPC | 用户填 RPC URL 或选预设 |

### §2.11.2 关闭 MEV 防护时的警告

首次切换为 Off 时弹一次 modal,提示"过去 30 天数据显示开启防护可避免平均 0.3% 的损失",确认后 24h 持久化。

### §2.11.3 Pro 模式自定义 RPC 白名单

| 链 | 预设 RPC 白名单 |
|---|---|
| ETH | Flashbots(/fast, strict)、Eden Network、MEV Blocker、Bloxroute、Public(警告) |
| BSC | bloXroute、48Club、Public(警告) |
| Base | Coinbase Preconf、Flashbots Base、Public(警告) |
| Solana | Helius、Triton、Public mainnet-beta(警告) |

---

## §2.12 重试策略

### §2.12.1 失败分类

| 失败类型 | 触发条件 | 是否重试 | 重试上限 | 重试间隔 | 重试时调整 |
|---|---|---|---|---|---|
| **F1: Quote spread 过大** | §2.8.2 触发 | 是 | 2 | 500ms | 重新询价 |
| **F2: Preflight 失败** | §2.8.3 触发 | 是 | 1 | 0(立即) | 重新询价 |
| **F3: 滑点 revert(链上)** | `INSUFFICIENT_OUTPUT_AMOUNT` | 是 | 场景定 | 见 §2.12.2 | 滑点 +bump(§2.9) |
| **F4: Gas 不足** | `out of gas` / `OutOfMemory` | 是 | 1 | 0 | gas × 1.3 |
| **F5: Nonce 冲突(EVM)** | `nonce too low / too high` | 是 | 2 | 200ms | 重取 nonce |
| **F6: 余额不足** | `insufficient balance` | 否 | 0 | — | 报错给用户 |
| **F7: Token 不存在 / 池子无** | `pool not found` | 否 | 0 | — | 报错给用户 |
| **F8: stuck tx(pending 超时)** | EVM 90s / Solana 5s 未确认 | 是 | 1 | 0 | replace-by-fee(§2.14) |
| **F9: 网络超时(RPC)** | HTTP timeout / RPC 5xx | 是 | 3 | 1s/2s/5s | 切下个 RPC |
| **F10: Bundle drop(MEV)** | Jito bundle / Flashbots inclusion 失败 | 是 | 1 | 0 | tip × 2 或 fallback 公开 mempool(场景 D) |
| **F11: 桥失败(场景 C)** | bridge tx 失败 | 是 | 1 | 0 | 切备用桥 |
| **F12: 签名失败(用户拒签)** | Pro 模式用户取消 | 否 | 0 | — | 报错 |

### §2.12.2 各场景重试上限矩阵

| 失败类型 | 场景 A | 场景 B | 场景 C | 场景 D |
|---|---|---|---|---|
| F3 滑点 revert | 1 次 | 子单 1 次 | 1 次 | 1 次 |
| F4 Gas 不足 | 1 次 | 1 次 | 1 次 | 1 次 |
| F8 stuck tx | 1 次 | 1 次 | 1 次 | 0 次(快比稳重要) |
| F9 RPC 超时 | 3 次 | 3 次 | 3 次 | 1 次(快) |
| F10 Bundle drop | 1 次 | 1 次 | 1 次 | 2 次(关键) |

### §2.12.3 重试间隔依据

链平均块时:
- Solana: 0.4s → 重试间隔最小 1s
- ETH: 12s → 重试间隔 13s(下个块)
- Base: 2s → 重试间隔 2.5s
- BSC: 3s → 重试间隔 3.5s
- Arb: 0.25s → 重试间隔 1s

### §2.12.4 用户感知重试

每次重试前推送一条 status:
```
"成交未达预期,正在以更宽滑点重试(2/3)..."
"网络超时,切换 RPC 节点重试(1/3)..."
"价格已超过你的容忍上限,本次跟单放弃"
```

**推送时延要求**:从触发到 chat 显示 ≤ 500ms。

---

## §2.13 Gas / 优先费动态策略

### §2.13.1 EVM EIP-1559 算法

```python
def eip1559_gas(chain, scenario, current_base_fee):
    recent_priorities = get_recent_priority_fees(chain, blocks=10)
    p75 = percentile(recent_priorities, 75)
    p95 = percentile(recent_priorities, 95)
    priority_target = {'A': p95, 'B': p75, 'C': p75, 'D': int(p95 * 1.5)}[scenario]
    max_fee = current_base_fee * 2 + priority_target
    return {'maxPriorityFeePerGas': priority_target, 'maxFeePerGas': max_fee}
```

### §2.13.2 Solana priority fee 算法

```python
def solana_priority_fee(scenario, account_keys):
    recent_fees = await rpc.getRecentPrioritizationFees(account_keys)
    p75 = percentile(recent_fees, 75)
    p95 = percentile(recent_fees, 95)
    priority = {'A': p95, 'B': p75, 'C': p75, 'D': int(p95 * 1.5)}[scenario]
    return max(priority, 1000)  # 至少 1000 micro-lamports/CU
```

### §2.13.3 拥堵升级阈值

| 链 | 正常 priority | 拥堵 priority(× 倍数) |
|---|---|---|
| ETH | P75 | × 1.5 |
| Base | P75 | × 1.2 |
| BSC | P75 | × 1.3 |
| Arb | P75 | × 1.1 |
| Solana | P75 | × 1.5 |

---

## §2.14 紧急加速(Stuck Transaction)

### §2.14.1 Stuck 检测

**EVM**:tx 已广播,90s 未上链 → 触发
**Solana**:5s 未达 `processed`(最早 commitment)→ 触发

### §2.14.2 EVM Replace-by-Fee(RBF)

```python
def replace_by_fee(stuck_tx):
    new_priority = stuck_tx.priority_fee * 1.3  # EIP-1559 协议要求最低
    new_max_fee = stuck_tx.max_fee * 1.3
    new_tx = build_tx(
        to=stuck_tx.to, data=stuck_tx.data, value=stuck_tx.value,
        nonce=stuck_tx.nonce,  # 必须同 nonce
        priority_fee=new_priority, max_fee=new_max_fee,
    )
    sign_and_broadcast(new_tx)
```

### §2.14.3 Solana 重发

Solana 没有 nonce 概念,但 blockhash 会过期(150 slots ~ 60s)。重新拿 blockhash + 重签 + 加费 50%。

### §2.14.4 加速次数上限

- EVM: 1 次 RBF
- Solana: 2 次重发

---

## §2.15 验收标准

### §2.15.1 上线必达 SLA(GA 阻塞项)

| 指标 | 标准 |
|---|---|
| 路由首次成功率 | ≥ 96% |
| MEV 被夹率 | ≤ 0.3%(EVM)/ ≤ 0.1%(Solana) |
| EPI 北极星 | ≥ -0.20% |
| 端到端时延 P95 | Solana 4s / EVM 35s |
| stuck tx 加速成功率 | ≥ 90% |
| 滑点 revert 重试成功率 | ≥ 70% |

### §2.15.2 4 场景独立 KPI

| 场景 | 关键 KPI | 阈值 |
|---|---|---|
| A | 时延 P95 < 3s(SOL)/ 20s(EVM) | 强制 |
| A | 成功率 ≥ 92%(meme 容忍略低) | 强制 |
| B | EPI ≥ -0.15% | 强制 |
| B | 拆单子单成功率 ≥ 98% | 强制 |
| C | 端到端总时延 P95 ≤ 180s | 强制 |
| C | 桥 + dest swap 总损耗 ≤ 0.6% | 强制 |
| D | 信号触发到 confirm P95 ≤ 5s | 强制 |
| D | 不错过率 ≥ 99% | 强制 |

### §2.15.3 资损红线(P0,30 分钟回滚)

- minOut 失效(任意一笔 tx 出去没带 minOut)
- MEV 防护静默关闭
- 拆单逻辑 bug 导致单子互相对夹
- 跨链场景资金停在桥
- 重试无上限导致用户被多次扣 gas

---

## §2.16 监控埋点

### §2.16.1 必埋点(每笔 tx)

`smart_routing_traces` 表存:trace_id / scenario / chain / token_in/out / amount_in_usd / path_type / hops_count / split_count / split_intervals_ms / slippage_quote_pct / slippage_minout_pct / slippage_actual_pct / mev_channel / mev_tip_usd / gas_strategy / gas_budget_usd / gas_actual_usd / retry_count / retry_reasons / quote_latency_ms / preflight_latency_ms / broadcast_latency_ms / confirm_latency_ms / total_latency_ms / status / output_amount / epi_pct / is_sandwiched / created_at

### §2.16.2 实时仪表盘

| 仪表 | 频率 | 报警阈值 |
|---|---|---|
| 全链首次成功率 | 1 min | < 90% 报警 |
| MEV 被夹率(滚动 1h) | 5 min | EVM > 0.5% / Solana > 0.2% 报警 |
| 各场景 P95 时延 | 1 min | 超阈值报警 |
| Gas 浪费率 | 5 min | > 20% 报警 |
| 重试率 | 5 min | > 25% 报警 |
| stuck tx 比例 | 5 min | > 5% 报警 |

### §2.16.3 异常 tx 自动归档

- EPI < -2%(成交价远差于市场)
- 滑点实际 > 链上 minOut × 0.9(滑点用满 90%,接近被夹)
- 重试 ≥ 2 次
- 总时延 > P95 × 2

PM 每周回看 anomalies 优化参数。
# §3 钱包基础功能 — 详细规格(R48)

> 三类用户共存:小白能上手 / Pro 能掌控 / Agent 能自动。

---

## §3.0 模块定位

### 3.0.1 一句话定位

> 钱包是 AI 交易产品的"账户底盘 + 风控前哨":对小白是钱包,对 Pro 是签名审核台,对 Agent 是密钥服务。

### 3.0.2 三类用户视角

| 用户类型 | 核心诉求 | 模块表现 |
|---|---|---|
| 小白(60%) | 不丢钱、不被骗、能下单 | 引导创建 → 强制备份 → 默认全自动 ≤$500 |
| Pro(30%) | 自己掌控 Gas / 路径 / 滑点 | 进阶模式开关 + Pre-Sim 详情 + 自定义 RPC |
| Agent-First(10%) | 把钱交给 AI、能撤销、能查账 | 多钱包独立策略 + HITL 倒计时撤销 + Audit Log |

---

## §3.1 用户故事(8 个)

### US-WAL-01:小白第一次创建钱包
> 第一次接触加密的内地用户,希望 90 秒内拿到可以收 USDC 的钱包,过程不出现 5 个以上术语
> **验收**:从点"开始"到看到收款地址 ≤ 90s

### US-WAL-02:小白第一次大额转账被拦
> 想转 $1500 USDC,App 拦一下、让我再看一眼地址(防剪贴板劫持)
> **验收**:≥$1000 必须二次确认页 + 地址前 6/后 4 大字号 + 6 位 App 密码

### US-WAL-03:Pro 用户导入硬件钱包前置策略
> 用 WalletConnect 接 Ledger,Agent 给"建议",签名我自己来
> **验收**:支持 WC v2,Agent 标记为"建议模式",每笔签名我手动批准

### US-WAL-04:Pro 用户检查 approve 风险
> 看到"将允许 Jupiter 花你的 USDC,无限额度"的明确警告,可改成 1.1x 本次交易额度
> **验收**:approve 默认渲染"无限额度"红字 + "改为 X.XX USDC"按钮

### US-WAL-05:Agent 自动用户多钱包隔离
> 3 个钱包(主仓 / 试验 / 老婆账户),给"试验仓"挂 Agent 跑高频,主仓和老婆账户钱不会被动
> **验收**:Agent 只能动绑定钱包,跨钱包转账必须人工 + 6 位密码

### US-WAL-06:小白助记词丢失场景
> App 明确告诉我"找回需要助记词,我们救不了"
> **验收**:登录失败页有"找回 = 助记词,无助记词无法恢复" + 教育页跳转

### US-WAL-07:小白被钓鱼合约签名
> 钱包在签名前告诉我"这笔签名将转走你 $5000 SOL"
> **验收**:Pre-Sim 必须显示"你将失去:5.2 SOL ≈ $5142.31",红色,默认按钮变"取消"

### US-WAL-08:Agent-First 用户日终对账
> 每个钱包能看到"Agent 操作了几次 / 总盈亏 / 每笔时间戳"
> **验收**:钱包详情 → "Agent 活动" tab,展示 7 天 / 30 天聚合 + 每笔 Tx hash 链接

---

## §3.2 产品边界

### 3.2.1 我们做(In Scope,R48)

| # | 功能 | 优先级 |
|---|---|---|
| 1 | EOA 钱包创建(Solana + EVM 多链同助记词) | P0 |
| 2 | 助记词 / 私钥导入 | P0 |
| 3 | WalletConnect v2(EVM 链)+ Solana Wallet Adapter | P0 |
| 4 | Pre-Execution Simulation(Rabby 模式) | P0 |
| 5 | 多钱包(上限 20 个,可命名 / 切换 / 删除) | P0 |
| 6 | 同链转账 + ENS / SNS 解析 | P0 |
| 7 | 大额二次确认($500 / $1000 / $5000 三档) | P0 |
| 8 | iOS Keychain / Android Keystore 本地加密 | P0 |
| 9 | 后端密文 AES-256-GCM 双重加密 | P0 |
| 10 | 强制备份引导 | P0 |
| 11 | Approve 无限额度警告 + 建议精确额 | P0 |
| 12 | 黑名单地址拦截 | P1 |
| 13 | Agent 活动日志(per-wallet) | P1 |

### 3.2.2 我们不做(Out of Scope)

- 硬件钱包直连(Ledger USB) — WC v2 已能接
- Multi-Sig 钱包 — R49+
- Account Abstraction(ERC-4337) — 标准未稳
- 助记词 iCloud 自动备份 — 监管 / 信任成本 > 收益
- 钱包内 NFT 浏览 — R49+

---

## §3.3 竞品全景对比(7 钱包 × 14 维度)

| 维度 | Phantom | MetaMask | Rabby | Trust | OKX | Backpack | Coinbase Wallet |
|---|---|---|---|---|---|---|---|
| **支持链数** | SOL/ETH/Base/Polygon/SUI(5) | EVM 全(70+) | EVM 全(50+) | 100+ | 90+ | SOL/ETH/Base/Polygon | 多 EVM + SOL |
| **多钱包上限** | ≤100 | 无硬上限 | 无上限 | 无上限 | 无上限 | 多账户 | 50 |
| **创建钱包步骤** | 4 步,~60s | 6 步,~120s | 5 步,~90s | 5 步,~80s | 5 步,~80s | 4 步,~60s | 6 步,~100s |
| **助记词验证** | 12 词,3 词随机回填 | 12 词顺序拖拽 | 12 词,3 词回填 | 12 词顺序点选 | 12 词顺序点选 | 12 词,3 词回填 | 12 词顺序点选 |
| **iCloud 备份选项** | ✓(可选) | ✗ | ✗ | ✓ | ✓ | ✗ | ✓ |
| **WalletConnect** | ✓(v2) | ✓(v2) | ✓(v2) | ✓(v2) | ✓(v2) | ✓(v2) | ✓(v2) |
| **硬件钱包** | Ledger | Ledger/Trezor/Lattice | Ledger/Trezor/OneKey | Ledger | Ledger/Keystone | Ledger | Ledger |
| **Pre-Exec Simulation** | ~(部分,只 SOL 进出) | ~(2024 起 Blockaid) | ✓✓(行业标杆) | ~ | ~ | ~ | ✓(Blockaid) |
| **Approve 无限额警告** | ✓ | ✓ | ✓✓(默认改精确额) | ✓ | ✓ | ~ | ✓ |
| **大额二次确认** | ✗ | ✗ | ✓(自定义阈值) | ✗ | ✓($USDT >1k) | ✗ | ~ |
| **ENS 解析** | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| **SNS 解析(Solana)** | ✓ | ✗ | ✗ | ~ | ✓ | ✓ | ✗ |
| **生物识别** | ✓ | ✓(可选) | ✓ | ✓ | ✓ | ✓ | ✓ |
| **私钥本地存储** | iOS Keychain / Android Keystore | 同 | 同 | 同 | 同 | 同 | 同 |

### 3.3.1 关键发现

1. **多钱包上限"5"过严**:Phantom 100、Coinbase 50。我们 R48 上限 **20**(原 spec 5 改了)
2. **Pre-Exec Simulation Rabby 是断层第一**:唯一对资金进出做"账户级模拟"的钱包
3. **大额二次确认行业普遍缺失** — 这是我们差异化机会
4. **SNS 解析 EVM 钱包普遍不做** — 我们做双解析(SNS + ENS)是差异化点

---

## §3.4 我们的差异化(5 条)

### D-1 | "三档 HITL"在签名层落地(行业首家)

- **<$500**:Agent 全自动,无弹窗
- **$500-$5000**:半自动,Pre-Sim + 10s 倒计时撤销
- **>$5000**:强制 6 位密码 + 生物识别 + 二次预览

### D-2 | Pre-Sim Plus(超 Rabby 一项)

我们叠加**风控引擎结果**:展示"风控评分 / 蜜罐检测 / 流动性深度 / 与黑名单 LP 关联":
```
你将得到:1,520,000 PUMP (≈ $487.21)
你将失去:0.5 SOL (≈ $493.50)
风控评分:62 / 100 (中等)
  ✓ 流动性 $480k(可承受)
  ✗ 创建者持仓 18%(>15% 风险)
  ✓ 非蜜罐
预期滑点:1.32%
Gas 费:$0.00012
```

### D-3 | "撤销 Agent"一键吊销

- 用户可一键"关闭 Agent 自动模式" → 后端密文软删 → 7 天宽限期可恢复 → 30 天硬删

### D-4 | SNS + ENS 双协议解析(同一输入框)

- `vitalik.eth` → 解析 EVM
- `toly.sol` → 解析 SOL
- 多链场景默认 EVM,但提示"此名称在 Solana 链无对应"

### D-5 | 钱包级 Agent 活动日志(可审计)

每个钱包独立 "Agent 活动" tab:7/30 天聚合 PnL、每笔 Tx hash、每笔决策依据,可导出 CSV。

---

## §3.5 创建钱包流程(每步 UI + 时间预算)

### 3.5.1 总览

> 4 步,目标 ≤ 90s 完成。

```
[Step 1: 入口]   →  [Step 2: 助记词展示]  →  [Step 3: 助记词验证]  →  [Step 4: 安全设置]
   ~5s                  ~30s                   ~30s                  ~25s
```

### 3.5.2 Step 1:入口页

| 字段 | 内容 |
|---|---|
| 主标题 | 创建你的钱包 |
| 副标题 | 1 分钟搞定。这个钱包将用于收发币、跑 Agent 自动交易。 |
| 主 CTA | 开始创建 |
| 次 CTA | 我已有钱包(导入) |
| 法律提示 | "创建钱包 = 同意 [服务条款] 和 [隐私政策]" |

### 3.5.3 Step 2:助记词展示

**前置弹窗**:阅读"用纸笔抄下来 / 不要截图 / 我们的客服永远不会向你索要"。

| 字段 | 内容 |
|---|---|
| 主标题 | 你的助记词 |
| 词块 | 4 列 × 3 行,每个词带序号 1-12,等宽字体 |
| 操作 | 复制按钮(灰色,默认禁用 5s 强制阅读)+ 隐藏/显示切换 |
| iCloud | 副 CTA "保存到 iCloud Keychain"(默认不勾选) |
| 主 CTA | 我已抄好,继续(5s 后才可点) |

**反作弊**:
- 截图检测 → 顶部 toast "检测到截图,强烈建议立即重新创建钱包"
- App 切到后台 → 助记词区域立即模糊
- Accessibility 服务屏蔽

### 3.5.4 Step 3:助记词验证

**机制**:从 12 词中**随机抽 3 词**,让用户从 12 个选项里点选正确的(每个位置一组 3 选 1)。

**对比竞品**:Phantom / Rabby 用 3 词回填(我们采用),MetaMask 12 词全顺序拖拽(放弃)。

**为什么 3 词够用**:
- 12 选 3 排列组合 = 220 种,纯猜中概率 0.45%
- 加上 "每位置 3 选 1" 校验 = 1/27 ≈ 3.7%(单次)
- 错 3 次后强制返回 Step 2 重抄 → 实际暴力概率 < 0.01%

### 3.5.5 Step 4:安全设置

**派生路径**:

| 链 | 路径(BIP44) | 备注 |
|---|---|---|
| Solana | `m/44'/501'/0'/0'` | Phantom 兼容 |
| Ethereum | `m/44'/60'/0'/0/0` | MetaMask 兼容 |
| BSC | `m/44'/60'/0'/0/0` | 同 ETH(地址相同) |
| Base | `m/44'/60'/0'/0/0` | 同 ETH |

**UI**:
- 选项 1:开启 Face ID / 指纹解锁(默认 ON)
- 选项 2:设置 6 位 App 密码(大额转账 + 关闭 Agent 时校验)
- 选项 3:我同意将私钥加密上传给 Agent 用于自动交易(默认 ON,可关)

### 3.5.6 时间预算

| 步骤 | 目标 P50 | 目标 P95 |
|---|---|---|
| Step 1 | 5s | 15s |
| Step 2 | 30s | 60s |
| Step 3 | 30s | 60s |
| Step 4 | 25s | 45s |
| **合计** | **90s** | **180s** |

---

## §3.6 导入钱包 — 助记词流程

### 3.6.1 入口
首启 → "我已有钱包" → 助记词 / 私钥 / WalletConnect 三选一

### 3.6.2 输入页关键字段

| 字段 | 内容 |
|---|---|
| 输入区 | 多行 textarea,等宽字体,自动小写 |
| 粘贴检测 | 首次粘贴弹窗:"检测到从剪贴板粘贴。完成后请立即清除剪贴板" |
| 词数自动识别 | 12 / 24 才允许下一步 |
| BIP39 校验 | 失焦时校验每个词;不在则该词标红 |
| Checksum 校验 | 全部词合法时,做 BIP39 checksum 校验 |

### 3.6.3 派生地址确认页

让用户确认"这个钱包是不是我以前的":显示 4 行(链 logo + 地址前 6/后 4 + 余额),如果余额不对可切换派生路径(Standard / Ledger Legacy / Custom)。

### 3.6.4 重复检测 + 错误处理

- 重复 → "此钱包已在你账号里(钱包 #2 - 试验仓)" + [打开钱包 #2]
- 词数不对 → 红字 "请输入 12 或 24 个单词"
- 词不在 BIP39 → 该词标红
- Checksum 失败 → "助记词不正确,请检查最后一个词或重新输入"

### 3.6.5 后端同步

```
本地(必做):
  SecureEnclave (iOS) / StrongBox (Android) → 存加密私钥 + 助记词

后端(可选,用户勾"启用 Agent 自动交易"才上传):
  POST /api/wallets/import
    body: { encrypted_seed (AES-256-GCM, PBKDF2 派生 key) }
    服务端再用 server_key 加一层 (HSM 或 KMS)
```

---

## §3.7 导入钱包 — 私钥流程

### 3.7.1 与助记词的差异

| 维度 | 助记词 | 私钥 |
|---|---|---|
| 多链派生 | ✓(同一组生 4 链) | ✗(单链单地址) |
| 用户群 | 主流 | 进阶(从交易所导出 / 老钱包) |
| 默认入口 | ✓(首选) | 隐藏在二级菜单 |

### 3.7.2 输入校验

| 步骤 | 校验内容 |
|---|---|
| 1 | 长度 + base58 / hex 格式 |
| 2 | 用私钥派生公钥 / 地址 |
| 3 | 与已导入钱包查重 |

**链识别**:Solana(base58, 64 字节) / EVM(0x 开头 64 hex)。

### 3.7.3 用户教育

私钥导入页底部固定文字(灰色小字):

> 私钥只能控制单条链上的单个地址。如果你的资产分布在多个链,建议关闭此页 → 用助记词导入。

---

## §3.8 WalletConnect 集成(含半自动 Agent 模式)

### 3.8.1 为什么要做 WC

> 用户场景:有人钱包里有 50 万 U,信不过 App 把私钥上传。但又想用 Agent 选币能力。
> 解法:WC 接入 → Agent 给"建议" → 用户手动签名。

### 3.8.2 支持范围

| 协议版本 | WalletConnect v2 |
|---|---|
| EVM 链 | Ethereum / BSC / Base / Polygon / Arbitrum |
| Solana | Solana Wallet Adapter(走 deeplink,Phantom / Backpack / Solflare) |

**不支持**:WC v1(已废弃)/ Cosmos / Sui

### 3.8.3 模式选择(关键差异化)

```
[ 全自动 ] (灰色,disabled — 外部钱包不支持全自动签名)
[ 半自动:AI 建议,你来签名 ] ✓ (默认)
[ 仅查看 ] (不参与交易,只展示余额和 Agent 分析)
```

### 3.8.4 半自动模式的 UX

```
1. 用户手机弹通知:"Agent 推荐买入 PUMP (评分 78/100)"
   ↓
2. 用户点 → 进入决策详情页:
   - Pre-Sim 完整结果
   - 预计盈亏区间
   - [ 同意 → 通过 WC 签名 ]  [ 拒绝 ]
   ↓
3. 同意 → App 调用 WC eth_sendTransaction
   ↓
4. 用户钱包(Phantom / Rabby 等)弹自己的签名页
   ↓
5. 签名成功 → 回到 Agent App,显示"已发送,Tx: 0xabc..."
```

### 3.8.5 与"全自动"的明显区分

UI 上多重提示:
- 钱包列表:半自动钱包标 "WC" 蓝色 chip
- 钱包详情顶部 banner:"此钱包为 WC 半自动模式,每笔需手动签名"
- Agent 启动开关:"Agent 推荐 → 你签名"(不是 "Agent 自动交易")
- 通知文案:"Agent 推荐..."(不是 "Agent 已下单...")

### 3.8.6 半自动的限制

- **不参与 SL / TP 自动平仓**(需要随时签名,不现实)
- **无 R47 P6 倒计时撤销**
- **大额阈值不生效**(签名权在用户钱包)

---

## §3.9 多钱包管理

### 3.9.1 上限决策(从 5 调到 20)

| 竞品 | 上限 |
|---|---|
| Phantom | 100 |
| MetaMask | 无硬上限 |
| Rabby | 无硬上限 |
| Coinbase Wallet | 50 |

**决策**:
- R48 上限 **20**(原 spec 5 太严,影响 Pro 用户)
- 软提示在第 10 个时:"你已创建 10 个钱包,管理较多?可考虑用单钱包多策略"
- 硬上限 20 时阻挡:"达到 20 个上限,请先删除不用的钱包"

### 3.9.2 钱包列表 UI

```
我的钱包                          [+ 新建]

⭐ 主仓
   $12,450.00  · 4 链  · Agent ON
───────────────
⚪ 试验仓
   $480.00  · Solana  · Agent ON · 高频策略
───────────────
🔵 老婆账户
   $5,200.00  · ETH  · Agent OFF
───────────────
🟢 Ledger 主仓 (WC)
   $48,200.00  · Agent 半自动
```

**操作**:长按 / 右滑 → 删除 / 改名 / 排序 / 设为默认

### 3.9.3 创建 / 命名 / 删除规则

| 操作 | 限制 |
|---|---|
| 创建 | 每分钟最多 3 个(防脚本滥用) |
| 命名 | 1-16 字符,可中英文 emoji,**禁止地址 / 助记词等敏感词** |
| 删除 | 必须先 ① 关 Agent ② 余额 < $10 ③ 6 位密码 |
| 排序 | 拖拽 |

### 3.9.4 资金不自动跨钱包(防误操作)

- Agent 自动交易**只能动绑定钱包**(后端校验:`event.user_id + event.wallet_id` 必须是同一对)
- 跨钱包转账走"普通转账"流程
- **没有"一键平移所有钱包到主仓"按钮**(诱导误操作)

---

## §3.10 转账 — 同链

### 3.10.1 输入页字段顺序

| # | 字段 | 说明 |
|---|---|---|
| 1 | 选择 Token | 默认 USDC |
| 2 | 接收地址 | 长输入框,支持 ENS / SNS / 0x... / Base58 |
| 3 | 金额 | 数字键盘,旁边 [Max] 按钮 |
| 4 | Memo(可选,Solana / Cosmos) | 单行,≤ 64 字 |

### 3.10.2 确认页字段(★ 重要)

> **设计原则**:把"会出错的字段"放最显眼,把"不会出错的字段"放下面。

```
确认转账

收款地址
  ┌──────────────────────────┐
  │ 9WzD...AWWM              │  ← 32px 大字号,等宽
  │ (vitalik.sol)            │  ← ENS/SNS 反向解析
  └──────────────────────────┘

金额        500.00 USDC ≈ $500.00
网络        Solana
网络费      ~$0.00012
到账估时    ~3 秒

[ 取消 ]              [ 确认发送 ]
```

### 3.10.3 黑名单地址拦截

- **静态名单**:Sanctions list(OFAC SDN 同步)+ 已知钓鱼合约
- **行为名单**:近 7 天有用户举报为诈骗的地址(R49 才上)
- 命中:**硬拦**,弹窗 "此地址在黑名单中(原因:OFAC 制裁),无法发送"

### 3.10.4 异常场景

| 场景 | 处理 |
|---|---|
| 余额不足 | "余额不够,你只有 X USDC" + [发送全部] |
| Gas 不足(EVM) | "ETH 不够支付 Gas,请先充 ETH" + [跨链桥充 ETH] |
| 网络拥堵 | "当前网络繁忙,预计 X 分钟" + [继续 / 取消] |
| 收款地址未激活(SOL) | "对方账户未激活,本次转账将额外消耗 0.002 SOL" |

---

## §3.11 转账 — 跨链(衔接 §4 跨链桥)

> 本节只描述钱包模块的"用户感知层"。具体跨链路径选择 / 桥安全评估 / 路由算法在 §4。

### 3.11.1 确认页(与同链的差异)

```
确认跨链转账

从     Solana    9WzD...AWWM
到     Base      0xC862...8582

你将发送   500.00 USDC
你将到账   ~498.50 USDC  (估)
桥费用     ~$1.50
预计耗时   3-7 分钟

桥服务商   LiFi (top route)
[ 查看其他路径 ]

⚠️ 跨链不可逆,请确认收款地址正确
```

### 3.11.2 与同链的关键差异

| 维度 | 同链 | 跨链 |
|---|---|---|
| 到账时间 | < 1 分钟 | 3-30 分钟 |
| 费用 | < $0.01(SOL)/ ~$0.5(EVM) | $1-$5 |
| 可逆 | 链上不可逆,但可重试 | 跨链桥失败可能卡资金,**强警告** |
| 拦截阈值 | $1000 | **$500**(更严) |

---

## §3.12 转账 — ENS / SNS 解析

### 3.12.1 解析能力矩阵

| 输入示例 | 链识别 | 解析结果 |
|---|---|---|
| `vitalik.eth` | EVM | 0xd8dA6...6045(ENS Public Resolver) |
| `toly.sol` | Solana | F1Yvg...Hp9d(SNS) |
| `贝壳.eth` | EVM | UTS-46 Unicode 兼容 |
| `wenrui.eth` | EVM(SNS 无对应) | 0x...,提示 "此名称无 Solana 关联" |
| `vitalik` | 模糊 | 提示 "请输入完整域名(如 vitalik.eth)" |

### 3.12.2 解析时机

- 用户输入框失焦后 300ms debounce
- 解析进行中:输入框右侧 spinner
- 解析成功:输入框下方绿色小字显示解析后的地址前 6 / 后 4
- 解析失败:红色 "无法解析,请检查域名"

### 3.12.3 反向解析(地址 → 名称)

- 用户输入完整地址 → App 后台查 ENS / SNS 反向记录
- 如有 → 确认页地址下方显示 `(vitalik.sol)` 灰色小字

### 3.12.4 安全:同形字攻击防护

> ENS 同形字攻击:`vitalik.eth` vs `vitаlik.eth`(第 4 位是 Cyrillic а)

- 前端用 ICU UTS-46 正规化
- 解析后**显示 Punycode 形式**作为补充:`vitаlik.eth` → `xn--vitlik-3vd.eth`
- 检测到 Mixed-Script(混合字符集) → 红色警告

### 3.12.5 性能 SLA

- 解析 P95 延迟 < 800ms(用 Cloudflare ENS Gateway / Bonfida SNS RPC)
- 缓存 24 小时(地址 → 名称双向)

---

## §3.13 大额二次确认(精确阈值 + UI)

### 3.13.1 三档阈值决策

| 档位 | 阈值 | 触发额 | UI |
|---|---|---|---|
| 0 | < $500 | 全自动 / 普通确认 | 单步确认页 |
| 1 | $500-$1000 | 中等 | 二次预览(地址放大 + 金额放大) |
| 2 | $1000-$5000 | 大额 | + 6 位 App 密码 |
| 3 | > $5000 | 超大额 | + 6 位密码 + 生物识别 + 二次预览 |

### 3.13.2 阈值依据

**$1000 的依据**:
- 用户调研(20 人):中位数答案 "$500-$1500"
- 竞品参考:OKX 默认 $1000、Rabby 用户最常配置 $1000-$2000
- A/B 测试计划:R48 上线后跑 30 天

**$5000 的依据**:
- R47 P6 已确定的"半自动 → 强制人工"分界点

### 3.13.3 UI 示例 — $5000+ 超大额

```
⚠️ 超大额转账

你正在转账 $7,500.00

收款地址  9WzD...AWWM
(vitalik.sol)

请输入 6 位 App 密码
○ ○ ○ ○ ○ ○

验证后还需 Face ID 确认

[ 取消 ]
```

### 3.13.4 用户自定义阈值

- 设置 → 安全 → "大额提醒阈值"
- 默认 $1000,可调到 $100 / $500 / $1000 / $5000 / 自定义
- 不能调到 0(避免每笔都拦)
- 不能调到 > $10,000(避免大户漏拦)

---

## §3.14 签名交互 — Pre-Execution Simulation(Rabby 模式)

### 3.14.1 实现路径

```
[用户/Agent 触发交易]
  ↓
[构造 unsigned tx]
  ↓
[发到本地 Sim 服务] → 调外部 RPC 的 eth_call / simulate-bundle
  ↓
[解析结果]
  ├─ 资产变化(asset diff): pre-balance vs post-balance per token
  ├─ 接触合约列表
  ├─ 风控引擎评分(我们 §6 自有)
  └─ 风险标记(approve / 蜜罐 / 黑名单 LP)
  ↓
[渲染 UI]
  ↓
[用户决定 → 真签名 → 广播]
```

### 3.14.2 EVM 链 Sim 实现细节

- **首选**:Tenderly Simulator API(免费 100 calls/day,付费无限)
- **备选**:Alchemy `alchemy_simulateAssetChanges` / Blockaid 自建
- **回退**:本地 ganache-fork(慢 + 不稳)

### 3.14.3 Solana 链 Sim 实现细节

- 用 Solana RPC `simulateTransaction` 拿 logs + accounts diff
- 解析 SPL token balance 变化
- 接 Birdeye / Jupiter Quote API 拿价格估值

### 3.14.4 标准 UI(覆盖 EVM swap 场景)

```
交易预览

操作  Swap on Jupiter

你将得到
  + 1,520,000 PUMP
    ≈ $487.21              ← 绿色

你将失去
  - 0.5 SOL
    ≈ $493.50              ← 红色

─── 风控评估(我们独家)───

评分  62 / 100  (中等)
✓ 流动性 $480k(可承受)
✗ 创建者持仓 18%(>15% 风险)
✓ 非蜜罐
✓ LP 已锁

─── 执行参数 ───

预期滑点  1.32%
Gas 费    $0.00012
有效期    3 秒(将作废)

合约   Jupiter v6 Aggregator
[✓ 已认证]

[ 取消 ]              [ 确认签名 ]
```

### 3.14.5 Approve 场景特殊处理

```
⚠️ Approve 检测

合约请求授权花费你的 USDC

合约     Jupiter v6 Aggregator
[✓ 已认证]

授权额度
  ┌────────────────────────┐
  │ ⚠️ 无限额度             │  ← 红色
  │  (115792089237...)     │
  │                         │
  │ 推荐改为本次需要额度:   │
  │   100.00 USDC           │
  │ [ 改为推荐额度 ]         │
  └────────────────────────┘

[ 取消 ]      [ 用无限额度签名 ]
```

- **默认按钮文字**:**"用无限额度签名"**(明示风险,降低误点)
- 旁边一直有"改为推荐额度"按钮

### 3.14.6 钓鱼合约签名拦截

- 检查合约地址是否在 ScamSniffer / Blockaid 黑名单
- 命中 → **硬拦**:"⚠️ 此合约被识别为高风险,无法签名" + [我了解风险,继续](隐藏在二级菜单,7s 倒计时才可点)

---

## §3.15 签名交互 — Agent 自动签名 vs WalletConnect

### 3.15.1 三种签名通道对比

| 通道 | 用户感知 | 安全性 | 速度 |
|---|---|---|---|
| **Agent 自动签名**(后端密文) | 无弹窗(<$500)/ 10s 倒计时($500-$5000) | 中 | 极快(<2s) |
| **WalletConnect 半自动** | 推送通知 → 用户外部钱包确认 | 高 | 慢(5-30s) |
| **手动转账** | 用户主动操作完整流程 | 高 | 慢 |

### 3.15.2 Agent 自动签名的安全护栏

| 护栏 | 实现 |
|---|---|
| 单笔上限 | strategy.max_position_usd ≤ user_settings.hitl_threshold($5000 默认) |
| 日累计上限 | 后端 daily_volume_check |
| 异常时间窗 | 用户当地时间 02:00-06:00 默认不下单(可关) |
| Killswitch | R47 P4 ADMIN_TOKEN 一键全停 |
| 单笔 Pre-Sim | 即使全自动也跑 Sim,失败拒绝 |
| 风控评分 | < 50 不下单 |

### 3.15.3 用户在 UI 上的"同意全自动"流程

```
⚠️ 启用 Agent 自动交易,你需要知道:

· 我们将用你的私钥代你下单
  (后端 AES-256 加密 + KMS 双层保护)

· 单笔上限 $5,000(可在策略里调小)

· 你可以随时关闭 → 后端密文 7 天内可恢复 → 30 天后硬删

· 我们救不了被黑事故(链上不可逆)

[ 我了解,启用 ]  [ 取消 ]
```

强制 5s 阅读时间。

---

## §3.16 备份 + 安全 + 用户教育

### 3.16.1 强制备份触发时机

| 场景 | 触发 | 强度 |
|---|---|---|
| 创建钱包后 | 立刻 | 不可跳过 |
| 主页常驻 | 创建后未确认 "已备份" | 顶部 banner 黄色 |
| 入金 ≥ $50 | 第一次充值到账 | 弹窗强提醒 |
| 大额转账前 | 转账 ≥ $1000 且未确认 "已备份" | 拦截 |
| 启用 Agent 前 | 同上 | 拦截 |

### 3.16.2 生物识别 + App 密码触发场景

| 场景 | 生物识别 | App 密码 |
|---|---|---|
| App 启动 | ✓ | ✗ |
| 切换钱包 | ✗ | ✗ |
| 转账 < $500 | ✗ | ✗ |
| 转账 $500-$1000 | ✓ | ✗ |
| 转账 $1000-$5000 | ✗ | ✓ |
| 转账 > $5000 | ✓ | ✓ |
| 修改安全设置 | ✗ | ✓ |
| 查看助记词 | ✓ | ✓ |
| 删除钱包 | ✓ | ✓ |
| 关闭 Agent 自动 | ✗ | ✓ |
| 导出私钥 | ✓ | ✓(+ 二次确认 30s 倒计时) |

### 3.16.3 私钥本地加密(平台差异)

| 平台 | 存储 | 加密方式 |
|---|---|---|
| iOS | Keychain Services + Secure Enclave | AES-256-GCM,key 由 Secure Enclave 派生,生物识别绑定 |
| Android | Keystore + StrongBox / TEE | AES-256-GCM,Hardware-backed key |
| Android(无 StrongBox) | Keystore + Software-backed | 弱化但仍 KeyStore 隔离 |

**永远不写入**:普通 SharedPreferences、文件系统、React Native AsyncStorage(明文)、Flutter SharedPreferences(明文)。

### 3.16.4 后端密文双重加密

```
[ 用户私钥 (32 bytes) ]
        ↓
[ AES-256-GCM, key=PBKDF2(用户密码, salt) ]   ← 第一层,用户控制
        ↓
[ AES-256-GCM, key=KMS_master_key ]           ← 第二层,服务器控制
        ↓
[ user_wallets 表存储 ]
```

**第一层**用户密码 → 即使数据库泄露,没用户密码也解不开
**第二层**KMS → 即使有用户密码,没服务器 KMS 也解不开
**双层任一失守都不致命**

---

## §3.17 钱包丢失救助(我们做不到什么)

### 3.17.1 明确做不到的清单

| 用户场景 | 我们能做 | 我们做不到 |
|---|---|---|
| 忘记 6 位 App 密码 | 用助记词重新导入 + 重设密码 | 直接重置密码进入旧钱包 |
| 丢手机 + 有助记词 | 用助记词在新机导入 | (无需做不到) |
| 丢手机 + 无助记词 | 钱包永久丢失 | 找回私钥 / 助记词 |
| 助记词被偷 + 钱被转走 | 教用户立即把剩余资金转新钱包 | 追回链上资金 |
| 误转钱到错地址 | 教用户尝试联系收款方(无法保证) | 撤回链上交易 |
| 黑客通过 Approve 套走资金 | 教用户撤销所有 Approve | 追回 |

### 3.17.2 救助页 UI

```
钱包找回

你的钱包就像现金钱包,我们不托管

你有以下情况吗?

◆ 我有助记词,想恢复
  → [ 用助记词导入 ]

◆ 我忘记 App 密码
  → [ 用助记词重置 ]

◆ 我没有助记词
  → 抱歉,我们无法找回。
    [ 了解为什么 ]

◆ 我被黑了
  → [ 紧急止损教学 ]
```

### 3.17.3 不诱导虚假希望

- 永远不说 "我们尝试帮你找回"
- 永远不说 "100% 安全"
- 永远不收任何 "找回手续费"

---

## §3.18 验收标准

### 3.18.1 功能验收(20 项)

| # | 验收项 | 通过条件 |
|---|---|---|
| 1 | 创建钱包 P50 | ≤ 90s |
| 2 | 创建钱包 P95 | ≤ 180s |
| 3 | 助记词验证错误 3 次 | 强制返回 Step 2 + 重新生成 |
| 4 | 派生 4 链地址 | 同一助记词派生 SOL/ETH/BSC/Base 地址,与 Phantom / MetaMask 派生结果完全一致 |
| 5 | 助记词导入 | 12 词 / 24 词都支持,checksum 错的词标红 |
| 6 | 私钥导入 | base58 / 0x hex 自动识别 |
| 7 | WC v2 接入 | EVM 5 链 + Solana 主流钱包 |
| 8 | 多钱包上限 | 20 个,达到上限阻挡 |
| 9 | 转账 ENS 解析 | `vitalik.eth` 解析正确 |
| 10 | 转账 SNS 解析 | `toly.sol` 解析正确 |
| 11 | 大额二次确认 | $1000 触发密码,$5000 触发密码 + 生物 |
| 12 | Pre-Sim EVM | swap 场景显示 "得到 X / 失去 Y / 滑点" |
| 13 | Pre-Sim Solana | 同上 |
| 14 | Approve 默认警告 | 无限额度红字 + "改精确额"按钮 |
| 15 | 黑名单地址 | OFAC SDN 同步,命中硬拦 |
| 16 | 强制备份 | 创建后立刻 + 入金 $50 + 大额前拦 |
| 17 | 私钥本地加密 | iOS Keychain + Secure Enclave / Android Keystore |
| 18 | 后端密文双层 | PBKDF2 用户密码 + KMS server key |
| 19 | Agent 撤销 | 关闭 → 7 天可恢复 → 30 天硬删 |
| 20 | 钱包丢失教育 | 救助页 + CS 话术上线 |

### 3.18.2 性能验收

| 指标 | P50 | P95 |
|---|---|---|
| 钱包列表加载 | < 500ms | < 1500ms |
| 余额刷新 | < 1s | < 3s |
| ENS / SNS 解析 | < 500ms | < 800ms |
| Pre-Sim EVM | < 2s | < 5s |
| Pre-Sim Solana | < 1.5s | < 4s |
| 转账签名 | < 1s(本地) | < 2s |
| WC 连接握手 | < 3s | < 8s |

### 3.18.3 UX 验收(用户测试)

招 10 个完全没用过加密的用户,完成以下任务:

| 任务 | 通过率目标 |
|---|---|
| 创建钱包并备份 | 100% |
| 收到测试 USDC | 100% |
| 转出 $10 USDC | ≥ 90% |
| 用 ENS 转账 | ≥ 80% |
| 看懂 Pre-Sim | ≥ 70% |
| 启用 Agent | ≥ 90% |

---

## §3.19 监控埋点

### 3.19.1 业务事件(主要)

`wallet_create_*` / `wallet_import_*` / `wallet_wc_connect` / `wallet_switch` / `wallet_delete` / `transfer_*` / `presim_*` / `backup_confirm` / `agent_enable/disable` / `recovery_help_view`

### 3.19.2 安全告警

| 告警名 | 触发 | 处理 |
|---|---|---|
| `mnemonic_screenshot_detected` | 用户在 Step 2 截图 | 上报 + 提醒用户 |
| `wallet_deletion_no_backup` | 用户删除未备份钱包 | 红色二次确认 |
| `mass_creation_detected` | 1 分钟创建 ≥ 3 个 | 临时拒绝 + 风控审查 |
| `ofac_address_attempt` | 用户尝试转给 OFAC 地址 | 硬拦 + 上报合规 |
| `homograph_address_attempt` | 同形字 ENS 尝试 | 强警告 + 二次确认 |
| `presim_high_risk_proceeded` | 风控评分 < 30 仍签名 | 上报(用户已知风险) |

### 3.19.3 周报指标(给 PM)

| 指标 | 目标 |
|---|---|
| 钱包创建成功率 | ≥ 95% |
| 创建中途流失率 | ≤ 10% |
| 创建 P50 耗时 | ≤ 90s |
| 助记词验证一次过率 | ≥ 80% |
| 备份确认率(创建后 7 日) | ≥ 70% |
| Agent 启用率(创建后 7 日) | ≥ 50% |
| 转账失败率 | ≤ 3% |
| Pre-Sim 显示率(签名场景) | 100% |
| WC 连接成功率 | ≥ 90% |

### 3.19.4 用户旅程漏斗

```
启动 App → 进入创建 → 看完助记词 → 通过验证 → 完成创建 → 首笔入金 → 启用 Agent → 首笔交易
  95%       92%        85%          95%        70%         60%         80%
```
# §4 跨链资金流转 — 详细规格(R48)

> 用户视角"我有 USDC,我要买另一条链的 X 币" — 中间过桥过程对用户透明,产品自己选最优桥。

---

## §4.0 模块定位

| 维度 | 说明 |
|------|------|
| **模块名** | Cross-Chain Fund Routing(CFR) |
| **上游** | Agent Intent Parser、Wallet Manager、Risk Engine |
| **下游** | DEX Router、Trade Executor、Notification |
| **核心承诺** | (1) 资金不蒸发 (2) 跨链报价聚合 (3) 全程可追溯 |
| **SLO** | P50 < 5 min(L2 ↔ L2)/ P50 < 8 min(Solana ↔ EVM);P95 < 25 min;失败率 < 0.5%(完全丢失 = 0%) |

---

## §4.1 用户故事(8 个)

**US-CFR-01 跨链买币(主路径)**:Solana 钱包 200 USDC,chat "买 1000 美元 ETH 上的 PEPE"。产品自动:Solana USDC → 跨链 → Ethereum USDC → Uniswap swap PEPE。

**US-CFR-02 报价透明**:Pro 模式秒回:"deBridge 199.85 USDC 到账 / Wormhole 199.21 USDC,deBridge 快 2 分钟 + 便宜 0.32%"

**US-CFR-03 失败兜底**:桥被黑(极端场景)→ 红色 banner:"您 200 USDC 因 XXX 桥事故被锁定,已切换备桥重试,12 min 内恢复;若桥方破产我方 $10M 保险垫付。"

**US-CFR-04 主动止损跨链**:Solana 仓位需要紧急止损,但流动性最深的市场在 Base。产品 30 秒内完成跨链 + swap

**US-CFR-05 桥健康度警告**:用户主动选小众桥 → 弹"该桥健康度评分 38/100,建议改用 Across(评分 92)"

**US-CFR-06 部分到账**:1000 USDC 跨链,因 LP 紧张目标链只到账 990。状态机准确显示"已到账 990 / 应到 990",**不会让用户误以为丢了 10**

**US-CFR-07 跟单跨链**:Agent 在预授权额度内自动跨链 + 跟单,合并为一条最终通知

**US-CFR-08 老资产解套**:BSC 上小币,流动性差。Agent 建议"先在 BSC swap 成 USDT → 跨链到 Base → 在 Base 卖出"

---

## §4.2 产品边界

**做**:USDC / USDT / ETH / SOL / WBTC 5 个**主流可桥资产**。8 条主链:Solana / Ethereum / Base / Arbitrum / Optimism / Polygon / BSC / Avalanche。桥聚合(自研报价层 + 接入 LiFi/Socket SDK 双源对账)。失败回滚 + 中间稳定币兜底。

**不做(R48 范围外)**:Cosmos / IBC / Bitcoin 主网跨链 / NFT 跨链 / 用户自托管以外的"产品中心化中转账户"

---

## §4.3 竞品全景对比表(9 桥 × 12 维度)

| 维度 | Wormhole | deBridge | Across | Axelar | Stargate | Hop | LiFi(聚合) | Socket(聚合) | Squid |
|---|---|---|---|---|---|---|---|---|---|
| **支持链数** | 30+ | 22+ | 12 EVM | 60+(GMP) | 14 | 8 Roll-up | 30+ | 25+ | 50+ |
| **是否含 Solana** | ✓(原生) | ✓ | ✗ | ✓(GMP) | ✗ | ✗ | ✓(经 Wormhole/deBridge) | ✓ | ✓ |
| **跨链时延 P50** | 5-15 min(Guardian 13 签) | 30s-3 min(快) | 30s-2 min(最快) | 5-15 min | 1-3 min | 1-5 min | 取决于路由 | 取决于路由 | 5-10 min |
| **协议费率** | 0%(只 Gas) | 0.04% + Gas | 0.04-0.12%(Filler 报价) | 动态(Gas 中转) | 0.06% LP fee | 0.04% bonder | 聚合器 0% | 聚合器 0% | 含 0.05% Squid fee |
| **流动性模型** | Lock-and-mint(canonical) | Solver 网络(Filler 抢单) | Filler 优化(UMA 验证) | Validator + GMP | LP 池(共享流动性) | Bonder 担保 | N/A | N/A | N/A |
| **TVL 量级** | $1.8B | $400M | $250M | $750M | $300M | $80M | N/A(零自有 TVL) | N/A | N/A |
| **安全模型** | 19 Guardians 13/19 多签 | Solver 抢单 + Chainlink 价格 | UMA Optimistic + Filler 押金 | 75+ Validator PoS | LayerZero Oracle+Relayer | zk + 信任 Bonder | N/A | N/A | 复用 Axelar |
| **历史攻击** | **2022-02 损失 $325M(Solana 签名漏洞)** | 无 | 无重大 | 无重大 | 无(LayerZero 系) | 无 | N/A | N/A | 无 |
| **失败回滚** | 部分支持(7-15 min 内可救) | 自动退原链(Solver 超时) | Filler 30s 超时退原链 | 慢(30+ min) | 同步 stuck(罕见) | 慢(Bonder 不接) | 取决于底层桥 | 取决于底层桥 | 取决于 Axelar |
| **API/SDK 难度** | 中(Sequence 监听复杂) | 低(REST + 状态查询) | 低(SpokePool 标准) | 中(GMP 较重) | 中 | 低 | **极低**(一个 SDK 全搞定) | 极低 | 低 |
| **已知问题** | Solana 重组导致延迟;签名集合升级慢 | 极罕见 RPC 卡顿 | 流动性紧张时拒单 | Validator 集中度 | LP 失衡时滑点高 | Roll-up 退出 7 天 | 报价不一致 | 报价不一致 | 受 Axelar 拖累 |
| **是否支持原生 ETH** | ✓ | ✓ | ✓ | wrap | wrap | ✓ | ✓ | ✓ | ✓ |

**结论**:没有任何一座桥能覆盖所有"源 → 目标"最优组合。必须**双层架构**:聚合器(LiFi)兜底广覆盖 + 自研报价对核心路径热点。Wormhole 是行业标准但有 $325M 历史,需特别关注。

---

## §4.4 我们的差异化

| 别人 | 我们 |
|---|---|
| LiFi 给一个最优解,用户黑盒接受 | **永远展示 Top 3 报价对比**,用户随时可查 |
| 失败后自己救援(用户多数不知) | **进度状态机透明**,失败必须明示 + 给方案 + 给文案 |
| 桥健康度靠"经验"选 | **0-100 量化评分公式**,可解释、可审计、可对外公示 |
| 桥被黑后用户客服半小时不回复 | **资金不蒸发承诺 + 自购 $10M 桥事故保险**(R49 谈) |
| 跨链 + Swap 两步要用户操作 | **一站式 Agent 内部解决** |
| 跟单跨链需要用户手动转账 | **预授权额度内 Agent 自动跨链** |

---

## §4.5 桥选型矩阵 — 完整二维矩阵

> 列:目标链;行:源链。每格按 **主桥 / 备桥 / 紧急桥** 三档。命名规则:`Bridge(预计时延 P50)`。

### §4.5.1 EVM ↔ EVM 矩阵(8 条 EVM 链)

| 源 \ 目标 | Ethereum | Base | Arbitrum | Optimism | Polygon | BSC | Avalanche |
|---|---|---|---|---|---|---|---|
| **Ethereum** | — | Across(2m) / Stargate(3m) / Hop | Across(2m) / Hop / Stargate | Across(2m) / Hop / Stargate | Stargate(3m) / Across / Polygon Bridge | Stargate(3m) / deBridge / cBridge | Stargate(3m) / deBridge / Axelar |
| **Base** | Across(2m) / deBridge / Stargate | — | Across(2m) / deBridge / Stargate | Across(2m) / Stargate / deBridge | deBridge(3m) / Stargate / Axelar | deBridge(3m) / Stargate / Axelar | deBridge(5m) / Stargate / Axelar |
| **Arbitrum** | Across(2m) / Hop / Stargate | Across(2m) / deBridge / Stargate | — | Across(2m) / Hop / Stargate | Stargate(3m) / Across / deBridge | Stargate(3m) / deBridge / cBridge | Stargate(3m) / deBridge / Axelar |
| **Optimism** | Across(2m) / Hop / Stargate | Across(2m) / Hop / Stargate | Across(2m) / Hop / Stargate | — | Stargate(3m) / Across / deBridge | Stargate(3m) / deBridge / cBridge | Stargate(3m) / deBridge / Axelar |
| **Polygon** | Stargate(3m) / Across / Polygon PoS | Stargate(3m) / deBridge / Across | Stargate(3m) / Across / deBridge | Stargate(3m) / Across / deBridge | — | Stargate(3m) / deBridge / cBridge | Stargate(3m) / deBridge / Axelar |
| **BSC** | Stargate(3m) / deBridge / cBridge | Stargate(3m) / deBridge / Axelar | Stargate(3m) / deBridge / cBridge | Stargate(3m) / deBridge / cBridge | Stargate(3m) / deBridge / cBridge | — | Stargate(3m) / deBridge / Axelar |
| **Avalanche** | Stargate(3m) / deBridge / Axelar | Stargate(3m) / deBridge / Axelar | Stargate(3m) / deBridge / Axelar | Stargate(3m) / deBridge / Axelar | Stargate(3m) / deBridge / Axelar | Stargate(3m) / deBridge / Axelar | — |

### §4.5.2 Solana ↔ EVM 矩阵

| 方向 | 主桥 | 备桥 | 紧急桥 |
|---|---|---|---|
| Solana → Ethereum | deBridge / DLN(2m) | Wormhole + Mayan(8m) | Allbridge(15m) |
| Solana → Base | deBridge / DLN(2m) | Wormhole + Mayan(8m) | Allbridge(15m) |
| Solana → Arbitrum | deBridge / DLN(3m) | Wormhole + Mayan(8m) | Allbridge(15m) |
| Solana → Optimism | deBridge / DLN(3m) | Wormhole + Mayan(8m) | Allbridge(15m) |
| Solana → Polygon | deBridge / DLN(3m) | Wormhole(8m) | Allbridge(15m) |
| Solana → BSC | deBridge / DLN(3m) | Wormhole(10m) | Allbridge(20m) |
| Solana → Avalanche | deBridge / DLN(3m) | Wormhole(10m) | Allbridge(20m) |
| Ethereum → Solana | deBridge(3m) | Wormhole + Mayan(10m) | Allbridge(15m) |
| Base → Solana | deBridge(3m) | Wormhole + Mayan(10m) | Allbridge(15m) |
| Arbitrum → Solana | deBridge(3m) | Wormhole(10m) | Allbridge(15m) |
| Optimism → Solana | deBridge(3m) | Wormhole(10m) | Allbridge(15m) |
| Polygon → Solana | deBridge(3m) | Wormhole(10m) | Allbridge(15m) |
| BSC → Solana | deBridge(5m) | Wormhole(12m) | Allbridge(20m) |
| Avalanche → Solana | deBridge(5m) | Wormhole(12m) | Allbridge(20m) |

### §4.5.3 选型逻辑

| 选型考量 | 解释 |
|---|---|
| **EVM 短链路 = Across 优先** | Filler 网络给最快报价,P50 30s-2m,L2 ↔ L2 行业最快 |
| **EVM 长链路 / 含 BSC/Avalanche = Stargate 优先** | Stargate LP 模型链覆盖广,BSC/Avax 流动性深 |
| **任何含 Solana = deBridge 优先** | DLN solver 网络对 Solana 路径报价最优,2-3 min |
| **Wormhole 永远不做主桥** | $325M 历史 + Guardian 集中度 + 时延较慢,只做 Solana 系备桥 |
| **deBridge 不做长 EVM 链路主桥** | EVM ↔ EVM 路径 Across 更快更便宜 |
| **紧急桥都给"慢但能到"的选项** | Allbridge / Axelar / cBridge 时延高但生态老,主备双断时不会让用户彻底卡死 |

### §4.5.4 矩阵动态调整规则

主桥不是写死的,**每 6 小时根据健康度评分重排**:
1. 健康度评分 < 60 自动降级为备桥
2. 健康度评分 < 40 自动剔除出矩阵
3. 24h 内有重大事故的桥强制 7 天黑名单
4. 日费用倒数前 20% + 时延前 20% 综合得分上调一档

---

## §4.6 桥健康度评分公式(0-100)

> 这是**用户原话 Open Question**的精确化结果。所有桥每 5 min 全量重算评分。

### §4.6.1 5 个维度 + 权重

| 维度 | 权重 | 子项 | 数据源 |
|---|---|---|---|
| **A 安全历史** | 30% | A1 是否被黑过(80) + A2 修复透明度(20) | Rekt News API + Chainalysis |
| **B 当前流动性** | 25% | B1 当前 TVL 绝对值(40) + B2 vs 30 天均值波动(30) + B3 链上深度查询(30) | DefiLlama API + 直接查 LP 合约 |
| **C 24h 性能** | 25% | C1 跨链成功率(50) + C2 平均时延 vs SLO(30) + C3 极端时延 P99(20) | 自家埋点 + 桥官方状态页 |
| **D 治理风险** | 12% | D1 多签门槛(40) + D2 是否升级冻结(30) + D3 是否社区可监督(30) | 桥官方文档 + 链上多签合约 |
| **E 流动性深度** | 8% | E1 单笔 $100k 滑点 + E2 单笔 $1M 滑点 | 实时 quote 模拟 |

总分 = 0.30 × A + 0.25 × B + 0.25 × C + 0.12 × D + 0.08 × E

### §4.6.2 子项打分细则

**A1 是否被黑过**(满分 80,以下扣分):
- 历史 1 次重大事故(损失 > $50M):**-50**
- 历史 1 次中等事故(损失 $5M - $50M):**-25**
- 历史多次小事故(< $5M)累计 ≥ 3 次:**-15**
- 修复后审计公开 + 用户全额赔付:**回 +20**

**B1 当前 TVL**(满分 40):

| TVL | 分 |
|---|---|
| ≥ $1B | 40 |
| $500M - $1B | 35 |
| $200M - $500M | 28 |
| $50M - $200M | 18 |
| $10M - $50M | 8 |
| < $10M | 0 |

**C1 24h 跨链成功率**(满分 50):

| 成功率 | 分 |
|---|---|
| ≥ 99.5% | 50 |
| 99% - 99.5% | 40 |
| 98% - 99% | 25 |
| 95% - 98% | 10 |
| < 95% | 0 |

**D1 多签门槛**(满分 40):
- ≥ 13/19(Wormhole 当前):40
- 8/12 - 12/15:30
- 4/7 - 7/11:18
- ≤ 3/5:0

**D2 升级冻结**(满分 30):
- 7 天 timelock + 多签:30
- 24-72h timelock:18
- 即时升级 / 单 EOA 控合约:0

**D3 社区可监督**(满分 30):
- 完整开源 + 第三方审计:30
- 部分开源:18
- 闭源:0

(其他子项同理,完整规则见前述)

### §4.6.3 阈值与动作

| 总分 | 状态 | 动作 |
|---|---|---|
| **≥ 80** | Healthy | 可作主桥 |
| **60 - 80** | Watching | 仅作备桥;UI 标注"健康度一般" |
| **40 - 60** | Risky | 移出矩阵;用户主动选则强制弹警告 |
| **< 40** | Banned | 7 天黑名单 |
| **任意分数 + 24h 内有事故** | Frozen | 立即 7 天黑名单 |

### §4.6.4 评分公开化(差异化卖点)

`/api/bridges/health` 公开端点 + 主页"桥健康度仪表盘",所有评分 + 子项打分实时可查。**竞品都不做这个**。

---

## §4.7 跨链报价聚合(并发查桥)

### §4.7.1 流程时序

```
用户:买 1000 USD ETH 上的 PEPE
   │
   ▼
[Intent 解析] → 源链 Solana,目标链 Ethereum,目标 token PEPE,金额 1000 USDC
   │
   ▼
[查 §4.5 矩阵] → 候选桥:[deBridge(主), Wormhole+Mayan(备), Allbridge(紧急)]
   │
   ▼
[查 §4.6 健康度] → 过滤掉 < 60 分的桥
   │
   ▼
[并发查报价 — 3 路并行,timeout 3s]
   ├── deBridge API: GET /quote?from=sol&to=eth&amt=1000
   ├── Wormhole+Mayan API
   └── LiFi SDK getQuote()  (兜底广覆盖)
   │
   ▼
[报价归一化 → §4.7.2 评分公式]
   │
   ▼
[默认返第一名;Pro 模式返 Top 3]
```

### §4.7.2 报价归一化评分公式

```
综合得分 =  -1.0 × 净到账金额(归一化 0-100)
          + 0.6 × 时延(归一化 0-100,越快越高)
          + 0.4 × 健康度(0-100)
          - 1000 × (健康度 < 60 ? 1 : 0)   ← 低于 60 分硬剔除
```

**净到账金额** = 用户在目标链最终拿到的 USDC(已扣全部协议费 + Gas + 滑点)。

### §4.7.3 决策矩阵示例(Solana → Ethereum 1000 USDC)

| 桥 | 净到账 | 时延 P50 | 健康度 | 综合得分 | 排名 |
|---|---|---|---|---|---|
| deBridge | 998.2 USDC | 2 min | 88 | **89.4** | 1(主推) |
| Wormhole+Mayan | 997.5 USDC | 8 min | 72 | 71.8 | 2 |
| Allbridge | 996.0 USDC | 15 min | 68 | 58.4 | 3 |
| LiFi 路由(实际指 deBridge) | 998.0 USDC | 2 min | 88 | 88.9 | 对账用 |

**对账规则**:LiFi 给的最优路由若与自研第一名差 > 0.3% 净到账,触发告警。

### §4.7.4 并发查询性能

- 总 timeout 3s(3s 内没回的桥被踢出本次)
- 至少 1 个桥成功才返报价;0 个 → 错误"目前所有桥不可用,请稍后再试"
- 报价缓存 30s(同源同目标同金额复用)— **注**:此缓存仅 30s,与 §1.7 价格不缓存铁律不冲突(桥报价含桥流动性 + 路径,可短时窗口稳定)

---

## §4.8 跨链报价对比展示

### §4.8.1 默认模式

```
┌─ 跨链买 PEPE ────────────────┐
│ 您支付:        1000 USDC(Sol)│
│ 目标到账:      约 998 USDC(Eth)│
│ 然后买入:      约 84,200 PEPE  │
│ 预计 5 分钟内完成              │
│                                │
│ [查看更多桥(Pro)]              │
│ [一键确认]                     │
└────────────────────────────────┘
```

### §4.8.2 Pro 模式

```
┌─ 跨链报价对比 ────────────────────────────────┐
│ 路径 1 ✓ deBridge       998.2 USDC  2 min  88 │
│ 路径 2   Wormhole+Mayan 997.5 USDC  8 min  72 │
│ 路径 3   Allbridge      996.0 USDC 15 min  68 │
│                                                │
│ 推荐路径 1:net 多 0.7 USDC,快 6 min,健康度高 │
│ [选路径 1] [选路径 2] [选路径 3] [刷新]        │
└────────────────────────────────────────────────┘
```

Pro 模式额外:每行点击展开 → 显示费用拆解(协议费 / Gas / 滑点);默认 30s 自动刷新。

---

## §4.9 跨链 + Swap 一站式

> US-CFR-01 主路径,产品差异化最强场景。

### §4.9.1 内部步骤

```
1. Intent 解析       → 跨链 Solana USDC → Ethereum,目标 swap PEPE
2. 跨链报价(§4.7)   → deBridge 1000 USDC → 998.2 USDC@Eth
3. 目标链 swap 报价  → Uniswap V3:998.2 USDC → 84,200 PEPE(滑点 0.5%)
4. 总成本核算        → 用户实付 1000 USDC,实得 84,200 PEPE,综合费率 0.18%
5. 用户确认          → 默认 [一键确认]
6. 执行
   ├── 6.1 Solana 端发起跨链(deBridge SDK)
   ├── 6.2 等到账(状态机 §4.10)
   ├── 6.3 到账后立即 swap(DEX Router §6)
   └── 6.4 失败回退 §4.9.3
```

### §4.9.2 失败回退(关键)

| 失败位置 | 处理 |
|---|---|
| 跨链失败 | 资金回 Solana 原地;通知用户 |
| **跨链成功但 swap 失败**(主流场景:目标 token 滑点暴跌 / 流动性消失) | **资金以 USDC 形式留在目标链**,通知用户:"已到账 998 USDC@Ethereum,但 PEPE 当前滑点过大未买入,资金安全;[再试一次] [换 token] [跨回 Solana]" |
| Gas 不足 | Agent 自动从 USDC 兑一点 ETH 作 Gas(预留缓冲) |

**核心承诺**:跨链 + swap 失败时,**资金必定以稳定币形式留在某条链上**,绝不会蒸发或卡在桥内部。

---

## §4.10 进度跟踪状态机

### §4.10.1 状态枚举(8 个 + 1 终态)

| 状态码 | 名称 | 含义 |
|---|---|---|
| `INITIATED` | 已发起 | 用户确认,产品已生成跨链订单 |
| `SRC_BROADCASTED` | 源链已广播 | 跨链 tx 上源链 mempool |
| `SRC_CONFIRMED` | 源链已确认 | 源链 tx 达到 finality(Sol: 32 slot / Eth: 12 block / L2: 1 block + 1 min) |
| `BRIDGE_PROCESSING` | 桥处理中 | 桥已收到事件,正在签名 / 转发 |
| `DST_BROADCASTED` | 目标链已广播 | 目标链 tx 上 mempool |
| `DST_CONFIRMED` | 目标链已确认 | 资金到账 |
| `SWAP_EXECUTING` | 目标 swap 中 | (跨链买币场景)swap 已提交 |
| `COMPLETED` | 已完成 | swap 成功 / 纯跨链已到账 |
| `FAILED_*` | 失败族(详见 §4.12) | 不同失败子类 |

### §4.10.2 状态转换图

```
INITIATED
   │ (源链签名 + 广播)
   ▼
SRC_BROADCASTED ────────────► FAILED_SRC_REVERT
   │ (源链 finality)              ▲ tx revert
   ▼
SRC_CONFIRMED  ────────────► FAILED_BRIDGE_TIMEOUT
   │ (桥事件 listener 触发)       ▲ 桥未在 SLO×3 内响应
   ▼
BRIDGE_PROCESSING ─────────► FAILED_BRIDGE_REJECT
   │ (桥发起目标链 tx)             ▲ 桥拒单
   ▼
DST_BROADCASTED ──────────► FAILED_DST_REVERT
   │ (目标链 finality)
   ▼
DST_CONFIRMED ─────────────► COMPLETED(纯跨链结束)
   │ (跨链买币场景才进下一步)
   ▼
SWAP_EXECUTING ────────────► FAILED_SWAP(资金停留 USDC,详见 §4.9.3)
   │ (swap tx confirmed)
   ▼
COMPLETED
```

### §4.10.3 转换条件 + 时延 + 用户感知

| 转换 | 触发条件 | 预期时延 | 用户感知 |
|---|---|---|---|
| INITIATED → SRC_BROADCASTED | 源链 RPC 接受 tx | < 5s | 静默(Spinner) |
| SRC_BROADCASTED → SRC_CONFIRMED | 达到 finality | Sol 13s / Eth 3min / L2 1min | 进度条 25% |
| SRC_CONFIRMED → BRIDGE_PROCESSING | 桥 listener 检测到事件 | < 30s | 进度条 50%,文案"桥正在处理" |
| BRIDGE_PROCESSING → DST_BROADCASTED | 桥发出目标链 tx | 与桥相关:Across 30s / deBridge 1m / Wormhole 5m | 进度条 70% |
| DST_BROADCASTED → DST_CONFIRMED | 目标链 finality | Sol 13s / Eth 3min / L2 1min | 进度条 90% |
| DST_CONFIRMED → SWAP_EXECUTING | swap tx 提交 | < 5s | 文案"已到账,正在买入 PEPE" |
| SWAP_EXECUTING → COMPLETED | swap tx 确认 | < 30s | 进度条 100%,绿色 ✓ |

### §4.10.4 状态查询机制

- **拉模式**:UI 每 3s 查 `/api/cross-chain/order/{id}/status`
- **推模式(主)**:WebSocket / SSE 推送状态变更,延迟 < 1s
- **断网兜底**:用户重新打开 App 时,后端从订单 ID 重建状态(任何状态都可幂等查询)

---

## §4.11 进度通知策略

### §4.11.1 通知矩阵

| 状态 | App Push | App Banner | Email | 系统通知中心 |
|---|---|---|---|---|
| INITIATED | — | ✓ | — | ✓ |
| SRC_CONFIRMED | — | ✓ | — | ✓ |
| BRIDGE_PROCESSING | — | ✓ | — | ✓ |
| DST_CONFIRMED | ✓ | ✓ | — | ✓ |
| COMPLETED | ✓ | ✓ | ✓(可选) | ✓ |
| FAILED_* | ✓(强制) | ✓(红色) | ✓(强制) | ✓ |
| 桥升级警告 | ✓ | — | — | ✓ |

### §4.11.2 文案原则

- 不说技术术语:不说"finality",说"已确认"
- 失败必给 3 个选项:重试 / 换桥 / 联系客服
- 时间永远是相对值:"约 3 min",不说"180s"
- 资金安全永远是第一句:"您的 USDC 安全,已留在 Ethereum"

### §4.11.3 通知节流

- 同一订单 < 1 min 内不重复推
- INITIATED → DST_CONFIRMED 中间状态默认不强推
- 跟单跨链(US-CFR-07)的中间过程**全合并为一条最终通知**

---

## §4.12 失败场景全分类

### §4.12.1 11 个具名失败场景

| ID | 场景 | 触发条件 | 处理方案 | 用户文案 |
|---|---|---|---|---|
| **F-01** | 源链 tx revert | Gas 不足 / nonce 冲突 / 余额不足 | 自动重发 1 次(Gas + 20%);仍失败终止 | "源链交易失败:Gas 不足 / 余额不够,资金未动" |
| **F-02** | 源链 tx 卡 mempool > 30 min | Gas 涨价 | replace-by-fee 提 Gas;仍卡 → 取消 tx | "源链拥堵,系统已自动加速" |
| **F-03** | 桥未响应(SRC_CONFIRMED 后 SLO×3 无桥事件) | 桥宕机 | 走备桥;若有部分入桥资金 → 等桥退款超时(deBridge 30 min) | "主桥延迟,系统已切备桥;原资金 30 min 内会自动退回源链" |
| **F-04** | 桥拒单 | 桥流动性紧张 / 价格脱锚 | 取消订单,资金已退原链;切备桥重试 | "桥流动性紧张,已切换备桥重试" |
| **F-05** | 桥被黑(极端) | 桥事故公开披露 | 立即冻结;启动 §4.13 流程 | 详见 §4.13 |
| **F-06** | 目标链 tx revert | 目标链 RPC 异常 | 桥会自动重试;若桥放弃 → 走 F-04 流程 | "目标链网络波动,已自动重试" |
| **F-07** | 目标链到账金额 < 预期(超 1%) | 桥滑点 > 报价 | 通知用户实到金额;不影响下一步 swap(用实到金额计算) | "实际到账 990 USDC(预报 998),原因:桥流动性波动,资金已到账安全" |
| **F-08** | 跨链买币 — swap 失败 | 目标 token 滑点暴跌 / 流动性枯竭 | 资金停留 USDC@目标链 | 详见 §4.9.3 |
| **F-09** | Gas 不足(目标链) | 用户目标链没原生 Gas token | Agent 自动从 USDC 兑 0.005 ETH 作 Gas | "已为您预留 0.005 ETH 作 Gas,共 ~ 12 USDC" |
| **F-10** | 部分到账(Stargate 路径 LP 不足) | 桥 LP 失衡 | 等待 LP 补充自动续到账;> 30 min 未补 → 走 F-04 退款 | "部分到账,LP 补充中" |
| **F-11** | 用户中途取消(已发出但未确认) | 用户主动点击取消 | 提交链上 cancel tx;若已 SRC_CONFIRMED 则不可取消 | "源链已确认,无法取消;若失败资金会自动退回" |

### §4.12.2 失败处理通用原则

1. **永不静默失败**:任何 FAILED_* 必须三渠道推送
2. **永不让用户找客服**:80% 失败场景必须有自动重试 / 切桥 / 退款
3. **失败可解释**:UI 永远展示具体原因(F-XX 编码)+ 当时的桥健康度快照
4. **失败可申诉**:用户一键发起客服工单,自动带上 order_id + 全状态机日志

---

## §4.13 资金不蒸发承诺(用户视角文案)

### §4.13.1 "你的钱永远在某条链上"

我们承诺:

> **任何跨链交易,资金最多以下 3 种状态存在:**
>
> 1. ✓ 在你**源链**钱包里(还没动 / 失败已退回)
> 2. ✓ 在你**目标链**钱包里(已到账)
> 3. ✓ 临时在桥的合约里(状态机精确显示哪一步,**桥被黑除外**)
>
> **资金永远不会"消失"。**

### §4.13.2 桥被黑场景文案(F-05)

```
┌─ 重要安全通知 ──────────────────────────────────┐
│ 您的 200 USDC 因 [Wormhole 桥事故] 暂时无法到账   │
│                                                  │
│ 我们已经做了:                                    │
│  ✓ 立即冻结所有该桥新订单                         │
│  ✓ 您的资金当前位置:Wormhole 桥合约              │
│  ✓ 已联系桥方协调退款                             │
│  ✓ 已启动我方 $10M 桥事故保险预备金               │
│                                                  │
│ 接下来:                                          │
│  • 桥方 7 天内出方案 → 等待                        │
│  • 桥方破产 → 我方保险 7 个工作日内全额垫付        │
│                                                  │
│ [查看公开声明]  [一键提交客服优先工单]             │
└──────────────────────────────────────────────────┘
```

### §4.13.3 保险机制(R49 落地,R48 PRD 锁定承诺)

- 自购险:每月预留 0.5% 跨链交易 GMV 进入保险池,目标 $10M cap
- 适用范围:桥被黑造成的用户资金损失,**仅限我们矩阵内主桥 + 备桥**
- 用户主动选低分桥(< 60)出事 → 不在保险范围(UI 警告时已明示)
- 限额:单用户单次 $50k 上限

---

## §4.14 桥黑名单 + 实时风险监测

### §4.14.1 数据源(7 个 + 自家)

| 数据源 | 用途 | 拉取频率 |
|---|---|---|
| Rekt News API | 历史攻击 + 实时大型 hack 事件 | 5 min |
| DefiLlama API | TVL 实时 | 1 min |
| Chainalysis Reactor(付费) | 链上异常资金流 | 实时 webhook |
| Etherscan / Solscan API | 合约升级监控 | 5 min |
| 桥官方 status page | 自报状态 | 1 min |
| Twitter / X 关键词 | "[桥名] hack/exploit/paused" | 实时 stream |
| GitHub Advisory | 公开漏洞披露 | 1h |
| **自家埋点** | 24h 成功率 / 时延 | 实时 |

### §4.14.2 自动加黑触发条件

任意条件命中 → 自动 7 天黑名单:

1. Rekt News 流量出现"[桥名] + exploit/hack/drained"
2. TVL 单次跌幅 > 30%
3. 24h 成功率跌破 95%
4. 桥官方 status 出现"degraded/incident"持续 > 30 min
5. Twitter 5 min 内出现 ≥ 50 条该桥 + "hack" 相关帖
6. 链上检测到桥合约被调用 admin function(非 timelock)
7. **风控团队人工拉黑**(任意时刻)

### §4.14.3 加黑动作(< 60s 完成)

```
1. /api/admin/bridge/{name}/blacklist 触发
2. 配置中心立即更新(Redis 推)
3. 所有进行中订单评估:
   ├── 状态 < BRIDGE_PROCESSING:立即取消,资金回原链
   └── 状态 ≥ BRIDGE_PROCESSING:不动,继续走完(桥已经在处理),但加红色 banner
4. 矩阵 §4.5 自动重排
5. 推送给所有受影响订单的用户
6. /admin/dashboard 红色高亮
7. 同步 Telegram / Slack 风控群
```

### §4.14.4 解除黑名单

- 7 天最短期限
- 期满后人工 review:健康度 ≥ 80 + 桥方完成 post-mortem + 第三方审计公开 → 可解黑
- 解黑后健康度上限锁 75 分(永远低于无事故桥),持续 30 天观察期

---

## §4.15 历史攻击案例(产品参考)

### §4.15.1 Wormhole — 2022-02-02

- **损失**:120,000 wETH(约 $325M)
- **根因**:Solana 合约 `verify_signatures` 实现允许伪造签名,绕过 Guardian 多签直接 mint
- **修复**:24h 内 Jump Trading 自掏 $325M 补窟窿
- **我们如何避免**:
  1. Wormhole 在 §4.5 矩阵中**永远不做主桥**
  2. §4.6 健康度公式 A1 子项扣 50 分,Wormhole 当前总分约 72(只能做备桥)
  3. 监听桥合约 admin event,类似事件 60s 内自动加黑

### §4.15.2 Nomad — 2022-08-01

- **损失**:$190M
- **根因**:合约升级时 `acceptableRoot[0x0]` 被错误初始化为 valid
- **特点**:这是开源代码升级失误,**不是私钥泄露**
- **我们如何避免**:
  1. §4.6 D2 子项严查升级 timelock
  2. §4.14 监听 Etherscan upgrade event;升级后 24h 内桥健康度自动 -20

### §4.15.3 Ronin Bridge — 2022-03-23

- **损失**:$625M(史上最大)
- **根因**:9 个验证者中 5 把私钥泄露(社工 Sky Mavis 员工)
- **我们如何避免**:任何 ≤ 5 验证者的桥永远不进矩阵

### §4.15.4 Multichain — 2023-07-07(跑路)

- **损失**:约 $1.5B(协议方失踪 + CEO 被中国警方带走)
- **根因**:**单一 EOA 控制所有桥合约的私钥**
- **我们如何避免**:任何 EOA 单签桥 = 直接 0 分,不可能进矩阵

### §4.15.5 教训汇总(产品规则)

| 历史教训 | 我们的产品规则 |
|---|---|
| 大桥也会被黑(Wormhole) | 没有桥能做"唯一桥",任何路径都必须有备 |
| 合约升级最危险(Nomad) | 升级后 24h 自动降级 |
| 私钥多签门槛是关键(Ronin / Harmony) | < 5/9 不入矩阵,< 8/12 不能做主桥 |
| 治理跑路也是失败(Multichain) | 单 EOA 直接 ban |
| 用户事后才知道,客服找不到 | 我们三渠道强推 + 客服 SLA 4h 必回 |

---

## §4.16 Agent 自动跨链跟单

### §4.16.1 预授权配置(用户在设置里勾)

```
☑ 允许 Agent 自动跨链(关闭则跨链必须确认)

单笔限额:    [$500]
单日限额:    [$2000]
仅以下场景可触发:
  ☑ 跟单 KOL(如 KOL 加仓另一链)
  ☑ 紧急止损(本链流动性差)
  ☐ 套利(默认关)

仅以下桥可用:
  ☑ 健康度 ≥ 80(高安全)
  ☐ 健康度 ≥ 60(中等)

通知频率:    [合并为一条最终通知 ▼]
```

### §4.16.2 风控前置检查链(每次自动跨链都跑一遍)

```
1. 是否在用户授权场景内?       否 → 拒,提示用户 hand-off 手动
2. 是否在单笔/单日限额内?       否 → 拒,提示用户 hand-off
3. 候选桥是否满足用户配置阈值?  否 → 降级走手动
4. 当前是否处于 Crisis 模式?    是 → 全停(联动 §9 风控 Kill Switch)
5. 用户是否在线? UI 是否打开?  无关(本来就要无人值守)
6. 全部通过 → 触发 §4.7 报价聚合 → 自动选 Top 1 → 执行
```

### §4.16.3 Agent 自动跨链与 HITL 联动

| 场景 | HITL 行为 |
|---|---|
| Agent 自动跨链 < 用户单笔限额 | 不触发 HITL,直接走 |
| Agent 自动跨链 ≥ 单笔限额 | **拒绝**(超授权,而非半自动) |
| Agent 自动跨链 + 跟单买入 ≥ HITL 阈值 | 跨链段不弹,**到目标链 swap 段触发 HITL 10s 撤销** |
| Agent 自动跨链 + 紧急止损 | sell-side,永远 auto 不弹 |

### §4.16.4 通知合并

跟单跨链场景,4 个状态变更不分别推送,**合并为最终一条**:

```
✓ 跟单 @KOLAlice 完成
路径:Solana 200 USDC → Base USDC → Cake
实付 200 USDC,实得 134.2 Cake
耗时 4 min,综合费率 0.21%
[查看详情]
```

---

## §4.17 验收标准

### §4.17.1 功能验收(10 项)

| 编号 | 验收点 | 通过条件 |
|---|---|---|
| AC-01 | 8 条主链 ↔ 8 条主链所有组合可成功跨链 | 矩阵每格至少 1 条路径成功率 ≥ 99%(7 天连续) |
| AC-02 | Solana ↔ EVM 跨链买币一站式 | US-CFR-01 完整链路,P50 < 8 min |
| AC-03 | 报价聚合返 ≥ 2 个桥报价 | 95% 请求返至少 2 个有效报价 |
| AC-04 | 桥健康度评分公开 + 实时 | `/api/bridges/health` 5 min 数据延迟 |
| AC-05 | 失败场景 F-01 ~ F-11 全部可测 | Chaos test 11 场景全过 |
| AC-06 | 桥黑名单加黑 < 60s | 模拟事故 → 加黑动作完成 < 60s |
| AC-07 | 资金不蒸发 | 30 天内 0 起"完全丢失"事件 |
| AC-08 | Agent 自动跨链限额检查 | 100% 超限请求被拒 |
| AC-09 | 进度状态机 8 状态 + 11 失败子态全实现 | 单测覆盖 100% |
| AC-10 | 通知 3 渠道送达 | 失败通知 P95 < 30s 触达三渠道 |

### §4.17.2 性能验收

| 指标 | 目标 |
|---|---|
| 报价聚合返回 P50 | < 1.5s |
| 报价聚合返回 P95 | < 3s |
| EVM ↔ EVM 跨链 P50 | < 5 min |
| Solana ↔ EVM 跨链 P50 | < 8 min |
| 跨链 + swap 一站式 P50 | < 10 min |
| 跨链 + swap 一站式 P95 | < 25 min |
| 跨链失败率 | < 0.5% |
| **完全丢失率** | 0% |
| 桥黑名单触发延迟 | < 60s |
| 用户感知状态延迟(UI) | < 5s |

---

## §4.18 监控埋点

### §4.18.1 表结构(新增)

| 表名 | 用途 |
|---|---|
| `cross_chain_orders` | 主订单(状态机 + 选定桥 + 用户 + 金额) |
| `cross_chain_quotes` | 每次报价聚合的全部候选(供事后审计 / 改进选桥) |
| `cross_chain_state_log` | 状态机变更历史 |
| `bridge_health_snapshots` | 每 5 min 全桥健康度快照 |
| `bridge_blacklist_events` | 加黑 / 解黑历史 |
| `bridge_incidents` | 已知桥事故事件(自家纪录 + 第三方喂源) |

### §4.18.2 必采指标(Prometheus / 自家时序库)

```
cross_chain.order.initiated.count    (counter, 含 src_chain/dst_chain/bridge label)
cross_chain.order.completed.count    (counter)
cross_chain.order.failed.count       (counter, 含 failure_code label F-01..F-11)
cross_chain.duration.p50/p95/p99     (histogram, 含 src/dst/bridge label)
cross_chain.quote.duration           (histogram)
cross_chain.quote.bridges_returned   (gauge, 每次返几个有效报价)
cross_chain.quote.aggregator_diff_bps (gauge, LiFi vs 自研第一名净到账差异)
bridge.health_score                  (gauge, 每桥每维度)
bridge.success_rate_24h              (gauge, 每桥)
bridge.tvl                            (gauge)
bridge.blacklist.events               (counter)
bridge.swap_slippage_actual           (gauge, 实际滑点)
agent.auto_cross_chain.attempts       (counter)
agent.auto_cross_chain.rejected_by_limit (counter)
```

### §4.18.3 告警阈值

| 告警 | 触发条件 | 严重等级 |
|---|---|---|
| 跨链失败率突增 | 1h 失败率 > 1% | P1 |
| 桥健康度暴跌 | 单桥 1h 内分数下降 > 20 | P1 |
| 任何桥被加入黑名单 | 黑名单 event | P0 |
| 跨链订单 stuck | 单订单超 SLO × 3 仍未终态 | P2(单订单),P1(同时刻 ≥ 5 个) |
| 报价聚合 0 桥可用 | 1 min 内无任何报价返回 | P0 |
| 报价对账偏差 | LiFi vs 自研第一名偏差 > 0.3% net | P2(单笔),P1(1h ≥ 10 笔) |
| 资金不蒸发承诺触发 | 任何"完全丢失" suspect | P0,人工立刻介入 |

### §4.18.4 公开仪表盘

`/admin/dashboard/cross-chain` 内部 + `/status/bridges` 公开。

公开页含:每桥健康度评分 + 24h 成功率 + 30 天事故时间线。

**这是产品差异化的信任锚**:用户可以直接看到我们对桥的判断,不是黑盒推荐。
# §5 链上数据信号 — 详细规格(R48)

> 链上发生有趣的事 → Agent 主动告诉用户 + 帮用户决定要不要跟。Owner:产品 + 数据团队 + Agent 团队。冲突时数据准确率 > 推送频率 > UI 美观。

---

## §5.0 模块定位 + 北极星指标

### 5.0.1 模块定位

链上数据信号(简称"信号模块")是 AI Agent 的**眼睛和耳朵**。它的职责是:

1. **监听**链上发生的"有交易价值的事件"(鲸鱼动作 / 异动 / 共识 / 新币 / KOL / 套利 / 风险 / 行业)
2. **过滤** 95% 的噪声,只把"有信号价值"的事件挑出来
3. **解释**给用户:为什么这件事值得看,过去类似事件的胜率
4. **推送**(App / TG / Web banner)在合适时机、合适频率、合适用户面前
5. **闭环**:一键跟单 → 风控 → 执行 → 反馈胜负 → 反哺鲸鱼/KOL 评分

**信号模块不是**:不是行情指标工具(MACD/RSI 不在此模块);不是投顾建议;不是全市场扫描器(我们做"用户相关"的精挑)。

### 5.0.2 北极星指标(R48 → R52 季度目标)

| 指标 | R48 上线 | R50(60 天) | R52(120 天) |
|------|---------|------------|-------------|
| 信号点击率(CTR) | ≥ 18% | ≥ 25% | ≥ 30% |
| 信号 → 跟单转化率 | ≥ 4% | ≥ 8% | ≥ 12% |
| 跟单 24h 胜率(中位数) | ≥ 52% | ≥ 56% | ≥ 60% |
| 跟单 24h 平均 PnL | ≥ +2% | ≥ +5% | ≥ +8% |
| 用户日均收到信号数 | 3-8 条 | 4-10 条 | 5-12 条(可个性化) |
| 推送投诉率(关闭通知) | < 2%/周 | < 1.5%/周 | < 1%/周 |
| 信号端到端延迟(P95) | < 30s | < 15s | < 8s |
| 信号准确率(数据真实性) | ≥ 99.0% | ≥ 99.5% | ≥ 99.9% |

**北极星单一指标(SVS)**:`跟单 24h 胜率 × 跟单转化率 × DAU`。三周环比下降 > 15% → 触发信号策略 review。

---

## §5.1 用户故事(10 个)

**US-S01 鲸鱼买入跟单**:T1 鲸鱼 18:32 买入 $WIF $187k,Agent 推送→ 用户点跟单 $200 → 14 秒后 Jupiter 路由完成 → 30 分钟后涨 12%。

**US-S02 多鲸鱼共识**:深夜 02:15,4 个 T1 鲸鱼独立买入 $BERA $1.2M。免打扰时段不弹,写入"晨报"。

**US-S03 大额卖出预警**:用户持仓 $POPCAT,T0 巨鲸向 Binance 充值 5% 流通。**critical 推送**:"60 天内 7 次类似动作中 5 次后 24h 跌 > 15%"。

**US-S04 聪明钱共识**:Top 200 聪明钱 6h AI 板块净流入从 $300k 跃 $4.2M。推 ETF 一键买。

**US-S05 KOL 喊单**:T2 KOL 推 $BONK,10 分钟链上**新地址 +280%、$1k+ 买单 × 4.2**。Agent 推+标"中等可信"。

**US-S06 新币上线高质量**:5 分钟 LP $0→$180k、独立买家 60、dev 未抛售。**严筛通过**才推。

**US-S07 套利机会(V2)**:$SOL Raydium $187.32 vs Orca $189.85 价差持续 > 3 秒,仅推高级用户。

**US-S08 老鼠仓警告**:用户持仓 $JTO,合约新增 30% 通胀 mint 权限。**最高优先级**。

**US-S09 行业事件**:BTC 03:47 突破 $108k ATH。**仅首屏 banner,不推 push**(避免半夜)。

**US-S10 用户自定义信号(V1.5)**:手动添加 3 鲸鱼 + 1 token 监听规则。

---

## §5.2 产品边界

### 在范围(R48 P0 MVP)
- 信号类型:鲸鱼买入 / 大额异动 / 聪明钱共识 / 新币上线 / 老鼠仓警告 / 行业事件(6 类)
- 链:Solana(主)、Ethereum、Base、BSC(EVM 三链)
- 推送通道:App push、Telegram、Web 站内 banner
- 信号语言:中文 + 英文
- 一键跟单:复用 §3 交易引擎,接 §6 风控

### 在范围(R49 P1)
- KOL 喊单(Twitter/X 监听 + 链上跟随交叉验证)
- 用户自定义信号
- 信号详情页"历史相似事件"分析

### 在范围(R50+ P2)
- 套利信号(链间 + DEX 间)
- 板块 ETF 一键买
- 信号转化率 A/B 实验框架

### 不在范围(本季度)
- 不做 K 线技术指标信号(MACD/RSI/布林)
- 不做 Twitter/Discord 全市场情绪扫描(仅做白名单 KOL)
- 不做合约预警之外的"DeFi 健康度监控"
- 不做 NFT 鲸鱼信号
- 不做"投顾"性质的"建议买入"措辞

---

## §5.3 竞品全景对比表(8 竞品 × 10 维度)

| 维度 | Nansen | Arkham | DeBank | GMGN | Cielo | Bullx | BananaGun/Maestro | Photon/Axiom/FOMO |
|------|--------|--------|--------|------|-------|-------|---------------------|-----|
| 起家定位 | 鲸鱼标签 + 链上分析 | 去匿名 + 实体追踪 | 钱包组合 + DeFi | TG bot 鲸鱼跟单 | Smart wallet 跟踪 | TG bot 交易 + 信号 | TG bot 快速 swap | Web 端 meme 交易 |
| 信号类型数 | 12+(Smart Money / Hot Contracts) | 8+(实体动作 / 大额) | 6(钱包动作为主) | 8+(鲸鱼 / 新币 / KOL) | 5(Smart wallet 跟踪) | 10+(TG bot 全套) | 5-7(快速跟单导向) | 8+(meme 币新发 / 拉盘) |
| 鲸鱼地址来源 | 自家 5 年标签库,~50 万地址 | 实体图谱 + UGC 标签 | UGC + 算法 | 算法挖掘 + 用户付费查 | 用户自添加 + Cielo 推荐 | 自家 + 第三方 | 第三方 + 算法 | 算法 + 第三方 |
| 鲸鱼分级 | 7+ tier(Smart Money / Fund / Whale) | 实体类型 | 简单 tag | 3 tier(K/M/B 资金量) | 用户自定 | 简单 tier | 无明确分级 | 简单分级 |
| 推送通道 | 邮件 + Web app + Telegram(付费) | Web + Email + Discord webhook | Web + Email | Telegram 为主 + Web | Telegram + Email + Discord | Telegram | Telegram | Telegram + Web |
| 一键跟单 | ✗(数据工具,不交易) | ✗ | ✗ | ✓(Telegram bot) | ✗(只通知) | ✓ | ✓(主打) | ✓ |
| 数据源(推测) | 自家 indexer + 多链 RPC | 自家 + The Graph | 自家 indexer | Helius + 自家 | Helius + Alchemy | Helius + 自家 | Helius + Jupiter | Helius |
| 历史准确率公开 | 部分(Smart Money 板块) | ✗ | ✗ | ✗(社区有口碑) | ✗ | ✗ | ✗ | ✗ |
| 定价 | $150-1800/月 | 免费 + Premium | 免费 + Pro | 免费 + 0.5% trade fee | 免费 + Premium $40/月 | 1% trade fee | 1% trade fee | 1% trade fee |

### 5.3.2 关键观察(我们的入场窗口)

1. **Nansen / Arkham / DeBank** 是"数据工具",有信号但**没有一键交易**
2. **GMGN / Bullx / BananaGun / Photon** 有交易能力,但**信号策略粗暴**,主打"全市场鲸鱼大单 list",**没有 AI 解释**
3. **Cielo** 做得最近(Smart wallet + 通知),但**只通知不交易**
4. 所有竞品**没有一家**做"AI 解释 + 历史相似度 + 一键跟单 + 风控"全闭环 — **这是我们的位置**

### 5.3.3 阈值参数对比

| 信号 | GMGN 默认 | Cielo 默认 | Nansen 默认 | 我们 R48 默认 |
|------|-----------|-----------|-------------|--------------|
| 鲸鱼单笔买入 | $10k(SOL)/ $50k(EVM) | $25k | $100k | **$50k**(EVM)/ **$10k**(SOL) |
| 多鲸鱼共识 | 无明确 | 3 个 / 24h | 5 个 / 24h | **3 个 / 6h**(独立钱包) |
| 大额异动(Token) | 单笔 ≥ 流通 0.5% | 单笔 ≥ $50k | 单笔 ≥ $200k | **单笔 ≥ MAX($50k, 流通量 0.3%)** |
| 新币质量门槛 | 5 分钟 LP ≥ $50k | 无 | 无 | **5 分钟 LP ≥ $80k + 买家 ≥ 30 + dev 不抛** |
| Token 通胀/mint 警告 | 无 | 无 | 部分 | **任何 mint 操作 + dev 钱包动作**立即推 |

---

## §5.4 我们的差异化(5 点)

1. **AI 解释层(独有)**:每条信号附"为什么这值得看"+"过去类似 N 次事件中 X 次盈利"。LLM 用 Haiku/Sonnet 生成 1-2 句话解释。
2. **跟单全闭环(独有)**:信号 → 一键跟 → 风控(§6) → 执行(§3) → SL/TP 监控 → 复盘反馈。**竞品最多做到"跟单",没人做"复盘 + 反哺评分"**。
3. **持仓优先级(独有)**:用户持仓 token 的负面信号最高优先级,**比鲸鱼买入信号更重要**($1 损失 ≈ $2 盈利的心理价值)。
4. **频率智能控制**:不是"每条都推",而是 LLM 判断"这条对当前用户的边际价值"。同类信号 30 分钟内合并。
5. **鲸鱼评分动态化**:鲸鱼 tier 不是静态,每 24h 重算胜率,T1 跌出门槛自动降级,T3 升档需 30 天 ≥ 60% 胜率。

**与 GMGN 的差异化定位**:GMGN 是"鲸鱼大单广播站",我们是"AI 私人交易顾问"(精选 + 解释 + 闭环 + 持仓相关优先)。GMGN 用户日均 50-200 条信号,我们目标 3-8 条。**少而精**。

---

## §5.5 信号类型全景(8 类 × 子场景矩阵)

### 通用字段(所有信号共有)

```json
{
  "signal_id": "sig_<uuid>",
  "type": "whale_buy | whale_sell | smart_money_consensus | kol_call | new_token | rugpull_warning | industry_event | arbitrage",
  "tier": "T0 | T1 | T2 | T3",
  "priority": "critical | high | medium | low",
  "chain": "solana | ethereum | base | bsc",
  "token": { "address", "symbol", "name", "liquidity_usd", "mcap_usd" },
  "trigger_at": "ISO8601",
  "trigger_value_usd": 187000,
  "explanation": "AI 生成的 1-2 句中文解释",
  "historical_similar_count": 14,
  "historical_win_rate": 0.67,
  "cta": [...],
  "data_source": "helius | alchemy | self_indexer",
  "data_latency_ms": 2400,
  "user_relevance": "holding | watching | none"
}
```

### §5.5.1 鲸鱼买入(5 子场景)

| 子场景 | 触发参数 | 推送模板 | 频率上限 | 优先级 |
|---|---|---|---|---|
| **S01a 单鲸鱼大额买入** | 单笔 ≥ MAX($50k EVM / $10k SOL, 流通 0.5%);来自 T0/T1/T2 鲸鱼 | `🐋 T{tier} 鲸鱼 {wallet}({label})刚以 ${amount} 买入 ${token},30 天胜率 {win_rate}%` | 每用户每个鲸鱼每日 ≤ 3 条 | T0=critical / T1=high / T2=medium / T3=low |
| **S01b 单鲸鱼 24h 累计** | 同一鲸鱼 24h 内同 token 累计 ≥ MAX($150k, 流通 1%) | `🐋📈 T{tier} 鲸鱼 24h 累计买入 ${total} 的 ${token}({n} 笔)` | 每用户每个鲸鱼每 token 每周 ≤ 1 条 | high |
| **S01c 多鲸鱼共识** | 6h 内 ≥ 3 个独立 T0/T1/T2 鲸鱼共识买入,累计 ≥ $300k(去重同一实体) | `🧠🐋 6h 内 {n} 个独立鲸鱼共识 ${token},累计 ${total}` | 每用户每 token 每 24h ≤ 1 条;全局每用户每日 ≤ 5 条 | high |
| **S01d 鲸鱼"破仓"重仓** | 持仓占组合 > 20%,7 天前持仓 ≥ 3x | `🐋💎 T{tier} 把 ${token} 加到组合 {pct}%(7 天前 {pct_7d}%)` | 每用户每个鲸鱼每周 ≤ 2 条 | medium |
| **S01e 鲸鱼反向(用户持仓加权)** | 用户持仓 token,T0/T1 鲸鱼单笔卖出 ≥ MAX($30k, 流通 0.3%) | `⚠️🐋 你持仓的 ${token},T{tier} 鲸鱼刚卖 ${amount}({pct}%其总持仓)` | 每用户每持仓 token 每日 ≤ 5 条 | **critical** |

### §5.5.2 大额异动(5 子场景)

| 子场景 | 触发参数 | 推送模板 | 优先级 |
|---|---|---|---|
| **S02a 单笔超大买单(无关钱包)** | 任意地址(≥ 30 天历史 + 不在反向白名单)单笔买入 ≥ MAX($200k, 流通 1%) | `💰📈 ${token} 单笔 ${amount} 大额买入(地址未标签)` | medium |
| **S02b 单笔超大卖单** | 单笔卖出 ≥ MAX($200k, 流通 1%) | `💰📉 ${token} 单笔 ${amount} 大额卖出(去向:{cex_or_dex})` | 持仓 → critical / 非持仓 → low |
| **S02c 同 token 多空对决** | 1h 内,买侧累计 ≥ $500k 且卖侧累计 ≥ $500k,买卖方向钱包数 ≥ 5 vs 5 | `⚔️ ${token} 1h 多空对决:买 ${buy_total} ({n}) vs 卖 ${sell_total} ({n})` | medium / 持仓 high |
| **S02d 流动性骤变** | 5 min 内 LP 变化 ≥ ±30% | `💧 ${token} 5min LP {dir} {pct}%(${before} → ${after})` | 撤出且持仓 → critical / 其他 → medium |
| **S02e 异常 buy pressure** | 5 min 独立买家 ≥ 24h 中位数 × 5,买入额 ≥ $100k | `🔥 ${token} 5min ${n} 独立买家(平时 {median}),买盘热度异常` | medium |

### §5.5.3 聪明钱共识(5 子场景)

> "聪明钱"定义:Top 200 钱包,过去 90 天 PnL > $50k 且胜率 > 55%(每周日 04:00 重算)

| 子场景 | 触发参数 | 推送模板 | 优先级 |
|---|---|---|---|
| **S03a 单 token 集中流入** | 6h 净买入 ≥ 日常 × 3,绝对值 ≥ $500k | `🧠 聪明钱 6h 净买入 ${token} ${amount}({mult}x 日常),涉及 {n} 地址` | high |
| **S03b 板块轮动** | 6h 板块净流入 ≥ $2M,涉及 ≥ 3 个 token | `🧠📂 聪明钱 6h 流入 {sector} 板块 ${total},Top 3:...` | high |
| **S03c 时间窗加速** | 连续 3 个 1h 净买入递增,每 h ≥ +50% | `🧠⏩ ${token} 聪明钱买入加速:1h 前 ${a1} → 现在 ${a3}` | high |
| **S03d 早期信号(mcap < $5M)** | mcap < $5M 阶段 ≥ 5 地址累计 > $100k | `🧠🌱 聪明钱介入早期 ${token}(mcap ${mcap})` | medium |
| **S03e 撤退信号** | 6h 净卖出 ≥ 日常 × 3 | `🧠📉 聪明钱 6h 撤离 ${token} ${amount}` | 持仓 → high |

### §5.5.4 KOL 喊单(V1 — R49 上线)

> 白名单制:产品 + 数据团队维护 200 个 Twitter/X KOL,分 4 tier。R48 不做。

| 子场景 | 触发参数 | 推送模板 | 优先级 |
|---|---|---|---|
| **S04a 单 KOL 喊 + 链上跟随** | 推文含 token 提及,10 分钟内新地址 ≥ 平时 × 2 OR $1k+ 买单 ≥ 平时 × 3 | `📢 KOL @{handle}({tier},粉丝 {fol},30d 胜率 {win}%)喊单 ${token},链上跟随显著` | T1 → high / T2 → medium / T3 → low / T4 → 不推 |
| **S04b 多 KOL 共识** | 6h 内 ≥ 3 个 T1/T2 KOL 独立提及同一 token | `📢🧠 6h 内 {n} 个 KOL 共识 ${token}` | high |
| **S04c KOL 提示风险** | T1 KOL 推文含负面关键词 + token 提及 / 链上 KOL 钱包卖 ≥ $50k | `⚠️📢 KOL @{handle} 警示 ${token}({reason})` | 持仓 → critical |

### §5.5.5 新币上线(5 子场景)

> 新币高风险,所有 CTA **默认禁用一键跟,要求二次确认 + 默认上限 $50**。

| 子场景 | 触发参数 | 推送模板 | 优先级 |
|---|---|---|---|
| **S05a 高质量新 mint** | mint 后 5 min:LP ≥ $80k / 独立买家 ≥ 30 / 单一钱包持仓 ≤ 5% / dev 未抛 ≥ 50% / 无 mint 权限 | `🆕 新币 ${token} 5min LP ${lp} / {n} 买家 / dev 未抛 / 无 mint 权限。**早鸟筛选通过**` | medium |
| **S05b 流动性突增** | mcap < $10M,5 min LP +100% 且 +$200k | `💧🆙 ${token} 5min LP +{pct}%` | medium |
| **S05c 第一笔大单** | mint 后首次单笔 ≥ $20k,且来自 T0-T2 鲸鱼或聪明钱 | `🆕💰 新币 ${token} 首笔大单:${wallet} 买 ${amount}` | medium |
| **S05d Pump.fun 毕业** | Pump.fun token 完成 bonding curve(mcap ≥ $69k 协议规则) | `🚀 ${token} 完成 Pump.fun → Raydium 迁移` | medium |
| **S05e dev 抛售警告** | mint 后 24h 内 dev 抛售 ≥ 持仓 10% | `⚠️🆕 新币 ${token} dev 抛售 {pct}%` | 持仓 → critical |

### §5.5.6 套利机会(V2 — R50+ 仅高级用户)

R48 不做。子场景:链间价差 / DEX 间价差 / 资金费率套利 / 跨期套利 / MEV 反向。

### §5.5.7 老鼠仓警告(用户持仓相关 — critical 优先级)

> **所有此类信号默认绕过免打扰时段、绕过频率限制(每日上限 ≤ 20)**

| 子场景 | 触发 | 推送 | 优先级 |
|---|---|---|---|
| **S07a 持仓巨鲸 CEX 充值** | T0/T1 巨鲸向 CEX hot wallet 充值 ≥ MAX($100k, 流通 0.3%) | `🚨 你持仓的 ${token} 巨鲸充值 ${cex} ${amount}({pct}%流通),60d 内 {n} 次类似 {m} 次后跌 ≥ 15%` | **critical** |
| **S07b 合约 mint 事件** | 用户持仓 token 合约触发 mint,新增 ≥ 1% 流通 | `🚨 你持仓的 ${token} 合约 mint,新增 {pct}% 流通` | **critical** |
| **S07c 持仓 LP 撤出** | 覆盖于 §5.5.2 S02d + 持仓加权 | (同 S02d) | **critical** |
| **S07d 持仓 dev 大额转出** | dev 钱包 24h 内转出 ≥ 10% | `🚨 ${token} dev 钱包 24h 转出 {pct}%` | **critical** |
| **S07e 异常通胀/合约升级** | 合约 admin function 调用(EVM)或 program upgrade(SPL) | `⚠️ ${token} 合约升级/admin 调用` | high-critical |

### §5.5.8 行业事件(5 子场景)

> 全市场低优先级。**仅 banner / 不推 push(除非用户开启)**。

| 子场景 | 触发 | 优先级 |
|---|---|---|
| **S08a BTC/ETH 突破 ATH** | 双源验证(Coinbase + Binance)创历史新高 | low(banner)/ 用户开启 → medium |
| **S08b 重大 hack** | rekt.news / Beosin / SlowMist webhook;损失 ≥ $5M | 持仓 → critical / 全市场 → high |
| **S08c 主流币重大新闻** | 5 个白名单新闻源 + LLM 摘要分类 high impact | low / banner |
| **S08d Fed 决议 / 宏观** | FOMC / CPI / PPI 前 1h 提醒 + 后 5min 推送 | medium |
| **S08e ETF 资金流** | BTC/ETH spot ETF 单日净 ≥ $500M / 净出 ≥ $300M | low |

---

## §5.6 鲸鱼地址列表来源 + Tier 分级

### 5.6.1 第一批 100 个鲸鱼来源

| 来源 | 数量 | 链 |
|------|------|----|
| Arkham 公开实体(VC / Fund / 知名个人) | 30 | EVM 主 |
| Nansen Smart Money 标签(部分公开 + 反推) | 20 | EVM |
| Solana 链上历史 PnL Top 200 自筛(过去 365 天) | 30 | SOL |
| GMGN / Cielo 公开鲸鱼榜爬取(去重) | 10 | SOL+EVM |
| 用户 UGC 提交(R48 上线后开放) | - | - |

**反向白名单(必须排除)**:
- DEX router(Jupiter v6 / Raydium / Uniswap Universal Router 等 ≈ 50 地址)
- CEX hot/cold wallet(Binance / Coinbase / OKX / Bybit ≈ 200 地址)
- MEV bot(自建启发式:每日 > 1000 笔 + sandwich 模式 + gas 异常)
- Bridge 合约
- Token deployer / dev wallet

### 5.6.2 Tier 分级标准(动态)

每 24h(04:00 UTC)自动重算所有鲸鱼 tier。

| Tier | 准入标准 | 信号优先级权重 |
|------|---------|---------------|
| **T0** | 历史标杆地址(V神 / Vitalik / 头部 VC):公开实体 + AUM > $50M | × 2.0 |
| **T1** | 过去 90 天 PnL > $500k 且胜率 > 60% 且 ≥ 50 笔 | × 1.5 |
| **T2** | 过去 90 天 PnL > $100k 且胜率 > 55% 且 ≥ 30 笔 | × 1.0 |
| **T3** | 过去 30 天 PnL > $30k 且胜率 > 52%(实验性) | × 0.6 |

**晋降规则**:
- T1 → T2:30 天滚动胜率跌破 55% 或 PnL 跌破 $50k
- T2 → T3:30 天滚动胜率跌破 50%
- T3 → 移除:30 天滚动胜率 < 45% 或活跃度 < 5 笔/30 天
- 升档:连续 60 天满足上一档标准 → 自动晋升

**胜率计算口径**:单笔"胜" = 买入后 24h 内最高价 ≥ 买入价 × 1.05;排除 < $5k 和 > $10M 极端单;排除 stable / WBTC / WETH 之间的 swap。

### 5.6.3 用户自定义(R49 P1)

- 免费用户最多 30 个自定义鲸鱼,付费用户 100 个
- 自定义鲸鱼默认 tier = T2,信号优先级 × 1.0
- 用户可对鲸鱼打分(1-5 星)

### 5.6.4 维护责任

- **数据团队**:每日 04:00 自动重算 + 每周一 review
- **产品**:每月 review,< 50% 跟单胜率的 tier 全档下调或剔除
- **安全**:每周扫新增鲸鱼,识别 MEV / wash trading 异常

---

## §5.7 信号 → 推送 链路

### 5.7.1 总览

```
链上事件 → indexer 解析 → 信号引擎 detect → 信号 enrich(LLM 解释 + 历史相似度)
→ 用户匹配 → 频率控制 → 优先级排序 → 通道选择 → 推送 dispatch → 用户接收 → 信号详情 / CTA
```

### 5.7.2 通道路由规则

| 优先级 | App push | Telegram | Web banner | Email |
|--------|----------|----------|------------|-------|
| critical | ✓(突破免打扰) | ✓ | ✓(顶部) | ✓ |
| high | ✓ | ✓ | ✓ | ✗ |
| medium | ✓(频率限) | 用户开启 | ✓ | ✗ |
| low | ✗ | 用户开启 | ✓ | ✗ |

### 5.7.3 用户场景行为差异

| 场景 | 处理 |
|------|------|
| 用户在 App 前台,正在看相关 token | 信号显示为 inline toast(不推 push) |
| 用户在 App 前台,看其他页 | 顶部 banner + 红点 |
| 用户在后台 < 30min | 仅 high/critical 推 push,medium 攒到下次开 App |
| 用户在后台 > 30min 或 App 关闭 | 按通道路由表 |
| 用户关闭通知 | 仅 Telegram(若开启)+ 下次开 App 看 inbox |

### 5.7.4 免打扰时段

- 默认:22:00-08:00 用户本地时间
- 例外:**critical 信号(用户持仓相关)永不静音**
- 用户可关闭免打扰
- 免打扰期间错过的 high 信号 → 早 8:00 合并发"晨报"

---

## §5.8 信号 → 跟单 完整链路

### 5.8.1 端到端流程

```
T+0s   链上 tx confirmed
T+1s   Helius webhook → 我们的 ingestion
T+2s   parser 提取(token / amount / wallet)
T+3s   去噪(白名单 / 反向白名单)
T+4s   信号引擎规则匹配 → 候选信号
T+5s   enrich:鲸鱼 tier + 历史相似度 + LLM 解释
T+6s   用户匹配 batch(查所有持仓+自选+订阅命中此 token 的用户)
T+7s   频率控制 filter
T+8s   优先级排序
T+9s   通道 dispatch:
        - App push:APNs/FCM
        - Telegram:bot api sendMessage
        - Web:WebSocket push 给在线用户
T+10s  用户收到推送

(用户点击)
T+12s  打开 App / 跳转信号详情页
T+14s  用户点 "一键跟单 $200"
T+15s  POST /api/agent/follow-signal
T+16s  后端 Agent:
        - 校验 signal 未过期(30min 有效)
        - 调用 §6 风控
        - 调用 §3 trade_executor
        - 自动设置 SL/TP
T+18s  风控通过 → broadcast tx
T+22s  tx confirmed → 写 agent_executions
T+25s  推送回执:"✓ 已跟单 $200,均价 ${avg}"

(后续监控)
T+30min ~ 24h:
  - position_monitor 触发 SL/TP
  - 若信号鲸鱼后续卖出 → 反向信号 critical
  - 24h 后回执:"信号复盘:盈/亏 X%"
  - 反哺鲸鱼评分:此次跟单结果加权进鲸鱼胜率
```

### 5.8.2 关键节点 SLA

| 节点 | P50 | P95 | P99 |
|------|-----|-----|-----|
| 链上 → ingestion | 1s | 3s | 8s |
| ingestion → 信号 ready | 2s | 5s | 10s |
| 信号 → 用户推送 | 3s | 8s | 15s |
| 用户点击 → 跟单完成 | 6s | 14s | 30s |
| **端到端 P95** | - | **< 30s** | - |

### 5.8.3 失败场景

| 失败点 | 处理 |
|--------|------|
| Helius webhook 丢包 | 备用 Alchemy + 自有 RPC 拉取 fallback;30s 重试 3 次 |
| LLM 解释超时(> 3s) | 跳过 LLM,用模板硬编码解释 |
| 用户匹配查询慢 | 异步处理,超时 5s 直接 dispatch 默认信号(无个性化) |
| 风控拒绝 | 推送回执"风控拒绝:{原因}",不下单 |
| 链上 tx 失败 | 推送 "tx 失败:{原因},已退还预扣资金" |
| 信号过期(> 30min) | 详情页显示"信号已过期",CTA 灰化 + 提示用户当前价格 |

---

## §5.9 频率控制 + 用户偏好

### 5.9.1 全局频率上限

| 维度 | 默认上限 |
|------|---------|
| 每用户每日总信号数 | ≤ 15 条(免费)/ ≤ 50 条(付费) |
| 每用户每小时 | ≤ 5 条 |
| 每用户同 token 同类信号 | 24h ≤ 1 条 |
| 每用户同鲸鱼信号 | 每日 ≤ 3 条 |
| Telegram/Email 重试 | 1 次 |

### 5.9.2 优先级丢弃规则

当用户达每日上限时,从 low → medium → high 顺序丢弃。**critical 永不丢弃**。

### 5.9.3 同类信号合并

30 分钟窗口内同 token 同类信号 ≥ 2 条 → 合并为一条:
```
🐋 ${token} 30min 内 {n} 条鲸鱼买入信号(累计 ${total},{n_wallets} 鲸鱼)
```

### 5.9.4 用户偏好维度

```json
{
  "signal_preferences": {
    "whale_buy": { "enabled": true, "min_tier": "T2", "min_amount_usd": 50000 },
    "whale_sell_holding": { "enabled": true, "always_critical": true },
    "smart_money_consensus": { "enabled": true },
    "kol_call": { "enabled": false, "min_tier": "T2" },
    "new_token": { "enabled": true, "default_buy_cap_usd": 50 },
    "rugpull_warning": { "enabled": true, "always_critical": true },
    "industry_event": { "enabled": false, "channels": ["banner"] },
    "arbitrage": { "enabled": false }
  },
  "channels": {
    "app_push": true, "telegram": false, "email": false, "web_banner": true
  },
  "quiet_hours": { "enabled": true, "start": "22:00", "end": "08:00", "tz": "user_local" },
  "max_signals_per_day": 15,
  "language": "zh"
}
```

### 5.9.5 智能频率(R49 P1.5)

LLM 根据用户行为调节:
- 用户连续 5 条信号未点击 → 该类型降级 medium → low(自动)
- 用户对鲸鱼 X 信号点击率 > 30% → 该鲸鱼信号优先级 +0.5 tier(个性化)
- 用户 7 天未开 App → 仅 critical 推送

---

## §5.10 给数据团队的 SLA + 数据契约

### 5.10.1 数据契约 D01:链上 tx 解析事件

```
{
  "tx_hash", "chain", "block_height", "block_time",
  "from_address", "to_address",
  "type": "swap | transfer | mint | burn | lp_add | lp_remove | program_upgrade",
  "token_in": { "address", "symbol", "decimals", "amount", "amount_usd" },
  "token_out": { "address", "symbol", "decimals", "amount", "amount_usd" },
  "dex": "raydium | orca | jupiter | uniswap_v3 | sushiswap | pancakeswap",
  "wallet_label": "T0|T1|T2|T3|cex|dex_router|mev_bot|null",
  "raw_data": {...}
}
```

**SLA**:
- 延迟:Solana P95 < 8s / EVM P95 < 15s(L1)/ < 8s(L2)
- 准确率:≥ 99.9%(amount_usd 误差 < 1%)
- 完整性:tx_hash 不丢
- 吞吐:Solana 4000 tps / EVM 全链 1000 tps

### 5.10.2 数据契约 D02:钱包标签查询

```
GET /internal/wallet/{address}
{
  "tier": "T0|T1|T2|T3|null",
  "labels": ["VC", "Fund", "MEV_bot", ...],
  "stats_30d": { "total_pnl_usd", "win_rate", "trade_count", "avg_hold_time_hours" },
  "stats_90d": {...},
  "is_excluded": false
}
```

**SLA**:延迟 P99 < 50ms;准确率 ≥ 99.5%;缓存 5 分钟 TTL

### 5.10.3 数据契约 D03:Token 元数据 + 实时价格

```
{
  "symbol", "name", "decimals",
  "price_usd", "mcap_usd", "liquidity_usd", "volume_24h_usd", "holders_count",
  "dev_wallet", "mint_authority", "freeze_authority",
  "lp_locked_pct": 0.95, "audit_status": "audited | unaudited | rugged"
}
```

**SLA**:延迟 P99 < 100ms;价格刷新 < 5s

### 5.10.4 数据契约 D04:历史相似度查询

```
POST /internal/similar-events
{ "signal_type": "whale_buy", "params": {...} }
=> { "similar_count": 14, "win_count_24h": 9, "win_rate_24h": 0.643, "avg_pnl_24h": 0.087, "lookback_days": 90 }
```

### 5.10.5 数据团队 OKR

| OKR | 指标 |
|-----|------|
| O1 链上 tx 解析准确率 | ≥ 99.9% |
| O2 端到端延迟 | P95 < 30s(R48)→ P95 < 15s(R50) |
| O3 鲸鱼标签覆盖率 | Solana T0-T3 ≥ 5000 / EVM ≥ 10000 |
| O4 鲸鱼 tier 重算稳定性 | 每日 04:00 UTC 完成,跑批 < 30min |
| O5 价格数据准确率 | 与 CoinGecko / DEXScreener 误差 < 1% |

---

## §5.11 信号产品价值度量(KPI)

| 层级 | KPI | R48 目标 | 监控周期 |
|------|-----|---------|---------|
| **触发层** | 信号生成数/天 | 每用户 3-8 条 | 每日 |
| | 信号生成准确率 | ≥ 99.0% | 每日 |
| **送达层** | 推送送达率 | ≥ 98% | 每日 |
| | 推送 P95 延迟 | < 30s | 每分钟 |
| **触达层** | 推送阅读率 | ≥ 30% | 每日 |
| | 信号详情停留 | ≥ 12s | 每日 |
| **转化层** | **信号 CTR** | **≥ 18%** | 每日 |
| | **信号 → 跟单转化率** | **≥ 4%** | 每日 |
| **盈利层** | **跟单 24h 胜率** | **≥ 52%** | 每日 |
| | **跟单 24h 平均 PnL** | **≥ +2%** | 每日 |
| | 信号月度净盈亏 | 正(R48 难,R50 必须) | 每月 |
| **健康层** | 推送投诉率 | < 2%/周 | 每周 |
| | 信号被忽略率 | < 70% | 每周 |
| **个性化层** | 个性化点击率提升 | ≥ +20%(R50) | 每月 |

**信号经济价值**:每条信号期望盈利(EV)= 跟单转化率 × 平均跟单金额 × 平均 24h PnL%。R48 目标 EV ≥ +$0.30/信号(日均 5 信号 = $1.5/用户/日)。

**鲸鱼/KOL 评分反哺**:每次跟单结果(成功/失败)→ `whale_follow_outcomes` 表 → 每日批跑 → 修正鲸鱼 tier。

---

## §5.12 验收标准(R48 上线必达)

- [ ] 6 类信号端到端打通
- [ ] 每类信号至少 3 个子场景上线
- [ ] 鲸鱼标签库 Solana ≥ 5000 / EVM ≥ 10000
- [ ] 鲸鱼 tier 自动重算 cron 每日 04:00 UTC 完成
- [ ] 推送通道:App push + Telegram + Web banner 三通道全通
- [ ] 信号 → 跟单端到端 < 30s P95
- [ ] 信号详情页(含鲸鱼历史 + 历史相似度 + LLM 解释)
- [ ] 用户偏好页(8 类信号开关 + tier 阈值 + 频率上限 + 免打扰)
- [ ] 频率控制规则全部生效
- [ ] **老鼠仓(critical)永不被免打扰静音 — 必测**
- [ ] 风控集成:跟单走 §6 全部 hook
- [ ] 反馈闭环:24h 后跟单复盘自动推送

### 验收测试用例(关键 10 条)

| ID | 测试 | 预期 |
|----|------|------|
| AT01 | T1 鲸鱼 $100k 买入 → 推送送达 | < 30s,弹窗含完整模板字段 |
| AT02 | 持仓用户该 token 出现卖出 → critical 推送 | 突破免打扰,通道齐推 |
| AT03 | 同 token 30min 内 3 条鲸鱼信号 → 合并 | 合并成 1 条 |
| AT04 | 每用户每日第 16 条信号(low) | 被丢弃,不送达 |
| AT05 | 用户点跟单 → 风控通过 → tx 成功 | < 30s 完成 |
| AT06 | 用户点跟单 → 风控拒绝 | 推送拒绝原因,不下单 |
| AT07 | 信号过期 30min → CTA 灰化 | 灰化 + 提示当前价 |
| AT08 | 鲸鱼地址在反向白名单(MEV bot) | 不触发信号 |
| AT09 | 新币 dev 抛售 10% → critical 推送给持仓用户 | 突破免打扰 |
| AT10 | 跟单 24h 后复盘 → 自动推送 | 含盈亏 % + 鲸鱼后续动作 |

---

## §5.13 监控埋点

### 5.13.1 必埋点事件(前端)

| 事件名 | 触发 | 字段 |
|--------|------|------|
| `signal_received` | 客户端收到推送 | signal_id, type, tier, channel |
| `signal_pushed` | 后端发出 | signal_id, type, tier, channel, user_id |
| `signal_opened` | 用户点击 | signal_id, channel, time_to_open_ms |
| `signal_detail_view` | 详情页打开 | signal_id, view_duration_ms |
| `signal_cta_click` | CTA 点击 | signal_id, cta_type, amount_usd |
| `signal_follow_submit` | 提交跟单 | signal_id, amount_usd |
| `signal_follow_success` | 跟单 tx 成功 | signal_id, tx_hash, amount_usd, slippage |
| `signal_follow_fail` | 跟单失败 | signal_id, fail_reason |
| `signal_dismiss` | 用户忽略 | signal_id, dismiss_action |
| `signal_unsubscribe` | 用户关闭通知 | signal_type |

### 5.13.2 后端 metrics(Prometheus)

```
signal_generated_total{type, tier, chain}
signal_filtered_total{type, reason}
signal_pushed_total{type, tier, channel}
signal_push_failed_total{type, channel, reason}
signal_push_latency_seconds{type, channel}  # histogram
signal_cta_click_total{type, cta_type}
signal_follow_total{type, outcome}
signal_follow_pnl_24h{type}  # gauge,后处理
user_signal_unsubscribe_total{type}
user_signal_per_day{user_id}  # gauge
```

### 5.13.3 告警规则

| 告警 | 条件 | 严重度 |
|------|------|--------|
| 信号生成异常下降 | 1h 内信号数 < 过去 7 天同时段中位数 × 30% | P1 |
| 推送 P95 延迟超标 | 5 分钟内 P95 > 60s | P1 |
| 推送失败率高 | 5 分钟内失败率 > 5% | P1 |
| 跟单失败率高 | 1h 内 follow_fail / follow_total > 20% | P0(可能链上事故) |
| 鲸鱼数据上游中断 | Helius webhook 5 分钟无数据 | P0 |
| 信号 → 跟单转化率骤降 | 24h 移动平均 < 2%(目标 4%) | P2 |
| 用户 unsubscribe 激增 | 1h > 100 用户关 | P1 |

---

## 附录 A:与其他模块的依赖

| 依赖模块 | 依赖关系 |
|---------|---------|
| §3 交易引擎 | 跟单 → trade_executor.execute_trade(user_id 透传) |
| §6 风控 | 跟单前 HR01 max_position / kill switch / geo / 滑点 |
| §4 持仓监控 | 跟单后 position_monitor 接管 SL/TP |
| §7 用户体系 | 用户偏好读写 / user_id 鉴权 |
| §8 算力 | 信号详情页 LLM 解释扣 credit |
| §9 数据团队 | 全部数据契约 D01-D05 |

## 附录 B:术语

- **鲸鱼(Whale)**:链上有标签的高净值/高胜率地址
- **聪明钱(Smart Money)**:Top 200 钱包(每周重算)
- **共识(Consensus)**:多个独立钱包同时段同方向
- **CTR**:推送点击率
- **EV**:每条信号期望盈利
- **SVS**:Signal Value Score 北极星指标
- **Tier**:鲸鱼分级(T0-T3)
- **持仓相关(holding-related)**:用户当前持有该 token 的信号
# §6 风控阻断 — 详细规格(R48)

---

## §6.0 模块定位 + 北极星指标

### §6.0.1 模块定位

**风控阻断**是 Agent Trading 平台**用户花钱前**的最后一道防线。它的存在不是为了"提供安全感",而是为了**精确拦截那些我们已经知道会赔钱的交易**。

**位置**:
```
[用户输入意图] → [LLM Parser 解析] → [订单参数生成] → 【§6 风控 5 道筛】 → [上链 / DEX 路由] → [Position Monitor]
```

意图阶段不做风控(用户随便聊),链上确认后做仓位监控(§7)。

### §6.0.2 三个核心承诺

1. **明显的雷必须拦下**:OFAC 制裁地址 / 公认蜜罐 / 流动性 < $5k 的 token,产品 100% 阻止
2. **拦截原因 100% 透明**:不说"该 token 风险过高",说"top 10 地址持仓 92%,中心化风险高"
3. **误报不超过 2%**:被强阻断的交易里,事后证明是合法机会的不超过 2%

### §6.0.3 北极星指标

| 指标 | 目标 | 测量方式 |
|------|------|----------|
| **拦截命中率** | ≥ 95% | 被强阻断的 token,30 天内确认是 rug/honeypot 的比例 |
| **误报率** | ≤ 2% | 被强阻断的交易,用户事后申诉证明是合法机会的比例 |
| **风控延迟 P95** | ≤ 1000ms | 5 道筛全跑 |
| **OFAC 命中漏报** | 0 | 法务底线 |
| **用户感知保护额** | > $X | 风控阻断的交易金额累计(展示在用户主页) |
| **GoPlus API 命中率** | ≥ 80% | 拦截原因 80% 能在 GoPlus 上交叉验证 |

### §6.0.4 反指标(防止过度风控)

| 反指标 | 阈值 |
|--------|------|
| **强阻断率** | ≤ 8% |
| **强警告通过率** | ≥ 60% |
| **风控引发的用户流失** | ≤ 3% |

---

## §6.1 用户故事(8 个)

**US-6.1 OFAC 制裁地址直接拦截**:token deployer 在 OFAC SDN 名单 → 100% 拦截 + "该地址受美国财政部制裁"

**US-6.2 蜜罐 token 强阻断**:模拟卖出 + 字节码扫描 + 历史卖单成功率三重验证 → "这个 token 你能买,但买完卖不出"

**US-6.3 高税率 WARN_HARD**:卖出税 12% → 双重确认:"这个 token 卖出要扣 12%,即使涨 15% 你也只赚 3%"

**US-6.4 流动性过低强阻断**:$5000 单进 $3k 池子 → "下单 $5000 会被滑点吃掉 80%"

**US-6.5 集中度过高 WARN_HARD**:top 10 88%、最大单地址 47% → 强警告

**US-6.6 风控保护历史可查**:主页"过去 30 天产品为你拦截 7 次,预估保护资金 $3,847"

**US-6.7 误报投诉路径**:任意 REJECT 弹窗都有"申诉"按钮,24h 内人工 review

**US-6.8 风控规则透明**:点"为什么阻断" → 看完整检测过程("GoPlus is_honeypot=1 / 字节码 transferOwnership 后 owner 改 sellTax 到 99% / 历史卖单成功率 12%")

---

## §6.2 产品边界

### §6.2.1 在范围内

- ✅ 5 道筛(黑名单 / 蜜罐 / 高税 / 低流动性 / 集中度)在订单上链前执行
- ✅ 三级拦截(REJECT / WARN_HARD / WARN_SOFT)
- ✅ 拦截原因透明展示 + UI 文案
- ✅ 风控保护历史(用户主页可查)
- ✅ 误报申诉(24h 人工 review)
- ✅ OFAC + Chainalysis + GoPlus + 我们自维护 4 大数据源整合
- ✅ 风控延迟 P95 ≤ 1000ms
- ✅ AML 大额跨链记录(不阻断,记录留痕)

### §6.2.2 不在范围内

- ❌ 已上链订单的事后撤销(链上不可逆)
- ❌ Smart Contract 漏洞审计(不替 Quantstamp 做)
- ❌ 价格预测 / 是否会涨(Agent 决策的事)
- ❌ 用户私钥被盗的检测(§3 钱包安全)
- ❌ DEX 自身的安全性评估(假设 Jupiter / 1inch 安全)
- ❌ 跨链桥风险评估(§4 跨链)

---

## §6.3 竞品全景对比表(8 竞品 × 10 维度)

| 竞品 | 主要检测维度 | 检测方法 | 准确率(蜜罐) | 实时性 | API 成本 | 限速 | 链支持 | 已知缺陷 | 是否被钱包集成 | 我们用不用 |
|------|-------------|---------|---------------|--------|----------|------|--------|---------|---------------|-----------|
| **GoPlus Security** | Token 安全(蜜罐/税/owner)+ NFT + 钓鱼地址 + 钱包地址 | 模拟交易 + 字节码扫描 + 链上历史 + 黑名单 | ~92%(社区交叉验证) | < 5s 同步检测 | 免费 30 QPS,付费 $99/月起 100 QPS | 免费 30K/天 | EVM 全链 + Solana(2024 加) | Solana 检测较弱 / 新 token 0-30 分钟检测延迟 / 偶有误报新 LP | Phantom / OKX / Trust / SafePal / Bitget | ✅ 主力 |
| **TokenSniffer** | Honeypot + Owner control + Liquidity locked + Holder | 字节码扫描 + 静态分析 + 模拟 | ~85% | 几分钟(需扫描完成) | 付费 $200/月 起 | 100 QPS | 仅 EVM | Solana / 新链不支持 / 评分主观 | Etherscan(部分) | ✅ 备份 |
| **De.Fi Scanner** | Risk Score 0-100 + Honeypot + 24 维度子分数 | 多源聚合 + 模拟 + AI 评分 | ~88% | 秒级 | 免费 + Premium $50/月 | 60 QPS | EVM 多链 + Solana(部分) | 评分黑盒 / 子分数权重不公开 | 部分钱包 | ⚠️ 参考 |
| **Honeypot.is** | 专门蜜罐(模拟买卖) | 模拟交易(eth_call simulate buy → simulate sell) | ~95%(蜜罐专项最高) | < 3s | 免费(开放 API) | 5 QPS | EVM(eth/bsc/base) | 不支持 Solana / 仅做蜜罐 / 限速低 | 少 | ✅ 蜜罐专项备份 |
| **Chainalysis** | OFAC 制裁地址 + AML + Mixer 关联 + 黑钱来源 | 链上 graph 分析 + KYC 数据 + 制裁名单 | OFAC 100% / AML 估计 ~75% | OFAC 实时 / AML 几小时 | 企业付费 $XX,XXX/年 起 | 协商 | 全链 | 贵 / 不卖小客户 | 大型 CEX / 银行 | ⚠️ 仅 OFAC 公开数据 |
| **Etherscan/Solscan Label** | 社区维护标签(scam / phishing / contract) | 人工 + 用户报告 + 算法 | ~70%(社区延迟) | 几小时 - 几天 | 免费 + Pro $200/月 | 5-100 QPS | 仅自家链 | 延迟高 / 标签不全 | 各种 explorer | ✅ 标签数据源 |
| **Forta Network** | 链上实时威胁监测 | 检测器网络 + 链上事件订阅 | N/A | 链上确认即出 alert | 免费 + Pro 付费 | API 限流 | EVM 主流链 | 监测向不是检测向 | 不直接 | ⚠️ 监测后续 |
| **Quantstamp / CertiK** | 合约审计 + Skynet 评分 | 人工审计 + 自动化 + 链上监控 | 审计通过率不等于 100% 安全 | 审计周期数周 / Skynet 实时 | 审计 $$$$$ / API 协商 | 协商 | 多链 | 审计过的还是 rug 过 | CertiK 有官网评分 | ⚠️ 仅参考评分 |

### §6.3.2 GoPlus token_security 关键字段(我们处理)

我们关心的字段(GoPlus 返回 JSON,值 "1" = 是 / "0" = 否 / "" = 未知):

| 字段 | 含义 | 我们的处理 |
|------|------|----------|
| `is_honeypot` | 是不是蜜罐 | "1" → 强阻断 |
| `honeypot_with_same_creator` | 同 creator 之前发过蜜罐 | "1" → 强警告 |
| `transfer_pausable` | 可暂停转账 | "1" → 强警告 |
| `cannot_buy` | 不能买 | "1" → 强阻断 |
| `cannot_sell_all` | 不能全部卖出 | "1" → 强警告 |
| `slippage_modifiable` | 滑点可改 | "1" → 强警告 |
| `personal_slippage_modifiable` | 单地址滑点可改 | "1" → 强阻断 |
| `is_blacklisted` | 有黑名单功能 | "1" → 弱警告 |
| `is_whitelisted` | 有白名单功能 | "1" → 弱警告 |
| `is_anti_whale` | 反巨鲸限制 | "1" → 弱警告 |
| `trading_cooldown` | 交易冷却 | "1" → 弱警告 |
| `is_mintable` | 可增发 | "1" → 强警告 |
| `owner_change_balance` | owner 可改任意地址余额 | "1" → 强阻断 |
| `hidden_owner` | 隐藏 owner | "1" → 强警告 |
| `selfdestruct` | 合约可自毁 | "1" → 强警告 |
| `external_call` | 转账时调用外部合约 | "1" → 弱警告 |
| `gas_abuse` | gas 滥用 | "1" → 弱警告 |
| `buy_tax` | 买入税 | 见 §6.8 分级 |
| `sell_tax` | 卖出税 | 见 §6.8 分级 |
| `holder_count` | 持有人数 | < 100 弱警告 |
| `holders` | top 10 持有详情 | 见 §6.10 集中度 |
| `lp_holder_count` | LP 持有人数 | < 5 警告 |
| `lp_holders` | LP top 10(含 is_locked) | 见 §6.10 |
| `creator_address` / `creator_balance` / `creator_percent` | 部署者信息 | > 30% 警告 |
| `owner_address` / `owner_balance` / `owner_percent` | owner 信息 | 0x0 = 弃权(好) |
| `note` | GoPlus 备注 | 显示给用户 |
| `trust_list` | 是不是 GoPlus 信任白名单 | "1" → 跳过强阻断 |

### §6.3.3 GoPlus 已知缺陷与对策

| 缺陷 | 对策 |
|------|----------|
| 新 token 0-30 分钟可能没数据 | 没数据时降级到 Honeypot.is + 我们自有字节码扫描 |
| Solana 检测覆盖弱 | Solana 用 GoPlus 优先 + 我们自己模拟 + Birdeye/Dexscreener cross check |
| 偶发误报合法新 LP | WARN_HARD 而非 REJECT,且支持申诉 |
| 限速 30 QPS 免费层不够 | 付费层 $99/月 100 QPS + Redis 缓存 5 分钟 |
| token 数据 5 分钟内不变(GoPlus 内部缓存) | 我们自己再加模拟卖出补足 |

---

## §6.4 我们的差异化

如果只接 GoPlus,我们就是 Phantom 的复刻。我们的差异化:

1. **5 道筛串行执行,每道筛有 fallback 数据源**:GoPlus 没数据 → Honeypot.is → 我们自己模拟 → 拒绝(默认拒)
2. **强阻断 vs 强警告 vs 弱警告 三级精确分级**
3. **拦截原因 100% 透明**:点击"为什么"看到完整规则触发链
4. **风控保护历史可查**:用户主页"产品为你拦截 7 次,保护 $3,847"
5. **误报申诉 24h SLA**:不像 Etherscan 标签错了几周才改
6. **AI Agent 上下文感知**:用户说"激进抄底"和"稳健 DCA",同一个 token 的风控阈值可以不同

### 与单纯钱包风控(Phantom 等)的关键区别

| 维度 | 钱包风控 | 我们的 Agent 风控 |
|------|----------|-------------------|
| 触发时机 | 用户点"签名"前 | 用户说出意图就开始 |
| 决策权 | 用户自己 | Agent 替用户决策(更高责任) |
| 风险偏好 | 用户固定 | 可基于用户上下文(激进/稳健)动态调整 |
| 拦截严厉度 | 警告为主 | 强阻断为主(因为 Agent 替用户开火) |
| 历史记录 | 不展示 | 主页可见保护历史 |
| 法律责任 | 钱包是中介 | Agent 是替执行,责任更重 |

---

## §6.5 5 道筛执行顺序 + 性能预算

### §6.5.1 总执行流(顺序)

```
[订单参数生成完成]
   ↓
[筛 1] 黑名单(预期 50ms,本地 Redis 缓存)
   ↓ (命中 OFAC → 立即 REJECT)
[筛 2] 蜜罐(预期 400ms,GoPlus + 模拟,并发执行)
   ↓ (命中蜜罐 → REJECT)
[筛 3] 高税率(预期 80ms,从筛 2 的 GoPlus 复用)
   ↓ (税 > 30% → REJECT,> 10% → WARN_HARD)
[筛 4] 极低流动性(预期 200ms,DEX router quote + Birdeye)
   ↓ (< $5k → REJECT)
[筛 5] 集中度(预期 200ms,从筛 2 的 GoPlus 复用 + 链上查 top10)
   ↓
[结果聚合 + 决策]
   ↓
[返回:PASS / WARN_SOFT / WARN_HARD / REJECT]
```

### §6.5.2 性能预算(P95)

| 筛 | 预算(P95) | 理由 |
|----|-----------|------|
| 筛 1 黑名单 | 50ms | Redis 内存查找 + bloom filter |
| 筛 2 蜜罐 | 400ms | GoPlus API ~ 200ms + 模拟交易 ~ 300ms 并发 |
| 筛 3 税率 | 80ms | 从筛 2 GoPlus 缓存读 |
| 筛 4 流动性 | 200ms | DEX router quote ~150ms + Birdeye 50ms 并发 |
| 筛 5 集中度 | 200ms | 大部分从 GoPlus 复用,部分 Solana 链调用 |
| **合计 P95** | **930ms** | 串行 50+400+80+200+200 |

实际通过并发可压到 600ms。

### §6.5.3 失败兜底

| 场景 | 处理 |
|------|------|
| 筛 1 Redis 挂 | fallback 到内存副本 + 报警,继续后续筛 |
| 筛 2 GoPlus 超时 5s | fallback Honeypot.is + 模拟交易 |
| 筛 4 Birdeye 失败 | fallback Dexscreener |
| 全部数据源失败 | 默认 REJECT(safety first)+ 报警 + 用户提示 |

### §6.5.4 缓存策略

| 数据 | 缓存层 | TTL | 失效策略 |
|------|-------|-----|---------|
| OFAC 名单 | Redis Set | 24h | 每天 02:00 拉取 |
| GoPlus token_security | Redis Hash | 5min | LRU 淘汰 |
| 流动性数据 | Redis | 60s | 高频更新 |
| 集中度 top10 | Redis | 5min | LRU |
| 蜜罐自维护 | Postgres + Redis | 1h | 用户报告触发即时更新 |

> **注**:这些缓存是**风险数据/标签**而非市场价格,与 §1.7 价格不缓存铁律不冲突。

---

## §6.6 筛 1 — 黑名单(精确数据源 + 检测规则 + 实时性)

### §6.6.1 数据源整合

| 数据源 | 覆盖 | 实时性 | 接入成本 | 我们的接入方式 |
|--------|------|-------|---------|---------------|
| **OFAC SDN List** | 全球美国制裁地址(法务底线) | 每天 1 次拉取 | 免费 | 我们自己 cron 拉 + parse + Redis 持久化 |
| **Chainalysis Sanctions API** | 链上扩展制裁(混币器关联等) | 实时 | 企业付费 $XX,XXX/年 | 暂不接,V1.5 评估;现阶段用 Chainalysis 公开 oracle 合约(免费查询) |
| **GoPlus 黑名单** | 钓鱼 + Mixer + 公认 scam | 5 分钟刷新 | 免费 30 QPS | API 调用 |
| **我们自维护黑名单** | 用户报告 + 内部 review | 4h SLA | 自建 | Postgres 表 `risk_blacklist` |
| **Etherscan / Solscan label** | 社区维护(phishing / scam) | 几小时 - 几天 | 免费 + Pro $200/月 | 周扫描同步 |
| **Forta Bot 输出**(选) | 链上实时威胁 | 链上确认即出 | 免费 | V1.5 评估 |

### §6.6.2 检测维度(对哪些地址查)

订单中所有相关地址都要查:
1. **Token 合约地址**(必查)
2. **Token deployer / creator 地址**(必查)
3. **Token owner 地址**(必查)
4. **Pool 合约地址**(必查)
5. **Pool 的 LP top 1 地址**(查,但只警告不强阻断)

### §6.6.3 命中规则

| 命中场景 | 决策 | 文案 |
|---------|------|------|
| Token / deployer / owner 任一命中 OFAC | **REJECT** | "该 token 的 [deployer / owner / 合约] 地址受美国财政部 OFAC 制裁,无法交易" |
| Chainalysis sanction oracle 返回 true | **REJECT** | "该地址被识别为受制裁地址" |
| GoPlus address_security 返回 phishing/blacklist=1 | **REJECT**(若是合约)/ **WARN_HARD**(若是辅助地址) | "该地址被 GoPlus 标记为 [钓鱼 / 黑名单]" |
| 自维护黑名单(scam_confirmed) | **REJECT** | "该 token 已被用户报告为诈骗,平台已确认" |
| 自维护黑名单(scam_suspected) | **WARN_HARD** | "该 token 被多名用户报告为可疑" |
| Etherscan/Solscan label 含 "phishing/scam/exploit" | **WARN_HARD** | "Etherscan 社区将该地址标记为 [phishing / scam]" |

### §6.6.4 OFAC 拉取细节

```
来源:https://www.treasury.gov/ofac/downloads/sdn.xml
   + https://www.treasury.gov/ofac/downloads/sdnlist.txt(纯文本备份)
   + https://www.treasury.gov/ofac/downloads/cons_advanced.xml
频率:每天 02:00 UTC + 美东时间 09:00 双拉
解析:提取所有 <digital currency> 类型的 ID,匹配出加密地址
存储:Redis Set `ofac:sanctioned_addresses` + Postgres 表 `ofac_history`(留 1 年审计)
报警:拉取失败 / 解析地址数变化 > 20% → PagerDuty
```

---

## §6.7 筛 2 — 蜜罐(6 子检测 + 误报兜底)

### §6.7.1 6 子检测概览

| 子检测 | 优先级 | 数据源 | 输出 |
|--------|--------|--------|------|
| §6.7.2 模拟卖出 | 必须 | eth_call simulate / Solana simulate | success/fail |
| §6.7.3 字节码扫描 | 必须 | 链上 bytecode + 黑名单 opcode 序列 | 命中规则数 |
| §6.7.4 历史卖单成功率 | 必须 | 24h 链上 swap 历史 | 成功率 % |
| §6.7.5 Owner 权限检测 | 必须 | GoPlus + 我们字节码 | owner 能改什么 |
| §6.7.6 Mint 权限检测 | 必须 | GoPlus `is_mintable` + 字节码 | 可否增发 |
| §6.7.7 Pause 权限检测 | 必须 | GoPlus `transfer_pausable` + 字节码 | 可否暂停 |

### §6.7.2 模拟卖出(子检测 1)

#### EVM 链(eth/bsc/base/arbitrum/optimism)

```
方法:eth_call(state override)
步骤:
  1. 假装我们的检测地址 0xDEAD...beef 拥有 1e18 wei 的目标 token(state override)
  2. 用 eth_call 模拟 router.swapExactTokensForETH(amountIn=1e18, amountOutMin=0, path=[token, WETH], to=0xDEAD..., deadline=now+600)
  3. 如果 revert 或 amountOut < 期望的 50% → 标记 honeypot
  4. 如果 success 且 amountOut > 50% → 通过

链支持:eth / bsc / base / arbitrum / optimism / polygon
工具:alchemy/quicknode 的 eth_call with state override
延迟:每次 ~ 250ms
失败兜底:Honeypot.is API
```

#### Solana 链

```
方法:Solana simulate transaction
步骤:
  1. 构造一个 swap instruction(我们 → SOL)用 Jupiter quote
  2. simulateTransaction 不真发
  3. 检查 logs 是否有 "Transfer" 失败或 program error
  4. 检查 simulation 返回的 token balance 变化是否符合预期

工具:Solana RPC simulateTransaction with sigVerify=false
延迟:每次 ~ 200ms
失败兜底:用 dev wallet 真发 0.001 SOL 的最小卖出尝试 + 立即买回(成本 ~ $0.005)
```

#### 模拟卖出失败的判断

| 模拟结果 | 判断 |
|---------|------|
| revert with "transfer failed" / "INSUFFICIENT_OUTPUT" | 强蜜罐 → REJECT |
| revert with "blacklisted" / "trading not enabled" | 蜜罐变种 → REJECT |
| success 但 amountOut < 期望 50%(高税) | 高税 → 走筛 3 |
| success 且 amountOut ≥ 期望 50% | 通过 |
| RPC 超时 / 节点错误 | 切换 RPC + 重试 1 次,仍失败 → fallback Honeypot.is |

### §6.7.3 字节码扫描(子检测 2)

#### 检测目标(EVM)

我们维护一个**已知蜜罐 opcode 序列黑名单**,通过反汇编合约 bytecode 比对。

#### 黑名单 opcode 序列

| 序列名 | opcode pattern | 含义 | 误报率 |
|--------|---------------|------|-------|
| `tx.origin == owner` 限制卖出 | `0x32 ... EQ ... JUMPI` | 只有 owner 能卖 | < 1% |
| `from != owner && to == pair` revert | `CALLER ... EQ ... ISZERO ... JUMPI ... REVERT` | 只 owner 卖给 pair | < 5% |
| `_taxFee >= 30` 或 `setTax > 30` 路径 | LIT > 30 + SSTORE 到 fee slot | 高税方法存在 | 10%(误报因为正常税设置) |
| `_isExcludedFromFee[from] = true` 后变化 | 配合时间戳 | owner 给自己免税但用户全税 | 8% |
| 含 `selfdestruct` | `0xff` (SELFDESTRUCT) | 合约可自毁 | 5%(老合约保留) |
| `_pause()` 或 `Pausable` | EQ to known pausable selector | 可暂停 | 30%(很多 OZ 合约都有,所以只警告) |

#### 实现

```
方法:web3.eth.getCode(token_addr) → bytecode
工具:python eth-abi + 自写反汇编器 + 黑名单 pattern matcher
延迟:200ms(本地计算)
误报兜底:
  - 字节码扫描结果只作为辅助 signal
  - 与模拟卖出 + 历史卖单成功率三者交叉验证
  - 任意 2 项命中 → REJECT;只 1 项命中 → WARN_HARD
```

**Solana**:V1 暂不做 Solana 字节码扫描(BPF 复杂度高),依赖模拟 + GoPlus + 历史卖单成功率三角验证。

### §6.7.4 历史卖单成功率(子检测 3)

```
取过去 24h(或最近 100 笔,取多者)该 token 的所有 swap 交易:
  - sold_count_total = 卖单总数
  - sold_count_success = 成功卖单数(实际收到 base token)
成功率 = sold_count_success / sold_count_total

数据源:
  EVM:Alchemy / The Graph subgraph(Uniswap/Sushi)
  Solana:Birdeye API / Helius enhanced transactions

阈值:
  > 95%:正常
  85-95%:WARN_SOFT(可能高失败网络拥堵)
  60-85%:WARN_HARD(疑似软蜜罐)
  < 60%:REJECT(强蜜罐 90% 概率)

样本不足兜底:
  < 20 笔历史卖单 → 跳过此子检测,不作判定
```

**边界情况**:
- 新 token < 1 小时:历史样本必定不足,跳过
- 高频 meme 大量小额 dust 交易:加权(只算 > $10 的卖单)
- 用户自己 wallet 测试卖单失败:从样本剔除

### §6.7.5 Owner 权限检测(子检测 4)

| 权限项 | GoPlus 字段 | 决策 |
|--------|-------------|------|
| Owner 可改税 | `slippage_modifiable` | 强警告 |
| Owner 可改单地址税 | `personal_slippage_modifiable` | 强阻断(典型蜜罐变种) |
| Owner 可改任意余额 | `owner_change_balance` | 强阻断 |
| Owner 可暂停转账 | `transfer_pausable` | 强警告 |
| Owner 可加黑名单 | `is_blacklisted` | 弱警告 |
| Owner 是合约(可升级) | 字节码 detect proxy pattern | 弱警告 |
| Owner 已弃权(0x0) | `owner_address == 0x0...0` | 加分(降级警告) |

### §6.7.6 Mint 权限检测(子检测 5)

```
GoPlus 字段:is_mintable
我们字节码扫描:找 mint() / _mint() 函数 + onlyOwner 修饰

决策:
  is_mintable = "1" 且 max supply 有限制 → 弱警告
  is_mintable = "1" 且 无限增发 → 强警告
  字节码有隐藏 mint(GoPlus 没标但我们扫到) → 强阻断 + 加自维护黑名单
```

### §6.7.7 Pause 权限检测(子检测 6)

```
GoPlus 字段:transfer_pausable
含义:owner 可在任意时刻暂停所有转账,用户买完无法卖

决策:
  transfer_pausable = "1" → 强警告(双重确认)
  + 检查最近 30 天有没有 pause 历史(如果 pause 过 → 强阻断)
```

### §6.7.8 6 子检测聚合规则

```python
def aggregate_honeypot(results):
    # 任一硬命中 → REJECT
    if results.simulate_sell == "HONEYPOT":
        return REJECT, "模拟卖出失败:[具体 revert reason]"
    if results.bytecode_scan.matches >= 2:
        return REJECT, f"字节码扫描命中 {N} 项可疑 pattern"
    if results.history_success_rate < 0.6 and results.sample_size >= 20:
        return REJECT, f"过去 24h 卖单成功率仅 {X}%"
    if results.owner_can_change_personal_slippage:
        return REJECT, "Owner 可单独修改你的卖出税(典型蜜罐变种)"
    
    # 两项软命中 → WARN_HARD
    soft_hits = count(history_success_rate < 0.85, owner_can_pause, owner_can_change_tax, is_mintable_unlimited)
    if soft_hits >= 2:
        return WARN_HARD, "多项可疑 signal:[X / Y / Z]"
    if soft_hits == 1:
        return WARN_SOFT, "[具体项]"
    
    return PASS
```

---

## §6.8 筛 3 — 高税率(精确分级)

### §6.8.1 数据源

主:GoPlus `buy_tax` 和 `sell_tax`(模拟交易测得)
辅助:我们自己的模拟交易对比 amountOut 和无税情况的差距

### §6.8.2 精确分级

#### 买入税(buy_tax)

| 税率 | 决策 | 文案 |
|------|------|------|
| 0-3% | PASS | 无 |
| 3-10% | WARN_SOFT | "买入税 X%,会立即扣减你的本金" |
| 10-30% | WARN_HARD | "买入税 X%,买入即损失 X% 本金,确认?" |
| > 30% | **REJECT** | "买入税 > 30%,该 token 极可能是蜜罐变种" |

#### 卖出税(sell_tax)

| 税率 | 决策 | 文案 |
|------|------|------|
| 0-3% | PASS | 无 |
| 3-10% | WARN_SOFT | "卖出税 X%,卖出会扣 X%" |
| 10-30% | WARN_HARD | "卖出税 X%,即使涨 50% 你净赚 < (50-X)%。确认?" |
| > 30% | **REJECT** | "卖出税 > 30%,事实上接近蜜罐" |

#### 总税(buy + sell)

| 总税 | 决策 |
|------|------|
| > 50% | **REJECT** |
| 30-50% | **WARN_HARD** |
| 15-30% | WARN_SOFT |
| < 15% | 看单项 |

### §6.8.3 阈值依据

- **30% 强阻断**:行业实证,超过 30% 单边税的 token 90% 是蜜罐变种
- **10% 强警告**:链上学界共识,正常 reflection token / 增长基金通常 5-10%,> 10% 异常
- **3% 弱警告**:大多数合规 meme 是 0-3%,> 3% 应让用户知情

### §6.8.4 检测方法精确

```
1. 调用 GoPlus token_security,拿 buy_tax 和 sell_tax
2. 我们自己 simulate buy + simulate sell:
   - simulate buy 100 USDC → 收到 X token
   - simulate sell X token → 收到 Y USDC
   - 实测 round-trip loss = (100 - Y) / 100
   - implied_total_tax = round-trip loss(扣除 0.3% LP 手续费 × 2 后)
3. 如果 GoPlus 报 buy_tax + sell_tax 与我们实测差 > 5 个百分点 → 取较大者(safety first)
4. 特殊处理:某些 token 大单超额税(如卖出 > total supply 0.5% 触发 99% 税)
   - 用我们 dry-run 卖单的实际单量比例做加权
```

---

## §6.9 筛 4 — 极低流动性(按 token 类型分级)

### §6.9.1 流动性的精确定义

我们用 **可执行流动性**,不是 TVL:
```
可执行流动性 = pool reserve_base × 2(双边定价)
针对用户实际下单金额的滑点换算:
  effective_liquidity_for_order = pool reserve_base × (1 - slippage_tolerance)
```

不要用 Dexscreener 的 "Liquidity" 字段(有时含锁仓 LP)。

### §6.9.2 数据源

| 数据源 | 用途 | 优先级 |
|--------|------|-------|
| **DEX router quote**(eth/bsc/base 用 Uniswap router / Solana 用 Jupiter) | 真实可成交量 + 滑点 | 主 |
| **Birdeye API**(Solana) | pool TVL + holder 数 | 主(Solana) |
| **Dexscreener API** | pool TVL 多链 | 备用 |
| **GoPlus lp_holders** | LP 锁仓状态 | 辅 |

### §6.9.3 按 token 类型分级阈值

| Token 类型 | < REJECT | < WARN_HARD | < WARN_SOFT |
|---|---|---|---|
| **类型 1 Stablecoin**(USDC/USDT/DAI) | $5k | $20k | $100k |
| **类型 2 大盘 Token**(mcap > $100M) | $10k | $50k | $200k |
| **类型 3 中盘 Token**($10M-$100M) | $5k | $20k | $100k |
| **类型 4 Meme/小盘**(< $10M) | $3k | $10k | $50k |
| **类型 5 Brand new**(< 1 小时) | $2k | $5k | $20k |

### §6.9.4 用户单量与流动性匹配(动态阈值)

除了池子绝对值,还要看**用户单量占池子的比例**:

```
order_to_pool_ratio = user_order_usd / pool_liquidity_usd

ratio > 5%:WARN_SOFT(滑点 > 1%)
ratio > 10%:WARN_HARD(滑点 > 5%)
ratio > 20%:REJECT(滑点 > 15%,基本被 sandwich)
```

不论 token 类型,这条都生效。

### §6.9.5 LP 锁仓加分(降级警告)

如果 LP top 1 是 lock contract(uncx / team finance / unicrypt),且 lock 时间 > 90 天:

```
原 WARN_HARD → 降为 WARN_SOFT
原 WARN_SOFT → 降为 PASS
原 REJECT → 仍 REJECT(锁仓不能补救池子太小)
```

### §6.9.6 阈值依据

- **$5k 强阻断**:链上历史显示 < $5k 池子的 token 90 天内 80% 进入死亡螺旋
- **滑点 5% / 15%**:meme 交易圈共识,> 5% 不亏不可能
- **token 类型分级**:阈值的核心,因为同样 $50k 流动性,大盘是死的,meme 是活的

---

## §6.10 筛 5 — 集中度过高(top10 / 单地址 / LP locked)

### §6.10.1 检测维度

#### Top 10 Holder 总持仓

| 占比 | 决策 |
|------|------|
| > 95% | REJECT(≈ 完全中心化) |
| 85-95% | WARN_HARD |
| 70-85% | WARN_SOFT |
| < 70% | PASS |

#### 单一最大地址持仓

| 占比 | 决策 |
|------|------|
| > 50% | REJECT(独大,任意时刻砸盘) |
| 30-50% | WARN_HARD |
| 15-30% | WARN_SOFT |
| < 15% | PASS |

#### 例外(降级)

如果 top 1 / top 10 中有以下地址,**不计入集中度**:

| 例外类型 | 识别方式 | 减权 |
|---------|---------|------|
| LP token / Pool 合约 | GoPlus 标记 / 已知 pool 列表 | 100% 减权 |
| 已锁定 LP | `is_locked = "1"` | 100% 减权 |
| 已知 burn address | 0x0...0 / 0x...dEaD | 100% 减权 |
| 已知 CEX 钱包 | Binance / Coinbase 热钱包 | 50% 减权(CEX 持币代表用户) |
| 已知 staking 合约 | Etherscan label | 50% 减权 |

### §6.10.2 LP Locked 单独检测

```
LP_locked_ratio = sum(is_locked == 1) / total_lp_supply

阈值:
  < 50% locked:WARN_SOFT(LP 可被 rug pull)
  < 30% locked:WARN_HARD
  < 10% locked:REJECT(LP 几乎随时可撤)
  > 95% locked & 锁期 > 365 天:加分(降级所有警告 1 级)
```

### §6.10.3 阈值依据

- **top10 > 70% 警告**:vitalik 公开数据,合理 token top10 < 50%
- **单地址 > 50% REJECT**:链上历史,> 50% 单地址 token 平均 30 天内归零率 65%
- **LP locked < 30% WARN_HARD**:rug pull 案例 80% 是 LP 未锁

---

## §6.11 拦截级别(3 级,具体场景列表)

### §6.11.1 三级定义

| 级别 | 用户体验 | 可否绕过 | 触发 |
|------|---------|---------|------|
| **REJECT**(强阻断) | 红色弹窗 + 不可点击"继续" | **不可绕过** | 法务 / 蜜罐 / 极低流动性 |
| **WARN_HARD**(强警告) | 黄色弹窗 + 双重确认(打字 "我了解风险" 才能继续) | 可绕过(但留痕) | 高税 / 集中度高 / 软蜜罐信号 |
| **WARN_SOFT**(弱警告) | 黄色 toast + 单次确认 | 可绕过 | 一般风险信号 |

### §6.11.2 REJECT 场景完整列表(19 项)

| 场景 | 触发条件 |
|------|---------|
| OFAC 制裁 | token / deployer / owner 任一在 OFAC SDN |
| Chainalysis 制裁 | sanctions oracle 返回 true |
| GoPlus 蜜罐 | `is_honeypot` = "1" |
| GoPlus 不可买 | `cannot_buy` = "1" |
| GoPlus 单地址滑点可改 | `personal_slippage_modifiable` = "1" |
| GoPlus owner 可改余额 | `owner_change_balance` = "1" |
| 模拟卖出失败 | eth_call simulate sell revert |
| 字节码 ≥ 2 项命中 | 子检测 §6.7.3 |
| 历史卖单成功率 < 60%(样本 ≥ 20) | §6.7.4 |
| 买入税 > 30% | §6.8.2.1 |
| 卖出税 > 30% | §6.8.2.2 |
| 总税 > 50% | §6.8.2.3 |
| 流动性 < $5k(meme < $3k) | §6.9.3 |
| 用户单量 / 池子 > 20% | §6.9.4 |
| Top 10 持仓 > 95% | §6.10.1.1 |
| 单地址持仓 > 50% | §6.10.1.2 |
| LP locked < 10% | §6.10.2 |
| 自维护黑名单 confirmed | §6.6.3 |
| 全部数据源失败(safety first) | §6.5.3 |

### §6.11.3 WARN_HARD 场景完整列表(20 项)

| 场景 | 触发 |
|------|------|
| GoPlus `transfer_pausable` = "1" | §6.7.7 |
| GoPlus `slippage_modifiable` = "1" | owner 可改税 |
| GoPlus `cannot_sell_all` = "1" | 不能全卖 |
| GoPlus `is_mintable` = "1" 且无 max supply | §6.7.6 |
| GoPlus `hidden_owner` = "1" | §6.7.5 |
| GoPlus `selfdestruct` = "1" | 字节码 |
| 字节码 1 项命中 | §6.7.3 |
| 历史卖单成功率 60-85% | §6.7.4 |
| 买入税 10-30% | §6.8.2.1 |
| 卖出税 10-30% | §6.8.2.2 |
| 总税 30-50% | §6.8.2.3 |
| 流动性 $5k-$20k(meme $3k-$10k) | §6.9.3 |
| 用户单量 / 池子 10-20% | §6.9.4 |
| Top 10 持仓 85-95% | §6.10.1.1 |
| 单地址持仓 30-50% | §6.10.1.2 |
| LP locked 10-30% | §6.10.2 |
| `honeypot_with_same_creator` = "1" | 同 creator 之前发过蜜罐 |
| 自维护黑名单 suspected | §6.6.3 |
| Etherscan/Solscan label "scam/phishing" | §6.6.3 |
| 多项软命中(≥ 2 项) | §6.7.8 |

### §6.11.4 WARN_SOFT 场景列表(部分)

买入税 / 卖出税 3-10% / 流动性中等 / 用户单量 5-10% / Top 10 70-85% / 单地址 15-30% / LP locked 30-50% / 历史卖单 85-95% / holder count < 100 / `is_blacklisted` 有功能但未使用 / `external_call` / `gas_abuse` / `is_anti_whale` / `trading_cooldown` / token 上线 < 1 小时 等。

---

## §6.12 阻断后用户体验

### §6.12.1 UI 设计原则

1. **不藏**:阻断信息必须出现在用户视线最重要位置
2. **不模糊**:具体哪一项触发,数值是多少
3. **可追溯**:点"查看完整检测结果"看 5 道筛全报告
4. **可申诉**:每个 REJECT 弹窗都有"我觉得这是误报"按钮
5. **不羞辱用户**:用"产品为你拦截"语气

### §6.12.2 REJECT 弹窗(完整文案)

```
┌────────────────────────────────────────────┐
│ [红色图标 X]                                  │
│                                              │
│ 已为你拦截这笔交易                              │
│                                              │
│ ── 拦截原因 ──                                │
│                                              │
│ [蜜罐]  GoPlus 检测显示该 token 是蜜罐:        │
│         模拟卖出失败(revert: transfer failed)│
│                                              │
│ [字节码] 我们的字节码扫描发现 onlyOwner          │
│         protected transfer 限制                │
│                                              │
│ [历史]  过去 24h 卖单成功率仅 18%              │
│         (158 笔尝试,29 笔成功)               │
│                                              │
│  [我了解,取消]  ← 主按钮                       │
│  [查看完整 5 道筛报告] ← 文字链接               │
│  [我认为这是误报,申诉] ← 文字链接               │
└────────────────────────────────────────────┘
```

### §6.12.3 WARN_HARD 弹窗(双重确认)

```
┌────────────────────────────────────────────┐
│ [黄色图标 ⚠]                                  │
│                                              │
│ 这笔交易有重大风险                              │
│                                              │
│ • 卖出税 22%(即使涨 50% 你净赚 ≤ 28%)        │
│ • Top 10 地址持仓 87%                        │
│                                              │
│ 如果你确定要继续,请在下方输入 "我了解风险":      │
│                                              │
│  [____________________]                      │
│                                              │
│  [仍要买入]  [取消(推荐)]                     │
└────────────────────────────────────────────┘
```

注:用户必须**精确输入"我了解风险"** 五个字才能解锁"仍要买入"按钮。这样不仅拦了误点击,还创造法律层面的"知情同意"留痕。

### §6.12.4 申诉路径

```
用户点"申诉" →
  弹窗:"为什么你认为这是误报?"
    选项:
    [ ] 我认识这个项目方,合法 token
    [ ] 已被审计(Quantstamp / CertiK)
    [ ] 大盘 token 被误判
    [ ] 其他(必填):________
    
  附:你的钱包地址 / 交易意图金额(自动填)
  
提交后:
  - 立即返回"已收到,24h 内 review"
  - 进入 risk_appeals 队列
  - 内部 risk team 24h 内处理
  - 处理结果邮件 / Push 通知用户
  - 若证实误报:加白名单,该地址未来不再触发同一规则
```

---

## §6.13 风控历史可查("已为你拦截 X 次")

### §6.13.1 用户主页展示

```
┌────────────────────────────────────┐
│  🛡 你的安全报告                    │
│                                      │
│  过去 30 天                          │
│  ─────────                           │
│  ✓ 拦截 7 次潜在风险                │
│  ✓ 预估保护资金 $3,847              │
│                                      │
│  细节:                              │
│  • 3 次蜜罐拦截                     │
│  • 2 次极低流动性拦截                │
│  • 1 次 OFAC 地址拦截               │
│  • 1 次集中度过高拦截                │
│                                      │
│  [查看完整历史]                      │
└────────────────────────────────────┘
```

### §6.13.2 "预估保护资金" 算法

```
对每次 REJECT:
  IF 蜜罐 / 黑名单 / 极低流动性 → estimated_loss = order_amount × 0.95
  IF 集中度高(REJECT) → estimated_loss = order_amount × 0.6
  IF 高税 > 30% → estimated_loss = order_amount × 0.5

对每次 WARN_HARD 用户取消:
  estimated_loss = order_amount × 0.3(打折,因为不一定真亏)

对每次 WARN_HARD 用户继续:
  不计入(用户自己选了)
```

### §6.13.3 营销价值

每月给用户邮件 / Push 一次:
```
"本月产品为你拦截 7 次潜在风险,保护资金 $3,847。
你的算力费 $X / 月,等于每 $1 算力费保护了 $X 资金"
```

---

## §6.14 规则更新机制

### §6.14.1 规则更新源

| 规则类型 | 更新源 | 频率 |
|---------|-------|------|
| OFAC 名单 | 美国财政部 SDN XML | 每天 02:00 UTC |
| Chainalysis Sanctions | oracle 合约 | 实时 |
| GoPlus 数据 | API 调用,无需我们更新 | 实时 |
| 自维护黑名单 | 用户报告 + 内部 review | 4h SLA |
| 自维护白名单 | 风控 team 维护 | 每周 review |
| 阈值参数 | spec 文档 | 季度 review |
| 字节码 pattern | 内部 R&D | 季度 + 突发(攻击事件后) |

### §6.14.2 自维护黑名单更新流程

```
[用户在产品内点"举报这个 token 是诈骗"]
   ↓
[填写理由 + 上传证据(可选)]
   ↓
[入库 risk_user_reports 表,status = pending]
   ↓
[累计 ≥ 3 个独立用户报告 → 自动 promote 到 risk_blacklist 表 status = suspected]
   ↓
[内部 risk team 4h 内 review]
   ↓
   ├ 证实诈骗 → status = confirmed → 全平台 REJECT
   ├ 不属实 → status = dismissed,白名单 + 反馈用户
   └ 持续监测 → status = suspected,WARN_HARD
```

### §6.14.3 阈值参数更新

`config/risk_thresholds.yaml`(示例):

```yaml
liquidity:
  meme:
    reject: 3000
    warn_hard: 10000
    warn_soft: 50000
  midcap:
    reject: 5000
    ...
tax:
  reject: 0.30
  warn_hard: 0.10
  warn_soft: 0.03
concentration:
  top10:
    reject: 0.95
    warn_hard: 0.85
    warn_soft: 0.70
```

季度 review:看历史拦截命中率 + 误报率,调阈值,灰度发布 → 全量。

---

## §6.15 误报机制(用户投诉 + 24h review)

### §6.15.1 SLA

- **响应**:用户提交后立即返回"已收到"
- **24h Review**:工作日 24h 内有结论,周末 48h
- **告知**:邮件 + Push 双通道

### §6.15.2 Review 流程

```
1. 自动 triage:
   - OFAC 拦截 → 自动 dismiss(法务底线不可申诉)
   - 流动性 / 税率 / 集中度 → 自动重新测一次,如果当前阈值变化 → 自动 reverse
   - 蜜罐 / 字节码 → 进入人工 review queue

2. 人工 review:
   - 风控 team 看用户提交的证据
   - 重新跑 5 道筛,看 token 当前状态
   - 查 token 是否上了 GoPlus trust_list
   - 若实测确实合法 → 加白名单 + 邮件用户

3. 反馈:
   - 误报 → 用户能再次买入(白名单生效)
   - 非误报 → 详细解释为什么我们坚持拦截
   - 用户可二次申诉(罕见)
```

### §6.15.3 误报率监控

```
被强阻断的交易,30 天后看:
  - 该 token 是否归零 / rug → 我们对了
  - 该 token 是否合法发展 → 我们错了(误报)

误报率 = 错的 / 总强阻断
目标 ≤ 2%
高于阈值 → 触发阈值 review
```

### §6.15.4 用户报告"诈骗"奖励

```
用户报告 token A 为诈骗
   ↓
被风控 team 确认
   ↓
自动给该用户 +$1 USDC 算力(或等值)
   ↓
公开榜单"过去 30 天报告最多的用户"(可选,kyc 后自愿)
```

---

## §6.16 AML / 合规法律边界

### §6.16.1 OFAC 法律必须接

- **必须**拦截 OFAC SDN 名单上的所有交易对手方
- **必须**留 1 年以上的拦截记录(审计要求)
- **必须**在产品 ToS 写明这一规则
- **不可**为"老美用户"特别开后门

### §6.16.2 Tornado Cash 制裁的处理

2022 年 8 月 OFAC 加 Tornado Cash 到 SDN,2024 年第五巡回法院判 OFAC 越权,但目前 SDN 上仍有 Tornado Cash 部分地址。

我们的处理:**保留 Tornado Cash 地址在我们的拦截名单**,理由:法律状态仍模糊,拦了不会出错(safety first),用户可申诉。

### §6.16.3 AML(反洗钱)审计跟踪

我们**不阻断 AML 风险**,因为我们不是 CEX,但**记录留痕**:

| 触发 | 记录 |
|------|------|
| 单笔 ≥ $10,000 | 记录到 aml_audit 表(用户 + 金额 + 时间 + token + counterparty) |
| 24h 内累计 ≥ $50,000 | 同上,标 high_volume |
| 来源是 mixer 类钱包(Chainalysis 标) | 同上,标 mixer_origin |
| 跨链桥转入后立即买 token | 同上,标 cross_chain_quick |

存储:Postgres `aml_audit` 表,留 7 年。监管要求时(美国 FinCEN 传票)我们能提供。

### §6.16.4 法律灰区 token

| 类型 | 我们的处理 |
|------|----------|
| **隐私币(Monero / Zcash)** | 多数 CEX 已下架。V1 不上架。V2 评估 |
| **Stake / Liquid Staking** | 美国 SEC 视情况认 securities,但执法案例少。我们买卖支持,不质押 |
| **Meme**(基本无证券争议) | 默认买卖支持,只看蜜罐 / 集中度 |
| **Algo stablecoin**(UST 类) | 历史教训。我们要求 stablecoin 至少 1:1 fiat backed,Algo 类 WARN_HARD |
| **NFT / SFT** | V1 不在范围,V2 评估 |

### §6.16.5 ToS 风控条款样本

```
"本产品为你提供 5 道筛风控保护,但 5 道筛不构成投资建议,
且不能保证 100% 拦截所有风险。

强阻断(REJECT)代表我们高度确信该交易会让你损失。
强警告(WARN_HARD)是我们建议你不要继续。
弱警告(WARN_SOFT)是信息提示。

无论拦截级别,你最终决定是否交易。
你点击"仍要买入"的交易,产品不承担投资损失责任。

我们对 OFAC 制裁地址的拦截是法律要求,不可申诉。"
```

---

## §6.17 数据源整合架构

### §6.17.1 整合架构

```
[5 道筛执行器]
   ↓
[数据源抽象层 — RiskDataProvider 接口]
   ├─ GoPlusProvider(主力)
   ├─ HoneypotIsProvider(蜜罐备份)
   ├─ ChainalysisProvider(OFAC + AML)
   ├─ OFACProvider(直接拉财政部)
   ├─ EtherscanLabelProvider(社区标签)
   ├─ BirdeyeProvider(Solana 主)
   ├─ DexscreenerProvider(多链备份)
   ├─ SelfMaintainedProvider(我们的库)
   └─ SimulationProvider(我们自己 eth_call)
```

每个 provider 实现统一接口:
```
class RiskDataProvider:
    async def check_token(token_addr, chain) -> dict
    async def check_address(addr, chain) -> dict
    async def get_holders(token_addr, chain) -> list
    async def simulate_sell(token_addr, chain, amount) -> bool
```

### §6.17.2 路由策略

| 链 | 主 provider | 备 provider |
|----|------------|------------|
| Ethereum | GoPlus | Honeypot.is + Etherscan + 自模拟 |
| BSC | GoPlus | Honeypot.is + 自模拟 |
| Base | GoPlus | 自模拟 |
| Polygon | GoPlus | 自模拟 |
| Arbitrum | GoPlus | 自模拟 |
| Optimism | GoPlus | 自模拟 |
| **Solana** | **GoPlus + Birdeye 双主** | Dexscreener + 自模拟 |

### §6.17.3 接入成本汇总

| 数据源 | 月成本 | 限速 |
|--------|-------|------|
| GoPlus | $0(免费 30 QPS / 30k 天)/ $99(标准 100 QPS) | 30/100 QPS |
| Honeypot.is | $0 | 5 QPS |
| OFAC 直拉 | $0 | 无 |
| Chainalysis 商业 | $XX,XXX/年 | 商谈 |
| Etherscan Pro | $200 | 100 QPS |
| Birdeye | $0 / $99 起 | 10/100 QPS |
| Dexscreener | $0 | 60/分钟 |

**V1 总成本**:**$0/月**(全免费层)
**V2 估算**:**~$300/月**(GoPlus + Etherscan + Birdeye 标准层)

---

## §6.18 验收标准(精确 KPI)

### §6.18.1 功能验收

| 项 | 验收标准 |
|----|---------|
| 5 道筛执行 | 每笔订单都跑过完整 5 道筛 |
| OFAC 拦截 | 测试用例 OFAC 地址 100% 拦截 |
| 蜜罐拦截 | 给出 50 个已知蜜罐 token,拦截率 ≥ 95% |
| 流动性拦截 | < $5k 池子 token 100% 拦截 |
| 集中度拦截 | top10 > 95% token 100% 拦截 |
| 三级分级正确 | 测试用例覆盖 REJECT / WARN_HARD / WARN_SOFT 各 20 个 |
| 弹窗文案 | 拦截原因展示具体数值,不出现"风险高"占位符 |
| 申诉路径 | 任意 REJECT 弹窗都有"申诉"按钮 |
| 风控历史 | 主页"已拦截 X 次"实时更新 |
| 误报申诉 24h SLA | 工作日 95% case 24h 内 review |

### §6.18.2 性能验收

| 项 | 标准 |
|----|------|
| 风控总延迟 P50 | ≤ 600ms |
| 风控总延迟 P95 | ≤ 1000ms |
| 风控总延迟 P99 | ≤ 2000ms |
| 单道筛超时 | ≤ 800ms |
| 数据源失败率 | < 0.1% |

### §6.18.3 准确性验收

| 项 | 标准 |
|----|------|
| 拦截命中率 | ≥ 95% |
| 误报率 | ≤ 2% |
| OFAC 漏报 | 0 |
| 蜜罐漏报 | ≤ 5% |
| GoPlus 交叉验证一致性 | ≥ 80% |

### §6.18.4 用户体验验收

| 项 | 标准 |
|----|------|
| REJECT 弹窗用户理解度 | 用户能复述拦截原因 |
| WARN_HARD 通过率 | 60-80%(< 60% 太严,> 80% 太松) |
| 风控引发用户流失 | < 3%(月度调研) |
| 申诉提交比例 | < 5% / REJECT |
| 申诉确认误报比例 | < 30% |

### §6.18.5 法务验收

| 项 | 标准 |
|----|------|
| OFAC 留痕 | 1 年内所有拦截可查 |
| AML 留痕 | 7 年内所有大额交易可查 |
| ToS 已写风控条款 | 法务 review 通过 |
| 用户"我了解风险"留痕 | 100% WARN_HARD 通过都有打字记录 |

---

## §6.19 监控埋点

### §6.19.1 业务指标

| 指标 | 频率 | 报警 |
|------|------|------|
| 5 道筛执行次数 | 实时 | 突降 50% → P1 |
| REJECT 率 | 5min 滚动 | > 12% 或 < 3% → P2 |
| WARN_HARD 通过率 | 1h 滚动 | < 50% 或 > 90% → P2 |
| 拦截命中率 | 7d 滚动 | < 90% → P2 |
| 误报率 | 7d 滚动 | > 5% → P1 |

### §6.19.2 性能指标

| 指标 | 频率 | 报警 |
|------|------|------|
| 风控总延迟 P50/P95/P99 | 1min | P95 > 1500ms → P2 |
| 各 provider 延迟 P95 | 1min | > 600ms → P3 |
| 各 provider 失败率 | 5min | > 5% → P2 |
| Redis 命中率 | 5min | < 80% → P3 |

### §6.19.3 数据库表

| 表 | 用途 |
|----|------|
| `risk_checks` | 每次执行的 5 道筛结果(留 90 天) |
| `risk_blacklist` | 自维护黑名单 |
| `risk_whitelist` | 自维护白名单(申诉通过) |
| `risk_user_reports` | 用户报告 token 是诈骗 |
| `risk_appeals` | 申诉队列 |
| `ofac_history` | OFAC 拉取历史(留 1 年) |
| `aml_audit` | AML 大额交易记录(留 7 年) |
| `risk_reason_codes` | 拦截原因字典(用于多语言文案) |

### §6.19.4 报警渠道

| 严重度 | 渠道 |
|-------|------|
| P1 | PagerDuty(call) + Slack #risk-emergency |
| P2 | Slack #risk-alert + 邮件 |
| P3 | Slack #risk-info |
# §7 AI Agent 怎么帮人下单 — 详细规格(R48)

> 本章是产品 PRD 的核心差异化章节。前面 6 个模块是工具底座;本章定义 **AI 如何把这些工具串成一个"能帮人决策、能解释、能被信任"的代理人**。这是我们对 Axiom / FOMO / GMGN 的根本性差异。

---

## §7.0 模块定位 + 北极星指标

### §7.0.1 模块在产品中的定位

```
┌─────────────────────────────────────────────────────────────┐
│  §7  AI Agent 决策层(本章)                                 │
│       ↑↑↑↑↑↑↑                                                │
│  ┌────┴──────┴──────┴──────┴──────┴──────┴──────┐           │
│  │ §1 信号   │ §2 扫盘  │ §3 风控  │ §4 执行  │ ...│           │
│  │ 工具底座(不会自己做决定)                  │           │
│  └─────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

- §1-§6 是**确定性工具**:你给参数它返结果,不思考
- §7 是**思考层**:把"我想买点 SOL 上有热度的东西"翻译成"在 §1 找信号 → 在 §3 过风控 → 在 §4 出单 → 在 §6 跟单"
- §7 不重新实现 §1-§6 的能力,**只编排和解释**

### §7.0.2 北极星指标(NSM)

**主指标:AI 信任度 NPS**

> 30 天内活跃用户回答"你愿意把日交易额 50% 以上交给 AI 全自动吗"的净推荐值

| 阶段 | 目标 NPS |
|---|---|
| GA + 30 天 | -20 ~ 0 |
| GA + 90 天 | +10 ~ +20 |
| GA + 180 天 | +30 ~ +40 |
| GA + 365 天 | +50(行业里最被信任的 AI Agent) |

**辅助指标**:
1. **Mode-A Adoption Rate**:开通模式 A 的用户 / DAU。GA+180 天 ≥ 20%
2. **AI Override Rate**:AI 给建议被用户改单 / 总建议数。≤ 25%(高于此说明 AI 不准)
3. **Action Log Open Rate**:用户点开 AI 决策详情的占比。≥ 40%(说明用户在意可解释)
4. **Emergency Stop Trigger Rate**:紧急停止按钮触发频次。≤ 0.5%(高于此说明用户对 AI 失控)
5. **AI-attributed PnL**:AI 主导决策的累积 PnL vs 用户主导的累积 PnL。AI 应至少不显著差

### §7.0.3 与上下游模块的契约

**上游提供给 §7**:
| 上游 | 提供 | §7 用法 |
|---|---|---|
| §1 信号 | 实时事件流 | 作为意图触发器 |
| §2 扫盘 | token meta + 流动性 + 持仓分布 | 决策树第 3-4 层 |
| §3 风控 | HR01-HR18 18 条硬线 + 软线评分 | 一票否决权 |
| §6 跟单 | 鲸鱼地址 + 历史胜率 | 模式 A 信号源之一 |

**下游使用 §7**:
| 下游 | §7 提供 |
|---|---|
| §4 执行器 | 结构化下单意图 `{token, side, amount_usd, slippage, route_pref, reason_id}` |
| §5 钱包 | user_id + 链 ID(解析钱包) |
| §8 通知 | event + template_id + payload |
| §10 Action Log | 完整决策快照 |

---

## §7.1 用户故事(10 个)

**US-7.1 — 新手 Echo(模式 B 默认)**
> 28 岁,听朋友说 Solana meme 有得做。下载 App 第一句问 AI:"现在 SOL 链上有什么热度高但没崩盘的"。AI 给 3 个候选 + 各自卡片。Echo 看了第 2 个的解释("5 分钟内三个 KOL 提到 + 流动性 $200K + 持仓集中度低")后点确认买 $50。
> **核心需求**:AI 不能替我决定,但要替我筛掉 99% 的垃圾。

**US-7.2 — 重度玩家 Maya(模式 A 全自动 + 跟单)**
> 锁定 5 个鲸鱼地址,每天人工盯太累。设:"这 5 个地址任一买入流动性 ≥$50K 的 token 时,按他买入额的 5% 跟单,单笔 cap $300,日 cap $2000,止盈 +50% 止损 -25%。"
> **核心需求**:AI 在我睡觉时也能动手,但有边界,能随时拉闸。

**US-7.3 — 风险规避者 Leo(模式 C 主动 + AI 优化)**
> 输入:"买 $200 的 $WIF",AI 自动选 Jupiter(流动性最深)+ 滑点 0.6% + 提示"3 分钟内有大额买盘,建议 split 成 3 笔"。
> **核心需求**:决策权在我,AI 帮我把执行细节做到最优。

**US-7.4 — 学习型用户 Iris(模式 D 教练)**
> 不下单,只想学。浏览鲸鱼 0xABC 最近 10 笔交易,每笔点开问"他为什么买这个"。AI 解释:"他在 KOL @vibe_eth 推前 3 分钟买入 + 当时该 token 流动性刚过 $30K 阈值 + 该地址历史胜率 67%"。
> **核心需求**:用 AI 当老师,不用 AI 当手脚。

**US-7.5 — 跨链投机者 Ben**:"BSC 上有什么 24h 涨幅前 10 但没有 honeypot 的?" → AI 走扫盘 + 风控,返 4 个候选

**US-7.6 — 防被骗用户 Tina**:复制 TG 群 token 地址问 AI → AI:"**拒绝执行 — HR03 命中:合约 owner 未弃权 + HR07 命中:TOP10 持仓 91%。这是高度疑似 rug pull**"

**US-7.7 — 跟单老用户 Kim(模式 A 异常处理)**:鲸鱼地址连续 3 笔亏损 -40% → AI 自动触发"跟单冷却":暂停 24h + 推送

**US-7.8 — 紧急止损用户 Rex**:凌晨 3 点 SOL 拥堵,模式 A 4 笔下单全部 timeout。一键拉**"暂停所有 AI 操作"** → 30 秒内所有 pending 自动撤销

**US-7.9 — 多账户用户 Owen**:3 个钱包(主仓不动 / 投机跟 5 鲸鱼 / 长仓只手动确认)
> **核心需求**:AI 必须按钱包分权限,不能越界

**US-7.10 — 模糊意图用户 Fan**:"我想买点便宜的" → AI 反问"想要哪个链上的(SOL/BSC/Base/ETH)?" → "SOL" → "便宜是指 < $1 还是市值 < $1M?"
> **核心需求**:AI 能多轮对话补全意图,不能让我重打

---

## §7.2 产品边界

### §7.2.1 §7 做的事

1. **意图识别**:把自然语言 / UI 操作 / 信号事件 → 结构化交易意图
2. **决策编排**:调度 §1-§6 的工具,组合出最终下单参数
3. **风控仲裁**:§3 给硬线 + §7 给软线评分,决定该不该执行
4. **执行下发**:把意图变成 §4 能消化的下单请求
5. **解释生成**:每笔决策给人话级别的 reason
6. **失败处理**:单笔失败的重试 / 降级 / 通知 / 回滚
7. **状态追踪**:每个 AI 启动的"任务"全程可追溯
8. **学习反馈**:用户改单 / 拒绝 / 紧急停止的信号回流到 prompt

### §7.2.2 §7 不做的事

1. **不重新实现 §1-§6**:信号是 §1 的,价格是 §2 的,签名是 §5 的
2. **不预测价格涨跌**(不是占卜师)
3. **不替用户做投资目标决策**(仓位规模上限始终用户定)
4. **不做高频套利**(毫秒级竞价让位给纯算法 §4)
5. **不写链上合约**(§5 的事)
6. **不存储用户私钥**(永远只 §5 加密管理)
7. **不下任何超出预授权的单**(即使是它"觉得"该下)
8. **不在用户离线时违规升级权限**(模式 B 不会自动变模式 A)

### §7.2.3 强约束

| ID | 约束 | 检查点 |
|---|---|---|
| §7-C01 | AI 主动下单仅在模式 A 且预授权未过期时允许 | dispatcher 入口 |
| §7-C02 | 任何决策必须留 Action Log(无 log 不下单) | logging gate |
| §7-C03 | §3 任一 HR0X 硬线命中 → AI 不可绕过 | risk_gate |
| §7-C04 | 单笔金额超出 max_position_usd → 强制人工确认 | semi-auto branch |
| §7-C05 | LLM 输出未过 schema 校验 → reject 不入执行链 | schema_validator |
| §7-C06 | 紧急停止后 30s 内停止所有 pending action | kill_switch |
| §7-C07 | 用户拒绝 3 次同类型建议后,30 天不再主动推送同类型 | user_feedback_loop |
| §7-C08 | LLM 调用失败 → 不允许走"默认动作",必须人工 | fail_closed |

---

## §7.3 竞品全景对比表(10 竞品 × 12 维度)

| 维度 | Axiom | FOMO | GMGN | Maestro | BananaGun | TrojanBot | Photon | Bullx | Universal X | Bitte/Pond/Mode |
|---|---|---|---|---|---|---|---|---|---|---|
| **AI 介入程度** | AI 建议 + 用户确认 | AI 自动 + 边界 | 工具 + 鲸鱼跟单 | 信号 + 一键 | sniper + AI 反诈 | 工具 + 限价 | 纯工具终端 | 信号订阅 | intent 分发 | 框架(无终端 UI) |
| **NLP 能力** | 部分(命令为主) | 完整对话 | 命令 + 预设 | 命令 | 命令 | 命令 | 无 | 无 | intent NL | 全 |
| **决策透明度** | 中(给信号源) | 高(给 reason) | 低(黑盒跟单) | 中(信号订阅) | 中(反诈分) | 低 | N/A | 中 | 中(路由可见) | 高(开源) |
| **失败回退** | 重试 1 次 | 重试 + 降级 | 重试 | 重试 | 重试 | 失败放弃 | N/A | N/A | 跨链回滚 | 自定义 |
| **授权模型** | 单笔签名 | 单笔 cap + 日 cap | 钱包级别 | 单笔 | 单笔 | 单笔 | 单笔 | N/A | session key | 自定义 |
| **安全约束** | 滑点保护 | honeypot + cap | 黑名单 | 滑点 | 反诈 | 滑点 | 滑点 | N/A | intent guard | 自定义 |
| **信任建立机制** | 战绩面板 | Action 卡片 + 解释 | 鲸鱼胜率 | 信号胜率 | 反诈率展示 | 无 | 速度 | 信号准确率 | intent log | 文档 |
| **收费** | 1% | 1% + 订阅 | 1% | 订阅 | 1% | 1% | 0.5% | 订阅 | gas 加价 | 开源免费 |
| **链覆盖** | SOL | SOL/ETH/Base/BSC | SOL/ETH/Base/Tron | ETH/SOL/BSC/Base/Blast | ETH/SOL/Base/Blast | SOL | SOL | SOL/ETH/Base | 多链 intent | 自配 |
| **载体** | Web + TG | iOS/Android App | Web + TG | TG | TG | TG | Web | TG + Web | Web + SDK | SDK/CLI |
| **用户层级** | 中级 | 新手友好 | 中高级 | 中级 | 中级 | 中高级 | 高级 | 中级 | 极客 | 开发者 |
| **AI 自动下单** | 半自动 | 是(有边界) | 是(仅跟单) | 否(仅信号) | 半自动 | 半自动 | 否 | 否 | 是(intent) | 自配 |

### §7.3.2 关键观察

1. **没人做"AI 教练"模式(模式 D)**:所有竞品都默认 AI 是手脚,不是老师。我们用模式 D 抢"想学习的小白" — 他们将来会变 paying user
2. **NLP 能力两极分化**:要么命令式,要么 intent-only。**没人做"完整对话 + 多轮回填 + 解释"**
3. **决策透明度普遍差**:GMGN 鲸鱼跟单是黑盒,Bullx 信号也是黑盒。我们 Action Log 是结构化、可分享、可导出 — 这就是差异化
4. **失败回退几乎都是"重试一次或放弃"**:没人做系统级降级 + 用户感知文案
5. **授权模型最弱**:基本是"单笔签名"或"钱包私钥托管",没有"日 cap + 单笔 cap + 白名单 token + 紧急停止"完整组合

---

## §7.4 我们的差异化

### §7.4.1 我们独有的 4 个杀手级功能

1. **决策树可视化**:每笔下单的"为什么"是结构化树,可点开每一层
2. **教练模式**:AI 不下单,只解释鲸鱼 / 信号 / 行情。培养小白成中级用户
3. **三级紧急停止**:全局 / 钱包 / 单策略。其他家都只有全局
4. **AI 失效冷却**:跟单的鲸鱼连亏 / 信号源准确率掉 / LLM 输出质量异常 → 自动暂停某来源 + 通知用户

### §7.4.2 vs Axiom / FOMO / GMGN

| 维度 | 别人 | 我们 |
|---|---|---|
| AI 角色 | 工具 | 决策代理 + 解释 |
| 模式 | 单一 | 4 种(A/B/C/D) |
| 解释 | 给信号来源 | 给完整决策树(为什么选这个工具 / 这个滑点 / 这个时机) |
| 教练模式 | 无 | 有 |
| 自动模式 cap | 有但简单 | cap + 白名单 + 日上限 + 时段限制 + 钱包分权 |
| 紧急停止 | 全局 | 全局 + 单策略 + 单钱包三级 |
| 失败回退 | 重试 + 放弃 | 三级失败 + 系统级降级 + 用户文案分场景 |
| 跟单 | 黑盒 | 可解释 + 自动暂停 + 用户可看为什么这笔没跟 |

---

## §7.5 4 种交互模式

> 4 种模式不是"高级与低级",而是"用户对 AI 信任程度的滑动条"。同一用户在不同场景可能用不同模式。

### §7.5.0 模式选择矩阵

| 用户类型 | 默认模式 | 升级路径 |
|---|---|---|
| 新手(首日) | B | → C → A(跟单) |
| 老 DeFi | C | → A(跟单 / 信号) |
| 学习型 | D | → B → C |
| 重度玩家 | A | 横向扩展更多策略 |

### §7.5.0.1 模式占比预测

| 阶段 | A | B | C | D |
|---|---|---|---|---|
| GA + 30 天 | 5% | 60% | 25% | 10% |
| GA + 90 天 | 12% | 50% | 28% | 10% |
| GA + 180 天 | 22% | 42% | 28% | 8% |
| GA + 365 天 | 30% | 35% | 28% | 7% |

---

### §7.5.1 模式 A — 全自动(用户配置策略后)

#### A.1 适用人群

- DeFi 老玩家(玩过 Photon / GMGN / Maestro 至少 30 天)
- 有明确策略(跟单 N 个鲸鱼 / 抢 pump 冷启动 / 解锁前清仓)
- 工作忙不能盯盘(夜班 / 跨时区)

#### A.2 完整 UX 流程

**Step 1 — 选策略模板**:鲸鱼跟单 / Pump 抢跑 / 解锁前清仓 / KOL 信号订阅 / 自定义

**Step 2 — 参数配置(以鲸鱼跟单为例)**:
- 跟单地址(最多 10 个,可粘贴 + 自动验证)
- 跟单比例(按鲸鱼仓位 1%-20%,默认 5%)
- 链选择(多选)
- 单笔上限(USDC,默认 $300,可调 $50-$10000)
- 日累计上限(默认 $1500)
- 时段限制(24h / 仅美股交易时段 / 仅亚洲时段)
- token 白名单(可选)
- token 黑名单(默认含 stable / wrapped / blue chip)
- 止盈止损(默认 +50% / -25%)
- 通知策略(每笔通知 / 每日汇总 / 仅异常)

**Step 3 — 预授权与确认**:
```
你即将授权 AI 在以下边界内自动下单:
• 单笔 ≤ $300 USDC
• 日累计 ≤ $1500 USDC
• 仅触发:地址 0xABC / 0xDEF / 0x123 的买入
• 时段:24h
• 链:SOL, BSC
• token 黑名单:USDT/USDC/SOL/WIF(标准)

你随时可以:
✓ 修改任意参数
✓ 暂停某个跟单地址
✓ 紧急停止整个策略

[ 取消 ]              [ 我已理解,启动 ]
```

**Step 5 — 单笔自动执行(无人值守)**:
```
[鲸鱼 0xABC 买入 $5000 $WIF]
      ↓
[§1 信号检测,60s 内]
      ↓
[§7 决策树启动]
  ├─ 意图:跟单买入
  ├─ 风控:HR01-HR18 全过 → 软线评分 7.2/10
  ├─ 路径:Jupiter v6(流动性最深)
  ├─ 大小:$5000 × 5% = $250(≤ 单笔上限)
  ├─ 滑点:0.7%(基于 1h 波动)
  └─ 决定:执行
      ↓
[§4 执行 → tx hash 0xabc...]
      ↓
[Action Log 写入]
      ↓
[通知用户:已为你跟单 0xABC 买入 $WIF $250,附 reason]
```

整个过程 **< 90 秒**(含 §1 检测 60s + §7 决策 5s + §4 执行 5-15s + 通知 1s)。

#### A.3 AI 决策的边界

**能做**:
- 在预授权范围内自主决定执行 / 跳过
- 选路由 / 滑点 / split 策略
- 触发止盈止损(自动卖出)
- 检测异常并自动冷却(鲸鱼连亏 / 信号源失准)
- 重试失败交易(最多 2 次)

**不能做**:
- ❌ 突破单笔 / 日上限(即使"觉得"很好的机会)
- ❌ 买入黑名单 token
- ❌ 修改预授权(只能用户改)
- ❌ 跨钱包动作(模式 A 钱包只能动自己)
- ❌ 转账(仅交易)
- ❌ 在紧急停止后还动作

#### A.4 失败回退

| 失败类型 | 1 次 | 2 次 | 3 次 |
|---|---|---|---|
| 单笔交易失败(链上 revert) | 立即重试同参数 | 5s 后重试 + 滑点 +0.3% | 放弃 + 推送用户 + Action Log 标 fail |
| 路由失败(Jupiter 不可用) | 切到 §4 备用路由 | 切到第三路由 | 跳过此次 + 通知 |
| 余额不足 | 推送用户 + 暂停策略 | - | - |
| §3 风控否决 | 不重试,记录原因 | - | - |
| LLM 超时 | 5s 后重试 | 切到备份 LLM(Haiku) | 跳过此次 + 通知 |
| 紧急停止触发 | 立即停止所有 pending | - | - |

#### A.5 数据预测

- **占比**:GA+30 天 5%,GA+180 天 22%,GA+365 天 30%
- **典型用户**:日交易 10-30 笔,AUM $5000-$50000
- **AI 介入率**:100%(用户配完后零参与)
- **风险**:一旦失控(跟错鲸鱼 / 黑天鹅)单日可能 -30%。所以**单笔 / 日上限是命**

---

### §7.5.2 模式 B — AI 建议 + 用户确认(默认)

#### B.1 适用人群

- 大部分新用户(60%-70%)
- 不愿意全交给 AI,又不想自己每次填参数

#### B.2 完整 UX 流程

**Step 1 — 用户提需求**:3 种方式
1. **自然语言**:"现在 SOL 上有什么热度高的"
2. **快捷命令**:`/recommend SOL hot`
3. **触发 UI**:Dashboard "AI 建议"按钮

**Step 2 — AI 思考态**:
```
AI 正在分析...
✓ 扫描 SOL 链 1247 个新 token
✓ 过滤 968 个不满足流动性下限
✓ 风控筛选 281 → 47 个
⏳ 评估热度 + 持仓分布...
```

约 3-5 秒(用户看得到 AI 在做事,建立信任)。

**Step 3 — AI 给候选**:3 个候选卡片,每个含:

```
┌──────────────────────────────────────────────────────┐
│  $WIF(候选 1,推荐度 ★★★★☆ 8.2/10)                │
│  价格 $1.23 / 流动性 $2.1M / 24h +12%               │
│  ────────────────────────────────────────           │
│  推荐理由:                                          │
│  • 流动性深($2.1M,HR12 优先级 1)                 │
│  • 持仓集中度低(TOP10 占 14%,HR07 通过)          │
│  • 1h 内 3 个 KOL 提及(@kol_a / @kol_b / @kol_c)  │
│  • 部署者 30 天无 rug 历史(HR05 通过)             │
│                                                      │
│  风险提示:                                          │
│  • 24h 涨幅已 +12%,可能短期回调                    │
│                                                      │
│  推荐买入额:$80(基于你余额 $1200,5% 分配)       │
│  推荐路由:Jupiter v6                                │
│  推荐滑点:0.5%                                      │
│                                                      │
│  [ 修改参数 ]    [ 看更多解释 ]    [ 确认买入 ]     │
└──────────────────────────────────────────────────────┘
```

**Step 4 — 用户确认**:
- 默认 30 秒倒计时(视觉条不强制)
- 用户可:直接点确认 / 改金额 / 改滑点 / 取消 / 看更详细解释
- 如果用户改了金额超过 max_position_usd → 进半自动 10s 撤销链路(与现有 R47 P6 一致)

#### B.3 AI 决策的边界

**能做**:主动给候选 + 推荐参数 / 解释为什么 / 风险点 / 检测明显的拒绝场景

**不能做**:
- ❌ 自己执行(必须用户点确认)
- ❌ 超出用户问的链 / 主题给候选
- ❌ 给超过 5 个候选(信息过载)

#### B.4 数据预测

- **占比**:GA+30 60% → GA+365 35%
- **典型用户**:日交易 2-8 笔,AUM $200-$5000
- **AI Override Rate**:目标 ≤ 25%

---

### §7.5.3 模式 C — 用户主动 + AI 优化

#### C.1 适用人群

- 自己做研究的中高级用户
- 已经知道要买什么 token,但不想手动填执行参数
- 希望 AI 帮做"执行优化"(路由 / 滑点 / split / 时机)

#### C.2 完整 UX 流程

**Step 1 — 用户给具体单**:输入 "买 $200 的 $WIF" / 扫盘点 "AI 优化下单" / 粘贴 token 地址 + 金额

**Step 2 — AI 优化**(不重新做尽调,只做执行优化):

```
你想买 $200 的 $WIF。我来优化执行:

路径:Jupiter v6(深度 $2.1M,比 Raydium 滑点低预估 0.3%)
滑点:0.6%(基于 1h 波动率 0.4% × 1.5 缓冲)

时机分析:
• 当前订单簿买盘较强(买卖比 1.4)
• 近 5 分钟无大额卖单
• 建议立即执行

Split:金额 < $500,无需 split

预估成本:$200 + gas $0.001 + 平台费 $0.01

风控提示:HR01-HR18 全过 ✓

[ 修改 ]    [ 跳过分析直接执行 ]    [ 确认 ]
```

**Step 4 — split 场景(金额大)**:输入 "买 $5000 的 $WIF" → AI:

```
$WIF 当前流动性 $2.1M,$5000 单笔会造成显著滑点(预估 1.8%)。
建议 split:
  - 第 1 笔 $2000(立即)
  - 第 2 笔 $1500(30 秒后)
  - 第 3 笔 $1500(60 秒后)
预计总滑点降至 0.7%,节省约 $55。
[ 接受 split ]   [ 一笔执行 ]   [ 改总额 ]
```

#### C.3 AI 决策的边界

**能做**:选路由 / 滑点 / split / 时机;提示"现在不是好时机";风控自动检查

**不能做**:
- ❌ 替用户决定要不要买
- ❌ 改 token / 改方向 / 改总额
- ❌ split 后偏离总额(split 总和 == 用户输入)

#### C.4 数据预测

- **占比**:GA+30 25% → GA+365 28%(中间稳定)
- **典型用户**:日交易 5-15 笔,AUM $1000-$20000
- **价值**:节省 30-60 秒手动选参数 + 降低实际滑点 0.3%-1%

---

### §7.5.4 模式 D — 教练模式(V2)

#### D.1 适用人群

- 学习型用户(想学但不敢动手)
- 老用户研究新链 / 新策略
- 拒绝"AI 替我决定"的怀疑型用户
- 内容创作者(看 AI 解释当素材)

#### D.2 完整 UX 流程

**入口**:Dashboard 切换 toggle 到"教练模式" / 任意 token / 鲸鱼 / 信号 → 长按 → "问 AI 教练"

**支持的问题类型(V2 至少 8 种)**:
1. "为什么这个鲸鱼买这个 token"
2. "这个 token 现在能买吗"(不下单,只解释)
3. "这个项目的代币经济怎么样"
4. "为什么这个 KOL 的信号准确率高"
5. "这次 pump 是真的还是伪造"
6. "这个 token 的退出风险点是什么"
7. "我现在的仓位结构合理吗"(不交易,只评估)
8. "假如我现在买 $100 会怎样"(模拟)

**AI 解释(教学风格)示例**:
```
为什么 0xABC 买 $WIF?让我们拆开看:

① 时间维度
   他在 14:23 UTC 买入。这个时段是 Solana pump.fun 新币毕业最频繁的窗口
   (亚洲交易者活跃 + 美股盘前关注度高)。他过去 30 天有 67% 的胜率交易在这个窗口完成。

② 信号触发
   KOL @vibe_eth 在 14:18 推 $WIF(5 分钟前)。
   0xABC 历史上有 23 次跟随这个 KOL,平均收益 +45%。这是他的"已知有效信号源"之一。

③ 流动性窗口
   当时流动性 $180K(刚刚突破 $150K 阈值)。这是 0xABC 的偏好区间 —
   他不买流动性 < $50K(滑点高),也不买 > $1M(涨幅小)。

④ 风控特征
   部署者钱包 30 天内无 rug 历史,TOP10 持仓 21%,处于他历史买入的舒适区。

💡 学习点:
跟单不是抄数字,是抄"模式"。0xABC 的模式是:
KOL 信号 + 流动性窗口 + 部署者信誉。掌握模式后你可以自己找下一个 0xABC。

[ 详细分析他的胜率分布 ]   [ 看类似的鲸鱼 ]
```

#### D.3 AI 决策的边界

**能做**:任意级别的解释 / 拆解 / 对比 / 模拟;推荐学习路径;在 D 模式下软推荐切换到 B / C 模式

**不能做**:
- ❌ 下任何单(这是 D 模式的硬约束)
- ❌ 以"建议"为名变相诱导(必须明确"这是教学,不是投资建议")
- ❌ 给具体金额 / 时机的"操作建议"

#### D.4 V1 vs V2

- **V1**(GA):模式 A/B/C
- **V2**(GA+90 天):加入模式 D
- **理由**:V1 优先验证决策准确性,D 模式建立在用户已经看过 AI 表现的基础上才有说服力

---

## §7.6 AI 决策树(每笔下单都跑这个)

### §7.6.1 决策树状态机

```
                    ┌────────────────────────┐
                    │  T0: 触发              │
                    │  (NL / 信号 / 用户操作) │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  T1: 意图识别          │
                    │  LLM-Haiku             │
                    │  → IntentSchema        │
                    └───────────┬────────────┘
                                │
                ┌───────────────┴───────────────┐
                │ 意图不明确?                   │
                ├──── YES ──→ T1.5 多轮回填     │
                │             (提问用户)        │
                └───────────────┬───────────────┘
                                │ NO
                    ┌───────────▼────────────┐
                    │  T2: 模式路由           │
                    │  根据用户当前模式 A/B/C/D │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  T3: 数据采集           │
                    │  §1 信号 + §2 token     │
                    │  + §6 跟单上下文        │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  T4: 风控硬线           │
                    │  §3 HR01-HR18           │
                    └───────────┬────────────┘
                                │
                ┌───────────────┴───────────────┐
                │ 任一硬线命中?                 │
                ├──── YES ──→ T-REJECT          │
                │             记 reason + 通知   │
                └───────────────┬───────────────┘
                                │ NO
                    ┌───────────▼────────────┐
                    │  T5: 软线评分           │
                    │  LLM-Sonnet 评估        │
                    │  → score 0-10           │
                    └───────────┬────────────┘
                                │
                ┌───────────────┴───────────────┐
                │ score < threshold(默认 5.5)? │
                ├──── YES ──→ T-SKIP            │
                │             记 reason         │
                └───────────────┬───────────────┘
                                │ NO
                    ┌───────────▼────────────┐
                    │  T6: 路径选择           │
                    │  比较 §4 候选路由       │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  T7: 大小判断           │
                    │  policy + 流动性约束    │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  T8: 滑点 / split       │
                    │  基于波动率 + 流动性    │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  T9: 时机评估           │
                    │  订单簿 + 1m 大单检测   │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  T10: 模式分支          │
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
   ┌────▼────┐            ┌─────▼─────┐          ┌─────▼─────┐
   │ Mode A  │            │ Mode B    │          │ Mode C    │
   │ 直接执行 │            │ 给候选卡   │          │ 优化后给确认│
   └────┬────┘            └─────┬─────┘          └─────┬─────┘
        │                       │                       │
        │    ┌──────────────────▼──────────────────┐    │
        │    │  T11: 用户决策(B/C)                │    │
        │    └──────────────────┬──────────────────┘    │
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  T12: 半自动闸门        │
                    │  amount > $500?         │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  T13: 执行 §4           │
                    │  → tx_hash 或 fail      │
                    └───────────┬────────────┘
                                │
                ┌───────────────┴───────────────┐
                │ 失败?                        │
                ├──── YES ──→ T-RETRY           │
                └───────────────┬───────────────┘
                                │ SUCCESS
                    ┌───────────▼────────────┐
                    │  T14: Action Log 写入   │
                    │  T15: 通知用户          │
                    │  T16: 监控 + 学习反馈   │
                    └────────────────────────┘
```

### §7.6.2 每个 step 的算法 / 输入 / 输出

#### T1 意图识别

**输入**:
- `user_message: string`(自然语言)
- `user_context: { mode, recent_intents[], wallet_state, balance }`
- `signal_event?: SignalEvent`(如果是信号触发)

**算法**:LLM-Haiku 调用,prompt 含 12 种意图 schema

**输出**:
```json
{
  "intent_type": "buy_specific" | "discover" | "follow_whale" | ...,
  "confidence": 0.0 - 1.0,
  "params": { "chain", "token", "amount_usd", "constraints" },
  "missing_fields": ["amount_usd"],
  "needs_clarification": true | false
}
```

#### T1.5 多轮回填

**算法**:扫 `missing_fields`,按优先级问最重要的 1 个
**优先级**:`chain > token (or constraint) > amount > slippage > others`

#### T4 风控硬线

**输入**:`token_addr, chain, amount_usd, route, user_id`
**算法**:调 §3 `risk_check.evaluate(...)`,返 `{ passed: bool, hits: HR0X[], details }`
**fail-closed**:任一 HR 命中即 reject,不允许 AI 绕过

#### T5 软线评分

**输入**:完整上下文
**算法**:LLM-Sonnet,prompt 含 12 个评分维度(流动性 / 热度 / KOL 共识 / 持仓分布 / 鲸鱼信誉 / ...)
**输出**:`{ score: 7.2, breakdown: { liquidity: 8, heat: 7, ... }, reasoning: "..." }`

#### T6 路径选择

**算法**:`§4.list_routes(token, amount)` → 比较 `(expected_output, gas, slippage)` → argmax

#### T7 大小判断

```
target = user_intent.amount_usd or policy.default
liquidity_cap = liquidity * 0.05  # 流动性 5% 上限
final = min(target, liquidity_cap, mode.single_cap)
```

#### T8 滑点

```
volatility_1h = §2.get_volatility(token, "1h")
slippage = max(0.3%, volatility_1h * 1.5)
slippage = min(slippage, 3%)  # 硬上限
```

#### T9 时机

- 取 §2 1m 订单簿快照
- 检测:买卖比 / 大单(> 流动性 5%)
- 如果买卖比 < 0.7 或检测到大卖单 → 建议等 30s

---

## §7.7 自然语言意图识别

### §7.7.1 12 个支持的意图

| ID | 意图 | 示例 | 调用 mode | 必需字段 |
|---|---|---|---|---|
| I-01 | 买特定 token | "买 $200 的 $WIF" | C | token, amount |
| I-02 | 卖特定持仓 | "卖掉我所有的 $WIF" | C | token |
| I-03 | 发现机会 | "现在 SOL 上有什么热度高的" | B | chain, theme |
| I-04 | 跟单鲸鱼(一次) | "复制 0xABC 这一笔" | B | tx_hash or addr |
| I-05 | 跟单订阅 | "持续跟 0xABC 的所有买入" | A | addr, cap |
| I-06 | 设止盈止损 | "$WIF 涨到 $2 卖一半" | A | token, trigger, action |
| I-07 | 查询行情 | "$WIF 现在多少钱" | D | token |
| I-08 | 查询持仓 | "我现在亏多少" | D | - |
| I-09 | 询问解释 | "为什么 0xABC 买这个" | D | tx_hash or addr+token |
| I-10 | 模拟 | "假如我 1 小时前买 $100 现在多少" | D | token, amount, time |
| I-11 | 风险评估 | "这个 token 安不安全" | D | token |
| I-12 | 撤销 / 停止 | "取消刚才那笔 / 停所有 AI" | All | scope |

### §7.7.2 模糊场景处理

**场景 1:意图模糊** — "我想买点便宜的"

AI 识别 `intent=I-03 (discover)`, `missing_fields=[chain, criteria]`,反问:
```
"便宜"是哪种?
• 单价低(< $1)
• 市值小(< $1M,潜力大)
• 涨幅未启动(< 24h +20%)

另外,哪条链?
• Solana(meme 多)
• BSC(pump 阶段早)
• Base(蓝筹起步)
```

**场景 2:多 token 同名** — "买 $PEPE"

AI 检测到 SOL/ETH/Base 都有 $PEPE:
```
有 3 条链都有 $PEPE。你指:
• ETH 上的 PEPE(市值 $4.2B,蓝筹 meme)
• SOL 上的 PEPE(市值 $1.2M,pump 阶段)
• Base 上的 PEPE(市值 $80K,新生)

(默认猜:ETH,因为市值最大;如果 1 分钟无回复用此默认)
```

**场景 3:金额模糊** — "买一点"

```
你余额 $1200。"一点"是:
• 小试($50)
• 标准($200,约 1/6)
• 重仓($500,约 1/2)
还是直接说金额?
```

**场景 4:时间模糊** — "如果跌了就卖"

```
"跌了"指:
• 跌破成本(即亏损时)
• 跌 X%(请告诉我百分比)
• 跌破支撑位(我会自动识别 1d 支撑)
```

**场景 5:相对意图** — "跟刚才那个鲸鱼一样的策略"

AI 拉历史 context,确认:
```
你说的是 0xABC(你 14:23 跟单过的)?要为他设置自动跟单:
• 比例 5%(默认)
• 单笔上限 $300
• 日上限 $1500
对吗?
```

### §7.7.3 不识别的兜底文案

3 级降级:

**Level 1**(部分识别):"我大致明白你想'做点什么 SOL 上的事',但具体是想买、卖、还是看?"

**Level 2**(完全不识别 + 检测到关键词):"我看到你提到 $WIF。你想:• 买 $WIF • 卖 $WIF • 看 $WIF 的行情 还是别的?"

**Level 3**(完全不识别):"没听懂这句。可以试试:'买 $200 的 $WIF' / '现在 SOL 上有什么热度高的' / '我现在亏多少'。或者说'帮助'看完整命令列表。"

### §7.7.4 多轮对话回填

**机制**:
- 每个 `intent` 缺字段 → 进入 "fill-in 队列"
- 每问一次只问 1 个最重要字段
- 用户回 → 填字段 → 检查是否还有缺 → 继续问 / 进入决策树
- 最多 4 轮(再多说明意图本身有问题,给兜底)

**会话状态保存**:
- `intent_session_id` 60s TTL
- 用户中途插入新意图 → 旧 session 标记 abandoned,开新 session
- 用户重启 App → session 不恢复(避免被错乱填)

---

## §7.8 AI 解释能力(场景 + 模板)

> 每个决策都必须能解释。这是我们和 GMGN / Photon 最根本的差异。

### §7.8.1 10 个解释模板

**EXP-01 为什么选 Jupiter 不选 Raydium**:
> 我选 Jupiter v6,因为:
> 1. 流动性更深:Jupiter 聚合 18 个 DEX,$WIF 给出 $2.1M 深度,Raydium 单池只有 $480K
> 2. 预估输出更高:同样 $200 USDC,Jupiter 给 162.4 $WIF,Raydium 给 161.1 $WIF(多 0.8%)
> 3. 滑点更低:Jupiter 0.4%,Raydium 1.1%
> 综合下来 Jupiter 划算 $1.6(约 0.8%)。

**EXP-02 为什么滑点设 0.8%**:
> 滑点 = max(0.3%, 1h 波动率 × 1.5)
> $WIF 1h 波动率 0.53% × 1.5 = 0.8%。
> 设太低(0.3%):交易可能因价格瞬时跳动 revert。
> 设太高(2%):可能被 MEV 三明治拉走更多。
> 0.8% 是 24h 内 $WIF 同类交易的"成功率 95% + 滑点最小"的甜点。

**EXP-03 为什么现在执行不等**:
> 当前买卖比 1.4(订单簿买盘强),1m 内无 > $5K 的卖单。
> 历史看,类似订单簿状态下,立即执行的成交价比"等 30s"平均高 0.2%(说明等会涨)。

**EXP-04 为什么拒绝(HR03 命中)**:
> 拒绝理由:合约 owner 未弃权(HR03)。
> 这意味着部署者**仍可以**:
> - 暂停交易(你买完卖不出)
> - 修改税率(卖出时被收 99%)
> - 增发代币(稀释你的份额)
>
> 历史数据:HR03 命中的 token 中 73% 在 30 天内 rug。
> 如果你确实想买(朋友强推 / 已做尽调),请手动操作(不会经过本平台)。

**EXP-05 为什么 split 成 3 笔**:
> 你想买 $5000 的 $WIF。
> 当前流动性 $2.1M,单笔 $5000 占 0.24%。
> 直接打:滑点 1.8%,成本 $90。
> Split 3 笔($2K + $1.5K + $1.5K,间隔 30s):滑点 0.7%,成本 $35。
> 节省 $55。

**EXP-06 为什么不跟单这一笔**:
> 0xABC 刚买入 $WIF,但我没跟单。原因:
> 1. 当前 $WIF 流动性 $42K,你的策略要求 ≥ $50K(HR12)
> 2. 0xABC 这次买入额 $20K(高于他平均 $5K 4 倍)— 偏离他常规模式
> 跟单的本质是抄"模式"不是抄"数字"。这次不跟。

**EXP-07 为什么推荐买入 $80(不是更多)**:
> 你余额 $1200。我的建议规则:单 token 不超过组合 5%-10%(避免单点风险)。
> $80 ≈ 你余额 6.7%,符合中性配置。

**EXP-08 为什么这是好机会(评分 8.2)**:
> 评分 8.2/10 的拆解:
> - 流动性 8/10($2.1M,深度好)
> - 热度 7/10(24h +12%,但还在上升通道)
> - KOL 共识 8/10(3 个 KOL 1h 内提及)
> - 持仓分布 9/10(TOP10 仅 14%,分散)
> - 鲸鱼参与 7/10(2 个胜率 60%+ 鲸鱼今日买入)
> - 部署者信誉 9/10(30 天无 rug)
> - 合约安全 10/10(owner 已弃权 + 无 mint)

**EXP-09 为什么暂停跟单 0xABC**:
> 0xABC 近 3 笔交易:
> - $TOKEN1: -42%(24h 内)
> - $TOKEN2: -38%(12h 内)
> - $TOKEN3: -25%(6h 内)
> 累计亏损 -34%(远超他历史平均胜率)。
> 推断:他可能换了策略 / 钱包被盗用 / 在测试新模式。
> 已自动暂停跟单 24h。

**EXP-10 为什么紧急停止**:
> 你触发了"暂停所有 AI 操作"。我做了:
> 1. 取消 4 个 pending 半自动订单(id #1234-#1237)
> 2. 冻结 2 个模式 A 策略(鲸鱼跟单 / pump 抢跑)
> 3. 不影响:你已经持仓的 token(不会自动卖)
> 4. 不影响:你手动下的单
> 恢复时,请检查所有策略参数后再启动。

### §7.8.2 解释生成机制

- **快路径**(< 200ms):模板化解释,预填 placeholder
- **慢路径**(< 2s):LLM-Sonnet 生成长文解释(用户点"看更多解释"才生成)
- **预生成**:决策时把关键 fact 存进 Action Log,解释时只是从 fact 渲染(不重新调 LLM)

---

## §7.9 AI 不可越权场景列表(15 条精确规则)

| # | 触发条件 | AI 不可做 | 替代行为 |
|---|---|---|---|
| 1 | amount > max_position_usd(默认 $500) | 全自动直接执行 | 进 10s 半自动撤销窗口 |
| 2 | amount > $5000 | 半自动撤销 | 强制人工点确认(即使模式 A) |
| 3 | 首次跟单某新地址(< 7 天加入) | 自动执行 | 第 1 笔强制确认,之后自动 |
| 4 | 用户余额 < 单笔金额 110% | 执行(会失败) | 提前拒绝 + 推送充值 |
| 5 | 紧急停止后 | 任何动作 | 仅记录、不执行 |
| 6 | LLM 输出未通过 schema 校验 | 强行执行 | 拒绝 + 记 LOG + alert 后端 |
| 7 | §3 任一硬线命中 | 绕过 | 拒绝 + 解释 + 提示用户手动(不经平台) |
| 8 | 同一 token 5 分钟内 AI 已自动买 3 次 | 第 4 次自动 | 强制确认(防过热失控) |
| 9 | 单日累计已达日 cap | 继续自动 | 拒绝 + 推送"今日额度已满" |
| 10 | LLM 多轮自相矛盾(前后 2 次评分差 > 4) | 取平均执行 | 拒绝 + alert 后端(疑似 prompt 注入) |
| 11 | 用户连续 3 次拒绝同类型建议 | 继续推同类 | 30 天不推 + 让用户主动开关 |
| 12 | 钱包属于"长仓钱包"(用户标记) | 任何 AI 自动操作 | 仅模式 D 解释,不动手 |
| 13 | token 是用户白名单外(模式 A 时) | 买入 | 跳过 + 记 LOG |
| 14 | 当前时段不在用户允许时段 | 执行 | 等到时段开放 / 跳过 |
| 15 | LLM API 整体失败率 > 30%(5 分钟) | 继续依赖 LLM 决策 | 全局降级到"仅信号 + 风控"模式,模式 A 暂停 |

### §7.9.2 越权防御机制

**Layer 1 — Schema 强校验**:所有 LLM 输出必走 pydantic schema,违反即 reject

**Layer 2 — Hard Gate(trade_executor 入口)**:
```
if amount > user.max_position_usd:
    if mode == 'A':
        return enter_semi_auto_pending(...)  # 不直接执行
```

**Layer 3 — Audit 异步**:每笔执行后异步审计,违反规则 → alert + 人工 review

**Layer 4 — 用户可见**:紧急停止 + 单策略停止按钮 + Action Log 实时

---

## §7.10 AI 失败回退(精确)

### §7.10.1 单笔失败的级联

| 失败次数 | 触发场景 | AI 行为 | 用户感知 |
|---|---|---|---|
| 第 1 次 | tx revert / RPC timeout | 立即重试同参数 | 无感(< 5s) |
| 第 2 次 | 仍失败 | 滑点 +0.3% + 5s 后重试 | 推送"已重试 1 次..." |
| 第 3 次 | 仍失败 | 切换路由(Jupiter → Raydium)+ 5s 后重试 | 推送"已切换路由..." |
| 第 4 次 | 仍失败 | 放弃 + 标 fail + 完整 reason | 推送"3 次重试失败,已放弃" |

**特殊失败**:

| 类型 | 处理 |
|---|---|
| Honeypot 检测命中 | 0 次重试,直接 reject |
| 滑点超过用户上限 | 不自动加大滑点,等 30s 价格回归再试 1 次 |
| 余额不足 | 立即拒绝 + 充值提示 |
| 用户钱包私钥解密失败 | 拒绝 + 推送"请重新登录" |

### §7.10.2 系统级降级

| 系统状态 | 触发阈值 | 降级动作 | 用户文案 |
|---|---|---|---|
| LLM 失败率高 | 5 分钟内 > 30% | 模式 A 暂停 / B 退化为命令式 / C 跳过优化 / D 全停 | "AI 服务波动,已自动降级。可手动操作。" |
| §1 信号源延迟 > 60s | RPC 慢 | 模式 A 暂停信号驱动策略 | "信号链路延迟,跟单已暂停" |
| §4 路由全部不可用 | Jupiter / Raydium 都返 5xx | 拒绝所有新单 | "DEX 网络异常,请稍后" |
| §3 风控服务 down | 健康检查失败 | 拒绝所有新单(fail-closed) | "风控服务异常,为安全暂停所有交易" |
| 数据库延迟 > 1s | DB 慢 | 模式 A 暂停(无法可靠记 LOG) | "系统繁忙,AI 自动模式暂停 5 分钟" |
| 用户余额服务异常 | credit 服务 down | 拒绝所有新单 | "账户服务异常,请稍后" |

### §7.10.3 用户感知文案分场景

**正常重试**:`⏳ 第 1 次失败(链上拥堵),自动重试中...`

**降级路由**:`🔄 Jupiter 暂时不可用,切换到 Raydium 重试...`

**最终放弃**:`❌ 3 次重试失败。原因:链上 gas 过高。已恢复你的 USDC,未扣款。要 5 分钟后再试吗?`

**系统降级**:`⚠️ 检测到 AI 服务波动,已暂时关闭自动跟单。手动交易不受影响。预计 5-10 分钟恢复。`

**紧急停止**:
```
🛑 你已紧急停止所有 AI 操作。
✓ 已取消 4 个待执行订单
✓ 已暂停 2 个自动策略
⊘ 已持仓不动(如需平仓请手动)
```

---

## §7.11 AI Action Log(可追溯)

### §7.11.1 字段定义

每条 Action Log 必含:

```json
{
  "log_id": "uuid",
  "user_id": "uuid",
  "wallet_id": "uuid",
  "timestamp": "ISO 8601",
  "mode": "A" | "B" | "C" | "D",
  "trigger": {
    "type": "user_nl" | "user_ui" | "signal" | "follow" | "schedule",
    "source": "...",
    "raw_input": "..."
  },
  "intent": { "type": "I-01..I-12", "params": {...} },
  "decision_tree": [
    { "step": "T1", "result": "intent=I-03, conf=0.92", "duration_ms": 280 },
    { "step": "T4", "result": "HR_passed=18/18", "duration_ms": 45 },
    { "step": "T5", "result": "score=7.2", "duration_ms": 1200 },
    ...
  ],
  "tool_choices": {
    "router": { "selected": "jupiter_v6", "alternatives": [...], "reason": "depth+0.8%" },
    "slippage": { "value": 0.008, "reason": "vol*1.5" },
    "split": { "n": 1 }
  },
  "outcome": {
    "status": "success" | "rejected" | "failed" | "skipped",
    "tx_hash": "0x...",
    "amount_executed": 200.0,
    "actual_slippage": 0.0072,
    "gas_used_usd": 0.001,
    "platform_fee_usd": 0.01
  },
  "explain": {
    "short": "为你买入 $WIF $200,理由:...",
    "long_template_id": "EXP-08",
    "facts": {...}
  },
  "user_feedback": { "modified": false, "modifications": [], "rated": null }
}
```

### §7.11.2 用户主页展示

**Action Log 列表页**(路径 `/app/agent/log`):
```
┌──────────────────────────────────────────────────────┐
│  AI 行动日志                          [筛选] [导出]   │
├──────────────────────────────────────────────────────┤
│  ✅ 14:32  买入 $WIF $200    [模式 B]    +$12      │
│      理由:3 KOL 共识 + 流动性深 + 持仓分散 ▾       │
├──────────────────────────────────────────────────────┤
│  🔇 14:18  跳过 $XYZ          [模式 A]               │
│      理由:HR03 命中(owner 未弃权)▾               │
├──────────────────────────────────────────────────────┤
│  ❌ 14:10  跟单失败 0xABC     [模式 A]               │
│      理由:3 次重试后链上 gas 异常 ▾                │
├──────────────────────────────────────────────────────┤
│  ⏸️ 13:45  暂停跟单 0xDEF     [系统]                  │
│      理由:近 3 笔亏损 ▾                            │
└──────────────────────────────────────────────────────┘
```

点击 ▾ 展开完整决策树(树形展示 T1-T16 每一步)。

### §7.11.3 单条详情页

- 完整决策树可视化(mermaid 图)
- 当时的 token 状态快照(价格 / 流动性)
- 用户当时的 context(mode / balance / 已用额度)
- 真实链上 tx 链接(Solscan / BscScan)
- 复盘按钮:"24h 后看这笔 PnL"

### §7.11.4 可分享 / 可导出

**分享**:单条 → 一键生成图片卡片(含决策树 + 关键 fact + 我们的 watermark);用户分享到 TG / X 时自动带 referral 链接

**导出**:全量导出(CSV / JSON);按时间段 / 按模式 / 按结果筛选;API 导出(开放给重度用户做自己的分析)

---

## §7.12 用户授权模型

### §7.12.1 模式 A 预授权字段

```yaml
authorization:
  user_id: uuid
  wallet_ids: [uuid, ...]      # 哪些钱包可被 AI 动
  
  amount_limits:
    max_per_trade: 300         # 单笔上限
    max_per_day: 1500          # 日上限
    max_per_week: 7500         # 周上限
    
  token_constraints:
    whitelist: [...]           # 可选 — 只买这些
    blacklist: [USDT, USDC, ...] # 默认 — 不买这些
    
  time_constraints:
    timezone: "Asia/Shanghai"
    allowed_hours: [0-24]      # 默认全天
    
  source_constraints:
    follow_addrs: [...]        # 跟单地址
    signal_sources: [kol_a, ...] # 信号订阅
    
  risk_profile:
    sl_pct: 25                 # 止损百分比(0-90)
    tp_pct: 50                 # 止盈百分比
    max_concurrent_positions: 5 # 最多同时持仓数
    
  notifications:
    per_trade: true
    daily_summary: true
    
  expires_at: "2026-08-01"     # 强制过期重新确认
```

### §7.12.2 撤销授权(3 种粒度)

1. **单策略撤销**:策略卡片 → 删除 → 即时生效
2. **钱包级撤销**:钱包页 → "AI 不再操作此钱包" → 24h 缓冲(pending 单完成后生效)
3. **全局撤销**:紧急停止按钮 → 30s 内停所有

### §7.12.3 紧急停止按钮(关键 UI)

**位置**:每页顶部右上角,红色感叹号图标,永远可见

**触发后**:
1. T+0:按钮变 spinner,提示"正在停止..."
2. T+1s:所有 pending 半自动订单 cancel
3. T+5s:所有模式 A 策略 frozen
4. T+30s:完成。提示"已停止,附带状态报告"

**报告**:
```
✓ 已取消 4 个待执行订单
✓ 已暂停 2 个自动策略  
⊘ 你的 7 个持仓未动(如需手动平仓请去仓位页)

要恢复时点这里 [恢复 AI 操作]
```

**恢复**:
- 必须用户主动点"恢复"(不会自己醒)
- 恢复时弹"请检查所有策略参数后再启动"提示
- 默认:策略保持暂停态,用户挨个手动启动

### §7.12.4 强制重确认

**触发**:
- 授权超过 90 天 → 强制重新确认
- 用户长期未登录(> 30 天)→ 模式 A 暂停 + 重登时确认
- 用户更换主设备 → 模式 A 暂停 + 设备验证后恢复

---

## §7.13 AI 模型选型(LLM 层)

### §7.13.1 各场景模型分配

| 场景 | 模型 | 输入 token | 输出 token | 单次成本 | 频率 | 月成本/用户 |
|---|---|---|---|---|---|---|
| 意图识别(T1) | Haiku | ~1500 | ~150 | $0.0006 | 50/天 | $0.90 |
| 多轮回填问答 | Haiku | ~800 | ~100 | $0.0003 | 10/天 | $0.09 |
| 软线评分(T5) | Sonnet | ~3000 | ~300 | $0.0135 | 30/天 | $12.15 |
| 决策辅助(路由/滑点解释) | Sonnet | ~1500 | ~200 | $0.0075 | 30/天 | $6.75 |
| 长文解释(用户点开) | Sonnet | ~2500 | ~500 | $0.015 | 5/天 | $2.25 |
| 教练模式(D) | Sonnet | ~3000 | ~800 | $0.021 | 8/天 | $5.04 |
| 复盘(每日总结) | Sonnet | ~5000 | ~1000 | $0.030 | 1/天 | $0.90 |
| 多模型辩论(L3,仅大额) | Opus | ~4000 | ~600 | $0.105 | 0.5/天 | $1.58 |

**月度合计预估(中度用户)**:≈ $30/用户/月

**计费传递**:用户充值 USDC,按消耗扣(参照 R47 Credit System,万 5 markup)

### §7.13.2 模型选型原则

- **意图识别**:Haiku 够(pattern 识别 + 简单分类)
- **决策评分**:Sonnet(多因子综合判断)
- **解释生成**:Sonnet(长文表达力)
- **大额辩论**:Opus(amount > $5000 时启动 3 模型 vote,1 个否决即拒)
- **教练模式**:Sonnet(教学需要表达力,不必 Opus)

### §7.13.3 成本控制

- **缓存**:相同 token 1h 内的评分结果缓存(不重新调 LLM)— 注:此为"风险评分"缓存,与 §1.7 价格不缓存铁律不冲突
- **预生成**:热门 token 每 30 分钟批量评分一次
- **降级**:LLM 失败率高时,意图识别降到模板匹配(不调 LLM)
- **上限**:单用户单日 LLM 调用 cap(防滥用)

---

## §7.14 用户信任建立路径

### §7.14.1 新用户旅程(注册 → 模式 A)

```
Day 0:注册 + 充值
  └─ 默认模式 D(教练)
  └─ Onboarding 引导:浏览 5 个鲸鱼 + 看 AI 解释 5 次
  └─ Milestone 1:用户主动问 AI 第 5 个问题 → 解锁模式 B 提示

Day 1-3:模式 B(AI 建议 + 确认)
  └─ AI 主动推:1 个低风险候选/天
  └─ 用户至少确认 1 笔 → AI 出"24h 后复盘"
  └─ Milestone 2:累计 3 笔 + 至少 2 笔正收益 → 解锁模式 C 提示

Day 4-14:模式 C(用户主动 + AI 优化)
  └─ 用户主动下单,AI 优化执行参数
  └─ AI 在每笔后给"如果你用模式 A 跟单 0xXXX,今天会..."
  └─ Milestone 3:累计 20 笔 + AI 推荐采纳率 > 60% → 解锁模式 A 邀请

Day 15+:模式 A(全自动)
  └─ AI 邀请:"你已经手动 20 笔,要试试自动跟单一个鲸鱼吗(金额 ≤ $50/笔,3 天试用)"
  └─ 用户开始模式 A,cap 极小($50/$300)
  └─ 7 天后用户主动调高 cap → 真正的模式 A 用户

Day 30+:高频信任
  └─ 多策略并行 / 高 cap / 推荐给朋友(referral)
```

### §7.14.2 每阶段关键 milestone

| Milestone | 触发条件 | 解锁内容 | 推送文案 |
|---|---|---|---|
| M1 教练吸引 | 看 AI 解释 5 次 | 模式 B 提示 | "你好像挺爱研究的。要试试 AI 给你筛 token 吗?" |
| M2 首胜 | 模式 B 累计 3 笔 + 2 胜 | 模式 C 提示 | "你已经赚了 $X。要试试自己挑 token,让 AI 优化执行吗?" |
| M3 熟练 | 模式 C 20 笔 + 采纳率 60%+ | 模式 A 邀请 | "你已经是熟手了。要试试小额自动跟单($50/笔)吗?" |
| M4 信任 | 模式 A 7 天无紧急停止 | cap 调高建议 | "7 天稳定运行。可以考虑把单笔上限调到 $200" |
| M5 推荐 | 模式 A 30 天 + 累计 +30% | referral 邀请 | "你的 AI 跟单 +35%。分享给朋友拿手续费返佣?" |

### §7.14.3 信任失败兜底

如果用户在某阶段卡住:

| 现象 | 触发 | AI 行为 |
|---|---|---|
| 模式 B 累计 5 笔但全亏 | low_pnl | 主动反思:"最近推荐准确率低,原因可能是市场系统性下跌。建议暂时切回模式 D 学习。" |
| 用户连续点紧急停止 3 次 | low_trust | 弹"听起来 AI 让你不安。要做一次 1on1 设置检查吗" |
| 30 天未升级模式 | stuck | 不主动推(避免烦),仅 Dashboard 显示"想看下一阶段是什么吗" |

---

## §7.15 验收标准

### §7.15.1 功能验收(10 项)

| ID | 验收条件 | 验证方式 |
|---|---|---|
| AC-01 | 12 种意图全部支持 + 各 ≥ 90% 识别准确率 | NL 测试集 1000 条 |
| AC-02 | 4 种模式独立运行,模式间不串扰 | E2E 测试 |
| AC-03 | 决策树 16 step 全部跑通 + 每 step 有 LOG | trace 抽查 |
| AC-04 | Action Log 全字段完整 + 可导出 | CSV/JSON 导出验证 |
| AC-05 | 紧急停止 30s 内停所有 pending | chaos test |
| AC-06 | 模式 A 单笔 / 日 cap 不会被绕过 | fuzzing |
| AC-07 | 15 条不可越权规则全部命中 | 红蓝对抗测试 |
| AC-08 | 失败回退 1/2/3 级行为符合规范 | mock RPC 失败测试 |
| AC-09 | 系统级降级 6 种场景符合规范 | chaos test |
| AC-10 | LLM schema 校验 100% 强制 | 注入测试 |

### §7.15.2 体验验收(8 项)

| ID | 验收条件 | 测量方式 |
|---|---|---|
| AC-11 | 模式 B 用户首笔决策时间 ≤ 90s | 漏斗 |
| AC-12 | 模式 C 优化后实际滑点 < 用户手动 1.5x | 对比测试 |
| AC-13 | Action Log 打开率 ≥ 40% | 埋点 |
| AC-14 | NPS(信任度)GA+90 天 ≥ +10 | 季度调研 |
| AC-15 | AI Override Rate ≤ 25% | 埋点 |
| AC-16 | 模式 A 月留存 ≥ 60% | 留存分析 |
| AC-17 | 解释长文用户满意度 ≥ 4/5 | 内置评分 |
| AC-18 | 紧急停止月触发率 ≤ 0.5% | 埋点 |

### §7.15.3 性能验收(5 项)

| ID | 指标 | 目标 |
|---|---|---|
| AC-19 | 意图识别 p95 | ≤ 500ms |
| AC-20 | 完整决策树(B/C 模式 T1-T11)p95 | ≤ 5s |
| AC-21 | 模式 A 信号触发到执行(T1-T13)p95 | ≤ 90s |
| AC-22 | Action Log 写入 p99 | ≤ 200ms |
| AC-23 | 紧急停止响应 p99 | ≤ 30s |

---

## §7.16 监控埋点

### §7.16.1 信任度量化埋点

**事件级**:

| event | 字段 | 用途 |
|---|---|---|
| `agent.intent.detected` | intent_type, confidence, mode | 意图分布 |
| `agent.intent.clarification_needed` | missing_fields | 模糊度 |
| `agent.decision.tree_completed` | duration_ms, score, outcome | 决策性能 |
| `agent.recommendation.given` | candidates_count, top_score, mode | 推荐质量 |
| `agent.recommendation.accepted` | latency, modified | 用户认可率 |
| `agent.recommendation.rejected` | reason | 失败原因 |
| `agent.recommendation.modified` | original, modified | 改单率 |
| `agent.execution.started` | mode, amount_usd | 执行起点 |
| `agent.execution.success` | tx_hash, slippage | 成功率 |
| `agent.execution.retry` | retry_count, reason | 失败模式 |
| `agent.execution.failed` | reason, total_retries | 最终失败 |
| `agent.explain.opened` | log_id, mode | 解释关注度 |
| `agent.explain.shared` | log_id, channel | 病毒系数 |
| `agent.kill_switch.triggered` | scope, reason_freeform | 信任危机 |
| `agent.policy.upgrade` | from_mode, to_mode | 模式升级 |
| `agent.policy.downgrade` | from_mode, to_mode, reason | 信任倒退 |

**周期级(小时)**:

| metric | 计算 |
|---|---|
| `agent.acceptance_rate` | accepted / (accepted + rejected) |
| `agent.modification_rate` | modified / accepted |
| `agent.success_rate` | execution.success / execution.started |
| `agent.kill_switch_rate` | kill_switch.triggered / DAU |
| `agent.mode_distribution` | { A: x%, B: y%, C: z%, D: w% } |

### §7.16.2 NPS 调研埋点

**触发**:
- 用户首次模式 A 7 天后弹问卷
- 季度对所有 30 天活跃用户弹问卷
- 紧急停止后 3 天弹"为什么停"

**问题**:
1. (NPS) 你愿意把日交易额 50% 以上交给 AI 全自动吗(0-10)
2. (满意度) AI 推荐的 token 准确率(1-5)
3. (解释清晰度) AI 给的理由清楚吗(1-5)
4. (信任) 你信任 AI 不会越权吗(1-5)
5. (开放) 一句话最不爽的事 → 文本

### §7.16.3 异常报警

| 异常 | 阈值 | 动作 |
|---|---|---|
| LLM 失败率 5min | > 30% | PD 报警 + 自动降级 |
| 紧急停止暴增 | > 1% DAU/h | PD 报警 + 排查 |
| 模式 A 单日亏损率 | > 30% 用户当日 -10% | PD 报警 + 暂停新模式 A 注册 |
| AI Override Rate 突增 | > 40% | 排查推荐质量 |
| Action Log 写入失败 | > 0.1% | PD 报警 + 拒绝新单 |

### §7.16.4 数据看板

**实时**:当前在跑模式 A 策略数 / 每分钟决策数 / LLM 调用数 / 成功率
**日报**:模式分布 / 准确率 / 紧急停止次数 / 升降级 / NPS 趋势
**周报**:信任度增长 / 留存曲线 / 模式 A 渗透率 / 单 token 异常

---

## §7.17 关键风险与对冲

| 风险 | 影响 | 对冲 |
|---|---|---|
| LLM 输出注入攻击(用户输入诱导越权) | 高 | schema 强校验 + 多层 hard gate + audit |
| 单一 LLM 服务故障 | 高 | 多 provider 切换(Anthropic primary + OpenAI backup) |
| 模式 A 用户被恶意鲸鱼 sandwich | 中 | 跟单冷却 + 鲸鱼信誉评分 |
| AI 推荐引发监管争议("你在给投资建议") | 高 | 模式 D 必须明示"教学非投资建议" + ToS 明确 |
| 用户对 AI 失败容忍度低 | 中 | 紧急停止 + 透明 LOG + 失败时无扣费 |
| LLM 成本爆炸 | 中 | 缓存 + 降级 + 单用户日 cap |

---

## §7.18 路线图

### V1(GA)
- 模式 A / B / C
- 12 意图识别
- 完整决策树
- Action Log
- 紧急停止 + 预授权

### V1.5(GA+30 天)
- 多轮对话回填强化
- 解释模板扩到 20 个
- 跨钱包分权细化

### V2(GA+90 天)
- 模式 D(教练)
- 用户信任 milestone 系统
- 多模型辩论(L3)
- AI 主动推送(基于历史偏好)

### V3(GA+180 天)
- 用户自定义 prompt(高级用户写自己的策略 prompt)
- AI Action 分享卡片(社交分发)
- referral 网络
- 跨链 intent(Universal X 同类能力)

---

> **本章是产品最大差异化卖点**。前面 6 个模块决定我们能不能做事,§7 决定**用户为什么选我们而不是 Axiom / FOMO / GMGN**。
> 
> 一句话总结:**别人在做"AI 帮你下单的工具",我们在做"AI 作为你交易代理人的关系"**。
# §8 总验收标准 + 关键 KPI

## 8.1 上线条件(GA Gate)

每个模块达到自己的验收 + 整体满足:

| 维度 | 目标 |
|---|---|
| 单笔交易端到端成功率 | ≥ 95% |
| 单笔平均成本(滑点 + gas + 桥费)| ≤ 行业聚合器 1.2x |
| 蜜罐 / 黑名单拦截覆盖 | ≥ 99% |
| AI 自动交易 24h 内累计错误数 | < 0.5% 总笔数 |
| 用户 30d 留存 | ≥ 30% |
| 用户主动开启自动模式占比 | ≥ 20% |
| NPS | ≥ 30 |

## 8.2 商业 KPI

| KPI | MVP | V1 | V2 |
|---|---|---|---|
| DAU | 100 | 1,000 | 10,000 |
| 日交易笔数 | 200 | 5,000 | 50,000 |
| 日交易额 | $10K | $500K | $5M |
| 平台费收入(0.1%)| $10/天 | $500/天 | $5K/天 |
| AI 自动交易笔数占比 | 5% | 25% | 50% |

## 8.3 技术 KPI(不直接产品价值,但必达)

| KPI | 目标 |
|---|---|
| API 可用性 | 99.9% |
| 报价 P95 延迟 | < 800ms |
| 链上 tx 平均确认时长 | < 30 秒(EVM)/ < 8 秒(Solana)|
| 数据源延迟 | < 5 秒 |

---

# §9 路线图 — 谁在哪一阶段做什么

## 9.1 R49(MVP, 4 周)

| 模块 | 工作 | 负责 |
|---|---|---|
| 聚合 | Jupiter + Pump.fun + 1inch ETH 接入 | 后端 + PM |
| 路由 | 单跳 + 基础滑点 + EVM 默认 RPC | 后端 |
| 钱包 | 创建 + 导入(助记词)+ 转账 + 多钱包 5 上限 | App + 后端 |
| 跨链 | ❌ 不做 | — |
| 信号 | ❌ 不做 | — |
| 风控 | 黑名单 + 蜜罐(基础)| 后端 + 数据 |
| AI | 自然语言下单(模式 C) | 后端 |

## 9.2 R50(V1, 4-6 周)

| 模块 | 工作 |
|---|---|
| 聚合 | + BSC / Base / Arb |
| 路由 | + 拆单 + Flashbots/Jito MEV 防护 + 重试 |
| 钱包 | + WalletConnect + 私钥导入 + 生物识别 |
| 跨链 | + Wormhole + deBridge(2 桥)|
| 信号 | + 鲸鱼信号 + 大额异动 |
| 风控 | + 高税率 + 流动性 + 集中度 |
| AI | + 模式 B(建议 + 确认)+ 模式 A(全自动)|

## 9.3 R51-R52(V2 + GA, 4-8 周)

| 模块 | 工作 |
|---|---|
| 聚合 | + 0x + Raydium 直连 + Meteora |
| 路由 | + 自适应滑点 + 隐蔽拆单 |
| 跨链 | + Across + Axelar(共 4 桥)+ 桥健康度监控 |
| 信号 | + 聪明钱共识信号 + 自定义鲸鱼列表 |
| 风控 | + 用户反馈系统 + Chainalysis API |
| AI | + 教练模式(模式 D)+ Action Log 可分享 |

---

# §A 技术附录(给工程实施参考)

## A.1 接入 API 优先级清单

### A.1.1 聚合 API

| 服务 | 用途 | 优先级 |
|---|---|---|
| Jupiter Aggregator | Solana 主聚合 | P0 |
| 1inch v6 | EVM 主聚合 | P0 |
| Pump.fun 直连(Solana 合约调用)| meme 币早期 | P0 |
| 0x (Matcha API) | EVM fallback | P1 |
| Aerodrome(Base 直连)| Base 链原生 | P1 |
| Pancake V3(BSC 直连)| BSC 链原生 | P1 |
| Camelot(Arb 直连)| Arb 原生 | P2 |

### A.1.2 跨链桥 API

| 服务 | 用途 | 优先级 |
|---|---|---|
| Wormhole SDK | Solana ↔ EVM | P0 |
| deBridge / DLN API | 全场景 fallback | P0 |
| Across | EVM ↔ EVM 快速 | P1 |
| Axelar SDK | 多链冷场景 | P2 |

### A.1.3 数据 API

| 服务 | 用途 | 优先级 |
|---|---|---|
| Helius | Solana 链上数据 + 增强 RPC | P0 |
| Alchemy / Infura | EVM 增强 RPC | P0 |
| Birdeye / DexScreener | 多链聚合数据 + 流动性 | P0 |
| Chainalysis | 黑名单 + 风控 | P1 |
| Etherscan / Solscan API | 标签 + 元数据 | P1 |

### A.1.4 MEV 防护

| 服务 | 用途 | 优先级 |
|---|---|---|
| Jito Block Engine(Solana)| Solana MEV 防护 | P0 |
| Flashbots Protect RPC(ETH)| ETH 私有内存池 | P0 |
| bloXroute(BSC)| BSC 防夹 | P1 |

## A.2 关键数据契约

### A.2.1 报价请求 / 响应

**请求字段**:
```
chain          - 链(solana/eth/bsc/base/arb)
in_token       - 输入 token 地址
out_token      - 输出 token 地址
in_amount      - 输入数量(精度按 token decimals)
slippage_bps   - 滑点(basis points,500 = 5%)
user_addr      - 用户地址
```

**响应字段**:
```
out_amount         - 预计输出
price_impact_pct   - 价格冲击 %
route              - 路径(数组,每跳 dex/pool)
gas_estimate       - 预估 gas(链原生币 单位)
fees_breakdown     - { dex_fee, protocol_fee, network_fee }
quote_expires_at   - 报价过期时间(UNIX 时间戳)
risk_flags         - [] | ['low_liquidity'] | ['high_tax']
```

### A.2.2 路由决策输入

```
quote_options[]    - 多家报价
user_preference    - 'fast' | 'best_price' | 'private'
amount_usd         - 美元金额
token_metadata     - { liquidity, holder_top10, ... }
regime             - 当前市场状态
```

**决策输出**:
```
chosen_quote_id    - 选哪一家
should_split       - 是否拆单
split_count        - 拆几笔
mev_protection     - 'jito' | 'flashbots' | 'none'
priority_fee       - 优先费(链单位)
```

### A.2.3 风控筛入参 / 出参

```
入:
  recipient_addr   - 收方地址(转账场景)
  token_addr       - token 地址(交易场景)
  amount_usd       - 金额
  user_id          - 用户 ID

出:
  decision         - 'pass' | 'warn_soft' | 'warn_hard' | 'reject'
  reason           - 拦截原因
  evidence         - 数据依据
  bypassable       - 是否可二次确认绕过
```

## A.3 关键决策树伪代码(给后端参考思路)

### A.3.1 路由选择决策树

```
input: quote_options[], user_preference

1. 滤掉过期报价(quote_expires_at < now)
2. 滤掉风控不通过的 DEX(蜜罐 / 黑名单)
3. 按 user_preference 排序:
   - fast      → 最快确认
   - best_price → out_amount 最大
   - private   → MEV 防护强的
4. 选 top 1
5. 如果 out_amount 比次优低 < 0.1% → 选第二便宜的(避免单点依赖)
```

### A.3.2 拆单决策树

```
input: amount_usd, token_liquidity, token_24h_volume

if amount_usd > 5000 OR
   amount_usd > token_liquidity * 0.1 OR
   amount_usd > token_24h_volume * 0.1:
   → split = True
   split_count = ceil(amount_usd / 1000)  # 每笔约 $1000
   split_interval = 5 + random(0, 25) seconds  # 5-30 秒错峰
else:
   → split = False
```

### A.3.3 滑点动态推荐

```
input: token_meta, regime

base_slippage =
  major_token: 0.5%
  liquidity > 1M: 1%
  liquidity > 100k: 2%
  liquidity > 10k: 3%
  else: 5%

multiplier =
  regime == CRISIS: 1.5
  token_24h_volatility > 50%: 1.3
  else: 1.0

final_slippage = base_slippage × multiplier
return min(final_slippage, 10%)  # 最大不超过 10%
```

## A.4 缓存与限流(给后端参考)

### A.4.1 缓存层

| 数据 | TTL | 存储 |
|---|---|---|
| 主流币报价 | 5 秒 | 内存 LRU |
| Meme 币报价 | 2 秒 | 内存 LRU |
| Token 元数据 | 24 小时 | Redis |
| 黑名单 | 4 小时 | Redis + 持久化 |
| 鲸鱼地址列表 | 1 小时 | Redis |

### A.4.2 限流

| 端点 | 限制 |
|---|---|
| 报价 API | 每用户 60 次 / 分钟 |
| 下单 API | 每用户 10 次 / 分钟 |
| 信号订阅 | 每用户 5 次 / 分钟 |
| 黑名单查询 | 每用户 100 次 / 分钟 |

## A.5 测试矩阵(给 QA 参考)

### A.5.1 单元测试

- 每个 §决策树 ≥ 30 个 case
- 每个数据契约的边界 / 异常 / 并发

### A.5.2 集成测试

- 每条链端到端 1 笔(测试网):创建钱包 → 报价 → 路由 → 签名 → 上链 → 验证到账
- 跨链测试(Solana ↔ Base 是基线)
- 各种失败场景:RPC 死、滑点炸、桥失败

### A.5.3 性能测试

- 100 并发用户报价,P95 < 800ms
- 信号推送 1000 用户同时收,< 5 秒全部到达

### A.5.4 风控压测

- 黑名单 10 万条命中实时查询
- 蜜罐检测准确率(用 100 个已知样本验证)

### A.5.5 安全测试

- 私钥加密 / 解密一致性
- API 鉴权所有路径
- SQL 注入 / 重放攻击
- 钱包合约函数白名单(防恶意签名)

## A.6 监控 + 告警

### A.6.1 必有监控

| 指标 | 阈值 |
|---|---|
| 报价 P95 延迟 | > 1.5s 告警 |
| 路由失败率 | > 5% 告警 |
| 链上交易成功率 | < 95% 告警 |
| 数据源延迟 | > 60s 告警 |
| 黑名单命中率 | 异常飙高/降低告警 |

### A.6.2 业务监控

| 指标 | 用途 |
|---|---|
| AI 自动交易笔数 / 总笔数 | 看用户信任度 |
| 用户主动撤销 AI 决策的比例 | 看 AI 决策质量 |
| 跟单胜率 | 看信号质量 |
| 跨链失败率(按桥)| 看哪个桥不靠谱 |

---

# §B 关联文档与依赖

## B.1 上游(本 PRD 依赖的)

- **数据团队** — 提供链上数据流(§5.4 清单)
- **风控团队** — 提供黑名单 / 蜜罐数据库(§6.5)
- **合规团队** — 确认 OFAC 接入合规

## B.2 下游(依赖本 PRD 的)

- **App / 前端团队** — 按本文档 UI 流程实施
- **客服团队** — 准备用户问"为什么交易失败"的话术库
- **运营团队** — 按 KPI 设监控大盘

## B.3 不在本 PRD 范围(由其他独立文档负责)

- 私钥加密技术细节 — 安全文档(独立项目)
- 算力 / 计费 — 独立体系
- 多语言 i18n — 前端文档
- 法务声明 — 法务文档

**再次强调**:本 PRD 是全新动作。其他文档存在与否不影响本文档的实施可行性。

---

# §C 不在本次范围(明确排除)

- ❌ 限价单 / 永续 / 期权 — V3+ 考虑
- ❌ NFT 交易 — 不在产品定位
- ❌ 法币入金 — 已有体系
- ❌ 借贷 / staking — 不在交易底座范围
- ❌ 自定义合约 ABI 调用 — Pro 功能,V3+
- ❌ 隐私交易(Tornado / Aztec)— 法律灰区,不碰

---

# §D Open Questions(等 review)

1. **桥健康度评分如何客观量化** — 数据团队 + 风控 review 后定
2. **AI 自动模式的最大单笔上限** — 跟法务 + 商务 review($5k? $10k? 或不设)
3. **多桥聚合的优先级算法** — 工程师评估 deBridge / Wormhole API 性能后定
4. **MEV 防护是否对 BSC 真有效** — 数据验证完再说
5. **第一批接入的"鲸鱼地址"列表** — 数据团队定义
