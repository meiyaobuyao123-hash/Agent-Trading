import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/daily_pick.dart';
import '../../services/supabase_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/pick_card.dart';
import 'token_detail_screen.dart';

class PicksScreen extends StatefulWidget {
  const PicksScreen({super.key});

  @override
  State<PicksScreen> createState() => _PicksScreenState();
}

class _PicksScreenState extends State<PicksScreen> {
  List<DailyPick> _picks = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final picks = await SupabaseService.instance.fetchTodayPicks();
      if (mounted) setState(() { _picks = picks; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final today = DateFormat('MM月dd日').format(DateTime.now());
    final strongCount = _picks.where((p) => p.recommendation == 'strong').length;

    return Scaffold(
      backgroundColor: AppColors.bg,
      body: CustomScrollView(
        slivers: [
          // ── 顶部标题 ──────────────────────────
          SliverAppBar(
            expandedHeight: 110,
            pinned: true,
            backgroundColor: AppColors.bg,
            flexibleSpace: FlexibleSpaceBar(
              collapseMode: CollapseMode.pin,
              titlePadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              title: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '今日信号',
                        style: const TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 22,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.5,
                        ),
                      ),
                      Text(
                        today,
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 12,
                          fontWeight: FontWeight.w400,
                        ),
                      ),
                    ],
                  ),
                  if (!_loading && _picks.isNotEmpty)
                    _SummaryBadge(
                      total: _picks.length,
                      strong: strongCount,
                    ),
                ],
              ),
            ),
          ),

          // ── 内容 ──────────────────────────────
          if (_loading)
            const SliverFillRemaining(child: _LoadingView())
          else if (_error != null)
            SliverFillRemaining(child: _ErrorView(error: _error!, onRetry: _load))
          else if (_picks.isEmpty)
            const SliverFillRemaining(child: _EmptyView())
          else
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (ctx, i) {
                  if (i == _picks.length) {
                    return const Padding(
                      padding: EdgeInsets.all(20),
                      child: Text(
                        '每日 UTC 00:05 更新 · pump.fun 内盘扫描',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: AppColors.textTertiary,
                          fontSize: 11,
                        ),
                      ),
                    );
                  }
                  final pick = _picks[i];
                  return PickCard(
                    pick: pick,
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => TokenDetailScreen(pick: pick),
                      ),
                    ),
                  );
                },
                childCount: _picks.length + 1,
              ),
            ),
        ],
      ),
    );
  }
}

// ─── 汇总 Badge ──────────────────────────────────────
class _SummaryBadge extends StatelessWidget {
  final int total;
  final int strong;
  const _SummaryBadge({required this.total, required this.strong});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.strongLight,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.bolt_rounded, color: AppColors.strong, size: 14),
          const SizedBox(width: 3),
          Text(
            '$strong 强 / $total 个',
            style: const TextStyle(
              color: AppColors.strong,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

// ─── 加载中 ──────────────────────────────────────────
class _LoadingView extends StatelessWidget {
  const _LoadingView();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(color: AppColors.primary, strokeWidth: 2),
          SizedBox(height: 16),
          Text('正在拉取今日信号...', style: TextStyle(color: AppColors.textSecondary)),
        ],
      ),
    );
  }
}

// ─── 空状态 ──────────────────────────────────────────
class _EmptyView extends StatelessWidget {
  const _EmptyView();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.search_off_rounded, size: 56, color: AppColors.textTertiary),
          SizedBox(height: 16),
          Text(
            '今日信号尚未生成',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 16,
              fontWeight: FontWeight.w600),
          ),
          SizedBox(height: 8),
          Text(
            '每日 UTC 00:05 自动生成\n请明天再来',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.textSecondary, fontSize: 13, height: 1.5),
          ),
        ],
      ),
    );
  }
}

// ─── 错误状态 ────────────────────────────────────────
class _ErrorView extends StatelessWidget {
  final String error;
  final VoidCallback onRetry;
  const _ErrorView({required this.error, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.wifi_off_rounded, size: 48, color: AppColors.danger),
            const SizedBox(height: 16),
            const Text('加载失败',
              style: TextStyle(color: AppColors.textPrimary, fontSize: 16,
                fontWeight: FontWeight.w600)),
            const SizedBox(height: 20),
            TextButton(
              onPressed: onRetry,
              child: const Text('重试', style: TextStyle(color: AppColors.primary)),
            ),
          ],
        ),
      ),
    );
  }
}
