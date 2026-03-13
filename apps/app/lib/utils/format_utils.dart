/// 通用格式化工具（价格 / 金额 / 数字 / 哈希截断）
class FormatUtils {
  FormatUtils._();

  /// 格式化代币价格（自适应精度）
  static String fmtPrice(double p) {
    if (p >= 1000) return '\$${p.toStringAsFixed(0)}';
    if (p >= 1) return '\$${p.toStringAsFixed(2)}';
    if (p >= 0.01) return '\$${p.toStringAsFixed(4)}';
    if (p >= 0.0001) return '\$${p.toStringAsFixed(6)}';
    return '\$${p.toStringAsFixed(8)}';
  }

  /// 紧凑市值 / Volume（B / M / K）
  static String fmtCompact(double v) {
    if (v >= 1e9) return '\$${(v / 1e9).toStringAsFixed(1)}B';
    if (v >= 1e6) return '\$${(v / 1e6).toStringAsFixed(1)}M';
    if (v >= 1e3) return '\$${(v / 1e3).toStringAsFixed(0)}K';
    if (v > 0) return '\$${v.toStringAsFixed(0)}';
    return '-';
  }

  /// 格式化交易金额（M / K / 小数）
  static String fmtAmt(double v) {
    if (v >= 1e6) return '\$${(v / 1e6).toStringAsFixed(2)}M';
    if (v >= 1e3) return '\$${(v / 1e3).toStringAsFixed(1)}K';
    return '\$${v.toStringAsFixed(2)}';
  }

  /// 格式化交易金额（不含$符号）
  static String fmtAmtRaw(double v) {
    if (v >= 1e6) return '${(v / 1e6).toStringAsFixed(2)}M';
    if (v >= 1e3) return '${(v / 1e3).toStringAsFixed(1)}K';
    return v.toStringAsFixed(2);
  }

  /// 格式化整数计数（M / K）
  static String fmtNum(int n) {
    if (n >= 1000000) return '${(n / 1000000).toStringAsFixed(1)}M';
    if (n >= 1000) return '${(n / 1000).toStringAsFixed(1)}K';
    return '$n';
  }

  /// 格式化 Volume（含 >=1e4 区间）
  static String fmtVolume(double v) {
    if (v >= 1e6) return '\$${(v / 1e6).toStringAsFixed(2)}M';
    if (v >= 1e4) return '\$${(v / 1e3).toStringAsFixed(1)}K';
    if (v >= 1e3) return '\$${(v / 1e3).toStringAsFixed(1)}K';
    if (v > 0) return '\$${v.toStringAsFixed(2)}';
    return '\$0';
  }

  /// 截断交易哈希
  static String truncHash(String hash) {
    if (hash.length < 16) return hash;
    return '${hash.substring(0, 8)}...${hash.substring(hash.length - 6)}';
  }
}
