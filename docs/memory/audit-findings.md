# 调研结论（2026-03-11）

## 1. 代币价格表现追踪计算口径
### 问题
- **outcome_labeler.py L70,L85-86**: `peak_multiplier = ath_mc_sol / initial_mc_sol`
  - 计算的是「初始市值 → 全生命周期ATH」，而非「推荐时市值 → 推荐后ATH」
  - 导致标签值虚高，影响后续 ML 训练
- **initial_mc_sol 来源混乱**：可能是创建时也可能是推荐时的市值
- **daily_highs 时间戳**：只存 HH:MM，缺少日期信息
### 正确部分
- performance_tracker.py 的 best_pct（推荐后30天最高涨幅）计算正确
- daily_highs D0~D30 边界已修复

## 2. 热币覆盖范围
- 当前仅 SOL/BSC/Base 3链，ETH 被排除
- 排除原因：GeckoTerminal ETH trending_pools 多为成熟协议(>90d)
- 数据源：GeckoTerminal + GoPlus + Helius + DexScreener，未用 OKX
- 每次扫描约 360 候选 → 过滤后 40-80 入库

## 3. 聪明钱系统
- 100% on-chain 来源（pump.fun WS 交易事件）
- 分层：Elite(≥65%胜率+≥10笔+≥2周+<15%BC入场) / Verified(≥50%+≥5笔) / Watching(≥40%+≥3笔)
- 60天衰减窗口，Bot检测（60秒买卖同币→黑名单）
- 库规模约 1K-5K 个有效钱包
- 缺失：无外部导入、冷启动不足、仅覆盖内盘

## 4. K线图 vs Bitget
- WebView + klinecharts v9，真正的 OHLCV 烛线图
- 7个指标（MA/BOLL/MACD/KDJ/RSI/WR/VOL），5个时间框架(5m~1d)
- 缺失：折线图模式、绘图工具、深度图
- WebView 加载慢（8-16秒）
- 数据源：GeckoTerminal OHLCV，100条/请求

## 5. 详情页数据 vs OKX/Bitget Wallet
- Holder 总数用 GoPlus（不如链 RPC 准确）
- Top10占比用 GoPlus（可能滞后）
- 4h 数据用 6h 近似（DexScreener 无4h endpoint）
- 市值/流动性与 DexScreener 一致（✅）
- CoinGecko 小币常 404（ATH/ATL/maxSupply 缺失）
- 流通供应量用 marketCap/price 反推（精度差）
