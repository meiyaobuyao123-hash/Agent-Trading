import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../l10n/app_localizations.dart';
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
                      S.of(context).disclaimerTitle,
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                        color: c.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      S.of(context).disclaimerScrollHint,
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
                        S.of(context).disclaimerCheckbox,
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
                    canAccept ? S.of(context).disclaimerAccept : S.of(context).disclaimerScrollFirst,
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
    final t = S.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _section(c, '\u26a0\ufe0f ${t.disclaimerGeoTitle}', t.disclaimerGeoBody),
        _divider(c),
        _section(c, '\ud83d\udcca ${t.disclaimerAdviceTitle}', t.disclaimerAdviceBody),
        _divider(c),
        _section(c, '\ud83e\udd16 ${t.disclaimerAutoTradeTitle}', t.disclaimerAutoTradeBody),
        _divider(c),
        _section(c, '\ud83d\udd10 ${t.disclaimerWalletTitle}', t.disclaimerWalletBody),
        _divider(c),
        _section(c, '\u2696\ufe0f ${t.disclaimerLegalTitle}', t.disclaimerLegalBody),
        _divider(c),
        _section(c, '\ud83d\udcc5 ${t.disclaimerVersionTitle}', t.disclaimerVersionBody),
        const SizedBox(height: 8),
        Center(
          child: Text(
            t.disclaimerReachedBottom,
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
