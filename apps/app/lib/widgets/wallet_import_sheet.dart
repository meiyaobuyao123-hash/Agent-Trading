import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../l10n/app_localizations.dart';
import '../theme/app_colors.dart';
import '../services/wallet_service.dart';

// ══════════════════════════════════════════════════════════════
//  钱包导入底部弹窗
// ══════════════════════════════════════════════════════════════

/// 首次导入时需显示的安全声明 SharedPreferences key
const _kDisclaimerShown = 'wallet_disclaimer_shown';

/// 打开钱包导入弹窗
/// 首次调用时先弹出非托管安全声明，用户确认后才进入导入界面
Future<UserWallet?> showWalletImportSheet(BuildContext context) async {
  // 检查是否首次导入（仅首次弹出声明）
  final prefs = await SharedPreferences.getInstance();
  final alreadyShown = prefs.getBool(_kDisclaimerShown) ?? false;

  if (!alreadyShown && context.mounted) {
    // 弹出非托管安全声明弹窗
    final confirmed = await _showDisclaimerDialog(context);
    if (confirmed != true) return null; // 用户点击"取消"，终止流程

    // 记录已显示，下次不再弹出
    await prefs.setBool(_kDisclaimerShown, true);
  }

  if (!context.mounted) return null;

  return showModalBottomSheet<UserWallet>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => const _WalletImportSheet(),
  );
}

/// 非托管安全声明弹窗 — 返回 true 表示用户点击了"我已了解，继续"
Future<bool?> _showDisclaimerDialog(BuildContext context) {
  final c = context.colors;
  return showDialog<bool>(
    context: context,
    barrierDismissible: false, // 必须点击按钮才能关闭
    builder: (ctx) => AlertDialog(
      backgroundColor: c.bgSecondary,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: Row(
        children: [
          Icon(Icons.security_rounded, color: c.primary, size: 22),
          const SizedBox(width: 8),
          Text(
            S.of(ctx).securityStatement,
            style: TextStyle(
              color: c.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _disclaimerItem(
            c,
            S.of(ctx).walletDisclaimer1,
          ),
          _disclaimerItem(
            c,
            S.of(ctx).walletDisclaimer2,
          ),
          _disclaimerItem(
            c,
            S.of(ctx).walletDisclaimer3,
          ),
          _disclaimerItem(
            c,
            S.of(ctx).walletDisclaimer4,
          ),
          _disclaimerItem(
            c,
            S.of(ctx).walletDisclaimer5,
            isWarning: true,
          ),
        ],
      ),
      actions: [
        // 取消按钮
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(false),
          child: Text(
            S.of(ctx).cancel,
            style: TextStyle(color: c.textTertiary),
          ),
        ),
        // 确认按钮
        FilledButton(
          onPressed: () => Navigator.of(ctx).pop(true),
          style: FilledButton.styleFrom(
            backgroundColor: c.primary,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
            ),
          ),
          child: Text(S.of(ctx).understood),
        ),
      ],
    ),
  );
}

/// 声明弹窗中的每一条条目
Widget _disclaimerItem(AppColorScheme c, String text,
    {bool isWarning = false}) {
  return Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          isWarning ? Icons.warning_amber_rounded : Icons.check_circle_outline,
          color: isWarning ? c.warning : c.success,
          size: 16,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            text,
            style: TextStyle(
              color: c.textSecondary,
              fontSize: 13,
              height: 1.4,
            ),
          ),
        ),
      ],
    ),
  );
}

class _WalletImportSheet extends StatefulWidget {
  const _WalletImportSheet();

  @override
  State<_WalletImportSheet> createState() => _WalletImportSheetState();
}

class _WalletImportSheetState extends State<_WalletImportSheet> {
  // ── 表单状态 ──
  bool _isMnemonic = true; // true=助记词, false=私钥
  String _selectedChain = 'solana';
  final _nameCtrl = TextEditingController();
  final _secretCtrl = TextEditingController();
  bool _obscureSecret = true;
  bool _loading = false;
  String? _error;

  static const _chains = [
    {'key': 'solana', 'label': 'Solana'},
    {'key': 'eth', 'label': 'ETH'},
    {'key': 'bsc', 'label': 'BSC'},
    {'key': 'base', 'label': 'Base'},
  ];

  // 助记词模式：各链是否选中（默认全选）
  final Map<String, bool> _mnemonicChainSelected = {
    'solana': true,
    'eth': true,
    'bsc': true,
    'base': true,
  };

  @override
  void dispose() {
    _nameCtrl.dispose();
    _secretCtrl.dispose();
    super.dispose();
  }

  Future<void> _pasteFromClipboard() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    if (data?.text != null && data!.text!.isNotEmpty) {
      _secretCtrl.text = data.text!;
      setState(() => _error = null);
    } else {
      setState(() => _error = S.of(context).clipboardEmpty);
    }
  }

  Future<void> _doImport() async {
    final secret = _secretCtrl.text.trim();
    if (secret.isEmpty) {
      setState(() => _error = _isMnemonic ? S.of(context).enterMnemonic : S.of(context).enterPrivateKey);
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final svc = WalletService.instance;
      UserWallet wallet;

      if (_isMnemonic) {
        final selectedChains = _mnemonicChainSelected.entries
            .where((e) => e.value)
            .map((e) => e.key)
            .toList();
        if (selectedChains.isEmpty) {
          setState(() { _error = S.of(context).selectAtLeastOneChain; _loading = false; });
          return;
        }
        final wallets = await svc.importFromMnemonicAllChains(
          mnemonic: secret,
          name: _nameCtrl.text.trim(),
          chains: selectedChains,
        );
        wallet = wallets.first;
      } else {
        wallet = await svc.importFromPrivateKey(
          privateKey: secret,
          chain: _selectedChain,
          name: _nameCtrl.text.trim(),
        );
      }

      if (mounted) Navigator.of(context).pop(wallet);
    } on ArgumentError catch (e) {
      setState(() => _error = e.message);
    } on StateError catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = S.of(context).importFailed(e.toString()));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final bottom = MediaQuery.of(context).viewInsets.bottom;

    return Container(
      decoration: BoxDecoration(
        color: c.bgSecondary,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 16,
        bottom: bottom + 20,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ── 拖动指示条 ──
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: c.textTertiary,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),

            // ── 标题 ──
            Text(
              S.of(context).importWallet,
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: c.textPrimary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 20),

            // ── 导入方式切换 ──
            _buildToggle(c),
            const SizedBox(height: 16),

            // ── 链选择（助记词模式自动全链，私钥模式才选链）──
            if (_isMnemonic) ...[
              _buildMnemonicAllChainsHint(c),
              const SizedBox(height: 16),
            ] else ...[
              Text(
                S.of(context).selectChain,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: c.textSecondary,
                ),
              ),
              const SizedBox(height: 8),
              _buildChainChips(c),
              const SizedBox(height: 16),
            ],

            // ── 钱包名称 ──
            _buildTextField(
              controller: _nameCtrl,
              label: S.of(context).walletNameLabel,
              hint: S.of(context).walletNameHint,
              colors: c,
            ),
            const SizedBox(height: 12),

            // ── 密钥输入（含粘贴按钮） ──
            _buildSecretField(c),
            const SizedBox(height: 8),

            // ── 一键粘贴按钮 ──
            GestureDetector(
              onTap: _pasteFromClipboard,
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  color: c.primaryLight,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: c.primary.withValues(alpha: 0.3)),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.content_paste_rounded,
                        size: 16, color: c.primary),
                    const SizedBox(width: 6),
                    Text(
                      S.of(context).pasteFromClipboard,
                      style: TextStyle(
                        color: c.primary,
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),

            // ── 错误提示 ──
            if (_error != null)
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: c.dangerLight,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  _error!,
                  style: TextStyle(color: c.danger, fontSize: 13),
                ),
              ),

            const SizedBox(height: 16),

            // ── 导入按钮 ──
            SizedBox(
              height: 48,
              child: ElevatedButton(
                onPressed: _loading ? null : _doImport,
                style: ElevatedButton.styleFrom(
                  backgroundColor: c.primary,
                  foregroundColor: c.textInverse,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  disabledBackgroundColor:
                      c.primary.withValues(alpha: 0.4),
                ),
                child: _loading
                    ? SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor:
                              AlwaysStoppedAnimation(c.textInverse),
                        ),
                      )
                    : Text(
                        S.of(context).importWallet,
                        style: const TextStyle(
                            fontSize: 16, fontWeight: FontWeight.w600),
                      ),
              ),
            ),
            const SizedBox(height: 16),

            // ── 安全提示 ──
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: c.warningLight,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: c.warning.withValues(alpha: 0.3),
                ),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.shield_outlined,
                      size: 18, color: c.warning),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      S.of(context).securityNote,
                      style: TextStyle(
                        fontSize: 12,
                        color: c.textSecondary,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── 导入方式切换 ────────────────────────────────────────────

  Widget _buildToggle(AppColorScheme c) {
    return Container(
      height: 40,
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: c.border),
      ),
      child: Row(
        children: [
          Expanded(
            child: _toggleItem(
              label: S.of(context).mnemonic,
              selected: _isMnemonic,
              onTap: () => setState(() => _isMnemonic = true),
              colors: c,
            ),
          ),
          Expanded(
            child: _toggleItem(
              label: S.of(context).privateKey,
              selected: !_isMnemonic,
              onTap: () => setState(() => _isMnemonic = false),
              colors: c,
            ),
          ),
        ],
      ),
    );
  }

  Widget _toggleItem({
    required String label,
    required bool selected,
    required VoidCallback onTap,
    required AppColorScheme colors,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        alignment: Alignment.center,
        margin: const EdgeInsets.all(3),
        decoration: BoxDecoration(
          color: selected ? colors.primary : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: selected ? colors.textInverse : colors.textSecondary,
          ),
        ),
      ),
    );
  }

  // ── 助记词模式：全链勾选提示 ────────────────────────────────

  Widget _buildMnemonicAllChainsHint(AppColorScheme c) {
    const chainIcons = {
      'solana': '◎',
      'eth': 'Ξ',
      'bsc': '⬡',
      'base': '🔵',
    };
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: c.primaryLight,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: c.primary.withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.account_tree_rounded, size: 14, color: c.primary),
              const SizedBox(width: 6),
              Text(
                S.of(context).mnemonicMultiChain,
                style: TextStyle(
                  fontSize: 12,
                  color: c.primary,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ..._chains.map((chain) {
            final key = chain['key']!;
            final label = chain['label']!;
            final selected = _mnemonicChainSelected[key] ?? true;
            return InkWell(
              onTap: () => setState(
                  () => _mnemonicChainSelected[key] = !selected),
              borderRadius: BorderRadius.circular(6),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    SizedBox(
                      width: 20,
                      height: 20,
                      child: Checkbox(
                        value: selected,
                        onChanged: (v) => setState(
                            () => _mnemonicChainSelected[key] = v ?? true),
                        activeColor: c.primary,
                        side: BorderSide(color: c.border, width: 1.5),
                        materialTapTargetSize:
                            MaterialTapTargetSize.shrinkWrap,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      chainIcons[key] ?? '',
                      style: const TextStyle(fontSize: 14),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      label,
                      style: TextStyle(
                        fontSize: 13,
                        color: selected
                            ? c.textPrimary
                            : c.textTertiary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const Spacer(),
                    Text(
                      key == 'solana'
                          ? "m/44'/501'/0'/0'"
                          : "m/44'/60'/0'/0/0",
                      style: TextStyle(
                        fontSize: 10,
                        color: c.textTertiary,
                        fontFamily: 'monospace',
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
        ],
      ),
    );
  }

  // ── 链选择芯片 ──────────────────────────────────────────────

  Widget _buildChainChips(AppColorScheme c) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: _chains.map((chain) {
        final key = chain['key']!;
        final selected = _selectedChain == key;
        return ChoiceChip(
          label: Text(chain['label']!),
          selected: selected,
          onSelected: (_) => setState(() => _selectedChain = key),
          selectedColor: c.primary.withValues(alpha: 0.2),
          backgroundColor: c.surface,
          side: BorderSide(
            color: selected ? c.primary : c.border,
          ),
          labelStyle: TextStyle(
            color: selected ? c.primary : c.textSecondary,
            fontWeight: FontWeight.w600,
            fontSize: 13,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        );
      }).toList(),
    );
  }

  // ── 输入框 ──────────────────────────────────────────────────

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    required String hint,
    required AppColorScheme colors,
  }) {
    return TextField(
      controller: controller,
      style: TextStyle(color: colors.textPrimary, fontSize: 14),
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        labelStyle: TextStyle(color: colors.textTertiary, fontSize: 13),
        hintStyle: TextStyle(color: colors.textTertiary, fontSize: 13),
        filled: true,
        fillColor: colors.surface,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: colors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: colors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: colors.primary, width: 1.5),
        ),
      ),
    );
  }

  Widget _buildSecretField(AppColorScheme c) {
    return TextField(
      controller: _secretCtrl,
      obscureText: _obscureSecret,
      maxLines: _obscureSecret ? 1 : 3,
      style: TextStyle(
        color: c.textPrimary,
        fontSize: 14,
        fontFamily: 'monospace',
      ),
      decoration: InputDecoration(
        labelText: _isMnemonic ? S.of(context).mnemonic : S.of(context).privateKey,
        hintText: _isMnemonic
            ? S.of(context).mnemonicHint
            : S.of(context).privateKeyHint,
        labelStyle: TextStyle(color: c.textTertiary, fontSize: 13),
        hintStyle: TextStyle(color: c.textTertiary, fontSize: 12),
        filled: true,
        fillColor: c.surface,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: c.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: c.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: c.primary, width: 1.5),
        ),
        suffixIcon: IconButton(
          icon: Icon(
            _obscureSecret ? Icons.visibility_off : Icons.visibility,
            color: c.iconInactive,
            size: 20,
          ),
          onPressed: () =>
              setState(() => _obscureSecret = !_obscureSecret),
        ),
      ),
    );
  }
}
