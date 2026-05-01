---
name: Flutter UI 验证必须用原生模拟器
description: Flutter UI 验证走原生 iOS 模拟器,不要走 Flutter web preview
type: feedback
originSessionId: 3b12747c-a69c-445e-bdcc-c755d41a1638
---
Flutter UI 演示/验证**必须用原生 iOS 模拟器**(`flutter run -d <device-id>`),**不要走 Flutter web 模式 + preview_start 工具**。

**Why:** 用户已装好 iPhone 17 Pro Max 模拟器(`DBC925B5-7657-4410-B770-F21E4605A9D6`),要的就是真实原生 UI 体验。Flutter web 是为 web 项目准备的,跟原生 iOS 渲染、交互、性能都不一样。2026-05-01 用户原话:"我要原生 flutter,我电脑装了模拟器,我只是要你优化原来的 app 的 agent 模块,你是不是跑偏了"

**How to apply:**
- 启动 app:`cd apps/app && flutter run -d DBC925B5-7657-4410-B770-F21E4605A9D6 --dart-define=API_BASE_URL=http://43.156.207.26 --dart-define=HELIUS_API_KEY=a194f0cb-e6f5-474d-a9fc-d13b6e916964`(后台 `run_in_background=true`)
- 截图:`xcrun simctl io booted screenshot /tmp/xxx.png`
- 看输出文件:`Read /tmp/xxx.png`
- 不要在 launch.json 加 flutter-web 配置
- 不要建 flutter-app 软链接到 Aitrading100/(给 preview_start 用的)
- preview_start / preview_screenshot 这套工具是 web 项目用的,跟 Flutter 原生无关

**点击交互方案**(用户没开辅助访问权限,osascript 控制不了):
- 用户手动点击,我等他截图前提示
- 或者临时改 `_MainShellState._currentIndex` 默认值 + 在 didChangeDependencies 加自动调用,演示后**立即撤回**(不要 commit 测试性默认值)
- 撤回时确认 `_currentIndex = 0` + 不在 didChangeDependencies 调 _loadDemoThesis

**已知坑**:
- AgentService 是 singleton:用 `AgentService.instance.xxx()`,**不是** `AgentService()`(后者 build 报 "Couldn't find constructor 'AgentService'")
- pub get 国际化警告 `"ja": 15 untranslated message(s)` 不影响 build
- Pods.xcodeproj IPHONEOS_DEPLOYMENT_TARGET 9.0 警告也不影响 build(只是 deprecated)
- Firebase init 警告预期(待配置 google-services.json,见 CLAUDE.md 待执行清单)
