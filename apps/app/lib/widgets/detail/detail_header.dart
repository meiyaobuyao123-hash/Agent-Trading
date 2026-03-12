import 'package:flutter/material.dart';
import '../../models/token_detail.dart';
import '../../theme/app_colors.dart';

/// 详情页头部：代币头像 + 名称 + 价格 + 多时段涨跌
class DetailHeader extends StatelessWidget {
  final TokenDetail token;
  final String? imageUrl;

  const DetailHeader({super.key, required this.token, this.imageUrl});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: context.colors.cardGlass,
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [
          BoxShadow(color: Color(0x0A000000), blurRadius: 10, offset: Offset(0, 2)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 代币信息行
          Row(
            children: [
              _TokenAvatar(token: token, imageUrl: imageUrl),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            token.symbol.toUpperCase(),
                            style: TextStyle(
                              fontSize: 22, fontWeight: FontWeight.w800,
                              color: context.colors.textPrimary, letterSpacing: -0.5,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: 8),
                        _ChainBadge(chain: token.chain),
                        if (token.recommendation == 'strong') ...[
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              gradient: const LinearGradient(
                                colors: [Color(0xFF34C759), Color(0xFF30D158)],
                              ),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text('强推',
                                style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700,
                                    color: Colors.white)),
                          ),
                        ],
                      ],
                    ),
                    if (token.name.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text(token.name,
                            style: TextStyle(fontSize: 13, color: context.colors.textSecondary),
                            overflow: TextOverflow.ellipsis),
                      ),
                  ],
                ),
              ),
              if (token.ageDays > 0)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: context.colors.bg,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text('${token.ageDays.toStringAsFixed(0)}天',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500,
                          color: context.colors.textSecondary)),
                ),
            ],
          ),
          const SizedBox(height: 16),

          // 价格
          if (token.priceUsd > 0) ...[
            Text(_fmtPrice(token.priceUsd),
              style: TextStyle(
                fontSize: 34, fontWeight: FontWeight.w800,
                color: context.colors.textPrimary, letterSpacing: -1.5, height: 1.1,
              ),
            ),
            const SizedBox(height: 12),
          ],

          // 多时段涨跌胶囊
          Row(children: [
            _ChangePill(label: '5m', pct: token.priceChange5m),
            const SizedBox(width: 6),
            _ChangePill(label: '1h', pct: token.priceChange1h),
            const SizedBox(width: 6),
            _ChangePill(label: '4h', pct: token.priceChange4h),
            const SizedBox(width: 6),
            _ChangePill(label: '24h', pct: token.priceChange24h),
          ]),
        ],
      ),
    );
  }

  String _fmtPrice(double p) {
    if (p >= 1) return '\$${p.toStringAsFixed(2)}';
    if (p >= 0.01) return '\$${p.toStringAsFixed(4)}';
    if (p >= 0.0001) return '\$${p.toStringAsFixed(6)}';
    return '\$${p.toStringAsFixed(8)}';
  }
}

class _TokenAvatar extends StatelessWidget {
  final TokenDetail token;
  final String? imageUrl;
  const _TokenAvatar({required this.token, this.imageUrl});

  Color _c(BuildContext context) => switch (token.chain) {
    'solana' => const Color(0xFF9945FF),
    'bsc' => const Color(0xFFF3BA2F),
    'base' => const Color(0xFF0052FF),
    'eth' => const Color(0xFF627EEA),
    _ => context.colors.primary,
  };

  @override
  Widget build(BuildContext context) {
    final cc = _c(context);
    if (imageUrl != null && imageUrl!.isNotEmpty) {
      return Container(
        width: 48, height: 48,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: cc.withValues(alpha: 0.2), width: 2),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(22),
          child: Image.network(
            imageUrl!,
            width: 44, height: 44,
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => _fallbackAvatar(cc),
          ),
        ),
      );
    }
    return _fallbackAvatar(cc);
  }

  Widget _fallbackAvatar(Color cc) {
    return Container(
      width: 48, height: 48,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [cc.withValues(alpha: 0.15), cc.withValues(alpha: 0.05)],
        ),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: cc.withValues(alpha: 0.15), width: 1.5),
      ),
      alignment: Alignment.center,
      child: Text(
        token.symbol.isNotEmpty ? token.symbol[0].toUpperCase() : '?',
        style: TextStyle(color: cc, fontSize: 20, fontWeight: FontWeight.w800),
      ),
    );
  }
}

class _ChainBadge extends StatelessWidget {
  final String chain;
  const _ChainBadge({required this.chain});

  Color _color(BuildContext context) => switch (chain) {
    'solana' => const Color(0xFF9945FF),
    'bsc' => const Color(0xFFF3BA2F),
    'base' => const Color(0xFF0052FF),
    'eth' => const Color(0xFF627EEA),
    _ => context.colors.textSecondary,
  };

  @override
  Widget build(BuildContext context) {
    final cc = _color(context);
    final label = switch (chain) { 'solana' => 'SOL', 'bsc' => 'BSC', 'base' => 'BASE', 'eth' => 'ETH', _ => chain.toUpperCase() };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: cc.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: cc.withValues(alpha: 0.2), width: 0.5),
      ),
      child: Text(label, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: cc)),
    );
  }
}

class _ChangePill extends StatelessWidget {
  final String label;
  final double pct;
  const _ChangePill({required this.label, required this.pct});
  @override
  Widget build(BuildContext context) {
    if (pct == 0) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(color: context.colors.bg, borderRadius: BorderRadius.circular(8)),
        child: Text('$label  0%', style: TextStyle(fontSize: 13, color: context.colors.textSecondary)),
      );
    }
    final isPos = pct >= 0;
    final color = isPos ? context.colors.success : context.colors.danger;
    final sign = isPos ? '+' : '';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(8)),
      child: Text('$label  $sign${pct.toStringAsFixed(1)}%',
          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: color)),
    );
  }
}
