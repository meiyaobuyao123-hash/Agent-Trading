import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'app_colors.dart';

class AppTheme {
  AppTheme._();

  // ═══════════════════════════════════════════════
  //  Dark 主题 — 默认
  // ═══════════════════════════════════════════════
  static ThemeData get dark {
    const c = AppColorScheme.dark;
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: c.bg,
      primaryColor: c.primary,
      useMaterial3: true,

      colorScheme: ColorScheme.dark(
        primary: c.primary,
        surface: c.surface,
        error: c.danger,
        onPrimary: Colors.white,
        onSurface: c.textPrimary,
        outline: c.border,
      ),

      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: c.textPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.5,
        ),
        iconTheme: IconThemeData(color: c.textPrimary),
        systemOverlayStyle: const SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarBrightness: Brightness.dark,
          statusBarIconBrightness: Brightness.light,
        ),
      ),

      cardTheme: CardThemeData(
        color: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: const BorderRadius.all(Radius.circular(16)),
          side: BorderSide(color: c.glassBorder, width: 0.5),
        ),
      ),

      dividerTheme: DividerThemeData(
        color: c.divider,
        thickness: 0.5,
        space: 0,
      ),

      tabBarTheme: TabBarThemeData(
        labelColor: c.textPrimary,
        unselectedLabelColor: c.textTertiary,
        indicatorColor: c.primary,
        indicatorSize: TabBarIndicatorSize.label,
        labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
        unselectedLabelStyle: const TextStyle(fontSize: 13),
        dividerColor: Colors.transparent,
        overlayColor: WidgetStateProperty.resolveWith((_) => Colors.transparent),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: c.surfaceAlt,
        hintStyle: TextStyle(color: c.textTertiary, fontSize: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: c.primary,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 13),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
        ),
      ),

      textTheme: TextTheme(
        displayLarge: TextStyle(color: c.textPrimary, fontSize: 32, fontWeight: FontWeight.w800),
        titleLarge:   TextStyle(color: c.textPrimary, fontSize: 20, fontWeight: FontWeight.w700, letterSpacing: -0.5),
        titleMedium:  TextStyle(color: c.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
        bodyLarge:    TextStyle(color: c.textPrimary, fontSize: 15),
        bodyMedium:   TextStyle(color: c.textSecondary, fontSize: 13),
        bodySmall:    TextStyle(color: c.textSecondary, fontSize: 12),
        labelSmall:   TextStyle(color: c.textTertiary, fontSize: 11),
      ),
    );
  }

  // ═══════════════════════════════════════════════
  //  Light 主题
  // ═══════════════════════════════════════════════
  static ThemeData get light {
    const c = AppColorScheme.light;
    return ThemeData(
      brightness: Brightness.light,
      scaffoldBackgroundColor: c.bg,
      primaryColor: c.primary,
      useMaterial3: true,

      colorScheme: ColorScheme.light(
        primary: c.primary,
        surface: c.surface,
        error: c.danger,
        onPrimary: Colors.white,
        onSurface: c.textPrimary,
        outline: c.border,
      ),

      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: c.textPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.5,
        ),
        iconTheme: IconThemeData(color: c.textPrimary),
        systemOverlayStyle: const SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarBrightness: Brightness.light,
          statusBarIconBrightness: Brightness.dark,
        ),
      ),

      cardTheme: CardThemeData(
        color: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: const BorderRadius.all(Radius.circular(16)),
          side: BorderSide(color: c.glassBorder, width: 0.5),
        ),
      ),

      dividerTheme: DividerThemeData(
        color: c.divider,
        thickness: 0.5,
        space: 0,
      ),

      tabBarTheme: TabBarThemeData(
        labelColor: c.textPrimary,
        unselectedLabelColor: c.textTertiary,
        indicatorColor: c.primary,
        indicatorSize: TabBarIndicatorSize.label,
        labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
        unselectedLabelStyle: const TextStyle(fontSize: 13),
        dividerColor: Colors.transparent,
        overlayColor: WidgetStateProperty.resolveWith((_) => Colors.transparent),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: c.surfaceAlt,
        hintStyle: TextStyle(color: c.textTertiary, fontSize: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: c.primary,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 13),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
        ),
      ),

      textTheme: TextTheme(
        displayLarge: TextStyle(color: c.textPrimary, fontSize: 32, fontWeight: FontWeight.w800),
        titleLarge:   TextStyle(color: c.textPrimary, fontSize: 20, fontWeight: FontWeight.w700, letterSpacing: -0.5),
        titleMedium:  TextStyle(color: c.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
        bodyLarge:    TextStyle(color: c.textPrimary, fontSize: 15),
        bodyMedium:   TextStyle(color: c.textSecondary, fontSize: 13),
        bodySmall:    TextStyle(color: c.textSecondary, fontSize: 12),
        labelSmall:   TextStyle(color: c.textTertiary, fontSize: 11),
      ),
    );
  }
}
