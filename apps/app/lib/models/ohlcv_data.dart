/// K 线蜡烛数据（GeckoTerminal OHLCV）
class OhlcvCandle {
  final DateTime timestamp;
  final double open;
  final double high;
  final double low;
  final double close;
  final double volume;

  const OhlcvCandle({
    required this.timestamp,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    required this.volume,
  });

  /// GeckoTerminal 返回 [timestamp, open, high, low, close, volume]
  factory OhlcvCandle.fromList(List<dynamic> arr) {
    return OhlcvCandle(
      timestamp: DateTime.fromMillisecondsSinceEpoch((arr[0] as num).toInt() * 1000),
      open:   (arr[1] as num).toDouble(),
      high:   (arr[2] as num).toDouble(),
      low:    (arr[3] as num).toDouble(),
      close:  (arr[4] as num).toDouble(),
      volume: (arr[5] as num).toDouble(),
    );
  }

  bool get isBullish => close >= open;
}
