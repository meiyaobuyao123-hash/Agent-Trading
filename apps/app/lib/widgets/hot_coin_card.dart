import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/hot_coin.dart';
import '../theme/app_colors.dart';
import '../utils/chain_utils.dart';
import '../utils/format_utils.dart';
import 'common/token_avatar.dart';
import 'common/rank_medal.dart';
import 'common/chain_badge.dart';

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
  Timer? _flashTimer;

  @override
  void initState() {
    super.initState();
    _prevPrice = widget.livePrice ?? widget.coin.priceUsd;
  }

  @override
  void dispose() {
    _flashTimer?.cancel();
    super.dispose();
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
      _flashTimer?.cancel();
      _flashTimer = Timer(const Duration(milliseconds: 600), () {
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
                    ? RankMedal(rank: widget.rank)
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
              TokenAvatar(imageUrl: ChainUtils.tokenImageUrl(coin.imageUrl, coin.chain, coin.address), symbol: coin.symbol, chain: coin.chain, size: 38),
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
                        ChainBadge(chain: coin.chain),
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
                    FormatUtils.fmtPrice(price),
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
}

// ─── HOT 标签（纯色简洁）──────────────────────
class _HotBadge extends StatelessWidget {
  const _HotBadge();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
      decoration: BoxDecoration(
        color: c.warning.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        'HOT',
        style: TextStyle(
          color: c.warning,
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
        Flexible(
          child: Text(
            FormatUtils.fmtCompact(coin.marketCapUsd),
            style: TextStyle(fontSize: 11, color: c.textSecondary),
            overflow: TextOverflow.ellipsis,
          ),
        ),
        _Dot(color: c.textTertiary),
        Flexible(
          child: Text(
            'Vol ${FormatUtils.fmtCompact(coin.volume24hUsd)}',
            style: TextStyle(fontSize: 11, color: c.textSecondary),
            overflow: TextOverflow.ellipsis,
          ),
        ),
        if (coin.holderCount > 0) ...[
          _Dot(color: c.textTertiary),
          Icon(Icons.people_outline, size: 10, color: c.textTertiary),
          const SizedBox(width: 2),
          Text(
            FormatUtils.fmtNum(coin.holderCount),
            style: TextStyle(fontSize: 11, color: c.textSecondary),
          ),
        ],
      ],
    );
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

// ─── 涨跌框（纯色简洁）─────────────────────────
class _ChangeBox extends StatelessWidget {
  final double pct;
  const _ChangeBox({required this.pct});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final isPos = pct >= 0;
    final color = isPos ? c.success : c.danger;
    final sign = isPos ? '+' : '';

    return Container(
      constraints: const BoxConstraints(minWidth: 72),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      alignment: Alignment.center,
      child: Text(
        '$sign${pct.toStringAsFixed(2)}%',
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w700,
          fontFeatures: const [FontFeature.tabularFigures()],
        ),
      ),
    );
  }
}
