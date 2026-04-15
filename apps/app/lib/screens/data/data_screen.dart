import 'dart:async';
import 'dart:convert';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'hot_sim_page.dart';

class DataScreen extends StatefulWidget {
  const DataScreen({super.key});
  @override
  State<DataScreen> createState() => _DataScreenState();
}

class _DataScreenState extends State<DataScreen> {
  Map<String, dynamic>? _data;
  bool _loading = true;
  bool _refreshing = false;
  String? _loadError;
  int _chainTab = 0;
  Timer? _autoRefreshTimer;

  static const _apiBase = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://43.156.207.26');
  static const _chainKeys = ['all', 'solana', 'bsc', 'ethereum', 'base'];
  static const _chainLabels = ['全链', 'SOL', 'BSC', 'ETH', 'Base'];
  static const _cacheKey = 'data_screen_cache_v2';

  @override
  void initState() {
    super.initState();
    _loadFromCache().then((_) => _load());
    // 每 5 分钟后台自动刷新一次，保证数据新鲜（失败也不影响显示）
    _autoRefreshTimer = Timer.periodic(const Duration(minutes: 5), (_) => _load(silent: true));
  }

  @override
  void dispose() {
    _autoRefreshTimer?.cancel();
    super.dispose();
  }

  /// 先从本地缓存加载，保证 App 一打开就有数据
  Future<void> _loadFromCache() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cached = prefs.getString(_cacheKey);
      if (cached != null && cached.isNotEmpty) {
        final data = jsonDecode(cached) as Map<String, dynamic>;
        if (mounted) setState(() { _data = data; _loading = false; });
      }
    } catch (_) {}
  }

  /// 从服务器加载，带 3 次自动重试 + 本地缓存
  /// silent=true 时不改 loading 状态（用于后台定时刷新）
  Future<void> _load({bool silent = false}) async {
    if (!silent && _data == null) {
      setState(() { _loading = true; _loadError = null; });
    }

    Map<String, dynamic>? newData;
    String? lastError;

    // 3 次重试，超时 15s，间隔 2s
    for (int attempt = 0; attempt < 3; attempt++) {
      try {
        final r = await http
            .get(Uri.parse('$_apiBase/api/data/pnl-distribution'))
            .timeout(const Duration(seconds: 15));
        if (r.statusCode == 200) {
          newData = jsonDecode(r.body) as Map<String, dynamic>;
          break;
        }
        lastError = 'HTTP ${r.statusCode}';
      } catch (e) {
        lastError = e.toString().split('\n').first;
      }
      if (attempt < 2) await Future.delayed(const Duration(seconds: 2));
    }

    if (!mounted) return;

    if (newData != null) {
      // 成功 → 更新数据并缓存到本地
      setState(() {
        _data = newData;
        _loading = false;
        _loadError = null;
      });
      try {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(_cacheKey, jsonEncode(newData));
      } catch (_) {}
    } else {
      // 失败 → 保留旧数据（如果有），只显示错误标识
      setState(() {
        _loading = false;
        _loadError = lastError;
      });
    }
  }

  /// 下拉刷新
  Future<void> _onRefresh() async {
    if (_refreshing) return;
    _refreshing = true;
    HapticFeedback.lightImpact();
    await _load();
    _refreshing = false;
  }

  // ── 设计系统 ──
  static const _bg = Color(0xFFF2F2F7);
  static const _card = Colors.white;
  static const _t1 = Color(0xFF000000);    // 标题
  static const _t2 = Color(0xFF3C3C43);    // 正文
  static const _t3 = Color(0xFF8E8E93);    // 辅助
  static const _t4 = Color(0xFFC7C7CC);    // 淡化
  static const _blue = Color(0xFF007AFF);
  static const _green = Color(0xFF34C759);
  static const _red = Color(0xFFFF3B30);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      body: SafeArea(
        child: _loading && _data == null
            ? const Center(child: CupertinoActivityIndicator())
            : _data == null
                ? _buildEmptyState()
                : RefreshIndicator(
                    onRefresh: _onRefresh,
                    color: _blue,
                    child: CustomScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    slivers: [
                      CupertinoSliverNavigationBar(largeTitle: const Text('数据'), backgroundColor: _bg.withOpacity(0.9), border: null),
                      if (_loadError != null) SliverToBoxAdapter(child: _buildOfflineBanner()),
                      SliverToBoxAdapter(child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          const SizedBox(height: 8),
                          _chainSelector(),
                          const SizedBox(height: 16),
                          _pnlCard(),
                          const SizedBox(height: 12),
                          _costCard(),
                          const SizedBox(height: 12),
                          _timeCard(),
                          const SizedBox(height: 12),
                          _lifecycleCard(),
                          const SizedBox(height: 12),
                          _amountCard(),
                          const SizedBox(height: 20),
                          // 弱化入口：模拟盘看板
                          GestureDetector(
                            onTap: () => Navigator.push(context, CupertinoPageRoute(
                              builder: (_) => const HotSimPage(),
                            )),
                            child: Container(
                              padding: const EdgeInsets.symmetric(vertical: 12),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(CupertinoIcons.chart_bar_alt_fill, size: 14, color: _t4),
                                  const SizedBox(width: 6),
                                  Text('策略监控', style: TextStyle(fontSize: 13, color: _t4)),
                                  const SizedBox(width: 4),
                                  Icon(CupertinoIcons.chevron_right, size: 12, color: _t4),
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(height: 20),
                        ]),
                      )),
                    ],
                  ),
                  ),
      ),
    );
  }

  /// 首次加载失败（无缓存）— 显示友好的空状态
  Widget _buildEmptyState() {
    return RefreshIndicator(
      onRefresh: _onRefresh,
      color: _blue,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          const SizedBox(height: 200),
          Icon(CupertinoIcons.wifi_exclamationmark, size: 56, color: _t4),
          const SizedBox(height: 16),
          Center(child: Text('暂时无法加载数据', style: TextStyle(fontSize: 15, color: _t2, fontWeight: FontWeight.w600))),
          const SizedBox(height: 8),
          Center(child: Text('下拉刷新重试', style: TextStyle(fontSize: 13, color: _t3))),
          const SizedBox(height: 24),
          Center(
            child: CupertinoButton(
              color: _blue,
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 10),
              borderRadius: BorderRadius.circular(20),
              onPressed: _loading ? null : _load,
              child: _loading
                  ? const CupertinoActivityIndicator(color: Colors.white)
                  : const Text('重新加载', style: TextStyle(fontSize: 14)),
            ),
          ),
        ],
      ),
    );
  }

  /// 有缓存数据但本次刷新失败 — 显示顶部小横幅，不影响内容展示
  Widget _buildOfflineBanner() {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 0),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF3CD),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFFFE69C), width: 0.5),
      ),
      child: Row(
        children: [
          Icon(CupertinoIcons.wifi_slash, size: 14, color: const Color(0xFF856404)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '当前为缓存数据，下拉刷新',
              style: TextStyle(fontSize: 12, color: const Color(0xFF856404)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _chainSelector() {
    return SizedBox(height: 32, child: ListView.separated(
      scrollDirection: Axis.horizontal, itemCount: _chainLabels.length,
      separatorBuilder: (_, __) => const SizedBox(width: 8),
      itemBuilder: (_, i) {
        final on = _chainTab == i;
        return GestureDetector(
          onTap: () => setState(() => _chainTab = i),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(color: on ? _t1 : _card, borderRadius: BorderRadius.circular(16)),
            alignment: Alignment.center,
            child: Text(_chainLabels[i], style: TextStyle(color: on ? Colors.white : _t3, fontSize: 13, fontWeight: FontWeight.w500)),
          ),
        );
      },
    ));
  }

  // ═══════════════════════════════════════
  //  1. 盈亏分布
  // ═══════════════════════════════════════
  Widget _pnlCard() {
    final d = _chainTab == 0
        ? _data!['all_chain'] as Map<String, dynamic>
        : ((_data!['by_chain'] as Map<String, dynamic>)[_chainKeys[_chainTab]] ?? {}) as Map<String, dynamic>;
    final tiers = (d['tiers'] ?? []) as List;
    final profit = (d['profit_pct'] ?? 0).toDouble();
    final loss = (d['loss_pct'] ?? 0).toDouble();
    final total = d['total_addresses'] ?? 0;

    return _C(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _H(title: '交易者盈亏', sub: '${_fn(total)} 地址', onTap: () => _info(d['methodology'] ?? '数据来源：Dune Analytics')),
      const SizedBox(height: 16),
      // 大数字
      Row(children: [
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${profit.toStringAsFixed(1)}%', style: TextStyle(fontSize: 34, fontWeight: FontWeight.w700, color: _green, fontFeatures: const [FontFeature.tabularFigures()])),
          Text('盈利', style: TextStyle(fontSize: 13, color: _t3)),
        ])),
        Container(width: 1, height: 40, color: _t4.withOpacity(0.3)),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text('${loss.toStringAsFixed(1)}%', style: TextStyle(fontSize: 34, fontWeight: FontWeight.w700, color: _red, fontFeatures: const [FontFeature.tabularFigures()])),
          Text('亏损', style: TextStyle(fontSize: 13, color: _t3)),
        ])),
      ]),
      const SizedBox(height: 16),
      // 比例条
      ClipRRect(borderRadius: BorderRadius.circular(4), child: Row(children: [
        Expanded(flex: (profit * 10).toInt(), child: Container(height: 6, color: _green)),
        const SizedBox(width: 2),
        Expanded(flex: (loss * 10).toInt(), child: Container(height: 6, color: _red)),
      ])),
      const SizedBox(height: 16),
      // 金字塔
      SizedBox(height: tiers.length * 32.0, child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(width: 100, child: CustomPaint(size: Size(100, tiers.length * 32.0), painter: _Pyramid(tiers.length))),
        const SizedBox(width: 12),
        Expanded(child: Column(children: List.generate(tiers.length, (i) {
          final t = tiers[i] as Map<String, dynamic>;
          return SizedBox(height: 32, child: Row(children: [
            Expanded(child: Text(t['label'] ?? '', style: TextStyle(fontSize: 12, color: _t2))),
            Text(_fn(t['count'] ?? 0), style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: _t1, fontFeatures: const [FontFeature.tabularFigures()])),
            const SizedBox(width: 6),
            SizedBox(width: 44, child: Text(_fp(t['pct']), textAlign: TextAlign.right, style: TextStyle(fontSize: 11, color: _t3, fontFeatures: const [FontFeature.tabularFigures()]))),
          ]));
        }))),
      ])),
    ]));
  }

  // ═══════════════════════════════════════
  //  2. 交易成本
  // ═══════════════════════════════════════
  Widget _costCard() {
    const items = [
      {'n': 'Axiom', 'v': 200, 'c': Color(0xFF007AFF)},
      {'n': 'Photon', 'v': 96, 'c': Color(0xFFAF52DE)},
      {'n': 'GMGN', 'v': 85, 'c': Color(0xFF34C759)},
      {'n': 'BullX', 'v': 50, 'c': Color(0xFFFF9500)},
      {'n': 'Trojan', 'v': 40, 'c': Color(0xFF5856D6)},
    ];
    return _C(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _H(title: '用户交易成本', sub: 'Top 5 手续费收入 · 2025', onTap: () => _info('用户亏损 ≈ 平台手续费 + MEV/滑点 + 代币归零。\n手续费来自 DeFiLlama，MEV 按 2.5% 估算。\n代币归零未计入。\n刷新周期：每月更新。')),
      const SizedBox(height: 16),
      ...items.map((it) {
        final v = it['v'] as int;
        return Padding(padding: const EdgeInsets.only(bottom: 12), child: Row(children: [
          SizedBox(width: 56, child: Text(it['n'] as String, style: TextStyle(fontSize: 13, color: _t2))),
          Expanded(child: Stack(children: [
            Container(height: 8, decoration: BoxDecoration(color: _bg, borderRadius: BorderRadius.circular(4))),
            FractionallySizedBox(widthFactor: (v / 200).clamp(0.05, 1.0),
              child: Container(height: 8, decoration: BoxDecoration(
                color: it['c'] as Color,
                borderRadius: BorderRadius.circular(4)))),
          ])),
          const SizedBox(width: 10),
          SizedBox(width: 50, child: Text('\$$v M', textAlign: TextAlign.right, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: _t1, fontFeatures: const [FontFeature.tabularFigures()]))),
        ]));
      }).toList(),
      const SizedBox(height: 4),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(color: _red.withOpacity(0.05), borderRadius: BorderRadius.circular(10)),
        child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text('确定性损失合计', style: TextStyle(fontSize: 13, color: _red)),
          Text('\$971M', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: _red, fontFeatures: const [FontFeature.tabularFigures()])),
        ]),
      ),
      Padding(padding: const EdgeInsets.only(top: 6), child: Text('不含代币归零损失', style: TextStyle(fontSize: 11, color: _t4))),
    ]));
  }

  // ═══════════════════════════════════════
  //  3. 交易时段 — 圆角竖柱
  // ═══════════════════════════════════════
  Widget _timeCard() {
    const d = [
      {'t': '00', 'v': 18}, {'t': '04', 'v': 13}, {'t': '08', 'v': 20},
      {'t': '12', 'v': 25}, {'t': '16', 'v': 16}, {'t': '20', 'v': 8},
    ];
    return _C(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _H(title: '交易量时段', sub: 'UTC · Solana', onTap: () => _info('Solana 链 DEX 交易量按 UTC 时段分布。\n12-16 UTC = 北京 20:00-00:00，欧美重叠。\n刷新周期：每周更新。')),
      const SizedBox(height: 20),
      SizedBox(height: 130, child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: d.map((s) {
        final v = s['v'] as int;
        final peak = v == 25;
        return Expanded(child: Padding(padding: const EdgeInsets.symmetric(horizontal: 4), child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
          Text('$v%', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: peak ? _blue : _t3, fontFeatures: const [FontFeature.tabularFigures()])),
          const SizedBox(height: 4),
          Container(height: 90.0 * v / 28, decoration: BoxDecoration(
            gradient: peak
                ? const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF007AFF), Color(0xFF5856D6)])
                : LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [const Color(0xFF007AFF).withOpacity(0.2), const Color(0xFF5856D6).withOpacity(0.1)]),
            borderRadius: BorderRadius.circular(8),
          )),
          const SizedBox(height: 6),
          Text('${s['t']}', style: TextStyle(fontSize: 11, color: _t3, fontFeatures: const [FontFeature.tabularFigures()])),
        ])));
      }).toList())),
    ]));
  }

  // ═══════════════════════════════════════
  //  4. 生命周期 — 数字卡片
  // ═══════════════════════════════════════
  Widget _lifecycleCard() {
    const items = [
      {'label': '<1h', 'pct': '45', 'sub': '狙击为主', 'color': Color(0xFF34C759)},
      {'label': '1h-24h', 'pct': '22', 'sub': '短线波段', 'color': Color(0xFF007AFF)},
      {'label': '1d-7d', 'pct': '18', 'sub': '中线持有', 'color': Color(0xFFAF52DE)},
      {'label': '>7d', 'pct': '15', 'sub': '长线', 'color': Color(0xFFFF9500)},
    ];
    return _C(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _H(title: '代币生命周期', sub: '交易量占比', onTap: () => _info('<1h：狙击新币。\n1h-24h：短线波段。\n1d-7d：中线。\n>7d：长线。\n刷新周期：每周更新。')),
      const SizedBox(height: 14),
      Row(children: items.map((it) {
        final c = it['color'] as Color;
        return Expanded(child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 3),
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: BoxDecoration(color: c.withOpacity(0.08), borderRadius: BorderRadius.circular(12)),
          child: Column(children: [
            Text('${it['pct']}%', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: c, fontFeatures: const [FontFeature.tabularFigures()])),
            const SizedBox(height: 4),
            Text(it['label'] as String, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: _t2)),
            const SizedBox(height: 2),
            Text(it['sub'] as String, style: TextStyle(fontSize: 10, color: _t4)),
          ]),
        ));
      }).toList()),
    ]));
  }

  // ═══════════════════════════════════════
  //  5. 交易金额 — 数字列表
  // ═══════════════════════════════════════
  Widget _amountCard() {
    const items = [
      {'r': '\$0-50', 'p': 55, 'tag': '散户试水', 'c': Color(0xFFFF9500)},
      {'r': '\$50-200', 'p': 22, 'tag': '中等仓位', 'c': Color(0xFFFF9F0A)},
      {'r': '\$200-1K', 'p': 12, 'tag': '', 'c': Color(0xFFFFB340)},
      {'r': '\$1K-5K', 'p': 7, 'tag': '', 'c': Color(0xFFFFCC00)},
      {'r': '\$5K+', 'p': 4, 'tag': '鲸鱼', 'c': Color(0xFF34C759)},
    ];
    return _C(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _H(title: '单笔交易金额', sub: '金额分布', onTap: () => _info('\$0-50 散户占 55%。\n\$5K+ 鲸鱼仅 4% 但贡献 ~40% 交易额。\n刷新周期：每周更新。')),
      const SizedBox(height: 12),
      ...items.map((it) {
        final p = it['p'] as int;
        final tag = it['tag'] as String;
        return Padding(padding: const EdgeInsets.only(bottom: 2), child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
          decoration: BoxDecoration(
            border: Border(bottom: BorderSide(color: _t4.withOpacity(0.3), width: 0.5)),
          ),
          child: Row(children: [
            SizedBox(width: 64, child: Text(it['r'] as String, style: TextStyle(fontSize: 14, color: _t2, fontFeatures: const [FontFeature.tabularFigures()]))),
            Expanded(child: tag.isNotEmpty ? Text(tag, style: TextStyle(fontSize: 12, color: _t4)) : const SizedBox()),
            Text('$p%', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: it['c'] as Color, fontFeatures: const [FontFeature.tabularFigures()])),
          ]),
        ));
      }).toList(),
    ]));
  }

  // ── 工具 ──
  void _info(String t) {
    showModalBottomSheet(context: context, backgroundColor: Colors.transparent, builder: (_) => Container(
      margin: const EdgeInsets.all(12), padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(16)),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Container(width: 36, height: 4, decoration: BoxDecoration(color: _t4, borderRadius: BorderRadius.circular(2))),
        const SizedBox(height: 14),
        Row(children: [Icon(CupertinoIcons.info_circle, size: 16, color: _blue), const SizedBox(width: 6),
          Text('数据说明', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: _t1))]),
        const SizedBox(height: 10),
        Text(t, style: TextStyle(fontSize: 13, color: _t3, height: 1.7)),
      ]),
    ));
  }

  String _fn(dynamic n) {
    if (n == null) return '0';
    final v = (n is int ? n : (n as num).toInt()).toDouble();
    if (v >= 1e6) return '${(v / 1e6).toStringAsFixed(1)}M';
    if (v >= 1e3) return '${(v / 1e3).toStringAsFixed(1)}K';
    return v.toStringAsFixed(0);
  }

  String _fp(dynamic p) {
    if (p == null) return '0%';
    final v = (p as num).toDouble();
    return v < 0.01 ? '<0.01%' : '${v.toStringAsFixed(v < 1 ? 2 : 1)}%';
  }
}

// ── 基础组件 ──

class _C extends StatelessWidget {
  final Widget child;
  const _C({required this.child});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(14)),
    child: child,
  );
}

class _H extends StatelessWidget {
  final String title, sub;
  final VoidCallback? onTap;
  const _H({required this.title, this.sub = '', this.onTap});
  @override
  Widget build(BuildContext context) => Row(children: [
    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: Color(0xFF000000), letterSpacing: -0.3)),
      if (sub.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 2), child: Text(sub, style: const TextStyle(fontSize: 12, color: Color(0xFF8E8E93)))),
    ])),
    if (onTap != null) GestureDetector(onTap: onTap, child: const Icon(CupertinoIcons.question_circle, size: 18, color: Color(0xFFC7C7CC))),
  ]);
}

class _Pyramid extends CustomPainter {
  final int n;
  _Pyramid(this.n);
  static const _colors = [Color(0xFFFF9500), Color(0xFFAF52DE), Color(0xFF007AFF), Color(0xFF5AC8FA), Color(0xFFAED6F1), Color(0xFFD1D1D6), Color(0xFFFF3B30)];

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height, rh = h / n;
    for (int i = 0; i < n; i++) {
      final t1 = i / n, t2 = (i + 1) / n;
      final ht = (0.15 + 0.85 * t1) * w / 2, hb = (0.15 + 0.85 * t2) * w / 2;
      final cx = w / 2, y1 = i * rh + 1.5, y2 = (i + 1) * rh - 1.5;
      canvas.drawPath(Path()..moveTo(cx - ht, y1)..lineTo(cx + ht, y1)..lineTo(cx + hb, y2)..lineTo(cx - hb, y2)..close(),
        Paint()..color = i < _colors.length ? _colors[i] : Colors.grey);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter old) => false;
}
