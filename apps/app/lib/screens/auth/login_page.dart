import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';

import '../../services/auth_service.dart';
import '../../theme/app_colors.dart';
import 'register_page.dart';

/// R46 — Flutter 登录页
///
/// 邮箱+密码登录(已注册)+ 跳转注册 + Continue with Google(R48 待 google_sign_in 配置完)
class LoginPage extends StatefulWidget {
  /// 登录成功后回调(由 main.dart 决定 push 主 App)
  final VoidCallback onLoggedIn;
  const LoginPage({super.key, required this.onLoggedIn});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _emailCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() => _error = null);
    final email = _emailCtrl.text.trim();
    final password = _passwordCtrl.text;
    if (email.isEmpty || password.isEmpty) {
      setState(() => _error = '邮箱和密码必填');
      return;
    }
    setState(() => _submitting = true);
    final r = await AuthService.instance.login(email, password);
    if (!mounted) return;
    setState(() => _submitting = false);
    if (r.success) {
      widget.onLoggedIn();
    } else {
      setState(() => _error = r.error ?? '登录失败');
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Scaffold(
      backgroundColor: c.bg,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 40),
              // Logo
              Row(
                children: [
                  Container(
                    width: 38,
                    height: 38,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF3C82F6), Color(0xFF8B5CF6)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(CupertinoIcons.sparkles, color: Colors.white, size: 20),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    '登录 Helix',
                    style: TextStyle(color: c.textPrimary, fontSize: 22, fontWeight: FontWeight.w700),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                'Web + App 共享同一账户体系,导入的钱包跟着账户走',
                style: TextStyle(color: c.textTertiary, fontSize: 12, height: 1.5),
              ),
              const SizedBox(height: 32),

              // 邮箱
              _Field(
                label: '邮箱',
                icon: CupertinoIcons.mail,
                child: TextField(
                  controller: _emailCtrl,
                  keyboardType: TextInputType.emailAddress,
                  textInputAction: TextInputAction.next,
                  autocorrect: false,
                  style: TextStyle(color: c.textPrimary, fontSize: 14),
                  decoration: _inputDeco(c, 'you@example.com'),
                ),
              ),
              const SizedBox(height: 14),
              _Field(
                label: '密码',
                icon: CupertinoIcons.lock,
                child: TextField(
                  controller: _passwordCtrl,
                  obscureText: true,
                  textInputAction: TextInputAction.go,
                  onSubmitted: (_) => _submit(),
                  style: TextStyle(color: c.textPrimary, fontSize: 14),
                  decoration: _inputDeco(c, ''),
                ),
              ),

              if (_error != null) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: const Color(0x1FEF4444),
                    border: Border.all(color: const Color(0x4DEF4444)),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(children: [
                    const Icon(CupertinoIcons.exclamationmark_circle, color: Color(0xFFEF4444), size: 14),
                    const SizedBox(width: 8),
                    Expanded(child: Text(_error!, style: const TextStyle(color: Color(0xFFEF4444), fontSize: 12))),
                  ]),
                ),
              ],

              const SizedBox(height: 20),
              _PrimaryBtn(
                label: _submitting ? '登录中...' : '登录',
                loading: _submitting,
                onTap: _submitting ? null : _submit,
              ),

              const SizedBox(height: 14),
              Center(
                child: GestureDetector(
                  onTap: _submitting
                      ? null
                      : () {
                          Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => RegisterPage(onRegistered: widget.onLoggedIn),
                            ),
                          );
                        },
                  child: Text(
                    '还没账户?去注册 →',
                    style: TextStyle(
                      color: c.primary,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),

              const SizedBox(height: 32),
              Row(children: [
                Expanded(child: Container(height: 1, color: c.border)),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  child: Text('Google 登录(待启用)', style: TextStyle(color: c.textTertiary, fontSize: 11)),
                ),
                Expanded(child: Container(height: 1, color: c.border)),
              ]),
              const SizedBox(height: 14),
              _GoogleBtnPlaceholder(),

              const SizedBox(height: 28),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                decoration: BoxDecoration(
                  color: const Color(0x14FFFFFF),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(children: [
                  const Icon(CupertinoIcons.shield_lefthalf_fill, color: Color(0xFF22C55E), size: 14),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '密码 bcrypt 加密 · JWT 7 天有效 · 加密货币交易高风险,可能全损',
                      style: TextStyle(color: c.textTertiary, fontSize: 11, height: 1.5),
                    ),
                  ),
                ]),
              ),
            ],
          ),
        ),
      ),
    );
  }

  InputDecoration _inputDeco(AppColorScheme c, String hint) {
    return InputDecoration(
      hintText: hint,
      hintStyle: TextStyle(color: c.textTertiary, fontSize: 14),
      filled: true,
      fillColor: c.surface,
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide(color: c.border, width: 1),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide(color: c.border, width: 1),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide(color: c.primary, width: 1.5),
      ),
    );
  }
}

class _Field extends StatelessWidget {
  final String label;
  final IconData icon;
  final Widget child;
  const _Field({required this.label, required this.icon, required this.child});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          Icon(icon, size: 13, color: c.textSecondary),
          const SizedBox(width: 6),
          Text(label, style: TextStyle(color: c.textSecondary, fontSize: 12, fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: 6),
        child,
      ],
    );
  }
}

class _PrimaryBtn extends StatelessWidget {
  final String label;
  final bool loading;
  final VoidCallback? onTap;
  const _PrimaryBtn({required this.label, this.loading = false, this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: onTap,
        child: Container(
          height: 48,
          decoration: BoxDecoration(
            color: const Color(0xFF3C82F6),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Center(
            child: loading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : Text(
                    label,
                    style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600),
                  ),
          ),
        ),
      ),
    );
  }
}

class _GoogleBtnPlaceholder extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      height: 48,
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.7),
        border: Border.all(color: c.border),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // 简易 Google 字母 Logo
          const Text('G', style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: Color(0xFF4285F4),
          )),
          const SizedBox(width: 10),
          Text(
            'Continue with Google(待启用)',
            style: TextStyle(
              color: Colors.black.withValues(alpha: 0.45),
              fontSize: 14,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
