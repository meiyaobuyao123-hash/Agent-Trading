# Agent-Trading 文档中心

按功能模块划分，每个 PRD 下包含需求文档、技术方案、测试用例三位一体。

## 文档结构

```
docs/
├── agent-trading/                    # Agent 交易系统
│   └── prd/
│       ├── PRD-001-sell-execution/
│       │   ├── PRD-001-sell-execution-v1.0.md   # 需求文档
│       │   ├── TECH-001-v1.0.md                 # 技术方案
│       │   └── TEST-001-v1.0.md                 # 测试用例
│       ├── PRD-002-risk-manager-bugfix/
│       │   ├── PRD-002-risk-manager-bugfix-v1.0.md
│       │   ├── TECH-002-v1.0.md
│       │   └── TEST-002-v1.0.md
│       ├── PRD-003-win-rate-unification/
│       │   ├── PRD-003-win-rate-unification-v1.0.md
│       │   ├── TECH-003-v1.0.md
│       │   └── TEST-003-v1.0.md
│       └── PRD-004-medium-issues/
│           ├── PRD-004-medium-issues-v1.0.md
│           ├── TECH-004-v1.0.md
│           └── TEST-004-v1.0.md
│
├── hot-coins/                        # 热币榜单系统
├── smart-money/                      # 聪明钱追踪系统
├── pump-scanner/                     # pump.fun 内盘采集
├── btc-eth-investment/               # BTC/ETH 智能投资
├── portal/                           # 监控 Portal
├── flutter-app/                      # Flutter App
└── memory/                           # 项目记忆文件
```

## 命名规范

每个 PRD 一个独立目录，目录下放：
- `PRD-{编号}-{功能名}-v{版本}.md` — 需求文档
- `TECH-{编号}-v{版本}.md` — 技术方案
- `TEST-{编号}-v{版本}.md` — 测试用例

## 版本管理

功能升级时更新版本号（v1.0 → v1.1 → v2.0）。重大改版升大版本号，小修改升小版本号。

## 当前文档清单

| PRD | 优先级 | 标题 | 文档 | 状态 |
|-----|--------|------|------|------|
| PRD-001 | P0 | Agent 卖出执行 | PRD + TECH + TEST | 待开发 |
| PRD-002 | P0 | 风控管理器 Bug 修复 | PRD + TECH + TEST | 待开发 |
| PRD-003 | P0 | 胜率定义统一 | PRD + TECH + TEST | 待开发 |
| PRD-004 | P1 | 中等问题合集（5项） | PRD + TECH + TEST | 待开发 |
