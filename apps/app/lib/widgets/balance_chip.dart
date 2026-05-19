import 'dart:async';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

import '../screens/credit/credit_page.dart';
import '../services/auth_service.dart';
import '../services/credit_service.dart';

/// R47 — 余额胶囊(用在 chat AppBar 右侧 / profile 入口)
///
/// 30 秒自动刷新一次。点击跳 CreditPage。
/// 余额低 / 0 时显示警告色。
///
/// R70.1:未登录态直接隐藏(算力依赖 user_id,未登录显示余额无意义 + 调
/// /api/credit/balance 会 401)。登录态变化自动 rebuild。
class BalanceChip extends StatefulWidget {
  const BalanceChip({super.key});

  @override
  State<BalanceChip> createState() => _BalanceChipState();
}

class _BalanceChipState extends State<BalanceChip> {
  Timer? _timer;
  CreditBalance? _balance;

  @override
  void initState() {
    super.initState();
    // R70.1 — 仅登录态启 timer + 拉余额
    if (AuthService.instance.isLoggedIn) {
      _refresh();
      _timer = Timer.periodic(const Duration(seconds: 30), (_) => _refresh());
    }
    CreditService.instance.addListener(_onChange);
    AuthService.instance.addListener(_onAuthChanged);
  }

  @override
  void dispose() {
    _timer?.cancel();
    CreditService.instance.removeListener(_onChange);
    AuthService.instance.removeListener(_onAuthChanged);
    super.dispose();
  }

  void _onChange() {
    if (mounted) setState(() => _balance = CreditService.instance.balance);
  }

  /// R70.1 — 登录态切换:登录后启 timer 拉余额,登出后停 timer + 清余额
  void _onAuthChanged() {
    if (!mounted) return;
    if (AuthService.instance.isLoggedIn) {
      _refresh();
      _timer ??= Timer.periodic(const Duration(seconds: 30), (_) => _refresh());
    } else {
      _timer?.cancel();
      _timer = null;
      setState(() => _balance = null);
    }
  }

  Future<void> _refresh() async {
    if (!AuthService.instance.isLoggedIn) return;
    final b = await CreditService.instance.fetchBalance();
    if (mounted) setState(() => _balance = b);
  }

  @override
  Widget build(BuildContext context) {
    // R70.1 — 未登录直接隐藏(避免在 AppBar 留一个 "$0.0000" 假入口)
    if (!AuthService.instance.isLoggedIn) {
      return const SizedBox.shrink();
    }

    final bal = _balance?.balanceUsd ?? 0;
    final lowBal = bal > 0 && bal < 0.1;
    final zeroBal = bal <= 0 && (_balance?.hasAccount ?? false);

    final color = zeroBal
        ? const Color(0xFFEF4444)
        : lowBal
            ? const Color(0xFFF59E0B)
            : const Color(0xFF3C82F6);

    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: () {
          Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const CreditPage()),
          );
        },
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            border: Border.all(color: color.withValues(alpha: 0.3)),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(CupertinoIcons.bolt_fill, color: color, size: 11),
              const SizedBox(width: 4),
              Text(
                _balance == null ? '...' : '\$${bal.toStringAsFixed(4)}',
                style: TextStyle(
                  color: color,
                  fontSize: 11.5,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
