import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';
import 'package:http/http.dart' as http;

class DataScreen extends StatefulWidget {
  const DataScreen({super.key});
  @override
  State<DataScreen> createState() => _DataScreenState();
}

class _DataScreenState extends State<DataScreen> {
  Map<String, dynamic>? _data;
  bool _loading = true;
  int _chainTab = 0;

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
        _data = jsonDecode(resp.body);
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  // ── 颜色系统（Apple 风格）──
  static const _bg = Color(0xFFF2F2F7);           // iOS 系统灰
  static const _cardBg = Colors.white;
  static const _textPrimary = Color(0xFF1C1C1E);
  static const _textSecondary = Color(0xFF8E8E93);
  static const _textTertiary = Color(0xFFAEAEB2);
  static const _accent = Color(0xFF007AFF);        // iOS 蓝
  static const _green = Color(0xFF34C759);
  static const _red = Color(0xFFFF3B30);
  static const _separator = Color(0xFFE5E5EA);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      body: SafeArea(
        child: _loading
            ? const Center(child: CupertinoActivityIndicator())
            : _data == null
                ? _buildError()
                : _buildContent(),
      ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(CupertinoIcons.wifi_slash, size: 48, color: _textTertiary),
          const SizedBox(height: 12),
          Text('数据加载失败', style: TextStyle(color: _textSecondary, fontSize: 15)),
          const SizedBox(height: 16),
          CupertinoButton(
            onPressed: _load,
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }

  Widget _buildContent() {
    return CustomScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      slivers: [
        // 大标题
        CupertinoSliverNavigationBar(
          largeTitle: const Text('数据'),
          backgroundColor: _bg.withOpacity(0.9),
          border: null,
        ),
        // 内容
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 8),
                _buildChainSelector(),
                const SizedBox(height: 16),
                _buildPnlCard(),
                const SizedBox(height: 12),
                _buildCostCard(),
                const SizedBox(height: 12),
                _buildTradingTimeCard(),
                const SizedBox(height: 12),
                _buildLifecycleCard(),
                const SizedBox(height: 12),
                _buildAmountCard(),
                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ],
    );
  }

  // ── 链选择器 ──
  Widget _buildChainSelector() {
    return SizedBox(
      height: 32,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: _chainLabels.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (_, i) {
          final active = _chainTab == i;
          return GestureDetector(
            onTap: () => setState(() => _chainTab = i),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14),
              decoration: BoxDecoration(
                color: active ? _accent : _cardBg,
                borderRadius: BorderRadius.circular(16),
              ),
              alignment: Alignment.center,
              child: Text(
                _chainLabels[i],
                style: TextStyle(
                  color: active ? Colors.white : _textSecondary,
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  // ══════════════════════════════════════════════
  //  卡片 1: 盈亏分布（金字塔）
  // ══════════════════════════════════════════════
  Widget _buildPnlCard() {
    final Map<String, dynamic> d;
    if (_chainTab == 0) {
      d = _data!['all_chain'] as Map<String, dynamic>;
    } else {
      final chain = _chainKeys[_chainTab];
      d = ((_data!['by_chain'] as Map<String, dynamic>)[chain] ?? {}) as Map<String, dynamic>;
    }
    final tiers = (d['tiers'] ?? []) as List;
    final profitPct = (d['profit_pct'] ?? 0).toDouble();
    final lossPct = (d['loss_pct'] ?? 0).toDouble();
    final totalAddr = d['total_addresses'] ?? 0;
    final source = d['source'] ?? d['top_platform'] ?? '';

    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _CardHeader(
            title: '交易者盈亏分布',
            subtitle: '${_fmtCount(totalAddr)} 地址 · $source',
            onInfo: () => _showInfo(d['methodology'] ?? '数据来源：Dune Analytics 全链 DEX 交易'),
          ),
          const SizedBox(height: 20),
          // 金字塔
          _buildPyramid(tiers),
          const SizedBox(height: 20),
          // 盈亏比例条
          _ProfitLossBar(profitPct: profitPct, lossPct: lossPct),
        ],
      ),
    );
  }

  static const _tierColors = [
    Color(0xFFFF9500), // 橙
    Color(0xFFAF52DE), // 紫
    Color(0xFF007AFF), // 蓝
    Color(0xFF5AC8FA), // 浅蓝
    Color(0xFFA2D2FF), // 更浅蓝
    Color(0xFFD1D1D6), // 灰
    Color(0xFFFF3B30), // 红
  ];

  Widget _buildPyramid(List<dynamic> tiers) {
    if (tiers.isEmpty) return const SizedBox.shrink();
    final n = tiers.length;

    return SizedBox(
      height: n * 36.0,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 金字塔图形
          SizedBox(
            width: 120,
            child: CustomPaint(
              size: Size(120, n * 36.0),
              painter: _PyramidPainter(
                count: n,
                colors: List.generate(n, (i) => i < _tierColors.length ? _tierColors[i] : Colors.grey),
              ),
            ),
          ),
          const SizedBox(width: 16),
          // 标签
          Expanded(
            child: Column(
              children: List.generate(n, (i) {
                final t = tiers[i] as Map<String, dynamic>;
                final color = i < _tierColors.length ? _tierColors[i] : Colors.grey;
                return SizedBox(
                  height: 36,
                  child: Row(
                    children: [
                      Container(width: 6, height: 6, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(t['label'] ?? '', style: TextStyle(fontSize: 13, color: _textPrimary, fontWeight: FontWeight.w400)),
                      ),
                      Text(_fmtCount(t['count'] ?? 0), style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: _textPrimary, fontFeatures: const [FontFeature.tabularFigures()])),
                      const SizedBox(width: 6),
                      SizedBox(
                        width: 50,
                        child: Text(
                          _fmtPct(t['pct']),
                          textAlign: TextAlign.right,
                          style: TextStyle(fontSize: 12, color: _textTertiary, fontFeatures: const [FontFeature.tabularFigures()]),
                        ),
                      ),
                    ],
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }

  // ══════════════════════════════════════════════
  //  卡片 2: 交易成本
  // ══════════════════════════════════════════════
  Widget _buildCostCard() {
    const platforms = [
      {'name': 'Axiom', 'rev': 200, 'color': Color(0xFF007AFF)},
      {'name': 'Photon', 'rev': 96, 'color': Color(0xFFAF52DE)},
      {'name': 'GMGN', 'rev': 85, 'color': Color(0xFF34C759)},
      {'name': 'BullX', 'rev': 50, 'color': Color(0xFFFF9500)},
      {'name': 'Trojan', 'rev': 40, 'color': Color(0xFF5856D6)},
    ];

    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _CardHeader(
            title: '用户交易成本',
            subtitle: 'Top 5 平台手续费收入 · 2025',
            onInfo: () => _showInfo('用户亏损 ≈ 平台手续费 + MEV/滑点损失 + 代币归零。\n'
                '手续费数据来自 DeFiLlama，MEV 按交易量 2.5% 估算。\n'
                '代币归零（pump.fun 97%）未计入，实际亏损远大于此。'),
          ),
          const SizedBox(height: 16),
          ...platforms.map((p) {
            final rev = p['rev'] as int;
            final color = p['color'] as Color;
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                children: [
                  SizedBox(width: 52, child: Text(p['name'] as String, style: TextStyle(fontSize: 13, color: _textSecondary))),
                  Expanded(
                    child: LayoutBuilder(builder: (_, c) {
                      return Stack(
                        children: [
                          Container(height: 20, decoration: BoxDecoration(color: _separator, borderRadius: BorderRadius.circular(5))),
                          Container(
                            height: 20,
                            width: c.maxWidth * (rev / 200).clamp(0.05, 1.0),
                            decoration: BoxDecoration(color: color.withOpacity(0.8), borderRadius: BorderRadius.circular(5)),
                            alignment: Alignment.centerRight,
                            padding: const EdgeInsets.only(right: 6),
                            child: Text('\$${rev}M', style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: Colors.white)),
                          ),
                        ],
                      );
                    }),
                  ),
                ],
              ),
            );
          }).toList(),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: _red.withOpacity(0.06),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('确定性损失合计', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: _red)),
                Text('\$971M', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: _red, fontFeatures: const [FontFeature.tabularFigures()])),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text('不含代币归零损失，实际亏损远大于此', style: TextStyle(fontSize: 11, color: _textTertiary)),
          ),
        ],
      ),
    );
  }

  // ══════════════════════════════════════════════
  //  卡片 3: 交易时段
  // ══════════════════════════════════════════════
  Widget _buildTradingTimeCard() {
    const data = [
      {'time': '00-04', 'pct': 18, 'note': '亚洲'},
      {'time': '04-08', 'pct': 13, 'note': ''},
      {'time': '08-12', 'pct': 20, 'note': '欧洲'},
      {'time': '12-16', 'pct': 25, 'note': '欧美'},
      {'time': '16-20', 'pct': 16, 'note': '美洲'},
      {'time': '20-24', 'pct': 8, 'note': ''},
    ];
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _CardHeader(title: '交易量时段分布', subtitle: 'UTC · Solana 链'),
          const SizedBox(height: 16),
          ...data.map((d) {
            final pct = d['pct'] as int;
            final isMax = pct == 25;
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  SizedBox(width: 40, child: Text(d['time'] as String, style: TextStyle(fontSize: 12, color: isMax ? _accent : _textSecondary, fontWeight: isMax ? FontWeight.w600 : FontWeight.w400, fontFeatures: const [FontFeature.tabularFigures()]))),
                  Expanded(
                    child: LayoutBuilder(builder: (_, c) {
                      return Container(
                        height: 16,
                        width: c.maxWidth * pct / 25,
                        decoration: BoxDecoration(
                          color: isMax ? _accent : _accent.withOpacity(0.3),
                          borderRadius: BorderRadius.circular(4),
                        ),
                      );
                    }),
                  ),
                  const SizedBox(width: 8),
                  SizedBox(width: 32, child: Text('$pct%', textAlign: TextAlign.right, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: isMax ? _accent : _textPrimary, fontFeatures: const [FontFeature.tabularFigures()]))),
                  SizedBox(width: 28, child: Text(d['note'] as String, textAlign: TextAlign.right, style: TextStyle(fontSize: 10, color: _textTertiary))),
                ],
              ),
            );
          }).toList(),
        ],
      ),
    );
  }

  // ══════════════════════════════════════════════
  //  卡片 4: 代币生命周期
  // ══════════════════════════════════════════════
  Widget _buildLifecycleCard() {
    const data = [
      {'label': '<1h 新币', 'pct': 45, 'note': '狙击'},
      {'label': '1h-24h', 'pct': 22, 'note': '短线'},
      {'label': '1d-7d', 'pct': 18, 'note': '中线'},
      {'label': '>7d', 'pct': 15, 'note': '长线'},
    ];
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _CardHeader(title: '按代币生命周期', subtitle: '交易量占比'),
          const SizedBox(height: 16),
          ...data.map((d) {
            final pct = d['pct'] as int;
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  SizedBox(width: 64, child: Text(d['label'] as String, style: TextStyle(fontSize: 12, color: _textSecondary))),
                  Expanded(
                    child: LayoutBuilder(builder: (_, c) {
                      return Container(
                        height: 16,
                        width: c.maxWidth * pct / 45,
                        decoration: BoxDecoration(
                          color: _green.withOpacity(0.2 + pct / 100),
                          borderRadius: BorderRadius.circular(4),
                        ),
                      );
                    }),
                  ),
                  const SizedBox(width: 8),
                  SizedBox(width: 32, child: Text('$pct%', textAlign: TextAlign.right, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: _textPrimary, fontFeatures: const [FontFeature.tabularFigures()]))),
                  SizedBox(width: 28, child: Text(d['note'] as String, textAlign: TextAlign.right, style: TextStyle(fontSize: 10, color: _textTertiary))),
                ],
              ),
            );
          }).toList(),
        ],
      ),
    );
  }

  // ══════════════════════════════════════════════
  //  卡片 5: 交易金额
  // ══════════════════════════════════════════════
  Widget _buildAmountCard() {
    const data = [
      {'label': '\$0-50', 'pct': 55, 'note': '散户'},
      {'label': '\$50-200', 'pct': 22, 'note': ''},
      {'label': '\$200-1K', 'pct': 12, 'note': ''},
      {'label': '\$1K-5K', 'pct': 7, 'note': ''},
      {'label': '\$5K+', 'pct': 4, 'note': '鲸鱼'},
    ];
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _CardHeader(title: '单笔交易金额', subtitle: '金额分布占比'),
          const SizedBox(height: 16),
          ...data.map((d) {
            final pct = d['pct'] as int;
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  SizedBox(width: 56, child: Text(d['label'] as String, style: TextStyle(fontSize: 12, color: _textSecondary, fontFeatures: const [FontFeature.tabularFigures()]))),
                  Expanded(
                    child: LayoutBuilder(builder: (_, c) {
                      return Container(
                        height: 16,
                        width: c.maxWidth * pct / 55,
                        decoration: BoxDecoration(
                          color: const Color(0xFFFF9500).withOpacity(0.2 + pct / 100),
                          borderRadius: BorderRadius.circular(4),
                        ),
                      );
                    }),
                  ),
                  const SizedBox(width: 8),
                  SizedBox(width: 32, child: Text('$pct%', textAlign: TextAlign.right, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: _textPrimary, fontFeatures: const [FontFeature.tabularFigures()]))),
                  SizedBox(width: 28, child: Text(d['note'] as String, textAlign: TextAlign.right, style: TextStyle(fontSize: 10, color: _textTertiary))),
                ],
              ),
            );
          }).toList(),
        ],
      ),
    );
  }

  // ── 工具 ──
  void _showInfo(String text) {
    showCupertinoModalPopup(
      context: context,
      builder: (_) => CupertinoActionSheet(
        title: const Text('数据说明'),
        message: Text(text),
        cancelButton: CupertinoActionSheetAction(
          onPressed: () => Navigator.pop(context),
          child: const Text('关闭'),
        ),
      ),
    );
  }

  String _fmtCount(dynamic n) {
    if (n == null) return '0';
    final v = (n is int ? n : (n as num).toInt()).toDouble();
    if (v >= 1e6) return '${(v / 1e6).toStringAsFixed(1)}M';
    if (v >= 1e3) return '${(v / 1e3).toStringAsFixed(1)}K';
    return v.toStringAsFixed(0);
  }

  String _fmtPct(dynamic p) {
    if (p == null) return '0%';
    final v = (p as num).toDouble();
    if (v < 0.01) return '<0.01%';
    return '${v.toStringAsFixed(v < 1 ? 2 : 1)}%';
  }
}

// ══════════════════════════════════════════════
//  通用组件
// ══════════════════════════════════════════════

class _Card extends StatelessWidget {
  final Widget child;
  const _Card({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: child,
    );
  }
}

class _CardHeader extends StatelessWidget {
  final String title;
  final String subtitle;
  final VoidCallback? onInfo;

  const _CardHeader({required this.title, this.subtitle = '', this.onInfo});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF1C1C1E))),
              if (subtitle.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text(subtitle, style: const TextStyle(fontSize: 12, color: Color(0xFF8E8E93))),
                ),
            ],
          ),
        ),
        if (onInfo != null)
          GestureDetector(
            onTap: onInfo,
            child: const Icon(CupertinoIcons.question_circle, size: 18, color: Color(0xFFAEAEB2)),
          ),
      ],
    );
  }
}

class _ProfitLossBar extends StatelessWidget {
  final double profitPct;
  final double lossPct;
  const _ProfitLossBar({required this.profitPct, required this.lossPct});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(3),
          child: Row(
            children: [
              Expanded(flex: (profitPct * 10).toInt(), child: Container(height: 6, color: const Color(0xFF34C759))),
              const SizedBox(width: 2),
              Expanded(flex: (lossPct * 10).toInt(), child: Container(height: 6, color: const Color(0xFFFF3B30))),
            ],
          ),
        ),
        const SizedBox(height: 6),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('${profitPct.toStringAsFixed(1)}% 盈利', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: Color(0xFF34C759))),
            Text('${lossPct.toStringAsFixed(1)}% 亏损', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: Color(0xFFFF3B30))),
          ],
        ),
      ],
    );
  }
}

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
    const topRatio = 0.2;
    const gap = 2.0;

    for (int i = 0; i < count; i++) {
      final t1 = i / count;
      final t2 = (i + 1) / count;
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

      canvas.drawPath(path, Paint()..color = (i < colors.length ? colors[i] : Colors.grey));
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
