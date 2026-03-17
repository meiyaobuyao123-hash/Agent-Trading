import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../l10n/app_localizations.dart';
import '../models/smart_money_signal.dart';
import '../theme/app_colors.dart';
import '../utils/chain_utils.dart';
import '../utils/format_utils.dart';
import 'common/token_avatar.dart';
import 'common/rank_medal.dart';
import 'common/chain_badge.dart';

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
          decoration: BoxDecoration(
            border: Border(
              bottom: BorderSide(
                color: c.textTertiary.withValues(alpha: 0.08),
                width: 0.5,
              ),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── 第1行: 排名 + 头像 + Symbol + Chain + Signal + timeAgo ──
              Row(
                children: [
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
                  TokenAvatar(imageUrl: ChainUtils.tokenImageUrl(sig.imageUrl, sig.chain, sig.tokenAddress), symbol: sig.tokenSymbol, chain: sig.chain, size: 36),
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
                                    : (sig.tokenAddress.length >= 6
                                        ? sig.tokenAddress.substring(0, 6)
                                        : sig.tokenAddress),
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
                            ChainBadge(chain: sig.chain),
                            if (isStrong) ...[
                              const SizedBox(width: 4),
                              _SignalBadge(strength: sig.signalStrength),
                            ],
                          ],
                        ),
                        const SizedBox(height: 2),
                        // 市值 · 流动性
                        Text(
                          S.of(context).mcLiquidity(sig.marketCapShort, sig.liquidityShort),
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
                          FormatUtils.fmtPrice(sig.priceUsd),
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
                      S.of(context).walletsCount(sig.uniqueBuyers),
                      style: TextStyle(
                        fontSize: 11, color: c.success,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (sig.eliteBuyCount > 0) ...[
                      Text(
                        S.of(context).eliteCountLabel(sig.eliteBuyCount),
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
                      S.of(context).walletsCount(sig.uniqueSellers),
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
              S.of(context).buyVolume(signal.buyVolumeShort),
              style: TextStyle(
                fontSize: 10, color: c.success,
                fontWeight: FontWeight.w600,
              ),
            ),
            Text(
              S.of(context).sellVolume(signal.sellVolumeShort),
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
        S.of(context).netAmount(signal.netFlowShort),
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
