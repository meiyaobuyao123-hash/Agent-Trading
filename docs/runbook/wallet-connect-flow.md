# WalletConnect 集成流程 (R42)

> **目的**:用户用自己手机的 Phantom (Solana) / MetaMask (EVM) 钱包签交易,我们后端不持有任何用户私钥。
>
> **取代**:KMS 占位方案(收费 + 仍需后端持私钥)
>
> **创建**:2026-05-05 R42

---

## 1. 整体流程图

```
┌─────────┐                ┌──────────┐               ┌──────────┐
│ Flutter │                │ 后端 API │               │ 用户钱包 │
│  App    │                │          │               │ (Phantom)│
└────┬────┘                └────┬─────┘               └────┬─────┘
     │                          │                          │
     │ 1. 用户点 "连接钱包"      │                          │
     │─────────────────────────>│                          │
     │                          │ 2. 生成 session id       │
     │ 3. 返 deep link          │                          │
     │<─────────────────────────│                          │
     │                          │                          │
     │ 4. 打开 Phantom App      │                          │
     │──────────────────────────────────────────────────>  │
     │                          │                          │
     │ 5. 用户在 Phantom 点同意                            │
     │                          │                          │
     │ 6. Phantom 回调 Flutter,带钱包公钥                   │
     │<──────────────────────────────────────────────────  │
     │                          │                          │
     │ 7. POST 公钥 + session   │                          │
     │─────────────────────────>│                          │
     │                          │ 8. 存 user_wallets 表    │
     │                          │                          │
     │                          │                          │
     │  ====== 之后用户触发交易 ======                      │
     │                          │                          │
     │ 9. POST /chat 触发策略    │                          │
     │─────────────────────────>│                          │
     │                          │ 10. 构造 unsigned tx     │
     │ 11. push 推送 unsigned tx│                          │
     │<─────────────────────────│                          │
     │                          │                          │
     │ 12. deep link 推 Phantom │                          │
     │──────────────────────────────────────────────────>  │
     │                          │                          │
     │ 13. 用户在 Phantom 签名   │                          │
     │                          │                          │
     │ 14. 签好的 tx hex 回调    │                          │
     │<──────────────────────────────────────────────────  │
     │                          │                          │
     │ 15. POST signed tx       │                          │
     │─────────────────────────>│                          │
     │                          │ 16. 广播到 Solana RPC    │
     │                          │ 17. 等 confirmation      │
     │                          │ 18. 写 agent_executions  │
     │ 19. 推送 "成交"           │                          │
     │<─────────────────────────│                          │
```

---

## 2. Flutter 端集成

### 2.1 添加依赖

`apps/app/pubspec.yaml`:
```yaml
dependencies:
  reown_walletkit: ^2.0.0   # 或 walletconnect_dart_v2
  url_launcher: ^6.0.0       # 已有,deep link
```

### 2.2 服务封装

新建 `apps/app/lib/services/wallet_service.dart`:

```dart
class WalletService {
  static final instance = WalletService._();

  /// 连接钱包(返用户钱包公钥)
  Future<String> connect({required String chain}) async {
    // chain: "solana" / "ethereum" / "bsc" / "base"
    // 1. 调 reown_walletkit 创建 session
    // 2. 打开 Phantom (sol) / MetaMask (evm) deep link
    // 3. 等用户同意,拿到公钥
    // 4. POST 后端 /api/wallet/connect 存表
  }

  /// 签名一笔交易(unsigned tx hex → signed tx hex)
  Future<String> signTransaction({
    required String chain,
    required String unsignedTxHex,
  }) async {
    // 1. push deep link 推给 Phantom/MetaMask
    // 2. 等用户在自己 App 里点 "签名"
    // 3. 接收 signed tx hex
  }

  /// 用户拒签 / 60s 超时 → 抛 WalletRejectedException
}
```

### 2.3 UI 入口

`apps/app/lib/screens/agent/strategy_detail_page.dart` 顶部加:

```
┌──────────────────────────────────┐
│  ⚠️ 实盘需先连接钱包              │
│  [连接 Phantom 钱包]              │  ← 点击触发 connect()
│  [连接 MetaMask 钱包]             │
└──────────────────────────────────┘
```

连接成功 → 顶部改成 `已连接: 7BeoEb...pump`(显示截断的钱包地址)

---

## 3. 后端集成

### 3.1 数据表

新建 `migrations/043_user_wallets.sql`:

```sql
CREATE TABLE IF NOT EXISTS user_wallets (
  id          BIGSERIAL PRIMARY KEY,
  user_id     UUID        NOT NULL,
  chain       TEXT        NOT NULL CHECK (chain IN ('solana','ethereum','bsc','base')),
  public_key  TEXT        NOT NULL,
  connected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at TIMESTAMPTZ,
  is_active   BOOL        NOT NULL DEFAULT TRUE,
  UNIQUE(user_id, chain, public_key)
);

CREATE INDEX idx_user_wallets_user ON user_wallets(user_id);
```

### 3.2 Endpoints

新建 `services/pump-scanner/api/routes_wallet.py`:

```python
@router.post("/api/wallet/connect")
async def connect_wallet(req: ConnectRequest, user_id: str = Depends(get_current_user)):
    # 存 user_wallets 表(UPSERT)
    # 返 success
    ...

@router.post("/api/wallet/sign-and-broadcast")
async def sign_and_broadcast(req: SignRequest, user_id: str = Depends(get_current_user)):
    # req: { unsigned_tx_hex, signed_tx_hex, chain, swap_id }
    # 1. 验签 (确认 signed tx 来自用户的钱包)
    # 2. 广播到 RPC (solana / EVM)
    # 3. 等 confirmation (max 30s)
    # 4. 写 agent_executions 表
    # 5. 返 tx_hash
    ...

@router.get("/api/wallet/list")
async def list_wallets(user_id: str = Depends(get_current_user)):
    # 返 user_wallets WHERE is_active=true
    ...
```

### 3.3 dex_router 改造

`agent/dex_router.py`:

```python
async def execute_swap(
    chain, token, side, amount_usd,
    user_id,             # R42 新增
    risk_params=None,
):
    # 1. 拿 user_wallets WHERE user_id=? AND chain=? AND is_active
    # 2. 构造 unsigned tx (Jupiter / 1inch)
    # 3. 写 pending_signing_tx 表(等 Flutter 推回 signed)
    # 4. push 通知 Flutter (deep link 信息)
    # 5. 异步等 30s,签名回来 → 广播
    #    超时 → mark "user_did_not_sign" + 退款
```

### 3.4 旧 KMS 代码

`agent/kms_client.py` 顶部加:

```python
"""
⚠️ R42 弃用 — 改用 WalletConnect (用户私钥永远在自己手机里)。

代码保留作 historical reference,不再被任何 caller 调用。
新代码看 services/pump-scanner/api/routes_wallet.py
"""
```

---

## 4. 异常处理矩阵

| 异常 | 错误码 | 用户体验 | 系统行为 |
|---|---|---|---|
| 用户拒绝签名 | `user_rejected` | "已取消" Toast | 不消耗 quota,trade 标 paper 重跑 |
| Phantom 未安装 | `wallet_not_installed` | 弹引导下载 + App Store 链接 | 中止 swap |
| 60s 内未签 | `sign_timeout` | "签名超时" 通知 | 退款 + 撤回 pending |
| 签后 RPC 广播失败 | `broadcast_failed` | "网络繁忙" + 重试按钮 | 自动重试 3 次,最终失败 → mark `failed` |
| 签后 RPC 通过但链上失败(滑点 / honeypot) | `tx_reverted` | 显示链上失败原因 + tx_hash 链接 | 写 agent_executions status=`reverted` |
| 钱包公钥与历史不一致(用户换钱包) | `wallet_mismatch` | "请重新连接钱包" | 强制 disconnect → 重 connect 流程 |

---

## 5. 安全考虑

1. **后端不存私钥**:从 .env 删除 `TRADE_WALLET_PRIVATE_KEY`(R42 P1 完成后)
2. **签名验证**:后端收到 signed tx 后,本地验证签名是否来自用户已注册的钱包公钥(防中间人替换)
3. **RPC 防护**:广播用 https / 有 retry,失败不阻断用户体验
4. **Audit log**:每次 sign-and-broadcast 写 `security_audit_log` event_type=`wallet_op`
5. **超时机制**:pending_signing_tx 60s 自动过期,防止 leaked unsigned tx 被滥用

---

## 6. 测试矩阵

| 场景 | 测试 |
|---|---|
| 首次连接 Phantom | 模拟器装 Phantom App + 走 deep link 流程 |
| 用户拒签 | mock Phantom 返 reject |
| 60s 超时 | mock 不返响应,等 60s |
| 签名后广播成功 | mock RPC 200 + confirmation |
| 链上 revert(高滑点) | mock RPC 返 tx 但 confirmation 失败 |
| 钱包不匹配 | 用 wallet A 连接,用 wallet B 签 |

---

## 7. 上线步骤

1. P1 实施完(Flutter + 后端代码)
2. 内部测试:开发者用 Phantom 测试网 SOL 跑 5 笔 dummy swap
3. 公网内测:邀请 2-3 个用户用 mainnet $0.50 swap 验证
4. 全量开放:Flutter App "连接钱包" 按钮上线 → 写公告

---

## 8. 不在本次范围(R43+)

- 多账号 / 多钱包同时连接
- 硬件钱包(Ledger / Trezor)集成
- 跨链 swap (Solana → ETH bridge)
- 社交登录(Web3Auth / Magic Link)
