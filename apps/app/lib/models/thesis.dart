/// Thesis — Agent 深度分析输出(S08 thesis-writer)
/// 引用 docs/agent-pm/03-prd.md §2.7
/// 引用 docs/agent-pm/17-tech-plan.md Phase 3
///
/// 状态: v0.1 占位(W7-W12 接入 mock + 真实 endpoint)
class Thesis {
  final String thesisId;
  final String chain;
  final String tokenAddress;
  final String? tokenSymbol;
  final String level; // 'L1' | 'L2' | 'L3'
  final String direction; // 'bullish' | 'bearish' | 'neutral' | 'hold' | 'avoid'
  final double conviction; // 0-1
  final EntryZone? entryZone;
  final double? stopLoss;
  final List<double> targetPrice; // [t1, t2, t3] 分批止盈
  final List<String> risks; // ≥ 2 条
  final String summary30w; // ≤ 30 字白话
  final List<EvidenceItem> evidence;
  final List<SimilarCase> similarPastCases;
  final double? costUsd;
  final int? latencyMs;
  final DateTime ts;

  const Thesis({
    required this.thesisId,
    required this.chain,
    required this.tokenAddress,
    this.tokenSymbol,
    required this.level,
    required this.direction,
    required this.conviction,
    this.entryZone,
    this.stopLoss,
    this.targetPrice = const [],
    required this.risks,
    required this.summary30w,
    this.evidence = const [],
    this.similarPastCases = const [],
    this.costUsd,
    this.latencyMs,
    required this.ts,
  });

  bool get isLowConviction => conviction < 0.5;
  bool get isHoldOrAvoid => direction == 'hold' || direction == 'avoid';

  factory Thesis.fromJson(Map<String, dynamic> j) {
    final ez = j['entry_zone'];
    return Thesis(
      thesisId: j['thesis_id'] as String,
      chain: j['chain'] as String,
      tokenAddress: j['token_address'] as String,
      tokenSymbol: j['token_symbol'] as String?,
      level: j['level'] as String? ?? 'L2',
      direction: j['direction'] as String,
      conviction: (j['conviction'] as num).toDouble(),
      entryZone: ez != null ? EntryZone.fromJson(ez as Map<String, dynamic>) : null,
      stopLoss: (j['stop_loss'] as num?)?.toDouble(),
      targetPrice: (j['target_price'] as List? ?? const [])
          .map((x) => (x as num).toDouble())
          .toList(),
      risks: (j['risks'] as List? ?? const []).map((x) => x.toString()).toList(),
      summary30w: j['summary_30w'] as String? ?? '',
      evidence: (j['evidence'] as List? ?? const [])
          .map((x) => EvidenceItem.fromJson(x as Map<String, dynamic>))
          .toList(),
      similarPastCases: (j['similar_past_cases'] as List? ?? const [])
          .map((x) => SimilarCase.fromJson(x as Map<String, dynamic>))
          .toList(),
      costUsd: (j['cost_usd'] as num?)?.toDouble(),
      latencyMs: j['latency_ms'] as int?,
      ts: j['ts'] != null
          ? DateTime.parse(j['ts'] as String)
          : DateTime.now().toUtc(),
    );
  }
}

class EntryZone {
  final double low;
  final double high;
  const EntryZone({required this.low, required this.high});
  factory EntryZone.fromJson(Map<String, dynamic> j) =>
      EntryZone(low: (j['low'] as num).toDouble(), high: (j['high'] as num).toDouble());
}

class EvidenceItem {
  final String source; // 'smart_money_signals' / 'hot_coins.score' / ...
  final String value;
  final DateTime? ts;
  const EvidenceItem({required this.source, required this.value, this.ts});
  factory EvidenceItem.fromJson(Map<String, dynamic> j) => EvidenceItem(
        source: j['source'] as String,
        value: j['value'].toString(),
        ts: j['ts'] != null ? DateTime.tryParse(j['ts'] as String) : null,
      );
}

class SimilarCase {
  final String tokenSymbol;
  final DateTime occurredAt;
  final String outcome; // 'win' | 'loss' | 'flat'
  final double similarity;
  const SimilarCase({
    required this.tokenSymbol,
    required this.occurredAt,
    required this.outcome,
    required this.similarity,
  });
  factory SimilarCase.fromJson(Map<String, dynamic> j) => SimilarCase(
        tokenSymbol: j['token_symbol'] as String? ?? '?',
        occurredAt: j['occurred_at'] != null
            ? DateTime.parse(j['occurred_at'] as String)
            : DateTime.now(),
        outcome: j['outcome'] as String? ?? 'flat',
        similarity: (j['similarity'] as num?)?.toDouble() ?? 0.0,
      );
}
