import 'dart:async';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import '../../models/pump_signal.dart';
import '../../models/token_detail.dart';
import '../../services/pump_signal_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/common/token_avatar.dart';
import '../detail/token_detail_page.dart';

class PicksScreen extends StatefulWidget {
  const PicksScreen({super.key});

  @override
  State<PicksScreen> createState() => _PicksScreenState();
}

class _PicksScreenState extends State<PicksScreen> {
  List<PumpSignal> _signals = [];
  bool _loading = true;
  String? _error;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load();
    // 30s 自动轮询
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => _load());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    if (_loading && _signals.isNotEmpty) return; // 避免重复loading
    try {
      final signals = await PumpSignalService.instance.fetchSignals();
      if (mounted) setState(() { _signals = signals; _loading = false; _error = null; });
    } catch (e) {
      if (mounted && _signals.isEmpty) {
        setState(() { _error = e.toString(); _loading = false; });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final strongCount = _signals.where((s) => s.isStrong).length;

    return Scaffold(
      backgroundColor: AppColors.bg,
      body: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          CupertinoSliverNavigationBar(
            largeTitle: const Text('实时信号'),
            backgroundColor: AppColors.bg.withValues(alpha: 0.9),
            border: null,
            trailing: _signals.isNotEmpty
                ? Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (strongCount > 0)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: AppColors.strong.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            '$strongCount 强推',
                            style: const TextStyle(
                              color: AppColors.strong,
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppColors.textTertiary.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          '${_signals.length}',
                          style: TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  )
                : null,
          ),

          // 副标题
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Text(
                '实时扫描 pump.fun · 30s刷新',
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 13,
                ),
              ),
            ),
          ),

          CupertinoSliverRefreshControl(onRefresh: _load),

          if (_loading && _signals.isEmpty)
            const SliverFillRemaining(child: _LoadingView())
          else if (_error != null && _signals.isEmpty)
            SliverFillRemaining(child: _ErrorView(onRetry: _load))
          else if (_signals.isEmpty)
            const SliverFillRemaining(child: _EmptyView())
          else ...[
            SliverToBoxAdapter(
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 16),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  children: List.generate(_signals.length, (i) {
                    final signal = _signals[i];
                    return Column(
                      children: [
                        _SignalCard(
                          signal: signal,
                          rank: i + 1,
                          onTap: () => Navigator.push(
                            context,
                            CupertinoPageRoute(
                              builder: (_) => TokenDetailPage(
                                token: _signalToDetail(signal),
                              ),
                            ),
                          ),
                        ),
                        if (i < _signals.length - 1)
                          const Padding(
                            padding: EdgeInsets.only(left: 64),
                            child: Divider(height: 0.5, thickness: 0.5, color: Color(0xFFE5E5EA)),
                          ),
                      ],
                    );
                  }),
                ),
              ),
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 32)),
          ],
        ],
      ),
    );
  }

  TokenDetail _signalToDetail(PumpSignal s) {
    return TokenDetail(
      chain: 'solana',
      address: s.mint,
      name: s.name,
      symbol: s.symbol,
      priceUsd: 0,
      marketCapUsd: 0,
      liquidityUsd: 0,
      volume24hUsd: 0,
      volume1hUsd: 0,
      priceChange1h: 0,
      priceChange6h: 0,
      priceChange24h: 0,
      buys1h: 0,
      sells1h: 0,
      buys24h: 0,
      sells24h: 0,
      ageDays: s.ageMinutes / 1440,
      holderCount: 0,
      goplusRisk: false,
      hasTwitter: s.twitter != null,
      hasTelegram: s.telegram != null,
      hasWebsite: s.website != null,
      score: s.score,
      scoreDetail: s.scoreDetail,
      recommendation: s.recommendation,
      source: TokenSource.pumpSignal,
      bcProgress: s.bcProgress,
      imageUri: s.imageUri,
    );
  }
}

// ─── 信号卡片 ──────────────────────────────────────
class _SignalCard extends StatelessWidget {
  final PumpSignal signal;
  final int rank;
  final VoidCallback? onTap;

  const _SignalCard({required this.signal, required this.rank, this.onTap});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;

    return CupertinoButton(
      padding: EdgeInsets.zero,
      onPressed: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
        child: Row(
          children: [
            // 排名
            SizedBox(
              width: 24,
              child: Text(
                '$rank',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: rank <= 3 ? c.primary : c.textSecondary,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ),
            const SizedBox(width: 8),

            // 头像
            TokenAvatar(imageUrl: signal.imageUri, symbol: signal.symbol, chain: 'solana', size: 38),
            const SizedBox(width: 10),

            // 中间列
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          signal.symbol.toUpperCase(),
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: c.textPrimary,
                            letterSpacing: -0.3,
                          ),
                        ),
                      ),
                      if (signal.isStrong) ...[
                        const SizedBox(width: 5),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                          decoration: BoxDecoration(
                            gradient: c.successGradient,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text(
                            '强推',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 9,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 5),
                  Row(
                    children: [
                      // BC 进度
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                        decoration: BoxDecoration(
                          color: c.primary.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          'BC ${signal.bcProgress.toStringAsFixed(1)}%',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: c.primary,
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      // 买家数
                      Text(
                        '${signal.uniqueBuyers}人',
                        style: TextStyle(fontSize: 11, color: c.textSecondary),
                      ),
                      const SizedBox(width: 6),
                      // 存活时间
                      Text(
                        signal.ageLabel,
                        style: TextStyle(fontSize: 11, color: c.textTertiary),
                      ),
                    ],
                  ),
                ],
              ),
            ),

            // 评分框
            _ScoreBox(score: signal.score),
            const SizedBox(width: 4),
            Icon(CupertinoIcons.chevron_right, size: 12, color: c.textTertiary),
          ],
        ),
      ),
    );
  }
}

// ─── 评分框 ──────────────────────────────────────────
class _ScoreBox extends StatelessWidget {
  final double score;
  const _ScoreBox({required this.score});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final gradient = score >= 75
        ? c.successGradient
        : score >= 55
            ? c.primaryGradient
            : LinearGradient(colors: [c.textSecondary, c.textTertiary]);

    return Container(
      constraints: const BoxConstraints(minWidth: 38),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: BorderRadius.circular(6),
      ),
      alignment: Alignment.center,
      child: Text(
        score.toStringAsFixed(0),
        style: const TextStyle(
          color: Colors.white,
          fontSize: 13,
          fontWeight: FontWeight.w800,
          fontFeatures: [FontFeature.tabularFigures()],
        ),
      ),
    );
  }
}

// ─── 加载中 ──────────────────────────────────────────
class _LoadingView extends StatelessWidget {
  const _LoadingView();
  @override
  Widget build(BuildContext context) {
    return const Center(child: CupertinoActivityIndicator(radius: 14));
  }
}

// ─── 空状态 ──────────────────────────────────────────
class _EmptyView extends StatelessWidget {
  const _EmptyView();
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(CupertinoIcons.waveform, size: 44, color: AppColors.textTertiary),
          const SizedBox(height: 12),
          const Text(
            '暂无实时信号',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 17,
              fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 6),
          const Text(
            '当有符合条件的代币时会自动出现',
            style: TextStyle(color: AppColors.textSecondary, fontSize: 15),
          ),
        ],
      ),
    );
  }
}

// ─── 错误状态 ────────────────────────────────────────
class _ErrorView extends StatelessWidget {
  final VoidCallback onRetry;
  const _ErrorView({required this.onRetry});
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(CupertinoIcons.wifi_slash, size: 44, color: AppColors.textTertiary),
          const SizedBox(height: 12),
          const Text('加载失败',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 17,
              fontWeight: FontWeight.w600)),
          const SizedBox(height: 16),
          CupertinoButton(
            onPressed: onRetry,
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }
}
