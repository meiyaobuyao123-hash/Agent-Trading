import 'dart:convert';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../../models/ohlcv_data.dart';
import '../../theme/app_colors.dart';

/// TradingView Lightweight Charts v5 — WebView K线图
class TradingViewChart extends StatefulWidget {
  final List<OhlcvCandle> candles;
  final String selectedTimeframe;
  final ValueChanged<String> onTimeframeChanged;
  final bool loading;

  const TradingViewChart({
    super.key,
    required this.candles,
    required this.selectedTimeframe,
    required this.onTimeframeChanged,
    this.loading = false,
  });

  @override
  State<TradingViewChart> createState() => _TradingViewChartState();
}

class _TradingViewChartState extends State<TradingViewChart> {
  late final WebViewController _controller;
  bool _chartReady = false;
  bool _dataPushed = false;

  static const _timeframes = ['5m', '15m', '1h', '4h', '1d'];

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(AppColors.chartBg)
      ..addJavaScriptChannel('FlutterBridge', onMessageReceived: (msg) {
        if (msg.message == 'ready' && !_chartReady) {
          _chartReady = true;
          _pushData();
        }
      })
      ..setNavigationDelegate(NavigationDelegate(
        onPageFinished: (_) {
          // Fallback: ensure data gets pushed even if JS channel fails
          Future.delayed(const Duration(milliseconds: 800), () {
            if (!_dataPushed && mounted) {
              _chartReady = true;
              _pushData();
            }
          });
        },
      ))
      ..loadHtmlString(_htmlTemplate);
  }

  @override
  void didUpdateWidget(TradingViewChart old) {
    super.didUpdateWidget(old);
    if (old.candles != widget.candles) {
      _dataPushed = false;
      _pushData();
    }
  }

  void _pushData() {
    if (!_chartReady || widget.candles.isEmpty) return;
    final jsonList = widget.candles.map((c) => {
      'time': c.timestamp.millisecondsSinceEpoch ~/ 1000,
      'open': c.open,
      'high': c.high,
      'low': c.low,
      'close': c.close,
      'volume': c.volume,
    }).toList();
    final jsonStr = jsonEncode(jsonList);
    _controller.runJavaScript('if(typeof updateData!=="undefined")updateData($jsonStr)');
    _dataPushed = true;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: AppColors.chartBg,
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [
          BoxShadow(color: Color(0x14000000), blurRadius: 16, offset: Offset(0, 4)),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          // K线图区域
          SizedBox(
            height: 320,
            child: widget.loading
                ? const Center(
                    child: CupertinoActivityIndicator(
                      radius: 12,
                      color: Colors.white54,
                    ),
                  )
                : widget.candles.isEmpty
                    ? const Center(
                        child: Text('暂无K线数据',
                          style: TextStyle(color: Colors.white38, fontSize: 14,
                              decoration: TextDecoration.none)),
                      )
                    : WebViewWidget(controller: _controller),
          ),

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
                          ? AppColors.primary
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
      ),
    );
  }

  static const _htmlTemplate = '''
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #1A1D26; overflow: hidden; }
  #chart { width: 100%; height: 100vh; }
  #error { display: none; color: #8E8E93; font-size: 13px; text-align: center;
           position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
           font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
</style>
</head>
<body>
<div id="chart"></div>
<div id="error">K线加载中...</div>
<script>
  var chartReady = false;
  var scriptEl = document.createElement('script');
  scriptEl.src = 'https://cdn.jsdelivr.net/npm/lightweight-charts@5.1.0/dist/lightweight-charts.standalone.production.js';
  scriptEl.onload = function() { initChart(); };
  scriptEl.onerror = function() {
    document.getElementById('error').style.display = 'block';
    document.getElementById('error').textContent = 'K线库加载失败';
  };
  document.head.appendChild(scriptEl);

  var chart, candleSeries, volumeSeries, ma7Series, ma25Series;

  function initChart() {
    try {
      var container = document.getElementById('chart');
      chart = LightweightCharts.createChart(container, {
        layout: {
          background: { color: '#1A1D26' },
          textColor: '#8E8E93',
          fontSize: 11,
          fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
        },
        grid: {
          vertLines: { color: '#2A2D38' },
          horzLines: { color: '#2A2D38' },
        },
        crosshair: {
          mode: 0,
          vertLine: { color: '#8E8E9380', width: 1, style: 3, labelBackgroundColor: '#363A45' },
          horzLine: { color: '#8E8E9380', width: 1, style: 3, labelBackgroundColor: '#363A45' },
        },
        timeScale: {
          timeVisible: true,
          secondsVisible: false,
          borderColor: '#2A2D38',
          fixLeftEdge: true,
          fixRightEdge: true,
        },
        rightPriceScale: {
          borderColor: '#2A2D38',
          scaleMargins: { top: 0.05, bottom: 0.25 },
        },
        handleScroll: { vertTouchDrag: false },
      });

      candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
        upColor: '#34C759',
        downColor: '#FF3B30',
        borderUpColor: '#34C759',
        borderDownColor: '#FF3B30',
        wickUpColor: '#34C75990',
        wickDownColor: '#FF3B3090',
      });

      ma7Series = chart.addSeries(LightweightCharts.LineSeries, {
        color: '#FF9500',
        lineWidth: 1.5,
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });

      ma25Series = chart.addSeries(LightweightCharts.LineSeries, {
        color: '#5AC8FA',
        lineWidth: 1.5,
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });

      volumeSeries = chart.addSeries(LightweightCharts.HistogramSeries, {
        priceScaleId: 'volume',
        priceFormat: { type: 'volume' },
        lastValueVisible: false,
        priceLineVisible: false,
      });

      chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });

      // Resize observer
      new ResizeObserver(function() {
        chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
      }).observe(container);

      chartReady = true;

      // Notify Flutter
      try { window.FlutterBridge.postMessage('ready'); } catch(e) {}
    } catch(e) {
      document.getElementById('error').style.display = 'block';
      document.getElementById('error').textContent = 'Chart init error';
    }
  }

  function calcMA(data, period) {
    var result = [];
    for (var i = period - 1; i < data.length; i++) {
      var sum = 0;
      for (var j = 0; j < period; j++) sum += data[i - j].close;
      result.push({ time: data[i].time, value: sum / period });
    }
    return result;
  }

  function updateData(data) {
    try {
      if (!chartReady || !data || data.length === 0) return;

      candleSeries.setData(data.map(function(d) {
        return { time: d.time, open: d.open, high: d.high, low: d.low, close: d.close };
      }));

      ma7Series.setData(calcMA(data, 7));
      ma25Series.setData(calcMA(data, 25));

      volumeSeries.setData(data.map(function(d) {
        return {
          time: d.time,
          value: d.volume,
          color: d.close >= d.open ? 'rgba(52,199,89,0.25)' : 'rgba(255,59,48,0.25)'
        };
      }));

      chart.timeScale().fitContent();
    } catch(e) {
      console.error('updateData error:', e);
    }
  }
</script>
</body>
</html>
''';
}
