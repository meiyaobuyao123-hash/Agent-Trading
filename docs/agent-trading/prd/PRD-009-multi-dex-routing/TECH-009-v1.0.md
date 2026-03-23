# TECH-009: 多 DEX 执行路由 — 技术方案

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-009 v1.1 |
| 创建日期 | 2026-03-24 |

---

## 一、文件结构

```
services/pump-scanner/
├── agent/
│   ├── dex_router.py                # 新建：多 DEX 比价+路由+fallback
│   ├── dex/
│   │   ├── __init__.py
│   │   ├── jupiter.py               # 新建：Jupiter v6 API (SOL)
│   │   └── oneinch.py               # 新建：1inch v6 API (EVM)
│   └── trade_executor.py            # 修改：调用 dex_router 替代直接 OKX
├── config.py                        # 修改：+Jupiter/1inch 配置
└── optimizer_tools.py               # 修改：+tool_read_execution_quality
```

---

## 二、dex_router.py

```python
"""多 DEX 路由 — 比价选优 + 自动 fallback + 大单拆分"""

QUOTE_TIMEOUT = 2.0  # 并行报价超时 2s（v1.1 Q10）
SPLIT_IMPACT_THRESHOLD = 0.02  # price_impact > 2% 拆分（v1.1 Q11）
MIN_SPLIT_AMOUNT = 20  # 最小拆分金额 $20

class DexRouter:
    async def execute(self, chain, token, action, amount, slippage, wallet, priv_key):
        # 1. 判断是否需要拆分
        if await self._should_split(chain, token, amount):
            return await self._execute_split(chain, token, action, amount, slippage, wallet, priv_key)

        # 2. 并行获取报价（2s 超时）
        quotes = await asyncio.wait_for(
            asyncio.gather(
                self._get_primary_quote(chain, token, amount, slippage),
                self._get_okx_quote(chain, token, amount, slippage),
                return_exceptions=True,
            ),
            timeout=QUOTE_TIMEOUT,
        )

        # 3. 选最优
        best = self._select_best(quotes)

        # 4. 执行
        result = await self._execute_on_dex(best, wallet, priv_key)

        # 5. 失败 → fallback
        if not result.success:
            fallback = [q for q in quotes if q != best and not isinstance(q, Exception)]
            if fallback:
                result = await self._execute_on_dex(fallback[0], wallet, priv_key)

        # 6. 记录路由决策（v1.1 Q12）
        self._record_routing(chain, token, quotes, best, result)
        return result

    async def _should_split(self, chain, token, amount):
        """v1.1 Q11: 用 price_impact 判断是否拆分"""
        try:
            quote = await self._get_primary_quote(chain, token, amount, "1")
            if isinstance(quote, dict) and quote.get("price_impact", 0) > SPLIT_IMPACT_THRESHOLD:
                return True
        except:
            pass
        return False

    async def _execute_split(self, chain, token, action, total_amount, slippage, wallet, priv_key):
        """大单拆分执行"""
        n = max(2, int(total_amount / MIN_SPLIT_AMOUNT))
        per_amount = total_amount / n
        results = []
        for i in range(n):
            r = await self.execute(chain, token, action, per_amount, slippage, wallet, priv_key)
            results.append(r)
            if i < n - 1:
                await asyncio.sleep(2)  # 2s 间隔
        # 合并结果
        ...
```

---

## 三、jupiter.py

```python
"""Jupiter v6 API — SOL 链最优 DEX 聚合器"""

JUPITER_BASE = "https://quote-api.jup.ag/v6"

class JupiterDex:
    async def get_quote(self, input_mint, output_mint, amount, slippage_bps):
        url = f"{JUPITER_BASE}/quote"
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": str(int(slippage_bps)),
        }
        # GET /quote → {outAmount, priceImpactPct, routePlan}

    async def get_swap(self, quote_response, user_public_key):
        url = f"{JUPITER_BASE}/swap"
        # POST /swap → {swapTransaction} (base64 encoded)
```

---

## 四、oneinch.py

```python
"""1inch v6 API — EVM 链最优 DEX 聚合器"""

ONEINCH_BASE = "https://api.1inch.dev/swap/v6.0"

class OneInchDex:
    def __init__(self):
        self._api_key = os.getenv("ONEINCH_API_KEY", "")  # v1.1 Q9: 可选

    async def get_quote(self, chain_id, from_token, to_token, amount):
        if not self._api_key:
            raise ValueError("1inch API key not configured")
        # v1.1 Q8: checksum address
        from eth_utils import to_checksum_address
        from_token = to_checksum_address(from_token)
        to_token = to_checksum_address(to_token)
        url = f"{ONEINCH_BASE}/{chain_id}/quote"
        # GET /quote → {toAmount, estimatedGas}

    async def get_swap(self, chain_id, from_token, to_token, amount, from_address, slippage):
        url = f"{ONEINCH_BASE}/{chain_id}/swap"
        # GET /swap → {tx: {to, data, value, gas}}
```

---

## 五、trade_executor.py 修改

```python
# execute_trade() 中替换直接 OKX 调用：

async def execute_trade(self, chain, token_address, action, amount_usd, ...):
    from agent.dex_router import get_dex_router
    router = get_dex_router()
    result = await router.execute(chain, token_address, action, amount_usd, slippage, wallet, priv_key)
    # 原有的记录逻辑保持不变
```

---

## 六、execution_quality 审计工具

```python
def tool_read_execution_quality(days=7):
    """优化 Agent 读取执行质量"""
    return {
        "by_dex": {
            "jupiter": {"trades": 45, "avg_slippage": 0.8, "fail_rate": 0.4},
            "oneinch": {"trades": 12, "avg_slippage": 0.6, "fail_rate": 0.8},
            "okx": {"trades": 30, "avg_slippage": 1.5, "fail_rate": 1.2},
        },
        "fallback_triggered": 5,
        "split_triggered": 3,
        "estimated_savings_usd": 45.20,  # vs 全部走 OKX
    }
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-24 | 初始版本（含 v1.1 审查修订） |
