import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/daily_pick.dart';
import '../models/hot_coin.dart';
import '../models/smart_money_signal.dart';

class SupabaseService {
  static final SupabaseService instance = SupabaseService._();
  SupabaseService._();

  SupabaseClient get _db => Supabase.instance.client;

  // ─────────────────────────────────────────────────
  // 新币榜：今日 AI 推荐 Top10
  // ─────────────────────────────────────────────────
  Future<List<DailyPick>> fetchTodayPicks() async {
    final today = _todayStr();
    return _fetchPicksByDate(today);
  }

  // ─────────────────────────────────────────────────
  // 历史推荐（最近 N 天）
  // ─────────────────────────────────────────────────
  Future<Map<String, List<DailyPick>>> fetchHistoryPicks({int days = 14}) async {
    final until = DateTime.now().subtract(const Duration(days: 1));
    final from  = until.subtract(Duration(days: days));

    final res = await _db
        .from('daily_picks')
        .select('''
          mint, pick_date, rank, score, score_detail,
          bc_progress, market_cap_sol,
          pump_tokens!inner(name, symbol, image_uri, twitter, telegram, website, creator),
          token_outcomes(did_graduate, peak_multiplier, label_2x, label_10x)
        ''')
        .gte('pick_date', _dateStr(from))
        .lte('pick_date', _dateStr(until))
        .order('pick_date', ascending: false)
        .order('rank');

    final grouped = <String, List<DailyPick>>{};
    for (final row in (res as List)) {
      final pick = DailyPick.fromJson(row as Map<String, dynamic>);
      grouped.putIfAbsent(pick.pickDate, () => []).add(pick);
    }
    return grouped;
  }

  // ─────────────────────────────────────────────────
  // 热币榜：多链外盘热币（hot_coins 表，每2小时更新）
  // 按综合分降序，强推优先，排除安全风险标记
  // ─────────────────────────────────────────────────
  Future<List<HotCoin>> fetchHotCoins({int limit = 50}) async {
    final res = await _db
        .from('hot_coins')
        .select(
          'chain, address, name, symbol, pair_address, dex_id, '
          'price_usd, market_cap_usd, liquidity_usd, '
          'volume_24h_usd, volume_1h_usd, '
          'price_change_1h, price_change_6h, price_change_24h, '
          'buys_1h, sells_1h, buys_24h, sells_24h, '
          'age_days, holder_count, top10_holder_pct, top1_holder_pct, '
          'goplus_risk, has_twitter, has_telegram, has_website, image_url, '
          'score, score_m, score_q, score_p, recommendation, scanned_at',
        )
        .eq('goplus_risk', false)
        .not('score', 'is', null)
        .neq('recommendation', 'skip')
        .order('score', ascending: false)
        .limit(limit);

    return (res as List)
        .map((e) => HotCoin.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ─────────────────────────────────────────────────
  // 聪明钱信号：多链聪明钱买卖聚合
  // ─────────────────────────────────────────────────
  Future<List<SmartMoneySignal>> fetchSmartMoneySignals({
    String? chain,
    int limit = 50,
    double minHeat = 0,
  }) async {
    var query = _db
        .from('smart_money_signals')
        .select()
        .gte('heat_score', minHeat);

    if (chain != null) {
      query = query.eq('chain', chain);
    }

    final res = await query
        .order('heat_score', ascending: false)
        .limit(limit);
    return (res as List)
        .map((e) => SmartMoneySignal.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ─────────────────────────────────────────────────
  // 私有工具
  // ─────────────────────────────────────────────────
  Future<List<DailyPick>> _fetchPicksByDate(String date) async {
    final res = await _db
        .from('daily_picks')
        .select('''
          mint, pick_date, rank, score, score_detail,
          bc_progress, market_cap_sol,
          pump_tokens!inner(name, symbol, image_uri, twitter, telegram, website, creator),
          token_outcomes(did_graduate, peak_multiplier, label_2x, label_10x)
        ''')
        .eq('pick_date', date)
        .order('rank');

    return (res as List)
        .map((e) => DailyPick.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  String _todayStr() => _dateStr(DateTime.now());
  String _dateStr(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}
