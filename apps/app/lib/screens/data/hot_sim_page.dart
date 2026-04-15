import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:ui';

class HotSimPage extends StatefulWidget {
  const HotSimPage({super.key});
  @override
  State<HotSimPage> createState() => _HotSimPageState();
}

class _HotSimPageState extends State<HotSimPage> {
  Map<String, dynamic>? _data;
  bool _loading = true;
  String? _loadError;
  int _sourceTab = 0; // 0=全部, 1=热币, 2=聪明钱, 3=新币, 4=BTC/ETH
  int _modeTab = 0;   // 0=repeat, 1=unique
  Timer? _autoRefreshTimer;

  static const _apiBase = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://43.156.207.26');
  static const _sourceKeys = ['', 'hot', 'smart_money', 'pump', 'btc_eth'];
  static const _sourceLabels = ['全部', '热币', '聪明钱', '新币', 'BTC/ETH'];
  static const _cachePrefix = 'hot_sim_cache_v1_';

  static const _t1 = Color(0xFF000000);
  static const _t2 = Color(0xFF3C3C43);
  static const _t3 = Color(0xFF8E8E93);
  static const _t4 = Color(0xFFC7C7CC);
  static const _bg = Color(0xFFF2F2F7);
  static const _blue = Color(0xFF007AFF);
  static const _green = Color(0xFF34C759);
  static const _red = Color(0xFFFF3B30);

  @override
  void initState() {
    super.initState();
    _loadFromCache().then((_) => _load());
    _autoRefreshTimer = Timer.periodic(const Duration(minutes: 2), (_) => _load(silent: true));
  }

  @override
  void dispose() {
    _autoRefreshTimer?.cancel();
    super.dispose();
  }

  String get _cacheKey => '$_cachePrefix${_sourceKeys[_sourceTab]}';

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

  Future<void> _load({bool silent = false}) async {
    if (!silent && _data == null) {
      setState(() { _loading = true; _loadError = null; });
    }

    Map<String, dynamic>? newData;
    String? lastError;

    final src = _sourceKeys[_sourceTab];
    final url = src.isEmpty
        ? '$_apiBase/api/data/hot-sim/compare'
        : '$_apiBase/api/data/hot-sim/compare?source=$src';

    // 3 次重试，超时 15s，间隔 2s
    for (int attempt = 0; attempt < 3; attempt++) {
      try {
        final r = await http.get(Uri.parse(url)).timeout(const Duration(seconds: 15));
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
      setState(() {
        _loading = false;
        _loadError = lastError;
      });
    }
  }

  Future<void> _onRefresh() async {
    HapticFeedback.lightImpact();
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _bg,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(CupertinoIcons.back, color: _t1, size: 22),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text('策略监控', style: TextStyle(color: _t1, fontSize: 17, fontWeight: FontWeight.w600)),
        centerTitle: true,
      ),
      body: _loading && _data == null
          ? const Center(child: CupertinoActivityIndicator())
          : _data == null
              ? _buildEmptyState()
              : RefreshIndicator(onRefresh: _onRefresh, color: _blue, child: _buildBody()),
    );
  }

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

  Widget _buildBody() {
    final isBtcEth = _sourceTab == 4;
    final modeKey = isBtcEth ? 'repeat' : (_modeTab == 0 ? 'repeat' : 'unique');
    final d = _data![modeKey] as Map<String, dynamic>? ?? {};
    final summary = d['summary'] as Map<String, dynamic>? ?? {};
    final trades = (d['recent_trades'] as List?) ?? [];

    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      children: [
        const SizedBox(height: 8),

        // 信号源 Tab
        SizedBox(height: 32, child: ListView.separated(
          scrollDirection: Axis.horizontal, itemCount: _sourceLabels.length,
          separatorBuilder: (_, __) => const SizedBox(width: 6),
          itemBuilder: (_, i) {
            final on = _sourceTab == i;
            return GestureDetector(
              onTap: () async {
                setState(() { _sourceTab = i; _modeTab = 0; _data = null; _loading = true; });
                await _loadFromCache();
                _load();
              },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(color: on ? _t1 : Colors.white, borderRadius: BorderRadius.circular(16)),
                alignment: Alignment.center,
                child: Text(_sourceLabels[i], style: TextStyle(color: on ? Colors.white : _t3, fontSize: 12, fontWeight: FontWeight.w500)),
              ),
            );
          },
        )),
        const SizedBox(height: 10),

        // 模式切换（BTC/ETH 不显示 unique）
        if (!isBtcEth)
          Container(
            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(10)),
            padding: const EdgeInsets.all(3),
            child: Row(
              children: List.generate(2, (i) {
                final on = _modeTab == i;
                return Expanded(child: GestureDetector(
                  onTap: () => setState(() => _modeTab = i),
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 7),
                    decoration: BoxDecoration(color: on ? _t1 : Colors.transparent, borderRadius: BorderRadius.circular(8)),
                    alignment: Alignment.center,
                    child: Text(i == 0 ? '每次都买' : '每币只买一次', style: TextStyle(color: on ? Colors.white : _t3, fontSize: 12, fontWeight: FontWeight.w500)),
                  ),
                ));
              }),
            ),
          ),
        const SizedBox(height: 12),

        // 配置说明
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(10)),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _configItem('买入金额', '\$10'),
              Container(width: 1, height: 24, color: _t4.withOpacity(0.3)),
              _configItem('止盈', '+15%'),
              Container(width: 1, height: 24, color: _t4.withOpacity(0.3)),
              _configItem('止损', '-15%'),
            ],
          ),
        ),
        const SizedBox(height: 12),

        // 核心数据
        _buildSummaryCard(summary),
        const SizedBox(height: 12),

        // 盈亏指标
        _buildMetricsRow(summary),
        const SizedBox(height: 12),

        // 交易记录
        _buildTradesCard(trades),
        const SizedBox(height: 32),
      ],
    );
  }

  Widget _configItem(String label, String value) {
    return Column(children: [
      Text(value, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: _t1)),
      const SizedBox(height: 2),
      Text(label, style: const TextStyle(fontSize: 11, color: _t3)),
    ]);
  }

  Widget _buildSummaryCard(Map<String, dynamic> s) {
    final pnl = (s['realized_pnl'] ?? 0).toDouble();
    final roi = (s['roi_pct'] ?? 0).toDouble();
    final invested = (s['total_invested'] ?? 0).toDouble();
    final isPositive = pnl >= 0;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(14)),
      child: Column(children: [
        // 已实现盈亏 — 大数字
        Text(
          '${isPositive ? "+" : ""}\$${pnl.toStringAsFixed(2)}',
          style: TextStyle(fontSize: 36, fontWeight: FontWeight.w700,
            color: isPositive ? _green : _red,
            fontFeatures: const [FontFeature.tabularFigures()]),
        ),
        const SizedBox(height: 4),
        Text('已实现盈亏', style: TextStyle(fontSize: 13, color: _t3)),
        const SizedBox(height: 16),

        // ROI + 投入
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: (isPositive ? _green : _red).withOpacity(0.1),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              '${isPositive ? "+" : ""}${roi.toStringAsFixed(1)}% ROI',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600,
                color: isPositive ? _green : _red,
                fontFeatures: const [FontFeature.tabularFigures()]),
            ),
          ),
          const SizedBox(width: 12),
          Text('投入 \$${invested.toStringAsFixed(0)}', style: TextStyle(fontSize: 13, color: _t3,
            fontFeatures: const [FontFeature.tabularFigures()])),
        ]),
      ]),
    );
  }

  Widget _buildMetricsRow(Map<String, dynamic> s) {
    final winRate = (s['win_rate'] ?? 0).toDouble();
    return Row(children: [
      _metricCard('总交易', '${s['total_trades'] ?? 0}', _blue),
      const SizedBox(width: 8),
      _metricCard('胜率', '${winRate.toStringAsFixed(1)}%', winRate >= 50 ? _green : _red),
      const SizedBox(width: 8),
      _metricCard('持仓中', '${s['open_trades'] ?? 0}', _blue),
      const SizedBox(width: 8),
      _metricCard('已平仓', '${s['closed_trades'] ?? 0}', _t2),
    ]);
  }

  Widget _metricCard(String label, String value, Color color) {
    return Expanded(child: Container(
      padding: const EdgeInsets.symmetric(vertical: 12),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(10)),
      child: Column(children: [
        Text(value, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: color,
          fontFeatures: const [FontFeature.tabularFigures()])),
        const SizedBox(height: 2),
        Text(label, style: const TextStyle(fontSize: 11, color: _t3)),
      ]),
    ));
  }

  Widget _buildTradesCard(List trades) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(14)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('交易记录', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: _t1)),
        const SizedBox(height: 12),
        if (trades.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 20),
            child: Center(child: Text('等待热币入榜触发...', style: TextStyle(fontSize: 13, color: _t4))),
          )
        else
          ...trades.map((t) {
            final status = t['status'] ?? 'open';
            final pnl = (t['pnl_usd'] as num?)?.toDouble();
            final pnlPct = (t['pnl_pct'] as num?)?.toDouble();
            final isWin = status == 'tp';
            final isLoss = status == 'sl';
            final isOpen = status == 'open';

            return Container(
              padding: const EdgeInsets.symmetric(vertical: 10),
              decoration: BoxDecoration(
                border: Border(bottom: BorderSide(color: _t4.withOpacity(0.2))),
              ),
              child: Row(children: [
                // 状态指示
                Container(
                  width: 6, height: 6,
                  decoration: BoxDecoration(
                    color: isWin ? _green : isLoss ? _red : _blue,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                // 代币信息
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(t['symbol'] ?? '?', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: _t1)),
                  Text('${t['chain'] ?? ''} · score ${(t['score'] as num?)?.toStringAsFixed(0) ?? '-'}',
                    style: TextStyle(fontSize: 11, color: _t3)),
                ])),
                // 盈亏
                Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                  if (pnl != null)
                    Text('${pnl >= 0 ? "+" : ""}\$${pnl.toStringAsFixed(2)}',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600,
                        color: pnl >= 0 ? _green : _red,
                        fontFeatures: const [FontFeature.tabularFigures()]))
                  else
                    Text('持仓中', style: TextStyle(fontSize: 13, color: _blue)),
                  Text(isOpen ? '进行中' : isWin ? '止盈' : '止损',
                    style: TextStyle(fontSize: 11, color: isWin ? _green : isLoss ? _red : _t3)),
                ]),
              ]),
            );
          }).toList(),
      ]),
    );
  }
}
