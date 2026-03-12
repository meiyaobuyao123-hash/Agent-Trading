import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../app.dart';
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
        title: Text('删除钱包', style: TextStyle(color: c.textPrimary, fontWeight: FontWeight.w700)),
        content: Text('确定删除 "${wallet.name}" 吗？密钥将从设备中移除。',
            style: TextStyle(color: c.textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('取消', style: TextStyle(color: c.textSecondary)),
          ),
          TextButton(
            onPressed: () {
              WalletService.instance.deleteWallet(wallet.id);
              Navigator.pop(ctx);
            },
            child: Text('删除', style: TextStyle(color: c.danger)),
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
              Text('我的钱包', style: TextStyle(
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
                  _wallets.isEmpty ? '未导入' : '${_wallets.length} 个',
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
                '导入钱包后，Agent 可以代你自动执行交易策略',
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
                              child: Text('默认', style: TextStyle(
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
                        content: Text('地址已复制', style: TextStyle(color: c.textPrimary)),
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
                _wallets.isEmpty ? '导入钱包' : '添加钱包',
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
