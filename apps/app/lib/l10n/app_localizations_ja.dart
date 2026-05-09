// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Japanese (`ja`).
class SJa extends S {
  SJa([String locale = 'ja']) : super(locale);

  @override
  String get tabMarket => '市場';

  @override
  String get tabAgent => 'Agent';

  @override
  String get tabHistory => 'シグナル';

  @override
  String get tabProfile => 'マイ';

  @override
  String get profileTitle => 'マイページ';

  @override
  String get notificationSettings => '通知設定';

  @override
  String get newCoinPush => '新規コインプッシュ';

  @override
  String get newCoinPushDesc => '毎日08:05にTop10をプッシュ';

  @override
  String get hotCoinAlert => 'ホットコインアラート';

  @override
  String get hotCoinAlertDesc => '人気急上昇時にプッシュ';

  @override
  String get agentNotification => 'Agent実行通知';

  @override
  String get agentNotificationDesc => 'ストラテジーが取引を実行した時にプッシュ';

  @override
  String get appearanceSettings => '外観設定';

  @override
  String get darkMode => 'ダークモード';

  @override
  String get darkModeOn => 'オン';

  @override
  String get darkModeOff => 'オフ';

  @override
  String get languageSettings => '言語設定';

  @override
  String get language => '言語';

  @override
  String get followSystem => 'システムに従う';

  @override
  String get about => 'アプリについて';

  @override
  String get version => 'バージョン';

  @override
  String get dataSource => 'データソース';

  @override
  String get riskWarning => 'リスク警告';

  @override
  String get comingSoon => '近日公開';

  @override
  String get riskContent =>
      '本アプリのシグナルは参考情報であり、投資助言ではありません。\n\nMemeトークンは非常に投機的で、全額損失のリスクがあります。\n\nご自身のリスク許容度に基づいて慎重にご判断ください。';

  @override
  String get iKnow => '了解しました';

  @override
  String get deleteWallet => 'ウォレットを削除';

  @override
  String deleteWalletConfirm(String name) {
    return '\"$name\"を削除しますか？秘密鍵はデバイスから削除されます。';
  }

  @override
  String get cancel => 'キャンセル';

  @override
  String get delete => '削除';

  @override
  String get myWallets => 'マイウォレット';

  @override
  String get notImported => '未インポート';

  @override
  String countUnit(int count) {
    return '$count個';
  }

  @override
  String get walletImportHint => 'ウォレットをインポートすると、Agentが自動取引ストラテジーを実行できます';

  @override
  String get defaultLabel => 'デフォルト';

  @override
  String get addressCopied => 'アドレスをコピーしました';

  @override
  String get importWallet => 'ウォレットをインポート';

  @override
  String get addWallet => 'ウォレットを追加';

  @override
  String get marketTitle => '市場';

  @override
  String get hotCoins => 'ホット';

  @override
  String get smartMoney => 'スマートマネー';

  @override
  String get newCoins => '新規';

  @override
  String get all => 'すべて';

  @override
  String get strongPush => 'おすすめ';

  @override
  String get token => 'トークン';

  @override
  String get priceChange24hLabel => '価格 / 24h変動';

  @override
  String get priceHeatLabel => '価格 / 人気度';

  @override
  String get scoreLabel => 'スコア';

  @override
  String get noHotCoins => 'ホットトークンなし';

  @override
  String get noSmartMoneySignals => 'スマートマネーシグナルなし';

  @override
  String get noSignals => 'ライブシグナルなし';

  @override
  String get pullToRefresh => 'プルダウンで更新';

  @override
  String get loadFailed => '読み込み失敗';

  @override
  String get retry => 'リトライ';

  @override
  String get tapToRetry => 'タップしてリトライ';

  @override
  String strongPushWithCount(int count) {
    return '$count件おすすめ';
  }

  @override
  String tokenCountRealtime(int strong, int total) {
    return '$strong件おすすめ · $totalトークン · リアルタイム';
  }

  @override
  String strongSignalInfo(int strong, int total) {
    return '$strong件強シグナル · $totalトークン · 5分更新';
  }

  @override
  String get scanInfo => 'リアルタイムスキャン · pump.fun · 30秒更新';

  @override
  String strongNormal2h(int strong, int normal) {
    return '$strongおすすめ  $normal普通  ·  2時間更新';
  }

  @override
  String get realtimeSignals => 'リアルタイムシグナル';

  @override
  String get watch => 'ウォッチ';

  @override
  String get whenTokenAppears => '条件を満たすトークンが自動的に表示されます';

  @override
  String buyersCount(int count) {
    return '$count人';
  }

  @override
  String get agentStrategy => 'Agentストラテジー';

  @override
  String get chatTab => 'チャット';

  @override
  String get myStrategyTab => 'マイストラテジー';

  @override
  String get dataSourceTab => 'データソース';

  @override
  String get agentIntro =>
      'こんにちは！AI取引アシスタントです。\n\nお手伝いできること：\n\n📊 自動取引ストラテジー作成\n• 「BTCが6万ドルに下がったら自動購入」\n• 「スコア70以上のホットコインを\$50で購入」\n• 「スマートマネーの取引をフォロー」\n\n🔍 バックテスト検証\n• 過去7日間の実データでテスト\n\n📋 テンプレートで簡単作成\n• MEMEスナイパー / ホット追随 / スマートマネー\n\n💡 「初心者向けのストラテジーを推薦して」と言ってみてください';

  @override
  String strategyCreated(String name) {
    return 'ストラテジー「$name」を作成して有効化しました！\n30秒ごとに条件をチェックします。\n「マイストラテジー」タブで管理できます。';
  }

  @override
  String get cancelled => 'キャンセルしました。他のストラテジーのアイデアを続けてお伝えください。';

  @override
  String get usageNotice => '利用規約';

  @override
  String get agentDisclaimer1 => '本ツールはデータ分析と自動化実行のみを提供し、投資助言ではありません。';

  @override
  String get riskSelfBorne => 'すべての取引ストラテジーはご自身で設定し、リスクはご自身が負います';

  @override
  String get noPlatformLicense => '当プラットフォームは金融ライセンスを保持していません';

  @override
  String get autoTradeRisk => '自動取引には損失リスクがあります。パラメータを慎重に設定してください';

  @override
  String get platformNotResponsible => 'プラットフォームは実行のみ担当し、利益や損失には責任を負いません';

  @override
  String get iReadAndAgree => '読みました。同意します';

  @override
  String get confirmEnableStrategy => 'ストラテジー有効化の確認';

  @override
  String get aboutToEnable => '自動取引ストラテジーを有効化します。確認してください：';

  @override
  String get paramSetByYou => 'ストラテジーパラメータはご自身が設定';

  @override
  String get understandRisk => '自動取引のリスクを理解しています';

  @override
  String get platformExecuteOnly => 'プラットフォームは実行のみ、投資助言なし';

  @override
  String get confirmEnable => '有効化を確認';

  @override
  String cooldownTime(int minutes) {
    return 'クールダウン: $minutes分';
  }

  @override
  String get unnamedStrategy => '名前なしストラテジー';

  @override
  String get securityStatement => 'セキュリティ声明';

  @override
  String get walletDisclaimer1 =>
      'ニーモニック/秘密鍵はデバイスのセキュアエリア（iOS Keychain / Android Keystore）にのみ保存されます';

  @override
  String get walletDisclaimer2 => '当サーバーは秘密鍵を受信、保存、送信しません';

  @override
  String get walletDisclaimer3 => 'すべてのトランザクションはデバイス上でローカル署名後にブロードキャストされます';

  @override
  String get walletDisclaimer4 => 'これは非カストディアルツールです。資金を保持しません';

  @override
  String get walletDisclaimer5 => 'ニーモニックを安全にバックアップしてください。紛失すると復元できません';

  @override
  String get understood => '了解しました、続ける';

  @override
  String get clipboardEmpty => 'クリップボードが空です';

  @override
  String get enterMnemonic => 'ニーモニックを入力してください';

  @override
  String get enterPrivateKey => '秘密鍵を入力してください';

  @override
  String get selectAtLeastOneChain => '少なくとも1つのチェーンを選択してください';

  @override
  String importFailed(String error) {
    return 'インポート失敗: $error';
  }

  @override
  String get selectChain => 'チェーンを選択';

  @override
  String get walletNameLabel => 'ウォレット名（任意）';

  @override
  String get walletNameHint => '例：メインウォレット';

  @override
  String get pasteFromClipboard => 'クリップボードから貼り付け';

  @override
  String get mnemonic => 'ニーモニック';

  @override
  String get privateKey => '秘密鍵';

  @override
  String get mnemonicMultiChain => '1つのニーモニックでマルチチェーンアドレスを生成';

  @override
  String get mnemonicHint => '12または24語をスペースで区切って入力';

  @override
  String get privateKeyHint => '秘密鍵を入力（16進数またはBase58）';

  @override
  String get securityNote =>
      'ニーモニックと秘密鍵はデバイスの暗号化セキュアエリアにのみ保存され、サーバーにアップロードされることはありません。バックアップを安全に保管してください。';

  @override
  String get running => '実行中';

  @override
  String get paused => '一時停止';

  @override
  String triggerInfo(int count, int minutes) {
    return '$count回トリガー · $minutes分クールダウン';
  }

  @override
  String get noTradeRecords => '取引記録なし';

  @override
  String get realizedProfit => '実現損益';

  @override
  String get buy => '買い';

  @override
  String get sell => '売り';

  @override
  String get successRate => '勝率';

  @override
  String allWithCount(int count) {
    return 'すべて $count';
  }

  @override
  String buyWithCount(int count) {
    return '買い $count';
  }

  @override
  String sellWithCount(int count) {
    return '売り $count';
  }

  @override
  String get noBuyRecords => '買い記録なし';

  @override
  String get noSellRecords => '売り記録なし';

  @override
  String get tradeRecordHint => 'ストラテジーが取引を実行すると、ここに記録が表示されます';

  @override
  String get txHashCopied => '取引ハッシュをコピーしました';

  @override
  String get detail => '詳細';

  @override
  String get totalInflow => '流入';

  @override
  String get totalOutflow => '流出';

  @override
  String get netFlowLabel => '純フロー';

  @override
  String get wallet => 'ウォレット';

  @override
  String buyerSellerCount(int buyers, int sellers) {
    return '$buyers買/$sellers売';
  }

  @override
  String get buyOverview => '買い概要';

  @override
  String get sellOverview => '売り概要';

  @override
  String walletTxInfo(int walletCount, int txCount) {
    return '$walletCountウォレット · $txCount件取引';
  }

  @override
  String avgPerTx(String amount) {
    return '平均 $amount/件';
  }

  @override
  String txCount(int count) {
    return '$count件';
  }

  @override
  String get learnTier => 'ウォレット階層について';

  @override
  String get tierExplanation => 'スマートマネー階層ガイド';

  @override
  String get elite => 'エリート';

  @override
  String get verified => '認証済み';

  @override
  String get watching => 'ウォッチ';

  @override
  String get eliteDesc => '勝率≥65%かつ≥10取引、シグナル重み×5';

  @override
  String get verifiedDesc => '勝率≥50%かつ≥5取引、シグナル重み×3';

  @override
  String get watchingDesc => '勝率≥40%かつ≥3取引、シグナル重み×1';

  @override
  String get tierSystemDesc =>
      'システムがオンチェーンスマートマネーウォレットの取引パフォーマンスを追跡し、自動評価します。エリートウォレットの買いシグナルが最も信頼性が高いです。';

  @override
  String copied(String address) {
    return '$addressをコピーしました';
  }

  @override
  String mcLiquidity(String mc, String liquidity) {
    return 'MC $mc · 流動性 $liquidity';
  }

  @override
  String walletsCount(int count) {
    return '$countウォレット';
  }

  @override
  String eliteCountLabel(int count) {
    return '($countエリート)';
  }

  @override
  String buyVolume(String amount) {
    return '買 $amount';
  }

  @override
  String sellVolume(String amount) {
    return '売 $amount';
  }

  @override
  String netAmount(String amount) {
    return '純$amount';
  }

  @override
  String get honeypotDetection => 'ハニーポット検出';

  @override
  String get dangerous => '危険';

  @override
  String get safe => '安全';

  @override
  String get contractOpenSource => 'オープンソース';

  @override
  String get yes => 'はい';

  @override
  String get no => 'いいえ';

  @override
  String get buyTax => '買い税';

  @override
  String get sellTax => '売り税';

  @override
  String get top10Concentration => 'Top10集中度';

  @override
  String get justNow => 'たった今';

  @override
  String minutesAgo(int minutes) {
    return '$minutes分前';
  }

  @override
  String hoursAgo(int hours) {
    return '$hours時間前';
  }

  @override
  String daysAgo(int days) {
    return '$days日前';
  }

  @override
  String get holders => '保有者';

  @override
  String get holderCount => '保有者数';

  @override
  String get top10Ratio => 'Top10割合';

  @override
  String get top1Ratio => 'Top1割合';

  @override
  String get noKlineData => 'K線データなし';

  @override
  String get tokenTooNew => 'トークンが新しすぎる可能性があります';

  @override
  String get chartLoadFailed => 'チャートの読み込みに失敗しました。ネットワークを確認してください';

  @override
  String get chartInitFailed => 'チャートの初期化に失敗しました';

  @override
  String serverError(int code) {
    return 'サーバーエラー ($code)';
  }

  @override
  String get networkFailed => 'ネットワーク接続失敗。バックエンドサービスを確認してください';

  @override
  String get dataFormatError => 'レスポンスフォーマットが無効です';

  @override
  String networkError(String error) {
    return 'ネットワークエラー: $error';
  }

  @override
  String get unnamed => '名前なし';

  @override
  String get mnemonicMustBe12or24 => 'ニーモニックは12語または24語である必要があります';

  @override
  String chainWallet(String chain) {
    return '$chainウォレット';
  }

  @override
  String get allChainsExist => 'すべてのチェーンのウォレットが既に存在します';

  @override
  String get invalidPrivateKey => '無効な秘密鍵';

  @override
  String get walletAlreadyExists => 'ウォレットは既に存在します';

  @override
  String get disclaimerTitle => '利用規約';

  @override
  String get disclaimerScrollHint => 'よく読んで、一番下までスクロールしてください';

  @override
  String get disclaimerCheckbox =>
      '私は18歳以上であり、上記のすべての条項を読み理解し、本アプリの利用規約に同意します。\nI am 18+, have read and understood all terms above.';

  @override
  String get disclaimerAccept => '同意して続ける';

  @override
  String get disclaimerScrollFirst => 'まず一番下までスクロールしてください';

  @override
  String get disclaimerReachedBottom => '— 一番下に到達しました。チェックして同意してください —';

  @override
  String get disclaimerGeoTitle => '地域制限';

  @override
  String get disclaimerGeoBody =>
      '本サービスは以下の地域のユーザーには提供されません：\n• 中国大陸（中国本土のIPは自動的にブロックされます）\n• 香港特別行政区\n• マカオ特別行政区\n• 台湾\n\n上記の地域にお住まいの場合は、直ちに使用を中止し、アプリをアンインストールしてください。';

  @override
  String get disclaimerAdviceTitle => '投資助言ではありません';

  @override
  String get disclaimerAdviceBody =>
      '本アプリが提供するすべてのコンテンツ（トークンスコア、シグナルアラート、スマートマネー追跡、Agentストラテジーを含む）は情報提供のみを目的としており、投資助言、財務助言、取引推奨ではありません。';

  @override
  String get disclaimerAutoTradeTitle => '自動取引リスク';

  @override
  String get disclaimerAutoTradeBody =>
      '• Agent機能は実際のブロックチェーン取引を実行し、資産損失の可能性があります。\n• 暗号資産市場は非常に変動が激しく、過去の実績は将来の結果を保証しません。\n• すべての取引結果に対する全責任はあなたが負います。';

  @override
  String get disclaimerWalletTitle => 'ウォレットセキュリティ';

  @override
  String get disclaimerWalletBody =>
      '• これは非カストディアルウォレットです：秘密鍵/ニーモニックはデバイス上にのみ保存され、サーバーは受信しません。\n• デバイスの紛失やニーモニックの忘却は資産の回復不能を意味します。\n• ニーモニックを安全なオフラインの場所にバックアップしてください。';

  @override
  String get disclaimerLegalTitle => '法的免責事項';

  @override
  String get disclaimerLegalBody =>
      '本アプリはいかなる金融規制機関の規制も受けず、投資顧問や金融サービスライセンスも保持していません。本アプリを使用することで、関連するすべてのリスクを理解し受け入れるものとします。';

  @override
  String get disclaimerVersionTitle => 'バージョン';

  @override
  String get disclaimerVersionBody => '最終更新: 2026年3月。';

  @override
  String get hotCoinList => 'ホットコイン';

  @override
  String get scanPumpFun => 'リアルタイムスキャン pump.fun · 30秒更新';

  @override
  String get tradeDynamics => '取引動態';

  @override
  String get securityCheck => 'セキュリティ検査';

  @override
  String get tokenInfo => 'トークン情報';

  @override
  String buyPressure(String pct) {
    return '$pct% 買い圧力';
  }

  @override
  String buyLabel(String count) {
    return '買 $count';
  }

  @override
  String sellLabel(String count) {
    return '売 $count';
  }

  @override
  String get noSocialInfo => 'ソーシャル情報なし';

  @override
  String get contractAddress => 'コントラクトアドレス';

  @override
  String get blockExplorer => 'ブロックエクスプローラー';

  @override
  String get textCopied => 'コピーしました';

  @override
  String distanceToGrad(String pct) {
    return '卒業まで残り$pct%';
  }

  @override
  String get graduated => '卒業済み';

  @override
  String get notGraduated => '未卒業';

  @override
  String daysUnit(String days) {
    return '$days日';
  }

  @override
  String get riskDetected => 'リスクあり';

  @override
  String get securityUnavailable => 'セキュリティデータ利用不可';

  @override
  String get momentumM => 'モメンタム M';

  @override
  String get qualityQ => '品質 Q';

  @override
  String get potentialP => 'ポテンシャル P';

  @override
  String get buySellRatio => '売買比率';

  @override
  String get smartMoneyLabel => 'スマートマネー';

  @override
  String get inflowAccel => '流入加速';

  @override
  String get creatorLabel => '作成者';

  @override
  String get buyerDiversity => '買い手分散度';

  @override
  String get socialLabel => 'ソーシャル';

  @override
  String get progressSpeed => '進捗速度';

  @override
  String get whaleBonus => '大口ボーナス';

  @override
  String get aiStrongPush => 'AIおすすめ';

  @override
  String get aiWatch => 'AI注目';

  @override
  String get aiObserve => 'AI様子見';

  @override
  String get stopLoss => 'ストップロス';

  @override
  String get takeProfit => 'テイクプロフィット';

  @override
  String get slippageLabel => 'スリッページ';

  @override
  String get priorityFee => '優先手数料';

  @override
  String get advancedTradeSettings => '高度な取引設定';

  @override
  String get tradingWallet => '取引ウォレット';

  @override
  String get describeStrategy => 'ストラテジーのアイデアを説明...';

  @override
  String get pumpFunSource => 'リアルタイムWebSocket + REST、BC進捗、取引フロー、卒業イベント';

  @override
  String get pumpFunStatus => 'スキャン中';

  @override
  String get multiChainHot => 'マルチチェーンホット';

  @override
  String get multiChainHotDesc => 'SOL/BSC/Base/ETH 4チェーンホットコインスキャン、2時間更新';

  @override
  String get connected => '接続済み';

  @override
  String get kolSentiment => 'KOLセンチメント';

  @override
  String get kolSentimentDesc => '212人のTwitter KOL監視、共鳴シグナル検出、感情分析';

  @override
  String get smartMoneySource => 'スマートマネー';

  @override
  String get smartMoneySourceDesc =>
      '多次元階層(Elite/Verified/Watching)、60日減衰、Bot検出';

  @override
  String get okxDexDesc => '30チェーン、リアルタイム見積+実行エンジン、自動取引対応';

  @override
  String get coinGeckoDesc => 'ATH/ATL、総供給量、コミュニティデータなどの補足情報';

  @override
  String get detailTabQuotes => '相場';

  @override
  String get detailTabDetails => '詳細';

  @override
  String get detailTabSecurity => 'セキュリティ';

  @override
  String get marketCap => '時価総額';

  @override
  String get liquidityPool => '流動性プール';

  @override
  String get holderAddressCount => '保有者数';

  @override
  String get tradingAddresses24h => '24h取引アドレス';

  @override
  String get moreLabel => 'もっと';

  @override
  String get priceLabel => '価格';

  @override
  String get holderAddressTab => '保有者';

  @override
  String get liquidityPoolTab => '流動性';

  @override
  String get devTokensTab => '開発者トークン';

  @override
  String get buyTxCount => '買い件数';

  @override
  String get sellTxCount => '売り件数';

  @override
  String get turnover => '出来高';

  @override
  String get netBuy => '純買い';

  @override
  String get holdersSmall => '保有者';

  @override
  String get liquiditySmall => '流動性';

  @override
  String get buySellColumn => '買/売';

  @override
  String get allTrades => '全取引';

  @override
  String get qtyTimeColumn => '数量 / 時間';

  @override
  String get valuePriceColumn => '価額 / 価格';

  @override
  String get addressColumn => 'アドレス';

  @override
  String get liqMcRatio => '流動性/時価';

  @override
  String get vol24h => '24h出来高';

  @override
  String get vol1h => '1h出来高';

  @override
  String get noDevTokenData => '開発者トークンデータなし';

  @override
  String get priceChangeLabel => '変動率';

  @override
  String get volumeLabel => '出来高';

  @override
  String get totalTurnover => '合計出来高';

  @override
  String get tradeCount => '取引件数';

  @override
  String get keyData => '主要データ';

  @override
  String get circulatingMC => '流通時価総額';

  @override
  String get holderCountTop10 => '保有者数（Top10占有率）';

  @override
  String get totalLiquidity => '総流動性';

  @override
  String get circulatingSupply => '流通供給量';

  @override
  String get maxSupplyLabel => '最大供給量';

  @override
  String get athLabel => '史上最高値';

  @override
  String get atlLabel => '史上最安値';

  @override
  String get basicInfo => '基本情報';

  @override
  String get mainChain => 'メインチェーン';

  @override
  String get tokenFullName => 'トークン名';

  @override
  String get createdTime => '作成日時';

  @override
  String aboutToken(String symbol) {
    return '$symbolについて';
  }

  @override
  String get noDescription => '説明なし';

  @override
  String get socialMedia => 'ソーシャルメディア';

  @override
  String get searchOnX => 'Xで検索';

  @override
  String get searchName => '名前で検索';

  @override
  String get searchAddress => 'アドレスで検索';

  @override
  String get securityDisclaimerText =>
      'このツールはトークンのセキュリティ評価を支援するものであり、投資助言として使用すべきではありません。取引前にリスクを自己評価してください。';

  @override
  String get riskItems => 'リスク';

  @override
  String get warningItems => '警告';

  @override
  String get tf5m => '5分';

  @override
  String get tf15m => '15分';

  @override
  String get tf1hLabel => '1時間';

  @override
  String get tf4h => '4時間';

  @override
  String get tf1d => '1日';

  @override
  String get tf5min => '5分';

  @override
  String get tf1hour => '1時間';

  @override
  String get tf4hour => '4時間';

  @override
  String get tf24hour => '24時間';

  @override
  String get recentTrades => '最近の取引';

  @override
  String get noTradePairData => 'ペアデータなし';

  @override
  String get noTradeData => '取引データなし';

  @override
  String secondsAgo(int seconds) {
    return '$seconds秒前';
  }

  @override
  String get vol24hShort => '24h量';

  @override
  String get vol1hShort => '1h量';

  @override
  String get liqMcShort => '流/時価';

  @override
  String get statusConfirmed => '確認済み';

  @override
  String get statusFailed => '失敗';

  @override
  String get statusSubmitting => '送信中';

  @override
  String get statusPending => '待機中';

  @override
  String get topHolders => '保有ランキング';

  @override
  String get addressLabel => 'アドレス';

  @override
  String get holdingPct => '保有率';

  @override
  String get fundFlow24h => '24h 資金フロー';

  @override
  String get netInflow => '純流入';

  @override
  String get netOutflow => '純流出';

  @override
  String get sellPressure => '売却';

  @override
  String get totalBuy => '総買い';

  @override
  String get totalSell => '総売り';

  @override
  String get largeOrders => '大口取引 (>\$10K)';

  @override
  String get largeBuy => '大口買い';

  @override
  String get largeSell => '大口売り';

  @override
  String get tradeHistory => '取引分布';

  @override
  String get buySimple => '買い';

  @override
  String get sellSimple => '売り';
}
