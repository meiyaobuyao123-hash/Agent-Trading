import 'package:flutter/material.dart';
import '../../services/agent_service.dart';
import '../../services/wallet_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/wallet_import_sheet.dart';

/// 策略详情页 — 模拟盘表现 + 交易记录(paper+live)+ 回测 + 风控编辑 + 切换实盘(R42 P0.4/P0.5)
class StrategyDetailPage extends StatefulWidget {
  final AgentStrategy strategy;
  const StrategyDetailPage({super.key, required this.strategy});

  @override
  State<StrategyDetailPage> createState() => _StrategyDetailPageState();
}

class _StrategyDetailPageState extends State<StrategyDetailPage> {
  Map<String, dynamic> _stats = {};
  List<Map<String, dynamic>> _trades = [];
  int _paperCount = 0;
  int _liveCount = 0;
  Map<String, dynamic>? _backtestResult;
  bool _loading = true;
  bool _backtesting = false;
  bool _promoting = false;

  // R42 P0.5 risk_params 状态(从策略读 + 编辑)
  bool _showRiskSettings = false;
  late double _maxSlippagePct;     // 0.01 = 1%
  late double _stopLossPct;        // 0.30 = 30%
  late double _takeProfitPct;      // 1.00 = 100%
  late double _maxPositionUsd;
  late double _priorityFeeSol;
  late double _mevBribeSol;
  bool _riskDirty = false;

  // 当前策略本地副本(promote/demote 后刷新)
  late Map<String, dynamic> _strategyData;

  @override
  void initState() {
    super.initState();
    _strategyData = {
      'id': widget.strategy.id,
      'name': widget.strategy.name,
      'mode': widget.strategy.status == 'live' ? 'live' : 'paper',
      'status': widget.strategy.status,
    };
    _loadRiskParamsFromStrategy();
    _load();
  }

  void _loadRiskParamsFromStrategy() {
    // 从 strategy 字段读 risk_params(如果后端有);否则用默认
    _maxSlippagePct = 0.01;
    _stopLossPct = 0.30;
    _takeProfitPct = 1.00;
    _maxPositionUsd = 50;
    _priorityFeeSol = 0.0005;
    _mevBribeSol = 0.001;
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final stats = await AgentService.instance.getPaperStats(widget.strategy.id);
    final tradesResp = await AgentService.instance.getTradesMerged(widget.strategy.id);
    if (mounted) {
      setState(() {
        _stats = stats;
        _trades = (tradesResp['trades'] as List?)?.cast<Map<String, dynamic>>() ?? [];
        _paperCount = (tradesResp['paper_count'] as int?) ?? 0;
        _liveCount = (tradesResp['live_count'] as int?) ?? 0;
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

  Future<void> _saveRiskParams() async {
    final ok = await AgentService.instance.updateRiskParams(
      widget.strategy.id,
      maxSlippagePct: _maxSlippagePct,
      stopLossPct: _stopLossPct,
      takeProfitPct: _takeProfitPct,
      maxPositionUsd: _maxPositionUsd,
      priorityFeeSol: _priorityFeeSol,
      mevBribeSol: _mevBribeSol,
    );
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(ok ? '风控参数已保存' : '保存失败'),
        backgroundColor: ok ? Colors.green : Colors.red,
      ));
      if (ok) setState(() => _riskDirty = false);
    }
  }

  /// R42 P0.4 用户主动 promote → 弹出解锁条件 sheet
  Future<void> _promoteToLive() async {
    final c = context.colors;
    final wallets = WalletService.instance.wallets;
    bool hasWallet = wallets.isNotEmpty;
    bool disclaimerAccepted = false;
    bool riskAcknowledged = false;
    double maxPos = _maxPositionUsd.clamp(10, 500);

    final result = await showModalBottomSheet<bool>(
      context: context,
      backgroundColor: c.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheet) => Padding(
          padding: EdgeInsets.only(
            left: 20, right: 20, top: 16,
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.rocket_launch, color: c.warning, size: 22),
                  const SizedBox(width: 8),
                  Text('切换到实盘 — 真金交易',
                      style: TextStyle(color: c.textPrimary, fontSize: 17, fontWeight: FontWeight.w700)),
                ],
              ),
              const SizedBox(height: 4),
              Text('请确认以下 4 项,通过后立即生效',
                  style: TextStyle(color: c.textSecondary, fontSize: 12)),
              const SizedBox(height: 18),

              // 1. 钱包检查(自动)
              _checklistRow(
                c,
                checked: hasWallet,
                title: hasWallet ? '已连接钱包(${wallets.length} 个)' : '需先导入钱包',
                trailing: hasWallet
                    ? null
                    : TextButton(
                        onPressed: () async {
                          final w = await showWalletImportSheet(ctx);
                          if (w != null) setSheet(() => hasWallet = true);
                        },
                        child: const Text('导入'),
                      ),
              ),

              // 2. 免责声明
              CheckboxListTile(
                value: disclaimerAccepted,
                onChanged: (v) => setSheet(() => disclaimerAccepted = v ?? false),
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                activeColor: c.primary,
                title: Text('我已阅读并同意《免责声明》',
                    style: TextStyle(color: c.textPrimary, fontSize: 14)),
                subtitle: Text('加密货币交易具有高风险,可能导致全部本金损失',
                    style: TextStyle(color: c.textTertiary, fontSize: 11)),
              ),

              // 3. 风险确认
              CheckboxListTile(
                value: riskAcknowledged,
                onChanged: (v) => setSheet(() => riskAcknowledged = v ?? false),
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                activeColor: c.primary,
                title: Text('我知道实盘交易会用真钱,可能亏损',
                    style: TextStyle(color: c.textPrimary, fontSize: 14)),
              ),

              // 4. 单笔上限
              const SizedBox(height: 8),
              Text('单笔最大金额',
                  style: TextStyle(color: c.textSecondary, fontSize: 12, fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              Row(
                children: [
                  Expanded(
                    child: SliderTheme(
                      data: SliderThemeData(
                        trackHeight: 3,
                        thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 7),
                        activeTrackColor: c.primary,
                        inactiveTrackColor: c.border,
                      ),
                      child: Slider(
                        value: maxPos,
                        min: 10,
                        max: 500,
                        divisions: 49,
                        onChanged: (v) => setSheet(() => maxPos = v),
                      ),
                    ),
                  ),
                  Container(
                    width: 80,
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: c.surfaceAlt,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: c.border, width: 0.5),
                    ),
                    child: Text(
                      '\$${maxPos.toStringAsFixed(0)}',
                      textAlign: TextAlign.right,
                      style: TextStyle(color: c.primary, fontSize: 14, fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: (hasWallet && disclaimerAccepted && riskAcknowledged)
                      ? () => Navigator.pop(ctx, true)
                      : null,
                  style: FilledButton.styleFrom(
                    backgroundColor: c.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  child: Text(
                    '确认切换实盘 (\$${maxPos.toStringAsFixed(0)} 单笔上限)',
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                  ),
                ),
              ),
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: TextButton(
                  onPressed: () => Navigator.pop(ctx, false),
                  child: Text('取消', style: TextStyle(color: c.textTertiary)),
                ),
              ),
            ],
          ),
        ),
      ),
    );

    if (result != true) return;

    setState(() => _promoting = true);
    final resp = await AgentService.instance.promoteToLive(
      widget.strategy.id,
      hasWallet: hasWallet,
      disclaimerAccepted: disclaimerAccepted,
      riskAcknowledged: riskAcknowledged,
      maxPositionUsd: maxPos,
    );
    if (!mounted) return;
    setState(() => _promoting = false);

    final promoted = resp['promoted'] == true;
    if (promoted) {
      setState(() {
        _strategyData['mode'] = 'live';
        _maxPositionUsd = maxPos;
      });
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(resp['message']?.toString() ?? '已切换到实盘'),
        backgroundColor: Colors.green,
      ));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('切换失败: ${resp['error'] ?? resp['missing'] ?? '未知错误'}'),
        backgroundColor: Colors.red,
      ));
    }
  }

  Future<void> _demoteToPaper() async {
    final c = context.colors;
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: c.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text('降回模拟盘?', style: TextStyle(color: c.textPrimary)),
        content: Text(
          '降回后策略将停止真金交易,改为模拟盘运行。已有持仓的止盈止损继续生效。',
          style: TextStyle(color: c.textSecondary, fontSize: 13),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: Text('取消', style: TextStyle(color: c.textTertiary))),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(backgroundColor: c.warning),
            child: const Text('确认降回'),
          ),
        ],
      ),
    );
    if (confirm != true) return;

    final ok = await AgentService.instance.demoteToPaper(widget.strategy.id);
    if (mounted) {
      if (ok) setState(() => _strategyData['mode'] = 'paper');
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(ok ? '已降回模拟盘' : '降级失败'),
        backgroundColor: ok ? Colors.green : Colors.red,
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final s = widget.strategy;
    final isLive = _strategyData['mode'] == 'live';
    final winRate = (_stats['win_rate'] as num?)?.toDouble() ?? 0;
    final totalPnl = (_stats['total_pnl_pct'] as num?)?.toDouble() ?? 0;
    final tradeCount = (_stats['trade_count'] as num?)?.toInt() ?? 0;

    return Scaffold(
      backgroundColor: c.surfaceAlt,
      appBar: AppBar(
        backgroundColor: c.surfaceAlt,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_ios, color: c.textPrimary, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(s.name, style: TextStyle(color: c.textPrimary, fontSize: 16)),
        actions: [
          if (!isLive)
            TextButton.icon(
              onPressed: _promoting ? null : _promoteToLive,
              icon: _promoting
                  ? SizedBox(width: 14, height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2, color: c.success))
                  : Icon(Icons.rocket_launch, size: 16, color: c.success),
              label: Text('切实盘', style: TextStyle(color: c.success, fontSize: 13, fontWeight: FontWeight.w600)),
            )
          else
            TextButton.icon(
              onPressed: _demoteToPaper,
              icon: Icon(Icons.science, size: 16, color: c.warning),
              label: Text('回模拟', style: TextStyle(color: c.warning, fontSize: 13, fontWeight: FontWeight.w600)),
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
                  _buildModeBadges(c, isLive, s.status),
                  const SizedBox(height: 16),
                  _buildStatsCard(c, winRate, totalPnl, tradeCount),
                  const SizedBox(height: 16),
                  _buildRiskSettingsCard(c),  // R42 P0.5 风控编辑
                  const SizedBox(height: 16),
                  _buildBacktestCard(c),
                  const SizedBox(height: 16),
                  _buildTradesCard(c),
                ],
              ),
            ),
    );
  }

  Widget _buildModeBadges(AppColorScheme c, bool isLive, String status) {
    return Row(children: [
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: isLive ? c.danger.withValues(alpha: 0.15) : c.primary.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(isLive ? Icons.attach_money : Icons.science,
              size: 12, color: isLive ? c.danger : c.primary),
          const SizedBox(width: 4),
          Text(isLive ? '实盘' : '模拟盘',
              style: TextStyle(color: isLive ? c.danger : c.primary,
                  fontSize: 12, fontWeight: FontWeight.w700)),
        ]),
      ),
      const SizedBox(width: 8),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: status == 'active' ? c.success.withValues(alpha: 0.15) : c.textTertiary.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          status == 'active' ? '运行中' : status == 'paused' ? '已暂停' : status,
          style: TextStyle(color: status == 'active' ? c.success : c.textTertiary, fontSize: 12),
        ),
      ),
    ]);
  }

  Widget _buildStatsCard(AppColorScheme c, double winRate, double totalPnl, int tradeCount) {
    return _card(c,
      title: '表现统计',
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          _statItem(c, '交易次数', '$tradeCount', c.textPrimary),
          _statItem(c, '胜率', '${(winRate * 100).toStringAsFixed(1)}%',
              winRate >= 0.5 ? c.success : c.danger),
          _statItem(c, '累计PNL', '${totalPnl >= 0 ? "+" : ""}${totalPnl.toStringAsFixed(1)}%',
              totalPnl >= 0 ? c.success : c.danger),
        ]),
        if (_stats['sharpe'] != null || _stats['max_drawdown'] != null) ...[
          const SizedBox(height: 12),
          Row(children: [
            _statItem(c, '夏普率', (_stats['sharpe'] as num?)?.toStringAsFixed(2) ?? '-', c.textSecondary),
            _statItem(c, '最大回撤', '${((_stats['max_drawdown'] as num?)?.toDouble() ?? 0).toStringAsFixed(1)}%', c.warning),
            _statItem(c, '盈亏比', (_stats['profit_factor'] as num?)?.toStringAsFixed(1) ?? '-', c.textSecondary),
          ]),
        ],
      ]),
    );
  }

  Widget _statItem(AppColorScheme c, String label, String value, Color color) {
    return Expanded(child: Column(children: [
      Text(value, style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.bold)),
      const SizedBox(height: 4),
      Text(label, style: TextStyle(color: c.textTertiary, fontSize: 11)),
    ]));
  }

  /// R42 P0.5 风控编辑卡片
  Widget _buildRiskSettingsCard(AppColorScheme c) {
    return _card(c,
      title: '风控设置',
      headerTrailing: IconButton(
        icon: Icon(_showRiskSettings ? Icons.expand_less : Icons.expand_more,
            color: c.textSecondary, size: 22),
        onPressed: () => setState(() => _showRiskSettings = !_showRiskSettings),
      ),
      child: _showRiskSettings
          ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              _riskSlider(c, '单笔金额', _maxPositionUsd, 10, 1000, '\$',
                  (v) => setState(() { _maxPositionUsd = v; _riskDirty = true; })),
              _riskSlider(c, '滑点容忍', _maxSlippagePct * 100, 0.5, 5, '%',
                  (v) => setState(() { _maxSlippagePct = v / 100; _riskDirty = true; })),
              _riskSlider(c, '止损', _stopLossPct * 100, 5, 50, '%',
                  (v) => setState(() { _stopLossPct = v / 100; _riskDirty = true; })),
              _riskSlider(c, '止盈', _takeProfitPct * 100, 10, 1000, '%',
                  (v) => setState(() { _takeProfitPct = v / 100; _riskDirty = true; })),
              const SizedBox(height: 4),
              Padding(
                padding: const EdgeInsets.only(top: 6, bottom: 4),
                child: Text('交易速度(影响成交速度 + 防三明治攻击)',
                    style: TextStyle(color: c.textSecondary, fontSize: 11, fontWeight: FontWeight.w600)),
              ),
              _speedPresets(c),
              if (_riskDirty)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _saveRiskParams,
                      style: FilledButton.styleFrom(
                        backgroundColor: c.primary,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                      child: const Text('保存修改', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                    ),
                  ),
                ),
            ])
          : Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(children: [
                _riskSummary(c, '单笔', '\$${_maxPositionUsd.toStringAsFixed(0)}'),
                _riskSummary(c, '滑点', '${(_maxSlippagePct * 100).toStringAsFixed(1)}%'),
                _riskSummary(c, '止损', '${(_stopLossPct * 100).toStringAsFixed(0)}%'),
                _riskSummary(c, '止盈', '${(_takeProfitPct * 100).toStringAsFixed(0)}%'),
              ]),
            ),
    );
  }

  Widget _riskSummary(AppColorScheme c, String label, String value) {
    return Expanded(child: Column(children: [
      Text(value, style: TextStyle(color: c.primary, fontSize: 14, fontWeight: FontWeight.w700)),
      Text(label, style: TextStyle(color: c.textTertiary, fontSize: 10)),
    ]));
  }

  Widget _riskSlider(AppColorScheme c, String label, double value,
      double min, double max, String unit, ValueChanged<double> onChanged) {
    final isMoneyOrPct = unit == '\$' || unit == '%';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        SizedBox(width: 64,
            child: Text(label, style: TextStyle(color: c.textSecondary, fontSize: 12, fontWeight: FontWeight.w500))),
        Expanded(
          child: SliderTheme(
            data: SliderThemeData(
              trackHeight: 3,
              thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 7),
              activeTrackColor: c.primary,
              inactiveTrackColor: c.border,
            ),
            child: Slider(
              value: value.clamp(min, max),
              min: min, max: max,
              onChanged: onChanged,
            ),
          ),
        ),
        Container(
          width: 78,
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
          decoration: BoxDecoration(
            color: c.surfaceAlt,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: c.border, width: 0.5),
          ),
          child: Text(
            isMoneyOrPct
                ? (unit == '\$' ? '\$${value.toStringAsFixed(0)}' : '${value.toStringAsFixed(value < 1 ? 1 : 0)}$unit')
                : '${value.toStringAsFixed(4)}$unit',
            textAlign: TextAlign.right,
            style: TextStyle(color: c.primary, fontSize: 13, fontWeight: FontWeight.w700),
          ),
        ),
      ]),
    );
  }

  Widget _speedPresets(AppColorScheme c) {
    int active = 1;  // 默认标准
    if (_priorityFeeSol >= 0.005) {
      active = 2;
    } else if (_priorityFeeSol < 0.0003 && _mevBribeSol == 0) {
      active = 0;
    }
    return Row(children: [
      _presetButton(c, '经济', '0.0001 + 0', 0, active == 0, () {
        setState(() { _priorityFeeSol = 0.0001; _mevBribeSol = 0; _riskDirty = true; });
      }),
      const SizedBox(width: 6),
      _presetButton(c, '标准', '0.0005 + 0.001', 1, active == 1, () {
        setState(() { _priorityFeeSol = 0.0005; _mevBribeSol = 0.001; _riskDirty = true; });
      }),
      const SizedBox(width: 6),
      _presetButton(c, '极速', '0.005 + 0.005', 2, active == 2, () {
        setState(() { _priorityFeeSol = 0.005; _mevBribeSol = 0.005; _riskDirty = true; });
      }),
    ]);
  }

  Widget _presetButton(AppColorScheme c, String name, String detail, int idx, bool active, VoidCallback onTap) {
    return Expanded(
      child: Material(color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 10),
            decoration: BoxDecoration(
              color: active ? c.primary.withValues(alpha: 0.15) : c.surfaceAlt,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: active ? c.primary : c.border, width: active ? 1.2 : 0.5),
            ),
            child: Column(children: [
              Text(name,
                  style: TextStyle(color: active ? c.primary : c.textPrimary, fontSize: 13, fontWeight: FontWeight.w700)),
              const SizedBox(height: 2),
              Text(detail, style: TextStyle(color: c.textTertiary, fontSize: 9)),
            ]),
          ),
        ),
      ),
    );
  }

  Widget _buildBacktestCard(AppColorScheme c) {
    return _card(c,
      title: '回测验证',
      headerTrailing: FilledButton.icon(
        onPressed: _backtesting ? null : _runBacktest,
        icon: _backtesting
            ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
            : const Icon(Icons.science, size: 16),
        label: Text(_backtesting ? '回测中...' : '运行回测', style: const TextStyle(fontSize: 12)),
        style: FilledButton.styleFrom(
          backgroundColor: c.primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
      ),
      child: _backtestResult == null
          ? Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Text('点击右侧"运行回测"查看 7 天历史回测结果',
                  style: TextStyle(color: c.textTertiary, fontSize: 12)),
            )
          : (_backtestResult!['trigger_count'] ?? _backtestResult!['triggers'] ?? 0) > 0
              ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    _statItem(c, '触发', '${_backtestResult!['trigger_count'] ?? _backtestResult!['triggers'] ?? 0}次', c.textPrimary),
                    _statItem(c, '胜率',
                        '${((_backtestResult!['simulated_win_rate'] ?? _backtestResult!['win_rate'] ?? 0) as num).toDouble() * 100 ~/ 1}%',
                        ((_backtestResult!['simulated_win_rate'] ?? _backtestResult!['win_rate'] ?? 0) as num).toDouble() >= 0.5 ? c.success : c.danger),
                    _statItem(c, '收益',
                        '${((_backtestResult!['avg_return_pct'] ?? _backtestResult!['total_pnl'] ?? 0) as num).toDouble() ~/ 1}%',
                        ((_backtestResult!['avg_return_pct'] ?? _backtestResult!['total_pnl'] ?? 0) as num).toDouble() >= 0 ? c.success : c.danger),
                  ]),
                  if (_backtestResult!['sample_triggers'] != null) ...[
                    const SizedBox(height: 8),
                    Text('样本:${(_backtestResult!['sample_triggers'] as List).take(3).map((t) => t['token'] ?? '').join(', ')}',
                        style: TextStyle(color: c.textTertiary, fontSize: 11)),
                  ],
                ])
              : Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Text('过去 ${_backtestResult!['period_days'] ?? 7} 天未触发任何信号',
                      style: TextStyle(color: c.textTertiary, fontSize: 13)),
                ),
    );
  }

  Widget _buildTradesCard(AppColorScheme c) {
    return _card(c,
      title: '交易记录 ($_paperCount 模拟 + $_liveCount 实盘 = ${_trades.length})',
      child: _trades.isEmpty
          ? Padding(
              padding: const EdgeInsets.symmetric(vertical: 20),
              child: Center(child: Text('暂无交易记录', style: TextStyle(color: c.textTertiary, fontSize: 13))),
            )
          : Column(children: _trades.take(20).map((t) {
              final pnl = (t['pnl_pct'] as num?)?.toDouble();
              final isWin = pnl != null && pnl > 0;
              final isLive = (t['mode'] ?? 'paper') == 'live';
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(children: [
                  // mode 标签
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                    decoration: BoxDecoration(
                      color: (isLive ? c.danger : c.primary).withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      isLive ? '实' : '模',
                      style: TextStyle(color: isLive ? c.danger : c.primary, fontSize: 9, fontWeight: FontWeight.w700),
                    ),
                  ),
                  const SizedBox(width: 6),
                  Icon(
                    t['side'] == 'buy' ? Icons.arrow_upward : Icons.arrow_downward,
                    color: t['side'] == 'buy' ? c.success : c.danger,
                    size: 16,
                  ),
                  const SizedBox(width: 6),
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(
                      '${t['asset'] ?? '?'} ${t['side'] ?? ''} \$${(t['amount_usd'] as num?)?.toStringAsFixed(0) ?? '?'}',
                      style: TextStyle(color: c.textPrimary, fontSize: 13),
                    ),
                    Text(
                      t['created_at']?.toString().substring(0, 16) ?? '',
                      style: TextStyle(color: c.textTertiary, fontSize: 11),
                    ),
                  ])),
                  if (pnl != null)
                    Text(
                      '${pnl >= 0 ? "+" : ""}${pnl.toStringAsFixed(1)}%',
                      style: TextStyle(color: isWin ? c.success : c.danger, fontSize: 14, fontWeight: FontWeight.bold),
                    )
                  else
                    Text(t['status']?.toString() ?? 'open',
                        style: TextStyle(color: c.textTertiary, fontSize: 12)),
                ]),
              );
            }).toList()),
    );
  }

  Widget _card(AppColorScheme c, {required String title, Widget? headerTrailing, required Widget child}) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: c.border, width: 0.5),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text(title, style: TextStyle(color: c.textPrimary, fontSize: 15, fontWeight: FontWeight.bold)),
          if (headerTrailing != null) headerTrailing,
        ]),
        const SizedBox(height: 10),
        child,
      ]),
    );
  }

  Widget _checklistRow(AppColorScheme c, {required bool checked, required String title, Widget? trailing}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(children: [
        Icon(checked ? Icons.check_circle : Icons.radio_button_unchecked,
            color: checked ? c.success : c.textTertiary, size: 20),
        const SizedBox(width: 10),
        Expanded(child: Text(title, style: TextStyle(color: c.textPrimary, fontSize: 14))),
        if (trailing != null) trailing,
      ]),
    );
  }
}
