# 23 — AI 技术路线图:预测 / Embedding / Retrieval / 时序

> **文档身份**:产品 PRD + 技术路线图(资深 Web3 交易产品专家 × 资深 Agent PM 视角)
> **目的**:回答一个具体问题 — **预测模型、Embedding、Retrieval、时序模型** 在 Agent-Trading 这个 Web3 交易 Agent 里**具体怎么用**?
> **不是**:不是写代码的 sprint,不是 vendor 选型 PoC,不是模型训练计划。**这是产品 + 工程的"我们做啥 / 为什么 / 数据够不够 / 怎么排优先级"。**
> **创建时间**:2026-05-14
> **关联**:`04-agent-spec.md`(Agent 主架构)/ `06-memory-spec.md`(3 层记忆)/ `IMPLEMENTATION-AUDIT.md`(设计 vs 代码对齐)

---

## 0. 为什么 Web3 交易 Agent 的 AI 跟传统量化不一样

如果直接把 BTC/股票圈那一套 ML 思路搬过来,99% 会翻车。这是底层差异:

| 维度 | 传统量化 / 股票圈 | Web3 / meme 交易 Agent |
|---|---|---|
| **数据噪音比** | 中等(S&P 500 日线噪音小) | 极高(meme 币 90% 半衰期 < 7 天,大量 rug / pump-and-dump) |
| **主数据源** | Bloomberg Terminal / Refinitiv | DexScreener + Helius + The Graph + 链上 RPC + Twitter |
| **信号维度** | 价格 + 成交量 + 财报 / 宏观 | 价格 + 成交量 + **KOL 提及** + **聪明钱地址** + **持币地址分布** + **流动性锁定状态** + **社媒情绪** |
| **风险敞口** | -50% 是大跌 | 可瞬间归零(rug / 流动性撤池) |
| **用户 JTBD** | "BTC 日内 ±0.5% alpha" | "找下一个 BONK / TRUMP 早期上车" |
| **MEV / 抢跑** | 不存在 | 所有公开的价格预测信号会被 MEV bot 截胡 |
| **数据延迟容忍度** | 秒级足够 | meme 段秒级也可能晚 3 个区块(已被先吃) |

**对 AI 设计的推论**:
1. **价格短期方向预测** 在 meme 段的真 alpha **接近零**(信号被截胡),做了也是给用户看 UX。把这种放低优先级。
2. **聪明钱模仿 / KOL 信号转化** 的 ML 才是项目独有的 alpha 来源。
3. **rug pull 预测 / 风险预警** ROI 极高 — 因为用户每避免一次归零,信任度暴涨。
4. **Memory + Retrieval** 是产品差异化护城河 — Photon / GMGN / Axiom 都没做"Agent 记得用户上次决策"。
5. **可解释性**(SHAP / 关键特征)是上线门槛 — 用户不会信"AI 说 rug"这种黑盒。

---

## 1. 项目当前 AI 能力基线

实摸代码 + docs 后(2026-05-14):

| 维度 | 实施度 | 实现方式 | 关键文件 |
|---|---|---|---|
| **Memory 3 层 + 反思引擎** | ✅ 已上线 | 纯文本 + 元数据评分(trigger+chain+regime+freshness 加权);**无 embedding** | `agent/memory/{working,episodic,semantic,reflection}.py` |
| **Retrieval 框架** | ⚠️ 框架在,**没接入决策链** | `episodic_memory.search()` 方法存在但 `chat_loop` / `thesis_loop` 没调用;无 FAISS / pgvector | `agent/memory/episodic_memory.py` |
| **预测模型** | 🟡 局部 | `hot_scorer.py` 规则评分(M50+Q30+P20);`ml_scorer.py` XGBoost 二分类(0-100 分);pump_scanner 纯 if-else | `hot_scorer.py` / `ml_scorer.py` / `agent/regime_detector.py` |
| **时序模型** | 🟡 局部 | `regime_detector.py`:CUSUM(变化点)+ HMM(4 状态)+ LLM(切换时);**只用于 regime 分类,无收益/价格/半衰期预测** | `agent/regime_detector.py` |
| **数据资产** | ✅ 充足 | 39 张 Supabase 表 + 8 张本地 PG;`token_performance` 秒级时序 + `agent_executions` 含 outcome + `agent_memory` 已分 episodic/semantic | `migrations/*.sql` |

**根本判断**:框架 70% 在,**缺 3 件事**:
1. **Embedding** — 一行没用
2. **Retrieval 调用链** — search() 方法在,没真在决策前 retrieve
3. **时序预测标签 / 模型** — 只用了无监督 HMM,没用监督学习预测收益

**不是从零起步,是把现成的串起来。**

---

## 2. 预测模型(Predictive ML)— 5 个高 ROI 应用

### P1 · 代币"毕业后涨幅"分桶预测 ⭐ **P0 立刻做**

- **问题**:用户问"这个新币会涨吗",当前 Agent 只能引用 `hot_scorer` 评分(规则)或 `ml_scorer` 二分类(0-100,粒度太粗)。需要更可解释的分桶 + 时间窗概率。
- **输入特征**(`token_performance` + `pump_tokens`):mcap / liquidity / holder N / 巨鲸入场率 / 早期 KOL 提及数 / chain / 创建后小时数 / 资金流入加速度
- **输出 / 标签**:7 天涨幅多分类 — `<-50% / -50~+50% / +50~+500% / >+500%`
- **模型**:LightGBM 多分类(比 XGBoost 在类不平衡下更稳)
- **样本量需求**:~5000 个代币历史 outcome(项目已沉淀够)
- **数据状态**:✅ 即用即跑
- **价值场景**:thesis 生成时,Agent 回答从"看起来不错"升级到"这个币 +500% 概率 8%,-50% 概率 42% — 你愿意接受这个赔率吗"
- **难度**:中(7-10 人天)
- **风险**:类不平衡 — 90% token 跌,需用 focal loss / class weight

### P2 · 聪明钱信号转化率预测

- **问题**:用户问"X 钱包刚买了 token Y,我要不要跟",当前 Agent 只看 `smart_wallets.tier` 标签(规则),不知道这个钱包**最近** 30d 实际跟单 PnL。
- **输入**:钱包 tier / 历史 30d 胜率 / 仓位 % / 持币时长分布 / 该钱包过去在该 chain 的命中率
- **输出**:该钱包买入后 24h token 涨跌方向(二分类)+ 期望涨幅(回归)
- **数据来源**:`smart_wallets` + `agent_executions`(谁跟单 / 结果)
- **难度**:中(7 人天)
- **优先级**:**P1**(聪明钱跟单是项目核心 alpha 来源)

### P3 · 入场胜率预测(给定策略 schema 估期望胜率)

- **问题**:用户写完策略 → "回测"是真历史回放,但回测只测**已有数据**。新策略上 paper 前,能不能预测"这个策略大概胜率几成"?
- **输入**:strategy.conditions JSON 特征化(信号源 / 阈值 / 风控参数)+ 当前 regime
- **输出**:未来 7d 该策略真触发次数 + 胜率
- **数据来源**:`agent_strategies` 历史 + 对应 `agent_executions`
- **难度**:**高** — 策略 schema 特征化是难点
- **优先级**:**P2**(数据少,等积累 1 季度真用户策略再做)

### P4 · Rug Pull 概率预测 ⭐ **P0 立刻做**

- **问题**:这是用户**每避免一次归零,信任度暴涨**的高 ROI 应用。当前 safety_engine 用规则(top 10 holder > 60% 拦)但漏报多。
- **输入**:持币 top10 占比 / LP 锁定状态 / 合约 owner 权限是否放弃 / 创建时间 / 巨鲸卖出节奏(过去 4h 净流出加速度)/ honeypot 检测结果
- **输出**:24h 内 rug 二分类 + 风险等级(low / medium / high / critical)
- **数据来源**:`token_performance` + `pump_tokens` + 需要补 `holder_distribution` 字段(从 Helius 拉)
- **难度**:中(10-14 人天)
- **可解释性 must-have**:SHAP 给"为什么判 rug"(top10 占比 X% + LP 不锁 + owner 还在 → 0.78 概率)
- **fallback**:模型置信度 < 0.6 → 走规则;> 0.9 → 直接 BLOCK 上链

### P5 · 滑点 / 价格冲击预测

- **问题**:用户拿到 Jupiter 报价但真成交常常少 1-3%(实际滑点)。能不能在下单前预测真滑点?
- **输入**:目标池子流动性 + 拟成交量 + 当前 mempool 拥堵 + 历史同池同时段滑点
- **输出**:预期实际 slippage_pct(回归)
- **数据来源**:DexScreener LP 时序 + Jupiter quote 历史 + 我们自己的 `agent_executions` 实际成交 vs 报价差
- **难度**:低(5 人天)
- **优先级**:**P1** — 配合 R64 priority_fee / jito_tip 决策,提升用户对成交质量信任

---

## 3. Embedding — 6 类向量化对象

### 为什么要 embedding(项目当前最大漏洞)

Agent-Trading memory 3 层都是**关键词 + 元数据评分**。意味着:
- 用户问"找个像 BONK 早期那样的币" → 关键词没"BONK"的 token 都召回不到
- thesis 生成"上次类似 token 你跟单 +48%" → 只能匹配元数据相同的 episode,语义相近的 miss
- 规则库召回"周五别交易 SOL 链" → 用户问"周末做 meme 安不安全",语义相关的规则查不到

**embedding 一旦上线,memory 3 层从"记得关键词"升级到"理解语义"。**

### 6 类向量化对象

| # | 对象 | 维度示例 | 用途 | 数据状态 |
|---|---|---|---|---|
| **E1** | **代币向量** | 链 + mcap bucket + holder 熵 + 巨鲸入场曲线 + 历史 regime 分布 + 早期 KOL 数 + 流动性轨迹 | "找跟 BONK 早期类似的当前代币" / 聚类发现 | ✅ token_performance 即用 |
| **E2** | **策略向量** | conditions JSON → text → embed | "你这条策略跟用户 X 类似,他后来调整了 stop_loss" | ⚠️ 真用户策略 < 100,数据攒一季度 |
| **E3** | **聪明钱钱包向量** | 行为模式 / 持币时长 / token chain 偏好 / 入场速度分布 | 找"潜在聪明钱"(行为类似但还没标签) | ✅ smart_wallets + on-chain |
| **E4** | **用户偏好向量** | 历史策略 + 提问 + 互动 | 个性化 thesis 语气 / 推荐相似用户的成功策略 | ⚠️ 真用户少 |
| **E5** | **Episode 经验向量** ⭐ | 过去交易复盘文本 embed | 真做 RAG(下一节) | ✅ episodic_memory 已 1000+ |
| **E6** | **Semantic 规则向量** | 规则文本 embed | retrieve 时按语义而非关键词 | ✅ agent_memory(type=semantic) |

### 技术选型

- **模型**:起步用 OpenAI `text-embedding-3-small`(1536 dim,$0.02/1M tokens)或 Voyage `voyage-3-lite`(中英文都好,价格友好)
- **不 fine-tune**:数据量 < 100K 时 fine-tune ROI 负;直接用 pretrained
- **存储**:Supabase 已支持 `pgvector` 扩展,开了即用;**不引** FAISS / Annoy / Qdrant 单独服务(架构复杂度收益不成正比)
- **维度**:1536 dim 对我们样本量 OK;>1M 行时考虑降维(PCA → 256 dim)
- **隐私**:用户策略 / 钱包 embedding 在 server 内做,**不要**把用户私密策略原文发给三方 embedding API(用 Voyage 的话走 server-to-server 加密通道)

### 优先级

- **立刻**:E5(episode 向量化)+ E1(代币向量)— 1-2 周
- **3 个月后**:E2(策略向量)+ E3(钱包向量)
- **6 个月后**:E4 / E6(等数据积累 + Memory shadow 阶段过了再上)

---

## 4. Retrieval / RAG — 5 个决策注入点 ⭐ **项目最高 ROI 改动**

### 为什么这是最高 ROI

当前 chat_loop / thesis_loop / multi_role_orchestrator **进 LLM 之前没 retrieve**:
- Episode 已有 1000+ 条 — 但 chat agent **看不到**
- 规则库已有 50+ 条 active rules — 但 thesis 生成时**没注入**
- 用户问"上次类似策略怎么样" — Agent **从头编造**(本质幻觉)

修这一个漏洞,**等于把已存的资产真用起来**,不需要训新模型。

### 5 个注入点

| # | 注入点 | retrieve 什么 | 喂给谁 | 工时 |
|---|---|---|---|---|
| **R1** | **chat 收策略请求** → 先 retrieve 过去类似策略(by 策略向量 + 当前 regime) | "过去 3 个月用户写过 8 个类似策略,平均胜率 32%,他们后来都加了 X 条件" | Opus 4.7 system prompt 注入 | 5-7 天 |
| **R2** | **thesis 生成** → retrieve "类似 token + 类似 regime 的 episode" | "上次 BONK 在 BREAKOUT regime 下,你跟单 +48%" | thesis_loop Sonnet | 3 天 |
| **R3** | **few-shot 示例选择** → 从 episodic 挑 3-5 个最相关 | 取代当前 prompt 里**固定的** examples(P04 / P05 等)| 所有 LLM 调用 | 4 天 |
| **R4** | **聪明钱跟单决策** → retrieve 该钱包过去 30d 真实 PnL | "这个钱包过去 30d 跟单亏 60%,要谨慎"| safety_engine pre-check | 3 天 |
| **R5** | **风险案例预警** → 策略上 paper 时 retrieve 历史失败案例 | "你这种 sl=30% slip=5% 的组合,过去 5 个用户上线后 4 个亏" | promote-to-live 二次确认 | 5 天 |

### 实施

- **不引 LangChain / LlamaIndex** — 项目当前自研 memory,API 设计很轻;LangChain 那套抽象会强加 Chain/Agent/Tool 概念,叠中间件越叠越乱
- **直接改**:`agent/memory/episodic_memory.py` 加 `embedding` 列 + `search_by_embedding(query_text, k=5, filter=...)` 方法
- **chat_loop / thesis_loop 决策前一行**:`hits = await episodic_memory.search_by_embedding(user_msg, k=5)` → 拼到 system prompt
- **migration 053**:`agent_memory ADD COLUMN embedding vector(1536)` + GIN/HNSW index
- **embedding worker**:cron 每小时把新写入的 episode batch embed(避免实时阻塞写)

### Wilson CI 验证

R1-R5 上线前 14 天 shadow 比对:
- Baseline = 不 retrieve 直接喂 LLM
- 试验组 = retrieve 后喂 LLM
- 度量:用户对 thesis 的"采纳率"(point or downvote) / 策略胜率
- 上线门槛:**Wilson CI 95% 下界 > baseline**(项目已有 shadow_mode_until 字段,复用)

---

## 5. 时序模型(Time-series)— 5 个应用

### T1 · 价格短期方向预测(15min / 1h ±%)

- **模型**:LightGBM with lag features / N-Beats / TS Transformer
- **数据**:token_performance 秒级
- **难度**:中等
- **老实告知**:meme 段 alpha **接近零**(信号被 MEV bot 截胡),做了主要是 UX("AI 看涨")而非真 alpha;**优先级 P3**(等其他都做完再说)

### T2 · 流动性时序预测 → 拆单决策

- **问题**:用户 $5K 单子拆 5 笔 vs 1 笔,什么时候哪种最优?当前 dex_router 拆单逻辑是规则(amount > threshold 直接拆)。
- **模型**:Prophet(简单)或 TS Transformer(精)
- **数据**:DexScreener LP 时序
- **价值**:大单成交滑点降低 0.5-2%(直接省钱)
- **难度**:中等(10 人天)
- **优先级**:**P2**(等 R64 priority_fee 真生效用一阵后再做)

### T3 · Regime 转换概率(当前 RANGING → BREAKOUT 多久) ⭐ **P1 复用现有 HMM**

- **问题**:Agent 当前能告"现在是 RANGING",但答不出"什么时候转 TRENDING"。
- **模型**:扩展现有 `regime_detector.py` 的 HMM 加 transition matrix 输出
- **数据**:已有 regime_detector
- **难度**:**低**(3 人天)— 直接改一行 `hmm.transmat_` 暴露出来
- **价值**:用户决策"我这策略要不要等转 TRENDING 再上"有数据支撑
- **优先级**:**P1**

### T4 · 策略半衰期(策略上线 N 天后 EV 衰减到 0)

- **问题**:用户问"我这条策略还能用吗" — **Agent 当前答不出**。这是用户最痛的盲区。
- **模型**:Cox 比例风险 / Weibull 生存分析
- **数据**:`agent_strategies` + `agent_executions`(需要 3+ 月真用户数据)
- **难度**:中(14 人天 — 含生存分析数据预处理)
- **价值**:**极高** — 直接回答用户最焦虑的问题
- **优先级**:**P1**(攒数据期间设计 / 上线在 Q3)

### T5 · 巨鲸/聪明钱集中度时序异常检测

- **问题**:在 rug 之前 1-3 天,巨鲸通常加速卖。当前 regime_detector 只看价格 CUSUM,**没看持币变化**。
- **模型**:扩展 CUSUM 加二阶(加速度),或者直接 isolation forest
- **数据**:smart_money_transfers + holder snapshot 时序
- **难度**:中(7 人天)
- **价值**:配合 P4 rug pull,双重风险预警
- **优先级**:**P1**

---

## 6. 优先级矩阵 — 产品 PM 拍板

```
                立刻可做 (数据够)             先攒数据 (1 季度后)
              ┌──────────────────────┐    ┌──────────────────────┐
   高 ROI ┃   R1-R5 RAG 注入 (P0)    ┃    ┃   P3 入场胜率预测     ┃
          ┃   P1 涨幅分桶预测 (P0)    ┃    ┃   T4 策略半衰期       ┃
          ┃   P4 rug pull (P0)        ┃    ┃                       ┃
          ┃   E1/E5 代币+经验向量(P0) ┃    ┃   E2 策略向量         ┃
          ┃   P2 聪明钱转化 (P1)      ┃    ┃   E3/E4 钱包/用户向量 ┃
          ┃   T3 regime 转换 (P1)     ┃    ┃                       ┃
          ┃   T5 巨鲸异常 (P1)        ┃    ┃                       ┃
   ━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━╋━━━━━━━━━━━━━━━━━━━━━━━┫
   低 ROI ┃   P5 滑点预测 (P1)        ┃    ┃   T1 价格短期方向     ┃
          ┃   T2 流动性时序 (P2)      ┃    ┃   E6 规则向量         ┃
          └──────────────────────────┘    └──────────────────────┘
```

### 3 期路线图

**Q1(立刻 ~ 6 周)**— 主题:**把现有资产真用起来**
- R1-R5 RAG 注入(5 个,3-4 周)
- E5 episode 向量化 + E1 代币向量(1-2 周)
- P1 涨幅分桶预测(1-2 周)
- P4 rug pull 预测(2-3 周)
- T3 regime 转换矩阵(3 天)
- **总工时**:~50-60 人天

**Q2(数据 1 季度后 ~ 4-6 周)**— 主题:**用真用户数据深化**
- T4 策略半衰期(14 天)
- P2 聪明钱转化率(7 天)
- T5 巨鲸异常(7 天)
- P5 滑点预测(5 天)
- E2 策略向量(5 天)

**Q3+** — 主题:**个性化 + 高阶时序**
- E3 钱包向量 / E4 用户偏好向量
- P3 入场胜率预测
- T1 价格短期方向(如果真有用户需求)
- T2 流动性时序

---

## 7. 工程落地节奏

| 项 | 工时 | 数据够? | 新依赖 | 风险 |
|---|---|---|---|---|
| R1 chat 决策前 RAG | 5-7 天 | ✅ Episode 1000+ | pgvector + voyage SDK | 低 |
| R2 thesis RAG | 3 天 | ✅ | 同上 | 低 |
| R3 few-shot 选择 | 4 天 | ✅ | 同上 | 中 — 改 prompt 框架 |
| R4 聪明钱 retrieve | 3 天 | ✅ | 同上 | 低 |
| R5 风险案例 retrieve | 5 天 | ⚠️ paper→live 历史 < 50 | 同上 | 中 — 数据有限 |
| E1 代币向量 | 4-5 天 | ✅ | pgvector | 低 |
| E5 Episode 向量化 | 2 天 | ✅ | 同上 | 低 |
| P1 涨幅预测 | 7-10 天 | ✅ token_performance | xgboost(已装)+ lightgbm | 中 — 类不平衡 |
| P4 rug pull | 10-14 天 | ⚠️ 需补 holder 分布 | xgboost + Helius SDK | 高 — 误报 = 拦了好币 / 漏报 = 用户归零 |
| T3 regime 转换矩阵 | 3 天 | ✅ | hmmlearn(已装) | 低 |
| T4 策略半衰期 | 14 天 | ❌ 需 3 月真用户数据 | lifelines | 中 |
| T5 巨鲸异常 | 7 天 | ✅ | scikit-learn(已装) | 低 |

### 不要做的事(明确边界)

- ❌ **不做大模型 fine-tune** — 在我们数据规模(< 100K)+ 预算下 prompt + RAG > fine-tune
- ❌ **不做价格短期高频预测** — meme 段被 MEV bot 截胡,投入产出比负
- ❌ **不引 LangChain / LlamaIndex** — 当前自研 memory 跟它们抽象冲突,叠中间件越叠越乱
- ❌ **不引独立向量 DB** — Supabase pgvector 够了,不上 Qdrant / Pinecone / Weaviate
- ❌ **不做主动 prompt engineering 比赛** — Anthropic 已经够强,做 RAG / 工具 > 改 prompt

---

## 8. 风险 + 隐私 + 安全

### 模型上线 4 道闸

每个 AI 特性上线前**必须**答:

1. **Baseline 是什么?**(当前规则 / 人工标注 / 现有简单模型)
2. **赢 baseline 多少 %?** Wilson 95% CI 下界 > baseline,**严格大于**,不是均值大于
3. **失败模式 + fallback?** 模型推理失败 / 置信度低 → 走规则 baseline
4. **可解释性?** rug pull / 聪明钱跟单这种高风险预测必须能给"为什么"(SHAP / 关键特征)

### Shadow Mode 必须

任何预测模型上线前,先 **14-30 天 shadow** 比对人工标注 / 现有规则:
- 项目已有 `shadow_mode_until` 字段(在 `agent_memory` 表),复用
- 度量:precision / recall / 用户采纳率 / 误报代价
- Wilson CI 下界 > baseline 才正式生效

### 数据漂移监测

- 每周对比模型输出分布 vs 训练时分布
- KL divergence > 阈值 → 触发告警
- meme 段 regime 切换频繁,漂移监测**必须**做(不像股票圈可以季度回看)

### Embedding 隐私

- 用户策略 / 钱包向量化 **在 server 内**完成
- 调用 OpenAI / Voyage 等三方 embedding API 时:
  - 用户私密策略原文**不直发**(脱敏 + abstract 化后再 embed)
  - 走 server-to-server 加密通道
  - 不在 client 端做 embedding(私钥泄露风险)

---

## 9. 度量 + 可观测性

每个 AI 特性必须出这些指标(沿用 `15-observability-tracing.md`):

| 指标 | P1 涨幅预测 | P4 rug pull | R1 chat RAG | T4 策略半衰期 |
|---|---|---|---|---|
| **Precision @ top decile** | ✅ | ✅ | — | — |
| **Recall** | ✅ | ✅(高优先) | — | — |
| **F1 / Brier score** | ✅ | ✅ | — | — |
| **用户采纳率**(downvote / upvote) | ✅ | ✅ | ✅(主指标)| ✅ |
| **模型推理 p95 延迟** | < 500ms | < 200ms | < 100ms | offline 不限 |
| **失败/降级率** | < 1% | < 0.1% | < 5% | — |
| **漂移指标**(KL) | 周报 | 周报 | 月报 | 月报 |

---

## 10. 跟项目现有架构的衔接 — 不破不立

### 不动(零冲突)

- 7 stage 共创流程(`agent/loops/chat_loop.py` 主路径)
- 18 个 Tool 框架
- 4 角色 multi_role_orchestrator(SafetyOfficer / Strategist / Auditor / Executor)
- Safety Engine 30 HR + 14 CB
- prompt_loader / pricing_loader 等基础设施

### 加(新文件,无破坏)

- `agent/ai/` 新目录
  - `embedding_service.py` — Voyage / OpenAI client + cache
  - `predictor_pump_outcome.py` — P1 涨幅分桶
  - `predictor_rug_pull.py` — P4 rug
  - `predictor_smart_money.py` — P2
  - `retriever.py` — R1-R5 公用 retriever
  - `timeseries_regime_transition.py` — T3
  - `timeseries_survival.py` — T4 半衰期

### 改(已有文件,小改动)

- `agent/loops/chat_loop.py` 进 LLM 前一行调 `retriever.fetch()`
- `agent/loops/thesis_loop.py` 同上
- `agent/memory/episodic_memory.py` 加 `search_by_embedding()` 方法
- `agent/safety_engine.py` rug pull / smart money 跟单时 pre-check
- `agent/trade_executor.py` 滑点预测注入大单决策(配合 R64)

### 数据迁移(零代码风险,先做)

- `migrations/053_pgvector_episodes.sql` — episodic_memory ADD COLUMN embedding vector(1536) + HNSW index
- `migrations/054_pgvector_tokens.sql` — token_embeddings 新表
- `migrations/055_holder_distribution.sql` — token_performance ADD COLUMN holder_top10_pct(给 P4 用)

---

## 11. 一句话总结

> **项目当前 AI 基线 ≈ 70% 框架在位,但 embedding / retrieval / 时序预测三块"空房间"。最高 ROI 是 R1-R5 RAG 把已有 1000+ episode 真用起来 + P4 rug pull 保用户钱 + E5/E1 向量化让 memory 从"记得关键词"升级到"理解语义"。不要追价格短期 alpha(被 MEV 截胡),不要 fine-tune,不要引 LangChain。Q1 用 6 周打通 RAG + 2 个预测模型,Q2 等真用户数据再做策略半衰期 / 聪明钱转化深化。**

---

## 12. 后续 SOP

本文档是路线图,不是单个 sprint。每个项目落地时:
1. 启 R 编号 sprint(沿用 R64 / R65 模式)
2. 写 `plans/` 单独 plan 文件
3. shadow mode 14-30 天比对
4. Wilson CI 通过 → 正式生效
5. 更新本文档对应模块的"实施度"

---

**附录 A:模型 / 数据资产对照表**

| 数据表 | 用途 | 行数级别 | AI 应用 |
|---|---|---|---|
| `token_performance` | 秒级价格 + 涨跌幅 | ~50M | P1 / T1 / T2 |
| `agent_executions` | 真实交易 outcome | ~10K | P2 / P3 / T4 |
| `agent_memory`(episodic) | 经验复盘 | ~1000 | R1-R3 / E5 |
| `agent_memory`(semantic) | 规则库 | ~50 | E6 |
| `smart_wallets` | 聪明钱标签 | ~2000 | P2 / E3 |
| `pump_tokens` | 新币池 | ~100K | P1 / P4 |
| `hot_coins` | 多链热币榜 | 每日 ~500 | (用于查询,非 AI) |

**附录 B:vendor / library 选型清单**

| 类别 | 推荐 | 备选 | 不选 |
|---|---|---|---|
| Embedding | Voyage `voyage-3-lite`(中英好) | OpenAI `text-embedding-3-small` | Cohere(贵)|
| Vector DB | **Supabase pgvector**(零新组件) | Postgres + pgvector self-host | Qdrant / Pinecone / Weaviate |
| Classifier | LightGBM(类不平衡稳)| XGBoost(已装) | sklearn RF(慢)|
| Time-series | Prophet(简单)/ darts | TS Transformer | TFT(复杂)|
| 生存分析 | lifelines | scikit-survival | — |
| 解释器 | SHAP | LIME(慢) | — |
| MLOps | 暂不引(单服务用 supabase 存 model artifact) | MLflow(Q3+ 再说) | Kubeflow |
