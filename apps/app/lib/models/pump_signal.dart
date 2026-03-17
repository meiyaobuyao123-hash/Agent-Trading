/// 实时 pump.fun 信号（来自后端内存信号池）
class PumpSignal {
  final String mint;
  final String symbol;
  final String name;
  final double score;
  final String recommendation;
  final double bcProgress;
  final double marketCapSol;
  final Map<String, dynamic> scoreDetail;
  final int uniqueBuyers;
  final double ageMinutes;
  final String? imageUri;
  final String? twitter;
  final String? telegram;
  final String? website;
  final String enteredAt;
  final String lastTradeAt;

  const PumpSignal({
    required this.mint,
    required this.symbol,
    required this.name,
    required this.score,
    required this.recommendation,
    required this.bcProgress,
    required this.marketCapSol,
    required this.scoreDetail,
    required this.uniqueBuyers,
    required this.ageMinutes,
    this.imageUri,
    this.twitter,
    this.telegram,
    this.website,
    required this.enteredAt,
    required this.lastTradeAt,
  });

  factory PumpSignal.fromJson(Map<String, dynamic> json) {
    return PumpSignal(
      mint: json['mint'] as String? ?? '',
      symbol: json['symbol'] as String? ?? '',
      name: json['name'] as String? ?? '',
      score: (json['score'] as num?)?.toDouble() ?? 0.0,
      recommendation: json['recommendation'] as String? ?? 'skip',
      bcProgress: (json['bc_progress'] as num?)?.toDouble() ?? 0.0,
      marketCapSol: (json['market_cap_sol'] as num?)?.toDouble() ?? 0.0,
      scoreDetail: (json['score_detail'] as Map<String, dynamic>?) ?? {},
      uniqueBuyers: (json['unique_buyers'] as num?)?.toInt() ?? 0,
      ageMinutes: (json['age_minutes'] as num?)?.toDouble() ?? 0.0,
      imageUri: json['image_uri'] as String?,
      twitter: json['twitter'] as String?,
      telegram: json['telegram'] as String?,
      website: json['website'] as String?,
      enteredAt: json['entered_at'] as String? ?? '',
      lastTradeAt: json['last_trade_at'] as String? ?? '',
    );
  }

  bool get isStrong => recommendation == 'strong';

  String get ageLabel {
    if (ageMinutes < 60) return '${ageMinutes.toInt()}m';
    return '${(ageMinutes / 60).toStringAsFixed(1)}h';
  }
}
