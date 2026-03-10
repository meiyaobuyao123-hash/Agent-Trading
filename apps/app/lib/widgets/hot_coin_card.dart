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

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isStrong ? AppColors.strong.withValues(alpha: 0.3) : AppColors.divider,
            width: isStrong ? 1.0 : 0.5,
          ),
          boxShadow: AppColors.cardShadow,
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              // ── 排名 ──────────────────────────────────────
              _RankCol(rank: rank, isStrong: isStrong),
              const SizedBox(width: 12),

              // ── 链徽章 ────────────────────────────────────
              _ChainBadge(chain: coin.chain),
              const SizedBox(width: 10),

              // ── 代币名称 + 年龄 + 市值 ────────────────────
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          coin.symbol.toUpperCase(),
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        if (isStrong) ...[
                          const SizedBox(width: 6),
                          _Badge(
                            label: '强推',
                            color: AppColors.strong,
                            bg: AppColors.strongLight,
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 3),
                    Row(
                      children: [
                        Text(
                          _fmtMC(coin.marketCapUsd),
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          '${coin.ageDays.toStringAsFixed(0)}d',
                          style: const TextStyle(
                            color: AppColors.textTertiary,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              // ── 评分 + 24h涨跌 ────────────────────────────
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  // 综合分
                  _ScoreChip(score: coin.score),
                  const SizedBox(height: 4),
                  // 24h 涨跌
                  _PctChange(pct: coin.priceChange24h),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _fmtMC(double usd) {
    if (usd >= 1e6) return '\$${(usd / 1e6).toStringAsFixed(1)}M';
    if (usd >= 1e3) return '\$${(usd / 1e3).toStringAsFixed(0)}K';
    return '\$${usd.toStringAsFixed(0)}';
  }
}

// ─── 排名列 ──────────────────────────────────────────
class _RankCol extends StatelessWidget {
  final int rank;
  final bool isStrong;
  const _RankCol({required this.rank, required this.isStrong});

  @override
  Widget build(BuildContext context) {
    final bg = rank == 1
        ? const Color(0x33FFD700)
        : rank == 2
            ? const Color(0x33C0C0C0)
            : rank == 3
                ? const Color(0x33CD7F32)
                : isStrong
                    ? AppColors.strongLight
                    : AppColors.surfaceAlt;
    final fg = rank <= 3
        ? const Color(0xFFFFD700)
        : isStrong
            ? AppColors.strong
            : AppColors.textTertiary;

    return Container(
      width: 34,
      height: 34,
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(10)),
      alignment: Alignment.center,
      child: Text(
        '$rank',
        style: TextStyle(color: fg, fontSize: 14, fontWeight: FontWeight.w800),
      ),
    );
  }
}

// ─── 链徽章 ──────────────────────────────────────────
class _ChainBadge extends StatelessWidget {
  final String chain;
  const _ChainBadge({required this.chain});

  (String, Color, Color) get _style => switch (chain) {
        'solana' => ('SOL', const Color(0xFF9945FF), const Color(0x1A9945FF)),
        'bsc'    => ('BSC', const Color(0xFFF3BA2F), const Color(0x1AF3BA2F)),
        'base'   => ('BASE', const Color(0xFF0052FF), const Color(0x1A0052FF)),
        _        => (chain.toUpperCase(), AppColors.textSecondary, AppColors.surfaceAlt),
      };

  @override
  Widget build(BuildContext context) {
    final (label, fg, bg) = _style;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(6)),
      child: Text(
        label,
        style: TextStyle(color: fg, fontSize: 10, fontWeight: FontWeight.w700),
      ),
    );
  }
}

// ─── 评分圆角矩形 ────────────────────────────────────
class _ScoreChip extends StatelessWidget {
  final double score;
  const _ScoreChip({required this.score});

  Color get _color {
    if (score >= 72) return AppColors.strong;
    if (score >= 50) return AppColors.normal;
    return AppColors.textSecondary;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: _color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        score.toStringAsFixed(0),
        style: TextStyle(
          color: _color,
          fontSize: 13,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

// ─── 24h 涨跌幅 ──────────────────────────────────────
class _PctChange extends StatelessWidget {
  final double pct;
  const _PctChange({required this.pct});

  @override
  Widget build(BuildContext context) {
    final isPos = pct >= 0;
    final color = isPos ? AppColors.success : AppColors.danger;
    final sign  = isPos ? '+' : '';
    return Text(
      '$sign${pct.toStringAsFixed(1)}%',
      style: TextStyle(
        color: color,
        fontSize: 12,
        fontWeight: FontWeight.w600,
      ),
    );
  }
}

// ─── 标签徽章 ────────────────────────────────────────
class _Badge extends StatelessWidget {
  final String label;
  final Color color;
  final Color bg;
  const _Badge({required this.label, required this.color, required this.bg});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(5)),
      child: Text(
        label,
        style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w700),
      ),
    );
  }
}
