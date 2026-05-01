// HITL 审批详情页 — W3 D4
// 引用 docs/agent-pm/03-prd.md §1.4 HITL 触发条件
// 引用 docs/agent-pm/05-tool-catalog.md T09 create_approval_request
// 引用 lib/models/pending_approval.dart
// 引用 lib/widgets/agent/thesis_card.dart
//
// 用户在策略 Tab / 推送通知 deep link 进来,
// 看到完整审批信息(策略 + 条件 + thesis + 风险 + 金额),
// approve(Face ID 占位 → 真实施 W4-W6 接 local_auth)/ reject(确认对话)。

import 'dart:async';
import 'package:flutter/material.dart';

import '../../models/pending_approval.dart';
import '../../models/thesis.dart';
import '../../services/agent_service.dart';
import '../../widgets/agent/thesis_card.dart';

class HitlApprovalPage extends StatefulWidget {
  final PendingApproval approval;
  final Thesis? thesis;

  const HitlApprovalPage({
    super.key,
    required this.approval,
    this.thesis,
  });

  @override
  State<HitlApprovalPage> createState() => _HitlApprovalPageState();
}

class _HitlApprovalPageState extends State<HitlApprovalPage> {
  Timer? _ticker;
  Duration _remaining = Duration.zero;
  bool _processing = false;
  String? _resultMsg;

  @override
  void initState() {
    super.initState();
    _remaining = widget.approval.remaining;
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() {
        _remaining = widget.approval.remaining;
      });
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  Future<void> _approve() async {
    if (_processing) return;
    // 简化版生物认证 → 弹输入框模拟签名(真实施 W4-W6 接 local_auth + wallet sig)
    final sig = await _promptForSignature();
    if (sig == null || sig.isEmpty) return;

    setState(() => _processing = true);
    final result = await AgentService.instance.approvePendingApproval(
      widget.approval.approvalId,
      signature: sig,
    );
    if (!mounted) return;
    setState(() {
      _processing = false;
      _resultMsg = result != null
          ? '✅ 已批准${result['tx_hash'] != null ? "(tx ${result['tx_hash']})" : ""}'
          : '❌ 批准失败,请重试';
    });
    if (result != null) {
      await Future.delayed(const Duration(seconds: 2));
      if (mounted) Navigator.of(context).pop(true);
    }
  }

  Future<void> _reject() async {
    if (_processing) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('拒绝此交易?'),
        content: const Text('拒绝后该交易不会执行,且不会消耗策略冷却。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('确认拒绝', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _processing = true);
    final ok = await AgentService.instance.rejectPendingApproval(
      widget.approval.approvalId,
    );
    if (!mounted) return;
    setState(() {
      _processing = false;
      _resultMsg = ok ? '✅ 已拒绝' : '❌ 拒绝失败';
    });
    if (ok) {
      await Future.delayed(const Duration(seconds: 1));
      if (mounted) Navigator.of(context).pop(false);
    }
  }

  Future<String?> _promptForSignature() async {
    final ctrl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('生物认证 + 钱包签名'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              '正式版会用 Face ID + wallet signature。\n'
              '当前 demo 直接输入任意字符串模拟签名:',
              style: TextStyle(fontSize: 12),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: ctrl,
              decoration: const InputDecoration(
                hintText: '签名(任意字符串)',
                border: OutlineInputBorder(),
              ),
              autofocus: true,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, null),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, ctrl.text),
            child: const Text('确认'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final a = widget.approval;
    return Scaffold(
      appBar: AppBar(
        title: const Text('HITL 审批'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Center(child: _CountdownBadge(remaining: _remaining)),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _StrategyCard(approval: a, scheme: scheme),
            _RiskCard(approval: a, scheme: scheme),
            if (widget.thesis != null) ThesisCard(thesis: widget.thesis!),
            const SizedBox(height: 80),  // 给底部按钮留空间
          ],
        ),
      ),
      bottomNavigationBar: SafeArea(
        child: Container(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
          decoration: BoxDecoration(
            color: scheme.surface,
            border: Border(top: BorderSide(color: scheme.outline.withValues(alpha: 0.2))),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (_resultMsg != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(_resultMsg!),
                ),
              Row(children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.close),
                    label: const Text('拒绝'),
                    onPressed: _processing || a.isExpired ? null : _reject,
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.red,
                      side: const BorderSide(color: Colors.red),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: FilledButton.icon(
                    icon: _processing
                        ? const SizedBox(width: 16, height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : const Icon(Icons.fingerprint),
                    label: Text(a.isExpired ? '已过期' : '批准并签名'),
                    onPressed: _processing || a.isExpired ? null : _approve,
                    style: FilledButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                ),
              ]),
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// 倒计时徽章
// ─────────────────────────────────────────────────────────────

class _CountdownBadge extends StatelessWidget {
  final Duration remaining;
  const _CountdownBadge({required this.remaining});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final expired = remaining.isNegative || remaining.inSeconds <= 0;
    final urgent = !expired && remaining.inSeconds < 60;
    final color = expired ? Colors.grey : (urgent ? Colors.red : scheme.primary);

    final mm = remaining.inMinutes.remainder(60).toString().padLeft(2, '0');
    final ss = remaining.inSeconds.remainder(60).toString().padLeft(2, '0');
    final label = expired ? '已过期' : '$mm:$ss';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.timer_outlined, size: 14, color: color),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(
            fontSize: 12, fontWeight: FontWeight.bold, color: color,
          )),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// 策略卡(策略名 + 触发条件)
// ─────────────────────────────────────────────────────────────

class _StrategyCard extends StatelessWidget {
  final PendingApproval approval;
  final ColorScheme scheme;
  const _StrategyCard({required this.approval, required this.scheme});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: scheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: scheme.outline.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.flash_on, size: 16, color: Colors.amber),
            const SizedBox(width: 4),
            const Text('策略触发', style: TextStyle(fontWeight: FontWeight.bold)),
            const Spacer(),
            if (approval.tokenSymbol != null)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: scheme.primaryContainer.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  '${approval.tokenSymbol} · ${(approval.chain ?? "?").toUpperCase()}',
                  style: const TextStyle(fontSize: 11),
                ),
              ),
          ]),
          const SizedBox(height: 10),
          ...approval.triggerConditionsMatched.map((c) => Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Padding(
                padding: EdgeInsets.only(top: 6),
                child: Icon(Icons.check_circle, size: 12, color: Colors.green),
              ),
              const SizedBox(width: 6),
              Expanded(child: Text(c, style: const TextStyle(fontSize: 13))),
            ]),
          )),
          if (approval.triggerConditionsMatched.isEmpty)
            Text('无具体触发条件', style: TextStyle(
              fontSize: 12, color: scheme.onSurface.withValues(alpha: 0.5),
            )),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// 风险卡(本次金额 / 剩余授权)
// ─────────────────────────────────────────────────────────────

class _RiskCard extends StatelessWidget {
  final PendingApproval approval;
  final ColorScheme scheme;
  const _RiskCard({required this.approval, required this.scheme});

  @override
  Widget build(BuildContext context) {
    final amount = approval.amountUsd ?? 0.0;
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.orange.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.orange.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: const [
            Icon(Icons.account_balance_wallet_outlined, size: 16, color: Colors.orange),
            SizedBox(width: 4),
            Text('本次交易金额', style: TextStyle(fontWeight: FontWeight.bold)),
          ]),
          const SizedBox(height: 8),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '\$${amount.toStringAsFixed(2)}',
                style: const TextStyle(
                  fontSize: 26, fontWeight: FontWeight.bold, color: Colors.orange,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                'USD',
                style: TextStyle(
                  fontSize: 13, color: scheme.onSurface.withValues(alpha: 0.6),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '⚠️ 通过即真金交易,不可撤销',
            style: TextStyle(
              fontSize: 11, color: Colors.orange.shade800,
            ),
          ),
        ],
      ),
    );
  }
}
