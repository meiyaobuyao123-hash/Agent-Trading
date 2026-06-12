// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Chinese (`zh`).
class SZh extends S {
  SZh([String locale = 'zh']) : super(locale);

  @override
  String get tabMarket => '行情';

  @override
  String get tabAgent => 'Agent';

  @override
  String get tabHistory => '历史';

  @override
  String get tabProfile => '我的';

  @override
  String get profileTitle => '我的';

  @override
  String get notificationSettings => '通知设置';

  @override
  String get newCoinPush => '新币榜推送';

  @override
  String get newCoinPushDesc => '每日 08:05 推送今日 Top10';

  @override
  String get hotCoinAlert => '热币预警';

  @override
  String get hotCoinAlertDesc => '热度突然飙升时推送';

  @override
  String get agentNotification => 'Agent 执行通知';

  @override
  String get agentNotificationDesc => '策略触发自动交易时推送';

  @override
  String get appearanceSettings => '外观设置';

  @override
  String get darkMode => '深色模式';

  @override
  String get darkModeOn => '开启';

  @override
  String get darkModeOff => '关闭';

  @override
  String get languageSettings => '语言设置';

  @override
  String get language => '语言';

  @override
  String get followSystem => '跟随系统';

  @override
  String get about => '关于';

  @override
  String get version => '版本';

  @override
  String get dataSource => '数据来源';

  @override
  String get riskWarning => '风险提示';

  @override
  String get comingSoon => '该功能即将上线';

  @override
  String get riskContent =>
      '本 App 提供的信号仅供参考，不构成投资建议。\n\nMeme 代币高度投机，存在归零风险。\n\n请根据自身风险承受能力独立决策，谨慎操作。';

  @override
  String get iKnow => '我知道了';

  @override
  String get deleteWallet => '删除钱包';

  @override
  String deleteWalletConfirm(String name) {
    return '确定删除 \"$name\" 吗？密钥将从设备中移除。';
  }

  @override
  String get cancel => '取消';

  @override
  String get delete => '删除';

  @override
  String get myWallets => '我的钱包';

  @override
  String get notImported => '未导入';

  @override
  String countUnit(int count) {
    return '$count 个';
  }

  @override
  String get walletImportHint => '导入钱包后，Agent 可以代你自动执行交易策略';

  @override
  String get defaultLabel => '默认';

  @override
  String get addressCopied => '地址已复制';

  @override
  String get importWallet => '导入钱包';

  @override
  String get addWallet => '添加钱包';

  @override
  String get marketTitle => '行情';

  @override
  String get hotCoins => '热币';

  @override
  String get smartMoney => '聪明钱';

  @override
  String get newCoins => '新币';

  @override
  String get all => '全部';

  @override
  String get strongPush => '强推';

  @override
  String get token => '代币';

  @override
  String get priceChange24hLabel => '价格 / 24h涨跌';

  @override
  String get priceHeatLabel => '价格 / 热度';

  @override
  String get scoreLabel => '评分';

  @override
  String get noHotCoins => '暂无热门代币';

  @override
  String get noSmartMoneySignals => '暂无聪明钱信号';

  @override
  String get noSignals => '暂无实时信号';

  @override
  String get pullToRefresh => '下拉刷新试试';

  @override
  String get loadFailed => '加载失败';

  @override
  String get retry => '重试';

  @override
  String get tapToRetry => '点击重试';

  @override
  String strongPushWithCount(int count) {
    return '$count 强推';
  }

  @override
  String tokenCountRealtime(int strong, int total) {
    return '$strong 强推 · $total 个代币 · 实时';
  }

  @override
  String strongSignalInfo(int strong, int total) {
    return '$strong 强信号 · $total 个代币 · 每5分钟更新';
  }

  @override
  String get scanInfo => '实时扫描 · pump.fun · 30s刷新';

  @override
  String strongNormal2h(int strong, int normal) {
    return '$strong 强推  $normal 普通  ·  每 2 小时更新';
  }

  @override
  String get realtimeSignals => '实时信号';

  @override
  String get watch => '关注';

  @override
  String get whenTokenAppears => '当有符合条件的代币时会自动出现';

  @override
  String buyersCount(int count) {
    return '$count人';
  }

  @override
  String get agentStrategy => 'Agent 策略';

  @override
  String get chatTab => '策略对话';

  @override
  String get myStrategyTab => '我的策略';

  @override
  String get noStrategiesYet => '还没有策略';

  @override
  String get createFirstStrategy => '去「策略对话」描述你的想法，创建第一个策略';

  @override
  String get dataSourceTab => '数据源';

  @override
  String get agentIntro =>
      '你好！我是你的 AI 交易助手。\n\n我能帮你：\n\n📊 创建自动交易策略\n• \"BTC 跌到 6 万自动买入\"\n• \"评分>70 的热币自动买 \$50\"\n• \"聪明钱买入时跟单\"\n\n🔍 回测验证策略效果\n• 用过去 7 天真实数据模拟测试\n\n📋 使用预设模板一键创建\n• MEME狙击 / 热币追涨 / 聪明钱跟单\n\n💡 试试说：\"推荐一个适合新手的策略\"';

  @override
  String strategyCreated(String name) {
    return '策略「$name」已创建并激活！\n系统将每 30 秒检查条件。\n可在「我的策略」标签页管理。';
  }

  @override
  String get cancelled => '已取消。你可以继续描述其他策略想法。';

  @override
  String get usageNotice => '使用须知';

  @override
  String get agentDisclaimer1 => '本工具仅提供数据分析和自动化执行能力，不构成任何投资建议。';

  @override
  String get riskSelfBorne => '所有交易策略由您自行设定，风险自担';

  @override
  String get noPlatformLicense => '平台不持有任何金融牌照';

  @override
  String get autoTradeRisk => '自动交易存在亏损风险，请谨慎设置参数';

  @override
  String get platformNotResponsible => '平台仅负责执行，不对收益或亏损承担责任';

  @override
  String get iReadAndAgree => '我已阅读并同意';

  @override
  String get confirmEnableStrategy => '确认启用策略';

  @override
  String get aboutToEnable => '您即将启用自动化交易策略，请确认：';

  @override
  String get paramSetByYou => '策略参数由您本人设定';

  @override
  String get understandRisk => '您了解自动交易的相关风险';

  @override
  String get platformExecuteOnly => '平台仅负责执行，不提供投资建议';

  @override
  String get confirmEnable => '确认启用';

  @override
  String cooldownTime(int minutes) {
    return '冷却时间: $minutes分钟';
  }

  @override
  String get unnamedStrategy => '未命名策略';

  @override
  String get securityStatement => '安全声明';

  @override
  String get walletDisclaimer1 =>
      '您的助记词/私钥仅存储在本设备系统加密区（iOS Keychain / Android Keystore）';

  @override
  String get walletDisclaimer2 => '我们的服务器从不接收、存储或传输您的私钥';

  @override
  String get walletDisclaimer3 => '所有交易均在设备本地签名后广播';

  @override
  String get walletDisclaimer4 => '本平台为非托管工具，不持有您的资金';

  @override
  String get walletDisclaimer5 => '请务必妥善备份助记词，丢失将无法找回';

  @override
  String get understood => '我已了解，继续';

  @override
  String get clipboardEmpty => '剪切板为空';

  @override
  String get enterMnemonic => '请输入助记词';

  @override
  String get enterPrivateKey => '请输入私钥';

  @override
  String get selectAtLeastOneChain => '请至少选择一条链';

  @override
  String importFailed(String error) {
    return '导入失败: $error';
  }

  @override
  String get selectChain => '选择链';

  @override
  String get walletNameLabel => '钱包名称（可选）';

  @override
  String get walletNameHint => '例如：主钱包';

  @override
  String get pasteFromClipboard => '从剪切板粘贴';

  @override
  String get mnemonic => '助记词';

  @override
  String get privateKey => '私钥';

  @override
  String get mnemonicMultiChain => '一个助记词自动派生多链地址';

  @override
  String get mnemonicHint => '输入 12 或 24 个助记词，用空格分隔';

  @override
  String get privateKeyHint => '输入私钥（十六进制或 Base58）';

  @override
  String get securityNote => '助记词和私钥仅存储在本设备的加密安全区域中，不会上传至任何服务器。请务必妥善保管备份。';

  @override
  String get running => '运行中';

  @override
  String get paused => '已暂停';

  @override
  String triggerInfo(int count, int minutes) {
    return '$count次触发 · $minutes分钟冷却';
  }

  @override
  String get noTradeRecords => '暂无交易记录';

  @override
  String get realizedProfit => '已实现收益';

  @override
  String get buy => '买入';

  @override
  String get sell => '卖出';

  @override
  String get successRate => '成功率';

  @override
  String allWithCount(int count) {
    return '全部 $count';
  }

  @override
  String buyWithCount(int count) {
    return '买入 $count';
  }

  @override
  String sellWithCount(int count) {
    return '卖出 $count';
  }

  @override
  String get noBuyRecords => '暂无买入记录';

  @override
  String get noSellRecords => '暂无卖出记录';

  @override
  String get tradeRecordHint => '当策略触发交易后，记录将在这里展示';

  @override
  String get txHashCopied => '交易哈希已复制';

  @override
  String get detail => '详情';

  @override
  String get totalInflow => '总流入';

  @override
  String get totalOutflow => '总流出';

  @override
  String get netFlowLabel => '净流入';

  @override
  String get wallet => '钱包';

  @override
  String buyerSellerCount(int buyers, int sellers) {
    return '$buyers买/$sellers卖';
  }

  @override
  String get buyOverview => '买入概览';

  @override
  String get sellOverview => '卖出概览';

  @override
  String walletTxInfo(int walletCount, int txCount) {
    return '$walletCount 个钱包 · $txCount 笔交易';
  }

  @override
  String avgPerTx(String amount) {
    return '均 $amount/笔';
  }

  @override
  String txCount(int count) {
    return '笔';
  }

  @override
  String get learnTier => '了解钱包分层';

  @override
  String get tierExplanation => '聪明钱分层说明';

  @override
  String get elite => '精英';

  @override
  String get verified => '认证';

  @override
  String get watching => '关注';

  @override
  String get eliteDesc => '胜率≥65%且≥10笔交易，信号权重×5';

  @override
  String get verifiedDesc => '胜率≥50%且≥5笔交易，信号权重×3';

  @override
  String get watchingDesc => '胜率≥40%且≥3笔交易，信号权重×1';

  @override
  String get tierSystemDesc => '系统追踪链上聪明钱钱包的历史交易表现，自动评级。精英钱包的买入信号可信度最高。';

  @override
  String copied(String address) {
    return '已复制 $address';
  }

  @override
  String mcLiquidity(String mc, String liquidity) {
    return 'MC $mc · 流动性 $liquidity';
  }

  @override
  String walletsCount(int count) {
    return '$count钱包';
  }

  @override
  String eliteCountLabel(int count) {
    return '($count精英)';
  }

  @override
  String buyVolume(String amount) {
    return '买 $amount';
  }

  @override
  String sellVolume(String amount) {
    return '卖 $amount';
  }

  @override
  String netAmount(String amount) {
    return '净$amount';
  }

  @override
  String get honeypotDetection => '蜜罐检测';

  @override
  String get dangerous => '危险';

  @override
  String get safe => '安全';

  @override
  String get contractOpenSource => '合约开源';

  @override
  String get yes => '是';

  @override
  String get no => '否';

  @override
  String get buyTax => '买入税';

  @override
  String get sellTax => '卖出税';

  @override
  String get top10Concentration => 'Top10 集中度';

  @override
  String get justNow => '刚刚';

  @override
  String minutesAgo(int minutes) {
    return '${minutes}m前';
  }

  @override
  String hoursAgo(int hours) {
    return '${hours}h前';
  }

  @override
  String daysAgo(int days) {
    return '${days}d前';
  }

  @override
  String get holders => '持有者';

  @override
  String get holderCount => '持有人数';

  @override
  String get top10Ratio => 'Top10 占比';

  @override
  String get top1Ratio => 'Top1 占比';

  @override
  String get noKlineData => '暂无K线数据';

  @override
  String get tokenTooNew => '该代币可能上线时间较短';

  @override
  String get chartLoadFailed => 'K线库加载失败，请检查网络';

  @override
  String get chartInitFailed => '图表初始化失败';

  @override
  String serverError(int code) {
    return '服务器错误 ($code)';
  }

  @override
  String get networkFailed => '网络连接失败，请检查后端服务是否启动';

  @override
  String get dataFormatError => '返回数据格式异常';

  @override
  String networkError(String error) {
    return '网络错误: $error';
  }

  @override
  String get unnamed => '未命名';

  @override
  String get mnemonicMustBe12or24 => '助记词必须是 12 或 24 个单词';

  @override
  String chainWallet(String chain) {
    return '$chain 钱包';
  }

  @override
  String get allChainsExist => '所有链的钱包均已存在';

  @override
  String get invalidPrivateKey => '无效的私钥';

  @override
  String get walletAlreadyExists => '该钱包已存在';

  @override
  String get disclaimerTitle => '使用须知 · Terms of Use';

  @override
  String get disclaimerScrollHint => '请仔细阅读并滑到底部后方可继续';

  @override
  String get disclaimerCheckbox =>
      '我已年满18岁，已阅读并理解上述全部条款，同意本应用的使用规则。\nI am 18+, have read and understood all terms above.';

  @override
  String get disclaimerAccept => '同意并进入  Agree & Continue';

  @override
  String get disclaimerScrollFirst => '请滑到底部并勾选  Scroll to bottom first';

  @override
  String get disclaimerReachedBottom => '— 已到达底部，请勾选同意 —';

  @override
  String get disclaimerGeoTitle => '服务地区限制 · Geographic Restriction';

  @override
  String get disclaimerGeoBody =>
      '本应用及其后端服务不向以下地区的用户提供任何服务：\n• 中华人民共和国大陆地区（中国大陆 IP 将被自动封禁）\n• 中国香港特别行政区\n• 中国澳门特别行政区\n• 中国台湾地区\n\nThis service is NOT available to users in:\n• Mainland China (PRC) — mainland CN IPs are automatically blocked\n• Hong Kong SAR\n• Macau SAR\n• Taiwan\n\n如您位于上述任一地区，请立即停止使用并卸载本应用。\nIf you are located in any of the above regions, please stop using and uninstall this app immediately.';

  @override
  String get disclaimerAdviceTitle => '非投资建议 · Not Investment Advice';

  @override
  String get disclaimerAdviceBody =>
      '本应用提供的所有内容，包括但不限于：代币评分、信号推送、聪明钱追踪、Agent策略，均为数据工具与信息参考，不构成任何形式的投资建议、财务建议或交易推荐。\n\nAll content provided by this app, including but not limited to token scoring, signal alerts, smart money tracking, and Agent strategies, is for informational purposes only and does NOT constitute investment advice, financial advice, or trading recommendations.';

  @override
  String get disclaimerAutoTradeTitle =>
      'Agent 自动交易风险 · Automated Trading Risk';

  @override
  String get disclaimerAutoTradeBody =>
      '• Agent 功能执行真实区块链交易，可能导致资产损失。\n• 加密资产市场波动剧烈，过往信号表现不代表未来结果。\n• 您对所有交易结果承担全部责任。\n\n• Agent feature executes real blockchain transactions, which may result in asset loss.\n• Crypto markets are highly volatile; past performance does not guarantee future results.\n• You bear full responsibility for all trading outcomes.';

  @override
  String get disclaimerWalletTitle => '钱包安全 · Wallet Security';

  @override
  String get disclaimerWalletBody =>
      '• 本应用为非托管钱包：您的私钥/助记词仅存储在您的设备本地，服务器从不接收。\n• 如您丢失设备或忘记助记词，资产将无法找回。\n• 请务必妥善备份您的助记词至安全的离线位置。\n\n• This is a non-custodial wallet: your private key/mnemonic is stored only on your device locally; our servers never receive it.\n• Lost device or forgotten mnemonic means unrecoverable assets.\n• Please back up your mnemonic to a secure offline location.';

  @override
  String get disclaimerLegalTitle => '法律声明 · Legal Disclaimer';

  @override
  String get disclaimerLegalBody =>
      '本应用不受任何金融监管机构监管，不持有任何投资顾问或金融服务牌照。使用本应用即表示您理解并承担所有相关风险。本条款受适用法律管辖。\n\nThis app is not regulated by any financial authority and holds no investment advisor or financial services license. By using this app, you acknowledge and accept all associated risks. These terms are governed by applicable law.';

  @override
  String get disclaimerVersionTitle => '版本 · Version';

  @override
  String get disclaimerVersionBody =>
      '本免责声明最后更新于 2026年3月。\nLast updated: March 2026.';

  @override
  String get hotCoinList => '热币榜';

  @override
  String get scanPumpFun => '实时扫描 pump.fun · 30s刷新';

  @override
  String get tradeDynamics => '交易动态';

  @override
  String get securityCheck => '安全检测';

  @override
  String get tokenInfo => '代币信息';

  @override
  String buyPressure(String pct) {
    return '买入';
  }

  @override
  String buyLabel(String count) {
    return '买 $count';
  }

  @override
  String sellLabel(String count) {
    return '卖 $count';
  }

  @override
  String get noSocialInfo => '暂无社交信息';

  @override
  String get contractAddress => '合约地址';

  @override
  String get blockExplorer => '区块浏览器';

  @override
  String get textCopied => '已复制';

  @override
  String distanceToGrad(String pct) {
    return '距离毕业还差 $pct%';
  }

  @override
  String get graduated => '已毕业';

  @override
  String get notGraduated => '未毕业';

  @override
  String daysUnit(String days) {
    return '$days天';
  }

  @override
  String get riskDetected => '有风险';

  @override
  String get securityUnavailable => '安全数据暂不可用';

  @override
  String get momentumM => '动量 M';

  @override
  String get qualityQ => '品质 Q';

  @override
  String get potentialP => '潜力 P';

  @override
  String get buySellRatio => '买卖比';

  @override
  String get smartMoneyLabel => '聪明钱';

  @override
  String get inflowAccel => '流入加速';

  @override
  String get creatorLabel => '创建者';

  @override
  String get buyerDiversity => '买家分散';

  @override
  String get socialLabel => '社交';

  @override
  String get progressSpeed => '进度速度';

  @override
  String get whaleBonus => '大单加成';

  @override
  String get aiStrongPush => 'AI 强推';

  @override
  String get aiWatch => 'AI 关注';

  @override
  String get aiObserve => 'AI 观望';

  @override
  String get stopLoss => '止损';

  @override
  String get takeProfit => '止盈';

  @override
  String get slippageLabel => '滑点';

  @override
  String get priorityFee => '优先费';

  @override
  String get advancedTradeSettings => '高级交易设置';

  @override
  String get tradingWallet => '交易钱包';

  @override
  String get describeStrategy => '描述你的策略想法...';

  @override
  String get pumpFunSource => '内盘实时 WebSocket + REST，BC进度、交易流、毕业事件';

  @override
  String get pumpFunStatus => '采集中';

  @override
  String get multiChainHot => '多链热币';

  @override
  String get multiChainHotDesc => 'SOL/BSC/Base/ETH 四链热币扫描，每2小时更新';

  @override
  String get connected => '已接入';

  @override
  String get kolSentiment => 'KOL 舆情';

  @override
  String get kolSentimentDesc => '212个 Twitter KOL 监控，共振信号检测，情绪分析';

  @override
  String get smartMoneySource => '聪明钱';

  @override
  String get smartMoneySourceDesc =>
      '多维度分层（Elite/Verified/Watching），60天衰减，Bot检测';

  @override
  String get okxDexDesc => '30条链，实时报价 + 执行引擎，支持自动交易';

  @override
  String get coinGeckoDesc => 'ATH/ATL、总供应量、社区数据等补充信息';

  @override
  String get detailTabQuotes => '行情';

  @override
  String get detailTabDetails => '详情';

  @override
  String get detailTabSecurity => '安全检测';

  @override
  String get marketCap => '市值';

  @override
  String get liquidityPool => '资金池';

  @override
  String get holderAddressCount => '持币地址数';

  @override
  String get tradingAddresses24h => '24h交易地址数';

  @override
  String get moreLabel => '更多';

  @override
  String get priceLabel => '价格';

  @override
  String get holderAddressTab => '持币地址';

  @override
  String get liquidityPoolTab => '资金池';

  @override
  String get devTokensTab => '开发者代币';

  @override
  String get buyTxCount => '买入笔数';

  @override
  String get sellTxCount => '卖出笔数';

  @override
  String get turnover => '成交额';

  @override
  String get netBuy => '净买入';

  @override
  String get holdersSmall => '持有人';

  @override
  String get liquiditySmall => '流动性';

  @override
  String get buySellColumn => '买/卖';

  @override
  String get allTrades => '所有交易';

  @override
  String get qtyTimeColumn => '数量 / 时间';

  @override
  String get valuePriceColumn => '价值 / 价格';

  @override
  String get addressColumn => '地址';

  @override
  String get liqMcRatio => '流/市值比';

  @override
  String get vol24h => '24h成交额';

  @override
  String get vol1h => '1h成交额';

  @override
  String get noDevTokenData => '暂无开发者代币数据';

  @override
  String get priceChangeLabel => '涨跌幅';

  @override
  String get volumeLabel => '成交量';

  @override
  String get totalTurnover => '成交总额';

  @override
  String get tradeCount => '交易笔数';

  @override
  String get keyData => '关键数据';

  @override
  String get circulatingMC => '流通市值';

  @override
  String get holderCountTop10 => '持有人数（Top10占比）';

  @override
  String get totalLiquidity => '总流动性';

  @override
  String get circulatingSupply => '流通供应量';

  @override
  String get maxSupplyLabel => '最大供应量';

  @override
  String get athLabel => '历史最高价';

  @override
  String get atlLabel => '历史最低价';

  @override
  String get basicInfo => '基础信息';

  @override
  String get mainChain => '主链';

  @override
  String get tokenFullName => '币种全称';

  @override
  String get createdTime => '创建时间';

  @override
  String aboutToken(String symbol) {
    return '关于 $symbol';
  }

  @override
  String get noDescription => '暂无简介';

  @override
  String get socialMedia => '社交媒体';

  @override
  String get searchOnX => '在 X 上搜索';

  @override
  String get searchName => '搜索名称';

  @override
  String get searchAddress => '搜索地址';

  @override
  String get securityDisclaimerText =>
      '本工具旨在提供代币安全性辅助判断，不应作为投资依据或推荐。请在交易前自行评估风险。';

  @override
  String get riskItems => '风险项';

  @override
  String get warningItems => '警示项';

  @override
  String get tf5m => '5分';

  @override
  String get tf15m => '15分';

  @override
  String get tf1hLabel => '1小时';

  @override
  String get tf4h => '4小时';

  @override
  String get tf1d => '1天';

  @override
  String get tf5min => '5分钟';

  @override
  String get tf1hour => '1小时';

  @override
  String get tf4hour => '4小时';

  @override
  String get tf24hour => '24小时';

  @override
  String get recentTrades => '最近交易';

  @override
  String get noTradePairData => '无交易对数据';

  @override
  String get noTradeData => '暂无交易数据';

  @override
  String secondsAgo(int seconds) {
    return '$seconds秒前';
  }

  @override
  String get vol24hShort => '24h量';

  @override
  String get vol1hShort => '1h量';

  @override
  String get liqMcShort => '流/市值';

  @override
  String get statusConfirmed => '已确认';

  @override
  String get statusFailed => '失败';

  @override
  String get statusSubmitting => '提交中';

  @override
  String get statusPending => '等待中';

  @override
  String get topHolders => '持仓排名';

  @override
  String get addressLabel => '地址';

  @override
  String get holdingPct => '占比';

  @override
  String get fundFlow24h => '24h 资金流向';

  @override
  String get netInflow => '净流入';

  @override
  String get netOutflow => '净流出';

  @override
  String get sellPressure => '卖出';

  @override
  String get totalBuy => '总买入';

  @override
  String get totalSell => '总卖出';

  @override
  String get largeOrders => '大额交易 (>\$10K)';

  @override
  String get largeBuy => '大额买入';

  @override
  String get largeSell => '大额卖出';

  @override
  String get tradeHistory => '交易分布';

  @override
  String get buySimple => '买入';

  @override
  String get sellSimple => '卖出';
}
