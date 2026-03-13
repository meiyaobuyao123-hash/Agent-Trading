import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import '../../utils/chain_utils.dart';

/// 通用代币头像组件
/// 支持网络图片 + 链颜色边框 + 首字母 fallback
class TokenAvatar extends StatelessWidget {
  final String? imageUrl;
  final String symbol;
  final String chain;
  final double size;
  final double borderWidth;

  const TokenAvatar({
    super.key,
    this.imageUrl,
    required this.symbol,
    required this.chain,
    this.size = 38,
    this.borderWidth = 1.5,
  });

  @override
  Widget build(BuildContext context) {
    final chainColor = ChainUtils.getColor(chain);
    final hasUrl = imageUrl != null && imageUrl!.isNotEmpty;

    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(
          color: chainColor.withValues(alpha: 0.2),
          width: borderWidth,
        ),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(size / 2),
        child: hasUrl
            ? CachedNetworkImage(
                imageUrl: imageUrl!,
                width: size,
                height: size,
                fit: BoxFit.cover,
                fadeInDuration: const Duration(milliseconds: 200),
                placeholder: (_, __) => _letterAvatar(chainColor),
                errorWidget: (_, __, ___) => _letterAvatar(chainColor),
              )
            : _letterAvatar(chainColor),
      ),
    );
  }

  Widget _letterAvatar(Color chainColor) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: chainColor.withValues(alpha: 0.12),
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        symbol.isNotEmpty ? symbol[0].toUpperCase() : '?',
        style: TextStyle(
          color: chainColor,
          fontSize: size * 0.4,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
