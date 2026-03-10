import 'dart:async';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../models/hot_coin.dart';
import '../../services/supabase_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/hot_coin_card.dart';

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
  DateTime? _lastUpdate;

  // 链过滤：null = 全部
  String? _chainFilter;
  static const _chains = ['全部', 'SOL', 'BSC', 'BASE'];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({bool silent = false}) async {
    if (!silent) setState(() { _loading = true; _error = null; });
    try {
      final coins = await SupabaseService.instance.fetchHotCoins(limit: 50);
      if (mounted) {
        setState(() {
          _coins      = coins;
          _lastUpdate = DateTime.now();
          _loading    = false;
          _applyFilter();
        });
      }
    } catch (e) {
      if (mounted && !silent) {
        setState(() { _error = e.toString(); _loading = false; });
      }
    }
  }

  void _applyFilter() {
    if (_chainFilter == null) {
      _filtered = List.from(_coins);
    } else {
      _filtered = _coins
          .where((c) => c.chainLabel == _chainFilter)
          .toList();
    }
  }

  void _setChain(String label) {
    setState(() {
      _chainFilter = (label == '全部') ? null : label;
      _applyFilter();
    });
  }

  /// 点击卡片 → 打开 DexScreener
  void _openDex(HotCoin coin) async {
    final chain = switch (coin.chain) {
      'solana' => 'solana',
      'bsc'    => 'bsc',
      'base'   => 'base',
      _        => coin.chain,
    };
    final addr = coin.pairAddress ?? coin.address;
    final url  = Uri.parse('https://dexscreener.com/$chain/$addr');
    if (await canLaunchUrl(url)) {
      await launchUrl(url, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: CustomScrollView(
        slivers: [
          // ── 顶部 AppBar ───────────────────────────────
          SliverAppBar(
            expandedHeight: 120,
            pinned: true,
            backgroundColor: AppColors.bg,
            flexibleSpace: FlexibleSpaceBar(
              collapseMode: CollapseMode.pin,
              titlePadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              title: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  const Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '热币榜',
                        style: TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 22,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.5,
                        ),
                      ),
                      Text(
                        '多链外盘 · SOL / BSC / Base',
                        style: TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 11,
                          fontWeight: FontWeight.w400,
                        ),
                      ),
                    ],
                  ),
                  // 刷新按钮
                  GestureDetector(
                    onTap: _load,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: AppColors.surfaceAlt,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.refresh_rounded,
                              size: 13, color: AppColors.textSecondary),
                          const SizedBox(width: 4),
                          Text(
                            _lastUpdate != null
                                ? _fmtTime(_lastUpdate!)
                                : '刷新',
                            style: const TextStyle(
                              color: AppColors.textSecondary,
                              fontSize: 11,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),

          // ── 链过滤 Tabs ───────────────────────────────
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: _chains.map((label) {
                    final active = (label == '全部')
                        ? _chainFilter == null
                        : _chainFilter == label;
                    return Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: _ChainTab(
                        label: label,
                        active: active,
                        onTap: () => _setChain(label),
                      ),
                    );
                  }).toList(),
                ),
              ),
            ),
          ),

          // ── 列头 ─────────────────────────────────────
          if (!_loading && _filtered.isNotEmpty)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 20, 2),
                child: Row(
                  children: [
                    const SizedBox(width: 34 + 12 + 40 + 10), // rank + chain badge
                    const Text('代币 / 市值 / 上线天',
                        style: TextStyle(color: AppColors.textTertiary, fontSize: 11)),
                    const Spacer(),
                    const Text('评分 / 24h涨幅',
                        style: TextStyle(color: AppColors.textTertiary, fontSize: 11)),
                  ],
                ),
              ),
            ),

          // ── 内容区 ────────────────────────────────────
          if (_loading)
            const SliverFillRemaining(child: _LoadingView())
          else if (_error != null)
            SliverFillRemaining(child: _ErrorView(error: _error!, onRetry: _load))
          else if (_filtered.isEmpty)
            const SliverFillRemaining(child: _EmptyView())
          else
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (ctx, i) {
                  if (i == _filtered.length) {
                    final strong  = _filtered.where((c) => c.recommendation == 'strong').length;
                    final normal  = _filtered.length - strong;
                    return Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(
                        '共 ${_filtered.length} 个  ·  强推 $strong  普通 $normal'
                        '  ·  每2小时更新',
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                            color: AppColors.textTertiary, fontSize: 11),
                      ),
                    );
                  }
                  final coin = _filtered[i];
                  return HotCoinCard(
                    coin: coin,
                    rank: i + 1,
                    onTap: () => _openDex(coin),
                  );
                },
                childCount: _filtered.length + 1,
              ),
            ),
        ],
      ),
    );
  }

  String _fmtTime(DateTime dt) {
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }
}

// ─── 链过滤 Tab ──────────────────────────────────────
class _ChainTab extends StatelessWidget {
  final String label;
  final bool active;
  final VoidCallback onTap;
  const _ChainTab({required this.label, required this.active, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
          color: active ? AppColors.primary : AppColors.surfaceAlt,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: active ? Colors.white : AppColors.textSecondary,
            fontSize: 12,
            fontWeight: active ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
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
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(color: AppColors.primary, strokeWidth: 2),
          SizedBox(height: 16),
          Text('加载热币数据...', style: TextStyle(color: AppColors.textSecondary)),
        ],
      ),
    );
  }
}

// ─── 空 ──────────────────────────────────────────────
class _EmptyView extends StatelessWidget {
  const _EmptyView();
  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('🔥', style: TextStyle(fontSize: 48)),
          SizedBox(height: 16),
          Text('暂无热门代币',
              style: TextStyle(color: AppColors.textPrimary, fontSize: 16,
                  fontWeight: FontWeight.w600)),
          SizedBox(height: 8),
          Text('热币榜每2小时更新一次\n首次扫描后自动出现',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textSecondary,
                  fontSize: 13, height: 1.5)),
        ],
      ),
    );
  }
}

// ─── 错误 ────────────────────────────────────────────
class _ErrorView extends StatelessWidget {
  final String error;
  final VoidCallback onRetry;
  const _ErrorView({required this.error, required this.onRetry});
  @override
  Widget build(BuildContext context) {
    return Center(
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
    );
  }
}
