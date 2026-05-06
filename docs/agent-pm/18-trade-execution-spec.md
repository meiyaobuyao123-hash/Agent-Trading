# 18 — 交易执行规范 (R42)

> **文档定位**:R42 实施周期权威规范。涵盖私钥管理、实盘/模拟盘控制、HITL 分层自动化、risk_params 真执行、止盈止损常驻 loop、WalletConnect 集成。
>
> **历史背景**:R36 audit 发现"trade_executor 不读 risk_params + position_monitor 不常驻 + KMS 占位",R42 全部修。
>
> **修订历史**:2026-05-05 R42 创建,作者 PM-lead

---

## 1. 私钥管理 — AES-256-GCM 加密存 DB(R42 P1 最终方案)

### 1.1 决策演化(三次推翻)

**v1 KMS 方案(R37 W3 原计划)的问题**:
- AWS/GCP KMS 按调用次数收费,key 月费 $1
- 即使在 KMS 里,服务器被黑仍可调 KMS API 用其身份解密
- 接入复杂(需要 IAM role / IAM policy / encrypt context)

**v2 WalletConnect 方案(2026-05-05 上午曾推荐,**已废弃**)的问题**:
- WalletConnect 每笔交易需用户在 Phantom App 点确认
- **跟 R42 P0.3 全自动化决策直接冲突**(用户希望真"自动驾驶",不要任何打断)
- 适合"NFT 单次签名"场景,**不适合自动化交易**

**v3 AES-256-GCM 加密存 DB(R42 P1 最终方案)**:
- 用户在 Flutter "导入私钥"输入框粘贴一次
- 后端 [agent/crypto_box.py](../../services/pump-scanner/agent/crypto_box.py) 用 master_key 加密 → 存 [user_wallets.encrypted_private_key](../../services/pump-scanner/migrations/local_pg/043_user_wallets.sql)
- 私钥**永不返给前端**(即使 list-wallets 返也只含 public_key)
- 每次交易 trade_executor → `routes_wallet.get_decrypted_wallet()` 解密 → 签名 → 立刻丢
- **全自动化**:用户不用点任何确认
- **完全免费**:本地 PG + cryptography Python 库

### 1.2 安全分析

| 攻击面 | 防御 |
|---|---|
| PG dump 单独泄漏 | 拿不出私钥(没 master_key) |
| master_key 单独泄漏(env 文件) | 拿不出私钥(没 PG) |
| **服务器被全黑**(同时拿到 PG + master_key) | 私钥可解 — 同 KMS / Vault 同问题 |
| 篡改 encrypted_blob | AESGCM auth tag 校验失败,decrypt 抛 InvalidTag |
| 重放攻击 | 每次加密用随机 nonce,blob 每次不同 |

**对比 KMS**:KMS 多一层硬件保护,但同样情况下 attacker 可用服务器身份调 KMS API。差距没那么大。

### 1.3 master_key 管理

```bash
# 生成新 master_key(32 字节 base64,只跑一次)
python3 -c "from agent.crypto_box import generate_new_master_key_b64; print(generate_new_master_key_b64())"

# 写入 .env(servers/.env;不入 git)
WALLET_MASTER_KEY=<output>
```

⚠️ master_key **永远不入 git**;改 master_key 必须**重加密所有 user_wallets**。

### 1.4 集成点

**Flutter**:
- [apps/app/lib/services/wallet_service.dart](../../apps/app/lib/services/wallet_service.dart) `importFromPrivateKey` → 本地 secure storage + 异步 `_pushWalletToBackend`
- [apps/app/lib/services/agent_service.dart](../../apps/app/lib/services/agent_service.dart) `importWalletToBackend` 调 POST `/api/wallet/import`

**后端**:
- [services/pump-scanner/agent/crypto_box.py](../../services/pump-scanner/agent/crypto_box.py) AES-256-GCM helpers
- [services/pump-scanner/api/routes_wallet.py](../../services/pump-scanner/api/routes_wallet.py) import / list / delete / set_default endpoints
- [services/pump-scanner/agent/trade_executor.py](../../services/pump-scanner/agent/trade_executor.py) `_resolve_wallet` 优先从 DB 拉(fallback .env)

**测试**:
- [tests/test_crypto_box.py](../../services/pump-scanner/tests/test_crypto_box.py) 16 单测(round-trip / 篡改 / 错 master_key / 边界)

### 1.5 异常处理

| 异常 | 处理 |
|---|---|
| master_key 未配置 | encrypt/decrypt 抛 RuntimeError(明显错,用户能修) |
| trade_executor 拉私钥失败 | fallback .env(过渡期);全失败 → trade 拒(返 success=False) |
| 用户首次导入未连后端 | 本地仍存(secure storage),后端推送失败 log warning |
| PG 不可用 | wallet/list 返空数组(不 crash);trade_executor 用 .env fallback |

### 1.2 集成方式

**Flutter 端**:
- pub.dev 包:`reown_walletkit` 或 `walletconnect_dart_v2`
- 加"连接钱包"按钮,支持 Phantom (Solana) / MetaMask (EVM) deep link
- 接收用户签名后的 tx hex,POST 回后端广播

**后端端**:
- `agent/dex_router.py` 改造:`execute_swap(strategy, user_id)` 返回:
  - 不再 `RUST_TRADE_WALLET_PRIVATE_KEY` 直接签
  - 而是构造 unsigned tx → 写入 `pending_signing_tx` 表 → 推送 Flutter
- 新 endpoint:`POST /api/agent/swap/sign-and-broadcast` 接收 Flutter 推回的 signed tx → 广播到 Solana RPC / EVM RPC
- `agent/kms_client.py` 加注释 "R42 弃用 — 用 WalletConnect 取代",代码暂留作 historical reference

### 1.3 异常处理

| 异常 | 处理 |
|---|---|
| 用户拒绝签名 | swap 标记 `user_rejected`,不消耗 quota |
| 60s 内未签 | 超时 → 撤销 pending,通知用户 |
| Phantom App 未安装 | Flutter 弹窗引导下载 |
| 签名后 RPC 广播失败 | 重试 3 次,失败 → 标记 `broadcast_failed` + 退款(全 paper) |

详细流程见 [docs/runbook/wallet-connect-flow.md](../runbook/wallet-connect-flow.md)

---

## 2. 实盘 / 模拟盘控制

### 2.1 模式定义

每个 `Strategy` 有 `mode` 字段:
- `paper`(默认):模拟盘,只记账不真买
- `live`:实盘,真用户钱

### 2.2 解锁 paper → live(用户主动 promote)

`POST /api/agent/strategies/{id}/promote-to-live` 必须满足全部条件:
1. 用户已连接钱包(WalletConnect handshake 成功;过渡期允许填私钥)
2. 已读 + 同意《免责声明》
3. 单笔金额 ≤ $50(可在策略详情手动调到 $500,见 §4)
4. 已勾选"我知道会亏钱"

### 2.3 强制保护(开实盘后系统自动加,用户不能关)

| 防护 | 阈值 | 触发动作 |
|---|---|---|
| 单日累计亏损 | > $200 | 强制锁回 paper + 推送通知 |
| 连续亏损笔数 | ≥ 3 | 自动暂停策略 |
| 30 天最大回撤 | > 30% | 强制锁回 paper |
| 单笔金额 | > 设定上限 | 拒绝下单 |

### 2.4 一键降回 paper

`POST /api/agent/strategies/{id}/demote-to-paper` 无条件成功,立即生效。

---

## 3. 全自动化 + 7 条兜底(取代 HITL 审批)

### 3.1 设计背景 + 用户决策

**原设计问题**:所有真金交易都强制 5/15/60min 审批。但 pump.fun 秒级机会等 5 分钟早飞了。

**R42 v1 (2026-05-05 上午)**:曾设计三档分层(auto/semi/manual),按金额自动判 + 用户覆盖。

**R42 v2 (2026-05-05 下午,与用户对齐)**:**完全废弃分层 + 不要紧急开关**。理由:
- 用户希望真"自动驾驶"体验,不要任何打断
- 三档过度复杂,用户决策成本高
- 只要兜底足够强,全自动是最佳产品形态

### 3.2 流程(4 步,无审批)

```
AI 找到机会 → 7 条兜底检查 → 通过则 trade_executor.execute_trade → 推送通知用户
```

### 3.3 7 条兜底防线

实现:[agent/hitl_router.py](../../services/pump-scanner/agent/hitl_router.py) `is_allowed_to_auto_execute()`

| # | 防线 | 触发 | 动作 |
|---|---|---|---|
| 1 | paper mode | mode == "paper" | **直接通过**(不消耗 daily cap) |
| 2 | 策略状态 | status in (archived, paused) | 拒,推送 "策略已暂停" |
| 3 | 单笔上限 | amount > strategy.max_position_usd(默认 $5,000) | 拒,推送 "单笔超限" |
| 4 | sell 豁免 | side == "sell" | **跳过 daily cap / 连亏 / 回撤检查**(止损必须能出货) |
| 5 | 单日累计 | 全 App 累计 > daily_auto_cap_usd(默认 **$50,000**) | 拒,明天 0 点重置 |
| 6 | 连续亏损 | strategy.consecutive_losses ≥ 3 | 策略自动暂停,推送 "已暂停" |
| 7 | 30 天回撤 | strategy.max_drawdown_pct_30d > 30% | 强制锁回 paper |

**额外继承**(已有,无需新加):
- `safety_engine` 30 HR + 13 CB(trade_executor 内部已 wire)
- `input_filter / cost_guard / output_filter`(R40+R41 chat 路径已 wire)
- `position_monitor`(R42 P0.1)单笔亏 > 50% 自动平仓

### 3.4 hitl_router 接口

```python
from agent.hitl_router import is_allowed_to_auto_execute, record_executed

# trade 之前 check
allowed, reason = is_allowed_to_auto_execute(
    user_id=user_id,
    strategy=strategy_dict,  # {id, status, mode, max_position_usd, ...}
    amount_usd=amount,
    side="buy",  # or "sell"
)
if not allowed:
    push_user(f"自动交易被拦: {reason}")
    return

# trade 真成功后 record(buy 才累计,sell 跳过)
record_executed(user_id, amount, side="buy")
```

### 3.5 不要紧急开关(用户决策)

不实现"全 App 一键停所有交易"按钮。理由:
- 用户单笔上限 + 单日上限 + 策略级 pause 已足够
- 紧急开关增加按钮 + UI 状态复杂度
- 出事时用户可逐策略 pause(承担多 30 秒延迟)

### 3.6 daily cap 实现说明

- **进程级内存** dict `_daily_totals[user_id][date_iso]`
- 失败降级:DB 不可用不阻断 trade(只 log warning)
- 进程重启 cap 清零(可接受 — 内测期;R43 改 Redis 持久化)
- **GC**:每次 record 自动清掉非今天的 entry,内存占用 O(N user)

---

## 4. risk_params 真执行(取代 schema-only)

### 4.1 现有 risk_params schema(`agent/schemas.py`)

所有字段已定义且 LLM Parser 已 `_normalize_spec` 校验 min/max,但 `trade_executor` **不读**:

| 字段 | 默认 | min | max | trade_executor 真用 |
|---|---|---|---|---|
| max_slippage_pct | 1.0% | 0.5% | 5% | ❌ → R42 ✅ |
| stop_loss_pct | 30% | 5% | 50% | ❌ → R42 ✅(经 position_monitor) |
| take_profit_pct | 100% | 10% | 1000% | ❌ → R42 ✅(经 position_monitor) |
| trailing_stop | true | bool | bool | ❌ → R42 ✅ |
| max_position_usd | 100 USD | 10 | 1000 | ❌ → R42 ✅ |
| priority_fee_sol | 0.0005 SOL | 0.0001 | 0.1 | ❌ → R42 ✅(经 dex_router) |
| mev_bribe_sol | 0 SOL | 0 | 0.1 | ❌ → R42 ✅(经 Jito bundle) |

### 4.2 trade_executor 改造

`agent/trade_executor.py:execute_trade(safety_ctx, **kwargs)` → 加 `risk_params: Optional[Dict]` 参数:

```python
async def execute_trade(
    self,
    strategy_id: str,
    token_address: str,
    chain: str,
    side: str,
    amount_usd: float,
    safety_ctx: Dict,
    risk_params: Optional[Dict] = None,   # R42 新增
) -> Dict:
    rp = risk_params or {}
    slippage = rp.get("max_slippage_pct", 0.01)
    priority_fee = rp.get("priority_fee_sol", 0.0005)
    mev_bribe = rp.get("mev_bribe_sol", 0)
    max_position = rp.get("max_position_usd", 100)

    # max_position 强制限制
    if amount_usd > max_position:
        amount_usd = max_position

    # 真传给 dex_router
    return await dex_router.execute_swap(
        chain=chain,
        token=token_address,
        side=side,
        amount_usd=amount_usd,
        slippage_pct=slippage,
        priority_fee_sol=priority_fee,   # R42
        mev_bribe_sol=mev_bribe,         # R42
    )
```

### 4.3 dex_router 改造(Solana 链接 Jito)

[agent/dex_router.py](../../services/pump-scanner/agent/dex_router.py) Solana 路径:

```python
async def execute_solana_swap(token, side, amount, slippage, priority_fee, mev_bribe):
    swap_tx = await build_jupiter_swap_tx(...)  # 现有

    if mev_bribe > 0:
        # R42:走 Jito bundle 获得 MEV 保护
        tip_tx = build_jito_tip_tx(amount=mev_bribe)
        bundle = [swap_tx, tip_tx]
        return await jito_send_bundle(bundle)   # https://mainnet.block-engine.jito.wtf
    else:
        # 走公共 RPC,只设 priority_fee
        return await rpc_send_tx(swap_tx, priority_fee=priority_fee)
```

EVM 路径同样接 Flashbots / 1inch Fee 参数。

---

## 5. 止盈止损常驻 loop(取代"代码完整但没人启动")

### 5.1 现状

[agent/position_monitor.py](../../services/pump-scanner/agent/position_monitor.py) 行 144-173 完整实现:
- 拉所有 open position
- 检查当前价 vs entry_price
- 触达 `stop_loss_pct` / `take_profit_pct` / `trailing_stop_pct` → 真调 `executor.execute_trade()` 卖

但 `main.py` **只在紧急 CB 平仓时调一次**,**不是常驻 loop**。

### 5.2 R42 改造

[main.py](../../services/pump-scanner/main.py) 启动时加 task:

```python
async def position_monitor_loop():
    monitor = get_position_monitor()
    while True:
        try:
            await monitor.scan_and_trigger_exits()  # 30s tick
        except Exception as e:
            log.warning("[position_monitor] tick fail: %s", e)
        await asyncio.sleep(30)

asyncio.create_task(position_monitor_loop())
```

`scan_and_trigger_exits()` 内部:
- 30s 拉一次所有 `mode=live` + status=`open` 的 position
- 触达条件 → 调 `trade_executor.execute_trade(side="sell", risk_params=strategy.risk_params)`

### 5.3 Paper 模式行为

`mode=paper` 的 position 也跑监控,但触达止损时只**记账**(`paper_engine` 关闭仓位)+ 推送通知,不真下单。

---

## 6. Flutter UI:risk_params 编辑

### 6.1 策略详情页加"风控设置"折叠区

[apps/app/lib/screens/agent/strategy_detail_page.dart](../../apps/app/lib/screens/agent/strategy_detail_page.dart):

```
┌─ 风控设置 ──────────────┐
│ 仓位                    │
│  单笔金额  [$50]  ━●━   │
│  最大开仓数 [3]          │
│  滑点容忍 [1.5%]  ━●━   │
│                         │
│ 止盈止损                │
│  止损   [-30%]  ━●━     │
│  止盈   [+100%] ━●━     │
│  追踪止损 [✓] [10%]      │
│                         │
│ 交易速度(MEV 保护)      │
│  ⚪ 经济                │
│  ⚫ 标准 [推荐]         │
│  ⚪ 极速                │
│                         │
│ ▸ 高级(手动)           │
│   优先 Gas [0.0005] SOL │
│   MEV 贿赂 [0.001] SOL  │
└─────────────────────────┘
```

### 6.2 三档预设映射

| 档位 | priority_fee_sol | mev_bribe_sol | 适用 |
|---|---|---|---|
| 经济 | 0.0001 | 0 | 不抢机会的波段 |
| 标准(默认) | 0.0005 | 0.001 | 大部分场景 |
| 极速 | 0.005 | 0.005 | pump.fun 抢机会 |

用户切档 → Flutter 自动设两个数字 + 显示在"高级"区供查看。

### 6.3 后端 update_strategy 接收

[api/routes_agent.py](../../services/pump-scanner/api/routes_agent.py) `update_strategy` `req.risk_params` 接收 → `_normalize_spec` 校验 min/max → upsert。

---

## 7. 部署计划

按 R39 v5 + R40 + R41 的同款 git workflow:

1. 本地 commit + push origin agent-v1
2. 服务器 `git pull && sudo systemctl restart pump-scanner-api`
3. `journalctl -u pump-scanner-api -n 50` 看启动 log
4. `curl http://43.156.207.26/health` 200

每个 P0 子项独立 commit,出问题可单独回滚。

---

## 8. 测试要求

- 后端 unit test ≥ 6 个 / 项
- Flutter widget test ≥ 5 个 / 项
- 端到端模拟器实操(用户在 iOS 模拟器试)
- 累计 40+ 新测试,跑全过 + 不破坏现有 29 测试

---

## 9. 不在本次范围(R43+)

- 真接入 Solana 主网做 $0.50 实盘验证(用户钱真出去)— 需要 P1 WalletConnect 完成后单独 milestone
- 多账号 / 多钱包管理
- 跨链 swap(Solana → ETH 桥)
- AI 自动调 priority_fee / mev_bribe(根据网络拥塞动态)— R44+ 智能化方向

---

## 10. EVM MEV 接通 (R45 — 2026-05-06)

### 10.1 决策背景

R44.4 之前 SpeedSection 在 EVM 链上把 MEV slider 灰掉,标"EVM 暂未接通"。用户问"EVM 是没 MEV 概念还是没做" — **MEV 是 EVM 鼻祖(Flashbots/MEV-Boost 90%+ ETH 出块)**,不是没概念,是我们没做。R45 接通。

### 10.2 各链 MEV 方案

| 链 | MEV 基础设施 | R45 方案 |
|---|---|---|
| Solana | Jito | ✅ 已接(R42 P0.2) |
| **Ethereum** | Flashbots / MEV-Boost | **Flashbots Protect RPC**(`https://rpc.flashbots.net/fast`),drop-in 替换 RPC URL,免费 + 0 配置 |
| **BSC** | bloXroute / 48 Club | 第一版 fallback 公共 RPC + log warning,后续接 bloXroute |
| **Base** | Flashblocks(beta) | 暂用公共 RPC + 1inch Fusion 兜底 |
| Polygon / Arb / OP | 各自 builder 生态 | 1inch 路由(自带 MEV 保护) |

### 10.3 后端实施

[services/pump-scanner/agent/trade_executor.py:60-78](services/pump-scanner/agent/trade_executor.py:60) 加:

```python
EVM_RPC_MEV_PROTECTED = {
    "eth": "https://rpc.flashbots.net/fast",
    "bsc": "",   # 第一版无,fallback 公共
    "base": "",
}
```

`_broadcast_evm(chain, signed_tx, mev_protected=False)` — `mev_protected=True` + 该链有 Protect URL → 走 Protect;否则降级公共 + log warning。

### 10.4 字段语义按链解释

`risk_params.mev_bribe_sol` 字段名不变(向后兼容),但**含义按链区分**:
- **Solana**:实际 SOL 数量(给 Jito tip)
- **EVM(eth)**:`> 0` 启用 Flashbots Protect 私有 mempool;`= 0` 走公共
- **EVM(bsc/base/polygon/arb/op)**:`> 0` 启用(第一版 fallback 公共 + log,等接 bloXroute / 1inch Fusion)

### 10.5 UI 适配(Web + App 同步)

- **Web**:[helix-marketing/src/components/app/StrategyCard.tsx](../../helix-marketing/src/components/app/StrategyCard.tsx) `<SpeedSection chain={chain} />`
  - Solana → MEV slider(0-0.01 SOL)
  - EVM → MEV toggle(✓ 已启用 / 未启用)+ 文案随 chain 变(Flashbots Protect / 1inch 路由)
- **App**:[apps/app/lib/screens/agent/strategy_detail_page.dart:472-481](../../apps/app/lib/screens/agent/strategy_detail_page.dart:472) 加链感知文案

### 10.6 测试

[services/pump-scanner/tests/test_evm_mev.py](../../services/pump-scanner/tests/test_evm_mev.py) — 9 测试:
- Flashbots URL 配置
- mev_protected=True/False 路径分别走对 RPC
- bsc 无 Protect URL → fallback 公共 + log warning
- 默认参数兼容旧 caller

### 10.7 不在 R45 范围(R46+)

- bloXroute BSC 真接入(替代 fallback)
- 1inch Fusion limit order 完整改造
- Arbitrum Express Lane 拍卖
- Base Flashblocks 接通
