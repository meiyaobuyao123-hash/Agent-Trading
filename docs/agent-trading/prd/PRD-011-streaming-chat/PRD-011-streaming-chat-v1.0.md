# PRD-011: Agent 对话流式输出（打字机效果）

**版本**: v1.0
**日期**: 2026-03-24
**优先级**: P0（用户体验核心）
**状态**: 待开发

---

## 一、背景与问题

### 当前体验
```
用户发送消息 → 等待 5-30 秒（全程 loading 动画）→ 突然整段文字出现
```

### 问题
1. **用户焦虑**：不知道 Agent 是否在工作，可能以为卡死了
2. **等待时间感知长**：Claude API 响应 5-30 秒，纯等待体验极差
3. **与竞品差距大**：ChatGPT/Claude.ai/Gemini 全部支持流式打字机输出
4. **Agent chat 响应慢于其他接口**：因为需要 Claude 分析+工具调用，特别是 L3 多角色辩论时可能 20-30 秒

### 目标体验
```
用户发送消息 → 300ms 后开始逐字显示回复 → 持续输出直到完成
```

---

## 二、需求定义

### 2.1 核心需求

| # | 需求 | 优先级 | 说明 |
|---|------|--------|------|
| 1 | 后端 SSE 流式端点 | P0 | FastAPI StreamingResponse + Claude Streaming API |
| 2 | Flutter SSE 客户端 | P0 | 解析 text/event-stream，逐字更新 UI |
| 3 | 打字机 UI 效果 | P0 | 光标闪烁 + 逐字追加 + 自动滚动 |
| 4 | 策略创建兼容 | P0 | 流式文本结束后解析 tool_use，创建策略 |
| 5 | 错误恢复 | P1 | 流中断后自动重试或 fallback 到非流式 |
| 6 | 网络优化 | P1 | 弱网环境下的流式体验 |

### 2.2 技术选型

**SSE (Server-Sent Events)** vs WebSocket：

| | SSE | WebSocket |
|--|-----|-----------|
| 方向 | 服务端→客户端（单向） | 双向 |
| 协议 | HTTP/1.1 | 独立协议 |
| 重连 | 浏览器自动重连 | 需手动 |
| 复杂度 | 低 | 高 |
| nginx 兼容 | 原生支持 | 需配置 upgrade |
| 适用场景 | ✅ 聊天流式输出 | 实时双向通信 |

**选择 SSE**：我们只需要服务端到客户端的流式推送，SSE 更简单且与现有 nginx 配置完全兼容。

---

## 三、数据流设计

### 3.1 流式架构

```
用户输入
  ↓
Flutter: AgentService.chatStream(message)
  ↓
HTTP POST /api/agent/chat/stream
  Content-Type: application/json
  Accept: text/event-stream
  ↓
FastAPI: StreamingResponse (text/event-stream)
  ↓
LLMParser: client.messages.stream()
  ↓
Claude API (流式返回 tokens)
  ↓
逐 token yield SSE events:
  data: {"type":"delta","text":"你"}
  data: {"type":"delta","text":"好"}
  data: {"type":"delta","text":"！"}
  ...
  data: {"type":"strategy","data":{...}}  ← 如果有策略创建
  data: {"type":"done"}
  ↓
Flutter: Stream<String> → 逐字更新 UI
```

### 3.2 SSE 消息格式

```
# 开始信号
data: {"type":"start","id":"msg_xxx"}

# 文本块（核心，高频）
data: {"type":"delta","text":"你好"}
data: {"type":"delta","text":"，我是"}
data: {"type":"delta","text":"你的交易 Agent"}

# 策略创建（文本结束后）
data: {"type":"strategy","data":{"id":"xxx","name":"SOL高分热币","mode":"paper","status":"active"}}

# 需要确认
data: {"type":"confirm","message":"确认启用此策略？"}

# 完成
data: {"type":"done","total_tokens":1234}

# 错误
data: {"type":"error","message":"Claude API 超时"}
```

---

## 四、后端改动

### 4.1 新增端点

```
POST /api/agent/chat/stream
  Request: ChatRequest (同现有)
  Response: StreamingResponse (text/event-stream)
```

**保留原有 `/api/agent/chat`** 作为 fallback（非流式客户端兼容）。

### 4.2 LLMParser 新增方法

```python
async def parse_strategy_stream(self, message, user_id, history):
    """流式版本，yield SSE 事件"""

    # 1. 构建 messages
    messages = self._build_messages(message, history)

    # 2. Claude streaming
    async for event in self._stream_claude(messages):
        if event.type == "text_delta":
            yield {"type": "delta", "text": event.text}
        elif event.type == "tool_use":
            strategy = self._process_tool(event)
            yield {"type": "strategy", "data": strategy}

    yield {"type": "done"}
```

### 4.3 Claude Streaming API 用法

```python
with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=2048,
    system=SYSTEM_PROMPT,
    tools=[STRATEGY_TOOL],
    messages=messages,
) as stream:
    for event in stream:
        if event.type == "content_block_delta":
            if event.delta.type == "text_delta":
                yield event.delta.text
            elif event.delta.type == "input_json_delta":
                # 工具参数（策略 JSON）增量拼接
                tool_json += event.delta.partial_json
```

### 4.4 nginx 配置

```nginx
location /api/agent/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_read_timeout 120s;
    proxy_buffering off;        # ← 关键：禁用缓冲，让 SSE 实时推送
    proxy_cache off;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding on;
}
```

---

## 五、Flutter 改动

### 5.1 AgentService 新增 chatStream()

```dart
Stream<StreamEvent> chatStream(String message, {String? userId}) async* {
    final request = http.Request('POST', Uri.parse('$_baseUrl/api/agent/chat/stream'));
    request.headers['Content-Type'] = 'application/json';
    request.body = jsonEncode({'message': message, 'user_id': userId ?? _deviceId});

    final response = await _client.send(request);

    await for (final chunk in response.stream.transform(utf8.decoder)) {
        for (final line in chunk.split('\n')) {
            if (line.startsWith('data: ')) {
                final json = jsonDecode(line.substring(6));
                yield StreamEvent.fromJson(json);
            }
        }
    }
}
```

### 5.2 UI 打字机效果

```dart
class _StreamingMessage extends StatefulWidget {
    // 接收 Stream<String>，逐字追加显示
}

class _StreamingMessageState extends State<_StreamingMessage> {
    String _text = '';
    bool _isStreaming = true;

    void _onChunk(String chunk) {
        setState(() {
            _text += chunk;
        });
        _scrollToBottom();
    }

    Widget build(context) {
        return Row(
            children: [
                Expanded(child: Text(_text)),
                if (_isStreaming) _CursorBlink(),  // 闪烁光标
            ],
        );
    }
}
```

### 5.3 光标闪烁组件

```dart
class _CursorBlink extends StatefulWidget { ... }

// 500ms 闪烁周期的竖线 "|"
```

### 5.4 自动滚动

```dart
// 每次新 chunk 到达时
_scrollController.animateTo(
    _scrollController.position.maxScrollExtent,
    duration: Duration(milliseconds: 100),
    curve: Curves.easeOut,
);
```

---

## 六、错误处理

| 场景 | 处理 |
|------|------|
| Claude API 超时 | 流中断 → 发送 `{"type":"error"}` → Flutter 显示"重试"按钮 |
| 网络断开 | Flutter 检测流关闭 → 显示已接收内容 + "连接中断" |
| Claude 429 限流 | 后端重试 3 次（指数退避），期间 yield `{"type":"delta","text":"(思考中...)"}` |
| 策略 JSON 解析失败 | 文本正常显示，策略创建 fallback 到非流式 |
| nginx 缓冲 | 配置 `proxy_buffering off` 解决 |

---

## 七、性能对比

| 指标 | 当前（非流式） | 流式 |
|------|--------------|------|
| 首字延迟 | 5-30 秒 | **300-500ms** |
| 感知等待 | 全程等待 | **无感知等待** |
| 总时间 | 5-30 秒 | 5-30 秒（不变） |
| 网络传输 | 1 次大包 | 多次小包（+5% overhead） |
| API 费用 | 不变 | **不变**（streaming 不额外计费） |

**关键**：总时间不变，但用户感知完全不同。300ms 出第一个字 vs 30 秒后突然出全文。

---

## 八、兼容性

1. **原有 `/api/agent/chat`** 保留不动，旧客户端不受影响
2. **新增 `/api/agent/chat/stream`** 供 Flutter 使用
3. **Flutter fallback**：如果 stream 失败，自动 fallback 到非流式调用
4. **i18n**：流式内容跟随 Agent 语言设置，无需额外处理

---

## 九、改动文件清单

### 后端（3 文件）
| 文件 | 操作 | 改动 |
|------|------|------|
| `api/routes_agent.py` | 修改 | 新增 `/chat/stream` SSE 端点 |
| `agent/llm_parser.py` | 修改 | 新增 `parse_strategy_stream()` 异步生成器 |
| `nginx config` | 修改 | `/api/agent/` 加 `proxy_buffering off` |

### Flutter（3 文件）
| 文件 | 操作 | 改动 |
|------|------|------|
| `services/agent_service.dart` | 修改 | 新增 `chatStream()` 返回 `Stream<StreamEvent>` |
| `screens/agent/agent_screen.dart` | 修改 | `_send()` 改用流式 + 打字机 UI |
| `widgets/cursor_blink.dart` | 新建 | 光标闪烁组件 |

---

## 十、验证标准

| # | 验证项 | 通过标准 |
|---|--------|---------|
| 1 | 首字延迟 | < 500ms |
| 2 | 流式显示 | 文字逐字出现，无跳跃 |
| 3 | 光标闪烁 | 输出中有闪烁光标，结束后消失 |
| 4 | 自动滚动 | 新内容出现时自动滚到底部 |
| 5 | 策略创建 | 文字流式输出后，策略正确创建 |
| 6 | 错误恢复 | 网络中断后显示已接收内容 + 重试按钮 |
| 7 | 弱网 | 3G 环境下仍能逐字显示（可能更慢） |
| 8 | fallback | stream 端点不可用时自动降级到非流式 |
| 9 | i18n | 中英文流式输出正常 |
| 10 | 并发 | 多用户同时流式不互相影响 |
