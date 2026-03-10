import 'package:flutter/material.dart';
import '../../models/token_detail.dart';
import '../../models/goplus_report.dart';
import '../../models/dexscreener_info.dart';
import '../../theme/app_colors.dart';
import 'trading_dynamics_card.dart';
import 'recent_trades_card.dart';
import 'holder_info_card.dart';
import 'security_check_card.dart';
import 'social_links_bar.dart';
import 'contract_address_card.dart';

/// 底部三 Tab 区域：行情 / 安全 / 信息
class BottomTabsSection extends StatefulWidget {
  final TokenDetail token;
  final GoPlusReport? goplus;
  final DexScreenerInfo? dexInfo;
  final double? top1Pct;
  final bool goplusLoading;
  final String? resolvedPair;

  const BottomTabsSection({
    super.key,
    required this.token,
    this.goplus,
    this.dexInfo,
    this.top1Pct,
    this.goplusLoading = false,
    this.resolvedPair,
  });

  @override
  State<BottomTabsSection> createState() => _BottomTabsSectionState();
}

class _BottomTabsSectionState extends State<BottomTabsSection> {
  int _tabIdx = 0;

  static const _tabs = ['交易动态', '安全检测', '代币信息'];

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [
          BoxShadow(color: Color(0x0A000000), blurRadius: 10, offset: Offset(0, 2)),
        ],
      ),
      child: Column(
        children: [
          // Tab 栏
          Container(
            padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
            child: Row(
              children: List.generate(_tabs.length, (i) {
                final selected = i == _tabIdx;
                return Expanded(
                  child: GestureDetector(
                    onTap: () => setState(() => _tabIdx = i),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      decoration: BoxDecoration(
                        border: Border(
                          bottom: BorderSide(
                            color: selected ? AppColors.primary : Colors.transparent,
                            width: 2,
                          ),
                        ),
                      ),
                      child: Text(
                        _tabs[i],
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                          color: selected ? AppColors.primary : AppColors.textSecondary,
                        ),
                      ),
                    ),
                  ),
                );
              }),
            ),
          ),
          const Divider(height: 1, color: Color(0xFFE8E8ED)),

          // Tab 内容
          Padding(
            padding: const EdgeInsets.all(12),
            child: _buildTabContent(),
          ),
        ],
      ),
    );
  }

  Widget _buildTabContent() {
    switch (_tabIdx) {
      case 0: // 交易动态
        return Column(
          children: [
            if (widget.token.buys1h + widget.token.sells1h > 0 ||
                widget.token.buys24h + widget.token.sells24h > 0) ...[
              TradingDynamicsCard(token: widget.token, embedded: true),
              const SizedBox(height: 12),
            ],
            RecentTradesCard(
              pairAddress: widget.resolvedPair ?? widget.token.pairAddress,
              network: widget.token.geckoNetwork,
              embedded: true,
            ),
          ],
        );
      case 1: // 安全检测
        return Column(
          children: [
            HolderInfoCard(
              token: widget.token,
              goplus: widget.goplus,
              top1Pct: widget.top1Pct,
              embedded: true,
            ),
            const SizedBox(height: 12),
            SecurityCheckCard(
              report: widget.goplus,
              loading: widget.goplusLoading,
              embedded: true,
            ),
          ],
        );
      case 2: // 代币信息
        return Column(
          children: [
            SocialLinksBar(info: widget.dexInfo, embedded: true),
            const SizedBox(height: 12),
            ContractAddressCard(token: widget.token, embedded: true),
          ],
        );
      default:
        return const SizedBox.shrink();
    }
  }
}
