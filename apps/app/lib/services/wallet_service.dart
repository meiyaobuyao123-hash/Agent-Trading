import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
// 使用系统级加密存储保管私钥/助记词（iOS Keychain / Android Keystore）
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

// ══════════════════════════════════════════════════════════════
//  钱包管理服务 — 本地存储 + 多链支持
//  敏感数据（私钥/助记词）存储于系统加密区，非敏感数据用 SharedPreferences
// ══════════════════════════════════════════════════════════════

/// 钱包类型
enum WalletType { mnemonic, privateKey }

/// 用户钱包模型
class UserWallet {
  final String id;
  final String name;
  final String address;
  final String chain; // solana / eth / bsc / base
  final WalletType type;
  final DateTime createdAt;
  final bool isDefault;

  const UserWallet({
    required this.id,
    required this.name,
    required this.address,
    required this.chain,
    required this.type,
    required this.createdAt,
    this.isDefault = false,
  });

  UserWallet copyWith({bool? isDefault}) {
    return UserWallet(
      id: id,
      name: name,
      address: address,
      chain: chain,
      type: type,
      createdAt: createdAt,
      isDefault: isDefault ?? this.isDefault,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'address': address,
        'chain': chain,
        'type': type == WalletType.mnemonic ? 'mnemonic' : 'privateKey',
        'createdAt': createdAt.toIso8601String(),
        'isDefault': isDefault,
      };

  factory UserWallet.fromJson(Map<String, dynamic> json) => UserWallet(
        id: json['id'] as String,
        name: json['name'] as String,
        address: json['address'] as String,
        chain: json['chain'] as String,
        type: json['type'] == 'mnemonic'
            ? WalletType.mnemonic
            : WalletType.privateKey,
        createdAt: DateTime.parse(json['createdAt'] as String),
        isDefault: json['isDefault'] as bool? ?? false,
      );
}

/// 钱包管理单例服务
class WalletService extends ChangeNotifier {
  WalletService._();
  static final WalletService _instance = WalletService._();
  static WalletService get instance => _instance;

  // SharedPreferences 存储 key（非敏感数据：钱包列表元信息）
  static const _kWalletList = 'wallet_list_v1';
  // 敏感数据 key 前缀（存储在 FlutterSecureStorage）
  static const _kSecretPrefix = 'wallet_secret_';

  // FlutterSecureStorage 实例 — 底层使用 iOS Keychain / Android Keystore
  static const _secureStorage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  List<UserWallet> _wallets = [];
  SharedPreferences? _prefs;

  /// 所有钱包（只读）
  List<UserWallet> get wallets => List.unmodifiable(_wallets);

  /// 默认钱包 ID
  String? get defaultWalletId {
    try {
      return _wallets.firstWhere((w) => w.isDefault).id;
    } catch (_) {
      return _wallets.isNotEmpty ? _wallets.first.id : null;
    }
  }

  /// 默认钱包
  UserWallet? get defaultWallet {
    try {
      return _wallets.firstWhere((w) => w.isDefault);
    } catch (_) {
      return _wallets.isNotEmpty ? _wallets.first : null;
    }
  }

  /// 初始化 — 从本地存储加载钱包列表
  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
    final raw = _prefs?.getString(_kWalletList);
    if (raw != null && raw.isNotEmpty) {
      try {
        final list = jsonDecode(raw) as List<dynamic>;
        _wallets = list
            .map((e) => UserWallet.fromJson(e as Map<String, dynamic>))
            .toList();
      } catch (e) {
        debugPrint('[WalletService] Failed to parse wallet list: $e');
        _wallets = [];
      }
    }
    notifyListeners();
  }

  /// 通过助记词导入钱包
  Future<UserWallet> importFromMnemonic({
    required String mnemonic,
    required String chain,
    required String name,
  }) async {
    final trimmed = mnemonic.trim().toLowerCase();
    final words = trimmed.split(RegExp(r'\s+'));
    if (words.length != 12 && words.length != 24) {
      throw ArgumentError('助记词必须是 12 或 24 个单词');
    }

    // 简化地址派生（生产环境应使用真实密码学库）
    final address = _deriveAddress(trimmed, chain);

    // 去重检查
    if (_wallets.any((w) => w.address == address && w.chain == chain)) {
      throw StateError('该钱包已存在');
    }

    final wallet = UserWallet(
      id: _generateId(),
      name: name.isNotEmpty ? name : '${_chainLabel(chain)} 钱包',
      address: address,
      chain: chain,
      type: WalletType.mnemonic,
      createdAt: DateTime.now(),
      isDefault: _wallets.isEmpty,
    );

    // 将助记词写入系统加密存储区（不经过 SharedPreferences）
    await _secureStorage.write(
      key: '$_kSecretPrefix${wallet.id}',
      value: trimmed,
    );

    _wallets.add(wallet);
    await _persist();
    notifyListeners();
    return wallet;
  }

  /// 通过私钥导入钱包
  Future<UserWallet> importFromPrivateKey({
    required String privateKey,
    required String chain,
    required String name,
  }) async {
    final trimmed = privateKey.trim();
    if (trimmed.isEmpty || trimmed.length < 32) {
      throw ArgumentError('无效的私钥');
    }

    // 简化地址派生
    final address = _deriveAddress(trimmed, chain);

    // 去重检查
    if (_wallets.any((w) => w.address == address && w.chain == chain)) {
      throw StateError('该钱包已存在');
    }

    final wallet = UserWallet(
      id: _generateId(),
      name: name.isNotEmpty ? name : '${_chainLabel(chain)} 钱包',
      address: address,
      chain: chain,
      type: WalletType.privateKey,
      createdAt: DateTime.now(),
      isDefault: _wallets.isEmpty,
    );

    // 将私钥写入系统加密存储区（不经过 SharedPreferences）
    await _secureStorage.write(
      key: '$_kSecretPrefix${wallet.id}',
      value: trimmed,
    );

    _wallets.add(wallet);
    await _persist();
    notifyListeners();
    return wallet;
  }

  /// 获取钱包私密信息（助记词/私钥）— 从系统加密存储区读取
  Future<String?> getSecret(String walletId) async {
    return _secureStorage.read(key: '$_kSecretPrefix$walletId');
  }

  /// 设置默认钱包
  Future<void> setDefault(String walletId) async {
    _wallets = _wallets.map((w) {
      return w.copyWith(isDefault: w.id == walletId);
    }).toList();
    await _persist();
    notifyListeners();
  }

  /// 删除钱包
  Future<void> deleteWallet(String walletId) async {
    _wallets.removeWhere((w) => w.id == walletId);
    // 从系统加密存储区删除私钥/助记词
    await _secureStorage.delete(key: '$_kSecretPrefix$walletId');

    // 如果删除了默认钱包，自动将第一个设为默认
    if (_wallets.isNotEmpty && !_wallets.any((w) => w.isDefault)) {
      _wallets[0] = _wallets[0].copyWith(isDefault: true);
    }

    await _persist();
    notifyListeners();
  }

  /// 按链过滤钱包
  List<UserWallet> walletsForChain(String chain) {
    return _wallets.where((w) => w.chain == chain).toList();
  }

  // ── 内部方法 ────────────────────────────────────────────────

  /// 简化地址派生
  /// 生产环境应使用 ed25519(Solana) / secp256k1(EVM) 真实派生
  String _deriveAddress(String seed, String chain) {
    // 简单哈希模拟（非密码学安全，仅用于开发阶段）
    int hash = 0;
    for (int i = 0; i < seed.length; i++) {
      hash = (hash * 31 + seed.codeUnitAt(i)) & 0x7FFFFFFF;
    }
    final hexHash = hash.toRadixString(16).padLeft(40, '0');

    if (chain == 'solana') {
      // Solana: Base58 格式模拟（44 字符 hex）
      final combined = '$hexHash${chain.hashCode.toRadixString(16).padLeft(4, '0')}';
      return combined.padRight(44, 'a').substring(0, 44);
    } else {
      // EVM 链: 0x 前缀 + 40 hex
      return '0x${hexHash.substring(0, 40)}';
    }
  }

  String _generateId() {
    final now = DateTime.now().microsecondsSinceEpoch;
    return now.toRadixString(36);
  }

  String _chainLabel(String chain) {
    switch (chain) {
      case 'solana':
        return 'Solana';
      case 'eth':
        return 'Ethereum';
      case 'bsc':
        return 'BSC';
      case 'base':
        return 'Base';
      default:
        return chain.toUpperCase();
    }
  }

  /// 持久化钱包列表
  Future<void> _persist() async {
    final json = jsonEncode(_wallets.map((w) => w.toJson()).toList());
    await _prefs?.setString(_kWalletList, json);
  }
}
