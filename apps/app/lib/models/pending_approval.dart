/// PendingApproval — HITL 待审批请求
/// 引用 docs/agent-pm/05-tool-catalog.md T09 create_approval_request
/// 引用 docs/agent-pm/17-tech-plan.md Phase 3
/// 引用 services/pump-scanner/migrations/036_pending_approvals_wal.sql
class PendingApproval {
  final String approvalId;
  final String strategyId;
  final List<String> triggerConditionsMatched;
  final String? thesisId;
  final String? tokenSymbol;
  final String? tokenAddress;
  final String? chain;
  final double? amountUsd;
  final String status; // 'pending' | 'approved' | 'rejected' | 'expired'
  final DateTime createdAt;
  final DateTime expiresAt;
  final DateTime? decidedAt;

  const PendingApproval({
    required this.approvalId,
    required this.strategyId,
    this.triggerConditionsMatched = const [],
    this.thesisId,
    this.tokenSymbol,
    this.tokenAddress,
    this.chain,
    this.amountUsd,
    required this.status,
    required this.createdAt,
    required this.expiresAt,
    this.decidedAt,
  });

  bool get isPending => status == 'pending';
  bool get isExpired => status == 'expired' || DateTime.now().isAfter(expiresAt);
  Duration get remaining => expiresAt.difference(DateTime.now());

  factory PendingApproval.fromJson(Map<String, dynamic> j) => PendingApproval(
        approvalId: j['approval_id'] as String,
        strategyId: j['strategy_id'] as String,
        triggerConditionsMatched:
            (j['trigger_conditions_matched'] as List? ?? const [])
                .map((x) => x.toString())
                .toList(),
        thesisId: j['thesis_id'] as String?,
        tokenSymbol: j['token_symbol'] as String?,
        tokenAddress: j['token_address'] as String?,
        chain: j['chain'] as String?,
        amountUsd: (j['amount_usd'] as num?)?.toDouble(),
        status: j['status'] as String? ?? 'pending',
        createdAt: DateTime.parse(j['created_at'] as String),
        expiresAt: DateTime.parse(j['expires_at'] as String),
        decidedAt: j['decided_at'] != null
            ? DateTime.parse(j['decided_at'] as String)
            : null,
      );
}
