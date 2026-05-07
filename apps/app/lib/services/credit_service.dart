import 'package:flutter/foundation.dart';

import '../config/app_config.dart';
import 'api_client.dart';

/// R47 — Flutter Credit 服务封装
///
/// 后端 endpoints:
///   GET  /api/credit/balance              余额 + 累计 + 估算
///   POST /api/credit/recharge-orders      创建订单 {chain, amount_usd}
///   GET  /api/credit/recharge-orders      列出订单
///   GET  /api/credit/transactions         交易历史
class CreditService extends ChangeNotifier {
  CreditService._();
  static final CreditService instance = CreditService._();

  CreditBalance? _balance;
  CreditBalance? get balance => _balance;

  String get _base => AppConfig.backendBaseUrl;

  Future<CreditBalance?> fetchBalance() async {
    final data = await ApiClient.instance.get('$_base/api/credit/balance');
    if (data == null) return null;
    _balance = CreditBalance.fromJson(data);
    notifyListeners();
    return _balance;
  }

  Future<RechargeOrder?> createRechargeOrder(String chain, int amountUsd) async {
    final data = await ApiClient.instance.post(
      '$_base/api/credit/recharge-orders',
      body: {'chain': chain, 'amount_usd': amountUsd},
    );
    if (data == null) return null;
    return RechargeOrder.fromJson(data);
  }

  Future<List<RechargeOrder>> listRechargeOrders({int limit = 20}) async {
    final data = await ApiClient.instance.get('$_base/api/credit/recharge-orders?limit=$limit');
    if (data == null) return const [];
    final orders = (data['orders'] as List?) ?? const [];
    return orders.map((e) => RechargeOrder.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<CreditTransaction>> listTransactions({int limit = 50}) async {
    final data = await ApiClient.instance.get('$_base/api/credit/transactions?limit=$limit');
    if (data == null) return const [];
    final txs = (data['transactions'] as List?) ?? const [];
    return txs.map((e) => CreditTransaction.fromJson(e as Map<String, dynamic>)).toList();
  }
}

class CreditBalance {
  final double balanceUsd;
  final double totalRecharged;
  final double totalConsumed;
  final bool hasAccount;
  final int estimatedMessagesLeft;
  CreditBalance({
    required this.balanceUsd,
    required this.totalRecharged,
    required this.totalConsumed,
    required this.hasAccount,
    required this.estimatedMessagesLeft,
  });
  factory CreditBalance.fromJson(Map<String, dynamic> j) => CreditBalance(
        balanceUsd: double.tryParse('${j['balance_usd'] ?? 0}') ?? 0,
        totalRecharged: double.tryParse('${j['total_recharged'] ?? 0}') ?? 0,
        totalConsumed: double.tryParse('${j['total_consumed'] ?? 0}') ?? 0,
        hasAccount: j['has_account'] == true,
        estimatedMessagesLeft: (j['estimated_messages_left'] as num?)?.toInt() ?? 0,
      );
}

class RechargeOrder {
  final int id;
  final String chain;
  final String address;
  final String amountExact;
  final String amountBase;
  final String amountNonce;
  final String? createdAt;
  final String? expiresAt;
  final String status;
  final String? chainTxHash;

  RechargeOrder({
    required this.id,
    required this.chain,
    required this.address,
    required this.amountExact,
    required this.amountBase,
    required this.amountNonce,
    this.createdAt,
    this.expiresAt,
    required this.status,
    this.chainTxHash,
  });

  factory RechargeOrder.fromJson(Map<String, dynamic> j) => RechargeOrder(
        id: (j['id'] as num).toInt(),
        chain: j['chain']?.toString() ?? '',
        address: j['address']?.toString() ?? '',
        amountExact: j['amount_exact']?.toString() ?? '0',
        amountBase: j['amount_base']?.toString() ?? '0',
        amountNonce: j['amount_nonce']?.toString() ?? '0',
        createdAt: j['created_at']?.toString(),
        expiresAt: j['expires_at']?.toString(),
        status: j['status']?.toString() ?? 'pending',
        chainTxHash: j['chain_tx_hash']?.toString(),
      );
}

class CreditTransaction {
  final int id;
  final String type; // recharge / consume / adjust / refund
  final double amountUsd;
  final double balanceAfter;
  final String? model;
  final int? tokensIn;
  final int? tokensOut;
  final String? chainTxHash;
  final String ts;

  CreditTransaction({
    required this.id,
    required this.type,
    required this.amountUsd,
    required this.balanceAfter,
    this.model,
    this.tokensIn,
    this.tokensOut,
    this.chainTxHash,
    required this.ts,
  });

  factory CreditTransaction.fromJson(Map<String, dynamic> j) => CreditTransaction(
        id: (j['id'] as num).toInt(),
        type: j['type']?.toString() ?? '',
        amountUsd: double.tryParse('${j['amount_usd'] ?? 0}') ?? 0,
        balanceAfter: double.tryParse('${j['balance_after'] ?? 0}') ?? 0,
        model: j['model']?.toString(),
        tokensIn: (j['tokens_in'] as num?)?.toInt(),
        tokensOut: (j['tokens_out'] as num?)?.toInt(),
        chainTxHash: j['chain_tx_hash']?.toString(),
        ts: j['ts']?.toString() ?? '',
      );
}
