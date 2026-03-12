import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/smart_money_signal.dart';
import '../theme/app_colors.dart';

/// 聪明钱信号卡片（重设计版）
/// 4行布局: 代币信息 | 市值·流动性 | 流量条 | 钱包数·净流·涨跌
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
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── 第1行: 排名 + 头像 + Symbol + Chain + Signal + timeAgo ──
              Row(
                children: [
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
                  _SignalAvatar(signal: sig, size: 36),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
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
                        const SizedBox(height: 2),
                        // 市值 · 流动性
                        Text(
                          'MC ${sig.marketCapShort} · 流动性 ${sig.liquidityShort}',
                          style: TextStyle(
                            fontSize: 11,
                            color: c.textTertiary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  // timeAgo + 价格
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      if (sig.priceUsd > 0)
                        Text(
                          _fmtPrice(sig.priceUsd),
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: c.textPrimary,
                            letterSpacing: -0.5,
                            fontFeatures: const [FontFeature.tabularFigures()],
                          ),
                        ),
                      const SizedBox(height: 2),
                      Text(
                        sig.timeAgo,
                        style: TextStyle(fontSize: 11, color: c.textTertiary),
                      ),
                    ],
                  ),
                ],
              ),

              const SizedBox(height: 8),

              // ── 第2行: 流量条 ──
              Padding(
                padding: const EdgeInsets.only(left: 32),
                child: _FlowBar(signal: sig),
              ),

              const SizedBox(height: 6),

              // ── 第3行: 钱包数 + 净流 + 涨跌 ──
              Padding(
                padding: const EdgeInsets.only(left: 32),
                child: Row(
                  children: [
                    // 买入钱包
                    Icon(Icons.arrow_upward_rounded, size: 10, color: c.success),
                    const SizedBox(width: 2),
                    Text(
                      '${sig.uniqueBuyers}钱包',
                      style: TextStyle(
                        fontSize: 11, color: c.success,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (sig.eliteBuyCount > 0) ...[
                      Text(
                        '(${sig.eliteBuyCount}精英)',
                        style: TextStyle(
                          fontSize: 9, color: c.accentGold,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                    const SizedBox(width: 6),
                    // 卖出钱包
                    Icon(Icons.arrow_downward_rounded, size: 10, color: c.danger),
                    const SizedBox(width: 2),
                    Text(
                      '${sig.uniqueSellers}钱包',
                      style: TextStyle(
                        fontSize: 11, color: c.danger,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const Spacer(),
                    // 净流入
                    _NetFlowChip(signal: sig),
                    const SizedBox(width: 6),
                    // 涨跌幅
                    if (sig.priceChange24h != 0)
                      _ChangeChip(change: sig.priceChange24h),
                  ],
                ),
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

// ─── 流量条: 绿(买入)/红(卖出) 比例可视化 ──────────────
class _FlowBar extends StatelessWidget {
  final SmartMoneySignal signal;
  const _FlowBar({required this.signal});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final ratio = signal.buyVolumeRatio;
    final buyFlex = (ratio * 100).round().clamp(5, 95);
    final sellFlex = 100 - buyFlex;

    return Column(
      children: [
        // 流量条
        ClipRRect(
          borderRadius: BorderRadius.circular(3),
          child: SizedBox(
            height: 6,
            child: Row(
              children: [
                Expanded(
                  flex: buyFlex,
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [c.success, c.success.withValues(alpha: 0.7)],
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 1),
                Expanded(
                  flex: sellFlex,
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [c.danger.withValues(alpha: 0.7), c.danger],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 3),
        // 金额标注
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              '买 ${signal.buyVolumeShort}',
              style: TextStyle(
                fontSize: 10, color: c.success,
                fontWeight: FontWeight.w600,
              ),
            ),
            Text(
              '卖 ${signal.sellVolumeShort}',
              style: TextStyle(
                fontSize: 10, color: c.danger,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

// ─── 净流入胶囊 ─────────────────────────────────
class _NetFlowChip extends StatelessWidget {
  final SmartMoneySignal signal;
  const _NetFlowChip({required this.signal});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final isPos = signal.netFlowUsd >= 0;
    final color = isPos ? c.success : c.danger;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        '净${signal.netFlowShort}',
        style: TextStyle(
          fontSize: 10, fontWeight: FontWeight.w700,
          color: color,
        ),
      ),
    );
  }
}

// ─── 涨跌幅胶囊 ─────────────────────────────────
class _ChangeChip extends StatelessWidget {
  final double change;
  const _ChangeChip({required this.change});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final isPos = change >= 0;
    final color = isPos ? c.success : c.danger;
    final text = isPos
        ? '+${change.toStringAsFixed(1)}%'
        : '${change.toStringAsFixed(1)}%';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
      decoration: BoxDecoration(
        gradient: isPos ? c.successGradient : c.dangerGradient,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 10, fontWeight: FontWeight.w700,
          color: Colors.white,
          fontFeatures: [FontFeature.tabularFigures()],
        ),
      ),
    );
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
