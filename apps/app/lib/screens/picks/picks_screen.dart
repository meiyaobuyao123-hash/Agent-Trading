import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/daily_pick.dart';
import '../../services/supabase_service.dart';
import '../../theme/app_colors.dart';
import '../../models/token_detail.dart';
import '../../widgets/pick_card.dart';
import '../detail/token_detail_page.dart';

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
    final today = DateFormat('M月d日').format(DateTime.now());
    final strongCount = _picks.where((p) => p.recommendation == 'strong').length;

    return Scaffold(
      backgroundColor: AppColors.bg,
      body: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          // ── iOS 大标题 ──────────────────────
          CupertinoSliverNavigationBar(
            largeTitle: const Text('今日信号'),
            backgroundColor: AppColors.bg.withValues(alpha: 0.9),
            border: null,
            trailing: _picks.isNotEmpty
                ? Container(
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
                  )
                : null,
          ),

          // ── 日期副标题 ──────────────────────
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Text(
                today,
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 15,
                ),
              ),
            ),
          ),

          // ── 下拉刷新 ──────────────────────
          CupertinoSliverRefreshControl(onRefresh: _load),

          // ── 内容 ──────────────────────────
          if (_loading)
            const SliverFillRemaining(child: _LoadingView())
          else if (_error != null)
            SliverFillRemaining(child: _ErrorView(onRetry: _load))
          else if (_picks.isEmpty)
            const SliverFillRemaining(child: _EmptyView())
          else ...[
            // 分组卡片容器
            SliverToBoxAdapter(
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 16),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  children: List.generate(_picks.length, (i) {
                    final pick = _picks[i];
                    return Column(
                      children: [
                        PickCard(
                          pick: pick,
                          onTap: () => Navigator.push(
                            context,
                            CupertinoPageRoute(
                              builder: (_) => TokenDetailPage(
                                token: TokenDetail.fromDailyPick(pick),
                              ),
                            ),
                          ),
                        ),
                        if (i < _picks.length - 1)
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
            // 底部说明
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
                child: Text(
                  '每日 UTC 00:05 更新  ·  pump.fun 内盘扫描',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                  ),
                ),
              ),
            ),
          ],
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
          Icon(CupertinoIcons.search, size: 44, color: AppColors.textTertiary),
          const SizedBox(height: 12),
          const Text(
            '今日信号尚未生成',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 17,
              fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 6),
          const Text(
            '每日 UTC 00:05 自动生成',
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
