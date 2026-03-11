import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/hot_coin.dart';
import '../theme/app_colors.dart';

/// Glassmorphism 风格热币卡片
/// 排名 | 头像 | Symbol·Name [Chain] | 价格 + 涨跌框
class HotCoinCard extends StatefulWidget {
  final HotCoin coin;
  final int rank;
  final VoidCallback? onTap;
  final double? livePrice;
  final double? liveChange24h;

  const HotCoinCard({
    super.key,
    required this.coin,
    required this.rank,
    this.onTap,
    this.livePrice,
    this.liveChange24h,
  });

  @override
  State<HotCoinCard> createState() => _HotCoinCardState();
}

class _HotCoinCardState extends State<HotCoinCard> {
  bool _pressed = false;
  double? _prevPrice;
  Color _flashColor = Colors.transparent;

  @override
  void initState() {
    super.initState();
    _prevPrice = widget.livePrice ?? widget.coin.priceUsd;
  }

  @override
  void didUpdateWidget(HotCoinCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    final newPrice = widget.livePrice ?? widget.coin.priceUsd;
    if (_prevPrice != null && newPrice != _prevPrice) {
      final c = context.colors;
      setState(() {
        _flashColor = newPrice > _prevPrice!
            ? c.success.withValues(alpha: 0.08)
            : c.danger.withValues(alpha: 0.08);
      });
      Future.delayed(const Duration(milliseconds: 600), () {
        if (mounted) setState(() => _flashColor = Colors.transparent);
      });
    }
    _prevPrice = newPrice;
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final coin = widget.coin;
    final isStrong = coin.recommendation == 'strong';
    final price = widget.livePrice ?? coin.priceUsd;
    final change24h = widget.liveChange24h ?? coin.priceChange24h;

    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        HapticFeedback.selectionClick();
        widget.onTap?.call();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: AnimatedScale(
        scale: _pressed ? 0.97 : 1.0,
        duration: const Duration(milliseconds: 100),
        curve: Curves.easeOut,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 400),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: _flashColor,
          ),
          child: Row(
            children: [
              // ── 排名 ────────────────────────
              SizedBox(
                width: 24,
                child: widget.rank <= 3
                    ? _RankMedal(rank: widget.rank)
                    : Text(
                        '${widget.rank}',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: c.textTertiary,
                          fontFeatures: const [FontFeature.tabularFigures()],
                        ),
                      ),
              ),
              const SizedBox(width: 8),

              // ── 头像 ────────────────────────
              _TokenAvatar(coin: coin, size: 38),
              const SizedBox(width: 10),

              // ── 中间：名称 + 指标行 ──────────
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Row(
                      children: [
                        Text(
                          coin.symbol.toUpperCase(),
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: c.textPrimary,
                            letterSpacing: -0.3,
                          ),
                        ),
                        if (coin.name.isNotEmpty &&
                            coin.name.toLowerCase() != coin.symbol.toLowerCase()) ...[
                          const SizedBox(width: 4),
                          Flexible(
                            child: Text(
                              coin.name,
                              style: TextStyle(fontSize: 11, color: c.textTertiary),
                              overflow: TextOverflow.ellipsis,
                              maxLines: 1,
                            ),
                          ),
                        ],
                        const SizedBox(width: 5),
                        _ChainBadge(chain: coin.chain),
                        if (isStrong) ...[
                          const SizedBox(width: 4),
                          const _HotBadge(),
                        ],
                      ],
                    ),
                    const SizedBox(height: 5),
                    _MetricsRow(coin: coin),
                  ],
                ),
              ),
              const SizedBox(width: 8),

              // ── 右侧：价格 + 涨跌框 ─────────
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    _fmtPrice(price),
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: c.textPrimary,
                      letterSpacing: -0.5,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                  const SizedBox(height: 4),
                  _ChangeBox(pct: change24h),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _fmtPrice(double p) {
    if (p >= 1000) return '\$${p.toStringAsFixed(0)}';
    if (p >= 1) return '\$${p.toStringAsFixed(2)}';
    if (p >= 0.01) return '\$${p.toStringAsFixed(4)}';
    if (p >= 0.0001) return '\$${p.toStringAsFixed(6)}';
    return '\$${p.toStringAsFixed(8)}';
  }
}

// ─── 排名奖牌（前3名）─────────────────────────
class _RankMedal extends StatelessWidget {
  final int rank;
  const _RankMedal({required this.rank});

  @override
  Widget build(BuildContext context) {
    final color = switch (rank) {
      1 => const Color(0xFFFFD700),
      2 => const Color(0xFFC0C0C0),
      _ => const Color(0xFFCD7F32),
    };
    return Container(
      width: 22,
      height: 22,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [color, color.withValues(alpha: 0.7)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(7),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.3),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      alignment: Alignment.center,
      child: Text(
        '$rank',
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w800,
          color: Colors.white,
        ),
      ),
    );
  }
}

// ─── 代币头像 ─────────────────────────────────
class _TokenAvatar extends StatelessWidget {
  final HotCoin coin;
  final double size;
  const _TokenAvatar({required this.coin, required this.size});

  Color get _chainColor => switch (coin.chain) {
    'solana' => const Color(0xFF9945FF),
    'bsc'    => const Color(0xFFF3BA2F),
    'base'   => const Color(0xFF0052FF),
    _        => const Color(0xFF3B82F6),
  };

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(
          color: _chainColor.withValues(alpha: 0.2),
          width: 1.5,
        ),
      ),
      child: coin.imageUrl != null && coin.imageUrl!.isNotEmpty
          ? ClipRRect(
              borderRadius: BorderRadius.circular(size / 2),
              child: Image.network(
                coin.imageUrl!,
                width: size,
                height: size,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => _letterAvatar(context),
              ),
            )
          : _letterAvatar(context),
    );
  }

  Widget _letterAvatar(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: _chainColor.withValues(alpha: 0.12),
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        coin.symbol.isNotEmpty ? coin.symbol[0].toUpperCase() : '?',
        style: TextStyle(
          color: _chainColor,
          fontSize: size * 0.4,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

// ─── 链标签（玻璃风格）────────────────────────
class _ChainBadge extends StatelessWidget {
  final String chain;
  const _ChainBadge({required this.chain});

  Color get _color => switch (chain) {
    'solana' => const Color(0xFF9945FF),
    'bsc'    => const Color(0xFFF3BA2F),
    'base'   => const Color(0xFF0052FF),
    _        => const Color(0xFF64748B),
  };

  String get _label => switch (chain) {
    'solana' => 'SOL',
    'bsc'    => 'BSC',
    'base'   => 'BASE',
    _        => chain.toUpperCase(),
  };

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
      decoration: BoxDecoration(
        color: _color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: _color.withValues(alpha: 0.15), width: 0.5),
      ),
      child: Text(
        _label,
        style: TextStyle(
          color: _color,
          fontSize: 9,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.3,
        ),
      ),
    );
  }
}

// ─── HOT 标签（带光晕）──────────────────────
class _HotBadge extends StatelessWidget {
  const _HotBadge();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
      decoration: BoxDecoration(
        gradient: c.successGradient,
        borderRadius: BorderRadius.circular(4),
        boxShadow: [
          BoxShadow(
            color: c.success.withValues(alpha: 0.3),
            blurRadius: 4,
          ),
        ],
      ),
      child: const Text(
        'HOT',
        style: TextStyle(
          color: Colors.white,
          fontSize: 8,
          fontWeight: FontWeight.w800,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}

// ─── 指标行 (MC · Vol · Holders) ───────────────
class _MetricsRow extends StatelessWidget {
  final HotCoin coin;
  const _MetricsRow({required this.coin});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Row(
      children: [
        Text(
          _fmtCompact(coin.marketCapUsd),
          style: TextStyle(fontSize: 11, color: c.textSecondary),
        ),
        _Dot(color: c.textTertiary),
        Text(
          'Vol ${_fmtCompact(coin.volume24hUsd)}',
          style: TextStyle(fontSize: 11, color: c.textSecondary),
        ),
        if (coin.holderCount > 0) ...[
          _Dot(color: c.textTertiary),
          Icon(Icons.people_outline, size: 10, color: c.textTertiary),
          const SizedBox(width: 2),
          Text(
            _fmtNum(coin.holderCount),
            style: TextStyle(fontSize: 11, color: c.textSecondary),
          ),
        ],
      ],
    );
  }

  String _fmtCompact(double v) {
    if (v >= 1e9) return '\$${(v / 1e9).toStringAsFixed(1)}B';
    if (v >= 1e6) return '\$${(v / 1e6).toStringAsFixed(1)}M';
    if (v >= 1e3) return '\$${(v / 1e3).toStringAsFixed(0)}K';
    if (v > 0) return '\$${v.toStringAsFixed(0)}';
    return '-';
  }

  String _fmtNum(int n) {
    if (n >= 1000000) return '${(n / 1000000).toStringAsFixed(1)}M';
    if (n >= 1000) return '${(n / 1000).toStringAsFixed(1)}K';
    return '$n';
  }
}

// ─── 分隔点 ────────────────────────────────────
class _Dot extends StatelessWidget {
  final Color color;
  const _Dot({required this.color});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Text(
        '·',
        style: TextStyle(
          fontSize: 11,
          color: color,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

// ─── 涨跌框（渐变填充）─────────────────────────
class _ChangeBox extends StatelessWidget {
  final double pct;
  const _ChangeBox({required this.pct});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final isPos = pct >= 0;
    final gradient = isPos ? c.successGradient : c.dangerGradient;
    final sign = isPos ? '+' : '';

    return Container(
      constraints: const BoxConstraints(minWidth: 72),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: BorderRadius.circular(6),
        boxShadow: [
          BoxShadow(
            color: (isPos ? c.success : c.danger).withValues(alpha: 0.2),
            blurRadius: 4,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      alignment: Alignment.center,
      child: Text(
        '$sign${pct.toStringAsFixed(2)}%',
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.w700,
          fontFeatures: [FontFeature.tabularFigures()],
        ),
      ),
    );
  }
}
