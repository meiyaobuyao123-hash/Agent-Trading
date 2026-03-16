/// 全局应用配置 — 通过 --dart-define 编译时注入
///
/// 开发环境（默认）:
///   flutter run
///
/// 生产环境:
///   flutter run \
///     --dart-define=DEV=false \
///     --dart-define=BACKEND_URL=https://api.your-domain.com \
///     --dart-define=SUPABASE_URL=https://xxx.supabase.co \
///     --dart-define=SUPABASE_KEY=your-anon-key
class AppConfig {
  AppConfig._();

  /// 是否开发环境
  static const bool isDev = bool.fromEnvironment(
    'DEV',
    defaultValue: true,
  );

  /// 后端 FastAPI 基础地址（不含尾部斜杠）
  static const String backendBaseUrl = String.fromEnvironment(
    'BACKEND_URL',
    defaultValue: 'http://43.156.207.26',
  );

  /// Supabase 项目 URL
  static const String supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: 'https://qmzsruqgwaqusywprxlj.supabase.co',
  );

  /// Supabase 匿名公钥（anon key）
  static const String supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_KEY',
    defaultValue: 'sb_publishable_2uL576o81fhTTuXxhTv20w_oKzjlLkS',
  );
}
