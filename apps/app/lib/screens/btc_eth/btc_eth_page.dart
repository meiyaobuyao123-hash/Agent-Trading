import 'dart:async';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import '../../models/btc_eth.dart';
import '../../services/btc_eth_service.dart';
import '../../widgets/btc_eth/cycle_status_bar.dart';
import '../../widgets/btc_eth/signal_card.dart';
import '../../widgets/btc_eth/risk_dashboard.dart';

/// BTC/ETH 智能投资页面
class BtcEthPage extends StatefulWidget {
  const BtcEthPage({super.key});

  @override
  State<BtcEthPage> createState() => _BtcEthPageState();
}

class _BtcEthPageState extends State<BtcEthPage> {
  BtcEthDashboard? _dashboard;
  List<BtcEthSignal> _signals = [];
  List<BtcEthAlert> _alerts = [];
  BtcEthReport? _btcReport;
  bool _loading = true;
  String _selectedAsset = 'BTC';
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _load();
    _refreshTimer = Timer.periodic(const Duration(seconds: 30), (_) => _load());
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    final svc = BtcEthService.instance;
    try {
      final results = await Future.wait([
        svc.fetchDashboard(),
        svc.fetchSignals(limit: 20),
        svc.fetchAlerts(),
        svc.fetchLatestReport('BTC'),
      ]);

      if (!mounted) return;
      setState(() {
        // 只在有新数据时更新，避免刷新失败清空旧数据
        final newDash = results[0] as BtcEthDashboard?;
        if (newDash != null) _dashboard = newDash;
        final newSignals = results[1] as List<BtcEthSignal>;
        if (newSignals.isNotEmpty || _signals.isEmpty) _signals = newSignals;
        final newAlerts = results[2] as List<BtcEthAlert>;
        _alerts = newAlerts;
        final newReport = results[3] as BtcEthReport?;
        if (newReport != null) _btcReport = newReport;
        _loading = false;
      });
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _dashboard == null) {
      return const Center(child: CupertinoActivityIndicator());
    }

    final assetData = _selectedAsset == 'BTC'
        ? _dashboard?.btc
        : _dashboard?.eth;

    return CustomScrollView(
      slivers: [
        CupertinoSliverRefreshControl(onRefresh: _load),

        // 价格头部
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: _buildPriceHeader(),
          ),
        ),

        // 资产切换
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: ['BTC', 'ETH'].map((asset) {
                final isSelected = asset == _selectedAsset;
                return Expanded(
                  child: GestureDetector(
                    onTap: () => setState(() => _selectedAsset = asset),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      decoration: BoxDecoration(
                        color: isSelected
                            ? const Color(0xFF3B82F6)
                            : const Color(0xFFF2F2F7),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        asset,
                        style: TextStyle(
                          color: isSelected ? Colors.white : const Color(0xFF8E8E93),
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
        ),

        // 周期状态条
        if (_btcReport != null)
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: CycleStatusBar(
                currentPhase: _btcReport!.cyclePhase,
                confidence: _btcReport!.cycleConfidence,
              ),
            ),
          ),

        // 风险仪表盘
        if (assetData != null)
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: RiskDashboard(data: assetData, asset: _selectedAsset),
            ),
          ),

        // 预警
        if (_alerts.isNotEmpty)
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
              child: _buildAlerts(),
            ),
          ),

        // 信号标题
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: Text(
              'Trading Signals',
              style: TextStyle(
                color: const Color(0xFF3C3C43),
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),

        // 信号列表
        if (_signals.isEmpty)
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Center(
                child: Text(
                  'No signals yet. Agent is analyzing market data...',
                  style: TextStyle(color: const Color(0xFFC7C7CC)),
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          )
        else
          SliverList(
            delegate: SliverChildBuilderDelegate(
              (context, index) {
                final filtered = _signals.where((s) =>
                    _selectedAsset == 'BTC' ? s.asset == 'BTC' : s.asset == 'ETH'
                ).toList();
                if (index >= filtered.length) return null;
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: BtcEthSignalCard(signal: filtered[index]),
                );
              },
              childCount: _signals.where((s) =>
                  _selectedAsset == 'BTC' ? s.asset == 'BTC' : s.asset == 'ETH'
              ).length,
            ),
          ),

        // 底部间距
        const SliverToBoxAdapter(child: SizedBox(height: 100)),
      ],
    );
  }

  Widget _buildPriceHeader() {
    final btc = _dashboard?.btc;
    final eth = _dashboard?.eth;
    return Row(
      children: [
        _priceChip('BTC', btc?.price ?? 0, btc?.change24h ?? 0),
        const SizedBox(width: 8),
        _priceChip('ETH', eth?.price ?? 0, eth?.change24h ?? 0),
      ],
    );
  }

  Widget _priceChip(String asset, double price, double change) {
    final isUp = change >= 0;
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFFF2F2F7),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(asset,
                style: const TextStyle(
                    color: const Color(0xFF8E8E93), fontSize: 12)),
            const SizedBox(height: 2),
            Text(
              '\$${price >= 1000 ? price.toStringAsFixed(0) : price.toStringAsFixed(2)}',
              style: const TextStyle(
                  color: const Color(0xFF000000),
                  fontSize: 20,
                  fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 2),
            Text(
              '${isUp ? '+' : ''}${change.toStringAsFixed(2)}%',
              style: TextStyle(
                color: isUp ? const Color(0xFF22C55E) : const Color(0xFFEF4444),
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAlerts() {
    return Column(
      children: _alerts.take(3).map((alert) {
        final color = alert.isCritical
            ? const Color(0xFFEF4444)
            : alert.isWarning
                ? const Color(0xFFF97316)
                : const Color(0xFF3B82F6);
        return Container(
          margin: const EdgeInsets.only(bottom: 4),
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: color.withValues(alpha: 0.3)),
          ),
          child: Row(
            children: [
              Icon(
                alert.isCritical ? Icons.warning : Icons.info_outline,
                color: color,
                size: 16,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  alert.title,
                  style: TextStyle(color: color, fontSize: 12),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }
}
