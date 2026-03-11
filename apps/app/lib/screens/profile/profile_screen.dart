import 'dart:ui';
import 'package:flutter/material.dart';
import '../../app.dart';
import '../../theme/app_colors.dart';

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
              '我的',
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

                  // ── 交易设置 ───────────────────
                  _SectionLabel(label: '交易设置'),
                  const SizedBox(height: 8),
                  _SettingItem(
                    icon: Icons.speed_rounded,
                    title: '默认滑点',
                    value: '1.0%',
                    onTap: () => _showComingSoon(context),
                  ),
                  _SettingItem(
                    icon: Icons.toll_rounded,
                    title: '优先费用',
                    value: '自动',
                    onTap: () => _showComingSoon(context),
                  ),
                  _SettingItem(
                    icon: Icons.account_balance_wallet_outlined,
                    title: '单次最大买入',
                    value: '0.5 SOL',
                    onTap: () => _showComingSoon(context),
                  ),
                  _SettingItem(
                    icon: Icons.shield_outlined,
                    title: '止损设置',
                    value: '-50%',
                    onTap: () => _showComingSoon(context),
                  ),

                  const SizedBox(height: 16),

                  // ── 通知设置 ───────────────────
                  _SectionLabel(label: '通知设置'),
                  const SizedBox(height: 8),
                  _ToggleItem(
                    icon: Icons.bolt_rounded,
                    title: '新币榜推送',
                    subtitle: '每日 08:05 推送今日 Top10',
                    value: true,
                    onChanged: (_) => _showComingSoon(context),
                  ),
                  _ToggleItem(
                    icon: Icons.local_fire_department_rounded,
                    title: '热币预警',
                    subtitle: '热度突然飙升时推送',
                    value: false,
                    onChanged: (_) => _showComingSoon(context),
                  ),
                  _ToggleItem(
                    icon: Icons.smart_toy_rounded,
                    title: 'Agent 执行通知',
                    subtitle: '策略触发自动交易时推送',
                    value: true,
                    onChanged: (_) => _showComingSoon(context),
                  ),

                  const SizedBox(height: 16),

                  // ── 外观设置 ───────────────────
                  _SectionLabel(label: '外观设置'),
                  const SizedBox(height: 8),
                  _SettingItem(
                    icon: context.isDark
                        ? Icons.dark_mode_rounded
                        : Icons.light_mode_rounded,
                    title: '深色模式',
                    value: context.isDark ? '开启' : '关闭',
                    onTap: () => themeNotifier.toggle(),
                  ),

                  const SizedBox(height: 16),

                  // ── 关于 ───────────────────────
                  _SectionLabel(label: '关于'),
                  const SizedBox(height: 8),
                  _SettingItem(
                    icon: Icons.info_outline_rounded,
                    title: '版本',
                    value: 'v1.0.0',
                    onTap: null,
                  ),
                  _SettingItem(
                    icon: Icons.data_object_rounded,
                    title: '数据来源',
                    value: 'pump.fun · OKX · Binance',
                    onTap: null,
                  ),
                  _SettingItem(
                    icon: Icons.warning_amber_rounded,
                    title: '风险提示',
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
          '该功能即将上线',
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
          title: Text('风险提示',
              style: TextStyle(
                  color: dc.textPrimary, fontWeight: FontWeight.w700)),
          content: Text(
            '本 App 提供的信号仅供参考，不构成投资建议。\n\n'
            'Meme 代币高度投机，存在归零风险。\n\n'
            '请根据自身风险承受能力独立决策，谨慎操作。',
            style: TextStyle(color: dc.textSecondary, height: 1.6),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogCtx),
              child:
                  Text('我知道了', style: TextStyle(color: dc.primary)),
            ),
          ],
        );
      },
    );
  }
}

// ─── 钱包绑定卡 ──────────────────────────────────────
class _WalletCard extends StatelessWidget {
  const _WalletCard();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: context.isDark
            ? const LinearGradient(
                colors: [Color(0xFF1A2550), Color(0xFF0D1530)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              )
            : LinearGradient(
                colors: [
                  c.primary.withValues(alpha: 0.08),
                  c.primary.withValues(alpha: 0.03),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: c.primary.withValues(alpha: 0.3),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.account_balance_wallet_rounded,
                  color: c.primary, size: 20),
              const SizedBox(width: 8),
              Text(
                'Solana 钱包',
                style: TextStyle(
                  color: c.textSecondary,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const Spacer(),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: c.surfaceAlt,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '未连接',
                  style: TextStyle(color: c.textTertiary, fontSize: 11),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            '连接钱包后，Agent 可以代你\n自动执行交易策略',
            style: TextStyle(
              color: c.textPrimary,
              fontSize: 15,
              fontWeight: FontWeight.w600,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () => _showConnectWallet(context),
              style: ElevatedButton.styleFrom(
                backgroundColor: c.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                elevation: 0,
              ),
              child: const Text(
                '导入钱包（即将开放）',
                style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showConnectWallet(BuildContext context) {
    final c = context.colors;
    showModalBottomSheet(
      context: context,
      backgroundColor: c.bg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetCtx) {
        final sc = sheetCtx.colors;
        return Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '连接钱包',
                style: TextStyle(
                  color: sc.textPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: sc.warningLight,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  children: [
                    Icon(Icons.warning_amber_rounded,
                        color: sc.warning, size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '私钥仅存储于本设备，不会上传任何服务器',
                        style:
                            TextStyle(color: sc.warning, fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              // 两种方式（占位）
              _ConnectOption(
                icon: Icons.vpn_key_rounded,
                title: '导入私钥',
                desc: '粘贴 Base58 格式私钥',
              ),
              const SizedBox(height: 8),
              _ConnectOption(
                icon: Icons.list_alt_rounded,
                title: '导入助记词',
                desc: '输入 12 / 24 个单词',
              ),
              const SizedBox(height: 20),
            ],
          ),
        );
      },
    );
  }
}

class _ConnectOption extends StatelessWidget {
  final IconData icon;
  final String title;
  final String desc;
  const _ConnectOption(
      {required this.icon, required this.title, required this.desc});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: c.cardGlass,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: c.glassBorder, width: 0.5),
      ),
      child: Row(
        children: [
          Icon(icon, color: c.primary, size: 20),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: TextStyle(
                    color: c.textPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  )),
              Text(desc,
                  style: TextStyle(color: c.textSecondary, fontSize: 12)),
            ],
          ),
          const Spacer(),
          Text('即将开放',
              style: TextStyle(color: c.textTertiary, fontSize: 11)),
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
