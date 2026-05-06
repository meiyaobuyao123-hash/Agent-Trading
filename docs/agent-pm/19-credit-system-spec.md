# 19 — Credit 算力体系规范

R47(2026-05-07)上线。

## 目标

用户必须先充值 credit 才能用 Agent chat;每次 LLM 调用按 token 价格扣费;余额 ≤ MIN_BALANCE_USD 拒绝并提示充值。

替代以前"无配额免费 chat"的内测模式 —— 把 LLM 调用成本透明传递给真付费用户。

## 计费模型

### 价目表(2026-05 Anthropic 公开价 USD per 1M tokens)

| Model              | input  | output |
| ------------------ | ------ | ------ |
| claude-haiku-4-5   | $0.25  | $1.25  |
| claude-sonnet-4-6  | $3.00  | $15.0  |
| claude-opus-4-6    | $15.0  | $75.0  |

Markup: × 1.0005(万分之五,覆盖 USDC RPC 监听 + 服务器开销)

### 成本公式

```
cost_usd = (tokens_in × in_price + tokens_out × out_price) / 1_000_000 × 1.0005
```

Decimal NUMERIC(14,8) 精度,避免浮点累计误差。

未知 model id → fallback 到 sonnet 价(保守)+ log warning。

## 数据表(migration 045)

### user_credits

每用户一行,实时余额。

| col              | type           | note                  |
| ---------------- | -------------- | --------------------- |
| user_id          | UUID PK FK     | references users(id)  |
| balance_usd      | NUMERIC(14,8)  | 当前余额              |
| total_recharged  | NUMERIC(14,8)  | 累计充值              |
| total_consumed   | NUMERIC(14,8)  | 累计消费              |
| updated_at       | TIMESTAMPTZ    | 最后更新              |

`balance_non_negative` CHECK >= -0.01(容许微量负数防并发)。

### credit_transactions

Append-only 流水,所有 deduct / add / adjust / refund。

| col               | type           | note                                |
| ----------------- | -------------- | ----------------------------------- |
| id                | BIGSERIAL PK   |                                     |
| user_id           | UUID FK        |                                     |
| type              | TEXT           | recharge / consume / adjust / refund |
| amount_usd        | NUMERIC(14,8)  | 正=入账,负=扣费                    |
| balance_after     | NUMERIC(14,8)  | 写入后余额(便于审计)              |
| recharge_order_id | BIGINT         | 关联充值订单                        |
| chain_tx_hash     | TEXT           | USDC tx hash                        |
| model             | TEXT           | LLM model id(consume 类型)         |
| tokens_in/out     | INT            | LLM token 用量                      |
| request_id        | TEXT           | chat conversation_id                |
| ts                | TIMESTAMPTZ    |                                     |
| meta              | JSONB          |                                     |

索引:`(user_id, ts DESC)` + `(type, ts DESC)`

### recharge_orders

充值订单,pending → confirmed/expired 状态机。

| col              | type           | note                                       |
| ---------------- | -------------- | ------------------------------------------ |
| id               | BIGSERIAL PK   |                                            |
| user_id          | UUID FK        |                                            |
| chain            | TEXT           | solana / ethereum / base / bsc             |
| receive_address  | TEXT           | 我们的收款 hot wallet                      |
| amount_usd       | NUMERIC(12,6)  | 用户实付金额(含 nonce,如 $10.0034)      |
| amount_base      | NUMERIC(12,6)  | 用户输入整数($10)                       |
| amount_nonce     | NUMERIC(8,6)   | 4 位小数随机零头($0.0034)用于唯一识别 tx |
| status           | TEXT           | pending / confirmed / expired / manual_review |
| chain_tx_hash    | TEXT           |                                            |
| created_at       | TIMESTAMPTZ    |                                            |
| confirmed_at     | TIMESTAMPTZ    |                                            |
| expires_at       | TIMESTAMPTZ    | 默认 30 min                                |

索引:partial `(status, expires_at) WHERE status='pending'` + `(user_id, created_at DESC)`

## 后端 API

### `agent/credit_service.py`

| function                   | use                                |
| -------------------------- | ---------------------------------- |
| `calc_cost(model, in, out)` | Decimal cost                       |
| `get_balance(uid)`         | 当前余额                           |
| `get_full_balance(uid)`    | 余额 + 累计充值/消费 + has_account |
| `can_proceed(uid)`         | (bool, reason)                     |
| `deduct(uid, model, in, out, request_id)` | 扣费 + 写流水,失败降级 |
| `add_credit(uid, amount, source_type, meta)` | 加余额 + 写流水         |
| `list_transactions(uid)`   | 交易历史                           |
| `create_recharge_order(uid, chain, amount_int)` | 创建订单            |
| `list_recharge_orders(uid)` | 订单列表                          |
| `confirm_recharge_order(order_id, tx_hash)` | 充值监听调用,加余额 |
| `expire_pending_orders()`  | cron 定期清                        |
| `estimate_remaining_messages(balance)` | 估算余额可发消息数         |

**DEV bypass**: `user_id == "00000000-0000-0000-0000-000000000001"` 不扣费(测试用)。

### `api/routes_credit.py`

5 endpoints,全部 require Bearer token:

| method | path                          | response                       |
| ------ | ----------------------------- | ------------------------------ |
| GET    | /api/credit/balance           | BalanceResponse                |
| POST   | /api/credit/recharge-orders   | RechargeOrderResponse(201)     |
| GET    | /api/credit/recharge-orders   | {orders: [...]}                |
| GET    | /api/credit/transactions      | {transactions: [...]}          |
| POST   | /api/credit/admin/grant       | admin 手动加 credit(USDC 监听上线前临时方案) |

### chat handler 接通

`api/routes_agent.py` chat() / chat_stream():

1. **Pre-call gate** — 检查 `can_proceed(user_id)`,失败返 `余额不足,请充值` 不调 LLM。
2. **Post-call deduct** — 拿 `_llm_parser._last_usage` 的真 token 数,调 `deduct()` 扣费。

`agent/llm_parser.py` 加 `self._last_usage = {"in": 0, "out": 0, "model": MODEL}` 累加器:
- parse 顶部 reset
- 每轮 `client.messages.create` 后从 `response.usage.input_tokens` / `output_tokens` 累加

## 充值流程

### 用户角度

1. Web `/app/credit` 点 "$10" 预设金额
2. POST `/api/credit/recharge-orders` 创建订单
3. 后端返 `{address, amount_exact: "$10.0034", expires_at, ...}`
4. 弹 modal 显示收款地址 + 精确金额(必须含 nonce,精确到 6 位小数)+ 30 分钟倒计时
5. 用户从 Phantom/Backpack/OKX 钱包转 USDC 到该地址(精确金额)
6. 后端 cron(R48 上线)监听 Solana RPC → 匹配 amount_exact → status=confirmed → `add_credit()` → user 余额更新
7. SubNav 余额胶囊 30s 自动刷新,显示新余额

### 收款 hot wallet 配置

后端 env:
```
RECHARGE_ADDRESS_SOLANA=<solana hot wallet address>
RECHARGE_ADDRESS_ETHEREUM=<eth hot wallet address>
RECHARGE_ADDRESS_BASE=<base hot wallet address>
```

R47 上线时只配 Solana(主链),其他链 R48+ 加。

### 防 nonce 撞车

`_gen_amount_with_nonce(amount_int)` 生成 4 位小数随机零头(0001-9999):
- 同一 chain pending 订单中,如果 amount_exact 已存在 → 重新生成(最多 5 次)
- 极端情况 5 次都撞车 → 返 None(用户重试)

## 监听服务(R48 实施)

`agent/loops/credit_recharge_loop.py`(每 30s):

1. 拉所有 `status='pending' AND expires_at > now()` orders,按 chain 分组
2. **Solana 路径**:
   - Helius RPC `getSignaturesForAddress(receive_address)` 拉最近 200 tx
   - 解析 USDC SPL transfer instruction
   - amount(USDC 6 decimals)= 本笔数量;sender = 转出方
   - 匹配 amount === order.amount_exact(精确到 6 位小数)→ 找到 order
   - `confirm_recharge_order(order_id, chain_tx_hash)`: status=confirmed + add_credit + 写 credit_transactions(type='recharge')
3. **Ethereum/Base 路径**(R48+):同样逻辑,USDC ERC-20 transfer event
4. 过期 orders → status='expired'
5. 不匹配的 incoming USDC → log + 写 manual_review queue

## 风险 + 安全

### 已知风险

1. **HTTPS 未上**(用户决策 R47):HTTP 明文 → 公共 WiFi 中间人嗅探风险高
   - 影响:登录密码 / JWT / 用户支付意图都裸传
   - mitigation:R48 单独开 HTTPS task,Let's Encrypt + certbot 1 小时配完
2. **收款地址私钥**:hot wallet 私钥配 env(`RECHARGE_HOT_WALLET_PRIVATE_KEY_SOL`),建议 admin 定期把 balance > $1000 转冷钱包
3. **Manual review queue**:用户转错金额(漏 nonce / 多发)需 admin 手动处理 — 写流程 SOP

### 并发安全

- `deduct`: `UPDATE ... SET balance = balance - cost RETURNING balance`(原子)
- `add_credit`: `INSERT ... ON CONFLICT (user_id) DO UPDATE`(防 race)
- `_ensure_user_credit_row`: `INSERT ... ON CONFLICT DO NOTHING`(并发安全)

### 余额持平问题

`balance_non_negative` CHECK 容许 -0.01,防并发扣费撞车。极端情况短暂负值会被 `can_proceed` 拒下次新请求。

## 测试覆盖

`tests/test_credit_service.py` 16 测试:
- calc_cost 6 测试(各 model + markup + 未知 fallback + 0 token)
- DEV bypass 2 测试
- estimate_remaining_messages 3 测试
- can_proceed (DB-mocked) 3 测试
- LLMParser._last_usage 累加器 2 测试

E2E 验证(已通):
- 新用户余额 $0 → chat 被拒(返"余额不足")
- 种 $1 → chat 成功,扣费 $0.0381(11594 in / 218 out × sonnet 价 × 1.0005)
- 余额变 $0.9619,交易流水正确记录

## Web UI

### `/app/credit` 页

三大块:
1. 余额卡 — balance_usd / total_recharged / total_consumed / 估算可发消息;余额低/0 时高亮警告色 + 充值按钮
2. 充值订单列表 — 待付款可点击重开 PayModal
3. 交易历史 — append-only 显示 consume / recharge / adjust

充值 modal:
- 三档预设(\$10/\$50/\$100/\$500)+ 自定义
- 选定后调 createRechargeOrder → 弹 PayModal 显示收款地址(QR + copy)+ 精确金额 + 倒计时

### SubNav 余额胶囊(R47)

所有 /app 子页右上角显示 `$X.XXXX` 余额胶囊:
- 余额 > \$0.10 → 蓝色(--accent-bright)
- \$0 < 余额 < \$0.10 → 橙色(warning)
- 余额 ≤ 0 → 红色(danger)

点击跳 /app/credit。30s 自动刷新。

## App Flutter(R48+)

deferred 到 R48+,与 Flutter R46(google_sign_in + login/register pages)一起做。

## 后续路线

| Release | 内容                                                 |
| ------- | ---------------------------------------------------- |
| R47     | 后端 + Web UI(已上线)                              |
| R48     | USDC Solana 监听 cron + ETH/Base 充值 + Flutter R46+R47 |
| R49     | 邮件月度账单 / usage 报表                            |
| R50     | 退款流程 / refund(用户多充转回)                    |

## 配置 checklist(GA 前)

- [ ] `RECHARGE_ADDRESS_SOLANA` env 配真 hot wallet
- [ ] `RECHARGE_HOT_WALLET_PRIVATE_KEY_SOL` 配 wallet 私钥(用于运维查 balance)
- [ ] 监听 cron 上线 + 5 笔实测 confirm 通过
- [ ] HTTPS 上线(R48,前置依赖)
- [ ] ADMIN_EMAILS 配 admin 邮箱列表
