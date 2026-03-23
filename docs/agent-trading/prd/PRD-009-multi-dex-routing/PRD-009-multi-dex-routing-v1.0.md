# PRD-009: 多 DEX 执行路由

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-03-23 |
| 所属模块 | Phase 5（交易 Agent M10 + 优化 Agent O8） |
| 优先级 | P2 |
| 状态 | 待审批 |

---

## 一、调研背景

| 数据 | 来源 |
|------|------|
| MEME 币 Jupiter 比 OKX DEX 滑点少 ~50%（流动性 $50K-$500K 场景） | Carbium 2026 对比 |
| Jupiter 平均失败率 <0.5%，OKX DEX 未公布 | Jupiter 官方 |
| 1inch Pathfinder 评估数千条路由同时计算 | 1inch Review 2026 |
| 1inch Fusion 2.0 提供 MEV 保护（intent-based） | 1inch Docs |
| DEX 聚合器响应延迟 250-450ms（Jupiter/OKX/1inch） | Carbium benchmark |
| Raydium 直连 <100ms 但无路由优化 | Raydium Docs |

---

## 二、方案

### 当前 vs 目标

```
当前：OKX DEX Aggregator v6 单通道（所有链所有交易）
目标：
  SOL 链 → Jupiter 优先 → OKX fallback
  EVM 链 → 1inch 优先 → OKX fallback
  所有链 → 比价选优 + 自动切换
```

### 路由策略

```
async def execute_with_routing(chain, token, action, amount, slippage):
    # 1. 并行获取报价
    quotes = await asyncio.gather(
        get_primary_quote(chain, token, amount),    # Jupiter / 1inch
        get_okx_quote(chain, token, amount),        # OKX DEX
        return_exceptions=True,
    )

    # 2. 选择最优
    best = select_best_quote(quotes, slippage)
    # 最优 = min(price_impact) 且 estimated_output 最高

    # 3. 执行
    result = await execute_on_dex(best.dex, best.swap_data)

    # 4. 失败 → fallback
    if not result.success:
        fallback = [q for q in quotes if q.dex != best.dex and not isinstance(q, Exception)]
        if fallback:
            result = await execute_on_dex(fallback[0].dex, fallback[0].swap_data)

    return result
```

### DEX 集成

| DEX | 链 | API | 成本 | 集成方式 |
|-----|-----|-----|------|---------|
| **Jupiter** | SOL | `https://quote-api.jup.ag/v6` | 免费 | REST: quote → swap → sign |
| **1inch** | ETH/BSC/Base | `https://api.1inch.dev/swap/v6.0` | 免费（需 API Key） | REST: quote → swap → sign |
| **OKX DEX** | 全链 | 已有 | 免费 | 保持现有 |

### 大单拆分

```
如果 amount > 流动性的 2%：
  将大单拆成 N 笔小单（每笔 ≤ 流动性 1%）
  间隔 2s 执行
  减少价格冲击

示例：
  流动性 $50K，买入 $2K
  → 拆成 4 笔 × $500，间隔 2s
  → 总滑点从 ~4% 降至 ~1.5%
```

---

## 三、技术影响

| 文件 | 操作 |
|------|------|
| `agent/dex_router.py` | **新建** — 多 DEX 比价+路由+fallback |
| `agent/dex/jupiter.py` | **新建** — Jupiter v6 API 集成 |
| `agent/dex/oneinch.py` | **新建** — 1inch v6 API 集成 |
| `agent/trade_executor.py` | 修改 — 调用 dex_router 替代直接调 OKX |
| `config.py` | 修改 — +Jupiter/1inch API Key |
| `optimizer_tools.py` | 修改 — +tool_read_execution_quality（O8 全链路回测） |

---

## 四、成本

| 项目 | 月成本 |
|------|--------|
| Jupiter API | $0（免费） |
| 1inch API | $0（免费，需注册 Key） |
| 额外 RPC 调用 | ~$0（已有 Helius/公共 RPC） |
| **总新增** | **$0** |

**收益**：MEME 场景滑点减少 ~50% → 每月节省用户 $X（取决于交易量）

---

## 五、验收标准

- [ ] SOL 链交易优先走 Jupiter，失败自动切 OKX
- [ ] EVM 链交易优先走 1inch，失败自动切 OKX
- [ ] 两个报价并行获取，总延迟 < 1s
- [ ] 大单自动拆分（amount > 流动性 2%）
- [ ] 执行质量统计：滑点/失败率/路由分布

---

## 六、v1.1 审查修订

| # | 修订 | 原因 |
|---|------|------|
| Q8 | EVM 地址需 EIP-55 checksum 转换（to_checksum_address） | 1inch 需要 checksum address |
| Q9 | 1inch Key 可选配置，未配置跳过不阻塞 | 不应因 Key 缺失导致功能不可用 |
| Q10 | 并行报价总超时 2s，慢的不等直接用快的 | MEME 行情不等人 |
| Q11 | 大单拆分用 price_impact>2% 判断（不依赖流动性数据） | 流动性数据可能缺失 |
| Q12 | 每笔交易记录 dex_used/quote/actual_slippage + 优化 Agent 可读 | 路由决策需要可审计 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-23 | 初始版本 |
| v1.1 | 2026-03-24 | 审查修订：5 项优化 |
