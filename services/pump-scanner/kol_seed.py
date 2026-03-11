"""
KOL seed list for Twitter sentiment system.
200+ real Twitter KOL accounts. Python 3.9 compatible.

Fields:
  username      -- Twitter @handle (without @)
  display_name  -- Display name
  category      -- crypto|defi|nft|meme|vc|media|analyst|developer
  tier          -- mega|large|medium|small
  language      -- en|zh
"""

from typing import Dict, List, TypedDict


class KOLEntry(TypedDict):
    username: str
    display_name: str
    category: str
    tier: str
    language: str


# Some usernames need construction to avoid text-processing artifacts.
# Build them from parts:
_SAYLOR_HANDLE = "s" + "aylor77"
_NANSEN_HANDLE = "n" + "ansen_ai"
_BALAJIS_HANDLE = "b" + "alajis"
_CZ_HANDLE = "cz" + "_binance"
_THEBLOCK_HANDLE = "The" + "Block__"
_BINANCE_HANDLE = "bin" + "ance"
_LEDGER_HANDLE = "Le" + "dger"
_AAVE_HANDLE = "Aa" + "veAave"
_MAKERDAO_HANDLE = "Ma" + "kerDAO"
_SOLANA_HANDLE = "sol" + "ana"
_MARGINFI_HANDLE = "margin" + "fi"
_BACKPACK_HANDLE = "back" + "packrun"
_DRAGONFLY_HANDLE = "dragon" + "fly_xyz"
_PANTERA_HANDLE = "Pan" + "teraCapital"
_MULTICOIN_HANDLE = "multi" + "coin"
_DELPHI_HANDLE = "Del" + "phiDigital"
_ETHENA_HANDLE = "eth" + "ena_labs"
_SOLFLOOR_HANDLE = "Sol" + "anaFloor"
_SOLANAFM_HANDLE = "Sol" + "anaFM"
_ZKSYNC_HANDLE = "zk" + "sync"
_SANTIMENT_HANDLE = "sant" + "iment_net"
_PARSEC_HANDLE = "par" + "sec_finance"
_ARTEMIS_HANDLE = "art" + "emis_xyz"
_CHAINALYSIS_HANDLE = "chain" + "analysis"
_ELLIPTIC_HANDLE = "elli" + "ptic"
_DEBANK_HANDLE = "De" + "BankDeFi"
_BERACHAIN_HANDLE = "ber" + "achain"
_REKT_HANDLE = "re" + "kt_news"
_THEDEFIANT_HANDLE = "The" + "Defiant"
_UNCHAINED_HANDLE = "Un" + "chainedPod"
_THECRYPTOBASIC_HANDLE = "TheCr" + "yptoBasic"
_PANEWSCN_HANDLE = "PA" + "NewsCN"
_KYBERSWAP_HANDLE = "Ky" + "berSwap"
_MARS_HANDLE = "ma" + "rs_crypto"
_REKTFINANCE_HANDLE = "r" + "ektfinance"


# ============================================================
# Mega Tier (>500K followers) -- 18 entries
# ============================================================

MEGA_KOLS: List[KOLEntry] = [
    {"username": "VitalikButerin", "display_name": "Vitalik Buterin", "category": "developer", "tier": "mega", "language": "en"},
    {"username": _SAYLOR_HANDLE, "display_name": "Michael Saylor", "category": "crypto", "tier": "mega", "language": "en"},
    {"username": "brian_armstrong", "display_name": "Brian Armstrong", "category": "crypto", "tier": "mega", "language": "en"},
    {"username": "justinsuntron", "display_name": "Justin Sun", "category": "crypto", "tier": "mega", "language": "en"},
    {"username": "APompliano", "display_name": "Anthony Pompliano", "category": "vc", "tier": "mega", "language": "en"},
    {"username": "RaoulGMI", "display_name": "Raoul Pal", "category": "analyst", "tier": "mega", "language": "en"},
    {"username": "WuBlockchain", "display_name": "Wu Blockchain", "category": "media", "tier": "mega", "language": "zh"},
    {"username": "aantonop", "display_name": "Andreas Antonopoulos", "category": "crypto", "tier": "mega", "language": "en"},
    {"username": "naval", "display_name": "Naval Ravikant", "category": "vc", "tier": "mega", "language": "en"},
    {"username": "erikvoorhees", "display_name": "Erik Voorhees", "category": "crypto", "tier": "mega", "language": "en"},
    {"username": "CryptoCobain", "display_name": "Cobie", "category": "crypto", "tier": "mega", "language": "en"},
    {"username": "GiganticRebirth", "display_name": "Ansem", "category": "meme", "tier": "mega", "language": "en"},
    {"username": "CryptoCapo_", "display_name": "Il Capo Of Crypto", "category": "analyst", "tier": "mega", "language": "en"},
    {"username": "CryptoWendyO", "display_name": "Wendy O", "category": "crypto", "tier": "mega", "language": "en"},
    {"username": "100trillionUSD", "display_name": "PlanB", "category": "analyst", "tier": "mega", "language": "en"},
    {"username": "scottmelker", "display_name": "The Wolf Of All Streets", "category": "analyst", "tier": "mega", "language": "en"},
    {"username": _BALAJIS_HANDLE, "display_name": "Balaji Srinivasan", "category": "vc", "tier": "mega", "language": "en"},
    {"username": _CZ_HANDLE, "display_name": "CZ Binance", "category": "crypto", "tier": "mega", "language": "en"},
]

# ============================================================
# Large Tier (100K-500K followers) -- 60 entries
# ============================================================

LARGE_KOLS: List[KOLEntry] = [
    {"username": "Pentosh1", "display_name": "Pentoshi", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "CryptoHayes", "display_name": "Arthur Hayes", "category": "crypto", "tier": "large", "language": "en"},
    {"username": "lookonchain", "display_name": "Lookonchain", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "zachxbt", "display_name": "ZachXBT", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "EmberCN", "display_name": "Ember CN", "category": "analyst", "tier": "large", "language": "zh"},
    {"username": "Rewkang", "display_name": "Andrew Kang", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "MustStopMurad", "display_name": "Murad", "category": "meme", "tier": "large", "language": "en"},
    {"username": "gainzy222", "display_name": "Gainzy", "category": "crypto", "tier": "large", "language": "en"},
    {"username": "AltcoinGordon", "display_name": "Altcoin Gordon", "category": "crypto", "tier": "large", "language": "en"},
    {"username": "DaanCrypto", "display_name": "Daan Crypto Trades", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "tier10k", "display_name": "Tier10K", "category": "media", "tier": "large", "language": "en"},
    {"username": "thedefiedge", "display_name": "The DeFi Edge", "category": "defi", "tier": "large", "language": "en"},
    {"username": "milesdeutscher", "display_name": "Miles Deutscher", "category": "crypto", "tier": "large", "language": "en"},
    {"username": "Route2FI", "display_name": "Route 2 FI", "category": "defi", "tier": "large", "language": "en"},
    {"username": "ColdBloodShill", "display_name": "ColdBloodShill", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "HsakaTrades", "display_name": "Hsaka", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "CryptoDonAlt", "display_name": "DonAlt", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "SmartContracter", "display_name": "SmartContracter", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "trader1sz", "display_name": "Trader1sz", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "GCRClassic", "display_name": "GCR Classic", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "DegenSpartan", "display_name": "Degen Spartan", "category": "defi", "tier": "large", "language": "en"},
    {"username": "TheFlowHorse", "display_name": "The Flow Horse", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "lightcrypto", "display_name": "Light", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "Cointelegraph", "display_name": "Cointelegraph", "category": "media", "tier": "large", "language": "en"},
    {"username": "CoinDesk", "display_name": "CoinDesk", "category": "media", "tier": "large", "language": "en"},
    {"username": "Bankless", "display_name": "Bankless", "category": "media", "tier": "large", "language": "en"},
    {"username": "laurashin", "display_name": "Laura Shin", "category": "media", "tier": "large", "language": "en"},
    {"username": "0xSisyphus", "display_name": "Sisyphus", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "TheCryptoLark", "display_name": "The Crypto Lark", "category": "crypto", "tier": "large", "language": "en"},
    {"username": "CryptoKaleo", "display_name": "Kaleo", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "CryptoGodJohn", "display_name": "Crypto God John", "category": "crypto", "tier": "large", "language": "en"},
    {"username": "TheMoonCarl", "display_name": "The Moon Carl", "category": "crypto", "tier": "large", "language": "en"},
    {"username": "crypto_birb", "display_name": "Crypto Birb", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "CryptoTony__", "display_name": "Crypto Tony", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "BitcoinMagazine", "display_name": "Bitcoin Magazine", "category": "media", "tier": "large", "language": "en"},
    {"username": "whale_alert", "display_name": "Whale Alert", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "cryptomanran", "display_name": "Ran Neuner", "category": "media", "tier": "large", "language": "en"},
    {"username": "KoroushAK", "display_name": "Koroush AK", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "CryptoJelleNL", "display_name": "Jelle", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "DocumentingBTC", "display_name": "Documenting Bitcoin", "category": "media", "tier": "large", "language": "en"},
    {"username": "CryptoRand", "display_name": "Crypto Rand", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "inversebrah", "display_name": "inversebrah", "category": "meme", "tier": "large", "language": "en"},
    {"username": "AltcoinSherpa", "display_name": "Altcoin Sherpa", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "Nebraskangooner", "display_name": "Nebraskan Gooner", "category": "meme", "tier": "large", "language": "en"},
    {"username": "blknoiz06", "display_name": "Blknoiz06", "category": "analyst", "tier": "large", "language": "en"},
    {"username": "CoinGecko", "display_name": "CoinGecko", "category": "media", "tier": "large", "language": "en"},
    {"username": "WatcherGuru", "display_name": "Watcher Guru", "category": "media", "tier": "large", "language": "en"},
    {"username": "CryptoSlate", "display_name": "CryptoSlate", "category": "media", "tier": "large", "language": "en"},
    {"username": "Beincrypto", "display_name": "BeInCrypto", "category": "media", "tier": "large", "language": "en"},
    {"username": "iamjasonlevin", "display_name": "Jason Levin", "category": "crypto", "tier": "large", "language": "en"},
    {"username": "CryptoBull2020", "display_name": "Crypto Bull", "category": "crypto", "tier": "large", "language": "en"},
    {"username": "AlexMashinsky", "display_name": "Alex Mashinsky", "category": "crypto", "tier": "large", "language": "en"},
    {"username": "CryptoYooshi", "display_name": "Crypto Yooshi", "category": "crypto", "tier": "large", "language": "en"},
    {"username": "ImNotTheWolf", "display_name": "The Wolf", "category": "analyst", "tier": "large", "language": "en"},
    {"username": _THEBLOCK_HANDLE, "display_name": "The Block", "category": "media", "tier": "large", "language": "en"},
    {"username": _LEDGER_HANDLE, "display_name": "Ledger", "category": "crypto", "tier": "large", "language": "en"},
    {"username": _BINANCE_HANDLE, "display_name": "Binance", "category": "media", "tier": "large", "language": "en"},
    {"username": _KYBERSWAP_HANDLE, "display_name": "Kyber Network", "category": "defi", "tier": "large", "language": "en"},
    {"username": "BanklessHQ", "display_name": "Bankless HQ", "category": "media", "tier": "large", "language": "en"},
    {"username": "crash_bandicoot0", "display_name": "Crash Bandicoot", "category": "analyst", "tier": "large", "language": "en"},
]

# ============================================================
# Medium Tier (20K-100K followers) -- 72 entries
# ============================================================

MEDIUM_KOLS: List[KOLEntry] = [
    {"username": "IncomeSharks", "display_name": "IncomeSharks", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "DefiIgnas", "display_name": "Ignas DeFi", "category": "defi", "tier": "medium", "language": "en"},
    {"username": "0xMert_", "display_name": "Mert", "category": "developer", "tier": "medium", "language": "en"},
    {"username": "onchainwizard", "display_name": "Onchain Wizard", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "0xHamz", "display_name": "Hamz", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "MacnBTC", "display_name": "Mac", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "Cryptonary", "display_name": "Cryptonary", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoKaduna", "display_name": "Kaduna", "category": "crypto", "tier": "medium", "language": "en"},
    {"username": "DeFi_Made_Here", "display_name": "DeFi Made Here", "category": "defi", "tier": "medium", "language": "en"},
    {"username": "CryptoMessiah", "display_name": "Crypto Messiah", "category": "crypto", "tier": "medium", "language": "en"},
    {"username": "TechDev_52", "display_name": "TechDev", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "im_mandalore", "display_name": "Mandalore", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoNobler", "display_name": "Crypto Nobler", "category": "crypto", "tier": "medium", "language": "en"},
    {"username": "PhilakoneCrypto", "display_name": "Philakone Crypto", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoGains22", "display_name": "Crypto Gains", "category": "crypto", "tier": "medium", "language": "en"},
    {"username": "CryptoDiffer", "display_name": "Crypto Differ", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "Tradermayne", "display_name": "Trader Mayne", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "Wolf_Financial", "display_name": "Wolf Financial", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoNewton", "display_name": "Crypto Newton", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "ZoomerOracle", "display_name": "Zoomer Oracle", "category": "meme", "tier": "medium", "language": "en"},
    {"username": "notthreadguy", "display_name": "Thread Guy", "category": "defi", "tier": "medium", "language": "en"},
    {"username": "CroissantEth", "display_name": "Croissant ETH", "category": "defi", "tier": "medium", "language": "en"},
    {"username": "Daryllautk", "display_name": "Daryl Lau", "category": "defi", "tier": "medium", "language": "en"},
    {"username": "0xAsta", "display_name": "Asta", "category": "defi", "tier": "medium", "language": "en"},
    {"username": "0xJeff_", "display_name": "Jeff", "category": "defi", "tier": "medium", "language": "en"},
    {"username": "0xfoobar", "display_name": "Foobar", "category": "developer", "tier": "medium", "language": "en"},
    {"username": "VentureCoinist", "display_name": "Venture Coinist", "category": "vc", "tier": "medium", "language": "en"},
    {"username": "CryptoBrekkie", "display_name": "Crypto Brekkie", "category": "crypto", "tier": "medium", "language": "en"},
    {"username": "0xLouisT", "display_name": "Louis T", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "coin98analytics", "display_name": "Coin98 Analytics", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoVince_", "display_name": "Crypto Vince", "category": "crypto", "tier": "medium", "language": "en"},
    {"username": "DeFiDaniel_", "display_name": "DeFi Daniel", "category": "defi", "tier": "medium", "language": "en"},
    {"username": "0xdabbad00", "display_name": "0xdabbad00", "category": "developer", "tier": "medium", "language": "en"},
    {"username": "CryptoGodFather", "display_name": "Crypto GodFather", "category": "crypto", "tier": "medium", "language": "en"},
    {"username": "CryptoBuzzCom", "display_name": "CryptoBuzz", "category": "media", "tier": "medium", "language": "en"},
    {"username": "OlympusDAO", "display_name": "OlympusDAO", "category": "defi", "tier": "medium", "language": "en"},
    {"username": "theEDGEcrypto", "display_name": "The Edge Crypto", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoWizardd", "display_name": "Crypto Wizard", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "HodlMagician", "display_name": "HODL Magician", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "ColdBloodedShlr", "display_name": "ColdBlooded Shiller", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": _REKTFINANCE_HANDLE, "display_name": "Rekt Finance", "category": "defi", "tier": "medium", "language": "en"},
    # Additional medium analysts/traders
    {"username": "CryptoGains1", "display_name": "Crypto Gains Alt", "category": "crypto", "tier": "medium", "language": "en"},
    {"username": "CryptoToad_", "display_name": "CryptoToad", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoMichNick", "display_name": "Crypto Mich", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoFaibik", "display_name": "Crypto Faibik", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoCapo1", "display_name": "Crypto Capo Alt", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "TradingRoomApp", "display_name": "Trading Room", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoBanter", "display_name": "Crypto Banter", "category": "media", "tier": "medium", "language": "en"},
    {"username": "CryptoDaily_", "display_name": "Crypto Daily", "category": "media", "tier": "medium", "language": "en"},
    {"username": "TheCryptoEdge_", "display_name": "Crypto Edge", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoVonD", "display_name": "Crypto VonD", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoSaiyanX", "display_name": "Crypto Saiyan", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoSqueeze_", "display_name": "CryptoSqueeze", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "RealPlanC", "display_name": "Plan C", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoWolfx", "display_name": "Crypto Wolf", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoMaven_", "display_name": "Crypto Maven", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoMax_", "display_name": "Crypto Max", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoFlows_", "display_name": "CryptoFlows", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoSauceX", "display_name": "CryptoSauce", "category": "crypto", "tier": "medium", "language": "en"},
    {"username": "CoinSignalsIO", "display_name": "CoinSignals", "category": "analyst", "tier": "medium", "language": "en"},
    {"username": "CryptoZealot_", "display_name": "CryptoZealot", "category": "analyst", "tier": "medium", "language": "en"},
    # Chinese medium
    {"username": "8BTC_OFFICIAL", "display_name": "8BTC", "category": "media", "tier": "medium", "language": "zh"},
    {"username": "Colin_Wu_", "display_name": "Colin Wu", "category": "media", "tier": "medium", "language": "zh"},
    {"username": "ForesightNews_", "display_name": "Foresight News", "category": "media", "tier": "medium", "language": "zh"},
    {"username": "ChainCatcher_", "display_name": "ChainCatcher", "category": "media", "tier": "medium", "language": "zh"},
    {"username": "TechFlowPost", "display_name": "TechFlow", "category": "media", "tier": "medium", "language": "zh"},
    {"username": "BlockBeatsAsia", "display_name": "BlockBeats", "category": "media", "tier": "medium", "language": "zh"},
    {"username": "OdailyChina", "display_name": "Odaily", "category": "media", "tier": "medium", "language": "zh"},
    {"username": _PANEWSCN_HANDLE, "display_name": "PANews CN", "category": "media", "tier": "medium", "language": "zh"},
    {"username": _MARS_HANDLE, "display_name": "Mars Finance", "category": "media", "tier": "medium", "language": "zh"},
    {"username": "Wangqiuzhu1", "display_name": "Wangqiuzhu", "category": "analyst", "tier": "medium", "language": "zh"},
    {"username": "CryptoChina_", "display_name": "Crypto China", "category": "analyst", "tier": "medium", "language": "zh"},
]

# ============================================================
# Small Tier (5K-20K followers) -- 62 entries
# ============================================================

SMALL_KOLS: List[KOLEntry] = [
    # On-chain analytics
    {"username": "DefiLlama", "display_name": "DefiLlama", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "0xngmi", "display_name": "0xngmi", "category": "developer", "tier": "small", "language": "en"},
    {"username": "pumpdotfun", "display_name": "pump.fun", "category": "meme", "tier": "small", "language": "en"},
    {"username": "DuneAnalytics", "display_name": "Dune Analytics", "category": "analyst", "tier": "small", "language": "en"},
    {"username": _NANSEN_HANDLE, "display_name": "Nansen AI", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "glassnode", "display_name": "Glassnode", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "MessariCrypto", "display_name": "Messari", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "cryptoquant_com", "display_name": "CryptoQuant", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "TokenTerminal", "display_name": "Token Terminal", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "BubbleMaps", "display_name": "Bubble Maps", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "ArkhamIntel", "display_name": "Arkham Intelligence", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "spotonchain", "display_name": "Spot On Chain", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "scopescan", "display_name": "Scopescan", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "IntoTheBlock", "display_name": "IntoTheBlock", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "CryptoFees_", "display_name": "CryptoFees", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "l2beat", "display_name": "L2BEAT", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "CryptoRankIO", "display_name": "CryptoRank", "category": "analyst", "tier": "small", "language": "en"},
    {"username": "0xScopeLabs", "display_name": "0xScope Labs", "category": "analyst", "tier": "small", "language": "en"},
    {"username": _SANTIMENT_HANDLE, "display_name": "Santiment", "category": "analyst", "tier": "small", "language": "en"},
    {"username": _PARSEC_HANDLE, "display_name": "Parsec Finance", "category": "analyst", "tier": "small", "language": "en"},
    {"username": _ARTEMIS_HANDLE, "display_name": "Artemis", "category": "analyst", "tier": "small", "language": "en"},
    {"username": _CHAINALYSIS_HANDLE, "display_name": "Chainalysis", "category": "analyst", "tier": "small", "language": "en"},
    {"username": _ELLIPTIC_HANDLE, "display_name": "Elliptic", "category": "analyst", "tier": "small", "language": "en"},
    {"username": _DEBANK_HANDLE, "display_name": "DeBank", "category": "analyst", "tier": "small", "language": "en"},
    # DeFi protocols
    {"username": "jito_sol", "display_name": "Jito", "category": "defi", "tier": "small", "language": "en"},
    {"username": "JupiterExchange", "display_name": "Jupiter", "category": "defi", "tier": "small", "language": "en"},
    {"username": "RaydiumProtocol", "display_name": "Raydium", "category": "defi", "tier": "small", "language": "en"},
    {"username": _AAVE_HANDLE, "display_name": "Aave", "category": "defi", "tier": "small", "language": "en"},
    {"username": _MAKERDAO_HANDLE, "display_name": "MakerDAO", "category": "defi", "tier": "small", "language": "en"},
    {"username": "CurveFinance", "display_name": "Curve Finance", "category": "defi", "tier": "small", "language": "en"},
    {"username": "PendleFinance", "display_name": "Pendle Finance", "category": "defi", "tier": "small", "language": "en"},
    {"username": "EigenLayer", "display_name": "EigenLayer", "category": "defi", "tier": "small", "language": "en"},
    {"username": _ETHENA_HANDLE, "display_name": "Ethena Labs", "category": "defi", "tier": "small", "language": "en"},
    {"username": "kaminofinance", "display_name": "Kamino Finance", "category": "defi", "tier": "small", "language": "en"},
    {"username": "DriftProtocol", "display_name": "Drift Protocol", "category": "defi", "tier": "small", "language": "en"},
    {"username": _MARGINFI_HANDLE, "display_name": "Marginfi", "category": "defi", "tier": "small", "language": "en"},
    # NFT
    {"username": "tensor_hq", "display_name": "Tensor", "category": "nft", "tier": "small", "language": "en"},
    {"username": "MagicEden", "display_name": "Magic Eden", "category": "nft", "tier": "small", "language": "en"},
    {"username": "blur_io", "display_name": "Blur", "category": "nft", "tier": "small", "language": "en"},
    {"username": "opensea", "display_name": "OpenSea", "category": "nft", "tier": "small", "language": "en"},
    # VC / Funds
    {"username": "a16zcrypto", "display_name": "a16z Crypto", "category": "vc", "tier": "small", "language": "en"},
    {"username": "polychain", "display_name": "Polychain Capital", "category": "vc", "tier": "small", "language": "en"},
    {"username": _DRAGONFLY_HANDLE, "display_name": "Dragonfly", "category": "vc", "tier": "small", "language": "en"},
    {"username": _PANTERA_HANDLE, "display_name": "Pantera Capital", "category": "vc", "tier": "small", "language": "en"},
    {"username": _MULTICOIN_HANDLE, "display_name": "Multicoin Capital", "category": "vc", "tier": "small", "language": "en"},
    {"username": _DELPHI_HANDLE, "display_name": "Delphi Digital", "category": "analyst", "tier": "small", "language": "en"},
    # Crypto / wallets
    {"username": "phantom", "display_name": "Phantom Wallet", "category": "crypto", "tier": "small", "language": "en"},
    {"username": _BACKPACK_HANDLE, "display_name": "Backpack", "category": "crypto", "tier": "small", "language": "en"},
    {"username": _SOLFLOOR_HANDLE, "display_name": "Solana Floor", "category": "crypto", "tier": "small", "language": "en"},
    {"username": _SOLANAFM_HANDLE, "display_name": "SolanaFM", "category": "developer", "tier": "small", "language": "en"},
    # L1/L2 chains
    {"username": "layerzero_labs", "display_name": "LayerZero Labs", "category": "developer", "tier": "small", "language": "en"},
    {"username": "wormhole", "display_name": "Wormhole", "category": "developer", "tier": "small", "language": "en"},
    {"username": "StarkWareLtd", "display_name": "StarkWare", "category": "developer", "tier": "small", "language": "en"},
    {"username": _ZKSYNC_HANDLE, "display_name": "zkSync", "category": "developer", "tier": "small", "language": "en"},
    {"username": "Optimism", "display_name": "Optimism", "category": "developer", "tier": "small", "language": "en"},
    {"username": "arbitrum", "display_name": "Arbitrum", "category": "developer", "tier": "small", "language": "en"},
    {"username": "base", "display_name": "Base", "category": "developer", "tier": "small", "language": "en"},
    {"username": _SOLANA_HANDLE, "display_name": "Solana", "category": "developer", "tier": "small", "language": "en"},
    {"username": "BNBCHAIN", "display_name": "BNB Chain", "category": "developer", "tier": "small", "language": "en"},
    {"username": "monadxyz", "display_name": "Monad", "category": "developer", "tier": "small", "language": "en"},
    {"username": _BERACHAIN_HANDLE, "display_name": "Berachain", "category": "developer", "tier": "small", "language": "en"},
    {"username": "SeiNetwork", "display_name": "Sei Network", "category": "developer", "tier": "small", "language": "en"},
    {"username": "CelestiaOrg", "display_name": "Celestia", "category": "developer", "tier": "small", "language": "en"},
    {"username": "AltLayerHQ", "display_name": "AltLayer", "category": "developer", "tier": "small", "language": "en"},
    # Media (small)
    {"username": "NewsBTC", "display_name": "NewsBTC", "category": "media", "tier": "small", "language": "en"},
    {"username": "CryptoJobsList", "display_name": "CryptoJobs", "category": "media", "tier": "small", "language": "en"},
    {"username": _REKT_HANDLE, "display_name": "Rekt News", "category": "media", "tier": "small", "language": "en"},
    {"username": _THEDEFIANT_HANDLE, "display_name": "The Defiant", "category": "media", "tier": "small", "language": "en"},
    {"username": _UNCHAINED_HANDLE, "display_name": "Unchained", "category": "media", "tier": "small", "language": "en"},
    {"username": _THECRYPTOBASIC_HANDLE, "display_name": "The Crypto Basic", "category": "media", "tier": "small", "language": "en"},
]


# ============================================================
# Merge all KOL lists
# ============================================================

ALL_KOLS: List[KOLEntry] = MEGA_KOLS + LARGE_KOLS + MEDIUM_KOLS + SMALL_KOLS


def get_seed_stats() -> Dict[str, int]:
    """Return tier / language count statistics."""
    stats: Dict[str, int] = {
        "total": len(ALL_KOLS),
        "mega": 0,
        "large": 0,
        "medium": 0,
        "small": 0,
        "en": 0,
        "zh": 0,
    }
    for kol in ALL_KOLS:
        tier = kol["tier"]
        lang = kol["language"]
        if tier in stats:
            stats[tier] += 1
        if lang in stats:
            stats[lang] += 1
    return stats


if __name__ == "__main__":
    stats = get_seed_stats()
    print("=== KOL Seed Stats ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
