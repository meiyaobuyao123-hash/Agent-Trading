---
name: 数据源选型原则
description: 各场景数据源优先级，避免用慢源替代快源
type: feedback
---

永远按以下优先级选数据源，不得降级使用慢源，除非快源明确不可用：

**聪明钱交易追踪（EVM链）：**
- ✅ 优先：`GET https://web3.okx.com/api/v5/wallet/post-transaction/transactions-by-address`
  - 参数：`chains=`（List，**不是** `chainIndex=`）
  - 必须加：`User-Agent: Mozilla/5.0`（否则 Cloudflare 403）
  - chainIndex: ETH=1, BSC=56, Base=8453
  - 响应结构：`data[].transactionList[]`（**不是** `tokenTransferDetails[]`）
  - 20 req/s，5s轮询，平均2.5s感知
- ❌ 禁止：`/api/v5/wallet/post-transaction/transactions`（需 accountId，不适合任意钱包监控）
- ❌ 禁止：`www.okx.com`（该域名对 Wallet API 返回403，必须用 `web3.okx.com`）
- ❌ 禁止：Etherscan/BscScan/Basescan 作为主力（5 req/s，30s轮询，平均15s感知，慢6倍）

**聪明钱交易追踪（SOL）：**
- ✅ 优先：Helius accountSubscribe WebSocket，~400ms感知
- ❌ 禁止：Helius REST polling getSignaturesForAddress 作为主力

**热币价格刷新：**
- ✅ OKX toplist（榜单内代币，2s刷新）
- ✅ OKX candles?bar=1s（榜单外代币，按地址查）
- ❌ 禁止：`refresh_okx_prices` 函数内用 DexScreener（函数名误导，实际是DexScreener）

**热币发现：**
- ✅ OKX toplist 多时间帧，4链并行
- DexScreener 仅作 fallback

**Why:** 用户多次要求最小时间粒度，每次执行时退回慢源是核心问题。OKX API Key已有，无需额外申请。

**How to apply:** 每次涉及数据源选型，先查此文件，不得在未说明理由的情况下使用慢源。
