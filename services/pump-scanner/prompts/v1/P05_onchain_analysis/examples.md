# P05 Few-shot

## Example 1 (healthy bullish)

**User:** token=TRUMP chain=SOL top10=45% sm_net=+82000 elite_wallets=5 liq=120000 vol_24h=850000

**Assistant:** {"direction":"bullish","confidence":0.7,"concentration_warning":false,"liquidity_warning":false,"points":["smart money 净流入 +$82k","5 个 elite 钱包同方向","top10 = 45% 健康分散","流动性 $120k 充足"]}

## Example 2 (rug warning)

**User:** token=NEW chain=BSC top10=78% sm_net=-15000 elite_wallets=0 liq=8000 vol_24h=45000

**Assistant:** {"direction":"bearish","confidence":0.8,"concentration_warning":true,"liquidity_warning":true,"points":["top10 = 78% 高度集中,rug 风险","流动性仅 $8k 低于门槛","smart money 净流出 -$15k","0 elite 跟单"]}

## Example 3 (neutral mid-cap)

**User:** token=PEPE chain=ETH top10=52% sm_net=+5000 elite_wallets=1 liq=2500000 vol_24h=12000000

**Assistant:** {"direction":"neutral","confidence":0.4,"concentration_warning":false,"liquidity_warning":false,"points":["smart money 净流微正 +$5k","流动性 $2.5M 充足","top10 = 52% 中等","信号偏弱"]}
