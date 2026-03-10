import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/daily_pick.dart';
import '../../services/supabase_service.dart';
import '../../theme/app_colors.dart';
import '../../models/token_detail.dart';
import '../../widgets/pick_card.dart';
import '../detail/token_detail_page.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  Map<String, List<DailyPick>> _history = {};
  bool _loading = true;
  String? _error;

  // 统计
  int _totalPicks = 0;
  int _graduatedCount = 0;
  int _twoXCount = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final history = await SupabaseService.instance.fetchHistoryPicks(days: 14);
      int total = 0, grad = 0, twox = 0;
      for (final picks in history.values) {
        for (final p in picks) {
          total++;
          if (p.hasOutcome) {
            if (p.didGraduate == true) grad++;
            if (p.label2x == true) twox++;
          }
        }
      }
      if (mounted) {
        setState(() {
          _history = history;
          _totalPicks = total;
          _graduatedCount = grad;
          _twoXCount = twox;
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            expandedHeight: 100,
            pinned: true,
            backgroundColor: AppColors.bg,
            flexibleSpace: const FlexibleSpaceBar(
              collapseMode: CollapseMode.pin,
              titlePadding: EdgeInsets.fromLTRB(16, 0, 16, 12),
              title: Text(
                '历史追踪',
                style: TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.5,
                ),
              ),
            ),
          ),

          if (_loading)
            const SliverFillRemaining(
              child: Center(
                child: CircularProgressIndicator(
                  color: AppColors.primary, strokeWidth: 2),
              ),
            )
          else if (_error != null)
            SliverFillRemaining(
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.wifi_off_rounded,
                      size: 48, color: AppColors.danger),
                    const SizedBox(height: 16),
                    TextButton(
                      onPressed: _load,
                      child: const Text('重试',
                        style: TextStyle(color: AppColors.primary)),
                    ),
                  ],
                ),
              ),
            )
          else if (_history.isEmpty)
            const SliverFillRemaining(
              child: Center(
                child: Text(
                  '暂无历史数据\n数据积累中...',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.textSecondary,
                    fontSize: 14, height: 1.6),
                ),
              ),
            )
          else ...[
            // ── 统计面板 ────────────────────────
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                child: _StatsPanel(
                  total: _totalPicks,
                  graduated: _graduatedCount,
                  twoX: _twoXCount,
                ),
              ),
            ),

            // ── 按天分组 ────────────────────────
            for (final entry in _history.entries) ...[
              SliverToBoxAdapter(
                child: _DateHeader(date: entry.key, picks: entry.value),
              ),
              SliverList(
                delegate: SliverChildBuilderDelegate(
                  (ctx, i) => PickCard(
                    pick: entry.value[i],
                    onTap: () => Navigator.push(
                      context,
                      CupertinoPageRoute(
                        builder: (_) => TokenDetailPage(
                          token: TokenDetail.fromDailyPick(entry.value[i]),
                        ),
                      ),
                    ),
                  ),
                  childCount: entry.value.length,
                ),
              ),
            ],

            const SliverToBoxAdapter(child: SizedBox(height: 32)),
          ],
        ],
      ),
    );
  }
}

// ─── 统计面板 ────────────────────────────────────────
class _StatsPanel extends StatelessWidget {
  final int total;
  final int graduated;
  final int twoX;
  const _StatsPanel({required this.total, required this.graduated, required this.twoX});

  @override
  Widget build(BuildContext context) {
    final gradRate = total > 0
        ? '${(graduated / total * 100).toStringAsFixed(0)}%'
        : '-';
    final twoXRate = total > 0
        ? '${(twoX / total * 100).toStringAsFixed(0)}%'
        : '-';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          _StatItem(value: '$total', label: '历史推送'),
          _Divider(),
          _StatItem(value: '$graduated', label: '已毕业', color: AppColors.success),
          _Divider(),
          _StatItem(value: gradRate, label: '毕业率', color: AppColors.success),
          _Divider(),
          _StatItem(value: twoXRate, label: '2x率', color: AppColors.primary),
        ],
      ),
    );
  }
}

class _StatItem extends StatelessWidget {
  final String value;
  final String label;
  final Color color;
  const _StatItem({required this.value, required this.label,
    this.color = AppColors.textPrimary});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Text(value,
            style: TextStyle(color: color, fontSize: 20,
              fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text(label,
            style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
        ],
      ),
    );
  }
}

class _Divider extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 0.5, height: 36,
      color: AppColors.divider,
      margin: const EdgeInsets.symmetric(horizontal: 4),
    );
  }
}

// ─── 日期组头 ────────────────────────────────────────
class _DateHeader extends StatelessWidget {
  final String date;
  final List<DailyPick> picks;
  const _DateHeader({required this.date, required this.picks});

  @override
  Widget build(BuildContext context) {
    // 计算这天的命中率
    final labeled = picks.where((p) => p.hasOutcome).toList();
    final hits    = labeled.where((p) => p.didGraduate == true || p.label2x == true).length;

    String hitStr = '';
    if (labeled.isNotEmpty) {
      hitStr = '  ·  命中 $hits/${labeled.length}';
    }

    // 日期格式化
    String displayDate = date;
    try {
      final dt = DateTime.parse(date);
      displayDate = DateFormat('MM/dd').format(dt);
    } catch (_) {}

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 6),
      child: Row(
        children: [
          Text(
            displayDate,
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontSize: 15,
              fontWeight: FontWeight.w700,
            ),
          ),
          Text(
            hitStr,
            style: const TextStyle(color: AppColors.textTertiary, fontSize: 12),
          ),
        ],
      ),
    );
  }
}
