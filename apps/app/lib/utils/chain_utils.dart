import 'package:flutter/material.dart';

/// 链相关工具方法（颜色 / 标签映射）
class ChainUtils {
  ChainUtils._();

  static Color getColor(String chain) => switch (chain) {
    'solana' => const Color(0xFF9945FF),
    'bsc'    => const Color(0xFFF3BA2F),
    'base'   => const Color(0xFF0052FF),
    'eth'    => const Color(0xFF627EEA),
    _        => const Color(0xFF3B82F6),
  };

  static String getLabel(String chain) => switch (chain) {
    'solana' => 'SOL',
    'bsc'    => 'BSC',
    'base'   => 'BASE',
    'eth'    => 'ETH',
    _        => chain.toUpperCase(),
  };

  /// 返回可用的代币图片 URL（空字符串视为无图）
  static String? tokenImageUrl(String? existingUrl, String chain, String address) {
    if (existingUrl != null && existingUrl.isNotEmpty) return existingUrl;
    return null; // 后端负责填充 image_url，Flutter 不做 CDN fallback
  }
}
