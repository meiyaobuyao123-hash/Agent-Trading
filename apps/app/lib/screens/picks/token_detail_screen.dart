import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../models/daily_pick.dart';
import '../../theme/app_colors.dart';
import '../../widgets/score_ring.dart';

class TokenDetailScreen extends StatelessWidget {
  final DailyPick pick;
  const TokenDetailScreen({super.key, required this.pick});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        title: Text(
          pick.symbol.toUpperCase(),
          style: const TextStyle(
            color: AppColors.textPrimary,
            fontSize: 18,
            fontWeight: FontWeight.w700,
          ),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_rounded, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          // pump.fun 链接
          IconButton(
            icon: const Icon(Icons.open_in_new_rounded, color: AppColors.primary),
            onPressed: () => _openPumpFun(pick.mint),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── 头部卡片 ──────────────────────────
            _HeaderCard(pick: pick),
            const SizedBox(height: 16),

            // ── 打分明细 ──────────────────────────
            if (pick.scoreDetail.isNotEmpty) ...[
              const _SectionTitle(title: '打分明细'),
              const SizedBox(height: 10),
              _ScoreDetailCard(detail: pick.scoreDetail, total: pick.score),
              const SizedBox(height: 16),
            ],

            // ── 代币信息 ──────────────────────────
            const _SectionTitle(title: '代币信息'),
            const SizedBox(height: 10),
            _InfoCard(pick: pick),
            const SizedBox(height: 16),

            // ── 结果（如果有）─────────────────────
            if (pick.hasOutcome) ...[
              const _SectionTitle(title: '72h 追踪结果'),
              const SizedBox(height: 10),
              _OutcomeCard(pick: pick),
              const SizedBox(height: 16),
            ],

            // ── 社交链接 ──────────────────────────
            if (pick.twitter != null || pick.telegram != null || pick.website != null) ...[
              const _SectionTitle(title: '社交媒体'),
              const SizedBox(height: 10),
              _SocialCard(pick: pick),
              const SizedBox(height: 16),
            ],

            // ── Mint 地址 ─────────────────────────
            _MintCard(mint: pick.mint),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  void _openPumpFun(String mint) {
    launchUrl(
      Uri.parse('https://pump.fun/coin/$mint'),
      mode: LaunchMode.externalApplication,
    );
  }
}

// ─── 头部卡片 ────────────────────────────────────────
class _HeaderCard extends StatelessWidget {
  final DailyPick pick;
  const _HeaderCard({required this.pick});

  @override
  Widget build(BuildContext context) {
    final isStrong = pick.recommendation == 'strong';
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isStrong
              ? AppColors.strong.withValues(alpha: 0.4)
              : AppColors.divider,
          width: isStrong ? 1.5 : 0.5,
        ),
        boxShadow: AppColors.cardShadow,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: AppColors.primaryDim,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        '#${pick.rank}',
                        style: const TextStyle(
                          color: AppColors.primary, fontSize: 12,
                          fontWeight: FontWeight.w700),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: isStrong ? AppColors.strongLight : AppColors.normalLight,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        isStrong ? '强烈推荐' : '关注',
                        style: TextStyle(
                          color: isStrong ? AppColors.strong : AppColors.normal,
                          fontSize: 12, fontWeight: FontWeight.w600),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  pick.symbol.toUpperCase(),
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 28,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.5,
                  ),
                ),
                Text(
                  pick.name,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 16),
                // BC 进度条
                _BcProgressBar(progress: pick.bcProgress),
              ],
            ),
          ),
          const SizedBox(width: 20),
          ScoreRing(score: pick.score, size: 72, strokeWidth: 6),
        ],
      ),
    );
  }
}

class _BcProgressBar extends StatelessWidget {
  final double progress;
  const _BcProgressBar({required this.progress});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('内盘进度',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
            Text('${progress.toStringAsFixed(1)}%',
              style: const TextStyle(color: AppColors.primary, fontSize: 12,
                fontWeight: FontWeight.w600)),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: progress / 100,
            backgroundColor: AppColors.divider,
            color: AppColors.primary,
            minHeight: 6,
          ),
        ),
      ],
    );
  }
}

// ─── 打分明细 ────────────────────────────────────────
class _ScoreDetailCard extends StatelessWidget {
  final Map<String, dynamic> detail;
  final double total;
  const _ScoreDetailCard({required this.detail, required this.total});

  static const _labels = {
    'buy_sell_ratio':     '买卖比',
    'smart_money':        '聪明钱',
    'inflow_acceleration':'流入加速',
    'creator_history':    '创建者历史',
    'buyer_diversity':    '买家分散度',
    'social':             '社交完整度',
    'progress_speed':     '进度速度',
    'large_buy_bonus':    '大单加成',
  };

  static const _maxScores = {
    'buy_sell_ratio':     25.0,
    'smart_money':        20.0,
    'inflow_acceleration':15.0,
    'creator_history':    15.0,
    'buyer_diversity':    10.0,
    'social':             10.0,
    'progress_speed':     5.0,
    'large_buy_bonus':    5.0,
  };

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: <Widget>[
          ...detail.entries.map((e) {
            final label = _labels[e.key] ?? e.key;
            final score = (e.value as num?)?.toDouble() ?? 0.0;
            final max   = _maxScores[e.key] ?? 10.0;
            return _ScoreRow(label: label, score: score, max: max);
          }),
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('综合分',
                  style: TextStyle(color: AppColors.textPrimary,
                    fontSize: 14, fontWeight: FontWeight.w700)),
                Text('${total.toStringAsFixed(1)} / 100',
                  style: const TextStyle(color: AppColors.primary,
                    fontSize: 14, fontWeight: FontWeight.w700)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ScoreRow extends StatelessWidget {
  final String label;
  final double score;
  final double max;
  const _ScoreRow({required this.label, required this.score, required this.max});

  @override
  Widget build(BuildContext context) {
    final pct = max > 0 ? (score / max).clamp(0.0, 1.0) : 0.0;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          SizedBox(
            width: 80,
            child: Text(label,
              style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
          ),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(
                value: pct,
                backgroundColor: AppColors.divider,
                color: pct >= 0.7 ? AppColors.strong : AppColors.primary,
                minHeight: 5,
              ),
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 40,
            child: Text(score.toStringAsFixed(1),
              textAlign: TextAlign.right,
              style: const TextStyle(color: AppColors.textPrimary,
                fontSize: 12, fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}

// ─── 代币信息卡 ──────────────────────────────────────
class _InfoCard extends StatelessWidget {
  final DailyPick pick;
  const _InfoCard({required this.pick});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          _InfoRow(label: '市值', value: '${pick.marketCapSol.toStringAsFixed(2)} SOL'),
          const Divider(color: AppColors.divider, height: 16),
          _InfoRow(label: '内盘进度', value: '${pick.bcProgress.toStringAsFixed(2)}%'),
          const Divider(color: AppColors.divider, height: 16),
          _InfoRow(label: '日期', value: pick.pickDate),
          if (pick.creator != null) ...[
            const Divider(color: AppColors.divider, height: 16),
            _InfoRow(
              label: '创建者',
              value: '${pick.creator!.substring(0, 8)}…${pick.creator!.substring(pick.creator!.length - 4)}',
            ),
          ],
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label,
          style: const TextStyle(color: AppColors.textSecondary, fontSize: 13)),
        Text(value,
          style: const TextStyle(color: AppColors.textPrimary, fontSize: 13,
            fontWeight: FontWeight.w500)),
      ],
    );
  }
}

// ─── 结果卡 ──────────────────────────────────────────
class _OutcomeCard extends StatelessWidget {
  final DailyPick pick;
  const _OutcomeCard({required this.pick});

  @override
  Widget build(BuildContext context) {
    final success = (pick.label2x ?? false) || (pick.didGraduate ?? false);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: success ? AppColors.successLight : AppColors.dangerLight,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: success
              ? AppColors.success.withValues(alpha: 0.3)
              : AppColors.danger.withValues(alpha: 0.3),
        ),
      ),
      child: Row(
        children: [
          Icon(
            success ? Icons.check_circle_rounded : Icons.cancel_rounded,
            color: success ? AppColors.success : AppColors.danger,
            size: 32,
          ),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                pick.outcomeLabel,
                style: TextStyle(
                  color: success ? AppColors.success : AppColors.danger,
                  fontSize: 16, fontWeight: FontWeight.w700),
              ),
              if (pick.peakMultiplier != null)
                Text(
                  '峰值涨幅 ${pick.peakMultiplier!.toStringAsFixed(2)}x',
                  style: TextStyle(
                    color: (success ? AppColors.success : AppColors.danger)
                        .withValues(alpha: 0.7),
                    fontSize: 12),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

// ─── 社交卡 ──────────────────────────────────────────
class _SocialCard extends StatelessWidget {
  final DailyPick pick;
  const _SocialCard({required this.pick});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          if (pick.twitter != null)
            Expanded(child: _SocialBtn(
              label: 'Twitter',
              icon: Icons.alternate_email_rounded,
              color: const Color(0xFF1DA1F2),
              onTap: () => launchUrl(Uri.parse(pick.twitter!),
                mode: LaunchMode.externalApplication),
            )),
          if (pick.twitter != null && pick.telegram != null)
            const SizedBox(width: 8),
          if (pick.telegram != null)
            Expanded(child: _SocialBtn(
              label: 'Telegram',
              icon: Icons.send_rounded,
              color: const Color(0xFF2AABEE),
              onTap: () => launchUrl(Uri.parse(pick.telegram!),
                mode: LaunchMode.externalApplication),
            )),
          if (pick.website != null) ...[
            if (pick.twitter != null || pick.telegram != null) const SizedBox(width: 8),
            Expanded(child: _SocialBtn(
              label: 'Website',
              icon: Icons.language_rounded,
              color: AppColors.textSecondary,
              onTap: () => launchUrl(Uri.parse(pick.website!),
                mode: LaunchMode.externalApplication),
            )),
          ],
        ],
      ),
    );
  }
}

class _SocialBtn extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
  const _SocialBtn({required this.label, required this.icon,
    required this.color, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(height: 4),
            Text(label, style: TextStyle(color: color, fontSize: 11)),
          ],
        ),
      ),
    );
  }
}

// ─── Mint 地址卡 ─────────────────────────────────────
class _MintCard extends StatelessWidget {
  final String mint;
  const _MintCard({required this.mint});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surfaceAlt,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.fingerprint_rounded,
            color: AppColors.textTertiary, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              mint,
              style: const TextStyle(
                color: AppColors.textTertiary,
                fontSize: 11,
                fontFamily: 'monospace',
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          GestureDetector(
            onTap: () {
              // TODO: 复制到剪贴板
            },
            child: const Icon(Icons.copy_rounded,
              color: AppColors.textTertiary, size: 16),
          ),
        ],
      ),
    );
  }
}

// ─── Section 标题 ────────────────────────────────────
class _SectionTitle extends StatelessWidget {
  final String title;
  const _SectionTitle({required this.title});

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: const TextStyle(
        color: AppColors.textSecondary,
        fontSize: 12,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.5,
      ),
    );
  }
}
