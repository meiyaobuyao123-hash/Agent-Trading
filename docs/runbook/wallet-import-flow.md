# 钱包私钥导入流程 (R42 P1 — AES 加密存 DB)

> **目的**:用户从 Flutter 一次性导入私钥 → 后端 AES-256-GCM 加密 → 存 PG。每次自动交易直接解密签名,**无需用户审批**。
>
> **取代**:WalletConnect(每笔确认,跟全自动化冲突)+ KMS(收费 + 复杂度高)
>
> **创建**:2026-05-05 R42 P1

---

## 1. 流程图

```
┌─────────┐         ┌──────────┐         ┌──────────┐
│ Flutter │         │ 后端 API │         │ Local PG │
└────┬────┘         └────┬─────┘         └────┬─────┘
     │                   │                    │
     │ 1. 用户点"导入私钥"                  │
     │ 输入助记词或粘贴私钥                  │
     │                   │                    │
     │ 2. wallet_service 派生 address        │
     │    存 iOS Keychain / Android Keystore │
     │                   │                    │
     │ 3. POST /api/wallet/import            │
     │ {chain, public_key, private_key}      │
     │──────────────────>│                    │
     │                   │ 4. crypto_box.encrypt
     │                   │    nonce + AES-GCM │
     │                   │ 5. INSERT user_wallets
     │                   │──────────────────> │
     │ 6. 返 {id, public_key, ...} (无私钥)  │
     │<──────────────────│                    │
     │                   │                    │
     │  ===== 之后 AI 自动触发交易 =====     │
     │                   │                    │
     │ 7. trade signal   │                    │
     │                   │ 8. _resolve_wallet │
     │                   │    SELECT user_wallets
     │                   │<──────────────────│
     │                   │ 9. crypto_box.decrypt
     │                   │ 10. sign + broadcast
     │                   │ 11. 写 agent_executions
     │                   │ 12. push 通知 Flutter
     │ 13. 推送"已买 X"   │                    │
     │<──────────────────│                    │
```

**关键**:第 1-6 步用户参与一次,第 7-13 步**全自动**(即使用户离线 / 睡觉)。

---

## 2. 服务器初始化(运维只跑一次)

### 2.1 生成 master_key

```bash
ssh ubuntu@43.156.207.26
cd /opt/agent-trading/services/pump-scanner

# 生成 32 字节 base64
python3 -c "from agent.crypto_box import generate_new_master_key_b64; print(generate_new_master_key_b64())"
```

### 2.2 写入 .env + 重启

```bash
echo "WALLET_MASTER_KEY=<output>" >> .env
sudo systemctl restart pump-scanner-api
```

### 2.3 跑 migration 043

```bash
psql -h 127.0.0.1 -U agent_local -d agent_trading_local \
     -f migrations/local_pg/043_user_wallets.sql
```

### 2.4 验证 ready

```bash
curl -s http://127.0.0.1:8000/api/wallet/master-status \
     -H "Authorization: Bearer dev_test"
# {"ready": true}
```

---

## 3. master_key 安全管理

| 状况 | 操作 |
|---|---|
| 入 git | **禁止** — `.env` 必须 `.gitignore` |
| log 出来 | **禁止** — crypto_box 失败时不 log key 内容 |
| 备份 | 多副本(运维保密箱 + 加密 USB),丢了所有钱包私钥**无法恢复** |
| 轮换 | 改 master_key 必须**重加密**所有 user_wallets |
| 环境隔离 | 测试用一组 / 生产用一组,**不要混** |

---

## 4. 异常矩阵

| 异常 | 处理 |
|---|---|
| 私钥格式错(<32 字符) | wallet_service 抛 / 后端 422 → "格式不对" Toast |
| address 已存在 | 后端 ON CONFLICT 复用 + 更新 → 静默 |
| master_key 未配置 | walletMasterReady → false → "云端未就绪" + 引导运维 |
| PG 不可用 | 推送失败 → 仍本地存 + Toast |
| 解密失败(master_key 改了) | trade_executor 返 success=False + 推送 "钱包错乱,请重新导入" |
| 篡改 blob | InvalidTag 抛 → 同上 |

---

## 5. 测试清单

### 5.1 单测

```bash
cd services/pump-scanner
python3 -m pytest tests/test_crypto_box.py -v
# 16 passed
```

### 5.2 端到端

1. 服务器初始化 master_key + migration 043
2. Flutter 导入一个 SOL 测试钱包($0.50 余额)
3. 验证后端存了:`SELECT id, public_key, length(encrypted_private_key) FROM user_wallets;`
4. 触发一笔 paper trade,验证 trade_executor 用 user_wallets 不是 .env

### 5.3 故障演练

- 改错 master_key → restart → trade 失败 + log "auth tag 不匹配"
- 删 user_wallets 一行 → trade fallback .env(若有)否则拒

---

## 6. 不在范围(R43+)

- 多账户切换(按策略分配)
- 硬件钱包 Ledger / Trezor
- 跨链 swap(Solana → ETH bridge)
- master_key 自动轮换
- KMS 集成(如客户合规要求,后续 hybrid 方案)
