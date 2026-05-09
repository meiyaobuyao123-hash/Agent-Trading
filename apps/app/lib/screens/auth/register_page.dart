import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';

import '../../services/auth_service.dart';
import '../../theme/app_colors.dart';

/// R46 — Flutter 注册页
class RegisterPage extends StatefulWidget {
  final VoidCallback onRegistered;
  const RegisterPage({super.key, required this.onRegistered});

  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final _emailCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _displayNameCtrl = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    _displayNameCtrl.dispose();
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
    if (password.length < 6) {
      setState(() => _error = '密码至少 6 位');
      return;
    }
    setState(() => _submitting = true);
    final r = await AuthService.instance.register(
      email,
      password,
      displayName: _displayNameCtrl.text.trim().isEmpty ? null : _displayNameCtrl.text.trim(),
    );
    if (!mounted) return;
    setState(() => _submitting = false);
    if (r.success) {
      widget.onRegistered();
    } else {
      setState(() => _error = r.error ?? '注册失败');
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Scaffold(
      backgroundColor: c.bg,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: IconThemeData(color: c.textPrimary),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 8),
              Text('注册 Future Trading',
                  style: TextStyle(color: c.textPrimary, fontSize: 22, fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              Text('一个账户 · Web + App 共享 · 钱包跟着账户走',
                  style: TextStyle(color: c.textTertiary, fontSize: 12, height: 1.5)),
              const SizedBox(height: 32),

              _Field(
                label: '邮箱',
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
                label: '密码(至少 6 位)',
                child: TextField(
                  controller: _passwordCtrl,
                  obscureText: true,
                  textInputAction: TextInputAction.next,
                  style: TextStyle(color: c.textPrimary, fontSize: 14),
                  decoration: _inputDeco(c, ''),
                ),
              ),
              const SizedBox(height: 14),
              _Field(
                label: '昵称(可选)',
                child: TextField(
                  controller: _displayNameCtrl,
                  textInputAction: TextInputAction.go,
                  onSubmitted: (_) => _submit(),
                  style: TextStyle(color: c.textPrimary, fontSize: 14),
                  decoration: _inputDeco(c, '例如:wenruiwei'),
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
              Material(
                color: Colors.transparent,
                child: InkWell(
                  borderRadius: BorderRadius.circular(10),
                  onTap: _submitting ? null : _submit,
                  child: Container(
                    height: 48,
                    decoration: BoxDecoration(
                      color: const Color(0xFF3C82F6),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Center(
                      child: _submitting
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : const Text('注册并登录',
                              style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600)),
                    ),
                  ),
                ),
              ),

              const SizedBox(height: 14),
              Center(
                child: GestureDetector(
                  onTap: _submitting ? null : () => Navigator.of(context).pop(),
                  child: Text('已有账户?去登录',
                      style: TextStyle(color: c.primary, fontSize: 13, fontWeight: FontWeight.w600)),
                ),
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
  final Widget child;
  const _Field({required this.label, required this.child});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: TextStyle(color: c.textSecondary, fontSize: 12, fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        child,
      ],
    );
  }
}
