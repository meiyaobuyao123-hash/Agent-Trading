import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../models/dexscreener_info.dart';
import '../../theme/app_colors.dart';

/// 紧凑社交图标行
class SocialLinksBar extends StatelessWidget {
  final DexScreenerInfo? info;
  final bool embedded;
  const SocialLinksBar({super.key, this.info, this.embedded = false});

  @override
  Widget build(BuildContext context) {
    final links = <_Link>[];
    if (info?.twitterUrl != null) {
      links.add(_Link('Twitter', CupertinoIcons.at, const Color(0xFF1DA1F2), info!.twitterUrl!));
    }
    if (info?.telegramUrl != null) {
      links.add(_Link('Telegram', CupertinoIcons.paperplane_fill, const Color(0xFF0088CC), info!.telegramUrl!));
    }
    if (info?.websiteUrl != null) {
      links.add(_Link('Website', CupertinoIcons.globe, AppColors.textSecondary, info!.websiteUrl!));
    }

    Widget content;
    if (links.isEmpty) {
      content = Row(
        children: [
          Icon(CupertinoIcons.link, size: 14, color: AppColors.textTertiary),
          const SizedBox(width: 6),
          const Text('暂无社交信息',
              style: TextStyle(fontSize: 13, color: AppColors.textTertiary)),
        ],
      );
    } else {
      content = Row(
        children: links.map((link) {
          return Padding(
            padding: const EdgeInsets.only(right: 12),
            child: GestureDetector(
              onTap: () => _open(link.url),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: link.color.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(link.icon, size: 16, color: link.color),
                    const SizedBox(width: 6),
                    Text(link.label,
                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500,
                            color: link.color)),
                  ],
                ),
              ),
            ),
          );
        }).toList(),
      );
    }

    if (embedded) return content;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: content,
    );
  }

  void _open(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }
}

class _Link {
  final String label;
  final IconData icon;
  final Color color;
  final String url;
  const _Link(this.label, this.icon, this.color, this.url);
}
