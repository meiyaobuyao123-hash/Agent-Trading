/// BTC/ETH 投资 Agent 数据模型

class BtcEthDashboard {
  final BtcEthAssetSummary btc;
  final BtcEthAssetSummary eth;

  const BtcEthDashboard({required this.btc, required this.eth});

  factory BtcEthDashboard.fromJson(Map<String, dynamic> json) {
    return BtcEthDashboard(
      btc: BtcEthAssetSummary.fromJson(json['btc'] ?? {}),
      eth: BtcEthAssetSummary.fromJson(json['eth'] ?? {}),
    );
  }
}

class BtcEthAssetSummary {
  final double price;
  final double change24h;
  final double? rsi;
  final int? fearGreed;
  final double? fundingRate;
  final Map<String, int> scores;

  const BtcEthAssetSummary({
    required this.price,
    required this.change24h,
    this.rsi,
    this.fearGreed,
    this.fundingRate,
    required this.scores,
  });

  factory BtcEthAssetSummary.fromJson(Map<String, dynamic> json) {
    final scoresMap = json['scores'] as Map<String, dynamic>? ?? {};
    return BtcEthAssetSummary(
      price: (json['price'] as num?)?.toDouble() ?? 0,
      change24h: (json['change_24h'] as num?)?.toDouble() ?? 0,
      rsi: (json['rsi'] as num?)?.toDouble(),
      fearGreed: json['fear_greed'] as int?,
      fundingRate: (json['funding_rate'] as num?)?.toDouble(),
      scores: scoresMap.map((k, v) => MapEntry(k, (v as num?)?.toInt() ?? 50)),
    );
  }
}

class BtcEthSignal {
  final String id;
  final String asset;
  final String signalType;
  final double entryPrice;
  final double stopLoss;
  final double targetPrice;
  final double riskReward;
  final int confidence;
  final String? reasoning;
  final String status;
  final double? exitPrice;
  final double? actualPnlPct;
  final DateTime createdAt;

  const BtcEthSignal({
    required this.id,
    required this.asset,
    required this.signalType,
    required this.entryPrice,
    required this.stopLoss,
    required this.targetPrice,
    required this.riskReward,
    required this.confidence,
    this.reasoning,
    required this.status,
    this.exitPrice,
    this.actualPnlPct,
    required this.createdAt,
  });

  factory BtcEthSignal.fromJson(Map<String, dynamic> json) {
    return BtcEthSignal(
      id: json['id'] ?? '',
      asset: json['asset'] ?? 'BTC',
      signalType: json['signal_type'] ?? 'long',
      entryPrice: (json['entry_price'] as num?)?.toDouble() ?? 0,
      stopLoss: (json['stop_loss'] as num?)?.toDouble() ?? 0,
      targetPrice: (json['target_price'] as num?)?.toDouble() ?? 0,
      riskReward: (json['risk_reward'] as num?)?.toDouble() ?? 0,
      confidence: (json['confidence'] as num?)?.toInt() ?? 50,
      reasoning: json['reasoning'] as String?,
      status: json['status'] ?? 'active',
      exitPrice: (json['exit_price'] as num?)?.toDouble(),
      actualPnlPct: (json['actual_pnl_pct'] as num?)?.toDouble(),
      createdAt: DateTime.tryParse(json['created_at'] ?? '') ?? DateTime.now(),
    );
  }

  bool get isLong => signalType == 'long';
  bool get isActive => status == 'active';
}

class BtcEthReport {
  final String asset;
  final String reportDate;
  final String cyclePhase;
  final double cycleConfidence;
  final String direction;
  final Map<String, dynamic>? positionAllocation;
  final Map<String, dynamic>? keyLevels;
  final List<dynamic>? riskFactors;
  final String? reasoning;

  const BtcEthReport({
    required this.asset,
    required this.reportDate,
    required this.cyclePhase,
    required this.cycleConfidence,
    required this.direction,
    this.positionAllocation,
    this.keyLevels,
    this.riskFactors,
    this.reasoning,
  });

  factory BtcEthReport.fromJson(Map<String, dynamic> json) {
    return BtcEthReport(
      asset: json['asset'] ?? 'BTC',
      reportDate: json['report_date'] ?? '',
      cyclePhase: json['cycle_phase'] ?? 'recovery',
      cycleConfidence: (json['cycle_confidence'] as num?)?.toDouble() ?? 50,
      direction: json['direction'] ?? 'neutral',
      positionAllocation: json['position_allocation'] as Map<String, dynamic>?,
      keyLevels: json['key_levels'] as Map<String, dynamic>?,
      riskFactors: json['risk_factors'] as List<dynamic>?,
      reasoning: json['reasoning'] as String?,
    );
  }

  String get cyclePhaseLabel {
    const labels = {
      'accumulation': 'Accumulation',
      'recovery': 'Recovery',
      'breakout': 'Breakout',
      'bull_run': 'Bull Run',
      'euphoria': 'Euphoria',
      'distribution': 'Distribution',
      'bear': 'Bear',
    };
    return labels[cyclePhase] ?? cyclePhase;
  }

  bool get isBullish => direction == 'bullish';
  bool get isBearish => direction == 'bearish';
}

class BtcEthAlert {
  final String id;
  final String? asset;
  final String severity;
  final String alertType;
  final String title;
  final String message;
  final DateTime createdAt;

  const BtcEthAlert({
    required this.id,
    this.asset,
    required this.severity,
    required this.alertType,
    required this.title,
    required this.message,
    required this.createdAt,
  });

  factory BtcEthAlert.fromJson(Map<String, dynamic> json) {
    return BtcEthAlert(
      id: json['id'] ?? '',
      asset: json['asset'] as String?,
      severity: json['severity'] ?? 'info',
      alertType: json['alert_type'] ?? '',
      title: json['title'] ?? '',
      message: json['message'] ?? '',
      createdAt: DateTime.tryParse(json['created_at'] ?? '') ?? DateTime.now(),
    );
  }

  bool get isCritical => severity == 'critical';
  bool get isWarning => severity == 'warning';
}
