import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../theme/app_colors.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: CustomScrollView(
        slivers: [
          // ── 顶部 AppBar ──────────────────────
          const SliverAppBar(
            pinned: true,
            backgroundColor: AppColors.bg,
            title: Text(
              '我的',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 22,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.5,
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
                  const _SectionLabel(label: '交易设置'),
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
                  const _SectionLabel(label: '通知设置'),
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

                  // ── 关于 ───────────────────────
                  const _SectionLabel(label: '关于'),
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
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('该功能即将上线'),
        backgroundColor: AppColors.surface,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  void _showRiskDisclaimer(BuildContext context) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('风险提示',
          style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w700)),
        content: const Text(
          '本 App 提供的信号仅供参考，不构成投资建议。\n\n'
          'Meme 代币高度投机，存在归零风险。\n\n'
          '请根据自身风险承受能力独立决策，谨慎操作。',
          style: TextStyle(color: AppColors.textSecondary, height: 1.6),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('我知道了', style: TextStyle(color: AppColors.primary)),
          ),
        ],
      ),
    );
  }
}

// ─── 钱包绑定卡 ──────────────────────────────────────
class _WalletCard extends StatelessWidget {
  const _WalletCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF1A2550), Color(0xFF0D1530)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: AppColors.primary.withValues(alpha: 0.3),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.account_balance_wallet_rounded,
                color: AppColors.primary, size: 20),
              const SizedBox(width: 8),
              const Text(
                'Solana 钱包',
                style: TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.surfaceAlt,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: const Text(
                  '未连接',
                  style: TextStyle(color: AppColors.textTertiary, fontSize: 11),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          const Text(
            '连接钱包后，Agent 可以代你\n自动执行交易策略',
            style: TextStyle(
              color: AppColors.textPrimary,
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
                backgroundColor: AppColors.primary,
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
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '连接钱包',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.normalLight,
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Row(
                children: [
                  Icon(Icons.warning_amber_rounded,
                    color: AppColors.normal, size: 16),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '私钥仅存储于本设备，不会上传任何服务器',
                      style: TextStyle(
                        color: AppColors.normal, fontSize: 12),
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
      ),
    );
  }
}

class _ConnectOption extends StatelessWidget {
  final IconData icon;
  final String title;
  final String desc;
  const _ConnectOption({required this.icon, required this.title, required this.desc});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surfaceAlt,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(icon, color: AppColors.primary, size: 20),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                )),
              Text(desc,
                style: const TextStyle(
                  color: AppColors.textSecondary, fontSize: 12)),
            ],
          ),
          const Spacer(),
          const Text('即将开放',
            style: TextStyle(color: AppColors.textTertiary, fontSize: 11)),
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
    return Text(
      label,
      style: const TextStyle(
        color: AppColors.textSecondary,
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
    required this.icon, required this.title,
    required this.value, this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 6),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Icon(icon, color: AppColors.textSecondary, size: 18),
            const SizedBox(width: 12),
            Expanded(
              child: Text(title,
                style: const TextStyle(
                  color: AppColors.textPrimary, fontSize: 14)),
            ),
            if (value.isNotEmpty)
              Text(value,
                style: const TextStyle(
                  color: AppColors.textSecondary, fontSize: 13)),
            if (onTap != null) ...[
              const SizedBox(width: 4),
              const Icon(Icons.chevron_right_rounded,
                color: AppColors.textTertiary, size: 18),
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
    required this.icon, required this.title,
    required this.subtitle, required this.value, required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(icon, color: AppColors.textSecondary, size: 18),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                  style: const TextStyle(
                    color: AppColors.textPrimary, fontSize: 14)),
                Text(subtitle,
                  style: const TextStyle(
                    color: AppColors.textSecondary, fontSize: 11)),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeThumbColor: Colors.white,
            activeTrackColor: AppColors.primary,
            inactiveThumbColor: AppColors.textTertiary,
            inactiveTrackColor: AppColors.surfaceAlt,
          ),
        ],
      ),
    );
  }
}
