import 'package:flutter/material.dart';
import '../../services/agent_service.dart';

/// 策略详情页 — 模拟盘表现 + 交易记录 + 回测 + 切换实盘
class StrategyDetailPage extends StatefulWidget {
  final AgentStrategy strategy;
  const StrategyDetailPage({super.key, required this.strategy});

  @override
  State<StrategyDetailPage> createState() => _StrategyDetailPageState();
}

class _StrategyDetailPageState extends State<StrategyDetailPage> {
  Map<String, dynamic> _stats = {};
  List<Map<String, dynamic>> _trades = [];
  Map<String, dynamic>? _backtestResult;
  bool _loading = true;
  bool _backtesting = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final stats = await AgentService.instance.getPaperStats(widget.strategy.id);
    final trades = await AgentService.instance.getPaperTrades(widget.strategy.id);
    if (mounted) {
      setState(() {
        _stats = stats;
        _trades = trades;
        _loading = false;
      });
    }
  }

  Future<void> _runBacktest() async {
    setState(() => _backtesting = true);
    final result = await AgentService.instance.backtest(widget.strategy.id);
    if (mounted) {
      setState(() {
        _backtestResult = result;
        _backtesting = false;
      });
    }
  }

  Future<void> _switchToLive() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1A1F2E),
        title: const Text('切换到实盘', style: TextStyle(color: Colors.white)),
        content: const Text(
          '切换后将使用真实资金交易。\n模拟盘将继续运行作为对照。\n\n确认切换？',
          style: TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.orange),
            child: const Text('确认切换实盘'),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    final ok = await AgentService.instance.goLive(widget.strategy.id);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(ok ? '已切换到实盘' : '切换失败'),
        backgroundColor: ok ? Colors.green : Colors.red,
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strategy;
    final isPaper = s.status != 'live';
    final winRate = (_stats['win_rate'] as num?)?.toDouble() ?? 0;
    final totalPnl = (_stats['total_pnl_pct'] as num?)?.toDouble() ?? 0;
    final tradeCount = (_stats['trade_count'] as num?)?.toInt() ?? 0;

    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0D1117),
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: Colors.white, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(s.name, style: const TextStyle(color: Colors.white, fontSize: 16)),
        actions: [
          if (isPaper)
            TextButton.icon(
              onPressed: _switchToLive,
              icon: const Icon(Icons.rocket_launch, size: 16, color: Color(0xFF22C55E)),
              label: const Text('切换实盘', style: TextStyle(color: Color(0xFF22C55E), fontSize: 12)),
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  // Mode 标签
                  Row(children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: isPaper ? Colors.blue.withValues(alpha: 0.2) : Colors.green.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        isPaper ? '模拟盘' : '实盘',
                        style: TextStyle(color: isPaper ? Colors.blue : Colors.green, fontSize: 12, fontWeight: FontWeight.bold),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: s.status == 'active' ? Colors.green.withValues(alpha: 0.2) : Colors.grey.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        s.status == 'active' ? '运行中' : s.status == 'paused' ? '已暂停' : s.status,
                        style: TextStyle(color: s.status == 'active' ? Colors.green : Colors.grey, fontSize: 12),
                      ),
                    ),
                  ]),
                  const SizedBox(height: 16),

                  // 核心指标卡片
                  _buildStatsCard(winRate, totalPnl, tradeCount),
                  const SizedBox(height: 16),

                  // 回测按钮 + 结果
                  _buildBacktestCard(),
                  const SizedBox(height: 16),

                  // 交易记录
                  _buildTradesCard(),
                ],
              ),
            ),
    );
  }

  Widget _buildStatsCard(double winRate, double totalPnl, int tradeCount) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('表现统计', style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          Row(
            children: [
              _statItem('交易次数', '$tradeCount', Colors.white),
              _statItem('胜率', '${(winRate * 100).toStringAsFixed(1)}%', winRate >= 0.5 ? Colors.green : Colors.red),
              _statItem('累计PNL', '${totalPnl >= 0 ? "+" : ""}${totalPnl.toStringAsFixed(1)}%', totalPnl >= 0 ? Colors.green : Colors.red),
            ],
          ),
          if (_stats['sharpe'] != null || _stats['max_drawdown'] != null) ...[
            const SizedBox(height: 8),
            Row(
              children: [
                _statItem('夏普率', (_stats['sharpe'] as num?)?.toStringAsFixed(2) ?? '-', Colors.white70),
                _statItem('最大回撤', '${((_stats['max_drawdown'] as num?)?.toDouble() ?? 0).toStringAsFixed(1)}%', Colors.orange),
                _statItem('盈亏比', (_stats['profit_factor'] as num?)?.toStringAsFixed(1) ?? '-', Colors.white70),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _statItem(String label, String value, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text(value, style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text(label, style: const TextStyle(color: Colors.white38, fontSize: 11)),
        ],
      ),
    );
  }

  Widget _buildBacktestCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('回测验证', style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
              ElevatedButton.icon(
                onPressed: _backtesting ? null : _runBacktest,
                icon: _backtesting
                    ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.science, size: 16),
                label: Text(_backtesting ? '回测中...' : '运行回测', style: const TextStyle(fontSize: 12)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue.withValues(alpha: 0.3),
                  foregroundColor: Colors.blue,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
              ),
            ],
          ),
          if (_backtestResult != null && (_backtestResult!['trigger_count'] ?? _backtestResult!['triggers'] ?? 0) > 0) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                _statItem('触发', '${_backtestResult!['trigger_count'] ?? _backtestResult!['triggers'] ?? 0}次', Colors.white),
                _statItem('胜率', '${((_backtestResult!['simulated_win_rate'] ?? _backtestResult!['win_rate'] ?? 0) as num).toDouble() * 100 ~/ 1}%',
                    ((_backtestResult!['simulated_win_rate'] ?? _backtestResult!['win_rate'] ?? 0) as num).toDouble() >= 0.5 ? Colors.green : Colors.red),
                _statItem('收益', '${((_backtestResult!['avg_return_pct'] ?? _backtestResult!['total_pnl'] ?? 0) as num).toDouble() ~/ 1}%',
                    ((_backtestResult!['avg_return_pct'] ?? _backtestResult!['total_pnl'] ?? 0) as num).toDouble() >= 0 ? Colors.green : Colors.red),
              ],
            ),
            if (_backtestResult!['sample_triggers'] != null) ...[
              const SizedBox(height: 8),
              Text('样本：${(_backtestResult!['sample_triggers'] as List).take(3).map((t) => t['token'] ?? '').join(', ')}',
                  style: const TextStyle(color: Colors.white38, fontSize: 11)),
            ],
          ] else if (_backtestResult != null) ...[
            const SizedBox(height: 8),
            Text('过去 ${_backtestResult!['period_days'] ?? 7} 天未触发任何信号',
                style: const TextStyle(color: Colors.white38, fontSize: 13)),
          ],
        ],
      ),
    );
  }

  Widget _buildTradesCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('交易记录 (${_trades.length})', style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          if (_trades.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 20),
              child: Center(child: Text('暂无交易记录', style: TextStyle(color: Colors.white38, fontSize: 13))),
            )
          else
            ..._trades.take(20).map((t) {
              final pnl = (t['pnl_pct'] as num?)?.toDouble();
              final isWin = pnl != null && pnl > 0;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(
                  children: [
                    Icon(
                      t['side'] == 'buy' ? Icons.arrow_upward : Icons.arrow_downward,
                      color: t['side'] == 'buy' ? Colors.green : Colors.red,
                      size: 16,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${t['asset'] ?? '?'} ${t['side'] ?? ''} \$${(t['amount_usd'] as num?)?.toStringAsFixed(0) ?? '?'}',
                            style: const TextStyle(color: Colors.white, fontSize: 13),
                          ),
                          Text(
                            t['created_at']?.toString().substring(0, 16) ?? '',
                            style: const TextStyle(color: Colors.white38, fontSize: 11),
                          ),
                        ],
                      ),
                    ),
                    if (pnl != null)
                      Text(
                        '${pnl >= 0 ? "+" : ""}${pnl.toStringAsFixed(1)}%',
                        style: TextStyle(
                          color: isWin ? Colors.green : Colors.red,
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                        ),
                      )
                    else
                      Text(
                        t['status'] ?? 'open',
                        style: const TextStyle(color: Colors.white38, fontSize: 12),
                      ),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }
}
