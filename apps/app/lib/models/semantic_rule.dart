/// SemanticRule — Semantic Memory 规则(用户可见 + 可控)
/// 引用 docs/agent-pm/06-memory-spec.md §3.3
/// 引用 docs/agent-pm/05-tool-catalog.md T11 approve_rule
/// 引用 docs/agent-pm/17-tech-plan.md Phase 3
///
/// 50 条上限;Shadow Mode 14d 观察期才正式激活
class SemanticRule {
  final String ruleId;
  final String humanReadable;
  final Map<String, dynamic> formalCondition; // {condition, action} 结构化
  final List<String> activeRegimes;
  final RuleEvidence evidence;
  final RuleStatus status;
  final DateTime? shadowModeUntil; // 14d 观察期结束
  final DateTime? dormantSince; // 30d 未匹配
  final int matchCount;
  final int proposeCount;
  final DateTime createdAt;
  final DateTime updatedAt;
  final double? userOverrideRate; // 用户手动覆盖率(>3 次提议降级)

  const SemanticRule({
    required this.ruleId,
    required this.humanReadable,
    required this.formalCondition,
    this.activeRegimes = const [],
    required this.evidence,
    required this.status,
    this.shadowModeUntil,
    this.dormantSince,
    this.matchCount = 0,
    this.proposeCount = 0,
    required this.createdAt,
    required this.updatedAt,
    this.userOverrideRate,
  });

  bool get isShadowMode =>
      shadowModeUntil != null && DateTime.now().isBefore(shadowModeUntil!);
  bool get isDormant => dormantSince != null;
  bool get isActive => status == RuleStatus.active && !isShadowMode;

  Duration? get shadowRemaining =>
      shadowModeUntil?.difference(DateTime.now());

  factory SemanticRule.fromJson(Map<String, dynamic> j) => SemanticRule(
        ruleId: j['rule_id'] as String,
        humanReadable: j['human_readable'] as String,
        formalCondition:
            (j['formal_condition'] as Map<String, dynamic>?) ?? const {},
        activeRegimes: (j['active_regimes'] as List? ?? const [])
            .map((x) => x.toString())
            .toList(),
        evidence: RuleEvidence.fromJson(
            (j['evidence'] as Map<String, dynamic>?) ?? const {}),
        status: _parseStatus(j['status'] as String?),
        shadowModeUntil: j['shadow_mode_until'] != null
            ? DateTime.parse(j['shadow_mode_until'] as String)
            : null,
        dormantSince: j['dormant_since'] != null
            ? DateTime.parse(j['dormant_since'] as String)
            : null,
        matchCount: j['match_count'] as int? ?? 0,
        proposeCount: j['propose_count'] as int? ?? 0,
        createdAt: DateTime.parse(j['created_at'] as String),
        updatedAt: DateTime.parse(j['updated_at'] as String),
        userOverrideRate: (j['user_override_rate'] as num?)?.toDouble(),
      );

  static RuleStatus _parseStatus(String? s) {
    switch (s) {
      case 'active':
        return RuleStatus.active;
      case 'shadow':
        return RuleStatus.shadow;
      case 'dormant':
        return RuleStatus.dormant;
      case 'disabled':
        return RuleStatus.disabled;
      case 'archived':
        return RuleStatus.archived;
      default:
        return RuleStatus.shadow;
    }
  }
}

enum RuleStatus { shadow, active, dormant, disabled, archived }

class RuleEvidence {
  final int sampleSize;
  final double winRateDiff; // 与 baseline 对比胜率差(pp)
  final double? tTestP;
  final double? wilsonCiLower;
  final List<String> regimesObserved;
  const RuleEvidence({
    this.sampleSize = 0,
    this.winRateDiff = 0.0,
    this.tTestP,
    this.wilsonCiLower,
    this.regimesObserved = const [],
  });
  factory RuleEvidence.fromJson(Map<String, dynamic> j) => RuleEvidence(
        sampleSize: j['sample_size'] as int? ?? 0,
        winRateDiff: (j['win_rate_diff'] as num?)?.toDouble() ?? 0.0,
        tTestP: (j['t_test_p'] as num?)?.toDouble(),
        wilsonCiLower: (j['wilson_ci_lower'] as num?)?.toDouble(),
        regimesObserved: (j['regimes_observed'] as List? ?? const [])
            .map((x) => x.toString())
            .toList(),
      );
}
