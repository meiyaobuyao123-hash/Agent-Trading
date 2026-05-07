import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../services/credit_service.dart';
import '../../theme/app_colors.dart';

/// R47 — Flutter Credit 算力页
///
/// 三大块:
///   1. 余额卡(balance / total_recharged / total_consumed / 估算)
///   2. 快速充值按钮(弹 RechargeSheet)
///   3. 充值订单 + 交易历史 tab 切换
class CreditPage extends StatefulWidget {
  const CreditPage({super.key});

  @override
  State<CreditPage> createState() => _CreditPageState();
}

class _CreditPageState extends State<CreditPage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  CreditBalance? _balance;
  List<RechargeOrder> _orders = const [];
  List<CreditTransaction> _txs = const [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _refresh();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    setState(() => _loading = true);
    final results = await Future.wait([
      CreditService.instance.fetchBalance(),
      CreditService.instance.listRechargeOrders(limit: 10),
      CreditService.instance.listTransactions(limit: 30),
    ]);
    if (!mounted) return;
    setState(() {
      _balance = results[0] as CreditBalance?;
      _orders = results[1] as List<RechargeOrder>;
      _txs = results[2] as List<CreditTransaction>;
      _loading = false;
    });
  }

  Future<void> _openRecharge() async {
    final newOrder = await showModalBottomSheet<RechargeOrder>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const RechargeSheet(),
    );
    if (newOrder != null && mounted) {
      // 弹 PayDialog
      await showDialog<void>(
        context: context,
        builder: (_) => PayDialog(order: newOrder),
      );
      _refresh();
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final bal = _balance?.balanceUsd ?? 0;
    final lowBal = bal > 0 && bal < 0.1;
    final zeroBal = bal <= 0 && (_balance?.hasAccount ?? false);

    return Scaffold(
      backgroundColor: c.bg,
      appBar: AppBar(
        backgroundColor: c.bg,
        elevation: 0,
        title: Text('算力余额', style: TextStyle(color: c.textPrimary, fontSize: 17, fontWeight: FontWeight.w600)),
        iconTheme: IconThemeData(color: c.textPrimary),
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: _loading && _balance == null
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  // 余额卡
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: zeroBal
                            ? [const Color(0x33EF4444), const Color(0x11EF4444)]
                            : lowBal
                                ? [const Color(0x33F59E0B), const Color(0x11F59E0B)]
                                : [c.surface, c.surfaceAlt],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: c.border),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(children: [
                          const Icon(CupertinoIcons.bolt_fill, color: Color(0xFF3C82F6), size: 16),
                          const SizedBox(width: 6),
                          Text('当前余额', style: TextStyle(color: c.textTertiary, fontSize: 12)),
                        ]),
                        const SizedBox(height: 6),
                        Text(
                          '\$${bal.toStringAsFixed(4)}',
                          style: TextStyle(
                            color: zeroBal
                                ? const Color(0xFFEF4444)
                                : lowBal
                                    ? const Color(0xFFF59E0B)
                                    : c.textPrimary,
                            fontSize: 36,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        Text(
                          '约 ${_balance?.estimatedMessagesLeft ?? 0} 次询问',
                          style: TextStyle(color: c.textTertiary, fontSize: 12),
                        ),
                        const SizedBox(height: 16),
                        Row(
                          children: [
                            Expanded(
                              child: _MiniStat(
                                label: '累计充值',
                                value: '\$${_balance?.totalRecharged.toStringAsFixed(2) ?? "0.00"}',
                                icon: CupertinoIcons.arrow_up_circle,
                                color: const Color(0xFF22C55E),
                              ),
                            ),
                            Container(width: 1, height: 28, color: c.border),
                            Expanded(
                              child: _MiniStat(
                                label: '累计消费',
                                value: '\$${_balance?.totalConsumed.toStringAsFixed(4) ?? "0.0000"}',
                                icon: CupertinoIcons.arrow_down_circle,
                                color: const Color(0xFFEF4444),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        Material(
                          color: Colors.transparent,
                          child: InkWell(
                            borderRadius: BorderRadius.circular(10),
                            onTap: _openRecharge,
                            child: Container(
                              height: 44,
                              decoration: BoxDecoration(
                                color: const Color(0xFF3C82F6),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: const Center(
                                child: Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Icon(CupertinoIcons.add, color: Colors.white, size: 14),
                                    SizedBox(width: 6),
                                    Text('充值算力',
                                        style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600)),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  if (zeroBal) ...[
                    const SizedBox(height: 12),
                    _Hint(
                      icon: CupertinoIcons.exclamationmark_circle,
                      color: const Color(0xFFEF4444),
                      text: '余额已耗尽 — 充值后才能继续 AI 询问',
                    ),
                  ] else if (lowBal) ...[
                    const SizedBox(height: 12),
                    _Hint(
                      icon: CupertinoIcons.clock,
                      color: const Color(0xFFF59E0B),
                      text: '余额较低 — 建议尽快充值避免询问中断',
                    ),
                  ],

                  const SizedBox(height: 24),
                  // Tab
                  Container(
                    decoration: BoxDecoration(
                      color: c.surface,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: TabBar(
                      controller: _tabController,
                      indicatorColor: c.primary,
                      labelColor: c.textPrimary,
                      unselectedLabelColor: c.textTertiary,
                      labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                      tabs: const [
                        Tab(text: '充值订单'),
                        Tab(text: '交易历史'),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    height: 360,
                    child: TabBarView(
                      controller: _tabController,
                      children: [
                        _OrderList(orders: _orders, onTap: (o) async {
                          if (o.status == 'pending') {
                            await showDialog<void>(
                              context: context,
                              builder: (_) => PayDialog(order: o),
                            );
                            _refresh();
                          }
                        }),
                        _TxList(txs: _txs),
                      ],
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;
  const _MiniStat({required this.label, required this.value, required this.icon, required this.color});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, color: color, size: 11),
            const SizedBox(width: 4),
            Text(label, style: TextStyle(color: c.textTertiary, fontSize: 11)),
          ]),
          const SizedBox(height: 2),
          Text(value, style: TextStyle(color: c.textPrimary, fontSize: 14, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

class _Hint extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String text;
  const _Hint({required this.icon, required this.color, required this.text});

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Icon(icon, color: color, size: 14),
      const SizedBox(width: 8),
      Expanded(child: Text(text, style: TextStyle(color: color, fontSize: 12))),
    ]);
  }
}

class _OrderList extends StatelessWidget {
  final List<RechargeOrder> orders;
  final ValueChanged<RechargeOrder> onTap;
  const _OrderList({required this.orders, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    if (orders.isEmpty) {
      return Center(child: Text('暂无充值订单', style: TextStyle(color: c.textTertiary, fontSize: 13)));
    }
    return ListView.separated(
      itemCount: orders.length,
      separatorBuilder: (_, __) => Divider(color: c.border, height: 1),
      itemBuilder: (_, i) {
        final o = orders[i];
        final pending = o.status == 'pending';
        final confirmed = o.status == 'confirmed';
        final color = confirmed
            ? const Color(0xFF22C55E)
            : pending
                ? const Color(0xFFF59E0B)
                : c.textTertiary;
        final statusText = confirmed
            ? '已到账'
            : pending
                ? '待付款'
                : (o.status == 'expired' ? '已过期' : o.status);
        return ListTile(
          dense: true,
          onTap: pending ? () => onTap(o) : null,
          leading: Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              confirmed
                  ? CupertinoIcons.check_mark
                  : pending
                      ? CupertinoIcons.clock
                      : CupertinoIcons.xmark,
              color: color,
              size: 14,
            ),
          ),
          title: Text(
            '\$${double.tryParse(o.amountBase)?.toStringAsFixed(2) ?? "0"} ${o.chain.toUpperCase()}',
            style: TextStyle(color: c.textPrimary, fontSize: 14, fontWeight: FontWeight.w600),
          ),
          subtitle: Text(
            o.createdAt?.replaceAll('T', ' ').split('.').first ?? '',
            style: TextStyle(color: c.textTertiary, fontSize: 11),
          ),
          trailing: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(statusText, style: TextStyle(color: color, fontSize: 11)),
          ),
        );
      },
    );
  }
}

class _TxList extends StatelessWidget {
  final List<CreditTransaction> txs;
  const _TxList({required this.txs});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    if (txs.isEmpty) {
      return Center(child: Text('暂无交易记录', style: TextStyle(color: c.textTertiary, fontSize: 13)));
    }
    return ListView.separated(
      itemCount: txs.length,
      separatorBuilder: (_, __) => Divider(color: c.border, height: 1),
      itemBuilder: (_, i) {
        final t = txs[i];
        final isConsume = t.type == 'consume';
        final isRecharge = t.type == 'recharge';
        final color = isConsume ? const Color(0xFFEF4444) : const Color(0xFF22C55E);
        final title = isConsume
            ? 'AI 询问消费'
            : isRecharge
                ? '充值到账'
                : (t.type == 'adjust' ? '余额调整' : '退款');
        final dec = t.amountUsd.abs();
        final precision = dec < 1 && dec > 0 ? 6 : 2;
        return ListTile(
          dense: true,
          leading: Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              isConsume ? CupertinoIcons.bolt : CupertinoIcons.arrow_up,
              color: color,
              size: 14,
            ),
          ),
          title: Text(title, style: TextStyle(color: c.textPrimary, fontSize: 13, fontWeight: FontWeight.w600)),
          subtitle: Text(
            isConsume && t.model != null
                ? '${t.ts.replaceAll("T", " ").split(".").first} · ${t.model!.replaceAll("claude-", "")} · ${t.tokensIn ?? 0}/${t.tokensOut ?? 0}'
                : t.ts.replaceAll("T", " ").split(".").first,
            style: TextStyle(color: c.textTertiary, fontSize: 10),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          trailing: Text(
            '${t.amountUsd >= 0 ? "+" : ""}\$${t.amountUsd.toStringAsFixed(precision)}',
            style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w600),
          ),
        );
      },
    );
  }
}

// ─────────────────────────────────────────────────────────
// 充值 Sheet
// ─────────────────────────────────────────────────────────

class _ChainOpt {
  final String id;
  final String label;
  final String sub;
  final String tokenStd;
  final String emoji;
  const _ChainOpt(this.id, this.label, this.sub, this.tokenStd, this.emoji);
}

const _CHAINS = [
  _ChainOpt('solana', 'Solana', '确认 ~30 秒', 'USDC SPL', '🌟'),
  _ChainOpt('base', 'Base', '确认 ~30 秒', 'USDC ERC-20', '🔷'),
  _ChainOpt('ethereum', 'Ethereum', '确认 1-2 分钟', 'USDC ERC-20', '💠'),
  _ChainOpt('bsc', 'BSC', '确认 ~10 秒', 'USDC BEP-20', '💎'),
];

const _PRESETS = [10, 50, 100, 500];

class RechargeSheet extends StatefulWidget {
  const RechargeSheet({super.key});

  @override
  State<RechargeSheet> createState() => _RechargeSheetState();
}

class _RechargeSheetState extends State<RechargeSheet> {
  String _chain = 'solana';
  final _customCtrl = TextEditingController();
  bool _creating = false;
  String? _err;

  @override
  void dispose() {
    _customCtrl.dispose();
    super.dispose();
  }

  Future<void> _create(int amount) async {
    setState(() {
      _creating = true;
      _err = null;
    });
    final order = await CreditService.instance.createRechargeOrder(_chain, amount);
    if (!mounted) return;
    setState(() => _creating = false);
    if (order == null) {
      setState(() => _err = '创建订单失败,请检查余额或网络');
      return;
    }
    Navigator.of(context).pop(order);
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final selected = _CHAINS.firstWhere((x) => x.id == _chain);
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.8,
      maxChildSize: 0.9,
      minChildSize: 0.5,
      builder: (_, scroll) => Container(
        decoration: BoxDecoration(
          color: c.bg,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.all(20),
        child: ListView(
          controller: scroll,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: c.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            Text('充值算力',
                style: TextStyle(color: c.textPrimary, fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            Text('USDC 链上充值 · 充值后立即可用 · 余额永不过期',
                style: TextStyle(color: c.textTertiary, fontSize: 12)),
            const SizedBox(height: 18),
            Text('1. 选择链', style: TextStyle(color: c.textSecondary, fontSize: 12, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: 2,
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              childAspectRatio: 2.7,
              children: _CHAINS.map((opt) {
                final active = opt.id == _chain;
                return GestureDetector(
                  onTap: _creating ? null : () => setState(() => _chain = opt.id),
                  child: Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: active ? const Color(0xFF3C82F6) : c.surface,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: active ? const Color(0xFF3C82F6) : c.border),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Row(children: [
                          Text(opt.emoji, style: const TextStyle(fontSize: 16)),
                          const SizedBox(width: 6),
                          Text(opt.label,
                              style: TextStyle(
                                color: active ? Colors.white : c.textPrimary,
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                              )),
                        ]),
                        const SizedBox(height: 2),
                        Text(opt.tokenStd,
                            style: TextStyle(
                              color: active ? Colors.white.withValues(alpha: 0.85) : c.textTertiary,
                              fontSize: 10,
                            )),
                        Text(opt.sub,
                            style: TextStyle(
                              color: active ? Colors.white.withValues(alpha: 0.85) : c.textTertiary,
                              fontSize: 10,
                            )),
                      ],
                    ),
                  ),
                );
              }).toList(),
            ),

            const SizedBox(height: 16),
            Text('2. 选择金额', style: TextStyle(color: c.textSecondary, fontSize: 12, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: 2,
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              childAspectRatio: 2.5,
              children: _PRESETS
                  .map((amt) => GestureDetector(
                        onTap: _creating ? null : () => _create(amt),
                        child: Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: c.surface,
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(color: c.border),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text('\$$amt',
                                  style: TextStyle(color: c.textPrimary, fontSize: 18, fontWeight: FontWeight.w700)),
                              Text('约 ${(amt * 144)} 次询问',
                                  style: TextStyle(color: c.textTertiary, fontSize: 11)),
                            ],
                          ),
                        ),
                      ))
                  .toList(),
            ),

            const SizedBox(height: 12),
            Row(children: [
              Expanded(
                child: TextField(
                  controller: _customCtrl,
                  keyboardType: TextInputType.number,
                  style: TextStyle(color: c.textPrimary, fontSize: 14),
                  decoration: InputDecoration(
                    hintText: '自定义金额(USD)',
                    hintStyle: TextStyle(color: c.textTertiary, fontSize: 13),
                    filled: true,
                    fillColor: c.surface,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide(color: c.border),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide(color: c.border),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              ElevatedButton(
                onPressed: _creating
                    ? null
                    : () {
                        final n = int.tryParse(_customCtrl.text.trim());
                        if (n != null && n >= 1 && n <= 10000) _create(n);
                      },
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF3C82F6),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                child: Text(_creating ? '...' : '充值 ${selected.label}'),
              ),
            ]),

            if (_err != null) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0x1FEF4444),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(_err!, style: const TextStyle(color: Color(0xFFEF4444), fontSize: 12)),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// 待付款 Dialog(显示地址 + 金额 + QR)
// ─────────────────────────────────────────────────────────

class PayDialog extends StatelessWidget {
  final RechargeOrder order;
  const PayDialog({super.key, required this.order});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final tokenStd = order.chain == 'solana'
        ? 'USDC SPL'
        : order.chain == 'bsc'
            ? 'USDC BEP-20'
            : 'USDC ERC-20';
    final qrData = order.address; // 第一版只编码地址(钱包扫码后用户手输金额)
    return Dialog(
      backgroundColor: c.bg,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 360),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                const Icon(CupertinoIcons.clock, color: Color(0xFFF59E0B), size: 18),
                const SizedBox(width: 8),
                Text('待付款',
                    style: TextStyle(color: c.textPrimary, fontSize: 16, fontWeight: FontWeight.w700)),
                const Spacer(),
                IconButton(
                  icon: Icon(CupertinoIcons.xmark, color: c.textTertiary, size: 18),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ]),
              const SizedBox(height: 8),
              Text('请在 30 分钟内完成转账,过期需重新创建订单',
                  style: TextStyle(color: c.textTertiary, fontSize: 11)),
              const SizedBox(height: 16),

              // QR
              Center(
                child: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: QrImageView(
                    data: qrData,
                    size: 160,
                    version: QrVersions.auto,
                    backgroundColor: Colors.white,
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // 精确金额
              Text('转账精确金额(必须完全一致)',
                  style: TextStyle(color: c.textSecondary, fontSize: 11)),
              const SizedBox(height: 4),
              _CopyRow(
                value: '\$${order.amountExact} USDC',
                copyValue: order.amountExact,
                strong: true,
              ),
              Text('零头 \$${order.amountNonce} 用于唯一识别您的转账',
                  style: TextStyle(color: c.textTertiary, fontSize: 10)),
              const SizedBox(height: 12),

              // 地址
              Text('收款地址(${order.chain.toUpperCase()} · $tokenStd)',
                  style: TextStyle(color: c.textSecondary, fontSize: 11)),
              const SizedBox(height: 4),
              _CopyRow(value: order.address, copyValue: order.address),

              const SizedBox(height: 14),
              ...['• 从你的 USDC 钱包发送(精确到 6 位小数)',
                  '• 少一分钱将无法识别',
                  '• 到账后 60 秒内自动加余额'].map((t) => Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(t, style: TextStyle(color: c.textTertiary, fontSize: 11)),
                  )),
            ],
          ),
        ),
      ),
    );
  }
}

class _CopyRow extends StatelessWidget {
  final String value;
  final String copyValue;
  final bool strong;
  const _CopyRow({required this.value, required this.copyValue, this.strong = false});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return GestureDetector(
      onTap: () {
        Clipboard.setData(ClipboardData(text: copyValue));
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('已复制'), duration: Duration(seconds: 1)),
        );
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: c.surface,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: strong ? const Color(0x66F59E0B) : c.border),
        ),
        child: Row(children: [
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                color: strong ? const Color(0xFFF59E0B) : c.textPrimary,
                fontSize: strong ? 14 : 11,
                fontWeight: strong ? FontWeight.w700 : FontWeight.w500,
                fontFamily: 'monospace',
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Icon(CupertinoIcons.doc_on_doc, color: c.textTertiary, size: 14),
        ]),
      ),
    );
  }
}
