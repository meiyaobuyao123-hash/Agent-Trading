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

# 公共 RPC fallback 列表(env 可覆盖第一个;429/超时按顺序 fallback)
# llamarpc 有时会"封 IP 50 天",所以多备几条
EVM_RPC_LIST: Dict[str, List[str]] = {
    "ethereum": [
        os.getenv("ETH_RPC") or "https://ethereum-rpc.publicnode.com",
        "https://rpc.ankr.com/eth",
        "https://eth.drpc.org",
        "https://eth.llamarpc.com",
    ],
    "base": [
        os.getenv("BASE_RPC") or "https://mainnet.base.org",
        "https://base-rpc.publicnode.com",
        "https://base.drpc.org",
    ],
    "bsc": [
        os.getenv("BSC_RPC") or "https://bsc-dataseed.binance.org",
        "https://bsc-rpc.publicnode.com",
        "https://bsc.drpc.org",
    ],
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

def _solana_rpc_list() -> List[str]:
    """Solana RPC fallback list — 公共优先,Helius 兜底(因免费 quota 易爆)。
    env SOL_RPC 可覆盖第一个。
    """
    api_key = os.getenv("HELIUS_API_KEY", "")
    return [
        os.getenv("SOL_RPC") or "https://solana-rpc.publicnode.com",
        "https://api.mainnet-beta.solana.com",
        "https://rpc.ankr.com/solana",
        f"https://mainnet.helius-rpc.com/?api-key={api_key}" if api_key else "",
    ]


async def _try_solana_rpcs(
    session: aiohttp.ClientSession,
    method: str,
    params: List[Any],
) -> Optional[Any]:
    last_err = None
    for url in _solana_rpc_list():
        if not url:
            continue
        try:
            return await _evm_rpc(session, url, method, params)
        except Exception as e:
            last_err = e
            continue
    if last_err:
        log.warning("[credit_recharge] solana all RPCs failed: %s", last_err)
    return None


async def scan_solana(session: aiohttp.ClientSession) -> int:
    """返本次 confirm 的订单数。
    使用 Solana 标准 RPC(fallback 列表):
      1. getSignaturesForAddress(addr, limit=10) → 10 个最新 tx 签名
      2. 对每条 sig:getTransaction(sig, jsonParsed) → 解析 tokenBalances 差值
      3. 如发现 USDC 增加到我们 → 与 pending order 匹配 → confirm
    """
    pending = credit_service.list_pending_orders_by_chain("solana")
    if not pending:
        return 0

    addr = pending[0]["receive_address"]

    # 1. 拉最新 10 条 tx 签名(fallback list)
    sigs_resp = await _try_solana_rpcs(session, "getSignaturesForAddress", [addr, {"limit": 10}])
    if not sigs_resp:
        return 0

    confirmed_count = 0
    for sig_obj in sigs_resp[:10]:
        sig = sig_obj.get("signature")
        if not sig:
            continue
        tx = await _try_solana_rpcs(session, "getTransaction", [
            sig,
            {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0},
        ])
        if not tx:
            continue

        # 解析 pre/postTokenBalances diff,找 USDC 增量到我们 addr
        meta = tx.get("meta") or {}
        pre = meta.get("preTokenBalances") or []
        post = meta.get("postTokenBalances") or []

        # 构 mint→{owner→amount} 映射
        def _idx(arr):
            d = {}
            for b in arr:
                m = b.get("mint")
                o = b.get("owner")
                ui = (b.get("uiTokenAmount") or {}).get("uiAmount")
                if m == USDC_SOL_MINT and o == addr and ui is not None:
                    d[o] = Decimal(str(ui))
            return d

        pre_d = _idx(pre)
        post_d = _idx(post)
        prev = pre_d.get(addr, Decimal(0))
        curr = post_d.get(addr, Decimal(0))
        delta = curr - prev
        if delta <= 0:
            continue

        order = _match_pending(pending, delta)
        if not order:
            continue
        res = credit_service.confirm_recharge_order(order["id"], sig)
        if res:
            confirmed_count += 1
            log.info(
                "[credit_recharge][solana] confirmed order=%s amount=%s tx=%s user=%s",
                order["id"], delta, sig, order["user_id"][:8],
            )
            pending = [o for o in pending if o["id"] != order["id"]]

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


async def _try_evm_rpcs(
    session: aiohttp.ClientSession,
    chain: str,
    method: str,
    params: List[Any],
) -> Optional[Any]:
    """尝试 fallback list 里的 RPC,第一个成功的返回。全部失败返 None。"""
    urls = EVM_RPC_LIST.get(chain) or []
    last_err = None
    for url in urls:
        if not url:
            continue
        try:
            return await _evm_rpc(session, url, method, params)
        except Exception as e:
            last_err = e
            continue
    if last_err:
        log.warning("[credit_recharge] %s all RPCs failed: %s", chain, last_err)
    return None


async def scan_evm(session: aiohttp.ClientSession, chain: str) -> int:
    """返本次 confirm 的订单数。"""
    pending = credit_service.list_pending_orders_by_chain(chain)
    if not pending:
        return 0

    usdc_info = USDC_EVM.get(chain)
    lookback = EVM_LOOKBACK_BLOCKS.get(chain, 200)
    if not usdc_info:
        return 0
    usdc_contract, decimals = usdc_info

    addr = pending[0]["receive_address"]

    # 当前块号(fallback 链)
    block_hex = await _try_evm_rpcs(session, chain, "eth_blockNumber", [])
    if not block_hex:
        return 0
    try:
        current = int(block_hex, 16)
    except Exception:
        return 0
    from_block = max(0, current - lookback)

    # eth_getLogs filter — Transfer to 我们(fallback 链)
    logs = await _try_evm_rpcs(session, chain, "eth_getLogs", [{
        "address": usdc_contract,
        "topics": [
            TRANSFER_TOPIC,
            None,                  # from(任意)
            _pad_evm_addr(addr),   # to(我们)
        ],
        "fromBlock": hex(from_block),
        "toBlock": "latest",
    }])
    if logs is None:
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
