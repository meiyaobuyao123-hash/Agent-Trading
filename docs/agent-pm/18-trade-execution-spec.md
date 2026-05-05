# 18 — 交易执行规范 (R42)

> **文档定位**:R42 实施周期权威规范。涵盖私钥管理、实盘/模拟盘控制、HITL 分层自动化、risk_params 真执行、止盈止损常驻 loop、WalletConnect 集成。
>
> **历史背景**:R36 audit 发现"trade_executor 不读 risk_params + position_monitor 不常驻 + KMS 占位",R42 全部修。
>
> **修订历史**:2026-05-05 R42 创建,作者 PM-lead

---

## 1. 私钥管理 — WalletConnect(取代 KMS)

### 1.1 决策背景

**KMS 方案(原 R37 W3 设计)的问题**:
- AWS/GCP KMS 都按调用次数收费(每月 20K 免费,超出 $0.03/10K + 每 key $1/月)
- 需要后端持有用户私钥(即使在硬件里),仍是单点风险
- 用户跑路 / 服务器被黑 → 仍可能丢币

**WalletConnect 方案(R42 决定)**:
- 用户在自己手机的 **Phantom (Solana)** / **MetaMask (EVM)** 钱包里持有私钥
- 我们后端**永不持有用户私钥**
- 后端构造 unsigned tx → 通过 WalletConnect deep link 推给用户钱包 → 用户在自己 App 里点确认 → 签好的 tx 推回我们广播
- **完全免费**(协议开源,SDK 开源,无 API 调用费)
- **行业标准**(Jupiter / Raydium / Magic Eden 全这么做)

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

## 3. HITL 分层自动化(取代统一 5/15/60min 审批)

### 3.1 设计背景

**原设计问题**:所有真金交易都强制 5/15/60min 审批。但 pump.fun 秒级机会等 5 分钟早飞了。

**R42 改为分层**:按"金额 + 策略类型 + 历史记录"自动判 + 用户可在策略层覆盖。

### 3.2 三档自动化

| 档位 | 触发条件(自动判) | 用户体验 |
|---|---|---|
| **auto** | 金额 < `auto_max_amount_usd`(默认 $20) **且** 策略已 graduated 30 天 | 直接下单,事后推送通知 |
| **semi**(默认) | $20 ≤ 金额 ≤ $200 **或** 策略 graduated < 30 天 | **推送 + 30s 撤销窗口**(用户不操作 → 自动下单) |
| **manual** | 金额 > $200 **或** 高风险策略(标 `is_high_risk=true`) | **必须点确认**,5/15/60min 审批 |

### 3.3 用户覆盖

策略详情 UI 暴露 `automation_level` 三档手动选择,用户可强制覆盖系统判定:
- 如选 `auto` 但金额 > `auto_max_amount_usd` → 拒绝设置 + 提示
- 如选 `manual`,所有交易都走全审批

### 3.4 全自动模式的兜底保护

- `daily_auto_cap_usd`(默认 $500/天):全自动模式日累计上限,超出强制冷却 1 小时
- 单笔亏损 > 50% → 强制平仓 + 暂停该策略
- 写 `security_audit_log` event_type=`hitl_decision` severity=`info`,事后可审

### 3.5 hitl_router 接口

新建 [agent/hitl_router.py](../../services/pump-scanner/agent/hitl_router.py):

```python
def decide_hitl_level(
    amount_usd: float,
    strategy: Dict,
    daily_auto_used_usd: float,
) -> Literal["auto", "semi", "manual"]:
    # 1. 用户强制 manual / auto → 检查约束后直接返
    # 2. 否则按金额 + graduated 自动判
    # 3. 全自动日累计超 cap → 降级 semi
    ...
```

trade_executor 每次 trade 前调一次 → 决定走哪条流程。

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
