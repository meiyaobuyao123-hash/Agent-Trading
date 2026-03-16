import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../theme/app_colors.dart';

/// 全局免责声明页 — 首次启动必须接受，否则无法进入 App
class DisclaimerPage extends StatefulWidget {
  final VoidCallback onAccepted;
  const DisclaimerPage({super.key, required this.onAccepted});

  @override
  State<DisclaimerPage> createState() => _DisclaimerPageState();
}

class _DisclaimerPageState extends State<DisclaimerPage> {
  final ScrollController _scrollCtrl = ScrollController();
  bool _scrolledToBottom = false;
  bool _checked = false;

  @override
  void initState() {
    super.initState();
    _scrollCtrl.addListener(_onScroll);
    // 首帧渲染后检查：若内容不需要滚动（大屏幕/内容较短），直接标记已到底
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        final maxScroll = _scrollCtrl.position.maxScrollExtent;
        if (maxScroll <= 0) {
          setState(() => _scrolledToBottom = true);
        }
      }
    });
  }

  void _onScroll() {
    if (!_scrolledToBottom) {
      final maxScroll = _scrollCtrl.position.maxScrollExtent;
      final current = _scrollCtrl.offset;
      if (current >= maxScroll - 40) {
        setState(() => _scrolledToBottom = true);
      }
    }
  }

  @override
  void dispose() {
    _scrollCtrl.dispose();
    super.dispose();
  }

  Future<void> _accept() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('app_global_disclaimer_v1', true);
    widget.onAccepted();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final canAccept = _scrolledToBottom && _checked;

    return Scaffold(
      backgroundColor: c.bg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 32),
              // 标题
              Center(
                child: Column(
                  children: [
                    Container(
                      width: 56,
                      height: 56,
                      decoration: BoxDecoration(
                        color: c.primary.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Icon(Icons.gavel_rounded, color: c.primary, size: 28),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      '使用须知 · Terms of Use',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                        color: c.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '请仔细阅读并滑到底部后方可继续',
                      style: TextStyle(fontSize: 13, color: c.textSecondary),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // 正文滚动区域
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    color: c.cardGlass,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: c.glassBorder),
                  ),
                  child: SingleChildScrollView(
                    controller: _scrollCtrl,
                    padding: const EdgeInsets.all(20),
                    child: _buildContent(c),
                  ),
                ),
              ),

              const SizedBox(height: 16),

              // 勾选同意
              GestureDetector(
                onTap: () => setState(() => _checked = !_checked),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: 22,
                      height: 22,
                      child: Checkbox(
                        value: _checked,
                        onChanged: (v) => setState(() => _checked = v ?? false),
                        activeColor: c.primary,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        '我已年满18岁，已阅读并理解上述全部条款，同意本应用的使用规则。\n'
                        'I am 18+, have read and understood all terms above.',
                        style: TextStyle(fontSize: 13, color: c.textSecondary, height: 1.5),
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 16),

              // 按钮
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton(
                  onPressed: canAccept ? _accept : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: canAccept ? c.primary : c.textSecondary,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                    elevation: 0,
                  ),
                  child: Text(
                    canAccept ? '同意并进入  Agree & Continue' : '请滑到底部并勾选  Scroll to bottom first',
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                  ),
                ),
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildContent(AppColorScheme c) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _section(c, '⚠️ 服务地区限制 · Geographic Restriction',
            '本应用及其后端服务不向以下地区的用户提供任何服务：\n'
            '• 中华人民共和国大陆地区（不含香港、澳门、台湾）\n\n'
            'This service is NOT available to users in:\n'
            '• Mainland China (PRC), excluding HK, Macau, and Taiwan\n\n'
            '如您位于上述地区，请立即停止使用并卸载本应用。\n'
            'If you are located in the above regions, please stop using and uninstall this app immediately.'),
        _divider(c),
        _section(c, '📊 非投资建议 · Not Investment Advice',
            '本应用提供的所有内容，包括但不限于：代币评分、信号推送、聪明钱追踪、Agent策略，'
            '均为数据工具与信息参考，不构成任何形式的投资建议、财务建议或交易推荐。\n\n'
            'All content provided by this app, including but not limited to token scoring, '
            'signal alerts, smart money tracking, and Agent strategies, is for informational '
            'purposes only and does NOT constitute investment advice, financial advice, or '
            'trading recommendations.'),
        _divider(c),
        _section(c, '🤖 Agent 自动交易风险 · Automated Trading Risk',
            '• Agent 功能执行真实区块链交易，可能导致资产损失。\n'
            '• 加密资产市场波动剧烈，过往信号表现不代表未来结果。\n'
            '• 您对所有交易结果承担全部责任。\n\n'
            '• Agent feature executes real blockchain transactions, which may result in asset loss.\n'
            '• Crypto markets are highly volatile; past performance does not guarantee future results.\n'
            '• You bear full responsibility for all trading outcomes.'),
        _divider(c),
        _section(c, '🔐 钱包安全 · Wallet Security',
            '• 本应用为非托管钱包：您的私钥/助记词仅存储在您的设备本地，服务器从不接收。\n'
            '• 如您丢失设备或忘记助记词，资产将无法找回。\n'
            '• 请务必妥善备份您的助记词至安全的离线位置。\n\n'
            '• This is a non-custodial wallet: your private key/mnemonic is stored only on '
            'your device locally; our servers never receive it.\n'
            '• Lost device or forgotten mnemonic means unrecoverable assets.\n'
            '• Please back up your mnemonic to a secure offline location.'),
        _divider(c),
        _section(c, '⚖️ 法律声明 · Legal Disclaimer',
            '本应用不受任何金融监管机构监管，不持有任何投资顾问或金融服务牌照。'
            '使用本应用即表示您理解并承担所有相关风险。本条款受适用法律管辖。\n\n'
            'This app is not regulated by any financial authority and holds no investment '
            'advisor or financial services license. By using this app, you acknowledge and '
            'accept all associated risks. These terms are governed by applicable law.'),
        _divider(c),
        _section(c, '📅 版本 · Version',
            '本免责声明最后更新于 2026年3月。\n'
            'Last updated: March 2026.'),
        const SizedBox(height: 8),
        Center(
          child: Text(
            '— 已到达底部，请勾选同意 —',
            style: TextStyle(fontSize: 12, color: c.primary),
          ),
        ),
      ],
    );
  }

  Widget _section(AppColorScheme c, String title, String body) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: TextStyle(
                  fontSize: 14, fontWeight: FontWeight.w700, color: c.textPrimary)),
          const SizedBox(height: 8),
          Text(body,
              style: TextStyle(fontSize: 13, color: c.textSecondary, height: 1.6)),
        ],
      ),
    );
  }

  Widget _divider(AppColorScheme c) {
    return Divider(color: c.glassBorder, height: 24);
  }
}
