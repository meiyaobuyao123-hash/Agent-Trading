import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../../l10n/app_localizations.dart';

class DataScreen extends StatefulWidget {
  const DataScreen({super.key});
  @override
  State<DataScreen> createState() => _DataScreenState();
}

class _DataScreenState extends State<DataScreen> {
  Map<String, dynamic>? _data;
  bool _loading = true;
  int _chainTab = 0; // 0=全链, 1=SOL, 2=BSC, 3=ETH, 4=Base

  static const _apiBase = String.fromEnvironment('API_BASE_URL',
      defaultValue: 'http://43.156.207.26');
  static const _chainKeys = ['all', 'solana', 'bsc', 'ethereum', 'base'];
  static const _chainLabels = ['全链', 'SOL', 'BSC', 'ETH', 'Base'];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final resp = await http
          .get(Uri.parse('$_apiBase/api/data/pnl-distribution'))
          .timeout(const Duration(seconds: 10));
      if (resp.statusCode == 200) {
        setState(() {
          _data = jsonDecode(resp.body);
          _loading = false;
        });
      } else {
        setState(() => _loading = false);
      }
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _data == null
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.error_outline, size: 48, color: Colors.grey),
                        const SizedBox(height: 12),
                        const Text('数据加载失败', style: TextStyle(color: Colors.grey)),
                        const SizedBox(height: 12),
                        ElevatedButton(onPressed: _load, child: const Text('重试')),
                      ],
                    ),
                  )
                : RefreshIndicator(
                    onRefresh: _load,
                    child: ListView(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      children: [
                        // 标题
                        const Padding(
                          padding: EdgeInsets.only(top: 8, bottom: 16),
                          child: Text('数据',
                              style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: Color(0xFF1A1A2E))),
                        ),

                        // 链选择 Tab
                        _buildChainTabs(),
                        const SizedBox(height: 16),

                        // 盈亏分布卡片
                        _buildPnlCard(),
                      ],
                    ),
                  ),
      ),
    );
  }

  Widget _buildChainTabs() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: List.generate(_chainLabels.length, (i) {
          final active = _chainTab == i;
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: GestureDetector(
              onTap: () => setState(() => _chainTab = i),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                decoration: BoxDecoration(
                  color: active ? const Color(0xFF2563EB) : const Color(0xFFF3F4F6),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  _chainLabels[i],
                  style: TextStyle(
                    color: active ? Colors.white : const Color(0xFF6B7280),
                    fontWeight: active ? FontWeight.w600 : FontWeight.w400,
                    fontSize: 13,
                  ),
                ),
              ),
            ),
          );
        }),
      ),
    );
  }

  Widget _buildPnlCard() {
    Map<String, dynamic> cardData;
    String title;
    String subtitle;
    int totalAddr;
    double profitPct;
    double lossPct;
    List<dynamic> tiers;

    if (_chainTab == 0) {
      // 全链
      final all = _data!['all_chain'] as Map<String, dynamic>;
      title = all['title'] ?? '交易者盈亏';
      subtitle = '${all['source']} · ${_fmtNum(all['total_addresses'])} 地址 · ${all['update_interval']}';
      totalAddr = all['total_addresses'] ?? 0;
      profitPct = (all['profit_pct'] ?? 0).toDouble();
      lossPct = (all['loss_pct'] ?? 0).toDouble();
      tiers = all['tiers'] ?? [];
      cardData = all;
    } else {
      final chainKey = _chainKeys[_chainTab];
      final chain = (_data!['by_chain'] as Map<String, dynamic>)[chainKey] as Map<String, dynamic>? ?? {};
      title = '${chain['chain'] ?? chainKey} 交易者盈亏';
      subtitle = '${_fmtNum(chain['total_addresses'])} 地址';
      totalAddr = chain['total_addresses'] ?? 0;
      profitPct = (chain['profit_pct'] ?? 0).toDouble();
      lossPct = (chain['loss_pct'] ?? 0).toDouble();
      tiers = chain['tiers'] ?? [];
      cardData = chain;
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.06), blurRadius: 12, offset: const Offset(0, 2)),
        ],
        border: Border.all(color: const Color(0xFFE5E7EB), width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 头部
          Row(
            children: [
              Container(
                width: 36, height: 36,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(colors: [Color(0xFFFF6B6B), Color(0xFFFF8E53)]),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.trending_up, color: Colors.white, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF1A1A2E))),
                    Text(subtitle, style: const TextStyle(fontSize: 11, color: Color(0xFF9CA3AF))),
                  ],
                ),
              ),
              // 问号按钮
              GestureDetector(
                onTap: () => _showMethodology(cardData),
                child: Container(
                  width: 28, height: 28,
                  decoration: BoxDecoration(
                    color: const Color(0xFFF3F4F6),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: const Icon(Icons.help_outline, size: 16, color: Color(0xFF9CA3AF)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // 金字塔
          _buildPyramid(tiers, totalAddr),
          const SizedBox(height: 20),

          // 底部盈亏条
          _buildProfitLossBar(profitPct, lossPct),
        ],
      ),
    );
  }

  Widget _buildPyramid(List<dynamic> tiers, int totalAddr) {
    if (tiers.isEmpty) return const SizedBox.shrink();

    // 金字塔颜色（从顶到底）
    const pyramidColors = [
      Color(0xFFFF6B00),  // 橙色（顶层 >$1M）
      Color(0xFF9B59B6),  // 紫色
      Color(0xFF3498DB),  // 蓝色
      Color(0xFF5DADE2),  // 浅蓝
      Color(0xFFAED6F1),  // 更浅蓝
      Color(0xFFD1D5DB),  // 灰色（盈亏平衡）
      Color(0xFFE74C3C),  // 红色（亏损）
    ];

    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        // 左侧金字塔
        Expanded(
          flex: 4,
          child: Column(
            children: List.generate(tiers.length, (i) {
              final tier = tiers[i] as Map<String, dynamic>;
              final widthRatio = 0.3 + (i / (tiers.length - 1)) * 0.7; // 从 30% 到 100%
              final color = i < pyramidColors.length
                  ? pyramidColors[i]
                  : Color(int.parse((tier['color'] ?? '#999999').replaceFirst('#', '0xFF')));

              return Padding(
                padding: const EdgeInsets.only(bottom: 2),
                child: Align(
                  alignment: Alignment.center,
                  child: FractionallySizedBox(
                    widthFactor: widthRatio,
                    child: Container(
                      height: 28,
                      decoration: BoxDecoration(
                        color: color,
                        borderRadius: i == 0
                            ? const BorderRadius.vertical(top: Radius.circular(6))
                            : i == tiers.length - 1
                                ? const BorderRadius.vertical(bottom: Radius.circular(6))
                                : BorderRadius.zero,
                      ),
                    ),
                  ),
                ),
              );
            }),
          ),
        ),

        // 右侧标签
        Expanded(
          flex: 6,
          child: Column(
            children: List.generate(tiers.length, (i) {
              final tier = tiers[i] as Map<String, dynamic>;
              final label = tier['label'] ?? '';
              final count = tier['count'] ?? 0;
              final pct = (tier['pct'] ?? 0).toDouble();
              final color = i < pyramidColors.length ? pyramidColors[i] : Colors.grey;

              return Container(
                height: 30,
                padding: const EdgeInsets.only(left: 12),
                child: Row(
                  children: [
                    Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(label, style: const TextStyle(fontSize: 13, color: Color(0xFF374151))),
                    ),
                    Text(
                      _fmtNum(count),
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF1A1A2E)),
                    ),
                    const SizedBox(width: 8),
                    SizedBox(
                      width: 50,
                      child: Text(
                        '${pct < 0.01 ? "<0.01" : pct.toStringAsFixed(pct < 1 ? 2 : 1)}%',
                        textAlign: TextAlign.right,
                        style: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF)),
                      ),
                    ),
                  ],
                ),
              );
            }),
          ),
        ),
      ],
    );
  }

  Widget _buildProfitLossBar(double profitPct, double lossPct) {
    return Column(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: Row(
            children: [
              Expanded(
                flex: (profitPct * 10).toInt(),
                child: Container(height: 8, color: const Color(0xFF22C55E)),
              ),
              Expanded(
                flex: (lossPct * 10).toInt(),
                child: Container(height: 8, color: const Color(0xFFEF4444)),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              '${profitPct.toStringAsFixed(1)}% 盈利',
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF22C55E)),
            ),
            Text(
              '${lossPct.toStringAsFixed(1)}% 亏损',
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFFEF4444)),
            ),
          ],
        ),
      ],
    );
  }

  void _showMethodology(Map<String, dynamic> data) {
    final methodology = data['methodology'] ?? '数据来源：Dune Analytics 全链 DEX 交易数据';
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(width: 36, height: 4,
                  decoration: BoxDecoration(color: Colors.grey[300], borderRadius: BorderRadius.circular(2))),
            ),
            const SizedBox(height: 16),
            const Text('数据说明', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF1A1A2E))),
            const SizedBox(height: 12),
            Text(methodology.toString(), style: const TextStyle(fontSize: 14, color: Color(0xFF4B5563), height: 1.6)),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  String _fmtNum(dynamic n) {
    if (n == null) return '0';
    final v = n is int ? n.toDouble() : (n as num).toDouble();
    if (v >= 1e6) return '${(v / 1e6).toStringAsFixed(2)}M';
    if (v >= 1e3) return '${(v / 1e3).toStringAsFixed(1)}K';
    return v.toStringAsFixed(0);
  }
}
