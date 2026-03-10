/// GoPlus 安全检测报告
class GoPlusReport {
  final bool isHoneypot;
  final bool isOpenSource;
  final double buyTax;
  final double sellTax;
  final bool cannotSellAll;
  final int holderCount;
  final double top10HolderPct;

  const GoPlusReport({
    required this.isHoneypot,
    required this.isOpenSource,
    required this.buyTax,
    required this.sellTax,
    required this.cannotSellAll,
    required this.holderCount,
    required this.top10HolderPct,
  });

  bool get overallRisk =>
      isHoneypot || cannotSellAll || buyTax > 10 || sellTax > 10 || top10HolderPct > 80;

  bool get hasTaxRisk => buyTax > 5.0 || sellTax > 5.0;
  bool get hasConcentrationRisk => top10HolderPct > 80;

  List<SecurityItem> get items => [
        SecurityItem(
          label: '蜜罐检测',
          value: isHoneypot ? '危险' : '安全',
          status: isHoneypot ? SecurityStatus.danger : SecurityStatus.safe,
        ),
        SecurityItem(
          label: '合约开源',
          value: isOpenSource ? '是' : '否',
          status: isOpenSource ? SecurityStatus.safe : SecurityStatus.warning,
        ),
        SecurityItem(
          label: '买入税',
          value: '${buyTax.toStringAsFixed(1)}%',
          status: buyTax > 10
              ? SecurityStatus.danger
              : buyTax > 5
                  ? SecurityStatus.warning
                  : SecurityStatus.safe,
        ),
        SecurityItem(
          label: '卖出税',
          value: '${sellTax.toStringAsFixed(1)}%',
          status: sellTax > 10
              ? SecurityStatus.danger
              : sellTax > 5
                  ? SecurityStatus.warning
                  : SecurityStatus.safe,
        ),
        SecurityItem(
          label: 'Top10 集中度',
          value: '${top10HolderPct.toStringAsFixed(1)}%',
          status: top10HolderPct > 80
              ? SecurityStatus.danger
              : top10HolderPct > 50
                  ? SecurityStatus.warning
                  : SecurityStatus.safe,
        ),
      ];
}

class SecurityItem {
  final String label;
  final String value;
  final SecurityStatus status;
  const SecurityItem({required this.label, required this.value, required this.status});
}

enum SecurityStatus { safe, warning, danger }
