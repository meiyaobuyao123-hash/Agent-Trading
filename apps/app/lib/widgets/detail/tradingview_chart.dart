import 'dart:convert';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../../models/ohlcv_data.dart';
import '../../theme/app_colors.dart';

/// KLineChart 专业K线图 — 内置 MA/BOLL/MACD/KDJ/RSI/WR/VOL 全部指标
/// chartType: 'candle_solid' (默认K线) 或 'area' (折线面积图)
class TradingViewChart extends StatefulWidget {
  final List<OhlcvCandle> candles;
  final String selectedTimeframe;
  final ValueChanged<String> onTimeframeChanged;
  final bool loading;
  final bool showControls;
  final Set<String> activeIndicators;
  final String chartType; // 'candle_solid' | 'area'

  const TradingViewChart({
    super.key,
    required this.candles,
    required this.selectedTimeframe,
    required this.onTimeframeChanged,
    this.loading = false,
    this.showControls = true,
    this.activeIndicators = const {'VOL', 'MA'},
    this.chartType = 'candle_solid',
  });

  @override
  State<TradingViewChart> createState() => _TradingViewChartState();
}

class _TradingViewChartState extends State<TradingViewChart> {
  late final WebViewController _controller;
  // JS 图表库是否已初始化完成（FlutterBridge 收到 'ready'）
  bool _chartReady = false;
  Set<String> _lastIndicators = {};
  String _lastChartType = '';

  static const _timeframes = ['5m', '15m', '1h', '4h', '1d'];

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFF1C1C2E)) // 固定暗色背景，避免 initState 中访问 context
      ..addJavaScriptChannel('FlutterBridge', onMessageReceived: (msg) {
        debugPrint('[KLineChart] FlutterBridge 收到: ${msg.message}');
        if (msg.message == 'ready') {
          // 图表库加载完成，推送数据和指标
          _chartReady = true;
          _pushData();
          _syncIndicators(force: true);
          _syncChartType(force: true);
        }
      })
      ..setNavigationDelegate(NavigationDelegate(
        onPageFinished: (_) {
          debugPrint('[KLineChart] onPageFinished 触发');
          // 兜底：如果 FlutterBridge 5秒后仍未触发 ready，尝试检查图表状态
          Future.delayed(const Duration(milliseconds: 5000), () {
            if (!_chartReady && mounted) {
              debugPrint('[KLineChart] 兜底：5秒后仍未收到 ready，尝试推送数据');
              _chartReady = true;
              _pushData();
              _syncIndicators(force: true);
              _syncChartType(force: true);
            }
          });
        },
      ))
      ..loadHtmlString(_klineHtml);
  }

  @override
  void didUpdateWidget(TradingViewChart old) {
    super.didUpdateWidget(old);
    // K线数据变化时重新推送
    if (old.candles != widget.candles) {
      debugPrint('[KLineChart] didUpdateWidget: candles 变化, 数量=${widget.candles.length}');
      _pushData();
    }
    // 指标变化时同步到 JS
    if (!_setEq(old.activeIndicators, widget.activeIndicators)) {
      debugPrint('[KLineChart] didUpdateWidget: 指标变化 ${widget.activeIndicators}');
      _syncIndicators();
    }
    // 图表类型变化时同步到 JS
    if (old.chartType != widget.chartType) {
      debugPrint('[KLineChart] didUpdateWidget: chartType 变化 ${widget.chartType}');
      _syncChartType();
    }
  }

  bool _setEq(Set<String> a, Set<String> b) {
    if (a.length != b.length) return false;
    return a.every(b.contains);
  }

  void _pushData() {
    if (!_chartReady || widget.candles.isEmpty) {
      debugPrint('[KLineChart] _pushData 跳过: chartReady=$_chartReady, candles=${widget.candles.length}');
      return;
    }
    final jsonList = widget.candles.map((c) => {
      'time': c.timestamp.millisecondsSinceEpoch ~/ 1000,
      'open': c.open,
      'high': c.high,
      'low': c.low,
      'close': c.close,
      'volume': c.volume,
    }).toList();
    final jsonStr = jsonEncode(jsonList);
    debugPrint('[KLineChart] _pushData: 推送 ${jsonList.length} 条K线数据');
    // 直接调用 updateData，不做 typeof 检查（此时 _chartReady 保证 JS 已初始化）
    _controller.runJavaScript('updateData($jsonStr)');
  }

  /// 同步指标到 JS 图表。force=true 时忽略缓存直接推送
  void _syncIndicators({bool force = false}) {
    if (!_chartReady) return;
    if (!force && _setEq(_lastIndicators, widget.activeIndicators)) return;
    final json = jsonEncode(widget.activeIndicators.toList());
    debugPrint('[KLineChart] _syncIndicators: 设置指标 ${widget.activeIndicators}');
    _controller.runJavaScript('setIndicators($json)');
    _lastIndicators = Set.from(widget.activeIndicators);
  }

  /// 同步图表类型（candle_solid / area）到 JS
  void _syncChartType({bool force = false}) {
    if (!_chartReady) return;
    if (!force && _lastChartType == widget.chartType) return;
    debugPrint('[KLineChart] _syncChartType: 设置图表类型 ${widget.chartType}');
    _controller.runJavaScript("setChartType('${widget.chartType}')");
    _lastChartType = widget.chartType;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(color: context.colors.chartBg),
      child: Column(
        children: [
          // K线图区域
          SizedBox(
            height: 380,
            child: widget.loading
                ? const Center(
                    child: CupertinoActivityIndicator(radius: 12, color: Colors.white54),
                  )
                : widget.candles.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(CupertinoIcons.chart_bar_alt_fill, size: 32, color: Colors.white24),
                            const SizedBox(height: 8),
                            const Text('暂无K线数据',
                              style: TextStyle(color: Colors.white38, fontSize: 14, decoration: TextDecoration.none)),
                            const SizedBox(height: 4),
                            const Text('该代币可能上线时间较短',
                              style: TextStyle(color: Colors.white24, fontSize: 11, decoration: TextDecoration.none)),
                          ],
                        ),
                      )
                    : WebViewWidget(controller: _controller),
          ),

          if (widget.showControls) ...[
            // MA 图例
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: Row(
                children: [
                  Container(width: 10, height: 2, color: const Color(0xFFFF9500)),
                  const SizedBox(width: 4),
                  const Text('MA7', style: TextStyle(fontSize: 10, color: Color(0xFFFF9500), decoration: TextDecoration.none)),
                  const SizedBox(width: 12),
                  Container(width: 10, height: 2, color: const Color(0xFF5AC8FA)),
                  const SizedBox(width: 4),
                  const Text('MA25', style: TextStyle(fontSize: 10, color: Color(0xFF5AC8FA), decoration: TextDecoration.none)),
                ],
              ),
            ),
            // 时间框架选择器
            Container(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 14),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: _timeframes.map((tf) {
                  final selected = tf == widget.selectedTimeframe;
                  return GestureDetector(
                    onTap: () => widget.onTimeframeChanged(tf),
                    child: Container(
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 7),
                      decoration: BoxDecoration(
                        color: selected
                            ? context.colors.primary
                            : Colors.white.withValues(alpha: 0.06),
                        borderRadius: BorderRadius.circular(10),
                        border: selected ? null : Border.all(
                          color: Colors.white.withValues(alpha: 0.08),
                          width: 0.5,
                        ),
                      ),
                      child: Text(
                        tf,
                        style: TextStyle(
                          color: selected ? Colors.white : Colors.white54,
                          fontSize: 13,
                          fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                          decoration: TextDecoration.none,
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
          ],
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════════
  //  KLineChart HTML — 专业K线图，内置全部技术指标
  // ═══════════════════════════════════════════════════════
  static const _klineHtml = '''
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #1A1D26; overflow: hidden; -webkit-user-select: none; user-select: none; }
  #chart { width: 100%; height: 100vh; }
  #msg { display: none; color: #8E8E93; font-size: 13px; text-align: center;
         position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
         font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
</style>
</head>
<body>
<div id="chart"></div>
<div id="msg">K线加载中...</div>
<script>
var chart = null;
var subPanes = {};
var mainInds = {};
var ready = false;
var pendingData = null;
var pendingIndicators = null;

// 多CDN备选，提高加载成功率
var cdnUrls = [
  'https://cdn.jsdelivr.net/npm/klinecharts@9/dist/klinecharts.min.js',
  'https://unpkg.com/klinecharts@9/dist/klinecharts.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/klinecharts/9.8.8/klinecharts.min.js'
];
var cdnIndex = 0;

function loadScript() {
  if (cdnIndex >= cdnUrls.length) {
    document.getElementById('msg').style.display = 'block';
    document.getElementById('msg').textContent = 'K线库加载失败，请检查网络';
    return;
  }
  var s = document.createElement('script');
  s.src = cdnUrls[cdnIndex];
  s.onload = function() { initChart(); };
  s.onerror = function() {
    cdnIndex++;
    loadScript();
  };
  // 单个CDN超时8秒则尝试下一个
  setTimeout(function() {
    if (!ready && cdnIndex < cdnUrls.length) {
      cdnIndex++;
      loadScript();
    }
  }, 8000);
  document.head.appendChild(s);
}
loadScript();

function initChart() {
  if (ready) return;
  try {
    chart = klinecharts.init('chart', {
      styles: {
        grid: {
          show: true,
          horizontal: { show: true, size: 1, color: '#2A2D38', style: 'dashed', dashedValue: [2, 2] },
          vertical: { show: true, size: 1, color: '#2A2D38', style: 'dashed', dashedValue: [2, 2] }
        },
        candle: {
          type: 'candle_solid',
          bar: {
            upColor: '#34C759', downColor: '#FF3B30',
            upBorderColor: '#34C759', downBorderColor: '#FF3B30',
            upWickColor: '#34C759', downWickColor: '#FF3B30'
          },
          priceMark: {
            show: true,
            high: { show: true, color: '#D1D1D6', textOffset: 5, textSize: 10, textFamily: 'Menlo' },
            low: { show: true, color: '#D1D1D6', textOffset: 5, textSize: 10, textFamily: 'Menlo' },
            last: {
              show: true, upColor: '#34C759', downColor: '#FF3B30', noChangeColor: '#888',
              line: { show: true, style: 'dashed', dashedValue: [4, 4], size: 1 },
              text: { show: true, size: 10, color: '#fff', family: 'Menlo',
                      paddingLeft: 4, paddingRight: 4, paddingTop: 2, paddingBottom: 2,
                      borderRadius: 2 }
            }
          },
          tooltip: {
            showRule: 'follow_cross',
            showType: 'rect',
            custom: [
              { title: 'O', value: '{open}' },
              { title: 'H', value: '{high}' },
              { title: 'L', value: '{low}' },
              { title: 'C', value: '{close}' },
              { title: 'V', value: '{volume}' }
            ],
            rect: { paddingLeft: 4, paddingRight: 4, paddingTop: 4, paddingBottom: 4,
                    offsetLeft: 4, offsetTop: 4, offsetRight: 4, borderRadius: 4,
                    borderSize: 0.5, borderColor: '#363A45', color: '#1A1D26E6' },
            text: { size: 10, family: 'Menlo', color: '#D1D1D6' }
          }
        },
        indicator: {
          tooltip: {
            showRule: 'follow_cross',
            showName: true,
            showParams: true,
            text: { size: 10, family: 'Menlo' }
          },
          bars: [
            { upColor: 'rgba(52,199,89,0.35)', downColor: 'rgba(255,59,48,0.35)', noChangeColor: '#555' }
          ],
          lines: [
            { size: 1, color: '#FF9500' },
            { size: 1, color: '#5AC8FA' },
            { size: 1, color: '#AF52DE' },
            { size: 1, color: '#FFD60A' },
            { size: 1, color: '#FF375F' }
          ]
        },
        xAxis: {
          show: true,
          axisLine: { show: true, color: '#2A2D38', size: 1 },
          tickLine: { show: true, size: 1, length: 3, color: '#2A2D38' },
          tickText: { show: true, color: '#8E8E93', size: 10, family: 'Menlo' }
        },
        yAxis: {
          show: true,
          position: 'right',
          type: 'normal',
          axisLine: { show: false },
          tickLine: { show: false },
          tickText: { show: true, color: '#8E8E93', size: 10, family: 'Menlo' }
        },
        separator: { size: 1, color: '#2A2D38', fill: true, activeBackgroundColor: 'rgba(142,142,147,0.08)' },
        crosshair: {
          show: true,
          horizontal: {
            show: true,
            line: { show: true, style: 'dashed', dashedValue: [4, 2], size: 1, color: 'rgba(142,142,147,0.5)' },
            text: { show: true, style: 'fill', color: '#fff', size: 10, family: 'Menlo',
                    backgroundColor: '#363A45', borderColor: '#363A45', borderSize: 0,
                    borderRadius: 2, paddingLeft: 4, paddingRight: 4, paddingTop: 2, paddingBottom: 2 }
          },
          vertical: {
            show: true,
            line: { show: true, style: 'dashed', dashedValue: [4, 2], size: 1, color: 'rgba(142,142,147,0.5)' },
            text: { show: true, style: 'fill', color: '#fff', size: 10, family: 'Menlo',
                    backgroundColor: '#363A45', borderColor: '#363A45', borderSize: 0,
                    borderRadius: 2, paddingLeft: 4, paddingRight: 4, paddingTop: 2, paddingBottom: 2 }
          }
        }
      }
    });

    ready = true;
    // 通知 Flutter 图表已就绪
    try { FlutterBridge.postMessage('ready'); } catch(e) {}
    // 如果在图表就绪前就收到了数据或指标，立即应用
    if (pendingData) { updateData(pendingData); pendingData = null; }
    if (pendingIndicators) { setIndicators(pendingIndicators); pendingIndicators = null; }
  } catch(e) {
    document.getElementById('msg').style.display = 'block';
    document.getElementById('msg').textContent = '图表初始化失败';
  }
}

function updateData(data) {
  if (!data || !data.length) return;
  // 如果图表尚未就绪，缓存数据等待初始化完成后使用
  if (!chart || !ready) { pendingData = data; return; }
  try {
    chart.applyNewData(data.map(function(d) {
      return {
        timestamp: d.time * 1000,
        open: d.open, high: d.high, low: d.low, close: d.close,
        volume: d.volume
      };
    }));
  } catch(e) { console.error('updateData:', e); }
}

function setIndicators(names) {
  if (!names) return;
  // 如果图表尚未就绪，缓存指标设置等待初始化完成后使用
  if (!chart || !ready) { pendingIndicators = names; return; }
  try {
    var mainTypes = ['MA', 'EMA', 'BOLL', 'SMA'];
    var wanted = {};
    names.forEach(function(n) { wanted[n] = true; });

    // 移除不需要的主图指标
    Object.keys(mainInds).forEach(function(k) {
      if (!wanted[k]) {
        try { chart.removeIndicator('candle_pane', k); } catch(e) {}
        delete mainInds[k];
      }
    });

    // 移除不需要的副图指标
    Object.keys(subPanes).forEach(function(k) {
      if (!wanted[k]) {
        try { chart.removeIndicator(subPanes[k]); } catch(e) {}
        delete subPanes[k];
      }
    });

    // 添加需要的指标
    names.forEach(function(name) {
      if (mainTypes.indexOf(name) >= 0) {
        if (!mainInds[name]) {
          chart.createIndicator(name, false, { id: 'candle_pane' });
          mainInds[name] = true;
        }
      } else {
        if (!subPanes[name]) {
          var paneId = chart.createIndicator(name);
          subPanes[name] = paneId || name;
        }
      }
    });
  } catch(e) { console.error('setIndicators:', e); }
}

function setChartType(type) {
  if (!chart || !ready) return;
  try {
    if (type === 'area') {
      chart.setStyles({
        candle: {
          type: 'area',
          area: {
            lineSize: 2,
            lineColor: '#007AFF',
            value: 'close',
            smooth: true,
            backgroundColor: [{
              offset: 0,
              color: 'rgba(0, 122, 255, 0.25)'
            }, {
              offset: 1,
              color: 'rgba(0, 122, 255, 0.01)'
            }],
            point: {
              show: true,
              color: '#007AFF',
              radius: 3,
              rippleColor: 'rgba(0, 122, 255, 0.3)',
              rippleRadius: 6,
              animation: true,
              animationDuration: 1000
            }
          },
          priceMark: {
            high: { show: false },
            low: { show: false },
            last: {
              show: true, upColor: '#007AFF', downColor: '#007AFF', noChangeColor: '#007AFF',
              line: { show: true, style: 'dashed', dashedValue: [4, 4], size: 1 },
              text: { show: true, size: 10, color: '#fff', family: 'Menlo',
                      paddingLeft: 4, paddingRight: 4, paddingTop: 2, paddingBottom: 2,
                      borderRadius: 2 }
            }
          }
        }
      });
    } else {
      chart.setStyles({
        candle: {
          type: 'candle_solid',
          priceMark: {
            high: { show: true, color: '#D1D1D6', textOffset: 5, textSize: 10, textFamily: 'Menlo' },
            low: { show: true, color: '#D1D1D6', textOffset: 5, textSize: 10, textFamily: 'Menlo' },
            last: {
              show: true, upColor: '#34C759', downColor: '#FF3B30', noChangeColor: '#888',
              line: { show: true, style: 'dashed', dashedValue: [4, 4], size: 1 },
              text: { show: true, size: 10, color: '#fff', family: 'Menlo',
                      paddingLeft: 4, paddingRight: 4, paddingTop: 2, paddingBottom: 2,
                      borderRadius: 2 }
            }
          }
        }
      });
    }
  } catch(e) { console.error('setChartType:', e); }
}
</script>
</body>
</html>
''';
}
