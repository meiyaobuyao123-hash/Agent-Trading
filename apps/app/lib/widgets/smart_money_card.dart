import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/smart_money_signal.dart';
import '../theme/app_colors.dart';

/// 聪明钱信号卡片
/// 显示: 代币头像 | Symbol·Chain | 买入/卖出钱包数 + 量 | 价格 + 热度
class SmartMoneyCard extends StatefulWidget {
  final SmartMoneySignal signal;
  final int rank;
  final VoidCallback? onTap;

  const SmartMoneyCard({
    super.key,
    required this.signal,
    required this.rank,
    this.onTap,
  });

  @override
  State<SmartMoneyCard> createState() => _SmartMoneyCardState();
}

class _SmartMoneyCardState extends State<SmartMoneyCard> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final sig = widget.signal;
    final isStrong = sig.signalStrength == 'strong';

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
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              // ── 排名 ────────────────────
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

              // ── 头像 ────────────────────
              _SignalAvatar(signal: sig, size: 38),
              const SizedBox(width: 10),

              // ── 中间：名称 + 买卖指标 ────
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            sig.tokenSymbol.isNotEmpty
                                ? sig.tokenSymbol.toUpperCase()
                                : sig.tokenAddress.substring(0, 6),
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              color: c.textPrimary,
                              letterSpacing: -0.3,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: 5),
                        _ChainBadge(chain: sig.chain),
                        if (isStrong) ...[
                          const SizedBox(width: 4),
                          _SignalBadge(strength: sig.signalStrength),
                        ],
                      ],
                    ),
                    const SizedBox(height: 5),
                    // 买卖指标行
                    Row(
                      children: [
                        // 买入
                        Icon(Icons.arrow_upward_rounded, size: 10,
                            color: c.success),
                        const SizedBox(width: 2),
                        Text(
                          '${sig.uniqueBuyers}钱包',
                          style: TextStyle(
                            fontSize: 11, color: c.success,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(width: 6),
                        // 卖出
                        Icon(Icons.arrow_downward_rounded, size: 10,
                            color: c.danger),
                        const SizedBox(width: 2),
                        Text(
                          '${sig.uniqueSellers}钱包',
                          style: TextStyle(
                            fontSize: 11, color: c.danger,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        if (sig.eliteBuyCount > 0) ...[
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 4, vertical: 1),
                            decoration: BoxDecoration(
                              color: c.accentGold.withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(3),
                            ),
                            child: Text(
                              '${sig.eliteBuyCount}精英',
                              style: TextStyle(
                                fontSize: 9,
                                fontWeight: FontWeight.w700,
                                color: c.accentGold,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),

              // ── 右侧：价格 + 热度 ─────────
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (sig.priceUsd > 0)
                    Text(
                      _fmtPrice(sig.priceUsd),
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: c.textPrimary,
                        letterSpacing: -0.5,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    )
                  else
                    Text(
                      sig.timeAgo,
                      style: TextStyle(
                        fontSize: 12, color: c.textTertiary,
                      ),
                    ),
                  const SizedBox(height: 4),
                  _HeatBox(score: sig.heatScore, isBullish: sig.isBullish),
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

// ─── 排名奖牌 ─────────────────────────────────
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
      width: 22, height: 22,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [color, color.withValues(alpha: 0.7)],
          begin: Alignment.topLeft, end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(7),
        boxShadow: [BoxShadow(
          color: color.withValues(alpha: 0.3), blurRadius: 6,
          offset: const Offset(0, 2),
        )],
      ),
      alignment: Alignment.center,
      child: Text('$rank', style: const TextStyle(
        fontSize: 11, fontWeight: FontWeight.w800, color: Colors.white,
      )),
    );
  }
}

// ─── 信号头像 ────────────────────────────────────
class _SignalAvatar extends StatelessWidget {
  final SmartMoneySignal signal;
  final double size;
  const _SignalAvatar({required this.signal, required this.size});

  Color get _chainColor => switch (signal.chain) {
    'solana' => const Color(0xFF9945FF),
    'bsc' => const Color(0xFFF3BA2F),
    'base' => const Color(0xFF0052FF),
    'eth' => const Color(0xFF627EEA),
    _ => const Color(0xFF3B82F6),
  };

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size, height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: _chainColor.withValues(alpha: 0.2), width: 1.5),
      ),
      child: signal.imageUrl != null && signal.imageUrl!.isNotEmpty
          ? ClipRRect(
              borderRadius: BorderRadius.circular(size / 2),
              child: Image.network(signal.imageUrl!, width: size, height: size,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => _letterAvatar(context),
              ),
            )
          : _letterAvatar(context),
    );
  }

  Widget _letterAvatar(BuildContext context) {
    final letter = signal.tokenSymbol.isNotEmpty
        ? signal.tokenSymbol[0].toUpperCase()
        : '?';
    return Container(
      width: size, height: size,
      decoration: BoxDecoration(
        color: _chainColor.withValues(alpha: 0.12),
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(letter, style: TextStyle(
        color: _chainColor, fontSize: size * 0.4, fontWeight: FontWeight.w700,
      )),
    );
  }
}

// ─── 链标签 ──────────────────────────────────────
class _ChainBadge extends StatelessWidget {
  final String chain;
  const _ChainBadge({required this.chain});

  Color get _color => switch (chain) {
    'solana' => const Color(0xFF9945FF),
    'bsc' => const Color(0xFFF3BA2F),
    'base' => const Color(0xFF0052FF),
    'eth' => const Color(0xFF627EEA),
    _ => const Color(0xFF64748B),
  };

  String get _label => switch (chain) {
    'solana' => 'SOL', 'bsc' => 'BSC', 'base' => 'BASE', 'eth' => 'ETH',
    _ => chain.toUpperCase(),
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
      child: Text(_label, style: TextStyle(
        color: _color, fontSize: 9, fontWeight: FontWeight.w700, letterSpacing: 0.3,
      )),
    );
  }
}

// ─── 信号强度标签 ────────────────────────────────
class _SignalBadge extends StatelessWidget {
  final String strength;
  const _SignalBadge({required this.strength});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final color = strength == 'strong' ? c.accentGold : c.primary;
    final label = strength == 'strong' ? 'ALPHA' : 'SIG';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
      decoration: BoxDecoration(
        gradient: LinearGradient(colors: [
          color, color.withValues(alpha: 0.8),
        ]),
        borderRadius: BorderRadius.circular(4),
        boxShadow: [BoxShadow(
          color: color.withValues(alpha: 0.3), blurRadius: 4,
        )],
      ),
      child: Text(label, style: const TextStyle(
        color: Colors.white, fontSize: 8, fontWeight: FontWeight.w800, letterSpacing: 0.5,
      )),
    );
  }
}

// ─── 热度框（替代涨跌框）─────────────────────────
class _HeatBox extends StatelessWidget {
  final double score;
  final bool isBullish;
  const _HeatBox({required this.score, required this.isBullish});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final gradient = isBullish ? c.successGradient : c.dangerGradient;
    final label = isBullish ? '+${score.toStringAsFixed(0)}' : '${score.toStringAsFixed(0)}';

    return Container(
      constraints: const BoxConstraints(minWidth: 56),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: BorderRadius.circular(6),
        boxShadow: [BoxShadow(
          color: (isBullish ? c.success : c.danger).withValues(alpha: 0.2),
          blurRadius: 4, offset: const Offset(0, 1),
        )],
      ),
      alignment: Alignment.center,
      child: Text(
        '$label 热度',
        style: const TextStyle(
          color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700,
          fontFeatures: [FontFeature.tabularFigures()],
        ),
      ),
    );
  }
}
