# Agent-Trading 文档中心

按功能模块划分，每个模块下包含 PRD（需求）、Tech（技术）、Test（测试）三类文档。

## 文档结构

```
docs/
├── agent-trading/        # Agent 交易系统
│   ├── prd/              # 需求文档
│   │   ├── PRD-001-sell-execution-v1.0.md        # P0: 卖出执行
│   │   ├── PRD-002-risk-manager-bugfix-v1.0.md   # P0: 风控 Bug 修复
│   │   ├── PRD-003-win-rate-unification-v1.0.md  # P0: 胜率定义统一
│   │   └── PRD-004-medium-issues-v1.0.md         # P1: 中等问题合集
│   ├── tech/             # 技术文档
│   └── test/             # 测试文档
│
├── hot-coins/            # 热币榜单系统
│   ├── prd/
│   ├── tech/
│   └── test/
│
├── smart-money/          # 聪明钱追踪系统
│   ├── prd/
│   ├── tech/
│   └── test/
│
├── pump-scanner/         # pump.fun 内盘采集
│   ├── prd/
│   ├── tech/
│   └── test/
│
├── btc-eth-investment/   # BTC/ETH 智能投资
│   ├── prd/
│   ├── tech/
│   └── test/
│
├── portal/               # 监控 Portal
│   ├── prd/
│   ├── tech/
│   └── test/
│
├── flutter-app/          # Flutter App
│   ├── prd/
│   ├── tech/
│   └── test/
│
└── memory/               # 项目记忆文件（Claude 使用）
```

## 文档命名规范

- PRD: `PRD-{编号}-{功能名}-v{版本}.md`
- Tech: `TECH-{编号}-{功能名}-v{版本}.md`
- Test: `TEST-{编号}-{功能名}-v{版本}.md`

## 版本管理

每次功能升级时更新对应文档版本号（v1.0 → v1.1 → v2.0）。重大改版升大版本号，小修改升小版本号。

## 当前待修复问题

| PRD | 优先级 | 标题 | 状态 |
|-----|--------|------|------|
| PRD-001 | P0 | Agent 卖出执行功能 | 待开发 |
| PRD-002 | P0 | 风控管理器 Bug 修复 | 待开发 |
| PRD-003 | P0 | 胜率定义统一 | 待开发 |
| PRD-004 | P1 | 中等问题合集（5项） | 待开发 |
