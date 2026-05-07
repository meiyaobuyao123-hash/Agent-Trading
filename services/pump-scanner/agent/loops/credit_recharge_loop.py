"""
R47 P2 — USDC 充值监听 cron(60s tick)

负责把用户从自己钱包转到我们 hot wallet 的 USDC 转账,匹配到 pending recharge_order
并自动 confirm + 加 credit。

Solana 路径:Helius Enhanced Transactions API
  GET https://api.helius.xyz/v0/addresses/<addr>/transactions?api-key=...&type=TRANSFER&limit=20
  → tokenTransfers 数组 → 找 mint == USDC SPL && toUserAccount == 我们 + amount 匹配

EVM 路径(eth/base/bsc):JSON-RPC eth_getLogs
  filter: { address: USDC_<chain>, topics: [TRANSFER, null, padded(我们 addr)],
            fromBlock: -200 blocks, toBlock: latest }
  → 解析 log.data 为 amount,/ 10^decimals(BSC 18 / 其他 6)

匹配:amount === order.amount_usd(Decimal 精确到 6 位小数)
命中:credit_service.confirm_recharge_order(order_id, tx_hash)
防重:credit_service 内部 UPDATE WHERE status='pending' RETURNING,过滤已 confirmed
失败:每个链独立 try/except,单链失败不影响其他链

Python 3.9 兼容。
"""
from __future__ import annotations
import asyncio
import logging
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from agent import credit_service

log = logging.getLogger(__name__)


# ── 链上常量 ──────────────────────────────────────────────

# Solana USDC SPL token mint
USDC_SOL_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# EVM USDC 合约 + 小数(BSC 18 位 / 其他 6 位 — 算错给用户多发 10^12 倍 credit!)
USDC_EVM: Dict[str, Tuple[str, int]] = {
    "ethereum": ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
    "base":     ("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6),
    "bsc":      ("0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", 18),
}

# ERC-20 Transfer 事件 topic0 = keccak256("Transfer(address,address,uint256)")
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# 公共 RPC(env 可覆盖)
EVM_RPC: Dict[str, str] = {
    "ethereum": os.getenv("ETH_RPC", "https://eth.llamarpc.com"),
    "base":     os.getenv("BASE_RPC", "https://mainnet.base.org"),
    "bsc":      os.getenv("BSC_RPC", "https://bsc-dataseed.binance.org"),
}

# 每次扫多少 blocks 回看(覆盖 30min 订单有效期 + 几次 cron 失败重试)
EVM_LOOKBACK_BLOCKS: Dict[str, int] = {
    "ethereum": 200,   # 12s × 200 ≈ 40min
    "base":     900,   # 2s × 900 ≈ 30min
    "bsc":      600,   # 3s × 600 ≈ 30min
}


# ── helpers ──────────────────────────────────────────────

def _quantize_6(amt: Decimal) -> Decimal:
    """归一化到 6 位小数(USDC 链上精度)再比对,避免 float 误差。"""
    return amt.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _pad_evm_addr(addr: str) -> str:
    """0xC862ff... → 0x000...000c862ff... (32 bytes,小写,topic 用)"""
    a = addr.lower().removeprefix("0x")
    return "0x" + ("0" * (64 - len(a))) + a


def _match_pending(
    pending: List[Dict[str, Any]],
    received_amount: Decimal,
) -> Optional[Dict[str, Any]]:
    """在 pending list 找 amount_usd == received_amount(6 位精度)的 order。"""
    target = _quantize_6(received_amount)
    for o in pending:
        if _quantize_6(o["amount_usd"]) == target:
            return o
    return None


# ── Solana ────────────────────────────────────────────────

async def scan_solana(session: aiohttp.ClientSession) -> int:
    """返本次 confirm 的订单数。"""
    pending = credit_service.list_pending_orders_by_chain("solana")
    if not pending:
        return 0

    # 我们的收款地址(订单内已带,假设全用同一地址 — 即 env 配的)
    addr = pending[0]["receive_address"]
    api_key = os.getenv("HELIUS_API_KEY", "")
    if not api_key:
        log.warning("[credit_recharge] HELIUS_API_KEY 未配,跳 Solana")
        return 0

    url = f"https://api.helius.xyz/v0/addresses/{addr}/transactions"
    params = {"api-key": api_key, "type": "TRANSFER", "limit": 20}

    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                log.warning("[credit_recharge] solana http=%s %s", r.status, await r.text())
                return 0
            txs = await r.json()
    except Exception as e:
        log.warning("[credit_recharge] solana RPC fail: %s", e)
        return 0

    confirmed_count = 0
    for tx in txs or []:
        sig = tx.get("signature")
        token_transfers = tx.get("tokenTransfers") or []
        for tt in token_transfers:
            mint = tt.get("mint")
            to_acc = tt.get("toUserAccount")
            amount = tt.get("tokenAmount")
            if mint != USDC_SOL_MINT or to_acc != addr or amount is None:
                continue
            received = Decimal(str(amount))
            order = _match_pending(pending, received)
            if not order:
                continue
            # 命中 — 调 confirm
            res = credit_service.confirm_recharge_order(order["id"], sig)
            if res:
                confirmed_count += 1
                log.info(
                    "[credit_recharge][solana] confirmed order=%s amount=%s tx=%s user=%s",
                    order["id"], received, sig, order["user_id"][:8],
                )
                # 已 confirmed 的 order 不再尝试匹配后续 tx
                pending = [o for o in pending if o["id"] != order["id"]]
                break

    return confirmed_count


# ── EVM(ethereum / base / bsc)────────────────────────────

async def _evm_rpc(session: aiohttp.ClientSession, url: str, method: str, params: List[Any]) -> Any:
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=15)) as r:
        if r.status != 200:
            raise RuntimeError(f"http {r.status}: {await r.text()}")
        d = await r.json()
        if "error" in d:
            raise RuntimeError(f"rpc error: {d['error']}")
        return d.get("result")


async def scan_evm(session: aiohttp.ClientSession, chain: str) -> int:
    """返本次 confirm 的订单数。"""
    pending = credit_service.list_pending_orders_by_chain(chain)
    if not pending:
        return 0

    rpc_url = EVM_RPC.get(chain)
    usdc_info = USDC_EVM.get(chain)
    lookback = EVM_LOOKBACK_BLOCKS.get(chain, 200)
    if not rpc_url or not usdc_info:
        return 0
    usdc_contract, decimals = usdc_info

    addr = pending[0]["receive_address"]

    try:
        # 当前块号
        block_hex = await _evm_rpc(session, rpc_url, "eth_blockNumber", [])
        current = int(block_hex, 16)
        from_block = max(0, current - lookback)

        # eth_getLogs filter — Transfer to 我们
        logs = await _evm_rpc(session, rpc_url, "eth_getLogs", [{
            "address": usdc_contract,
            "topics": [
                TRANSFER_TOPIC,
                None,                  # from(任意)
                _pad_evm_addr(addr),   # to(我们)
            ],
            "fromBlock": hex(from_block),
            "toBlock": "latest",
        }])
    except Exception as e:
        log.warning("[credit_recharge] %s RPC fail: %s", chain, e)
        return 0

    confirmed_count = 0
    divisor = Decimal(10) ** decimals
    for lg in logs or []:
        try:
            data = lg.get("data") or "0x0"
            raw_amount = int(data, 16)  # uint256
            received = Decimal(raw_amount) / divisor
        except Exception:
            continue
        order = _match_pending(pending, received)
        if not order:
            continue
        tx_hash = lg.get("transactionHash") or ""
        res = credit_service.confirm_recharge_order(order["id"], tx_hash)
        if res:
            confirmed_count += 1
            log.info(
                "[credit_recharge][%s] confirmed order=%s amount=%s tx=%s user=%s",
                chain, order["id"], received, tx_hash, order["user_id"][:8],
            )
            pending = [o for o in pending if o["id"] != order["id"]]

    return confirmed_count


# ── 主入口 ────────────────────────────────────────────────

async def run_once() -> Dict[str, int]:
    """被 main.py APScheduler 调用。返各链 confirm 数量。"""
    result = {"solana": 0, "ethereum": 0, "base": 0, "bsc": 0}
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            result["solana"] = await scan_solana(session)
        except Exception as e:
            log.warning("[credit_recharge] solana fail: %s", e)
        for chain in ("ethereum", "base", "bsc"):
            try:
                result[chain] = await scan_evm(session, chain)
            except Exception as e:
                log.warning("[credit_recharge] %s fail: %s", chain, e)
    return result


# 命令行单跑(调试用)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = asyncio.run(run_once())
    print(f"confirmed: {res}")
