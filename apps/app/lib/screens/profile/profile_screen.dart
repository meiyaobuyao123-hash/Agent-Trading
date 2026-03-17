import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../app.dart';
import '../../l10n/app_localizations.dart';
import '../../providers/locale_provider.dart';
import '../../services/wallet_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/wallet_import_sheet.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: CustomScrollView(
        slivers: [
          // ── 顶部 AppBar ──────────────────────
          SliverAppBar(
            pinned: true,
            backgroundColor: Colors.transparent,
            flexibleSpace: ClipRect(
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 24, sigmaY: 24),
                child: Container(color: Colors.transparent),
              ),
            ),
            title: Text(
              S.of(context).profileTitle,
              style: TextStyle(
                color: c.textPrimary,
                fontSize: 20,
                fontWeight: FontWeight.w600,
                letterSpacing: -0.3,
              ),
            ),
          ),

          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ── 钱包绑定卡 ─────────────────
                  const _WalletCard(),
                  const SizedBox(height: 16),

                  // ── 通知设置 ───────────────────
                  _SectionLabel(label: S.of(context).notificationSettings),
                  const SizedBox(height: 8),
                  _ToggleItem(
                    icon: Icons.bolt_rounded,
                    title: S.of(context).newCoinPush,
                    subtitle: S.of(context).newCoinPushDesc,
                    value: true,
                    onChanged: (_) => _showComingSoon(context),
                  ),
                  _ToggleItem(
                    icon: Icons.local_fire_department_rounded,
                    title: S.of(context).hotCoinAlert,
                    subtitle: S.of(context).hotCoinAlertDesc,
                    value: false,
                    onChanged: (_) => _showComingSoon(context),
                  ),
                  _ToggleItem(
                    icon: Icons.smart_toy_rounded,
                    title: S.of(context).agentNotification,
                    subtitle: S.of(context).agentNotificationDesc,
                    value: true,
                    onChanged: (_) => _showComingSoon(context),
                  ),

                  const SizedBox(height: 16),

                  // ── 外观设置 ───────────────────
                  _SectionLabel(label: S.of(context).appearanceSettings),
                  const SizedBox(height: 8),
                  _SettingItem(
                    icon: context.isDark
                        ? Icons.dark_mode_rounded
                        : Icons.light_mode_rounded,
                    title: S.of(context).darkMode,
                    value: context.isDark ? S.of(context).darkModeOn : S.of(context).darkModeOff,
                    onTap: () => themeNotifier.toggle(),
                  ),

                  const SizedBox(height: 16),

                  // ── 语言设置 ───────────────────
                  _SectionLabel(label: S.of(context).languageSettings),
                  const SizedBox(height: 8),
                  _SettingItem(
                    icon: Icons.language_rounded,
                    title: S.of(context).language,
                    value: LocaleProvider.displayName(localeProvider.locale),
                    onTap: () => _showLanguagePicker(context),
                  ),

                  const SizedBox(height: 16),

                  // ── 关于 ───────────────────────
                  _SectionLabel(label: S.of(context).about),
                  const SizedBox(height: 8),
                  _SettingItem(
                    icon: Icons.info_outline_rounded,
                    title: S.of(context).version,
                    value: 'v1.0.0',
                    onTap: null,
                  ),
                  _SettingItem(
                    icon: Icons.data_object_rounded,
                    title: S.of(context).dataSource,
                    value: 'pump.fun · OKX · Binance',
                    onTap: null,
                  ),
                  _SettingItem(
                    icon: Icons.warning_amber_rounded,
                    title: S.of(context).riskWarning,
                    value: '',
                    onTap: () => _showRiskDisclaimer(context),
                  ),

                  const SizedBox(height: 32),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showComingSoon(BuildContext context) {
    final c = context.colors;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          S.of(context).comingSoon,
          style: TextStyle(color: c.textPrimary),
        ),
        backgroundColor: c.cardGlass,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  void _showRiskDisclaimer(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogCtx) {
        final dc = dialogCtx.colors;
        return AlertDialog(
          backgroundColor: dc.bg,
          title: Text(S.of(dialogCtx).riskWarning,
              style: TextStyle(
                  color: dc.textPrimary, fontWeight: FontWeight.w700)),
          content: Text(
            S.of(dialogCtx).riskContent,
            style: TextStyle(color: dc.textSecondary, height: 1.6),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogCtx),
              child:
                  Text(S.of(dialogCtx).iKnow, style: TextStyle(color: dc.primary)),
            ),
          ],
        );
      },
    );
  }

  void _showLanguagePicker(BuildContext context) {
    final c = context.colors;
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
        decoration: BoxDecoration(
          color: c.bgSecondary,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 36, height: 4,
              decoration: BoxDecoration(
                color: c.textTertiary.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 16),
            Text(S.of(context).languageSettings,
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: c.textPrimary)),
            const SizedBox(height: 14),
            // Follow system
            _languageOption(ctx, c, null, S.of(context).followSystem),
            // zh
            _languageOption(ctx, c, const Locale('zh'), '中文'),
            // en
            _languageOption(ctx, c, const Locale('en'), 'English'),
            // ja
            _languageOption(ctx, c, const Locale('ja'), '日本語'),
            // ko
            _languageOption(ctx, c, const Locale('ko'), '한국어'),
          ],
        ),
      ),
    );
  }

  Widget _languageOption(BuildContext ctx, AppColorScheme c, Locale? locale, String label) {
    final isSelected = localeProvider.locale?.languageCode == locale?.languageCode;
    return GestureDetector(
      onTap: () {
        localeProvider.setLocale(locale);
        Navigator.pop(ctx);
      },
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
        margin: const EdgeInsets.only(bottom: 4),
        decoration: BoxDecoration(
          color: isSelected ? c.primary.withValues(alpha: 0.12) : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(
          children: [
            Text(label, style: TextStyle(
              fontSize: 15, color: isSelected ? c.primary : c.textPrimary,
              fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
            )),
            const Spacer(),
            if (isSelected) Icon(Icons.check_rounded, color: c.primary, size: 20),
          ],
        ),
      ),
    );
  }
}

// ─── 钱包管理卡 ──────────────────────────────────────
class _WalletCard extends StatefulWidget {
  const _WalletCard();

  @override
  State<_WalletCard> createState() => _WalletCardState();
}

class _WalletCardState extends State<_WalletCard> {
  List<UserWallet> _wallets = [];

  @override
  void initState() {
    super.initState();
    _loadWallets();
    WalletService.instance.addListener(_loadWallets);
  }

  @override
  void dispose() {
    WalletService.instance.removeListener(_loadWallets);
    super.dispose();
  }

  void _loadWallets() {
    if (mounted) setState(() => _wallets = WalletService.instance.wallets);
  }

  Future<void> _openImport() async {
    final wallet = await showWalletImportSheet(context);
    if (wallet != null) _loadWallets();
  }

  void _confirmDelete(UserWallet wallet) {
    final c = context.colors;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: c.bg,
        title: Text(S.of(ctx).deleteWallet, style: TextStyle(color: c.textPrimary, fontWeight: FontWeight.w700)),
        content: Text(S.of(ctx).deleteWalletConfirm(wallet.name),
            style: TextStyle(color: c.textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(S.of(ctx).cancel, style: TextStyle(color: c.textSecondary)),
          ),
          TextButton(
            onPressed: () {
              WalletService.instance.deleteWallet(wallet.id);
              Navigator.pop(ctx);
            },
            child: Text(S.of(ctx).delete, style: TextStyle(color: c.danger)),
          ),
        ],
      ),
    );
  }

  Color _chainColor(String chain) => switch (chain) {
    'solana' => const Color(0xFF9945FF),
    'eth' => const Color(0xFF627EEA),
    'bsc' => const Color(0xFFF3BA2F),
    'base' => const Color(0xFF0052FF),
    _ => const Color(0xFF3B82F6),
  };

  String _chainLabel(String chain) => switch (chain) {
    'solana' => 'SOL',
    'eth' => 'ETH',
    'bsc' => 'BSC',
    'base' => 'BASE',
    _ => chain.toUpperCase(),
  };

  @override
  Widget build(BuildContext context) {
    final c = context.colors;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: context.isDark
            ? const LinearGradient(
                colors: [Color(0xFF1A2550), Color(0xFF0D1530)],
                begin: Alignment.topLeft, end: Alignment.bottomRight,
              )
            : LinearGradient(
                colors: [
                  c.primary.withValues(alpha: 0.08),
                  c.primary.withValues(alpha: 0.03),
                ],
                begin: Alignment.topLeft, end: Alignment.bottomRight,
              ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: c.primary.withValues(alpha: 0.3), width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.account_balance_wallet_rounded, color: c.primary, size: 20),
              const SizedBox(width: 8),
              Text(S.of(context).myWallets, style: TextStyle(
                color: c.textSecondary, fontSize: 12, fontWeight: FontWeight.w500,
              )),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: _wallets.isEmpty
                      ? c.surfaceAlt
                      : c.success.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  _wallets.isEmpty ? S.of(context).notImported : S.of(context).countUnit(_wallets.length),
                  style: TextStyle(
                    color: _wallets.isEmpty ? c.textTertiary : c.success,
                    fontSize: 11, fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // 钱包列表
          if (_wallets.isEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(
                S.of(context).walletImportHint,
                style: TextStyle(color: c.textPrimary, fontSize: 14,
                    fontWeight: FontWeight.w500, height: 1.5),
              ),
            )
          else
            ...(_wallets.map((w) => Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: c.cardGlass,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: c.glassBorder, width: 0.5),
              ),
              child: Row(
                children: [
                  // 链标识
                  Container(
                    width: 28, height: 28,
                    decoration: BoxDecoration(
                      color: _chainColor(w.chain).withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    alignment: Alignment.center,
                    child: Text(_chainLabel(w.chain), style: TextStyle(
                      color: _chainColor(w.chain), fontSize: 9,
                      fontWeight: FontWeight.w800,
                    )),
                  ),
                  const SizedBox(width: 10),
                  // 名称 + 地址
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(children: [
                          Text(w.name, style: TextStyle(
                            color: c.textPrimary, fontSize: 13,
                            fontWeight: FontWeight.w600,
                          )),
                          if (w.isDefault) ...[
                            const SizedBox(width: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                              decoration: BoxDecoration(
                                color: c.primary.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(S.of(context).defaultLabel, style: TextStyle(
                                color: c.primary, fontSize: 9, fontWeight: FontWeight.w700,
                              )),
                            ),
                          ],
                        ]),
                        const SizedBox(height: 2),
                        Text(
                          '${w.address.substring(0, 6)}...${w.address.substring(w.address.length - 4)}',
                          style: TextStyle(color: c.textTertiary, fontSize: 11),
                        ),
                      ],
                    ),
                  ),
                  // 操作
                  if (!w.isDefault)
                    GestureDetector(
                      onTap: () => WalletService.instance.setDefault(w.id),
                      child: Padding(
                        padding: const EdgeInsets.all(4),
                        child: Icon(Icons.star_border_rounded,
                            color: c.textTertiary, size: 18),
                      ),
                    ),
                  GestureDetector(
                    onTap: () {
                      Clipboard.setData(ClipboardData(text: w.address));
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                        content: Text(S.of(context).addressCopied, style: TextStyle(color: c.textPrimary)),
                        backgroundColor: c.cardGlass,
                        behavior: SnackBarBehavior.floating,
                        duration: const Duration(seconds: 1),
                      ));
                    },
                    child: Padding(
                      padding: const EdgeInsets.all(4),
                      child: Icon(Icons.copy_rounded, color: c.textTertiary, size: 16),
                    ),
                  ),
                  GestureDetector(
                    onTap: () => _confirmDelete(w),
                    child: Padding(
                      padding: const EdgeInsets.all(4),
                      child: Icon(Icons.delete_outline_rounded,
                          color: c.danger.withValues(alpha: 0.6), size: 16),
                    ),
                  ),
                ],
              ),
            ))),

          // 导入按钮
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _openImport,
              icon: const Icon(Icons.add_rounded, size: 18),
              label: Text(
                _wallets.isEmpty ? S.of(context).importWallet : S.of(context).addWallet,
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: c.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                elevation: 0,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ─── Section 标签 ────────────────────────────────────
class _SectionLabel extends StatelessWidget {
  final String label;
  const _SectionLabel({required this.label});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;

    return Text(
      label,
      style: TextStyle(
        color: c.textSecondary,
        fontSize: 12,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.5,
      ),
    );
  }
}

// ─── 设置项 ──────────────────────────────────────────
class _SettingItem extends StatelessWidget {
  final IconData icon;
  final String title;
  final String value;
  final VoidCallback? onTap;
  const _SettingItem({
    required this.icon,
    required this.title,
    required this.value,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 6),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
        decoration: BoxDecoration(
          color: c.cardGlass,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: c.glassBorder, width: 0.5),
        ),
        child: Row(
          children: [
            Icon(icon, color: c.textSecondary, size: 18),
            const SizedBox(width: 12),
            Expanded(
              child: Text(title,
                  style: TextStyle(color: c.textPrimary, fontSize: 14)),
            ),
            if (value.isNotEmpty)
              Text(value,
                  style: TextStyle(color: c.textSecondary, fontSize: 13)),
            if (onTap != null) ...[
              const SizedBox(width: 4),
              Icon(Icons.chevron_right_rounded,
                  color: c.textTertiary, size: 18),
            ],
          ],
        ),
      ),
    );
  }
}

// ─── Toggle 项 ───────────────────────────────────────
class _ToggleItem extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;
  const _ToggleItem({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;

    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: c.cardGlass,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: c.glassBorder, width: 0.5),
      ),
      child: Row(
        children: [
          Icon(icon, color: c.textSecondary, size: 18),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style:
                        TextStyle(color: c.textPrimary, fontSize: 14)),
                Text(subtitle,
                    style:
                        TextStyle(color: c.textSecondary, fontSize: 11)),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeThumbColor: Colors.white,
            activeTrackColor: c.primary,
            inactiveThumbColor: c.textTertiary,
            inactiveTrackColor: c.surfaceAlt,
          ),
        ],
      ),
    );
  }
}
