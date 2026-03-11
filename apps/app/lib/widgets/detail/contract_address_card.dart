import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../models/token_detail.dart';
import '../../theme/app_colors.dart';

/// 合约地址 + 外部链接
class ContractAddressCard extends StatelessWidget {
  final TokenDetail token;
  final bool embedded;
  const ContractAddressCard({super.key, required this.token, this.embedded = false});

  @override
  Widget build(BuildContext context) {
    final short = '${token.address.substring(0, 6)}...${token.address.substring(token.address.length - 4)}';

    final content = Column(
      children: [
        _Row(
          icon: CupertinoIcons.doc_on_doc,
          label: '合约地址',
          trailing: Row(mainAxisSize: MainAxisSize.min, children: [
            Text(short, style: TextStyle(fontSize: 13,
                color: context.colors.textSecondary,
                fontFamily: 'Menlo')),
            const SizedBox(width: 4),
            Icon(CupertinoIcons.doc_on_clipboard, size: 14,
                color: context.colors.textTertiary),
          ]),
          onTap: () {
            Clipboard.setData(ClipboardData(text: token.address));
            _showCopied(context);
          },
        ),
        const Padding(padding: EdgeInsets.only(left: 44),
          child: Divider(height: 0.5, thickness: 0.5, color: Color(0xFFE5E5EA))),
        _Row(
          icon: CupertinoIcons.compass,
          label: '区块浏览器',
          onTap: () => _launch(token.explorerTokenUrl),
        ),
        const Padding(padding: EdgeInsets.only(left: 44),
          child: Divider(height: 0.5, thickness: 0.5, color: Color(0xFFE5E5EA))),
        _Row(
          icon: CupertinoIcons.chart_bar_alt_fill,
          label: 'DexScreener',
          onTap: () => _launch(token.dexScreenerUrl),
        ),
        const Padding(padding: EdgeInsets.only(left: 44),
          child: Divider(height: 0.5, thickness: 0.5, color: Color(0xFFE5E5EA))),
        _Row(
          icon: CupertinoIcons.graph_circle,
          label: 'GeckoTerminal',
          onTap: () => _launch(token.geckoTerminalUrl),
        ),
      ],
    );

    if (embedded) return content;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: context.colors.cardGlass,
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [
          BoxShadow(color: Color(0x0A000000), blurRadius: 10, offset: Offset(0, 2)),
        ],
      ),
      child: content,
    );
  }

  void _showCopied(BuildContext context) {
    final overlay = Overlay.of(context);
    final entry = OverlayEntry(
      builder: (_) => Positioned(
        bottom: 100, left: 0, right: 0,
        child: Center(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.black87,
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Text('已复制', style: TextStyle(color: Colors.white, fontSize: 14)),
          ),
        ),
      ),
    );
    overlay.insert(entry);
    Future.delayed(const Duration(seconds: 1), () => entry.remove());
  }

  void _launch(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }
}

class _Row extends StatelessWidget {
  final IconData icon;
  final String label;
  final Widget? trailing;
  final VoidCallback onTap;
  const _Row({required this.icon, required this.label, this.trailing, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return CupertinoButton(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      onPressed: onTap,
      child: Row(
        children: [
          Icon(icon, size: 16, color: context.colors.textSecondary),
          const SizedBox(width: 10),
          Text(label, style: TextStyle(fontSize: 14, color: context.colors.textPrimary)),
          const Spacer(),
          if (trailing != null) trailing!
          else Icon(CupertinoIcons.chevron_right, size: 14, color: context.colors.textTertiary),
        ],
      ),
    );
  }
}
