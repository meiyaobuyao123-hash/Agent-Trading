/// Review — 日/周/月复盘报告
/// 引用 docs/agent-pm/03-prd.md §7.7
/// 引用 docs/agent-pm/05-tool-catalog.md S07 review-engine
/// 引用 docs/agent-pm/17-tech-plan.md Phase 3
class Review {
  final String reviewId;
  final String period; // 'daily' | 'weekly' | 'monthly'
  final DateTime periodFrom;
  final DateTime periodTo;
  final ReviewSummary summary;
  final List<Insight> insights;
  final List<RuleProposal> ruleProposals;
  final ReviewMetrics metrics;
  final String? coldStartState; // 'no_trades' / 'few_trades' / 'normal' / null

  const Review({
    required this.reviewId,
    required this.period,
    required this.periodFrom,
    required this.periodTo,
    required this.summary,
    this.insights = const [],
    this.ruleProposals = const [],
    required this.metrics,
    this.coldStartState,
  });

  factory Review.fromJson(Map<String, dynamic> j) => Review(
        reviewId: j['review_id'] as String,
        period: j['period'] as String,
        periodFrom: DateTime.parse(j['period_from'] as String),
        periodTo: DateTime.parse(j['period_to'] as String),
        summary: ReviewSummary.fromJson(j['summary'] as Map<String, dynamic>),
        insights: (j['insights'] as List? ?? const [])
            .map((x) => Insight.fromJson(x as Map<String, dynamic>))
            .toList(),
        ruleProposals: (j['rule_proposals'] as List? ?? const [])
            .map((x) => RuleProposal.fromJson(x as Map<String, dynamic>))
            .toList(),
        metrics: ReviewMetrics.fromJson(j['metrics'] as Map<String, dynamic>),
        coldStartState: j['cold_start_state'] as String?,
      );
}

class ReviewSummary {
  final String headline;
  final String body; // ≤ 300 字
  const ReviewSummary({required this.headline, required this.body});
  factory ReviewSummary.fromJson(Map<String, dynamic> j) =>
      ReviewSummary(headline: j['headline'] as String, body: j['body'] as String);
}

class Insight {
  final String type; // 'win_pattern' | 'loss_pattern' | 'risk_warning' | 'observation'
  final String text;
  final List<String> evidenceTradeIds;
  final double? llmJudgeScore; // LLM-as-judge 0-1,< 0.5 丢弃
  const Insight({
    required this.type,
    required this.text,
    this.evidenceTradeIds = const [],
    this.llmJudgeScore,
  });
  factory Insight.fromJson(Map<String, dynamic> j) => Insight(
        type: j['type'] as String,
        text: j['text'] as String,
        evidenceTradeIds: (j['evidence_trade_ids'] as List? ?? const [])
            .map((x) => x.toString())
            .toList(),
        llmJudgeScore: (j['llm_judge_score'] as num?)?.toDouble(),
      );
}

class RuleProposal {
  final String proposalId;
  final String humanReadable;
  final Map<String, dynamic> formalCondition; // 结构化 condition/action JSON
  final int sampleSize;
  final double winRateDiff; // 与 baseline 对比的胜率差(pp)
  final double? wilsonCiLower;
  final List<String> activeRegimes;
  final String? reflectionId;

  const RuleProposal({
    required this.proposalId,
    required this.humanReadable,
    required this.formalCondition,
    required this.sampleSize,
    required this.winRateDiff,
    this.wilsonCiLower,
    this.activeRegimes = const [],
    this.reflectionId,
  });

  factory RuleProposal.fromJson(Map<String, dynamic> j) => RuleProposal(
        proposalId: j['proposal_id'] as String,
        humanReadable: j['human_readable'] as String,
        formalCondition:
            (j['formal_condition'] as Map<String, dynamic>?) ?? const {},
        sampleSize: j['sample_size'] as int? ?? 0,
        winRateDiff: (j['win_rate_diff'] as num?)?.toDouble() ?? 0.0,
        wilsonCiLower: (j['wilson_ci_lower'] as num?)?.toDouble(),
        activeRegimes: (j['active_regimes'] as List? ?? const [])
            .map((x) => x.toString())
            .toList(),
        reflectionId: j['reflection_id'] as String?,
      );
}

class ReviewMetrics {
  final int tradeCount;
  final double winRate; // 0-1
  final double evPct;
  final double sharpe;
  final double maxDrawdownPct;
  final double profitFactor;
  final double? klyFraction; // Kelly fraction
  const ReviewMetrics({
    required this.tradeCount,
    required this.winRate,
    required this.evPct,
    required this.sharpe,
    required this.maxDrawdownPct,
    required this.profitFactor,
    this.klyFraction,
  });
  factory ReviewMetrics.fromJson(Map<String, dynamic> j) => ReviewMetrics(
        tradeCount: j['trade_count'] as int? ?? 0,
        winRate: (j['win_rate'] as num?)?.toDouble() ?? 0.0,
        evPct: (j['ev_pct'] as num?)?.toDouble() ?? 0.0,
        sharpe: (j['sharpe'] as num?)?.toDouble() ?? 0.0,
        maxDrawdownPct: (j['max_drawdown_pct'] as num?)?.toDouble() ?? 0.0,
        profitFactor: (j['profit_factor'] as num?)?.toDouble() ?? 1.0,
        klyFraction: (j['kelly_fraction'] as num?)?.toDouble(),
      );
}
