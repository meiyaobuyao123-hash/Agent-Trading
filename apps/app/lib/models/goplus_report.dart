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

  int get dangerCount => items.where((i) => i.status == SecurityStatus.danger).length;
  int get warningCount => items.where((i) => i.status == SecurityStatus.warning).length;

  List<SecurityItem> get items => [
        SecurityItem(
          key: 'honeypot',
          value: isHoneypot ? 'danger' : 'safe',
          status: isHoneypot ? SecurityStatus.danger : SecurityStatus.safe,
        ),
        SecurityItem(
          key: 'open_source',
          value: isOpenSource ? 'yes' : 'no',
          status: isOpenSource ? SecurityStatus.safe : SecurityStatus.warning,
        ),
        SecurityItem(
          key: 'buy_tax',
          value: '${buyTax.toStringAsFixed(1)}%',
          status: buyTax > 10
              ? SecurityStatus.danger
              : buyTax > 5
                  ? SecurityStatus.warning
                  : SecurityStatus.safe,
        ),
        SecurityItem(
          key: 'sell_tax',
          value: '${sellTax.toStringAsFixed(1)}%',
          status: sellTax > 10
              ? SecurityStatus.danger
              : sellTax > 5
                  ? SecurityStatus.warning
                  : SecurityStatus.safe,
        ),
        SecurityItem(
          key: 'top10_concentration',
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
  final String key;   // identifier for i18n resolution
  final String value;
  final SecurityStatus status;
  const SecurityItem({required this.key, required this.value, required this.status});
}

enum SecurityStatus { safe, warning, danger }
