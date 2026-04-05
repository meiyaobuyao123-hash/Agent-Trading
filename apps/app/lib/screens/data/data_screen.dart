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
  Map<String, dynamic>? _tradingData;
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
      final results = await Future.wait([
        http.get(Uri.parse('$_apiBase/api/data/pnl-distribution')).timeout(const Duration(seconds: 10)),
        http.get(Uri.parse('$_apiBase/api/data/trading-distribution')).timeout(const Duration(seconds: 10)),
      ]);
      setState(() {
        if (results[0].statusCode == 200) _data = jsonDecode(results[0].body);
        if (results[1].statusCode == 200) _tradingData = jsonDecode(results[1].body);
        _loading = false;
      });
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
                        const SizedBox(height: 16),

                        // 交易成本拆解卡片
                        _buildCostCard(),
                        const SizedBox(height: 16),

                        // 交易行为分布
                        if (_tradingData != null) ...[
                          _buildDistributionCard(
                            _tradingData!['by_time_utc'] as Map<String, dynamic>? ?? {},
                            Icons.access_time,
                            const [Color(0xFF6366F1), Color(0xFF818CF8)],
                          ),
                          const SizedBox(height: 16),
                          _buildDistributionCard(
                            _tradingData!['by_token_age'] as Map<String, dynamic>? ?? {},
                            Icons.timer,
                            const [Color(0xFF059669), Color(0xFF34D399)],
                          ),
                          const SizedBox(height: 16),
                          _buildDistributionCard(
                            _tradingData!['by_amount'] as Map<String, dynamic>? ?? {},
                            Icons.attach_money,
                            const [Color(0xFFD97706), Color(0xFFFBBF24)],
                          ),
                        ],
                        const SizedBox(height: 32),
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

    const pyramidColors = [
      Color(0xFFFF6B00),
      Color(0xFF9B59B6),
      Color(0xFF3498DB),
      Color(0xFF5DADE2),
      Color(0xFFAED6F1),
      Color(0xFFD1D5DB),
      Color(0xFFE74C3C),
    ];

    final n = tiers.length;
    final pyramidHeight = n * 32.0;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 左侧金字塔（CustomPainter 画梯形，侧边一条斜线）
        SizedBox(
          width: 140,
          height: pyramidHeight,
          child: CustomPaint(
            painter: _PyramidPainter(
              count: n,
              colors: List.generate(n, (i) => i < pyramidColors.length ? pyramidColors[i] : Colors.grey),
            ),
          ),
        ),

        const SizedBox(width: 12),

        // 右侧标签
        Expanded(
          child: Column(
            children: List.generate(n, (i) {
              final tier = tiers[i] as Map<String, dynamic>;
              final label = tier['label'] ?? '';
              final count = tier['count'] ?? 0;
              final pct = (tier['pct'] ?? 0).toDouble();
              final color = i < pyramidColors.length ? pyramidColors[i] : Colors.grey;

              return SizedBox(
                height: 32,
                child: Row(
                  children: [
                    Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(label, style: const TextStyle(fontSize: 12, color: Color(0xFF374151))),
                    ),
                    Text(
                      _fmtNum(count),
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF1A1A2E)),
                    ),
                    const SizedBox(width: 6),
                    SizedBox(
                      width: 48,
                      child: Text(
                        pct < 0.01 ? '<0.01%' : '${pct.toStringAsFixed(pct < 1 ? 2 : 1)}%',
                        textAlign: TextAlign.right,
                        style: const TextStyle(fontSize: 11, color: Color(0xFF9CA3AF)),
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

  Widget _buildCostCard() {
    const costs = [
      {"label": "Axiom", "value": 200, "color": Color(0xFF3B82F6)},
      {"label": "Photon", "value": 96, "color": Color(0xFF8B5CF6)},
      {"label": "GMGN", "value": 85, "color": Color(0xFF22C55E)},
      {"label": "BullX", "value": 50, "color": Color(0xFFF97316)},
      {"label": "Trojan", "value": 40, "color": Color(0xFF6366F1)},
    ];
    const totalFee = 471; // $471M
    const mevSlippage = 500; // $500M
    const totalLoss = 971; // $971M

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
                  gradient: const LinearGradient(colors: [Color(0xFFEF4444), Color(0xFFF97316)]),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.account_balance_wallet, color: Colors.white, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('用户真实交易成本', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF1A1A2E))),
                    const Text('Top 5 平台 · DeFiLlama · 2025年数据', style: TextStyle(fontSize: 11, color: Color(0xFF9CA3AF))),
                  ],
                ),
              ),
              GestureDetector(
                onTap: () => _showMethodology({
                  "methodology": "用户亏损 ≈ 平台手续费收入 + MEV/滑点损失 + 代币归零损失。"
                      "平台收入来自 DeFiLlama 公开数据，MEV/滑点按交易量 2.5% 保守估算（\$20B × 2.5% = \$500M）。"
                      "代币归零：pump.fun 97% 代币归零，全链估计 80%+，此部分未计入。"
                      "实际用户总亏损远大于此数字。"
                }),
                child: Container(
                  width: 28, height: 28,
                  decoration: BoxDecoration(color: const Color(0xFFF3F4F6), borderRadius: BorderRadius.circular(14)),
                  child: const Icon(Icons.help_outline, size: 16, color: Color(0xFF9CA3AF)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // 平台手续费条形图
          const Text('平台手续费收入（= 用户直接损失）', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF374151))),
          const SizedBox(height: 12),
          ...costs.map((c) {
            final val = c["value"] as int;
            final color = c["color"] as Color;
            final ratio = val / 200; // 最大值 200
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  SizedBox(
                    width: 52,
                    child: Text(c["label"] as String, style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
                  ),
                  Expanded(
                    child: Stack(
                      children: [
                        Container(
                          height: 22,
                          decoration: BoxDecoration(
                            color: const Color(0xFFF3F4F6),
                            borderRadius: BorderRadius.circular(4),
                          ),
                        ),
                        FractionallySizedBox(
                          widthFactor: ratio.clamp(0.05, 1.0),
                          child: Container(
                            height: 22,
                            decoration: BoxDecoration(
                              color: color,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            alignment: Alignment.centerRight,
                            padding: const EdgeInsets.only(right: 6),
                            child: Text(
                              '\$${val}M',
                              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Colors.white),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            );
          }).toList(),
          const SizedBox(height: 16),

          // 汇总
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: const Color(0xFFFEF2F2),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFFFECACA)),
            ),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: const [
                    Text('Top 5 手续费合计', style: TextStyle(fontSize: 13, color: Color(0xFF991B1B))),
                    Text('\$471M', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFFEF4444))),
                  ],
                ),
                const SizedBox(height: 6),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: const [
                    Text('MEV + 滑点损失（估）', style: TextStyle(fontSize: 13, color: Color(0xFF991B1B))),
                    Text('\$500M', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFFEF4444))),
                  ],
                ),
                const Divider(height: 16, color: Color(0xFFFECACA)),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: const [
                    Text('用户确定性损失合计', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF991B1B))),
                    Text('\$971M', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Color(0xFFDC2626))),
                  ],
                ),
                const SizedBox(height: 6),
                const Text(
                  '* 不含代币归零损失（pump.fun 97% 代币归零），实际亏损远大于此',
                  style: TextStyle(fontSize: 10, color: Color(0xFFB91C1C)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDistributionCard(Map<String, dynamic> section, IconData icon, List<Color> gradientColors) {
    final title = section['title'] ?? '';
    final items = (section['data'] as List<dynamic>?) ?? [];
    if (items.isEmpty) return const SizedBox.shrink();

    final maxPct = items.fold<double>(0, (m, e) => m > ((e['pct'] ?? 0) as num).toDouble() ? m : ((e['pct'] ?? 0) as num).toDouble());

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.06), blurRadius: 12, offset: const Offset(0, 2))],
        border: Border.all(color: const Color(0xFFE5E7EB), width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 32, height: 32,
                decoration: BoxDecoration(
                  gradient: LinearGradient(colors: gradientColors),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: Colors.white, size: 18),
              ),
              const SizedBox(width: 10),
              Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF1A1A2E))),
            ],
          ),
          const SizedBox(height: 16),
          ...items.map((item) {
            final label = item['label'] ?? '';
            final pct = ((item['pct'] ?? 0) as num).toDouble();
            final tag = item['tag'] ?? '';
            final isHighlight = item['highlight'] == true;
            final ratio = maxPct > 0 ? pct / maxPct : 0.0;

            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                children: [
                  SizedBox(
                    width: 65,
                    child: Text(label, style: TextStyle(fontSize: 12, color: isHighlight ? gradientColors[0] : const Color(0xFF6B7280), fontWeight: isHighlight ? FontWeight.w600 : FontWeight.w400)),
                  ),
                  Expanded(
                    child: Stack(
                      children: [
                        Container(height: 20, decoration: BoxDecoration(color: const Color(0xFFF3F4F6), borderRadius: BorderRadius.circular(4))),
                        FractionallySizedBox(
                          widthFactor: ratio.clamp(0.03, 1.0),
                          child: Container(
                            height: 20,
                            decoration: BoxDecoration(
                              gradient: LinearGradient(colors: isHighlight ? gradientColors : [gradientColors[0].withOpacity(0.7), gradientColors[1].withOpacity(0.7)]),
                              borderRadius: BorderRadius.circular(4),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  SizedBox(
                    width: 35,
                    child: Text('${pct.toStringAsFixed(0)}%', textAlign: TextAlign.right, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: isHighlight ? gradientColors[0] : const Color(0xFF374151))),
                  ),
                  if (tag.isNotEmpty) ...[
                    const SizedBox(width: 6),
                    Text(tag, style: TextStyle(fontSize: 10, color: isHighlight ? gradientColors[0] : const Color(0xFF9CA3AF))),
                  ],
                ],
              ),
            );
          }).toList(),
        ],
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

/// 金字塔画家 — 侧边是一条平滑斜线的梯形
class _PyramidPainter extends CustomPainter {
  final int count;
  final List<Color> colors;

  _PyramidPainter({required this.count, required this.colors});

  @override
  void paint(Canvas canvas, Size size) {
    if (count == 0) return;

    final w = size.width;
    final h = size.height;
    final rowH = h / count;
    final gap = 1.5; // 行间距

    // 顶部最窄宽度 30%，底部 100%
    const topRatio = 0.25;

    for (int i = 0; i < count; i++) {
      final t1 = i / count;
      final t2 = (i + 1) / count;

      // 该行顶边和底边的半宽
      final halfTop = (topRatio + (1 - topRatio) * t1) * w / 2;
      final halfBot = (topRatio + (1 - topRatio) * t2) * w / 2;

      final cx = w / 2;
      final y1 = i * rowH + (i > 0 ? gap / 2 : 0);
      final y2 = (i + 1) * rowH - (i < count - 1 ? gap / 2 : 0);

      final path = Path()
        ..moveTo(cx - halfTop, y1)
        ..lineTo(cx + halfTop, y1)
        ..lineTo(cx + halfBot, y2)
        ..lineTo(cx - halfBot, y2)
        ..close();

      final paint = Paint()
        ..color = i < colors.length ? colors[i] : Colors.grey
        ..style = PaintingStyle.fill;

      canvas.drawPath(path, paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
