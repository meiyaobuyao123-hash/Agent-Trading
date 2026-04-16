// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Korean (`ko`).
class SKo extends S {
  SKo([String locale = 'ko']) : super(locale);

  @override
  String get tabMarket => '시세';

  @override
  String get tabAgent => 'Agent';

  @override
  String get tabHistory => '시그널';

  @override
  String get tabProfile => '마이';

  @override
  String get profileTitle => '마이페이지';

  @override
  String get notificationSettings => '알림 설정';

  @override
  String get newCoinPush => '신규 코인 알림';

  @override
  String get newCoinPushDesc => '매일 08:05 Top10 푸시';

  @override
  String get hotCoinAlert => '핫코인 알림';

  @override
  String get hotCoinAlertDesc => '인기 급상승 시 푸시';

  @override
  String get agentNotification => 'Agent 실행 알림';

  @override
  String get agentNotificationDesc => '전략이 거래를 실행할 때 푸시';

  @override
  String get appearanceSettings => '외관 설정';

  @override
  String get darkMode => '다크 모드';

  @override
  String get darkModeOn => '켜기';

  @override
  String get darkModeOff => '끄기';

  @override
  String get languageSettings => '언어 설정';

  @override
  String get language => '언어';

  @override
  String get followSystem => '시스템 기본값';

  @override
  String get about => '정보';

  @override
  String get version => '버전';

  @override
  String get dataSource => '데이터 소스';

  @override
  String get riskWarning => '위험 경고';

  @override
  String get comingSoon => '곧 출시 예정';

  @override
  String get riskContent =>
      '본 앱의 시그널은 참고용이며 투자 조언이 아닙니다.\n\nMeme 토큰은 매우 투기적이며 전액 손실 위험이 있습니다.\n\n본인의 위험 감수 능력에 따라 신중하게 결정하세요.';

  @override
  String get iKnow => '알겠습니다';

  @override
  String get deleteWallet => '지갑 삭제';

  @override
  String deleteWalletConfirm(String name) {
    return '\"$name\"을(를) 삭제하시겠습니까? 키가 기기에서 제거됩니다.';
  }

  @override
  String get cancel => '취소';

  @override
  String get delete => '삭제';

  @override
  String get myWallets => '내 지갑';

  @override
  String get notImported => '미가져옴';

  @override
  String countUnit(int count) {
    return '$count개';
  }

  @override
  String get walletImportHint => '지갑을 가져오면 Agent가 자동으로 거래 전략을 실행할 수 있습니다';

  @override
  String get defaultLabel => '기본';

  @override
  String get addressCopied => '주소가 복사되었습니다';

  @override
  String get importWallet => '지갑 가져오기';

  @override
  String get addWallet => '지갑 추가';

  @override
  String get marketTitle => '시세';

  @override
  String get hotCoins => '핫';

  @override
  String get smartMoney => '스마트머니';

  @override
  String get newCoins => '신규';

  @override
  String get all => '전체';

  @override
  String get strongPush => '추천';

  @override
  String get token => '토큰';

  @override
  String get priceChange24hLabel => '가격 / 24h 변동';

  @override
  String get priceHeatLabel => '가격 / 인기도';

  @override
  String get scoreLabel => '점수';

  @override
  String get noHotCoins => '핫 토큰 없음';

  @override
  String get noSmartMoneySignals => '스마트머니 시그널 없음';

  @override
  String get noSignals => '실시간 시그널 없음';

  @override
  String get pullToRefresh => '당겨서 새로고침';

  @override
  String get loadFailed => '로딩 실패';

  @override
  String get retry => '다시 시도';

  @override
  String get tapToRetry => '탭하여 다시 시도';

  @override
  String strongPushWithCount(int count) {
    return '$count개 추천';
  }

  @override
  String tokenCountRealtime(int strong, int total) {
    return '$strong개 추천 · $total개 토큰 · 실시간';
  }

  @override
  String strongSignalInfo(int strong, int total) {
    return '$strong개 강력 · $total개 토큰 · 5분 업데이트';
  }

  @override
  String get scanInfo => '실시간 스캔 · pump.fun · 30초 새로고침';

  @override
  String strongNormal2h(int strong, int normal) {
    return '$strong개 추천  $normal개 보통  ·  2시간 업데이트';
  }

  @override
  String get realtimeSignals => '실시간 시그널';

  @override
  String get watch => '관심';

  @override
  String get whenTokenAppears => '조건에 맞는 토큰이 자동으로 나타납니다';

  @override
  String buyersCount(int count) {
    return '$count명';
  }

  @override
  String get agentStrategy => 'Agent 전략';

  @override
  String get chatTab => '채팅';

  @override
  String get myStrategyTab => '내 전략';

  @override
  String get dataSourceTab => '데이터 소스';

  @override
  String get agentIntro =>
      '안녕하세요! AI 트레이딩 어시스턴트입니다.\n\n도와드릴 수 있는 것:\n\n📊 자동 거래 전략 생성\n• \"BTC가 6만 달러로 떨어지면 자동 매수\"\n• \"점수 70 이상 핫코인 \$50 매수\"\n• \"스마트머니 매수 따라하기\"\n\n🔍 백테스트 검증\n• 과거 7일 실제 데이터로 테스트\n\n📋 템플릿으로 간편 생성\n• MEME스나이퍼 / 핫코인추격 / 스마트머니\n\n💡 \"초보자용 전략 추천해줘\"라고 말해보세요';

  @override
  String strategyCreated(String name) {
    return '전략 \"$name\" 생성 및 활성화!\n30초마다 조건을 확인합니다.\n\"내 전략\" 탭에서 관리하세요.';
  }

  @override
  String get cancelled => '취소되었습니다. 다른 전략 아이디어를 계속 설명하세요.';

  @override
  String get usageNotice => '이용약관';

  @override
  String get agentDisclaimer1 => '본 도구는 데이터 분석 및 자동화 실행만 제공하며 투자 조언이 아닙니다.';

  @override
  String get riskSelfBorne => '모든 거래 전략은 본인이 설정하며 위험은 본인이 부담합니다';

  @override
  String get noPlatformLicense => '플랫폼은 금융 라이선스를 보유하지 않습니다';

  @override
  String get autoTradeRisk => '자동 거래에는 손실 위험이 있으며 매개변수를 신중하게 설정하세요';

  @override
  String get platformNotResponsible => '플랫폼은 실행만 담당하며 수익이나 손실에 대해 책임지지 않습니다';

  @override
  String get iReadAndAgree => '읽었으며 동의합니다';

  @override
  String get confirmEnableStrategy => '전략 활성화 확인';

  @override
  String get aboutToEnable => '자동 거래 전략을 활성화합니다. 확인해 주세요:';

  @override
  String get paramSetByYou => '전략 매개변수는 본인이 설정';

  @override
  String get understandRisk => '자동 거래의 위험을 이해합니다';

  @override
  String get platformExecuteOnly => '플랫폼은 실행만 담당, 투자 조언 없음';

  @override
  String get confirmEnable => '활성화 확인';

  @override
  String cooldownTime(int minutes) {
    return '쿨다운: $minutes분';
  }

  @override
  String get unnamedStrategy => '이름 없는 전략';

  @override
  String get securityStatement => '보안 성명';

  @override
  String get walletDisclaimer1 =>
      '니모닉/개인키는 기기의 보안 영역(iOS Keychain / Android Keystore)에만 저장됩니다';

  @override
  String get walletDisclaimer2 => '서버는 개인키를 수신, 저장 또는 전송하지 않습니다';

  @override
  String get walletDisclaimer3 => '모든 거래는 기기에서 로컬 서명 후 브로드캐스트됩니다';

  @override
  String get walletDisclaimer4 => '비수탁 도구이며 자금을 보유하지 않습니다';

  @override
  String get walletDisclaimer5 => '니모닉을 안전하게 백업하세요. 분실 시 복구할 수 없습니다';

  @override
  String get understood => '이해했습니다, 계속';

  @override
  String get clipboardEmpty => '클립보드가 비어 있습니다';

  @override
  String get enterMnemonic => '니모닉을 입력하세요';

  @override
  String get enterPrivateKey => '개인키를 입력하세요';

  @override
  String get selectAtLeastOneChain => '최소 하나의 체인을 선택하세요';

  @override
  String importFailed(String error) {
    return '가져오기 실패: $error';
  }

  @override
  String get selectChain => '체인 선택';

  @override
  String get walletNameLabel => '지갑 이름 (선택)';

  @override
  String get walletNameHint => '예: 메인 지갑';

  @override
  String get pasteFromClipboard => '클립보드에서 붙여넣기';

  @override
  String get mnemonic => '니모닉';

  @override
  String get privateKey => '개인키';

  @override
  String get mnemonicMultiChain => '하나의 니모닉으로 멀티체인 주소 생성';

  @override
  String get mnemonicHint => '12개 또는 24개 단어를 공백으로 구분하여 입력';

  @override
  String get privateKeyHint => '개인키 입력 (16진수 또는 Base58)';

  @override
  String get securityNote =>
      '니모닉과 개인키는 기기의 암호화된 보안 영역에만 저장되며 서버에 업로드되지 않습니다. 백업을 안전하게 보관하세요.';

  @override
  String get running => '실행 중';

  @override
  String get paused => '일시정지';

  @override
  String triggerInfo(int count, int minutes) {
    return '$count회 트리거 · $minutes분 쿨다운';
  }

  @override
  String get noTradeRecords => '거래 기록 없음';

  @override
  String get realizedProfit => '실현 손익';

  @override
  String get buy => '매수';

  @override
  String get sell => '매도';

  @override
  String get successRate => '승률';

  @override
  String allWithCount(int count) {
    return '전체 $count';
  }

  @override
  String buyWithCount(int count) {
    return '매수 $count';
  }

  @override
  String sellWithCount(int count) {
    return '매도 $count';
  }

  @override
  String get noBuyRecords => '매수 기록 없음';

  @override
  String get noSellRecords => '매도 기록 없음';

  @override
  String get tradeRecordHint => '전략이 거래를 실행하면 여기에 기록이 표시됩니다';

  @override
  String get txHashCopied => '거래 해시가 복사되었습니다';

  @override
  String get detail => '상세';

  @override
  String get totalInflow => '유입';

  @override
  String get totalOutflow => '유출';

  @override
  String get netFlowLabel => '순 흐름';

  @override
  String get wallet => '지갑';

  @override
  String buyerSellerCount(int buyers, int sellers) {
    return '$buyers매수/$sellers매도';
  }

  @override
  String get buyOverview => '매수 개요';

  @override
  String get sellOverview => '매도 개요';

  @override
  String walletTxInfo(int walletCount, int txCount) {
    return '$walletCount개 지갑 · $txCount건 거래';
  }

  @override
  String avgPerTx(String amount) {
    return '평균 $amount/건';
  }

  @override
  String txCount(int count) {
    return '건';
  }

  @override
  String get learnTier => '지갑 등급 안내';

  @override
  String get tierExplanation => '스마트머니 등급 가이드';

  @override
  String get elite => '엘리트';

  @override
  String get verified => '인증';

  @override
  String get watching => '관심';

  @override
  String get eliteDesc => '승률≥65% 및 ≥10 거래, 시그널 가중치 ×5';

  @override
  String get verifiedDesc => '승률≥50% 및 ≥5 거래, 시그널 가중치 ×3';

  @override
  String get watchingDesc => '승률≥40% 및 ≥3 거래, 시그널 가중치 ×1';

  @override
  String get tierSystemDesc =>
      '시스템이 온체인 스마트머니 지갑의 거래 성과를 추적하고 자동 등급을 매깁니다. 엘리트 지갑의 매수 시그널이 가장 신뢰할 수 있습니다.';

  @override
  String copied(String address) {
    return '$address 복사됨';
  }

  @override
  String mcLiquidity(String mc, String liquidity) {
    return 'MC $mc · 유동성 $liquidity';
  }

  @override
  String walletsCount(int count) {
    return '$count개 지갑';
  }

  @override
  String eliteCountLabel(int count) {
    return '($count엘리트)';
  }

  @override
  String buyVolume(String amount) {
    return '매수 $amount';
  }

  @override
  String sellVolume(String amount) {
    return '매도 $amount';
  }

  @override
  String netAmount(String amount) {
    return '순$amount';
  }

  @override
  String get honeypotDetection => '허니팟 감지';

  @override
  String get dangerous => '위험';

  @override
  String get safe => '안전';

  @override
  String get contractOpenSource => '오픈소스';

  @override
  String get yes => '예';

  @override
  String get no => '아니오';

  @override
  String get buyTax => '매수세';

  @override
  String get sellTax => '매도세';

  @override
  String get top10Concentration => 'Top10 집중도';

  @override
  String get justNow => '방금';

  @override
  String minutesAgo(int minutes) {
    return '$minutes분 전';
  }

  @override
  String hoursAgo(int hours) {
    return '$hours시간 전';
  }

  @override
  String daysAgo(int days) {
    return '$days일 전';
  }

  @override
  String get holders => '보유자';

  @override
  String get holderCount => '보유자 수';

  @override
  String get top10Ratio => 'Top10 비율';

  @override
  String get top1Ratio => 'Top1 비율';

  @override
  String get noKlineData => 'K선 데이터 없음';

  @override
  String get tokenTooNew => '토큰이 너무 새로울 수 있습니다';

  @override
  String get chartLoadFailed => '차트 로딩 실패, 네트워크를 확인하세요';

  @override
  String get chartInitFailed => '차트 초기화 실패';

  @override
  String serverError(int code) {
    return '서버 오류 ($code)';
  }

  @override
  String get networkFailed => '네트워크 연결 실패, 백엔드 서비스를 확인하세요';

  @override
  String get dataFormatError => '잘못된 응답 형식';

  @override
  String networkError(String error) {
    return '네트워크 오류: $error';
  }

  @override
  String get unnamed => '이름 없음';

  @override
  String get mnemonicMustBe12or24 => '니모닉은 12개 또는 24개 단어여야 합니다';

  @override
  String chainWallet(String chain) {
    return '$chain 지갑';
  }

  @override
  String get allChainsExist => '모든 체인의 지갑이 이미 존재합니다';

  @override
  String get invalidPrivateKey => '잘못된 개인키';

  @override
  String get walletAlreadyExists => '지갑이 이미 존재합니다';

  @override
  String get disclaimerTitle => '이용약관';

  @override
  String get disclaimerScrollHint => '주의 깊게 읽고 맨 아래까지 스크롤하세요';

  @override
  String get disclaimerCheckbox =>
      '만 18세 이상이며, 위의 모든 조항을 읽고 이해했으며, 본 앱의 이용 규칙에 동의합니다.\nI am 18+, have read and understood all terms above.';

  @override
  String get disclaimerAccept => '동의하고 계속';

  @override
  String get disclaimerScrollFirst => '먼저 맨 아래까지 스크롤하세요';

  @override
  String get disclaimerReachedBottom => '— 맨 아래에 도달했습니다. 체크하여 동의하세요 —';

  @override
  String get disclaimerGeoTitle => '지역 제한';

  @override
  String get disclaimerGeoBody =>
      '본 서비스는 다음 지역의 사용자에게 제공되지 않습니다:\n• 중국 대륙 (중국 본토 IP는 자동 차단)\n• 홍콩 특별행정구\n• 마카오 특별행정구\n• 대만\n\n위 지역에 거주하는 경우 즉시 사용을 중단하고 앱을 삭제하세요.';

  @override
  String get disclaimerAdviceTitle => '투자 조언이 아닙니다';

  @override
  String get disclaimerAdviceBody =>
      '본 앱이 제공하는 모든 콘텐츠(토큰 점수, 시그널 알림, 스마트머니 추적, Agent 전략 포함)는 정보 제공 목적으로만 사용되며 투자 조언, 재무 조언 또는 거래 추천이 아닙니다.';

  @override
  String get disclaimerAutoTradeTitle => '자동 거래 위험';

  @override
  String get disclaimerAutoTradeBody =>
      '• Agent 기능은 실제 블록체인 거래를 실행하며 자산 손실이 발생할 수 있습니다.\n• 암호화폐 시장은 매우 변동성이 높으며 과거 성과가 미래 결과를 보장하지 않습니다.\n• 모든 거래 결과에 대한 전적인 책임은 사용자에게 있습니다.';

  @override
  String get disclaimerWalletTitle => '지갑 보안';

  @override
  String get disclaimerWalletBody =>
      '• 비수탁 지갑입니다: 개인키/니모닉은 기기에만 저장되며 서버는 수신하지 않습니다.\n• 기기 분실 또는 니모닉 분실은 자산 복구 불가를 의미합니다.\n• 니모닉을 안전한 오프라인 위치에 백업하세요.';

  @override
  String get disclaimerLegalTitle => '법적 면책 조항';

  @override
  String get disclaimerLegalBody =>
      '본 앱은 금융 규제 기관의 규제를 받지 않으며 투자 자문이나 금융 서비스 라이선스를 보유하지 않습니다. 본 앱을 사용함으로써 관련 모든 위험을 인지하고 수용하는 것입니다.';

  @override
  String get disclaimerVersionTitle => '버전';

  @override
  String get disclaimerVersionBody => '최종 업데이트: 2026년 3월.';

  @override
  String get hotCoinList => '핫코인';

  @override
  String get scanPumpFun => '실시간 스캔 pump.fun · 30초 새로고침';

  @override
  String get tradeDynamics => '거래 동태';

  @override
  String get securityCheck => '보안 검사';

  @override
  String get tokenInfo => '토큰 정보';

  @override
  String buyPressure(String pct) {
    return '매수';
  }

  @override
  String buyLabel(String count) {
    return '매수 $count';
  }

  @override
  String sellLabel(String count) {
    return '매도 $count';
  }

  @override
  String get noSocialInfo => '소셜 정보 없음';

  @override
  String get contractAddress => '컨트랙트 주소';

  @override
  String get blockExplorer => '블록 탐색기';

  @override
  String get textCopied => '복사됨';

  @override
  String distanceToGrad(String pct) {
    return '졸업까지 $pct% 남음';
  }

  @override
  String get graduated => '졸업됨';

  @override
  String get notGraduated => '미졸업';

  @override
  String daysUnit(String days) {
    return '$days일';
  }

  @override
  String get riskDetected => '위험 감지';

  @override
  String get securityUnavailable => '보안 데이터 이용 불가';

  @override
  String get momentumM => '모멘텀 M';

  @override
  String get qualityQ => '품질 Q';

  @override
  String get potentialP => '잠재력 P';

  @override
  String get buySellRatio => '매수/매도 비율';

  @override
  String get smartMoneyLabel => '스마트머니';

  @override
  String get inflowAccel => '유입 가속';

  @override
  String get creatorLabel => '생성자';

  @override
  String get buyerDiversity => '매수자 분산도';

  @override
  String get socialLabel => '소셜';

  @override
  String get progressSpeed => '진행 속도';

  @override
  String get whaleBonus => '고래 보너스';

  @override
  String get aiStrongPush => 'AI 추천';

  @override
  String get aiWatch => 'AI 관심';

  @override
  String get aiObserve => 'AI 관망';

  @override
  String get stopLoss => '손절';

  @override
  String get takeProfit => '익절';

  @override
  String get slippageLabel => '슬리피지';

  @override
  String get priorityFee => '우선 수수료';

  @override
  String get advancedTradeSettings => '고급 거래 설정';

  @override
  String get tradingWallet => '거래 지갑';

  @override
  String get describeStrategy => '전략 아이디어를 설명하세요...';

  @override
  String get pumpFunSource => '실시간 WebSocket + REST, BC 진행률, 거래 흐름, 졸업 이벤트';

  @override
  String get pumpFunStatus => '스캔 중';

  @override
  String get multiChainHot => '멀티체인 핫';

  @override
  String get multiChainHotDesc => 'SOL/BSC/Base/ETH 4체인 핫코인 스캔, 2시간 업데이트';

  @override
  String get connected => '연결됨';

  @override
  String get kolSentiment => 'KOL 여론';

  @override
  String get kolSentimentDesc => '212개 Twitter KOL 모니터링, 공진 시그널 감지, 감정 분석';

  @override
  String get smartMoneySource => '스마트머니';

  @override
  String get smartMoneySourceDesc =>
      '다차원 계층(Elite/Verified/Watching), 60일 감쇠, Bot 감지';

  @override
  String get okxDexDesc => '30개 체인, 실시간 시세 + 실행 엔진, 자동 거래 지원';

  @override
  String get coinGeckoDesc => 'ATH/ATL, 총 공급량, 커뮤니티 데이터 등 보충 정보';

  @override
  String get detailTabQuotes => '시세';

  @override
  String get detailTabDetails => '상세';

  @override
  String get detailTabSecurity => '보안검사';

  @override
  String get marketCap => '시가총액';

  @override
  String get liquidityPool => '유동성 풀';

  @override
  String get holderAddressCount => '보유자 수';

  @override
  String get tradingAddresses24h => '24h 거래 주소';

  @override
  String get moreLabel => '더보기';

  @override
  String get priceLabel => '가격';

  @override
  String get holderAddressTab => '보유자';

  @override
  String get liquidityPoolTab => '유동성';

  @override
  String get devTokensTab => '개발자 토큰';

  @override
  String get buyTxCount => '매수 건수';

  @override
  String get sellTxCount => '매도 건수';

  @override
  String get turnover => '거래액';

  @override
  String get netBuy => '순매수';

  @override
  String get holdersSmall => '보유자';

  @override
  String get liquiditySmall => '유동성';

  @override
  String get buySellColumn => '매수/매도';

  @override
  String get allTrades => '전체 거래';

  @override
  String get qtyTimeColumn => '수량 / 시간';

  @override
  String get valuePriceColumn => '가치 / 가격';

  @override
  String get addressColumn => '주소';

  @override
  String get liqMcRatio => '유동성/시총';

  @override
  String get vol24h => '24h 거래액';

  @override
  String get vol1h => '1h 거래액';

  @override
  String get noDevTokenData => '개발자 토큰 데이터 없음';

  @override
  String get priceChangeLabel => '등락률';

  @override
  String get volumeLabel => '거래량';

  @override
  String get totalTurnover => '총 거래액';

  @override
  String get tradeCount => '거래 건수';

  @override
  String get keyData => '주요 데이터';

  @override
  String get circulatingMC => '유통 시가총액';

  @override
  String get holderCountTop10 => '보유자 수(Top10 비율)';

  @override
  String get totalLiquidity => '총 유동성';

  @override
  String get circulatingSupply => '유통 공급량';

  @override
  String get maxSupplyLabel => '최대 공급량';

  @override
  String get athLabel => '역대 최고가';

  @override
  String get atlLabel => '역대 최저가';

  @override
  String get basicInfo => '기본 정보';

  @override
  String get mainChain => '메인체인';

  @override
  String get tokenFullName => '토큰 전체명';

  @override
  String get createdTime => '생성 시간';

  @override
  String aboutToken(String symbol) {
    return '$symbol 소개';
  }

  @override
  String get noDescription => '설명 없음';

  @override
  String get socialMedia => '소셜 미디어';

  @override
  String get searchOnX => 'X에서 검색';

  @override
  String get searchName => '이름 검색';

  @override
  String get searchAddress => '주소 검색';

  @override
  String get securityDisclaimerText =>
      '이 도구는 토큰 보안 평가를 지원하며 투자 조언으로 사용해서는 안 됩니다. 거래 전 리스크를 직접 평가하세요.';

  @override
  String get riskItems => '위험';

  @override
  String get warningItems => '경고';

  @override
  String get tf5m => '5분';

  @override
  String get tf15m => '15분';

  @override
  String get tf1hLabel => '1시간';

  @override
  String get tf4h => '4시간';

  @override
  String get tf1d => '1일';

  @override
  String get tf5min => '5분';

  @override
  String get tf1hour => '1시간';

  @override
  String get tf4hour => '4시간';

  @override
  String get tf24hour => '24시간';

  @override
  String get recentTrades => '최근 거래';

  @override
  String get noTradePairData => '페어 데이터 없음';

  @override
  String get noTradeData => '거래 데이터 없음';

  @override
  String secondsAgo(int seconds) {
    return '$seconds초 전';
  }

  @override
  String get vol24hShort => '24h량';

  @override
  String get vol1hShort => '1h량';

  @override
  String get liqMcShort => '유/시총';

  @override
  String get statusConfirmed => '확인됨';

  @override
  String get statusFailed => '실패';

  @override
  String get statusSubmitting => '제출 중';

  @override
  String get statusPending => '대기 중';

  @override
  String get topHolders => '보유 순위';

  @override
  String get addressLabel => '주소';

  @override
  String get holdingPct => '비율';

  @override
  String get fundFlow24h => '24h 자금 흐름';

  @override
  String get netInflow => '순 유입';

  @override
  String get netOutflow => '순 유출';

  @override
  String get sellPressure => '매도';

  @override
  String get totalBuy => '총 매수';

  @override
  String get totalSell => '총 매도';

  @override
  String get largeOrders => '대규모 거래 (>\$10K)';

  @override
  String get largeBuy => '대규모 매수';

  @override
  String get largeSell => '대규모 매도';

  @override
  String get tradeHistory => '거래 분포';

  @override
  String get buySimple => '매수';

  @override
  String get sellSimple => '매도';
}
