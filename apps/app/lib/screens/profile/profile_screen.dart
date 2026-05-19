import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../app.dart';
import '../../l10n/app_localizations.dart';
import '../../providers/locale_provider.dart';
import '../../services/wallet_service.dart';
import '../../services/auth_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/wallet_import_sheet.dart';
import '../credit/credit_page.dart';
import '../auth/login_page.dart';
import '../../services/push_notification_service.dart';

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
    // R70.1 — 登录态变化时自动重 rebuild,让 Profile 在登录/登出后立即切换布局
    AuthService.instance.addListener(_onAuthChanged);
  }

  @override
  void dispose() {
    AuthService.instance.removeListener(_onAuthChanged);
    super.dispose();
  }

  void _onAuthChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _doLogout() async {
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
            child: const Text('登出', style: TextStyle(color: Color(0xFFEF4444))),
          ),
        ],
      ),
    );
    if (confirm == true) {
      await AuthService.instance.logout();
    }
  }

  void _gotoLogin() {
    Navigator.of(context).push(
      MaterialPageRoute(
        fullscreenDialog: true,
        builder: (_) => LoginPage(
          onLoggedIn: () => Navigator.of(context).pop(true),
          onClose: () => Navigator.of(context).pop(false),
        ),
      ),
    );
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
      // 用户首次开启 → 请求 iOS 推送权限
      try {
        final messenger = WidgetsBinding.instance.platformDispatcher;
        // 触发 Firebase 权限请求（如果未初始化则跳过）
        // ignore: unused_import
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
      debugPrint('[Push] Notification permission requested from user toggle');
    } catch (e) {
      debugPrint('[Push] Permission request failed: $e');
    }
  }

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
              child: _buildBody(context),
            ),
          ),
        ],
      ),
    );
  }

  /// R70.1 — 按登录态分支:
  /// - 未登录:**1 个**登录卡(顶部主色)+ 外观 / 语言 / 关于(无需账户也可用)
  /// - 已登录:身份卡(头像+邮箱,不含登出)+ 算力 + 钱包 + 通知 + 外观 / 语言 / 关于
  ///   + 底部**1 个**独立"登出"红字按钮(全局唯一登出入口,放最远防误点)
  /// 全局保证:登录按钮 ≤ 1 / 登出按钮 ≤ 1,**未登录态不出现"登出"** / **已登录态不出现"登录"**
  Widget _buildBody(BuildContext context) {
    final isLoggedIn = AuthService.instance.isLoggedIn;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── ① 顶部:登录态分支 ─────────────────────────────
        if (!isLoggedIn) ...[
          _LoginPromptCard(onTap: _gotoLogin),
          const SizedBox(height: 20),
        ] else ...[
          _AccountIdentityCard(
            email: AuthService.instance.email ?? '',
            displayName: AuthService.instance.displayName,
          ),
          const SizedBox(height: 16),
          // 算力余额(仅已登录)
          _SectionLabel(label: '账户 & 算力'),
          const SizedBox(height: 8),
          _SettingItem(
            icon: Icons.bolt_rounded,
            title: '算力余额',
            value: '充值 / 流水',
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const CreditPage()),
            ),
          ),
          const SizedBox(height: 16),

          // 钱包(仅已登录)
          const _WalletCard(),
          const SizedBox(height: 16),

          // 通知设置(仅已登录 — 推送依赖 user_id)
          _SectionLabel(label: S.of(context).notificationSettings),
          const SizedBox(height: 8),
          _ToggleItem(
            icon: Icons.bolt_rounded,
            title: S.of(context).newCoinPush,
            subtitle: S.of(context).newCoinPushDesc,
            value: _notifNewCoin,
            onChanged: (v) => _onToggleNotif('notif_new_coin', v),
          ),
          _ToggleItem(
            icon: Icons.local_fire_department_rounded,
            title: S.of(context).hotCoinAlert,
            subtitle: S.of(context).hotCoinAlertDesc,
            value: _notifHotCoin,
            onChanged: (v) => _onToggleNotif('notif_hot_coin', v),
          ),
          _ToggleItem(
            icon: Icons.smart_toy_rounded,
            title: S.of(context).agentNotification,
            subtitle: S.of(context).agentNotificationDesc,
            value: _notifAgent,
            onChanged: (v) => _onToggleNotif('notif_agent', v),
          ),
          const SizedBox(height: 16),
        ],

        // ── ② 外观(已登录 + 未登录都显示)─────────────────
        _SectionLabel(label: S.of(context).appearanceSettings),
        const SizedBox(height: 8),
        _SettingItem(
          icon: context.isDark ? Icons.dark_mode_rounded : Icons.light_mode_rounded,
          title: S.of(context).darkMode,
          value: context.isDark ? S.of(context).darkModeOn : S.of(context).darkModeOff,
          onTap: () => themeNotifier.toggle(),
        ),
        const SizedBox(height: 16),

        // ── ③ 语言 ─────────────────────────────────
        _SectionLabel(label: S.of(context).languageSettings),
        const SizedBox(height: 8),
        _SettingItem(
          icon: Icons.language_rounded,
          title: S.of(context).language,
          value: LocaleProvider.displayName(localeProvider.locale),
          onTap: () => _showLanguagePicker(context),
        ),
        const SizedBox(height: 16),

        // ── ④ 关于 ─────────────────────────────────
        _SectionLabel(label: S.of(context).about),
        const SizedBox(height: 8),
        _SettingItem(
          icon: Icons.info_outline_rounded,
          title: S.of(context).version,
          value: 'v2.0.0',
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

        // ── ⑤ 底部"登出"(仅已登录,全局唯一登出入口)──────
        if (isLoggedIn) ...[
          const SizedBox(height: 24),
          _DangerLogoutCard(onTap: _doLogout),
        ],

        const SizedBox(height: 32),
      ],
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

// ─── R70.1:登录提示卡(未登录态唯一登录入口)──────────
class _LoginPromptCard extends StatelessWidget {
  final VoidCallback onTap;
  const _LoginPromptCard({required this.onTap});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft, end: Alignment.bottomRight,
              colors: [c.primary, c.primary.withOpacity(0.78)],
            ),
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: c.primary.withOpacity(0.18),
                blurRadius: 16, offset: const Offset(0, 6),
              ),
            ],
          ),
          child: Row(children: [
            Container(
              width: 48, height: 48,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.22),
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Icon(Icons.account_circle_outlined,
                  color: Colors.white, size: 28),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text('登录 / 注册',
                      style: TextStyle(color: Colors.white,
                          fontSize: 16, fontWeight: FontWeight.w700,
                          letterSpacing: -0.2)),
                  SizedBox(height: 3),
                  Text('登录后解锁 Agent 自动交易 / 算力充值 / 钱包管理 / 推送通知',
                      style: TextStyle(color: Colors.white70,
                          fontSize: 11.5, height: 1.4)),
                ],
              ),
            ),
            const SizedBox(width: 6),
            const Icon(Icons.arrow_forward_ios_rounded,
                color: Colors.white, size: 14),
          ]),
        ),
      ),
    );
  }
}

// ─── R70.1:已登录账户身份卡(纯展示,不含登出)──────
class _AccountIdentityCard extends StatelessWidget {
  final String email;
  final String? displayName;
  const _AccountIdentityCard({required this.email, this.displayName});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final initial = (displayName?.isNotEmpty == true
        ? displayName!.substring(0, 1)
        : (email.isNotEmpty ? email.substring(0, 1) : '?')).toUpperCase();
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: c.border, width: 0.5),
      ),
      child: Row(children: [
        Container(
          width: 52, height: 52,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [c.primary, c.primary.withOpacity(0.65)],
            ),
            borderRadius: BorderRadius.circular(16),
          ),
          alignment: Alignment.center,
          child: Text(initial,
              style: const TextStyle(color: Colors.white,
                  fontSize: 22, fontWeight: FontWeight.w700)),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(displayName?.isNotEmpty == true ? displayName! : email,
                  style: TextStyle(color: c.textPrimary,
                      fontSize: 15.5, fontWeight: FontWeight.w700,
                      letterSpacing: -0.1),
                  maxLines: 1, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 3),
              Text(email,
                  style: TextStyle(color: c.textSecondary,
                      fontSize: 12, letterSpacing: 0.1),
                  maxLines: 1, overflow: TextOverflow.ellipsis),
            ],
          ),
        ),
      ]),
    );
  }
}

// ─── R70.1:底部独立"登出"红卡(已登录态唯一登出入口)──
class _DangerLogoutCard extends StatelessWidget {
  final VoidCallback onTap;
  const _DangerLogoutCard({required this.onTap});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    const danger = Color(0xFFEF4444);
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
          decoration: BoxDecoration(
            color: const Color(0xFFFEF2F2),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: danger.withOpacity(0.18), width: 0.6),
          ),
          alignment: Alignment.center,
          child: Row(mainAxisSize: MainAxisSize.min, children: const [
            Icon(Icons.logout_rounded, color: danger, size: 18),
            SizedBox(width: 8),
            Text('登出',
                style: TextStyle(color: danger,
                    fontSize: 15, fontWeight: FontWeight.w600,
                    letterSpacing: 0.2)),
          ]),
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
