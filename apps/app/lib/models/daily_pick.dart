class DailyPick {
  final String mint;
  final String pickDate;
  final int rank;
  final double score;
  final Map<String, dynamic> scoreDetail;
  final double bcProgress;
  final double marketCapSol;

  // 来自 pump_tokens 的 join
  final String name;
  final String symbol;
  final String? imageUri;
  final String? twitter;
  final String? telegram;
  final String? website;
  final String? creator;

  // 来自 token_outcomes 的 left join（可能还没标签）
  final bool? didGraduate;
  final double? peakMultiplier;
  final bool? label2x;
  final bool? label10x;

  const DailyPick({
    required this.mint,
    required this.pickDate,
    required this.rank,
    required this.score,
    required this.scoreDetail,
    required this.bcProgress,
    required this.marketCapSol,
    required this.name,
    required this.symbol,
    this.imageUri,
    this.twitter,
    this.telegram,
    this.website,
    this.creator,
    this.didGraduate,
    this.peakMultiplier,
    this.label2x,
    this.label10x,
  });

  factory DailyPick.fromJson(Map<String, dynamic> json) {
    final pt = (json['pump_tokens'] as Map<String, dynamic>?) ?? {};
    // token_outcomes 嵌套在 pump_tokens 内部（通过 FK 关联）
    final toRaw = pt['token_outcomes'];
    final to = toRaw is List
        ? (toRaw.isNotEmpty ? toRaw.first as Map<String, dynamic> : <String, dynamic>{})
        : (toRaw as Map<String, dynamic>?) ?? {};

    return DailyPick(
      mint:          json['mint'] as String? ?? '',
      pickDate:      json['pick_date'] as String? ?? '',
      rank:          (json['rank'] as num?)?.toInt() ?? 0,
      score:         (json['score'] as num?)?.toDouble() ?? 0.0,
      scoreDetail:   (json['score_detail'] as Map<String, dynamic>?) ?? {},
      bcProgress:    (json['bc_progress'] as num?)?.toDouble() ?? 0.0,
      marketCapSol:  (json['market_cap_sol'] as num?)?.toDouble() ?? 0.0,
      name:          pt['name'] as String? ?? '',
      symbol:        pt['symbol'] as String? ?? '',
      imageUri:      pt['image_uri'] as String?,
      twitter:       pt['twitter'] as String?,
      telegram:      pt['telegram'] as String?,
      website:       pt['website'] as String?,
      creator:       pt['creator'] as String?,
      didGraduate:   to['did_graduate'] as bool?,
      peakMultiplier:(to['peak_multiplier'] as num?)?.toDouble(),
      label2x:       to['label_2x'] as bool?,
      label10x:      to['label_10x'] as bool?,
    );
  }

  /// 推荐强度
  String get recommendation {
    if (score >= 75) return 'strong';
    if (score >= 55) return 'normal';
    return 'skip';
  }

  /// 是否有结果（已经72h过去了）
  bool get hasOutcome => didGraduate != null;

  /// 最终结果描述
  String get outcomeLabel {
    if (!hasOutcome) return '追踪中';
    if (label10x == true) return '🚀 10x+';
    if (label2x == true) return '✅ 2x+';
    if (didGraduate == true) return '🎓 已毕业';
    return '❌ 未毕业';
  }
}
