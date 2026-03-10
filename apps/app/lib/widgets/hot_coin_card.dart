import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import '../models/hot_coin.dart';
import '../theme/app_colors.dart';

class HotCoinCard extends StatelessWidget {
  final HotCoin coin;
  final int rank;
  final VoidCallback? onTap;

  const HotCoinCard({super.key, required this.coin, required this.rank, this.onTap});

  @override
  Widget build(BuildContext context) {
    final isStrong = coin.recommendation == 'strong';

    return CupertinoButton(
      padding: EdgeInsets.zero,
      onPressed: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            // ── 代币头像 ──────────────────────
            _TokenAvatar(coin: coin, rank: rank),
            const SizedBox(width: 12),

            // ── 名称 + 市值/年龄/链 ──────────
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          coin.symbol.toUpperCase(),
                          style: const TextStyle(
                            color: AppColors.textPrimary, fontSize: 16,
                            fontWeight: FontWeight.w600, letterSpacing: -0.3,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 4),
                      _ChainDot(chain: coin.chain),
                      if (isStrong) ...[
                        const SizedBox(width: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                          decoration: BoxDecoration(
                            color: AppColors.strong.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text('HOT',
                              style: TextStyle(color: AppColors.strong, fontSize: 10, fontWeight: FontWeight.w700)),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '${_fmtMC(coin.marketCapUsd)} · ${coin.ageDays.toStringAsFixed(0)}天',
                    style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
                  ),
                ],
              ),
            ),

            // ── 右侧：价格 + 涨跌幅 ──────────
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  _fmtPrice(coin.priceUsd),
                  style: const TextStyle(
                    color: AppColors.textPrimary, fontSize: 15,
                    fontWeight: FontWeight.w600, letterSpacing: -0.3,
                  ),
                ),
                const SizedBox(height: 3),
                _ChangeChip(pct: coin.priceChange24h),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _fmtMC(double usd) {
    if (usd >= 1e6) return '\$${(usd / 1e6).toStringAsFixed(1)}M';
    if (usd >= 1e3) return '\$${(usd / 1e3).toStringAsFixed(0)}K';
    return '\$${usd.toStringAsFixed(0)}';
  }

  String _fmtPrice(double p) {
    if (p >= 1) return '\$${p.toStringAsFixed(2)}';
    if (p >= 0.01) return '\$${p.toStringAsFixed(4)}';
    if (p >= 0.0001) return '\$${p.toStringAsFixed(6)}';
    return '\$${p.toStringAsFixed(8)}';
  }
}

// ─── 代币头像（网络图片 or 首字母） ──────────────
class _TokenAvatar extends StatelessWidget {
  final HotCoin coin;
  final int rank;
  const _TokenAvatar({required this.coin, required this.rank});

  Color get _chainColor => switch (coin.chain) {
    'solana' => const Color(0xFF9945FF),
    'bsc'    => const Color(0xFFF3BA2F),
    'base'   => const Color(0xFF0052FF),
    _        => AppColors.primary,
  };

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 44, height: 44,
      child: Stack(
        children: [
          if (coin.imageUrl != null && coin.imageUrl!.isNotEmpty)
            Container(
              width: 44, height: 44,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(22),
                border: Border.all(color: _chainColor.withValues(alpha: 0.15), width: 1.5),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(20),
                child: Image.network(
                  coin.imageUrl!,
                  width: 41, height: 41, fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => _letterAvatar(),
                ),
              ),
            )
          else
            _letterAvatar(),

          if (rank <= 3)
            Positioned(
              right: 0, bottom: 0,
              child: Container(
                width: 16, height: 16,
                decoration: BoxDecoration(
                  color: rank == 1 ? const Color(0xFFFFD700)
                      : rank == 2 ? const Color(0xFFC0C0C0)
                      : const Color(0xFFCD7F32),
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.surface, width: 1.5),
                ),
                alignment: Alignment.center,
                child: Text('$rank',
                    style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.w800)),
              ),
            ),
        ],
      ),
    );
  }

  Widget _letterAvatar() {
    return Container(
      width: 44, height: 44,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [_chainColor.withValues(alpha: 0.15), _chainColor.withValues(alpha: 0.05)],
        ),
        borderRadius: BorderRadius.circular(22),
      ),
      alignment: Alignment.center,
      child: Text(
        coin.symbol.isNotEmpty ? coin.symbol[0].toUpperCase() : '?',
        style: TextStyle(color: _chainColor, fontSize: 18, fontWeight: FontWeight.w700),
      ),
    );
  }
}

// ─── 链色圆点 ──────────────────────────────
class _ChainDot extends StatelessWidget {
  final String chain;
  const _ChainDot({required this.chain});

  Color get _color => switch (chain) {
    'solana' => const Color(0xFF9945FF),
    'bsc'    => const Color(0xFFF3BA2F),
    'base'   => const Color(0xFF0052FF),
    _        => AppColors.textSecondary,
  };

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 7, height: 7,
      decoration: BoxDecoration(color: _color, shape: BoxShape.circle),
    );
  }
}

// ─── 涨跌幅胶囊 ──────────────────────────────
class _ChangeChip extends StatelessWidget {
  final double pct;
  const _ChangeChip({required this.pct});

  @override
  Widget build(BuildContext context) {
    final isPos = pct >= 0;
    final color = isPos ? AppColors.success : AppColors.danger;
    final sign  = isPos ? '+' : '';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        '$sign${pct.toStringAsFixed(1)}%',
        style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w600),
      ),
    );
  }
}
