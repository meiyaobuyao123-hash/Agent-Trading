import 'package:flutter/material.dart';
import '../../models/btc_eth.dart';
import '../../l10n/app_localizations.dart';

/// 市场状态仪表盘 — 通俗易懂版
class RiskDashboard extends StatelessWidget {
  final BtcEthAssetSummary data;
  final String asset;

  const RiskDashboard({super.key, required this.data, required this.asset});

  @override
  Widget build(BuildContext context) {
    final fgi = data.fearGreed ?? 50;
    final rsi = data.rsi ?? 50;
    final funding = data.fundingRate ?? 0;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 标题
          Row(
            children: [
              const Icon(Icons.dashboard, color: Colors.white54, size: 14),
              const SizedBox(width: 6),
              Text('$asset Market Status',
                  style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.7), fontSize: 13, fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 12),

          // 三个指标卡片（点击查看解释）
          Row(
            children: [
              _indicatorCard(
                icon: Icons.mood,
                title: 'Market Mood',
                value: fgi.toString(),
                label: _fgiLabel(fgi),
                color: _fgiColor(fgi),
                progress: fgi / 100,
                context: context,
                explanation: _isZh(context)
                    ? '恐慌贪婪指数 (0-100)\n\n'
                      '0-20: 极度恐慌 — 市场恐慌抛售，历史上往往是好的买入机会\n'
                      '20-40: 恐慌 — 投资者担忧，可能是逢低买入区域\n'
                      '40-60: 中性 — 市场没有明显倾向\n'
                      '60-80: 贪婪 — 市场升温，需要谨慎\n'
                      '80-100: 极度贪婪 — FOMO 情绪，回调风险高\n\n'
                      '当前: $fgi (${_fgiLabel(fgi)})'
                    : 'Fear & Greed Index (0-100)\n\n'
                      '0-20: Extreme Fear — Market panic, historically good buying opportunities\n'
                      '20-40: Fear — Investors are worried, potential dip buying zone\n'
                      '40-60: Neutral — No strong bias\n'
                      '60-80: Greed — Market is heating up, be cautious\n'
                      '80-100: Extreme Greed — FOMO territory, high risk of correction\n\n'
                      'Current: $fgi (${_fgiLabel(fgi)})',
              ),
              const SizedBox(width: 8),
              _indicatorCard(
                icon: Icons.speed,
                title: 'Momentum',
                value: rsi.toStringAsFixed(0),
                label: _rsiLabel(rsi),
                color: _rsiColor(rsi),
                progress: rsi / 100,
                context: context,
                explanation: _isZh(context)
                    ? 'RSI 相对强弱指标 (0-100)\n\n'
                      '衡量价格上涨/下跌的速度。\n\n'
                      '0-30: 超卖 — 价格跌太快，可能反弹（买入信号）\n'
                      '30-50: 偏弱 — 下行压力\n'
                      '50-70: 正常 — 健康上升趋势\n'
                      '70-100: 超买 — 价格涨太快，可能回调（卖出信号）\n\n'
                      '当前: ${rsi.toStringAsFixed(0)} (${_rsiLabel(rsi)})'
                    : 'RSI - Relative Strength Index (0-100)\n\n'
                      'Measures how fast price is moving up or down.\n\n'
                      '0-30: Oversold — Price dropped too fast, may bounce up (buy signal)\n'
                      '30-50: Weak — Downward pressure\n'
                      '50-70: Normal — Healthy uptrend\n'
                      '70-100: Overbought — Price rose too fast, may pull back (sell signal)\n\n'
                      'Current: ${rsi.toStringAsFixed(0)} (${_rsiLabel(rsi)})',
              ),
              const SizedBox(width: 8),
              _indicatorCard(
                icon: Icons.account_balance,
                title: 'Leverage',
                value: '${(funding * 100).toStringAsFixed(3)}%',
                label: _fundingLabel(funding),
                color: _fundingColor(funding),
                progress: (funding * 5000 + 50).clamp(0, 100) / 100,
                context: context,
                explanation: _isZh(context)
                    ? '资金费率（合约市场）\n\n'
                      '显示永续合约中多空双方谁在付费给对方。\n\n'
                      '正值 (>0.01%): 多头付费给空头 — 做多的人太多，可能下跌\n'
                      '接近零: 市场平衡\n'
                      '负值 (<-0.005%): 空头付费给多头 — 做空的人太多，可能反弹\n\n'
                      '当前: ${(funding * 100).toStringAsFixed(4)}% (${_fundingLabel(funding)})'
                    : 'Funding Rate (Futures Market)\n\n'
                      'Shows which side (long/short) is paying the other in perpetual futures.\n\n'
                      'Positive (>0.01%): Longs pay shorts — too many buyers, may drop\n'
                      'Near zero: Balanced market\n'
                      'Negative (<-0.005%): Shorts pay longs — too many sellers, may bounce\n\n'
                      'Current: ${(funding * 100).toStringAsFixed(4)}% (${_fundingLabel(funding)})',
              ),
            ],
          ),
          const SizedBox(height: 10),

          // 综合评分（点击查看解释）
          GestureDetector(
            onTap: () => _showExplanation(context,
                _isZh(context) ? '综合评分' : 'Composite Scores',
                _isZh(context)
                    ? '五个维度综合评估市场状况 (每项 0-100):\n\n'
                      'Trend — 价格动量（RSI + MACD + 涨跌幅 + 持仓量变化）\n'
                      'Mood — 市场情绪（恐慌指数 + 资金费率 + 多空比 + 新闻情绪）\n'
                      'Chain — 链上活跃度（交易所资金流 + 活跃地址 + SOPR）\n'
                      'Macro — 宏观环境（美元指数 + ETF 资金流 + 稳定币供给）\n'
                      'Safety — 安全程度（爆仓量 + 资金费率极端 + 订单簿深度）\n\n'
                      '>70 = 看涨  |  50 = 中性  |  <30 = 看跌'
                    : 'Five dimensions that together assess the overall market condition (0-100 each):\n\n'
                      'Trend — Price momentum (RSI + MACD + price change + OI change)\n'
                      'Mood — Market sentiment (Fear/Greed + funding rate + long/short ratio + news)\n'
                      'Chain — On-chain activity (exchange flow + active addresses + SOPR)\n'
                      'Macro — Macro environment (DXY + ETF flows + stablecoin supply)\n'
                      'Safety — Risk level (liquidations + funding extremes + order book depth)\n\n'
                      '>70 = Bullish  |  50 = Neutral  |  <30 = Bearish',
                const Color(0xFF3B82F6)),
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.03),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: data.scores.entries.map((e) {
                  final label = _scoreLabel(e.key);
                  final color = _scoreColor(e.value);
                  return Expanded(
                    child: Column(
                      children: [
                        Text(label,
                            style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.5),
                                fontSize: 10)),
                        const SizedBox(height: 4),
                        SizedBox(
                          width: 36,
                          height: 36,
                          child: Stack(
                            alignment: Alignment.center,
                            children: [
                              CircularProgressIndicator(
                                value: e.value / 100,
                                strokeWidth: 3,
                                backgroundColor: Colors.white.withValues(alpha: 0.08),
                                valueColor: AlwaysStoppedAnimation(color),
                              ),
                              Text('${e.value}',
                                  style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold)),
                            ],
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _indicatorCard({
    required IconData icon,
    required String title,
    required String value,
    required String label,
    required Color color,
    required double progress,
    required String explanation,
    required BuildContext context,
  }) {
    return Expanded(
      child: GestureDetector(
        onTap: () => _showExplanation(context, title, explanation, color),
        child: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: color.withValues(alpha: 0.15)),
          ),
          child: Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(icon, color: color, size: 14),
                  const SizedBox(width: 2),
                  Icon(Icons.info_outline, color: Colors.white.withValues(alpha: 0.3), size: 10),
                ],
              ),
              const SizedBox(height: 4),
              Text(value,
                  style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 2),
              Text(label,
                  style: TextStyle(color: color.withValues(alpha: 0.8), fontSize: 10, fontWeight: FontWeight.w600)),
              const SizedBox(height: 4),
              ClipRRect(
                borderRadius: BorderRadius.circular(2),
                child: LinearProgressIndicator(
                  value: progress.clamp(0, 1),
                  minHeight: 3,
                  backgroundColor: Colors.white.withValues(alpha: 0.1),
                  valueColor: AlwaysStoppedAnimation(color),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showExplanation(BuildContext context, String title, String text, Color color) {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF1A1A2E),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 36, height: 4,
                decoration: BoxDecoration(
                  color: Colors.white24,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(title,
                style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            Text(text,
                style: const TextStyle(color: Colors.white70, fontSize: 14, height: 1.6)),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  String _fgiLabel(int val) {
    if (val <= 10) return 'Extreme Fear';
    if (val <= 25) return 'Fear';
    if (val <= 45) return 'Cautious';
    if (val <= 55) return 'Neutral';
    if (val <= 75) return 'Greedy';
    if (val <= 90) return 'Very Greedy';
    return 'Extreme Greed';
  }

  String _rsiLabel(double val) {
    if (val <= 20) return 'Very Oversold';
    if (val <= 30) return 'Oversold';
    if (val <= 45) return 'Weak';
    if (val <= 55) return 'Neutral';
    if (val <= 70) return 'Strong';
    if (val <= 80) return 'Overbought';
    return 'Very Overbought';
  }

  String _fundingLabel(double val) {
    if (val > 0.02) return 'Longs Crowded';
    if (val > 0.005) return 'Bullish Bias';
    if (val > -0.005) return 'Balanced';
    if (val > -0.02) return 'Bearish Bias';
    return 'Shorts Crowded';
  }

  String _scoreLabel(String key) {
    const labels = {
      'momentum': 'Trend',
      'sentiment': 'Mood',
      'onchain': 'Chain',
      'macro': 'Macro',
      'risk': 'Safety',
    };
    return labels[key] ?? key;
  }

  bool _isZh(BuildContext context) {
    return Localizations.localeOf(context).languageCode == 'zh';
  }

  Color _fgiColor(int val) {
    if (val <= 20) return const Color(0xFFEF4444);
    if (val <= 40) return const Color(0xFFF97316);
    if (val <= 60) return const Color(0xFFFBBF24);
    if (val <= 80) return const Color(0xFF22C55E);
    return const Color(0xFF10B981);
  }

  Color _rsiColor(double val) {
    if (val <= 30) return const Color(0xFF22C55E);
    if (val >= 70) return const Color(0xFFEF4444);
    return const Color(0xFF64748B);
  }

  Color _fundingColor(double val) {
    if (val > 0.01) return const Color(0xFFEF4444);
    if (val < -0.005) return const Color(0xFF22C55E);
    return const Color(0xFF64748B);
  }

  Color _scoreColor(int val) {
    if (val >= 70) return const Color(0xFF22C55E);
    if (val >= 50) return const Color(0xFFFBBF24);
    if (val >= 30) return const Color(0xFFF97316);
    return const Color(0xFFEF4444);
  }
}
