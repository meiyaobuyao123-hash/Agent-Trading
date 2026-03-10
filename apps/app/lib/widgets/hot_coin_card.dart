import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/hot_coin.dart';
import '../theme/app_colors.dart';

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

class _HotCoinCardState extends State<HotCoinCard>
    with SingleTickerProviderStateMixin {
  bool _pressed = false;
  double? _prevPrice;
  Color _flashColor = Colors.transparent;

  @override
  void didUpdateWidget(HotCoinCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    // 价格闪烁效果
    final newPrice = widget.livePrice ?? widget.coin.priceUsd;
    if (_prevPrice != null && newPrice != _prevPrice) {
      setState(() {
        _flashColor = newPrice > _prevPrice!
            ? AppColors.success.withValues(alpha: 0.15)
            : AppColors.danger.withValues(alpha: 0.15);
      });
      Future.delayed(const Duration(milliseconds: 600), () {
        if (mounted) setState(() => _flashColor = Colors.transparent);
      });
    }
    _prevPrice = newPrice;
  }

  @override
  void initState() {
    super.initState();
    _prevPrice = widget.livePrice ?? widget.coin.priceUsd;
  }

  @override
  Widget build(BuildContext context) {
    final coin = widget.coin;
    final isStrong = coin.recommendation == 'strong';
    final price = widget.livePrice ?? coin.priceUsd;
    final change = widget.liveChange24h ?? coin.priceChange24h;

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
        duration: const Duration(milliseconds: 120),
        curve: Curves.easeOut,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 500),
          curve: Curves.easeOut,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            color: _flashColor == Colors.transparent
                ? Colors.transparent
                : _flashColor,
          ),
          child: Row(
            children: [
              // ── 代币头像 ──────────────────────
              _TokenAvatar(coin: coin, rank: widget.rank, isStrong: isStrong),
              const SizedBox(width: 12),

              // ── 名称 + 链标签 + 市值 ──────────
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
                              color: AppColors.textPrimary,
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                              letterSpacing: -0.3,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: 6),
                        _ChainLabel(chain: coin.chain),
                        if (isStrong) ...[
                          const SizedBox(width: 6),
                          _HotBadge(),
                        ],
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${_fmtMC(coin.marketCapUsd)}  ·  ${coin.ageDays.toStringAsFixed(0)}天',
                      style: const TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 13,
                        letterSpacing: -0.1,
                      ),
                    ),
                  ],
                ),
              ),

              // ── 右侧：价格 + 涨跌幅 ──
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    _fmtPrice(price),
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -0.5,
                      fontFeatures: [FontFeature.tabularFigures()],
                    ),
                  ),
                  const SizedBox(height: 4),
                  _ChangeChip(pct: change),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _fmtMC(double usd) {
    if (usd >= 1e9) return '\$${(usd / 1e9).toStringAsFixed(1)}B';
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

// ─── 代币头像（网络图片 or 首字母）──────────────
class _TokenAvatar extends StatelessWidget {
  final HotCoin coin;
  final int rank;
  final bool isStrong;
  const _TokenAvatar({required this.coin, required this.rank, required this.isStrong});

  Color get _chainColor => switch (coin.chain) {
    'solana' => const Color(0xFF9945FF),
    'bsc'    => const Color(0xFFF3BA2F),
    'base'   => const Color(0xFF0052FF),
    _        => AppColors.primary,
  };

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 46, height: 46,
      child: Stack(
        children: [
          // 外圈光环（强推加金色）
          Container(
            width: 46, height: 46,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: isStrong
                    ? AppColors.accentGold.withValues(alpha: 0.4)
                    : _chainColor.withValues(alpha: 0.2),
                width: isStrong ? 2.5 : 2,
              ),
              boxShadow: isStrong ? [
                BoxShadow(
                  color: AppColors.accentGold.withValues(alpha: 0.15),
                  blurRadius: 8,
                  spreadRadius: 1,
                ),
              ] : null,
            ),
          ),
          // 头像内容
          Positioned.fill(
            child: Padding(
              padding: const EdgeInsets.all(2),
              child: coin.imageUrl != null && coin.imageUrl!.isNotEmpty
                  ? ClipOval(
                      child: Image.network(
                        coin.imageUrl!,
                        width: 42, height: 42, fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => _letterAvatar(),
                      ),
                    )
                  : _letterAvatar(),
            ),
          ),
          // 排名 badge
          if (rank <= 3)
            Positioned(
              right: -1, bottom: -1,
              child: Container(
                width: 18, height: 18,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft, end: Alignment.bottomRight,
                    colors: rank == 1
                        ? [const Color(0xFFFFD700), const Color(0xFFF0C020)]
                        : rank == 2
                            ? [const Color(0xFFC0C0C0), const Color(0xFFA0A0A0)]
                            : [const Color(0xFFCD7F32), const Color(0xFFB06020)],
                  ),
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.surface, width: 2),
                  boxShadow: const [
                    BoxShadow(color: Color(0x20000000), blurRadius: 3, offset: Offset(0, 1)),
                  ],
                ),
                alignment: Alignment.center,
                child: Text('$rank',
                    style: const TextStyle(
                      color: Colors.white, fontSize: 9,
                      fontWeight: FontWeight.w800,
                      height: 1,
                    )),
              ),
            ),
        ],
      ),
    );
  }

  Widget _letterAvatar() {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [_chainColor.withValues(alpha: 0.18), _chainColor.withValues(alpha: 0.06)],
        ),
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        coin.symbol.isNotEmpty ? coin.symbol[0].toUpperCase() : '?',
        style: TextStyle(color: _chainColor, fontSize: 18, fontWeight: FontWeight.w700),
      ),
    );
  }
}

// ─── 链标签（彩色文字）──────────────────────────
class _ChainLabel extends StatelessWidget {
  final String chain;
  const _ChainLabel({required this.chain});

  Color get _color => switch (chain) {
    'solana' => const Color(0xFF9945FF),
    'bsc'    => const Color(0xFFF3BA2F),
    'base'   => const Color(0xFF0052FF),
    _        => AppColors.textSecondary,
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
        color: _color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        _label,
        style: TextStyle(
          color: _color,
          fontSize: 10,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.3,
        ),
      ),
    );
  }
}

// ─── HOT 徽章 ──────────────────────────────
class _HotBadge extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF34C759), Color(0xFF30D158)],
        ),
        borderRadius: BorderRadius.circular(4),
        boxShadow: [
          BoxShadow(
            color: AppColors.success.withValues(alpha: 0.25),
            blurRadius: 4,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: const Text('HOT',
          style: TextStyle(
            color: Colors.white,
            fontSize: 9,
            fontWeight: FontWeight.w800,
            letterSpacing: 0.5,
          )),
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
    final arrow = isPos ? '▲' : '▼';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3.5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(arrow,
            style: TextStyle(color: color, fontSize: 8, height: 1)),
          const SizedBox(width: 2),
          Text(
            '$sign${pct.toStringAsFixed(1)}%',
            style: TextStyle(
              color: color,
              fontSize: 13,
              fontWeight: FontWeight.w700,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}
