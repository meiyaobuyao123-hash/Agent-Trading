import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_ja.dart';
import 'app_localizations_ko.dart';
import 'app_localizations_zh.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of S
/// returned by `S.of(context)`.
///
/// Applications need to include `S.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: S.localizationsDelegates,
///   supportedLocales: S.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the S.supportedLocales
/// property.
abstract class S {
  S(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static S of(BuildContext context) {
    return Localizations.of<S>(context, S)!;
  }

  static const LocalizationsDelegate<S> delegate = _SDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('ja'),
    Locale('ko'),
    Locale('zh'),
  ];

  /// No description provided for @tabMarket.
  ///
  /// In zh, this message translates to:
  /// **'行情'**
  String get tabMarket;

  /// No description provided for @tabAgent.
  ///
  /// In zh, this message translates to:
  /// **'Agent'**
  String get tabAgent;

  /// No description provided for @tabHistory.
  ///
  /// In zh, this message translates to:
  /// **'历史'**
  String get tabHistory;

  /// No description provided for @tabProfile.
  ///
  /// In zh, this message translates to:
  /// **'我的'**
  String get tabProfile;

  /// No description provided for @profileTitle.
  ///
  /// In zh, this message translates to:
  /// **'我的'**
  String get profileTitle;

  /// No description provided for @notificationSettings.
  ///
  /// In zh, this message translates to:
  /// **'通知设置'**
  String get notificationSettings;

  /// No description provided for @newCoinPush.
  ///
  /// In zh, this message translates to:
  /// **'新币榜推送'**
  String get newCoinPush;

  /// No description provided for @newCoinPushDesc.
  ///
  /// In zh, this message translates to:
  /// **'每日 08:05 推送今日 Top10'**
  String get newCoinPushDesc;

  /// No description provided for @hotCoinAlert.
  ///
  /// In zh, this message translates to:
  /// **'热币预警'**
  String get hotCoinAlert;

  /// No description provided for @hotCoinAlertDesc.
  ///
  /// In zh, this message translates to:
  /// **'热度突然飙升时推送'**
  String get hotCoinAlertDesc;

  /// No description provided for @agentNotification.
  ///
  /// In zh, this message translates to:
  /// **'Agent 执行通知'**
  String get agentNotification;

  /// No description provided for @agentNotificationDesc.
  ///
  /// In zh, this message translates to:
  /// **'策略触发自动交易时推送'**
  String get agentNotificationDesc;

  /// No description provided for @appearanceSettings.
  ///
  /// In zh, this message translates to:
  /// **'外观设置'**
  String get appearanceSettings;

  /// No description provided for @darkMode.
  ///
  /// In zh, this message translates to:
  /// **'深色模式'**
  String get darkMode;

  /// No description provided for @darkModeOn.
  ///
  /// In zh, this message translates to:
  /// **'开启'**
  String get darkModeOn;

  /// No description provided for @darkModeOff.
  ///
  /// In zh, this message translates to:
  /// **'关闭'**
  String get darkModeOff;

  /// No description provided for @languageSettings.
  ///
  /// In zh, this message translates to:
  /// **'语言设置'**
  String get languageSettings;

  /// No description provided for @language.
  ///
  /// In zh, this message translates to:
  /// **'语言'**
  String get language;

  /// No description provided for @followSystem.
  ///
  /// In zh, this message translates to:
  /// **'跟随系统'**
  String get followSystem;

  /// No description provided for @about.
  ///
  /// In zh, this message translates to:
  /// **'关于'**
  String get about;

  /// No description provided for @version.
  ///
  /// In zh, this message translates to:
  /// **'版本'**
  String get version;

  /// No description provided for @dataSource.
  ///
  /// In zh, this message translates to:
  /// **'数据来源'**
  String get dataSource;

  /// No description provided for @riskWarning.
  ///
  /// In zh, this message translates to:
  /// **'风险提示'**
  String get riskWarning;

  /// No description provided for @comingSoon.
  ///
  /// In zh, this message translates to:
  /// **'该功能即将上线'**
  String get comingSoon;

  /// No description provided for @riskContent.
  ///
  /// In zh, this message translates to:
  /// **'本 App 提供的信号仅供参考，不构成投资建议。\n\nMeme 代币高度投机，存在归零风险。\n\n请根据自身风险承受能力独立决策，谨慎操作。'**
  String get riskContent;

  /// No description provided for @iKnow.
  ///
  /// In zh, this message translates to:
  /// **'我知道了'**
  String get iKnow;

  /// No description provided for @deleteWallet.
  ///
  /// In zh, this message translates to:
  /// **'删除钱包'**
  String get deleteWallet;

  /// No description provided for @deleteWalletConfirm.
  ///
  /// In zh, this message translates to:
  /// **'确定删除 \"{name}\" 吗？密钥将从设备中移除。'**
  String deleteWalletConfirm(String name);

  /// No description provided for @cancel.
  ///
  /// In zh, this message translates to:
  /// **'取消'**
  String get cancel;

  /// No description provided for @delete.
  ///
  /// In zh, this message translates to:
  /// **'删除'**
  String get delete;

  /// No description provided for @myWallets.
  ///
  /// In zh, this message translates to:
  /// **'我的钱包'**
  String get myWallets;

  /// No description provided for @notImported.
  ///
  /// In zh, this message translates to:
  /// **'未导入'**
  String get notImported;

  /// No description provided for @countUnit.
  ///
  /// In zh, this message translates to:
  /// **'{count} 个'**
  String countUnit(int count);

  /// No description provided for @walletImportHint.
  ///
  /// In zh, this message translates to:
  /// **'导入钱包后，Agent 可以代你自动执行交易策略'**
  String get walletImportHint;

  /// No description provided for @defaultLabel.
  ///
  /// In zh, this message translates to:
  /// **'默认'**
  String get defaultLabel;

  /// No description provided for @addressCopied.
  ///
  /// In zh, this message translates to:
  /// **'地址已复制'**
  String get addressCopied;

  /// No description provided for @importWallet.
  ///
  /// In zh, this message translates to:
  /// **'导入钱包'**
  String get importWallet;

  /// No description provided for @addWallet.
  ///
  /// In zh, this message translates to:
  /// **'添加钱包'**
  String get addWallet;

  /// No description provided for @marketTitle.
  ///
  /// In zh, this message translates to:
  /// **'行情'**
  String get marketTitle;

  /// No description provided for @hotCoins.
  ///
  /// In zh, this message translates to:
  /// **'热币'**
  String get hotCoins;

  /// No description provided for @smartMoney.
  ///
  /// In zh, this message translates to:
  /// **'聪明钱'**
  String get smartMoney;

  /// No description provided for @newCoins.
  ///
  /// In zh, this message translates to:
  /// **'新币'**
  String get newCoins;

  /// No description provided for @all.
  ///
  /// In zh, this message translates to:
  /// **'全部'**
  String get all;

  /// No description provided for @strongPush.
  ///
  /// In zh, this message translates to:
  /// **'强推'**
  String get strongPush;

  /// No description provided for @token.
  ///
  /// In zh, this message translates to:
  /// **'代币'**
  String get token;

  /// No description provided for @priceChange24hLabel.
  ///
  /// In zh, this message translates to:
  /// **'价格 / 24h涨跌'**
  String get priceChange24hLabel;

  /// No description provided for @priceHeatLabel.
  ///
  /// In zh, this message translates to:
  /// **'价格 / 热度'**
  String get priceHeatLabel;

  /// No description provided for @scoreLabel.
  ///
  /// In zh, this message translates to:
  /// **'评分'**
  String get scoreLabel;

  /// No description provided for @noHotCoins.
  ///
  /// In zh, this message translates to:
  /// **'暂无热门代币'**
  String get noHotCoins;

  /// No description provided for @noSmartMoneySignals.
  ///
  /// In zh, this message translates to:
  /// **'暂无聪明钱信号'**
  String get noSmartMoneySignals;

  /// No description provided for @noSignals.
  ///
  /// In zh, this message translates to:
  /// **'暂无实时信号'**
  String get noSignals;

  /// No description provided for @pullToRefresh.
  ///
  /// In zh, this message translates to:
  /// **'下拉刷新试试'**
  String get pullToRefresh;

  /// No description provided for @loadFailed.
  ///
  /// In zh, this message translates to:
  /// **'加载失败'**
  String get loadFailed;

  /// No description provided for @retry.
  ///
  /// In zh, this message translates to:
  /// **'重试'**
  String get retry;

  /// No description provided for @tapToRetry.
  ///
  /// In zh, this message translates to:
  /// **'点击重试'**
  String get tapToRetry;

  /// No description provided for @strongPushWithCount.
  ///
  /// In zh, this message translates to:
  /// **'{count} 强推'**
  String strongPushWithCount(int count);

  /// No description provided for @tokenCountRealtime.
  ///
  /// In zh, this message translates to:
  /// **'{strong} 强推 · {total} 个代币 · 实时'**
  String tokenCountRealtime(int strong, int total);

  /// No description provided for @strongSignalInfo.
  ///
  /// In zh, this message translates to:
  /// **'{strong} 强信号 · {total} 个代币 · 每5分钟更新'**
  String strongSignalInfo(int strong, int total);

  /// No description provided for @scanInfo.
  ///
  /// In zh, this message translates to:
  /// **'实时扫描 · pump.fun · 30s刷新'**
  String get scanInfo;

  /// No description provided for @strongNormal2h.
  ///
  /// In zh, this message translates to:
  /// **'{strong} 强推  {normal} 普通  ·  每 2 小时更新'**
  String strongNormal2h(int strong, int normal);

  /// No description provided for @realtimeSignals.
  ///
  /// In zh, this message translates to:
  /// **'实时信号'**
  String get realtimeSignals;

  /// No description provided for @watch.
  ///
  /// In zh, this message translates to:
  /// **'关注'**
  String get watch;

  /// No description provided for @whenTokenAppears.
  ///
  /// In zh, this message translates to:
  /// **'当有符合条件的代币时会自动出现'**
  String get whenTokenAppears;

  /// No description provided for @buyersCount.
  ///
  /// In zh, this message translates to:
  /// **'{count}人'**
  String buyersCount(int count);

  /// No description provided for @agentStrategy.
  ///
  /// In zh, this message translates to:
  /// **'Agent 策略'**
  String get agentStrategy;

  /// No description provided for @chatTab.
  ///
  /// In zh, this message translates to:
  /// **'策略对话'**
  String get chatTab;

  /// No description provided for @myStrategyTab.
  ///
  /// In zh, this message translates to:
  /// **'我的策略'**
  String get myStrategyTab;

  /// No description provided for @dataSourceTab.
  ///
  /// In zh, this message translates to:
  /// **'数据源'**
  String get dataSourceTab;

  /// No description provided for @agentIntro.
  ///
  /// In zh, this message translates to:
  /// **'你好！我是你的 AI 交易助手。\n\n我能帮你：\n\n📊 创建自动交易策略\n• \"BTC 跌到 6 万自动买入\"\n• \"评分>70 的热币自动买 \$50\"\n• \"聪明钱买入时跟单\"\n\n🔍 回测验证策略效果\n• 用过去 7 天真实数据模拟测试\n\n📋 使用预设模板一键创建\n• MEME狙击 / 热币追涨 / 聪明钱跟单\n\n💡 试试说：\"推荐一个适合新手的策略\"'**
  String get agentIntro;

  /// No description provided for @strategyCreated.
  ///
  /// In zh, this message translates to:
  /// **'策略「{name}」已创建并激活！\n系统将每 30 秒检查条件。\n可在「我的策略」标签页管理。'**
  String strategyCreated(String name);

  /// No description provided for @cancelled.
  ///
  /// In zh, this message translates to:
  /// **'已取消。你可以继续描述其他策略想法。'**
  String get cancelled;

  /// No description provided for @usageNotice.
  ///
  /// In zh, this message translates to:
  /// **'使用须知'**
  String get usageNotice;

  /// No description provided for @agentDisclaimer1.
  ///
  /// In zh, this message translates to:
  /// **'本工具仅提供数据分析和自动化执行能力，不构成任何投资建议。'**
  String get agentDisclaimer1;

  /// No description provided for @riskSelfBorne.
  ///
  /// In zh, this message translates to:
  /// **'所有交易策略由您自行设定，风险自担'**
  String get riskSelfBorne;

  /// No description provided for @noPlatformLicense.
  ///
  /// In zh, this message translates to:
  /// **'平台不持有任何金融牌照'**
  String get noPlatformLicense;

  /// No description provided for @autoTradeRisk.
  ///
  /// In zh, this message translates to:
  /// **'自动交易存在亏损风险，请谨慎设置参数'**
  String get autoTradeRisk;

  /// No description provided for @platformNotResponsible.
  ///
  /// In zh, this message translates to:
  /// **'平台仅负责执行，不对收益或亏损承担责任'**
  String get platformNotResponsible;

  /// No description provided for @iReadAndAgree.
  ///
  /// In zh, this message translates to:
  /// **'我已阅读并同意'**
  String get iReadAndAgree;

  /// No description provided for @confirmEnableStrategy.
  ///
  /// In zh, this message translates to:
  /// **'确认启用策略'**
  String get confirmEnableStrategy;

  /// No description provided for @aboutToEnable.
  ///
  /// In zh, this message translates to:
  /// **'您即将启用自动化交易策略，请确认：'**
  String get aboutToEnable;

  /// No description provided for @paramSetByYou.
  ///
  /// In zh, this message translates to:
  /// **'策略参数由您本人设定'**
  String get paramSetByYou;

  /// No description provided for @understandRisk.
  ///
  /// In zh, this message translates to:
  /// **'您了解自动交易的相关风险'**
  String get understandRisk;

  /// No description provided for @platformExecuteOnly.
  ///
  /// In zh, this message translates to:
  /// **'平台仅负责执行，不提供投资建议'**
  String get platformExecuteOnly;

  /// No description provided for @confirmEnable.
  ///
  /// In zh, this message translates to:
  /// **'确认启用'**
  String get confirmEnable;

  /// No description provided for @cooldownTime.
  ///
  /// In zh, this message translates to:
  /// **'冷却时间: {minutes}分钟'**
  String cooldownTime(int minutes);

  /// No description provided for @unnamedStrategy.
  ///
  /// In zh, this message translates to:
  /// **'未命名策略'**
  String get unnamedStrategy;

  /// No description provided for @securityStatement.
  ///
  /// In zh, this message translates to:
  /// **'安全声明'**
  String get securityStatement;

  /// No description provided for @walletDisclaimer1.
  ///
  /// In zh, this message translates to:
  /// **'您的助记词/私钥仅存储在本设备系统加密区（iOS Keychain / Android Keystore）'**
  String get walletDisclaimer1;

  /// No description provided for @walletDisclaimer2.
  ///
  /// In zh, this message translates to:
  /// **'我们的服务器从不接收、存储或传输您的私钥'**
  String get walletDisclaimer2;

  /// No description provided for @walletDisclaimer3.
  ///
  /// In zh, this message translates to:
  /// **'所有交易均在设备本地签名后广播'**
  String get walletDisclaimer3;

  /// No description provided for @walletDisclaimer4.
  ///
  /// In zh, this message translates to:
  /// **'本平台为非托管工具，不持有您的资金'**
  String get walletDisclaimer4;

  /// No description provided for @walletDisclaimer5.
  ///
  /// In zh, this message translates to:
  /// **'请务必妥善备份助记词，丢失将无法找回'**
  String get walletDisclaimer5;

  /// No description provided for @understood.
  ///
  /// In zh, this message translates to:
  /// **'我已了解，继续'**
  String get understood;

  /// No description provided for @clipboardEmpty.
  ///
  /// In zh, this message translates to:
  /// **'剪切板为空'**
  String get clipboardEmpty;

  /// No description provided for @enterMnemonic.
  ///
  /// In zh, this message translates to:
  /// **'请输入助记词'**
  String get enterMnemonic;

  /// No description provided for @enterPrivateKey.
  ///
  /// In zh, this message translates to:
  /// **'请输入私钥'**
  String get enterPrivateKey;

  /// No description provided for @selectAtLeastOneChain.
  ///
  /// In zh, this message translates to:
  /// **'请至少选择一条链'**
  String get selectAtLeastOneChain;

  /// No description provided for @importFailed.
  ///
  /// In zh, this message translates to:
  /// **'导入失败: {error}'**
  String importFailed(String error);

  /// No description provided for @selectChain.
  ///
  /// In zh, this message translates to:
  /// **'选择链'**
  String get selectChain;

  /// No description provided for @walletNameLabel.
  ///
  /// In zh, this message translates to:
  /// **'钱包名称（可选）'**
  String get walletNameLabel;

  /// No description provided for @walletNameHint.
  ///
  /// In zh, this message translates to:
  /// **'例如：主钱包'**
  String get walletNameHint;

  /// No description provided for @pasteFromClipboard.
  ///
  /// In zh, this message translates to:
  /// **'从剪切板粘贴'**
  String get pasteFromClipboard;

  /// No description provided for @mnemonic.
  ///
  /// In zh, this message translates to:
  /// **'助记词'**
  String get mnemonic;

  /// No description provided for @privateKey.
  ///
  /// In zh, this message translates to:
  /// **'私钥'**
  String get privateKey;

  /// No description provided for @mnemonicMultiChain.
  ///
  /// In zh, this message translates to:
  /// **'一个助记词自动派生多链地址'**
  String get mnemonicMultiChain;

  /// No description provided for @mnemonicHint.
  ///
  /// In zh, this message translates to:
  /// **'输入 12 或 24 个助记词，用空格分隔'**
  String get mnemonicHint;

  /// No description provided for @privateKeyHint.
  ///
  /// In zh, this message translates to:
  /// **'输入私钥（十六进制或 Base58）'**
  String get privateKeyHint;

  /// No description provided for @securityNote.
  ///
  /// In zh, this message translates to:
  /// **'助记词和私钥仅存储在本设备的加密安全区域中，不会上传至任何服务器。请务必妥善保管备份。'**
  String get securityNote;

  /// No description provided for @running.
  ///
  /// In zh, this message translates to:
  /// **'运行中'**
  String get running;

  /// No description provided for @paused.
  ///
  /// In zh, this message translates to:
  /// **'已暂停'**
  String get paused;

  /// No description provided for @triggerInfo.
  ///
  /// In zh, this message translates to:
  /// **'{count}次触发 · {minutes}分钟冷却'**
  String triggerInfo(int count, int minutes);

  /// No description provided for @noTradeRecords.
  ///
  /// In zh, this message translates to:
  /// **'暂无交易记录'**
  String get noTradeRecords;

  /// No description provided for @realizedProfit.
  ///
  /// In zh, this message translates to:
  /// **'已实现收益'**
  String get realizedProfit;

  /// No description provided for @buy.
  ///
  /// In zh, this message translates to:
  /// **'买入'**
  String get buy;

  /// No description provided for @sell.
  ///
  /// In zh, this message translates to:
  /// **'卖出'**
  String get sell;

  /// No description provided for @successRate.
  ///
  /// In zh, this message translates to:
  /// **'成功率'**
  String get successRate;

  /// No description provided for @allWithCount.
  ///
  /// In zh, this message translates to:
  /// **'全部 {count}'**
  String allWithCount(int count);

  /// No description provided for @buyWithCount.
  ///
  /// In zh, this message translates to:
  /// **'买入 {count}'**
  String buyWithCount(int count);

  /// No description provided for @sellWithCount.
  ///
  /// In zh, this message translates to:
  /// **'卖出 {count}'**
  String sellWithCount(int count);

  /// No description provided for @noBuyRecords.
  ///
  /// In zh, this message translates to:
  /// **'暂无买入记录'**
  String get noBuyRecords;

  /// No description provided for @noSellRecords.
  ///
  /// In zh, this message translates to:
  /// **'暂无卖出记录'**
  String get noSellRecords;

  /// No description provided for @tradeRecordHint.
  ///
  /// In zh, this message translates to:
  /// **'当策略触发交易后，记录将在这里展示'**
  String get tradeRecordHint;

  /// No description provided for @txHashCopied.
  ///
  /// In zh, this message translates to:
  /// **'交易哈希已复制'**
  String get txHashCopied;

  /// No description provided for @detail.
  ///
  /// In zh, this message translates to:
  /// **'详情'**
  String get detail;

  /// No description provided for @totalInflow.
  ///
  /// In zh, this message translates to:
  /// **'总流入'**
  String get totalInflow;

  /// No description provided for @totalOutflow.
  ///
  /// In zh, this message translates to:
  /// **'总流出'**
  String get totalOutflow;

  /// No description provided for @netFlowLabel.
  ///
  /// In zh, this message translates to:
  /// **'净流入'**
  String get netFlowLabel;

  /// No description provided for @wallet.
  ///
  /// In zh, this message translates to:
  /// **'钱包'**
  String get wallet;

  /// No description provided for @buyerSellerCount.
  ///
  /// In zh, this message translates to:
  /// **'{buyers}买/{sellers}卖'**
  String buyerSellerCount(int buyers, int sellers);

  /// No description provided for @buyOverview.
  ///
  /// In zh, this message translates to:
  /// **'买入概览'**
  String get buyOverview;

  /// No description provided for @sellOverview.
  ///
  /// In zh, this message translates to:
  /// **'卖出概览'**
  String get sellOverview;

  /// No description provided for @walletTxInfo.
  ///
  /// In zh, this message translates to:
  /// **'{walletCount} 个钱包 · {txCount} 笔交易'**
  String walletTxInfo(int walletCount, int txCount);

  /// No description provided for @avgPerTx.
  ///
  /// In zh, this message translates to:
  /// **'均 {amount}/笔'**
  String avgPerTx(String amount);

  /// No description provided for @txCount.
  ///
  /// In zh, this message translates to:
  /// **'笔'**
  String txCount(int count);

  /// No description provided for @learnTier.
  ///
  /// In zh, this message translates to:
  /// **'了解钱包分层'**
  String get learnTier;

  /// No description provided for @tierExplanation.
  ///
  /// In zh, this message translates to:
  /// **'聪明钱分层说明'**
  String get tierExplanation;

  /// No description provided for @elite.
  ///
  /// In zh, this message translates to:
  /// **'精英'**
  String get elite;

  /// No description provided for @verified.
  ///
  /// In zh, this message translates to:
  /// **'认证'**
  String get verified;

  /// No description provided for @watching.
  ///
  /// In zh, this message translates to:
  /// **'关注'**
  String get watching;

  /// No description provided for @eliteDesc.
  ///
  /// In zh, this message translates to:
  /// **'胜率≥65%且≥10笔交易，信号权重×5'**
  String get eliteDesc;

  /// No description provided for @verifiedDesc.
  ///
  /// In zh, this message translates to:
  /// **'胜率≥50%且≥5笔交易，信号权重×3'**
  String get verifiedDesc;

  /// No description provided for @watchingDesc.
  ///
  /// In zh, this message translates to:
  /// **'胜率≥40%且≥3笔交易，信号权重×1'**
  String get watchingDesc;

  /// No description provided for @tierSystemDesc.
  ///
  /// In zh, this message translates to:
  /// **'系统追踪链上聪明钱钱包的历史交易表现，自动评级。精英钱包的买入信号可信度最高。'**
  String get tierSystemDesc;

  /// No description provided for @copied.
  ///
  /// In zh, this message translates to:
  /// **'已复制 {address}'**
  String copied(String address);

  /// No description provided for @mcLiquidity.
  ///
  /// In zh, this message translates to:
  /// **'MC {mc} · 流动性 {liquidity}'**
  String mcLiquidity(String mc, String liquidity);

  /// No description provided for @walletsCount.
  ///
  /// In zh, this message translates to:
  /// **'{count}钱包'**
  String walletsCount(int count);

  /// No description provided for @eliteCountLabel.
  ///
  /// In zh, this message translates to:
  /// **'({count}精英)'**
  String eliteCountLabel(int count);

  /// No description provided for @buyVolume.
  ///
  /// In zh, this message translates to:
  /// **'买 {amount}'**
  String buyVolume(String amount);

  /// No description provided for @sellVolume.
  ///
  /// In zh, this message translates to:
  /// **'卖 {amount}'**
  String sellVolume(String amount);

  /// No description provided for @netAmount.
  ///
  /// In zh, this message translates to:
  /// **'净{amount}'**
  String netAmount(String amount);

  /// No description provided for @honeypotDetection.
  ///
  /// In zh, this message translates to:
  /// **'蜜罐检测'**
  String get honeypotDetection;

  /// No description provided for @dangerous.
  ///
  /// In zh, this message translates to:
  /// **'危险'**
  String get dangerous;

  /// No description provided for @safe.
  ///
  /// In zh, this message translates to:
  /// **'安全'**
  String get safe;

  /// No description provided for @contractOpenSource.
  ///
  /// In zh, this message translates to:
  /// **'合约开源'**
  String get contractOpenSource;

  /// No description provided for @yes.
  ///
  /// In zh, this message translates to:
  /// **'是'**
  String get yes;

  /// No description provided for @no.
  ///
  /// In zh, this message translates to:
  /// **'否'**
  String get no;

  /// No description provided for @buyTax.
  ///
  /// In zh, this message translates to:
  /// **'买入税'**
  String get buyTax;

  /// No description provided for @sellTax.
  ///
  /// In zh, this message translates to:
  /// **'卖出税'**
  String get sellTax;

  /// No description provided for @top10Concentration.
  ///
  /// In zh, this message translates to:
  /// **'Top10 集中度'**
  String get top10Concentration;

  /// No description provided for @justNow.
  ///
  /// In zh, this message translates to:
  /// **'刚刚'**
  String get justNow;

  /// No description provided for @minutesAgo.
  ///
  /// In zh, this message translates to:
  /// **'{minutes}m前'**
  String minutesAgo(int minutes);

  /// No description provided for @hoursAgo.
  ///
  /// In zh, this message translates to:
  /// **'{hours}h前'**
  String hoursAgo(int hours);

  /// No description provided for @daysAgo.
  ///
  /// In zh, this message translates to:
  /// **'{days}d前'**
  String daysAgo(int days);

  /// No description provided for @holders.
  ///
  /// In zh, this message translates to:
  /// **'持有者'**
  String get holders;

  /// No description provided for @holderCount.
  ///
  /// In zh, this message translates to:
  /// **'持有人数'**
  String get holderCount;

  /// No description provided for @top10Ratio.
  ///
  /// In zh, this message translates to:
  /// **'Top10 占比'**
  String get top10Ratio;

  /// No description provided for @top1Ratio.
  ///
  /// In zh, this message translates to:
  /// **'Top1 占比'**
  String get top1Ratio;

  /// No description provided for @noKlineData.
  ///
  /// In zh, this message translates to:
  /// **'暂无K线数据'**
  String get noKlineData;

  /// No description provided for @tokenTooNew.
  ///
  /// In zh, this message translates to:
  /// **'该代币可能上线时间较短'**
  String get tokenTooNew;

  /// No description provided for @chartLoadFailed.
  ///
  /// In zh, this message translates to:
  /// **'K线库加载失败，请检查网络'**
  String get chartLoadFailed;

  /// No description provided for @chartInitFailed.
  ///
  /// In zh, this message translates to:
  /// **'图表初始化失败'**
  String get chartInitFailed;

  /// No description provided for @serverError.
  ///
  /// In zh, this message translates to:
  /// **'服务器错误 ({code})'**
  String serverError(int code);

  /// No description provided for @networkFailed.
  ///
  /// In zh, this message translates to:
  /// **'网络连接失败，请检查后端服务是否启动'**
  String get networkFailed;

  /// No description provided for @dataFormatError.
  ///
  /// In zh, this message translates to:
  /// **'返回数据格式异常'**
  String get dataFormatError;

  /// No description provided for @networkError.
  ///
  /// In zh, this message translates to:
  /// **'网络错误: {error}'**
  String networkError(String error);

  /// No description provided for @unnamed.
  ///
  /// In zh, this message translates to:
  /// **'未命名'**
  String get unnamed;

  /// No description provided for @mnemonicMustBe12or24.
  ///
  /// In zh, this message translates to:
  /// **'助记词必须是 12 或 24 个单词'**
  String get mnemonicMustBe12or24;

  /// No description provided for @chainWallet.
  ///
  /// In zh, this message translates to:
  /// **'{chain} 钱包'**
  String chainWallet(String chain);

  /// No description provided for @allChainsExist.
  ///
  /// In zh, this message translates to:
  /// **'所有链的钱包均已存在'**
  String get allChainsExist;

  /// No description provided for @invalidPrivateKey.
  ///
  /// In zh, this message translates to:
  /// **'无效的私钥'**
  String get invalidPrivateKey;

  /// No description provided for @walletAlreadyExists.
  ///
  /// In zh, this message translates to:
  /// **'该钱包已存在'**
  String get walletAlreadyExists;

  /// No description provided for @disclaimerTitle.
  ///
  /// In zh, this message translates to:
  /// **'使用须知 · Terms of Use'**
  String get disclaimerTitle;

  /// No description provided for @disclaimerScrollHint.
  ///
  /// In zh, this message translates to:
  /// **'请仔细阅读并滑到底部后方可继续'**
  String get disclaimerScrollHint;

  /// No description provided for @disclaimerCheckbox.
  ///
  /// In zh, this message translates to:
  /// **'我已年满18岁，已阅读并理解上述全部条款，同意本应用的使用规则。\nI am 18+, have read and understood all terms above.'**
  String get disclaimerCheckbox;

  /// No description provided for @disclaimerAccept.
  ///
  /// In zh, this message translates to:
  /// **'同意并进入  Agree & Continue'**
  String get disclaimerAccept;

  /// No description provided for @disclaimerScrollFirst.
  ///
  /// In zh, this message translates to:
  /// **'请滑到底部并勾选  Scroll to bottom first'**
  String get disclaimerScrollFirst;

  /// No description provided for @disclaimerReachedBottom.
  ///
  /// In zh, this message translates to:
  /// **'— 已到达底部，请勾选同意 —'**
  String get disclaimerReachedBottom;

  /// No description provided for @disclaimerGeoTitle.
  ///
  /// In zh, this message translates to:
  /// **'服务地区限制 · Geographic Restriction'**
  String get disclaimerGeoTitle;

  /// No description provided for @disclaimerGeoBody.
  ///
  /// In zh, this message translates to:
  /// **'本应用及其后端服务不向以下地区的用户提供任何服务：\n• 中华人民共和国大陆地区（中国大陆 IP 将被自动封禁）\n• 中国香港特别行政区\n• 中国澳门特别行政区\n• 中国台湾地区\n\nThis service is NOT available to users in:\n• Mainland China (PRC) — mainland CN IPs are automatically blocked\n• Hong Kong SAR\n• Macau SAR\n• Taiwan\n\n如您位于上述任一地区，请立即停止使用并卸载本应用。\nIf you are located in any of the above regions, please stop using and uninstall this app immediately.'**
  String get disclaimerGeoBody;

  /// No description provided for @disclaimerAdviceTitle.
  ///
  /// In zh, this message translates to:
  /// **'非投资建议 · Not Investment Advice'**
  String get disclaimerAdviceTitle;

  /// No description provided for @disclaimerAdviceBody.
  ///
  /// In zh, this message translates to:
  /// **'本应用提供的所有内容，包括但不限于：代币评分、信号推送、聪明钱追踪、Agent策略，均为数据工具与信息参考，不构成任何形式的投资建议、财务建议或交易推荐。\n\nAll content provided by this app, including but not limited to token scoring, signal alerts, smart money tracking, and Agent strategies, is for informational purposes only and does NOT constitute investment advice, financial advice, or trading recommendations.'**
  String get disclaimerAdviceBody;

  /// No description provided for @disclaimerAutoTradeTitle.
  ///
  /// In zh, this message translates to:
  /// **'Agent 自动交易风险 · Automated Trading Risk'**
  String get disclaimerAutoTradeTitle;

  /// No description provided for @disclaimerAutoTradeBody.
  ///
  /// In zh, this message translates to:
  /// **'• Agent 功能执行真实区块链交易，可能导致资产损失。\n• 加密资产市场波动剧烈，过往信号表现不代表未来结果。\n• 您对所有交易结果承担全部责任。\n\n• Agent feature executes real blockchain transactions, which may result in asset loss.\n• Crypto markets are highly volatile; past performance does not guarantee future results.\n• You bear full responsibility for all trading outcomes.'**
  String get disclaimerAutoTradeBody;

  /// No description provided for @disclaimerWalletTitle.
  ///
  /// In zh, this message translates to:
  /// **'钱包安全 · Wallet Security'**
  String get disclaimerWalletTitle;

  /// No description provided for @disclaimerWalletBody.
  ///
  /// In zh, this message translates to:
  /// **'• 本应用为非托管钱包：您的私钥/助记词仅存储在您的设备本地，服务器从不接收。\n• 如您丢失设备或忘记助记词，资产将无法找回。\n• 请务必妥善备份您的助记词至安全的离线位置。\n\n• This is a non-custodial wallet: your private key/mnemonic is stored only on your device locally; our servers never receive it.\n• Lost device or forgotten mnemonic means unrecoverable assets.\n• Please back up your mnemonic to a secure offline location.'**
  String get disclaimerWalletBody;

  /// No description provided for @disclaimerLegalTitle.
  ///
  /// In zh, this message translates to:
  /// **'法律声明 · Legal Disclaimer'**
  String get disclaimerLegalTitle;

  /// No description provided for @disclaimerLegalBody.
  ///
  /// In zh, this message translates to:
  /// **'本应用不受任何金融监管机构监管，不持有任何投资顾问或金融服务牌照。使用本应用即表示您理解并承担所有相关风险。本条款受适用法律管辖。\n\nThis app is not regulated by any financial authority and holds no investment advisor or financial services license. By using this app, you acknowledge and accept all associated risks. These terms are governed by applicable law.'**
  String get disclaimerLegalBody;

  /// No description provided for @disclaimerVersionTitle.
  ///
  /// In zh, this message translates to:
  /// **'版本 · Version'**
  String get disclaimerVersionTitle;

  /// No description provided for @disclaimerVersionBody.
  ///
  /// In zh, this message translates to:
  /// **'本免责声明最后更新于 2026年3月。\nLast updated: March 2026.'**
  String get disclaimerVersionBody;

  /// No description provided for @hotCoinList.
  ///
  /// In zh, this message translates to:
  /// **'热币榜'**
  String get hotCoinList;

  /// No description provided for @scanPumpFun.
  ///
  /// In zh, this message translates to:
  /// **'实时扫描 pump.fun · 30s刷新'**
  String get scanPumpFun;

  /// Recent signal review hint (shown when live pool is empty)
  String get recentSignalReview;

  /// No description provided for @tradeDynamics.
  ///
  /// In zh, this message translates to:
  /// **'交易动态'**
  String get tradeDynamics;

  /// No description provided for @securityCheck.
  ///
  /// In zh, this message translates to:
  /// **'安全检测'**
  String get securityCheck;

  /// No description provided for @tokenInfo.
  ///
  /// In zh, this message translates to:
  /// **'代币信息'**
  String get tokenInfo;

  /// No description provided for @buyPressure.
  ///
  /// In zh, this message translates to:
  /// **'买入'**
  String buyPressure(String pct);

  /// No description provided for @buyLabel.
  ///
  /// In zh, this message translates to:
  /// **'买 {count}'**
  String buyLabel(String count);

  /// No description provided for @sellLabel.
  ///
  /// In zh, this message translates to:
  /// **'卖 {count}'**
  String sellLabel(String count);

  /// No description provided for @noSocialInfo.
  ///
  /// In zh, this message translates to:
  /// **'暂无社交信息'**
  String get noSocialInfo;

  /// No description provided for @contractAddress.
  ///
  /// In zh, this message translates to:
  /// **'合约地址'**
  String get contractAddress;

  /// No description provided for @blockExplorer.
  ///
  /// In zh, this message translates to:
  /// **'区块浏览器'**
  String get blockExplorer;

  /// No description provided for @textCopied.
  ///
  /// In zh, this message translates to:
  /// **'已复制'**
  String get textCopied;

  /// No description provided for @distanceToGrad.
  ///
  /// In zh, this message translates to:
  /// **'距离毕业还差 {pct}%'**
  String distanceToGrad(String pct);

  /// No description provided for @graduated.
  ///
  /// In zh, this message translates to:
  /// **'已毕业'**
  String get graduated;

  /// No description provided for @notGraduated.
  ///
  /// In zh, this message translates to:
  /// **'未毕业'**
  String get notGraduated;

  /// No description provided for @daysUnit.
  ///
  /// In zh, this message translates to:
  /// **'{days}天'**
  String daysUnit(String days);

  /// No description provided for @riskDetected.
  ///
  /// In zh, this message translates to:
  /// **'有风险'**
  String get riskDetected;

  /// No description provided for @securityUnavailable.
  ///
  /// In zh, this message translates to:
  /// **'安全数据暂不可用'**
  String get securityUnavailable;

  /// No description provided for @momentumM.
  ///
  /// In zh, this message translates to:
  /// **'动量 M'**
  String get momentumM;

  /// No description provided for @qualityQ.
  ///
  /// In zh, this message translates to:
  /// **'品质 Q'**
  String get qualityQ;

  /// No description provided for @potentialP.
  ///
  /// In zh, this message translates to:
  /// **'潜力 P'**
  String get potentialP;

  /// No description provided for @buySellRatio.
  ///
  /// In zh, this message translates to:
  /// **'买卖比'**
  String get buySellRatio;

  /// No description provided for @smartMoneyLabel.
  ///
  /// In zh, this message translates to:
  /// **'聪明钱'**
  String get smartMoneyLabel;

  /// No description provided for @inflowAccel.
  ///
  /// In zh, this message translates to:
  /// **'流入加速'**
  String get inflowAccel;

  /// No description provided for @creatorLabel.
  ///
  /// In zh, this message translates to:
  /// **'创建者'**
  String get creatorLabel;

  /// No description provided for @buyerDiversity.
  ///
  /// In zh, this message translates to:
  /// **'买家分散'**
  String get buyerDiversity;

  /// No description provided for @socialLabel.
  ///
  /// In zh, this message translates to:
  /// **'社交'**
  String get socialLabel;

  /// No description provided for @progressSpeed.
  ///
  /// In zh, this message translates to:
  /// **'进度速度'**
  String get progressSpeed;

  /// No description provided for @whaleBonus.
  ///
  /// In zh, this message translates to:
  /// **'大单加成'**
  String get whaleBonus;

  /// No description provided for @aiStrongPush.
  ///
  /// In zh, this message translates to:
  /// **'AI 强推'**
  String get aiStrongPush;

  /// No description provided for @aiWatch.
  ///
  /// In zh, this message translates to:
  /// **'AI 关注'**
  String get aiWatch;

  /// No description provided for @aiObserve.
  ///
  /// In zh, this message translates to:
  /// **'AI 观望'**
  String get aiObserve;

  /// No description provided for @stopLoss.
  ///
  /// In zh, this message translates to:
  /// **'止损'**
  String get stopLoss;

  /// No description provided for @takeProfit.
  ///
  /// In zh, this message translates to:
  /// **'止盈'**
  String get takeProfit;

  /// No description provided for @slippageLabel.
  ///
  /// In zh, this message translates to:
  /// **'滑点'**
  String get slippageLabel;

  /// No description provided for @priorityFee.
  ///
  /// In zh, this message translates to:
  /// **'优先费'**
  String get priorityFee;

  /// No description provided for @advancedTradeSettings.
  ///
  /// In zh, this message translates to:
  /// **'高级交易设置'**
  String get advancedTradeSettings;

  /// No description provided for @tradingWallet.
  ///
  /// In zh, this message translates to:
  /// **'交易钱包'**
  String get tradingWallet;

  /// No description provided for @describeStrategy.
  ///
  /// In zh, this message translates to:
  /// **'描述你的策略想法...'**
  String get describeStrategy;

  /// No description provided for @pumpFunSource.
  ///
  /// In zh, this message translates to:
  /// **'内盘实时 WebSocket + REST，BC进度、交易流、毕业事件'**
  String get pumpFunSource;

  /// No description provided for @pumpFunStatus.
  ///
  /// In zh, this message translates to:
  /// **'采集中'**
  String get pumpFunStatus;

  /// No description provided for @multiChainHot.
  ///
  /// In zh, this message translates to:
  /// **'多链热币'**
  String get multiChainHot;

  /// No description provided for @multiChainHotDesc.
  ///
  /// In zh, this message translates to:
  /// **'SOL/BSC/Base/ETH 四链热币扫描，每2小时更新'**
  String get multiChainHotDesc;

  /// No description provided for @connected.
  ///
  /// In zh, this message translates to:
  /// **'已接入'**
  String get connected;

  /// No description provided for @kolSentiment.
  ///
  /// In zh, this message translates to:
  /// **'KOL 舆情'**
  String get kolSentiment;

  /// No description provided for @kolSentimentDesc.
  ///
  /// In zh, this message translates to:
  /// **'212个 Twitter KOL 监控，共振信号检测，情绪分析'**
  String get kolSentimentDesc;

  /// No description provided for @smartMoneySource.
  ///
  /// In zh, this message translates to:
  /// **'聪明钱'**
  String get smartMoneySource;

  /// No description provided for @smartMoneySourceDesc.
  ///
  /// In zh, this message translates to:
  /// **'多维度分层（Elite/Verified/Watching），60天衰减，Bot检测'**
  String get smartMoneySourceDesc;

  /// No description provided for @okxDexDesc.
  ///
  /// In zh, this message translates to:
  /// **'30条链，实时报价 + 执行引擎，支持自动交易'**
  String get okxDexDesc;

  /// No description provided for @coinGeckoDesc.
  ///
  /// In zh, this message translates to:
  /// **'ATH/ATL、总供应量、社区数据等补充信息'**
  String get coinGeckoDesc;

  /// No description provided for @detailTabQuotes.
  ///
  /// In zh, this message translates to:
  /// **'行情'**
  String get detailTabQuotes;

  /// No description provided for @detailTabDetails.
  ///
  /// In zh, this message translates to:
  /// **'详情'**
  String get detailTabDetails;

  /// No description provided for @detailTabSecurity.
  ///
  /// In zh, this message translates to:
  /// **'安全检测'**
  String get detailTabSecurity;

  /// No description provided for @marketCap.
  ///
  /// In zh, this message translates to:
  /// **'市值'**
  String get marketCap;

  /// No description provided for @liquidityPool.
  ///
  /// In zh, this message translates to:
  /// **'资金池'**
  String get liquidityPool;

  /// No description provided for @holderAddressCount.
  ///
  /// In zh, this message translates to:
  /// **'持币地址数'**
  String get holderAddressCount;

  /// No description provided for @tradingAddresses24h.
  ///
  /// In zh, this message translates to:
  /// **'24h交易地址数'**
  String get tradingAddresses24h;

  /// No description provided for @moreLabel.
  ///
  /// In zh, this message translates to:
  /// **'更多'**
  String get moreLabel;

  /// No description provided for @priceLabel.
  ///
  /// In zh, this message translates to:
  /// **'价格'**
  String get priceLabel;

  /// No description provided for @holderAddressTab.
  ///
  /// In zh, this message translates to:
  /// **'持币地址'**
  String get holderAddressTab;

  /// No description provided for @liquidityPoolTab.
  ///
  /// In zh, this message translates to:
  /// **'资金池'**
  String get liquidityPoolTab;

  /// No description provided for @devTokensTab.
  ///
  /// In zh, this message translates to:
  /// **'开发者代币'**
  String get devTokensTab;

  /// No description provided for @buyTxCount.
  ///
  /// In zh, this message translates to:
  /// **'买入笔数'**
  String get buyTxCount;

  /// No description provided for @sellTxCount.
  ///
  /// In zh, this message translates to:
  /// **'卖出笔数'**
  String get sellTxCount;

  /// No description provided for @turnover.
  ///
  /// In zh, this message translates to:
  /// **'成交额'**
  String get turnover;

  /// No description provided for @netBuy.
  ///
  /// In zh, this message translates to:
  /// **'净买入'**
  String get netBuy;

  /// No description provided for @holdersSmall.
  ///
  /// In zh, this message translates to:
  /// **'持有人'**
  String get holdersSmall;

  /// No description provided for @liquiditySmall.
  ///
  /// In zh, this message translates to:
  /// **'流动性'**
  String get liquiditySmall;

  /// No description provided for @buySellColumn.
  ///
  /// In zh, this message translates to:
  /// **'买/卖'**
  String get buySellColumn;

  /// No description provided for @allTrades.
  ///
  /// In zh, this message translates to:
  /// **'所有交易'**
  String get allTrades;

  /// No description provided for @qtyTimeColumn.
  ///
  /// In zh, this message translates to:
  /// **'数量 / 时间'**
  String get qtyTimeColumn;

  /// No description provided for @valuePriceColumn.
  ///
  /// In zh, this message translates to:
  /// **'价值 / 价格'**
  String get valuePriceColumn;

  /// No description provided for @addressColumn.
  ///
  /// In zh, this message translates to:
  /// **'地址'**
  String get addressColumn;

  /// No description provided for @liqMcRatio.
  ///
  /// In zh, this message translates to:
  /// **'流/市值比'**
  String get liqMcRatio;

  /// No description provided for @vol24h.
  ///
  /// In zh, this message translates to:
  /// **'24h成交额'**
  String get vol24h;

  /// No description provided for @vol1h.
  ///
  /// In zh, this message translates to:
  /// **'1h成交额'**
  String get vol1h;

  /// No description provided for @noDevTokenData.
  ///
  /// In zh, this message translates to:
  /// **'暂无开发者代币数据'**
  String get noDevTokenData;

  /// No description provided for @priceChangeLabel.
  ///
  /// In zh, this message translates to:
  /// **'涨跌幅'**
  String get priceChangeLabel;

  /// No description provided for @volumeLabel.
  ///
  /// In zh, this message translates to:
  /// **'成交量'**
  String get volumeLabel;

  /// No description provided for @totalTurnover.
  ///
  /// In zh, this message translates to:
  /// **'成交总额'**
  String get totalTurnover;

  /// No description provided for @tradeCount.
  ///
  /// In zh, this message translates to:
  /// **'交易笔数'**
  String get tradeCount;

  /// No description provided for @keyData.
  ///
  /// In zh, this message translates to:
  /// **'关键数据'**
  String get keyData;

  /// No description provided for @circulatingMC.
  ///
  /// In zh, this message translates to:
  /// **'流通市值'**
  String get circulatingMC;

  /// No description provided for @holderCountTop10.
  ///
  /// In zh, this message translates to:
  /// **'持有人数（Top10占比）'**
  String get holderCountTop10;

  /// No description provided for @totalLiquidity.
  ///
  /// In zh, this message translates to:
  /// **'总流动性'**
  String get totalLiquidity;

  /// No description provided for @circulatingSupply.
  ///
  /// In zh, this message translates to:
  /// **'流通供应量'**
  String get circulatingSupply;

  /// No description provided for @maxSupplyLabel.
  ///
  /// In zh, this message translates to:
  /// **'最大供应量'**
  String get maxSupplyLabel;

  /// No description provided for @athLabel.
  ///
  /// In zh, this message translates to:
  /// **'历史最高价'**
  String get athLabel;

  /// No description provided for @atlLabel.
  ///
  /// In zh, this message translates to:
  /// **'历史最低价'**
  String get atlLabel;

  /// No description provided for @basicInfo.
  ///
  /// In zh, this message translates to:
  /// **'基础信息'**
  String get basicInfo;

  /// No description provided for @mainChain.
  ///
  /// In zh, this message translates to:
  /// **'主链'**
  String get mainChain;

  /// No description provided for @tokenFullName.
  ///
  /// In zh, this message translates to:
  /// **'币种全称'**
  String get tokenFullName;

  /// No description provided for @createdTime.
  ///
  /// In zh, this message translates to:
  /// **'创建时间'**
  String get createdTime;

  /// No description provided for @aboutToken.
  ///
  /// In zh, this message translates to:
  /// **'关于 {symbol}'**
  String aboutToken(String symbol);

  /// No description provided for @noDescription.
  ///
  /// In zh, this message translates to:
  /// **'暂无简介'**
  String get noDescription;

  /// No description provided for @socialMedia.
  ///
  /// In zh, this message translates to:
  /// **'社交媒体'**
  String get socialMedia;

  /// No description provided for @searchOnX.
  ///
  /// In zh, this message translates to:
  /// **'在 X 上搜索'**
  String get searchOnX;

  /// No description provided for @searchName.
  ///
  /// In zh, this message translates to:
  /// **'搜索名称'**
  String get searchName;

  /// No description provided for @searchAddress.
  ///
  /// In zh, this message translates to:
  /// **'搜索地址'**
  String get searchAddress;

  /// No description provided for @securityDisclaimerText.
  ///
  /// In zh, this message translates to:
  /// **'本工具旨在提供代币安全性辅助判断，不应作为投资依据或推荐。请在交易前自行评估风险。'**
  String get securityDisclaimerText;

  /// No description provided for @riskItems.
  ///
  /// In zh, this message translates to:
  /// **'风险项'**
  String get riskItems;

  /// No description provided for @warningItems.
  ///
  /// In zh, this message translates to:
  /// **'警示项'**
  String get warningItems;

  /// No description provided for @tf5m.
  ///
  /// In zh, this message translates to:
  /// **'5分'**
  String get tf5m;

  /// No description provided for @tf15m.
  ///
  /// In zh, this message translates to:
  /// **'15分'**
  String get tf15m;

  /// No description provided for @tf1hLabel.
  ///
  /// In zh, this message translates to:
  /// **'1小时'**
  String get tf1hLabel;

  /// No description provided for @tf4h.
  ///
  /// In zh, this message translates to:
  /// **'4小时'**
  String get tf4h;

  /// No description provided for @tf1d.
  ///
  /// In zh, this message translates to:
  /// **'1天'**
  String get tf1d;

  /// No description provided for @tf5min.
  ///
  /// In zh, this message translates to:
  /// **'5分钟'**
  String get tf5min;

  /// No description provided for @tf1hour.
  ///
  /// In zh, this message translates to:
  /// **'1小时'**
  String get tf1hour;

  /// No description provided for @tf4hour.
  ///
  /// In zh, this message translates to:
  /// **'4小时'**
  String get tf4hour;

  /// No description provided for @tf24hour.
  ///
  /// In zh, this message translates to:
  /// **'24小时'**
  String get tf24hour;

  /// No description provided for @recentTrades.
  ///
  /// In zh, this message translates to:
  /// **'最近交易'**
  String get recentTrades;

  /// No description provided for @noTradePairData.
  ///
  /// In zh, this message translates to:
  /// **'无交易对数据'**
  String get noTradePairData;

  /// No description provided for @noTradeData.
  ///
  /// In zh, this message translates to:
  /// **'暂无交易数据'**
  String get noTradeData;

  /// No description provided for @secondsAgo.
  ///
  /// In zh, this message translates to:
  /// **'{seconds}秒前'**
  String secondsAgo(int seconds);

  /// No description provided for @vol24hShort.
  ///
  /// In zh, this message translates to:
  /// **'24h量'**
  String get vol24hShort;

  /// No description provided for @vol1hShort.
  ///
  /// In zh, this message translates to:
  /// **'1h量'**
  String get vol1hShort;

  /// No description provided for @liqMcShort.
  ///
  /// In zh, this message translates to:
  /// **'流/市值'**
  String get liqMcShort;

  /// No description provided for @statusConfirmed.
  ///
  /// In zh, this message translates to:
  /// **'已确认'**
  String get statusConfirmed;

  /// No description provided for @statusFailed.
  ///
  /// In zh, this message translates to:
  /// **'失败'**
  String get statusFailed;

  /// No description provided for @statusSubmitting.
  ///
  /// In zh, this message translates to:
  /// **'提交中'**
  String get statusSubmitting;

  /// No description provided for @statusPending.
  ///
  /// In zh, this message translates to:
  /// **'等待中'**
  String get statusPending;

  /// No description provided for @topHolders.
  ///
  /// In zh, this message translates to:
  /// **'持仓排名'**
  String get topHolders;

  /// No description provided for @addressLabel.
  ///
  /// In zh, this message translates to:
  /// **'地址'**
  String get addressLabel;

  /// No description provided for @holdingPct.
  ///
  /// In zh, this message translates to:
  /// **'占比'**
  String get holdingPct;

  /// No description provided for @fundFlow24h.
  ///
  /// In zh, this message translates to:
  /// **'24h 资金流向'**
  String get fundFlow24h;

  /// No description provided for @netInflow.
  ///
  /// In zh, this message translates to:
  /// **'净流入'**
  String get netInflow;

  /// No description provided for @netOutflow.
  ///
  /// In zh, this message translates to:
  /// **'净流出'**
  String get netOutflow;

  /// No description provided for @sellPressure.
  ///
  /// In zh, this message translates to:
  /// **'卖出'**
  String get sellPressure;

  /// No description provided for @totalBuy.
  ///
  /// In zh, this message translates to:
  /// **'总买入'**
  String get totalBuy;

  /// No description provided for @totalSell.
  ///
  /// In zh, this message translates to:
  /// **'总卖出'**
  String get totalSell;

  /// No description provided for @largeOrders.
  ///
  /// In zh, this message translates to:
  /// **'大额交易 (>\$10K)'**
  String get largeOrders;

  /// No description provided for @largeBuy.
  ///
  /// In zh, this message translates to:
  /// **'大额买入'**
  String get largeBuy;

  /// No description provided for @largeSell.
  ///
  /// In zh, this message translates to:
  /// **'大额卖出'**
  String get largeSell;

  /// No description provided for @tradeHistory.
  ///
  /// In zh, this message translates to:
  /// **'交易分布'**
  String get tradeHistory;

  /// No description provided for @buySimple.
  ///
  /// In zh, this message translates to:
  /// **'买入'**
  String get buySimple;

  /// No description provided for @sellSimple.
  ///
  /// In zh, this message translates to:
  /// **'卖出'**
  String get sellSimple;
}

class _SDelegate extends LocalizationsDelegate<S> {
  const _SDelegate();

  @override
  Future<S> load(Locale locale) {
    return SynchronousFuture<S>(lookupS(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'ja', 'ko', 'zh'].contains(locale.languageCode);

  @override
  bool shouldReload(_SDelegate old) => false;
}

S lookupS(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return SEn();
    case 'ja':
      return SJa();
    case 'ko':
      return SKo();
    case 'zh':
      return SZh();
  }

  throw FlutterError(
    'S.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
