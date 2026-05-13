import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../app.dart';
import '../../l10n/app_localizations.dart';
import '../../providers/locale_provider.dart';
import '../../services/wallet_service.dart';
import '../../services/auth_service.dart';
import '../../services/credit_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/wallet_import_sheet.dart';
import '../credit/credit_page.dart';
import '../auth/login_page.dart';
import '../../services/push_notification_service.dart';

// ═══════════════════════════════════════════════════════════════════
// R59.1 — 「我的」页 iOS Settings 范式重做
//
// 设计原则:
// 1. Apple-ID 风格账户 header(非卡片,直接显示在顶部)
// 2. Hero 算力余额卡(渐变 mint + 大字数字 + inline buttons)
// 3. Grouped list section:多个 row 共享一个圆角白卡 + 内部细线分割
// 4. 登出移到底部"危险区域"
//
// 旧 _SettingItem / _ToggleItem / _AccountIdentityCard / _CreditBalanceCard
// / _SectionLabel 已全部撤掉,改用统一的 _GroupedSection + _GroupedRow + _GroupedToggleRow。
// ═══════════════════════════════════════════════════════════════════

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  bool _notifNewCoin = false;
  bool _notifHotCoin = false;
  bool _notifAgent = false;

  @override
  void initState() {
    super.initState();
    _loadNotifSettings();
    AuthService.instance.addListener(_onAuthChanged);
    CreditService.instance.addListener(_onCreditChanged);
    if (AuthService.instance.isLoggedIn) {
      CreditService.instance.fetchBalance();
    }
  }

  @override
  void dispose() {
    AuthService.instance.removeListener(_onAuthChanged);
    CreditService.instance.removeListener(_onCreditChanged);
    super.dispose();
  }

  void _onAuthChanged() {
    if (!mounted) return;
    setState(() {});
    if (AuthService.instance.isLoggedIn) {
      CreditService.instance.fetchBalance();
    }
  }

  void _onCreditChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _loadNotifSettings() async {
    final prefs = await SharedPreferences.getInstance();
    if (mounted) {
      setState(() {
        _notifNewCoin = prefs.getBool('notif_new_coin') ?? false;
        _notifHotCoin = prefs.getBool('notif_hot_coin') ?? false;
        _notifAgent = prefs.getBool('notif_agent') ?? false;
      });
    }
  }

  Future<void> _onToggleNotif(String key, bool value) async {
    if (value) {
      try {
        await _requestPushPermission();
      } catch (_) {}
    }
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(key, value);
    if (mounted) {
      setState(() {
        switch (key) {
          case 'notif_new_coin': _notifNewCoin = value; break;
          case 'notif_hot_coin': _notifHotCoin = value; break;
          case 'notif_agent': _notifAgent = value; break;
        }
      });
    }
  }

  Future<void> _requestPushPermission() async {
    try {
      await PushNotificationService.initialize();
    } catch (e) {
      debugPrint('[Push] Permission request failed: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;

    return Scaffold(
      backgroundColor: c.bg,
      body: CustomScrollView(
        slivers: [
          // ── 顶部 AppBar(透明,跟下面 header 顺接)──
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
          SliverToBoxAdapter(child: _buildBody(context)),
        ],
      ),
    );
  }

  Widget _buildBody(BuildContext context) {
    final isLoggedIn = AuthService.instance.isLoggedIn;
    if (!isLoggedIn) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: 8),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16),
            child: _LoginPromptCard(),
          ),
          const SizedBox(height: 24),
          ..._buildCommonTail(context),
        ],
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // 1. Apple-ID 风格账户 header
        _AccountHeader(),
        const SizedBox(height: 16),
        // 2. Hero 算力余额卡
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 16),
          child: _HeroCreditCard(),
        ),
        const SizedBox(height: 28),
        // 3. 我的钱包 section
        const _WalletSection(),
        const SizedBox(height: 24),
        // 4. 通知设置 section
        _GroupedSection(
          title: S.of(context).notificationSettings,
          rows: [
            _GroupedToggleRow(
              icon: Icons.bolt_rounded,
              iconColor: const Color(0xFFF59E0B),
              title: S.of(context).newCoinPush,
              subtitle: S.of(context).newCoinPushDesc,
              value: _notifNewCoin,
              onChanged: (v) => _onToggleNotif('notif_new_coin', v),
            ),
            _GroupedToggleRow(
              icon: Icons.local_fire_department_rounded,
              iconColor: const Color(0xFFEF4444),
              title: S.of(context).hotCoinAlert,
              subtitle: S.of(context).hotCoinAlertDesc,
              value: _notifHotCoin,
              onChanged: (v) => _onToggleNotif('notif_hot_coin', v),
            ),
            _GroupedToggleRow(
              icon: Icons.smart_toy_rounded,
              iconColor: const Color(0xFF8B5CF6),
              title: S.of(context).agentNotification,
              subtitle: S.of(context).agentNotificationDesc,
              value: _notifAgent,
              onChanged: (v) => _onToggleNotif('notif_agent', v),
            ),
          ],
        ),
        const SizedBox(height: 24),
        // 5. 外观 + 关于 — 跟未登录态共用
        ..._buildCommonTail(context),
        // 6. 底部危险区域 — 登出
        const SizedBox(height: 16),
        _GroupedSection(
          rows: [
            _DangerLogoutRow(onTap: _confirmLogout),
          ],
        ),
        const SizedBox(height: 40),
      ],
    );
  }

  List<Widget> _buildCommonTail(BuildContext context) {
    return [
      _GroupedSection(
        title: S.of(context).appearanceSettings,
        rows: [
          _GroupedRow(
            icon: context.isDark
                ? Icons.dark_mode_rounded
                : Icons.light_mode_rounded,
            iconColor: const Color(0xFF6366F1),
            title: S.of(context).darkMode,
            trailingText: context.isDark
                ? S.of(context).darkModeOn
                : S.of(context).darkModeOff,
            onTap: () => themeNotifier.toggle(),
          ),
          _GroupedRow(
            icon: Icons.language_rounded,
            iconColor: const Color(0xFF14B8A6),
            title: S.of(context).language,
            trailingText: LocaleProvider.displayName(localeProvider.locale),
            onTap: () => _showLanguagePicker(context),
          ),
        ],
      ),
      const SizedBox(height: 24),
      _GroupedSection(
        title: S.of(context).about,
        rows: [
          _GroupedRow(
            icon: Icons.info_outline_rounded,
            iconColor: const Color(0xFF3B82F6),
            title: S.of(context).version,
            trailingText: 'v1.0.0',
          ),
          _GroupedRow(
            icon: Icons.data_object_rounded,
            iconColor: const Color(0xFF8B5CF6),
            title: S.of(context).dataSource,
            trailingText: 'pump.fun · OKX',
          ),
          _GroupedRow(
            icon: Icons.warning_amber_rounded,
            iconColor: const Color(0xFFEF4444),
            title: S.of(context).riskWarning,
            onTap: () => _showRiskDisclaimer(context),
          ),
        ],
      ),
    ];
  }

  Future<void> _confirmLogout() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('确认登出?'),
        content: const Text('登出后下次启动需要重新登录'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('登出',
                style: TextStyle(color: Color(0xFFEF4444))),
          ),
        ],
      ),
    );
    if (confirm == true) {
      await AuthService.instance.logout();
    }
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
            _languageOption(ctx, c, null, S.of(context).followSystem),
            _languageOption(ctx, c, const Locale('zh'), '中文'),
            _languageOption(ctx, c, const Locale('en'), 'English'),
            _languageOption(ctx, c, const Locale('ja'), '日本語'),
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

// ═══════════════════════════════════════════════════════════════════
// R59.1 · 顶部 Apple-ID 风格账户 Header(非卡片,占顶部一段)
// ═══════════════════════════════════════════════════════════════════
class _AccountHeader extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final email = AuthService.instance.email ?? '';
    final displayName = AuthService.instance.displayName;
    final initial = email.isNotEmpty ? email[0].toUpperCase() : '?';

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 8),
      child: Row(
        children: [
          // 56px 圆形 gradient 头像
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [c.primary, c.primary.withValues(alpha: 0.65)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(28),
              boxShadow: [
                BoxShadow(
                  color: c.primary.withValues(alpha: 0.2),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            alignment: Alignment.center,
            child: Text(
              initial,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 22,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (displayName != null && displayName.isNotEmpty) ...[
                  Text(
                    displayName,
                    style: TextStyle(
                      color: c.textPrimary,
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -0.2,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    email,
                    style: TextStyle(
                      color: c.textSecondary,
                      fontSize: 13,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ] else ...[
                  Text(
                    email,
                    style: TextStyle(
                      color: c.textPrimary,
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
// R59.1 · Hero 算力余额卡 — gradient mint + 大字数字 + 2 inline button
// ═══════════════════════════════════════════════════════════════════
class _HeroCreditCard extends StatelessWidget {
  const _HeroCreditCard();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final balance = CreditService.instance.balance;
    final balanceUsd = balance?.balanceUsd ?? 0.0;
    final isLow = balance != null && balanceUsd < 1.0;
    final isCritical = balance != null && balanceUsd < 0.01;

    // < $0.01 显示 4 位,否则 2 位
    final balanceStr = balanceUsd < 0.01
        ? balanceUsd.toStringAsFixed(4)
        : balanceUsd.toStringAsFixed(2);

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: isLow
              ? [const Color(0xFFFEF2F2), const Color(0xFFFFF7ED)]
              : [const Color(0xFFECFDF5), const Color(0xFFF0FDFA)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isLow
              ? const Color(0xFFEF4444).withValues(alpha: 0.18)
              : const Color(0xFF10B981).withValues(alpha: 0.18),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 顶部 label
          Row(children: [
            Icon(
              Icons.bolt_rounded,
              size: 16,
              color: isLow
                  ? const Color(0xFFEF4444)
                  : const Color(0xFF10B981),
            ),
            const SizedBox(width: 6),
            Text(
              '算力余额',
              style: TextStyle(
                color: c.textSecondary,
                fontSize: 13,
                fontWeight: FontWeight.w500,
                letterSpacing: 0.2,
              ),
            ),
            if (isCritical) ...[
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFFEF4444).withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text(
                  '余额不足',
                  style: TextStyle(
                    color: Color(0xFFEF4444),
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ]),
          const SizedBox(height: 12),
          // 主数字
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                '\$$balanceStr',
                style: TextStyle(
                  color: isLow
                      ? const Color(0xFFEF4444)
                      : c.textPrimary,
                  fontSize: 32,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.8,
                  fontFeatures: const [
                    FontFeature.tabularFigures(),
                  ],
                ),
              ),
              const SizedBox(width: 6),
              Text(
                'USD',
                style: TextStyle(
                  color: c.textTertiary,
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // 2 inline action buttons
          Row(children: [
            Expanded(
              child: _HeroActionButton(
                label: isLow ? '立即充值' : '充值',
                icon: Icons.add_circle_outline_rounded,
                primary: true,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const CreditPage()),
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _HeroActionButton(
                label: '流水',
                icon: Icons.receipt_long_outlined,
                primary: false,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const CreditPage()),
                ),
              ),
            ),
          ]),
        ],
      ),
    );
  }
}

class _HeroActionButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool primary;
  final VoidCallback onTap;
  const _HeroActionButton({
    required this.label,
    required this.icon,
    required this.primary,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Material(
      color: primary ? c.primary : Colors.white,
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 11),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(10),
            border: primary
                ? null
                : Border.all(color: c.glassBorder, width: 1),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 16,
                color: primary ? Colors.white : c.textPrimary,
              ),
              const SizedBox(width: 6),
              Text(
                label,
                style: TextStyle(
                  color: primary ? Colors.white : c.textPrimary,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
// R59.1 · 通用 Grouped Section(替代旧 _SectionLabel + 独立卡)
// ═══════════════════════════════════════════════════════════════════
class _GroupedSection extends StatelessWidget {
  final String? title;
  final List<Widget> rows;
  const _GroupedSection({this.title, required this.rows});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (title != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
            child: Text(
              title!,
              style: TextStyle(
                color: c.textSecondary,
                fontSize: 13,
                fontWeight: FontWeight.w500,
                letterSpacing: 0.3,
              ),
            ),
          ),
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(14),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.04),
                blurRadius: 2,
                offset: const Offset(0, 1),
              ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(14),
            child: Column(
              children: _withDividers(context, rows),
            ),
          ),
        ),
      ],
    );
  }

  static List<Widget> _withDividers(BuildContext context, List<Widget> rows) {
    final out = <Widget>[];
    for (var i = 0; i < rows.length; i++) {
      out.add(rows[i]);
      if (i < rows.length - 1) {
        out.add(Container(
          height: 0.5,
          margin: const EdgeInsets.only(left: 52),
          color: const Color(0xFFE5E7EB),
        ));
      }
    }
    return out;
  }
}

// ═══════════════════════════════════════════════════════════════════
// R59.1 · Grouped Row(section 内单行,跟 iOS Settings 一致)
// ═══════════════════════════════════════════════════════════════════
class _GroupedRow extends StatelessWidget {
  final IconData icon;
  final Color? iconColor;
  final String title;
  final String? subtitle;
  final String? trailingText;
  final Widget? trailing;
  final VoidCallback? onTap;
  const _GroupedRow({
    required this.icon,
    this.iconColor,
    required this.title,
    this.subtitle,
    this.trailingText,
    this.trailing,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final iconC = iconColor ?? c.primary;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
          child: Row(
            children: [
              // Icon tint background
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  color: iconC.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(7),
                ),
                alignment: Alignment.center,
                child: Icon(icon, size: 17, color: iconC),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        color: c.textPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    if (subtitle != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        subtitle!,
                        style: TextStyle(
                          color: c.textSecondary,
                          fontSize: 12,
                          height: 1.3,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (trailing != null)
                trailing!
              else if (trailingText != null)
                Padding(
                  padding: const EdgeInsets.only(left: 6),
                  child: Text(
                    trailingText!,
                    style: TextStyle(
                      color: c.textTertiary,
                      fontSize: 13,
                    ),
                  ),
                ),
              if (onTap != null && trailing == null) ...[
                const SizedBox(width: 4),
                Icon(
                  Icons.chevron_right_rounded,
                  color: c.textTertiary,
                  size: 18,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
// R59.1 · Grouped Toggle Row(section 内的 switch 行)
// ═══════════════════════════════════════════════════════════════════
class _GroupedToggleRow extends StatelessWidget {
  final IconData icon;
  final Color? iconColor;
  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;
  const _GroupedToggleRow({
    required this.icon,
    this.iconColor,
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final iconC = iconColor ?? c.primary;

    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: iconC.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(7),
            ),
            alignment: Alignment.center,
            child: Icon(icon, size: 17, color: iconC),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    color: c.textPrimary,
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: TextStyle(
                    color: c.textSecondary,
                    fontSize: 12,
                    height: 1.3,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 4),
          Transform.scale(
            scale: 0.85,
            child: Switch(
              value: value,
              onChanged: onChanged,
              activeThumbColor: Colors.white,
              activeTrackColor: c.primary,
              inactiveThumbColor: Colors.white,
              inactiveTrackColor: const Color(0xFFE5E7EB),
            ),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
// R59.1 · 底部"危险区域" — 登出
// ═══════════════════════════════════════════════════════════════════
class _DangerLogoutRow extends StatelessWidget {
  final VoidCallback onTap;
  const _DangerLogoutRow({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 14),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: const [
              Icon(
                Icons.logout_rounded,
                size: 16,
                color: Color(0xFFEF4444),
              ),
              SizedBox(width: 6),
              Text(
                '登出',
                style: TextStyle(
                  color: Color(0xFFEF4444),
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
// R59.1 · 钱包 Section(替代旧 _WalletCard 重蓝 banner)
// ═══════════════════════════════════════════════════════════════════
class _WalletSection extends StatefulWidget {
  const _WalletSection();

  @override
  State<_WalletSection> createState() => _WalletSectionState();
}

class _WalletSectionState extends State<_WalletSection> {
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
        title: Text(S.of(ctx).deleteWallet,
            style: TextStyle(color: c.textPrimary, fontWeight: FontWeight.w700)),
        content: Text(S.of(ctx).deleteWalletConfirm(wallet.name),
            style: TextStyle(color: c.textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(S.of(ctx).cancel,
                style: TextStyle(color: c.textSecondary)),
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

    final rows = <Widget>[];

    if (_wallets.isEmpty) {
      // 未导入态:placeholder 行 + 导入引导行
      rows.add(_GroupedRow(
        icon: Icons.account_balance_wallet_outlined,
        iconColor: const Color(0xFF6B7280),
        title: '还没导入钱包',
        subtitle: '导入后 Agent 可代你自动执行交易策略',
        trailingText: '未导入',
      ));
      rows.add(Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _openImport,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
            child: Row(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    color: c.primary.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(7),
                  ),
                  alignment: Alignment.center,
                  child: Icon(Icons.add_rounded, size: 17, color: c.primary),
                ),
                const SizedBox(width: 12),
                Text(
                  '导入钱包',
                  style: TextStyle(
                    color: c.primary,
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                Icon(Icons.chevron_right_rounded,
                    color: c.textTertiary, size: 18),
              ],
            ),
          ),
        ),
      ));
    } else {
      // 已导入态:每个钱包一行
      for (final w in _wallets) {
        rows.add(_WalletRow(
          wallet: w,
          chainColor: _chainColor(w.chain),
          chainLabel: _chainLabel(w.chain),
          onSetDefault: w.isDefault
              ? null
              : () => WalletService.instance.setDefault(w.id),
          onDelete: () => _confirmDelete(w),
        ));
      }
      // 末行:添加钱包
      rows.add(Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _openImport,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
            child: Row(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    color: c.primary.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(7),
                  ),
                  alignment: Alignment.center,
                  child: Icon(Icons.add_rounded, size: 17, color: c.primary),
                ),
                const SizedBox(width: 12),
                Text(
                  '添加钱包',
                  style: TextStyle(
                    color: c.primary,
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                Icon(Icons.chevron_right_rounded,
                    color: c.textTertiary, size: 18),
              ],
            ),
          ),
        ),
      ));
    }

    return _GroupedSection(title: S.of(context).myWallets, rows: rows);
  }
}

class _WalletRow extends StatelessWidget {
  final UserWallet wallet;
  final Color chainColor;
  final String chainLabel;
  final VoidCallback? onSetDefault;
  final VoidCallback onDelete;
  const _WalletRow({
    required this.wallet,
    required this.chainColor,
    required this.chainLabel,
    required this.onSetDefault,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final addrShort =
        '${wallet.address.substring(0, 6)}...${wallet.address.substring(wallet.address.length - 4)}';

    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 12, 8, 12),
      child: Row(
        children: [
          // 链 chip(28x28)
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: chainColor.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(7),
            ),
            alignment: Alignment.center,
            child: Text(
              chainLabel,
              style: TextStyle(
                color: chainColor,
                fontSize: 9,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.2,
              ),
            ),
          ),
          const SizedBox(width: 12),
          // 名称 + 地址
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Flexible(
                    child: Text(
                      wallet.name,
                      style: TextStyle(
                        color: c.textPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w500,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  if (wallet.isDefault) ...[
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(
                        color: c.primary.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        S.of(context).defaultLabel,
                        style: TextStyle(
                          color: c.primary,
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ],
                ]),
                const SizedBox(height: 2),
                Text(
                  addrShort,
                  style: TextStyle(
                    color: c.textTertiary,
                    fontSize: 12,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ],
            ),
          ),
          // 操作:复制 + 设默认 + 删除
          IconButton(
            iconSize: 16,
            visualDensity: VisualDensity.compact,
            padding: const EdgeInsets.all(6),
            constraints: const BoxConstraints(),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: wallet.address));
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                content: Text(S.of(context).addressCopied),
                behavior: SnackBarBehavior.floating,
                duration: const Duration(seconds: 1),
              ));
            },
            icon: Icon(Icons.copy_rounded,
                color: c.textTertiary, size: 16),
          ),
          if (onSetDefault != null)
            IconButton(
              iconSize: 16,
              visualDensity: VisualDensity.compact,
              padding: const EdgeInsets.all(6),
              constraints: const BoxConstraints(),
              onPressed: onSetDefault,
              icon: Icon(Icons.star_border_rounded,
                  color: c.textTertiary, size: 18),
            ),
          IconButton(
            iconSize: 16,
            visualDensity: VisualDensity.compact,
            padding: const EdgeInsets.all(6),
            constraints: const BoxConstraints(),
            onPressed: onDelete,
            icon: Icon(Icons.delete_outline_rounded,
                color: c.danger.withValues(alpha: 0.7), size: 16),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
// R59 · 未登录:登录/注册引导卡(顶部) — 保留 R59 设计,微调阴影
// ═══════════════════════════════════════════════════════════════════
class _LoginPromptCard extends StatelessWidget {
  const _LoginPromptCard();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            c.primary.withValues(alpha: 0.12),
            c.primary.withValues(alpha: 0.04),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: c.primary.withValues(alpha: 0.22), width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(Icons.account_circle_rounded, color: c.primary, size: 24),
            const SizedBox(width: 8),
            Text(
              '欢迎回来',
              style: TextStyle(
                color: c.textPrimary,
                fontSize: 17,
                fontWeight: FontWeight.w700,
              ),
            ),
          ]),
          const SizedBox(height: 8),
          Text(
            '登录后解锁 Agent 自动交易、算力充值、推送通知',
            style: TextStyle(color: c.textSecondary, fontSize: 13, height: 1.5),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    fullscreenDialog: true,
                    builder: (ctx) => LoginPage(
                      onLoggedIn: () => Navigator.of(ctx).pop(),
                      onClose: () => Navigator.of(ctx).pop(),
                    ),
                  ),
                );
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: c.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
                elevation: 0,
              ),
              child: const Text('登录 / 注册',
                  style:
                      TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            ),
          ),
        ],
      ),
    );
  }
}
