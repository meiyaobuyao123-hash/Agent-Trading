import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import '../../models/hot_coin.dart';
import '../../models/token_detail.dart';
import '../../services/supabase_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/hot_coin_card.dart';
import '../detail/token_detail_page.dart';

class HotScreen extends StatefulWidget {
  const HotScreen({super.key});

  @override
  State<HotScreen> createState() => _HotScreenState();
}

class _HotScreenState extends State<HotScreen> {
  List<HotCoin> _coins = [];
  List<HotCoin> _filtered = [];
  bool _loading = true;
  String? _error;

  int _chainIndex = 0; // 0=全部, 1=SOL, 2=BSC, 3=BASE, 4=ETH
  static const _chainKeys = [null, 'SOL', 'BSC', 'BASE', 'ETH'];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final coins = await SupabaseService.instance.fetchHotCoins(limit: 50);
      if (mounted) {
        setState(() {
          _coins   = coins;
          _loading = false;
          _applyFilter();
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() { _error = e.toString(); _loading = false; });
      }
    }
  }

  void _applyFilter() {
    final key = _chainKeys[_chainIndex];
    if (key == null) {
      _filtered = List.from(_coins);
    } else {
      _filtered = _coins.where((c) => c.chainLabel == key).toList();
    }
  }

  void _openDetail(HotCoin coin) {
    Navigator.push(
      context,
      CupertinoPageRoute(
        builder: (_) => TokenDetailPage(
          token: TokenDetail.fromHotCoin(coin),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          // ── iOS 大标题导航栏 ──────────────────────
          CupertinoSliverNavigationBar(
            largeTitle: const Text('热币榜'),
            backgroundColor: AppColors.bg.withValues(alpha: 0.9),
            border: null,
            trailing: _coins.isNotEmpty
                ? Text(
                    '${_filtered.length} 个',
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 15,
                    ),
                  )
                : null,
          ),

          // ── 链过滤分段控件 ──────────────────────
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
              child: CupertinoSlidingSegmentedControl<int>(
                groupValue: _chainIndex,
                onValueChanged: (v) {
                  if (v == null) return;
                  setState(() {
                    _chainIndex = v;
                    _applyFilter();
                  });
                },
                children: const {
                  0: Padding(
                    padding: EdgeInsets.symmetric(horizontal: 4),
                    child: Text('全部', style: TextStyle(fontSize: 13)),
                  ),
                  1: Padding(
                    padding: EdgeInsets.symmetric(horizontal: 4),
                    child: Text('SOL', style: TextStyle(fontSize: 13)),
                  ),
                  2: Padding(
                    padding: EdgeInsets.symmetric(horizontal: 4),
                    child: Text('BSC', style: TextStyle(fontSize: 13)),
                  ),
                  3: Padding(
                    padding: EdgeInsets.symmetric(horizontal: 4),
                    child: Text('BASE', style: TextStyle(fontSize: 13)),
                  ),
                },
              ),
            ),
          ),

          // ── 下拉刷新包裹的内容区 ──────────────────
          CupertinoSliverRefreshControl(onRefresh: _load),

          // ── 内容区 ──────────────────────────────
          if (_loading)
            const SliverFillRemaining(child: _LoadingView())
          else if (_error != null)
            SliverFillRemaining(child: _ErrorView(onRetry: _load))
          else if (_filtered.isEmpty)
            const SliverFillRemaining(child: _EmptyView())
          else ...[
            // 分组卡片背景
            SliverToBoxAdapter(
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 16),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  children: List.generate(_filtered.length, (i) {
                    final coin = _filtered[i];
                    return Column(
                      children: [
                        HotCoinCard(
                          coin: coin,
                          rank: i + 1,
                          onTap: () => _openDetail(coin),
                        ),
                        if (i < _filtered.length - 1)
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
                  '${_filtered.where((c) => c.recommendation == "strong").length} 强推  '
                  '${_filtered.length - _filtered.where((c) => c.recommendation == "strong").length} 普通  ·  每 2 小时更新',
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

// ─── 加载 ────────────────────────────────────────────
class _LoadingView extends StatelessWidget {
  const _LoadingView();
  @override
  Widget build(BuildContext context) {
    return const Center(
      child: CupertinoActivityIndicator(radius: 14),
    );
  }
}

// ─── 空 ──────────────────────────────────────────────
class _EmptyView extends StatelessWidget {
  const _EmptyView();
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(CupertinoIcons.flame, size: 44, color: AppColors.textTertiary),
          const SizedBox(height: 12),
          const Text('暂无热门代币',
              style: TextStyle(color: AppColors.textPrimary, fontSize: 17,
                  fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          const Text('下拉刷新试试',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 15)),
        ],
      ),
    );
  }
}

// ─── 错误 ────────────────────────────────────────────
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
