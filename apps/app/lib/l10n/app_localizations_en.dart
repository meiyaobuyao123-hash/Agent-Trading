// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class SEn extends S {
  SEn([String locale = 'en']) : super(locale);

  @override
  String get tabMarket => 'Market';

  @override
  String get tabAgent => 'Agent';

  @override
  String get tabHistory => 'Signals';

  @override
  String get tabProfile => 'Profile';

  @override
  String get profileTitle => 'Profile';

  @override
  String get notificationSettings => 'Notifications';

  @override
  String get newCoinPush => 'New Coin Push';

  @override
  String get newCoinPushDesc => 'Daily Top 10 at 08:05';

  @override
  String get hotCoinAlert => 'Hot Coin Alert';

  @override
  String get hotCoinAlertDesc => 'Push when heat surges';

  @override
  String get agentNotification => 'Agent Notification';

  @override
  String get agentNotificationDesc => 'Push when strategy triggers a trade';

  @override
  String get appearanceSettings => 'Appearance';

  @override
  String get darkMode => 'Dark Mode';

  @override
  String get darkModeOn => 'On';

  @override
  String get darkModeOff => 'Off';

  @override
  String get languageSettings => 'Language';

  @override
  String get language => 'Language';

  @override
  String get followSystem => 'System Default';

  @override
  String get about => 'About';

  @override
  String get version => 'Version';

  @override
  String get dataSource => 'Data Source';

  @override
  String get riskWarning => 'Risk Warning';

  @override
  String get comingSoon => 'Coming soon';

  @override
  String get riskContent =>
      'Signals provided by this app are for reference only and do not constitute investment advice.\n\nMeme tokens are highly speculative and may lose all value.\n\nPlease make independent decisions based on your risk tolerance.';

  @override
  String get iKnow => 'Got it';

  @override
  String get deleteWallet => 'Delete Wallet';

  @override
  String deleteWalletConfirm(String name) {
    return 'Delete \"$name\"? The key will be removed from this device.';
  }

  @override
  String get cancel => 'Cancel';

  @override
  String get delete => 'Delete';

  @override
  String get myWallets => 'My Wallets';

  @override
  String get notImported => 'Not imported';

  @override
  String countUnit(int count) {
    return '$count';
  }

  @override
  String get walletImportHint =>
      'Import a wallet so Agent can auto-execute trading strategies for you';

  @override
  String get defaultLabel => 'Default';

  @override
  String get addressCopied => 'Address copied';

  @override
  String get importWallet => 'Import Wallet';

  @override
  String get addWallet => 'Add Wallet';

  @override
  String get marketTitle => 'Market';

  @override
  String get hotCoins => 'Hot';

  @override
  String get smartMoney => 'Smart \$';

  @override
  String get newCoins => 'New';

  @override
  String get all => 'All';

  @override
  String get strongPush => 'Top Pick';

  @override
  String get token => 'Token';

  @override
  String get priceChange24hLabel => 'Price / 24h Change';

  @override
  String get priceHeatLabel => 'Price / Heat';

  @override
  String get scoreLabel => 'Score';

  @override
  String get noHotCoins => 'No hot tokens';

  @override
  String get noSmartMoneySignals => 'No smart money signals';

  @override
  String get noSignals => 'No live signals';

  @override
  String get pullToRefresh => 'Pull to refresh';

  @override
  String get loadFailed => 'Load failed';

  @override
  String get retry => 'Retry';

  @override
  String get tapToRetry => 'Tap to retry';

  @override
  String strongPushWithCount(int count) {
    return '$count Top Picks';
  }

  @override
  String tokenCountRealtime(int strong, int total) {
    return '$strong Top · $total tokens · Live';
  }

  @override
  String strongSignalInfo(int strong, int total) {
    return '$strong strong · $total tokens · 5min update';
  }

  @override
  String get scanInfo => 'Live scan · pump.fun · 30s refresh';

  @override
  String strongNormal2h(int strong, int normal) {
    return '$strong top  $normal normal  ·  2h update';
  }

  @override
  String get realtimeSignals => 'Live Signals';

  @override
  String get watch => 'Watch';

  @override
  String get whenTokenAppears =>
      'Tokens meeting criteria will appear automatically';

  @override
  String buyersCount(int count) {
    return '$count buyers';
  }

  @override
  String get agentStrategy => 'Agent Strategy';

  @override
  String get chatTab => 'Chat';

  @override
  String get myStrategyTab => 'My Strategies';

  @override
  String get dataSourceTab => 'Data Source';

  @override
  String get agentIntro =>
      'Hi! I\'m your AI trading assistant.\n\nI can help you:\n\n📊 Create automated strategies\n• \"Buy BTC when it drops to \$60K\"\n• \"Auto-buy hot tokens scoring >70 for \$50\"\n• \"Follow smart money buys\"\n\n🔍 Backtest with real data\n• Test strategies against last 7 days\n\n📋 Use preset templates\n• MEME Sniper / Hot Breakout / Smart Money Follow\n\n💡 Try: \"Recommend a beginner-friendly strategy\"';

  @override
  String strategyCreated(String name) {
    return 'Strategy \"$name\" created and activated!\nSystem checks conditions every 30s.\nManage in \"My Strategies\" tab.';
  }

  @override
  String get cancelled =>
      'Cancelled. You can continue describing other strategy ideas.';

  @override
  String get usageNotice => 'Terms of Use';

  @override
  String get agentDisclaimer1 =>
      'This tool provides data analysis and automation only, and does not constitute investment advice.';

  @override
  String get riskSelfBorne =>
      'All trading strategies are set by you; risks are yours to bear';

  @override
  String get noPlatformLicense => 'The platform holds no financial license';

  @override
  String get autoTradeRisk =>
      'Automated trading carries loss risk; set parameters carefully';

  @override
  String get platformNotResponsible =>
      'Platform only executes; not responsible for gains or losses';

  @override
  String get iReadAndAgree => 'I have read and agree';

  @override
  String get confirmEnableStrategy => 'Confirm Enable Strategy';

  @override
  String get aboutToEnable =>
      'You are about to enable an automated trading strategy. Please confirm:';

  @override
  String get paramSetByYou => 'Strategy parameters are set by you';

  @override
  String get understandRisk => 'You understand the risks of automated trading';

  @override
  String get platformExecuteOnly =>
      'Platform only executes, no investment advice';

  @override
  String get confirmEnable => 'Confirm Enable';

  @override
  String cooldownTime(int minutes) {
    return 'Cooldown: $minutes min';
  }

  @override
  String get unnamedStrategy => 'Unnamed Strategy';

  @override
  String get securityStatement => 'Security Statement';

  @override
  String get walletDisclaimer1 =>
      'Your mnemonic/private key is stored only in your device\'s secure enclave (iOS Keychain / Android Keystore)';

  @override
  String get walletDisclaimer2 =>
      'Our servers never receive, store, or transmit your private key';

  @override
  String get walletDisclaimer3 =>
      'All transactions are signed locally on device then broadcast';

  @override
  String get walletDisclaimer4 =>
      'This is a non-custodial tool; we do not hold your funds';

  @override
  String get walletDisclaimer5 =>
      'Please back up your mnemonic safely; lost keys cannot be recovered';

  @override
  String get understood => 'I understand, continue';

  @override
  String get clipboardEmpty => 'Clipboard is empty';

  @override
  String get enterMnemonic => 'Please enter mnemonic';

  @override
  String get enterPrivateKey => 'Please enter private key';

  @override
  String get selectAtLeastOneChain => 'Select at least one chain';

  @override
  String importFailed(String error) {
    return 'Import failed: $error';
  }

  @override
  String get selectChain => 'Select Chain';

  @override
  String get walletNameLabel => 'Wallet name (optional)';

  @override
  String get walletNameHint => 'e.g. Main Wallet';

  @override
  String get pasteFromClipboard => 'Paste from clipboard';

  @override
  String get mnemonic => 'Mnemonic';

  @override
  String get privateKey => 'Private Key';

  @override
  String get mnemonicMultiChain => 'One mnemonic derives multi-chain addresses';

  @override
  String get mnemonicHint => 'Enter 12 or 24 words separated by spaces';

  @override
  String get privateKeyHint => 'Enter private key (hex or Base58)';

  @override
  String get securityNote =>
      'Mnemonic and private key are stored only in your device\'s encrypted secure area and will never be uploaded to any server. Please keep your backup safe.';

  @override
  String get running => 'Running';

  @override
  String get paused => 'Paused';

  @override
  String triggerInfo(int count, int minutes) {
    return '$count triggers · ${minutes}min cooldown';
  }

  @override
  String get noTradeRecords => 'No trade records';

  @override
  String get realizedProfit => 'Realized P&L';

  @override
  String get buy => 'Buy';

  @override
  String get sell => 'Sell';

  @override
  String get successRate => 'Win Rate';

  @override
  String allWithCount(int count) {
    return 'All $count';
  }

  @override
  String buyWithCount(int count) {
    return 'Buy $count';
  }

  @override
  String sellWithCount(int count) {
    return 'Sell $count';
  }

  @override
  String get noBuyRecords => 'No buy records';

  @override
  String get noSellRecords => 'No sell records';

  @override
  String get tradeRecordHint =>
      'Trade records will appear here when strategies trigger trades';

  @override
  String get txHashCopied => 'Tx hash copied';

  @override
  String get detail => 'Detail';

  @override
  String get totalInflow => 'Inflow';

  @override
  String get totalOutflow => 'Outflow';

  @override
  String get netFlowLabel => 'Net Flow';

  @override
  String get wallet => 'Wallets';

  @override
  String buyerSellerCount(int buyers, int sellers) {
    return '${buyers}B/${sellers}S';
  }

  @override
  String get buyOverview => 'Buy Overview';

  @override
  String get sellOverview => 'Sell Overview';

  @override
  String walletTxInfo(int walletCount, int txCount) {
    return '$walletCount wallets · $txCount txns';
  }

  @override
  String avgPerTx(String amount) {
    return 'Avg $amount/tx';
  }

  @override
  String txCount(int count) {
    return 'txns';
  }

  @override
  String get learnTier => 'About wallet tiers';

  @override
  String get tierExplanation => 'Smart Money Tier Guide';

  @override
  String get elite => 'Elite';

  @override
  String get verified => 'Verified';

  @override
  String get watching => 'Watching';

  @override
  String get eliteDesc => 'Win rate >=65% & >=10 trades, signal weight x5';

  @override
  String get verifiedDesc => 'Win rate >=50% & >=5 trades, signal weight x3';

  @override
  String get watchingDesc => 'Win rate >=40% & >=3 trades, signal weight x1';

  @override
  String get tierSystemDesc =>
      'System tracks on-chain smart money wallet performance and auto-rates them. Elite wallet buy signals are most reliable.';

  @override
  String copied(String address) {
    return 'Copied $address';
  }

  @override
  String mcLiquidity(String mc, String liquidity) {
    return 'MC $mc · Liq $liquidity';
  }

  @override
  String walletsCount(int count) {
    return '$count wallets';
  }

  @override
  String eliteCountLabel(int count) {
    return '($count elite)';
  }

  @override
  String buyVolume(String amount) {
    return 'Buy $amount';
  }

  @override
  String sellVolume(String amount) {
    return 'Sell $amount';
  }

  @override
  String netAmount(String amount) {
    return 'Net $amount';
  }

  @override
  String get honeypotDetection => 'Honeypot';

  @override
  String get dangerous => 'Danger';

  @override
  String get safe => 'Safe';

  @override
  String get contractOpenSource => 'Open Source';

  @override
  String get yes => 'Yes';

  @override
  String get no => 'No';

  @override
  String get buyTax => 'Buy Tax';

  @override
  String get sellTax => 'Sell Tax';

  @override
  String get top10Concentration => 'Top10 Concentration';

  @override
  String get justNow => 'Just now';

  @override
  String minutesAgo(int minutes) {
    return '${minutes}m ago';
  }

  @override
  String hoursAgo(int hours) {
    return '${hours}h ago';
  }

  @override
  String daysAgo(int days) {
    return '${days}d ago';
  }

  @override
  String get holders => 'Holders';

  @override
  String get holderCount => 'Holder Count';

  @override
  String get top10Ratio => 'Top10 Ratio';

  @override
  String get top1Ratio => 'Top1 Ratio';

  @override
  String get noKlineData => 'No K-line data';

  @override
  String get tokenTooNew => 'Token may be too new';

  @override
  String get chartLoadFailed => 'Chart failed to load, check network';

  @override
  String get chartInitFailed => 'Chart initialization failed';

  @override
  String serverError(int code) {
    return 'Server error ($code)';
  }

  @override
  String get networkFailed => 'Network failed, check if backend is running';

  @override
  String get dataFormatError => 'Invalid response format';

  @override
  String networkError(String error) {
    return 'Network error: $error';
  }

  @override
  String get unnamed => 'Unnamed';

  @override
  String get mnemonicMustBe12or24 => 'Mnemonic must be 12 or 24 words';

  @override
  String chainWallet(String chain) {
    return '$chain Wallet';
  }

  @override
  String get allChainsExist => 'Wallets already exist for all chains';

  @override
  String get invalidPrivateKey => 'Invalid private key';

  @override
  String get walletAlreadyExists => 'Wallet already exists';

  @override
  String get disclaimerTitle => 'Terms of Use';

  @override
  String get disclaimerScrollHint =>
      'Please read carefully and scroll to bottom';

  @override
  String get disclaimerCheckbox =>
      'I am 18+, have read and understood all terms above, and agree to the usage rules.\nI am 18+, have read and understood all terms above.';

  @override
  String get disclaimerAccept => 'Agree & Continue';

  @override
  String get disclaimerScrollFirst => 'Scroll to bottom first';

  @override
  String get disclaimerReachedBottom =>
      '— Reached bottom, please check to agree —';

  @override
  String get disclaimerGeoTitle => 'Geographic Restriction';

  @override
  String get disclaimerGeoBody =>
      'This service is NOT available to users in:\n• Mainland China (PRC) — mainland CN IPs are automatically blocked\n• Hong Kong SAR\n• Macau SAR\n• Taiwan\n\nIf you are located in any of the above regions, please stop using and uninstall this app immediately.';

  @override
  String get disclaimerAdviceTitle => 'Not Investment Advice';

  @override
  String get disclaimerAdviceBody =>
      'All content provided by this app, including but not limited to token scoring, signal alerts, smart money tracking, and Agent strategies, is for informational purposes only and does NOT constitute investment advice, financial advice, or trading recommendations.';

  @override
  String get disclaimerAutoTradeTitle => 'Automated Trading Risk';

  @override
  String get disclaimerAutoTradeBody =>
      '• Agent feature executes real blockchain transactions, which may result in asset loss.\n• Crypto markets are highly volatile; past performance does not guarantee future results.\n• You bear full responsibility for all trading outcomes.';

  @override
  String get disclaimerWalletTitle => 'Wallet Security';

  @override
  String get disclaimerWalletBody =>
      '• This is a non-custodial wallet: your private key/mnemonic is stored only on your device locally; our servers never receive it.\n• Lost device or forgotten mnemonic means unrecoverable assets.\n• Please back up your mnemonic to a secure offline location.';

  @override
  String get disclaimerLegalTitle => 'Legal Disclaimer';

  @override
  String get disclaimerLegalBody =>
      'This app is not regulated by any financial authority and holds no investment advisor or financial services license. By using this app, you acknowledge and accept all associated risks. These terms are governed by applicable law.';

  @override
  String get disclaimerVersionTitle => 'Version';

  @override
  String get disclaimerVersionBody => 'Last updated: March 2026.';

  @override
  String get hotCoinList => 'Hot Coins';

  @override
  String get scanPumpFun => 'Live scan pump.fun · 30s refresh';

  @override
  String get tradeDynamics => 'Trade Dynamics';

  @override
  String get securityCheck => 'Security Check';

  @override
  String get tokenInfo => 'Token Info';

  @override
  String buyPressure(String pct) {
    return 'Buy';
  }

  @override
  String buyLabel(String count) {
    return 'Buy $count';
  }

  @override
  String sellLabel(String count) {
    return 'Sell $count';
  }

  @override
  String get noSocialInfo => 'No social info';

  @override
  String get contractAddress => 'Contract Address';

  @override
  String get blockExplorer => 'Block Explorer';

  @override
  String get textCopied => 'Copied';

  @override
  String distanceToGrad(String pct) {
    return '$pct% to graduation';
  }

  @override
  String get graduated => 'Graduated';

  @override
  String get notGraduated => 'Not graduated';

  @override
  String daysUnit(String days) {
    return '${days}d';
  }

  @override
  String get riskDetected => 'Risk detected';

  @override
  String get securityUnavailable => 'Security data unavailable';

  @override
  String get momentumM => 'Momentum M';

  @override
  String get qualityQ => 'Quality Q';

  @override
  String get potentialP => 'Potential P';

  @override
  String get buySellRatio => 'Buy/Sell Ratio';

  @override
  String get smartMoneyLabel => 'Smart Money';

  @override
  String get inflowAccel => 'Inflow Accel';

  @override
  String get creatorLabel => 'Creator';

  @override
  String get buyerDiversity => 'Buyer Diversity';

  @override
  String get socialLabel => 'Social';

  @override
  String get progressSpeed => 'Progress Speed';

  @override
  String get whaleBonus => 'Whale Bonus';

  @override
  String get aiStrongPush => 'AI Top Pick';

  @override
  String get aiWatch => 'AI Watch';

  @override
  String get aiObserve => 'AI Observe';

  @override
  String get stopLoss => 'Stop Loss';

  @override
  String get takeProfit => 'Take Profit';

  @override
  String get slippageLabel => 'Slippage';

  @override
  String get priorityFee => 'Priority Fee';

  @override
  String get advancedTradeSettings => 'Advanced Trade Settings';

  @override
  String get tradingWallet => 'Trading Wallet';

  @override
  String get describeStrategy => 'Describe your strategy idea...';

  @override
  String get pumpFunSource =>
      'Real-time WebSocket + REST, BC progress, trade flow, graduation events';

  @override
  String get pumpFunStatus => 'Scanning';

  @override
  String get multiChainHot => 'Multi-chain Hot';

  @override
  String get multiChainHotDesc =>
      'SOL/BSC/Base/ETH 4-chain hot coin scan, 2h update';

  @override
  String get connected => 'Connected';

  @override
  String get kolSentiment => 'KOL Sentiment';

  @override
  String get kolSentimentDesc =>
      '212 Twitter KOL monitoring, resonance signal detection, sentiment analysis';

  @override
  String get smartMoneySource => 'Smart Money';

  @override
  String get smartMoneySourceDesc =>
      'Multi-tier (Elite/Verified/Watching), 60-day decay, Bot detection';

  @override
  String get okxDexDesc =>
      '30 chains, real-time quotes + execution engine, supports auto-trading';

  @override
  String get coinGeckoDesc => 'ATH/ATL, total supply, community data and more';

  @override
  String get detailTabQuotes => 'Quotes';

  @override
  String get detailTabDetails => 'Details';

  @override
  String get detailTabSecurity => 'Security';

  @override
  String get marketCap => 'MC';

  @override
  String get liquidityPool => 'Pool';

  @override
  String get holderAddressCount => 'Holders';

  @override
  String get tradingAddresses24h => '24h Traders';

  @override
  String get moreLabel => 'More';

  @override
  String get priceLabel => 'Price';

  @override
  String get holderAddressTab => 'Holders';

  @override
  String get liquidityPoolTab => 'Liquidity';

  @override
  String get devTokensTab => 'Dev Tokens';

  @override
  String get buyTxCount => 'Buy Count';

  @override
  String get sellTxCount => 'Sell Count';

  @override
  String get turnover => 'Volume';

  @override
  String get netBuy => 'Net Buy';

  @override
  String get holdersSmall => 'Holders';

  @override
  String get liquiditySmall => 'Liquidity';

  @override
  String get buySellColumn => 'Buy/Sell';

  @override
  String get allTrades => 'All Trades';

  @override
  String get qtyTimeColumn => 'Qty / Time';

  @override
  String get valuePriceColumn => 'Value / Price';

  @override
  String get addressColumn => 'Address';

  @override
  String get liqMcRatio => 'Liq/MC';

  @override
  String get vol24h => '24h Volume';

  @override
  String get vol1h => '1h Volume';

  @override
  String get noDevTokenData => 'No dev token data';

  @override
  String get priceChangeLabel => 'Change';

  @override
  String get volumeLabel => 'Volume';

  @override
  String get totalTurnover => 'Total Volume';

  @override
  String get tradeCount => 'Trade Count';

  @override
  String get keyData => 'Key Data';

  @override
  String get circulatingMC => 'Circulating MC';

  @override
  String get holderCountTop10 => 'Holders (Top10%)';

  @override
  String get totalLiquidity => 'Total Liquidity';

  @override
  String get circulatingSupply => 'Circ. Supply';

  @override
  String get maxSupplyLabel => 'Max Supply';

  @override
  String get athLabel => 'ATH';

  @override
  String get atlLabel => 'ATL';

  @override
  String get basicInfo => 'Basic Info';

  @override
  String get mainChain => 'Chain';

  @override
  String get tokenFullName => 'Full Name';

  @override
  String get createdTime => 'Created';

  @override
  String aboutToken(String symbol) {
    return 'About $symbol';
  }

  @override
  String get noDescription => 'No description';

  @override
  String get socialMedia => 'Social Media';

  @override
  String get searchOnX => 'Search on X';

  @override
  String get searchName => 'Search Name';

  @override
  String get searchAddress => 'Search Address';

  @override
  String get securityDisclaimerText =>
      'This tool provides security assessment assistance and should not be used as investment advice. Please evaluate risks before trading.';

  @override
  String get riskItems => 'Risk';

  @override
  String get warningItems => 'Warning';

  @override
  String get tf5m => '5m';

  @override
  String get tf15m => '15m';

  @override
  String get tf1hLabel => '1h';

  @override
  String get tf4h => '4h';

  @override
  String get tf1d => '1d';

  @override
  String get tf5min => '5min';

  @override
  String get tf1hour => '1h';

  @override
  String get tf4hour => '4h';

  @override
  String get tf24hour => '24h';

  @override
  String get recentTrades => 'Recent Trades';

  @override
  String get noTradePairData => 'No pair data';

  @override
  String get noTradeData => 'No trade data';

  @override
  String secondsAgo(int seconds) {
    return '${seconds}s ago';
  }

  @override
  String get vol24hShort => '24h Vol';

  @override
  String get vol1hShort => '1h Vol';

  @override
  String get liqMcShort => 'Liq/MC';

  @override
  String get statusConfirmed => 'Confirmed';

  @override
  String get statusFailed => 'Failed';

  @override
  String get statusSubmitting => 'Submitting';

  @override
  String get statusPending => 'Pending';

  @override
  String get topHolders => 'Top Holders';

  @override
  String get addressLabel => 'Address';

  @override
  String get holdingPct => 'Holding %';

  @override
  String get fundFlow24h => '24h Fund Flow';

  @override
  String get netInflow => 'Net Inflow';

  @override
  String get netOutflow => 'Net Outflow';

  @override
  String get sellPressure => 'Sell';

  @override
  String get totalBuy => 'Total Buy';

  @override
  String get totalSell => 'Total Sell';

  @override
  String get largeOrders => 'Large Orders (>\$10K)';

  @override
  String get largeBuy => 'Large Buy';

  @override
  String get largeSell => 'Large Sell';

  @override
  String get tradeHistory => 'Trade Distribution';

  @override
  String get buySimple => 'Buy';

  @override
  String get sellSimple => 'Sell';
}
