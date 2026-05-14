import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
  // R59.4 — 删 3 个 fake 通知 toggle(后端 0 接 user preference,纯 dead UI)
  //          相关 _notif* state / _loadNotifSettings / _onToggleNotif /
  //          _requestPushPermission / push_notification_service import 全清。
  //          真要做 per-user 推送 → R60+ 加 user_notification_preferences 表 +
  //          后端 cron 真接通后再恢复 UI。

  @override
  void initState() {
    super.initState();
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

  @override
  Widget build(BuildContext context) {
    final c = context.colors;

    return Scaffold(
      backgroundColor: c.bg,
      body: CustomScrollView(
        slivers: [
          // R59.3:AppBar 简化 — 去掉 BackdropFilter blur(light page 没东西 blur)
          SliverAppBar(
            pinned: true,
            backgroundColor: c.bg,
            elevation: 0,
            scrolledUnderElevation: 0,
            title: Text(
              S.of(context).profileTitle,
              style: TextStyle(
                color: c.textPrimary,
                fontSize: 28,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.5,
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

    // R59.3 — 加 stagger fade-in 动效:每个 section 延迟 70ms 入场
    // R59.4 — 删「通知设置」section(3 个 toggle 是 dead UI,后端未接 user preference)
    final commonTail = _buildCommonTail(context);
    final tailCount = commonTail.length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // 1. Premium Hero(融合身份+算力)
        _StaggeredFadeIn(
          index: 0,
          child: const Padding(
            padding: EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: _HeroAccountCard(),
          ),
        ),
        const SizedBox(height: 24),
        // 2. 我的钱包 single-card hero
        _StaggeredFadeIn(
          index: 1,
          child: const _WalletSection(),
        ),
        const SizedBox(height: 24),
        // 3. 外观/语言/关于 sections — staggered
        for (int i = 0; i < tailCount; i++)
          tailCount > 0 && commonTail[i] is _GroupedSection
              ? _StaggeredFadeIn(index: 2 + i, child: commonTail[i])
              : commonTail[i],
        // 4. 底部登出
        const SizedBox(height: 16),
        _StaggeredFadeIn(
          index: 2 + tailCount,
          child: _DangerLogoutCard(onTap: _confirmLogout),
        ),
        const SizedBox(height: 28),
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
// R59.2 · Premium Hero Card — 融合身份 + 算力,深紫 radial gradient
//         + Liquid Glass 高光层 + specular highlights + 微光粒子
// ═══════════════════════════════════════════════════════════════════
class _HeroAccountCard extends StatelessWidget {
  const _HeroAccountCard();

  @override
  Widget build(BuildContext context) {
    final email = AuthService.instance.email ?? '';
    final displayName = AuthService.instance.displayName;
    final initial = email.isNotEmpty ? email[0].toUpperCase() : '?';

    final balance = CreditService.instance.balance;
    final balanceUsd = balance?.balanceUsd ?? 0.0;
    final isLow = balance != null && balanceUsd < 1.0;
    final isCritical = balance != null && balanceUsd < 0.01;
    final balanceStr = balanceUsd < 0.01
        ? balanceUsd.toStringAsFixed(4)
        : balanceUsd.toStringAsFixed(2);

    return ClipRRect(
      borderRadius: BorderRadius.circular(22),
      child: Stack(
        children: [
          // ── 底层:深紫 → 深蓝 radial gradient(R59.3 简化两段)──
          Container(
            decoration: const BoxDecoration(
              gradient: RadialGradient(
                center: Alignment(0.85, -0.5),
                radius: 1.6,
                colors: [
                  Color(0xFF2A1F5C),  // 深紫
                  Color(0xFF0F1729),  // 深蓝
                ],
              ),
            ),
          ),
          // ── Liquid Glass 高光层 ──
          Positioned.fill(
            child: CustomPaint(
              painter: _LiquidGlassHighlightPainter(),
            ),
          ),
          // ── 顶层内容 ──
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // 身份段
                Row(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFF34D399), Color(0xFF06B6D4)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(24),
                        boxShadow: [
                          BoxShadow(
                            color: const Color(0xFF06B6D4)
                                .withValues(alpha: 0.4),
                            blurRadius: 12,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        initial,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            displayName != null && displayName.isNotEmpty
                                ? displayName
                                : email.split('@').first,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                              letterSpacing: -0.2,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 3),
                          Text(
                            email,
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.5),
                              fontSize: 11,
                              letterSpacing: 0.1,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                    // R59.3:删 PRO badge(fake data),留白
                  ],
                ),
                const SizedBox(height: 22),
                // 渐变 divider
                Container(
                  height: 1,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        Colors.white.withValues(alpha: 0.0),
                        Colors.white.withValues(alpha: 0.12),
                        Colors.white.withValues(alpha: 0.0),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 18),
                // 算力段
                Row(
                  children: [
                    Icon(
                      Icons.bolt_rounded,
                      size: 13,
                      color: const Color(0xFF34D399)
                          .withValues(alpha: 0.9),
                    ),
                    const SizedBox(width: 5),
                    Text(
                      '算力余额',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.6),
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                        letterSpacing: 0.6,
                      ),
                    ),
                    const Spacer(),
                    if (isCritical)
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 7, vertical: 3),
                        decoration: BoxDecoration(
                          color: const Color(0xFFEF4444)
                              .withValues(alpha: 0.18),
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(
                            color: const Color(0xFFEF4444)
                                .withValues(alpha: 0.4),
                            width: 0.5,
                          ),
                        ),
                        child: const Text(
                          '余额不足',
                          style: TextStyle(
                            color: Color(0xFFFCA5A5),
                            fontSize: 9.5,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 0.3,
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    // R59.3:纯白大数字(去 ShaderMask 渐变)— 反差最大可读性最好
                    Text(
                      '\$$balanceStr',
                      style: TextStyle(
                        color: isLow
                            ? const Color(0xFFFCA5A5)
                            : Colors.white,
                        fontSize: 40,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -1.2,
                        height: 0.95,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    ),
                    const SizedBox(width: 7),
                    Padding(
                      padding: const EdgeInsets.only(bottom: 5),
                      child: Text(
                        'USD',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.4),
                          fontSize: 11.5,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 0.6,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                // 2 action buttons
                Row(
                  children: [
                    Expanded(
                      child: _HeroActionButton(
                        label: isLow ? '立即充值' : '充值',
                        icon: Icons.add_rounded,
                        primary: true,
                        onTap: () => Navigator.of(context).push(
                          MaterialPageRoute(
                              builder: (_) => const CreditPage()),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _HeroActionButton(
                        label: '流水',
                        icon: Icons.receipt_long_outlined,
                        primary: false,
                        onTap: () => Navigator.of(context).push(
                          MaterialPageRoute(
                              builder: (_) => const CreditPage()),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
// R59.2 · Liquid Glass 高光层(specular highlights + edge bleed + 粒子)
// 静态渲染,shouldRepaint=false,低端设备无性能担忧
// ═══════════════════════════════════════════════════════════════════
class _LiquidGlassHighlightPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    // 1. Specular highlight 椭圆 — 右上角光源(R59.3:alpha 0.22 → 0.16)
    final specularRect = Rect.fromCircle(
      center: Offset(size.width * 0.85, size.height * -0.1),
      radius: size.width * 0.6,
    );
    final specularPaint = Paint()
      ..shader = RadialGradient(
        colors: [
          Colors.white.withValues(alpha: 0.16),
          Colors.white.withValues(alpha: 0.0),
        ],
        stops: const [0.0, 1.0],
      ).createShader(specularRect);
    canvas.drawOval(specularRect, specularPaint);

    // R59.3:删 cyan glow(跟 specular 重复,克制)
    // 2. 静态微光粒子(12 个,克制版)
    final particlePaint = Paint()..style = PaintingStyle.fill;
    const positions = <List<double>>[
      [0.18, 0.22, 1.4, 0.10],   // [xRatio, yRatio, radius, alpha]
      [0.42, 0.38, 1.6, 0.12],
      [0.65, 0.18, 1.2, 0.09],
      [0.78, 0.55, 1.8, 0.11],
      [0.32, 0.72, 1.5, 0.10],
      [0.55, 0.88, 1.3, 0.08],
      [0.88, 0.72, 1.4, 0.10],
      [0.12, 0.58, 1.6, 0.09],
      [0.48, 0.55, 1.5, 0.10],
      [0.72, 0.32, 1.4, 0.11],
      [0.22, 0.45, 1.2, 0.09],
      [0.92, 0.45, 1.7, 0.10],
    ];
    for (final p in positions) {
      particlePaint.color = Colors.white.withValues(alpha: p[3]);
      canvas.drawCircle(
        Offset(size.width * p[0], size.height * p[1]),
        p[2],
        particlePaint,
      );
    }

    // 3. Edge bleed — 顶部 highlight gradient
    final topGlow = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          Colors.white.withValues(alpha: 0.14),
          Colors.white.withValues(alpha: 0.0),
        ],
        stops: const [0.0, 0.18],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));
    canvas.drawRect(
        Rect.fromLTWH(0, 0, size.width, size.height), topGlow);

    // 4. Inner highlight 1px stroke 顶部
    final stroke = Paint()
      ..color = Colors.white.withValues(alpha: 0.16)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.8;
    canvas.drawLine(
      const Offset(20, 0.4),
      Offset(size.width - 20, 0.4),
      stroke,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
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
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(11),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            gradient: primary
                ? const LinearGradient(
                    colors: [Color(0xFF34D399), Color(0xFF10B981)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  )
                : LinearGradient(
                    colors: [
                      Colors.white.withValues(alpha: 0.10),
                      Colors.white.withValues(alpha: 0.04),
                    ],
                  ),
            borderRadius: BorderRadius.circular(11),
            border: primary
                ? null
                : Border.all(
                    color: Colors.white.withValues(alpha: 0.18),
                    width: 0.8,
                  ),
            boxShadow: primary
                ? [
                    BoxShadow(
                      color: const Color(0xFF10B981).withValues(alpha: 0.22),
                      blurRadius: 10,
                      offset: const Offset(0, 3),
                    ),
                  ]
                : null,
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 15,
                color: Colors.white,
              ),
              const SizedBox(width: 5),
              Text(
                label,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 13.5,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.2,
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
              // R59.2 — 圆形 gradient chip
              Container(
                width: 30,
                height: 30,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [iconC, iconC.withValues(alpha: 0.72)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(15),
                  boxShadow: [
                    BoxShadow(
                      color: iconC.withValues(alpha: 0.2),
                      blurRadius: 5,
                      offset: const Offset(0, 1.5),
                    ),
                  ],
                ),
                alignment: Alignment.center,
                child: Icon(icon, size: 15, color: Colors.white),
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
                        fontSize: 14.5,
                        fontWeight: FontWeight.w600,
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

// R59.4 — _GroupedToggleRow 删除(随通知 section 一起撤,本页无 switch 行)
//          将来 R60+ user_notification_preferences 真接通时再恢复。

// ═══════════════════════════════════════════════════════════════════
// R59.2 · 底部"危险区域" — 独立卡 + red tint bg
// ═══════════════════════════════════════════════════════════════════
class _DangerLogoutCard extends StatelessWidget {
  final VoidCallback onTap;
  const _DangerLogoutCard({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(14),
          child: Container(
            decoration: BoxDecoration(
              color: const Color(0xFFFEF2F2),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: const Color(0xFFEF4444).withValues(alpha: 0.15),
                width: 0.8,
              ),
            ),
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
                    fontSize: 14.5,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.2,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
// R59.2 · Wallet Hero Card — 默认钱包单卡(crypto wallet 卡片视觉)
//         多钱包列表移到 _WalletManagementPage 子页
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

  void _openManagement() {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => const _WalletManagementPage(),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;

    if (_wallets.isEmpty) {
      // 未导入 — empty state 卡(虚线 + 主色引导)
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: _openImport,
            borderRadius: BorderRadius.circular(14),
            child: DottedBorderBox(
              child: Padding(
                padding: const EdgeInsets.symmetric(
                    horizontal: 18, vertical: 22),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Container(
                        width: 32,
                        height: 32,
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: [
                              c.primary.withValues(alpha: 0.18),
                              c.primary.withValues(alpha: 0.08),
                            ],
                          ),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        alignment: Alignment.center,
                        child: Icon(
                          Icons.account_balance_wallet_outlined,
                          color: c.primary,
                          size: 17,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Text(
                        '我的钱包',
                        style: TextStyle(
                          color: c.textPrimary,
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const Spacer(),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: c.textTertiary.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(5),
                        ),
                        child: Text(
                          '未导入',
                          style: TextStyle(
                            color: c.textTertiary,
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0.3,
                          ),
                        ),
                      ),
                    ]),
                    const SizedBox(height: 12),
                    Text(
                      '导入钱包后 Agent 可代你自动执行交易策略',
                      style: TextStyle(
                        color: c.textSecondary,
                        fontSize: 12.5,
                        height: 1.4,
                      ),
                    ),
                    const SizedBox(height: 14),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 9),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            c.primary,
                            c.primary.withValues(alpha: 0.82),
                          ],
                        ),
                        borderRadius: BorderRadius.circular(9),
                        boxShadow: [
                          BoxShadow(
                            color: c.primary.withValues(alpha: 0.25),
                            blurRadius: 8,
                            offset: const Offset(0, 3),
                          ),
                        ],
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: const [
                          Icon(Icons.add_rounded,
                              color: Colors.white, size: 16),
                          SizedBox(width: 4),
                          Text(
                            '导入钱包',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 13.5,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    }

    // 已导入 — 找默认钱包(无默认则用第一个)
    final defaultWallet = _wallets.firstWhere(
      (w) => w.isDefault,
      orElse: () => _wallets.first,
    );
    final otherCount = _wallets.length - 1;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _openManagement,
          borderRadius: BorderRadius.circular(16),
          child: _WalletHeroCard(
            wallet: defaultWallet,
            otherCount: otherCount,
          ),
        ),
      ),
    );
  }
}

// 默认钱包 Hero 卡 — crypto wallet 卡片视觉
class _WalletHeroCard extends StatelessWidget {
  final UserWallet wallet;
  final int otherCount;
  const _WalletHeroCard({required this.wallet, required this.otherCount});

  Color get _chainColor => switch (wallet.chain) {
        'solana' => const Color(0xFF9945FF),
        'eth' => const Color(0xFF627EEA),
        'bsc' => const Color(0xFFF3BA2F),
        'base' => const Color(0xFF0052FF),
        _ => const Color(0xFF3B82F6),
      };

  String get _chainLabel => switch (wallet.chain) {
        'solana' => 'Solana',
        'eth' => 'Ethereum',
        'bsc' => 'BSC',
        'base' => 'Base',
        _ => wallet.chain.toUpperCase(),
      };

  String get _chainShort => switch (wallet.chain) {
        'solana' => 'SOL',
        'eth' => 'ETH',
        'bsc' => 'BSC',
        'base' => 'BASE',
        _ => wallet.chain.toUpperCase(),
      };

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final addr = wallet.address;
    final addrShort = addr.length > 12
        ? '${addr.substring(0, 6)}...${addr.substring(addr.length - 4)}'
        : addr;

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: _chainColor.withValues(alpha: 0.08),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 2,
            offset: const Offset(0, 1),
          ),
        ],
        border: Border.all(
          color: _chainColor.withValues(alpha: 0.10),
          width: 0.8,
        ),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: Stack(
          children: [
            // 右上角链色 ambient glow
            Positioned(
              top: -40,
              right: -40,
              child: Container(
                width: 140,
                height: 140,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      _chainColor.withValues(alpha: 0.10),
                      _chainColor.withValues(alpha: 0.0),
                    ],
                  ),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 14, 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    // 链 chip — 圆形 gradient
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            _chainColor,
                            _chainColor.withValues(alpha: 0.7),
                          ],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(18),
                        boxShadow: [
                          BoxShadow(
                            color: _chainColor.withValues(alpha: 0.3),
                            blurRadius: 6,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        _chainShort,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0.3,
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
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
                                  fontSize: 15.5,
                                  fontWeight: FontWeight.w700,
                                  letterSpacing: -0.2,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            const SizedBox(width: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color:
                                    _chainColor.withValues(alpha: 0.10),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                '默认',
                                style: TextStyle(
                                  color: _chainColor,
                                  fontSize: 9,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: 0.3,
                                ),
                              ),
                            ),
                          ]),
                          const SizedBox(height: 2),
                          Text(
                            _chainLabel,
                            style: TextStyle(
                              color: c.textTertiary,
                              fontSize: 11,
                              fontWeight: FontWeight.w500,
                              letterSpacing: 0.2,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Icon(
                      Icons.arrow_forward_ios_rounded,
                      size: 13,
                      color: c.textTertiary.withValues(alpha: 0.6),
                    ),
                  ]),
                  const SizedBox(height: 14),
                  // 地址
                  GestureDetector(
                    onTap: () {
                      Clipboard.setData(ClipboardData(text: addr));
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                        content: Text(S.of(context).addressCopied),
                        behavior: SnackBarBehavior.floating,
                        duration: const Duration(seconds: 1),
                      ));
                    },
                    child: Container(
                      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF9FAFB),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: const Color(0xFFE5E7EB),
                          width: 0.5,
                        ),
                      ),
                      child: Row(children: [
                        Icon(Icons.tag_rounded,
                            size: 12, color: c.textTertiary),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            addrShort,
                            style: TextStyle(
                              color: c.textSecondary,
                              fontSize: 12.5,
                              fontFeatures: const [
                                FontFeature.tabularFigures()
                              ],
                              letterSpacing: 0.2,
                            ),
                          ),
                        ),
                        Icon(Icons.content_copy_rounded,
                            size: 12, color: c.textTertiary),
                      ]),
                    ),
                  ),
                  if (otherCount > 0) ...[
                    const SizedBox(height: 12),
                    Container(
                      height: 0.5,
                      color: const Color(0xFFE5E7EB),
                    ),
                    const SizedBox(height: 10),
                    Row(children: [
                      Icon(
                        Icons.account_balance_wallet_outlined,
                        size: 13,
                        color: c.textTertiary,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        '管理 ${_wallets(context)} 个钱包',
                        style: TextStyle(
                          color: c.textSecondary,
                          fontSize: 12.5,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      const Spacer(),
                      Text(
                        '查看全部',
                        style: TextStyle(
                          color: c.primary,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(width: 3),
                      Icon(
                        Icons.arrow_forward_rounded,
                        size: 12,
                        color: c.primary,
                      ),
                    ]),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  int _wallets(BuildContext context) => otherCount + 1;
}

// 虚线 box — 未导入 empty state 用
class DottedBorderBox extends StatelessWidget {
  final Widget child;
  const DottedBorderBox({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return CustomPaint(
      painter: _DottedBorderPainter(color: c.primary.withValues(alpha: 0.35)),
      child: Container(
        decoration: BoxDecoration(
          color: c.primary.withValues(alpha: 0.025),
          borderRadius: BorderRadius.circular(14),
        ),
        child: child,
      ),
    );
  }
}

class _DottedBorderPainter extends CustomPainter {
  final Color color;
  _DottedBorderPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;
    const dashWidth = 4.0;
    const dashGap = 4.0;
    final rrect = RRect.fromRectAndRadius(
      Offset.zero & size,
      const Radius.circular(14),
    );
    final path = Path()..addRRect(rrect);
    final metrics = path.computeMetrics();
    for (final metric in metrics) {
      double dist = 0.0;
      while (dist < metric.length) {
        final next = dist + dashWidth;
        canvas.drawPath(
          metric.extractPath(dist, next.clamp(0, metric.length)),
          paint,
        );
        dist = next + dashGap;
      }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// ═══════════════════════════════════════════════════════════════════
// R59.2 · 钱包管理子页(多钱包列表 — 设默认 / 复制 / 删除)
// ═══════════════════════════════════════════════════════════════════
class _WalletManagementPage extends StatefulWidget {
  const _WalletManagementPage();

  @override
  State<_WalletManagementPage> createState() =>
      _WalletManagementPageState();
}

class _WalletManagementPageState extends State<_WalletManagementPage> {
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

  String _chainShort(String chain) => switch (chain) {
        'solana' => 'SOL',
        'eth' => 'ETH',
        'bsc' => 'BSC',
        'base' => 'BASE',
        _ => chain.toUpperCase(),
      };

  @override
  Widget build(BuildContext context) {
    final c = context.colors;

    return Scaffold(
      backgroundColor: c.bg,
      appBar: AppBar(
        backgroundColor: c.bg,
        elevation: 0,
        title: Text(
          '钱包管理',
          style: TextStyle(
            color: c.textPrimary,
            fontSize: 17,
            fontWeight: FontWeight.w700,
          ),
        ),
        leading: IconButton(
          icon: Icon(Icons.arrow_back_ios_new_rounded,
              color: c.textPrimary, size: 18),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          for (final w in _wallets) ...[
            _WalletManageRow(
              wallet: w,
              chainColor: _chainColor(w.chain),
              chainShort: _chainShort(w.chain),
              onSetDefault: w.isDefault
                  ? null
                  : () => WalletService.instance.setDefault(w.id),
              onDelete: () => _confirmDelete(w),
            ),
            const SizedBox(height: 10),
          ],
          const SizedBox(height: 8),
          Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: _openImport,
              borderRadius: BorderRadius.circular(12),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 14),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      c.primary,
                      c.primary.withValues(alpha: 0.85),
                    ],
                  ),
                  borderRadius: BorderRadius.circular(12),
                  boxShadow: [
                    BoxShadow(
                      color: c.primary.withValues(alpha: 0.3),
                      blurRadius: 10,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: const [
                    Icon(Icons.add_rounded, color: Colors.white, size: 18),
                    SizedBox(width: 6),
                    Text(
                      '导入新钱包',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _WalletManageRow extends StatelessWidget {
  final UserWallet wallet;
  final Color chainColor;
  final String chainShort;
  final VoidCallback? onSetDefault;
  final VoidCallback onDelete;
  const _WalletManageRow({
    required this.wallet,
    required this.chainColor,
    required this.chainShort,
    required this.onSetDefault,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final addrShort =
        '${wallet.address.substring(0, 6)}...${wallet.address.substring(wallet.address.length - 4)}';

    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 6, 12),
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
        border: Border.all(
          color: const Color(0xFFE5E7EB),
          width: 0.5,
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [chainColor, chainColor.withValues(alpha: 0.7)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(18),
            ),
            alignment: Alignment.center,
            child: Text(
              chainShort,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 10,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.3,
              ),
            ),
          ),
          const SizedBox(width: 12),
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
                        fontWeight: FontWeight.w600,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  if (wallet.isDefault) ...[
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: chainColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        S.of(context).defaultLabel,
                        style: TextStyle(
                          color: chainColor,
                          fontSize: 9,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ],
                ]),
                const SizedBox(height: 3),
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

// ═══════════════════════════════════════════════════════════════════
// R59.3 · Staggered fade-in 入场动效
// 每个 section 按 index 延迟 70ms 入场,fade 0→1 + slide-up 6px
// 280ms easeOutCubic
// ═══════════════════════════════════════════════════════════════════
class _StaggeredFadeIn extends StatelessWidget {
  final int index;
  final Widget child;
  const _StaggeredFadeIn({required this.index, required this.child});

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: Duration(milliseconds: 280 + (index * 70)),
      curve: Interval(
        (index * 70) / (280 + index * 70).clamp(1, 10000),
        1.0,
        curve: Curves.easeOutCubic,
      ),
      builder: (context, t, child_) {
        return Opacity(
          opacity: t.clamp(0.0, 1.0),
          child: Transform.translate(
            offset: Offset(0, (1 - t) * 6),
            child: child_,
          ),
        );
      },
      child: child,
    );
  }
}
