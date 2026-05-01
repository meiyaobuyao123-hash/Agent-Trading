import 'package:flutter/material.dart';
import '../../services/agent_service.dart';
import 'review_page.dart';
import 'memory_management_page.dart';

/// AI 洞察 Tab — Regime 状态 + 学到的规则 + 反思 + 风控
class AiInsightsTab extends StatefulWidget {
  const AiInsightsTab({super.key});

  @override
  State<AiInsightsTab> createState() => _AiInsightsTabState();
}

class _AiInsightsTabState extends State<AiInsightsTab> with AutomaticKeepAliveClientMixin {
  Map<String, dynamic> _memory = {};
  Map<String, dynamic> _regime = {};
  Map<String, dynamic> _performance = {};
  bool _loading = true;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final results = await Future.wait([
      AgentService.instance.getMemory(),
      AgentService.instance.getRegime(),
      AgentService.instance.getPerformance(),
    ]);
    if (mounted) {
      setState(() {
        _memory = results[0];
        _regime = results[1];
        _performance = results[2];
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    if (_loading) return const Center(child: CircularProgressIndicator());

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildPhase3Entry(),
          const SizedBox(height: 12),
          _buildRegimeCard(),
          const SizedBox(height: 12),
          _buildPerformanceCard(),
          const SizedBox(height: 12),
          _buildRulesCard(),
          const SizedBox(height: 12),
          _buildRecentEventsCard(),
        ],
      ),
    );
  }

  /// Phase 3 入口:复盘 + 记忆管理
  Widget _buildPhase3Entry() {
    Widget tile({
      required IconData icon,
      required String title,
      required String subtitle,
      required Color color,
      required VoidCallback onTap,
    }) {
      return Expanded(
        child: Material(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(12),
          child: InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(icon, color: color, size: 18),
                  const SizedBox(height: 6),
                  Text(title,
                      style: const TextStyle(
                          fontSize: 13, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 2),
                  Text(subtitle,
                      style: const TextStyle(
                          fontSize: 11, color: Colors.white60)),
                ],
              ),
            ),
          ),
        ),
      );
    }

    return Row(children: [
      tile(
        icon: Icons.summarize_outlined,
        title: '复盘报告',
        subtitle: '日 / 周 / 月',
        color: Colors.tealAccent,
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const ReviewPage()),
        ),
      ),
      const SizedBox(width: 10),
      tile(
        icon: Icons.psychology_outlined,
        title: '我的规则',
        subtitle: '记忆管理',
        color: Colors.purpleAccent,
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const MemoryManagementPage()),
        ),
      ),
    ]);
  }

  /// Regime 状态条
  Widget _buildRegimeCard() {
    final regime = _regime['global_regime'] ?? 'UNKNOWN';
    final shadow = _regime['shadow_mode'] == true;
    final phases = ['TRENDING_UP', 'BREAKOUT', 'RANGING', 'HIGH_VOLATILITY', 'TRENDING_DOWN', 'CRISIS', 'RECOVERY'];
    final labels = ['上涨', '突破', '震荡', '高波动', '下跌', '危机', '恢复'];
    final colors = [Colors.green, Colors.blue, Colors.grey, Colors.orange, Colors.red, Colors.red.shade900, Colors.teal];

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.radar, color: Colors.blue, size: 18),
              const SizedBox(width: 8),
              const Text('市场状态', style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
              const Spacer(),
              if (shadow) Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(color: Colors.orange.withValues(alpha: 0.2), borderRadius: BorderRadius.circular(8)),
                child: const Text('Shadow', style: TextStyle(color: Colors.orange, fontSize: 10)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: List.generate(phases.length, (i) {
              final isActive = regime == phases[i];
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: isActive ? colors[i].withValues(alpha: 0.3) : Colors.white.withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(8),
                  border: isActive ? Border.all(color: colors[i], width: 1.5) : null,
                ),
                child: Text(
                  labels[i],
                  style: TextStyle(
                    color: isActive ? colors[i] : Colors.white30,
                    fontSize: 12,
                    fontWeight: isActive ? FontWeight.bold : FontWeight.normal,
                  ),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }

  /// 表现概览
  Widget _buildPerformanceCard() {
    final p = _performance;
    final winRate = (p['win_rate'] as num?)?.toDouble() ?? 0;
    final totalPnl = (p['total_pnl_pct'] as num?)?.toDouble() ?? 0;
    final trades = (p['total_trades'] as num?)?.toInt() ?? 0;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.analytics, color: Colors.green, size: 18),
              SizedBox(width: 8),
              Text('Agent 表现', style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _stat('总交易', '$trades', Colors.white),
              _stat('胜率', '${(winRate * 100).toStringAsFixed(0)}%', winRate >= 0.5 ? Colors.green : Colors.red),
              _stat('PNL', '${totalPnl >= 0 ? "+" : ""}${totalPnl.toStringAsFixed(1)}%', totalPnl >= 0 ? Colors.green : Colors.red),
            ],
          ),
        ],
      ),
    );
  }

  Widget _stat(String label, String value, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text(value, style: TextStyle(color: color, fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(color: Colors.white38, fontSize: 11)),
        ],
      ),
    );
  }

  /// Agent 学到的规则
  Widget _buildRulesCard() {
    final rules = (_memory['active_rules'] as List?) ?? [];

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.psychology, color: Colors.purple, size: 18),
              const SizedBox(width: 8),
              Text('Agent 学到的规则 (${rules.length})', style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 8),
          if (rules.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('Agent 还在学习中...', style: TextStyle(color: Colors.white38, fontSize: 13)),
            )
          else
            ...rules.take(5).map((r) {
              final rule = r as Map<String, dynamic>;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('💡', style: TextStyle(fontSize: 14)),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            rule['content'] ?? rule['condition'] ?? '',
                            style: const TextStyle(color: Colors.white70, fontSize: 13),
                          ),
                          if (rule['importance'] != null)
                            Text(
                              '置信度: ${rule['importance']}/10',
                              style: const TextStyle(color: Colors.white30, fontSize: 11),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }

  /// 最近事件
  Widget _buildRecentEventsCard() {
    final events = (_memory['recent_events'] as List?) ?? [];
    final stats = _memory['stats'] as Map<String, dynamic>? ?? {};

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.memory, color: Colors.cyan, size: 18),
              const SizedBox(width: 8),
              Text(
                '短期记忆 (${stats['working_memory_size'] ?? 0})',
                style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (events.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('暂无事件', style: TextStyle(color: Colors.white38, fontSize: 13)),
            )
          else
            ...events.take(8).map((e) {
              final ev = e as Map<String, dynamic>;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Text(
                  ev['summary'] ?? '',
                  style: const TextStyle(color: Colors.white54, fontSize: 12),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              );
            }),
        ],
      ),
    );
  }
}
