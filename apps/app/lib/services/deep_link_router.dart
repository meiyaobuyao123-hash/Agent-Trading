// Deep Link 路由器 — 把推送的 deep_link URL 翻译成 Flutter Navigator 跳转
//
// 引用 docs/agent-pm/03-prd.md §推送通知
// 引用 services/pump-scanner/agent/push_service.py:build_deep_link
//
// 支持格式:
//   aitrading://strategy/{strategy_id}             → StrategyDetailPage
//   aitrading://hitl/{approval_id}                 → HitlApprovalPage
//   aitrading://review/{period}                    → ReviewPage(period)
//   aitrading://token/{chain}/{address}            → TokenDetailPage(chain, address)
//   aitrading://memory/proposals/{proposal_id}     → MemoryManagementPage(scrollTo)
//   aitrading://memory                             → MemoryManagementPage
//   aitrading://home                               → 主页(默认)
//
// 设计:GlobalKey<NavigatorState> 注入,Service 层无需 BuildContext。
//      未识别的 link 默认回主页(不抛异常)。

import 'package:flutter/material.dart';

// R58:ReviewPage / MemoryManagementPage 已删 — `aitrading://review` 和 `aitrading://memory`
// 推送类型现在回主页占位,等 R59+ 策略健康度 PRD 落地时再接
// hitl 推送当前用 _DeepLinkPlaceholder 占位,真接 HitlApprovalPage 留 R57+(local_auth + 钱包真签)

class DeepLinkRouter {
  /// 主导航 GlobalKey,App 启动时通过 main.dart 的 MaterialApp.navigatorKey 注入
  static final GlobalKey<NavigatorState> navigatorKey =
      GlobalKey<NavigatorState>();

  static const _scheme = 'aitrading://';

  /// 处理推送 data map 里的 deep_link 字段
  static Future<bool> handleFromPushData(Map<String, dynamic> data) async {
    final raw = data['deep_link'];
    if (raw is String && raw.isNotEmpty) {
      return handle(raw);
    }
    return false;
  }

  /// 解析 + 跳转。返回是否成功路由。
  static Future<bool> handle(String url) async {
    if (!url.startsWith(_scheme)) {
      debugPrint('[DeepLink] not aitrading scheme: $url');
      return false;
    }
    final path = url.substring(_scheme.length);
    final segs = path.split('/').where((s) => s.isNotEmpty).toList();
    if (segs.isEmpty) return _navHome();

    final nav = navigatorKey.currentState;
    if (nav == null) {
      debugPrint('[DeepLink] navigator not ready, skip: $url');
      return false;
    }

    debugPrint('[DeepLink] routing: $url (segs=$segs)');

    switch (segs[0]) {
      case 'strategy':
        // 策略详情页需要 strategy 对象,deep_link 只有 id;暂时跳到 Agent 页让用户挑
        // TODO(W7-W12):新建 StrategyDetailById 页直接按 id 拉
        return _navHome();
      case 'hitl':
        if (segs.length >= 2) {
          // approvalId-only 跳转;详情页支持 fetchById(下次实施)
          // 暂时:打开 HITL 页面,内部去 fetch by id
          // 简化:展示一个提示信息加跳到主页
          // 完整 fix 留下次,先确保不崩
          await nav.push(MaterialPageRoute(
            builder: (_) => _DeepLinkPlaceholder(
              title: 'HITL 审批',
              message: '正在加载审批 ${segs[1].substring(0, segs[1].length.clamp(0, 8))}…',
              fallback: () => Navigator.of(nav.context).pop(),
            ),
          ));
          return true;
        }
        return _navHome();
      case 'review':
      case 'memory':
        // R58:ReviewPage / MemoryManagementPage 已撤(跨用户隐私 bug + UI 风格不搭)
        // 后续 R59+ 策略健康度 PRD 落地后,这些 deep link 应导向"策略健康度"页面
        debugPrint('[DeepLink] $url — review/memory page removed in R58, fallback to home');
        return _navHome();
      case 'token':
        if (segs.length >= 3) {
          // TokenDetailPage 需要 chain + address
          // 当前 app 没统一的 token 路由 by id,暂跳主页
          return _navHome();
        }
        return _navHome();
      case 'home':
      default:
        return _navHome();
    }
  }

  static bool _navHome() {
    final nav = navigatorKey.currentState;
    if (nav == null) return false;
    nav.popUntil((r) => r.isFirst);
    return true;
  }
}

/// 临时占位:HITL by id fetch 真实施前用
class _DeepLinkPlaceholder extends StatelessWidget {
  final String title;
  final String message;
  final VoidCallback? fallback;
  const _DeepLinkPlaceholder({
    required this.title,
    required this.message,
    this.fallback,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.hourglass_empty, size: 48),
              const SizedBox(height: 16),
              Text(
                message,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 14, height: 1.5),
              ),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: fallback ?? () => Navigator.of(context).pop(),
                child: const Text('返回'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
