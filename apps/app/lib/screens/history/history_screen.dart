import 'dart:async';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import '../../l10n/app_localizations.dart';
import '../../models/pump_signal.dart';
import '../../models/token_detail.dart';
import '../../services/pump_signal_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/common/token_avatar.dart';
import '../detail/token_detail_page.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<PumpSignal> _signals = [];
  bool _loading = true;
  String? _error;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => _load());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final result = await PumpSignalService.instance.fetchSignals();
      if (mounted) {
        setState(() {
          _signals = result.signals;
          _loading = false;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted && _signals.isEmpty) {
        setState(() { _error = e.toString(); _loading = false; });
      }
    }
  }

  TokenDetail _signalToDetail(PumpSignal s) {
    return TokenDetail(
      chain: 'solana', address: s.mint, name: s.name, symbol: s.symbol,
      priceUsd: 0, marketCapUsd: 0, liquidityUsd: 0,
      volume24hUsd: 0, volume1hUsd: 0,
      priceChange1h: 0, priceChange6h: 0, priceChange24h: 0,
      buys1h: 0, sells1h: 0, buys24h: 0, sells24h: 0,
      ageDays: s.ageMinutes / 1440, holderCount: 0,
      goplusRisk: false,
      hasTwitter: s.twitter != null, hasTelegram: s.telegram != null, hasWebsite: s.website != null,
      score: s.score, scoreDetail: s.scoreDetail, recommendation: s.recommendation,
      source: TokenSource.pumpSignal, bcProgress: s.bcProgress, imageUri: s.imageUri,
    );
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final strongCount = _signals.where((s) => s.isStrong).length;

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          SliverAppBar(
            expandedHeight: 100,
            pinned: true,
            backgroundColor: Colors.transparent,
            flexibleSpace: FlexibleSpaceBar(
              collapseMode: CollapseMode.pin,
              titlePadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              title: Text(
                S.of(context).realtimeSignals,
                style: TextStyle(
                  color: c.textPrimary,
                  fontSize: 20,
                  fontWeight: FontWeight.w600,
                  letterSpacing: -0.3,
                ),
              ),
            ),
          ),

          // 统计面板
          if (!_loading && _signals.isNotEmpty)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: c.cardGlass,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: c.glassBorder, width: 0.5),
                  ),
                  child: Row(
                    children: [
                      _StatItem(value: '${_signals.length}', label: S.of(context).realtimeSignals),
                      _Divider(),
                      _StatItem(value: '$strongCount', label: S.of(context).strongPush, color: c.success),
                      _Divider(),
                      _StatItem(
                        value: '${_signals.length - strongCount}',
                        label: S.of(context).watch,
                        color: c.primary,
                      ),
                    ],
                  ),
                ),
              ),
            ),

          CupertinoSliverRefreshControl(onRefresh: _load),

          if (_loading)
            SliverFillRemaining(
              child: Center(
                child: CircularProgressIndicator(color: c.primary, strokeWidth: 2),
              ),
            )
          else if (_error != null)
            SliverFillRemaining(
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.wifi_off_rounded, size: 48, color: c.danger),
                    const SizedBox(height: 16),
                    TextButton(
                      onPressed: _load,
                      child: Text(S.of(context).retry, style: TextStyle(color: c.primary)),
                    ),
                  ],
                ),
              ),
            )
          else if (_signals.isEmpty)
            SliverFillRemaining(
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(CupertinoIcons.waveform, size: 48, color: c.textTertiary),
                    const SizedBox(height: 14),
                    Text(S.of(context).noSignals,
                      style: TextStyle(color: c.textPrimary, fontSize: 17, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 8),
                    Text(S.of(context).whenTokenAppears,
                      style: TextStyle(color: c.textSecondary, fontSize: 15)),
                  ],
                ),
              ),
            )
          else ...[
            SliverToBoxAdapter(
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 16),
                decoration: BoxDecoration(
                  color: c.cardGlass,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: c.glassBorder, width: 0.5),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(16),
                  child: Column(
                    children: List.generate(_signals.length, (i) {
                      final signal = _signals[i];
                      return Column(children: [
                        _SignalRow(
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
                          Padding(
                            padding: const EdgeInsets.only(left: 80),
                            child: Container(height: 0.5, color: c.divider),
                          ),
                      ]);
                    }),
                  ),
                ),
              ),
            ),
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                child: Center(
                  child: Text(
                    S.of(context).scanInfo,
                    style: TextStyle(fontSize: 12, color: c.textTertiary),
                  ),
                ),
              ),
            ),
          ],

          const SliverToBoxAdapter(child: SizedBox(height: 32)),
        ],
      ),
    );
  }
}

class _StatItem extends StatelessWidget {
  final String value;
  final String label;
  final Color? color;
  const _StatItem({required this.value, required this.label, this.color});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final effectiveColor = color ?? c.textPrimary;

    return Expanded(
      child: Column(
        children: [
          Text(value,
            style: TextStyle(color: effectiveColor, fontSize: 18,
              fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          Text(label,
            style: TextStyle(color: c.textSecondary, fontSize: 11)),
        ],
      ),
    );
  }
}

class _Divider extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      width: 0.5, height: 36,
      color: c.divider,
      margin: const EdgeInsets.symmetric(horizontal: 4),
    );
  }
}

class _SignalRow extends StatelessWidget {
  final PumpSignal signal;
  final int rank;
  final VoidCallback? onTap;

  const _SignalRow({required this.signal, required this.rank, this.onTap});

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
            SizedBox(
              width: 24,
              child: Text(
                '$rank',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w600,
                  color: rank <= 3 ? c.primary : c.textSecondary,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ),
            const SizedBox(width: 8),
            TokenAvatar(imageUrl: signal.imageUri, symbol: signal.symbol, chain: 'solana', size: 38),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(children: [
                    Flexible(
                      child: Text(
                        signal.symbol.toUpperCase(),
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700,
                          color: c.textPrimary, letterSpacing: -0.3),
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
                        child: Text(S.of(context).strongPush,
                          style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.w800)),
                      ),
                    ],
                  ]),
                  const SizedBox(height: 5),
                  Row(children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                      decoration: BoxDecoration(
                        color: c.primary.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        'BC ${signal.bcProgress.toStringAsFixed(1)}%',
                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: c.primary),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(S.of(context).buyersCount(signal.uniqueBuyers),
                      style: TextStyle(fontSize: 11, color: c.textSecondary)),
                    const SizedBox(width: 6),
                    Text(signal.ageLabel,
                      style: TextStyle(fontSize: 11, color: c.textTertiary)),
                  ]),
                ],
              ),
            ),
            Container(
              constraints: const BoxConstraints(minWidth: 38),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              decoration: BoxDecoration(
                gradient: signal.score >= 75 ? c.successGradient : c.primaryGradient,
                borderRadius: BorderRadius.circular(6),
              ),
              alignment: Alignment.center,
              child: Text(
                signal.score.toStringAsFixed(0),
                style: const TextStyle(color: Colors.white, fontSize: 13,
                  fontWeight: FontWeight.w800, fontFeatures: [FontFeature.tabularFigures()]),
              ),
            ),
            const SizedBox(width: 4),
            Icon(CupertinoIcons.chevron_right, size: 12, color: c.textTertiary),
          ],
        ),
      ),
    );
  }
}
