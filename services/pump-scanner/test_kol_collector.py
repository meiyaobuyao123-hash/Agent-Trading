"""
KOL Collector 快速测试脚本

用法：
    # 设置 API Key 后运行
    TWITTERAPI_IO_KEY=your_key_here python3 test_kol_collector.py

    # 或直接编辑下方 API_KEY 变量
"""
import asyncio
import os
import sys
import json
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# 如果没有设置环境变量，可以在这里直接填入 API Key
API_KEY = os.getenv("TWITTERAPI_IO_KEY", "")

if not API_KEY:
    print("=" * 60)
    print("请设置 TWITTERAPI_IO_KEY 环境变量或编辑此文件中的 API_KEY")
    print("用法: TWITTERAPI_IO_KEY=xxx python3 test_kol_collector.py")
    print("=" * 60)
    sys.exit(1)

# 临时设置环境变量
os.environ["TWITTERAPI_IO_KEY"] = API_KEY

from kol_collector import KOLCollector


async def test_user_info():
    """测试获取用户信息"""
    print("\n" + "=" * 60)
    print("Test 1: 获取用户信息 (@elonmusk)")
    print("=" * 60)

    collector = KOLCollector()
    info = await collector.get_user_info("elonmusk")

    if info:
        print(f"  Username: @{info.get('userName', 'N/A')}")
        print(f"  Name: {info.get('name', 'N/A')}")
        print(f"  Followers: {info.get('followers', 0):,}")
        print(f"  Following: {info.get('following', 0):,}")
        print(f"  Tweets: {info.get('statusesCount', 0):,}")
        print(f"  Verified: {info.get('isBlueVerified', False)}")
        print(f"  Bio: {(info.get('description', '') or '')[:100]}")
        print("  ✅ 成功!")
    else:
        print("  ❌ 失败!")

    return info


async def test_user_tweets():
    """测试获取用户推文"""
    print("\n" + "=" * 60)
    print("Test 2: 获取最新推文 (@VitalikButerin, 5条)")
    print("=" * 60)

    collector = KOLCollector()
    tweets = await collector.collect_user_tweets(
        username="VitalikButerin",
        twitter_uid="vitalik_test",
        limit=5,
    )

    if tweets:
        for i, t in enumerate(tweets):
            text = t["content"][:80].replace("\n", " ")
            print(f"  [{i+1}] {text}...")
            print(f"      ❤️ {t['like_count']:,}  🔁 {t['retweet_count']:,}  "
                  f"💬 {t['reply_count']:,}  👀 {t['view_count']:,}")
        print(f"  ✅ 获取 {len(tweets)} 条推文!")
    else:
        print("  ❌ 未获取到推文!")

    return tweets


async def test_search():
    """测试搜索推文"""
    print("\n" + "=" * 60)
    print("Test 3: 搜索代币提及 (\"$PEPE\" OR \"$WIF\")")
    print("=" * 60)

    collector = KOLCollector()
    tweets = await collector.search_token_mentions(
        query='("$PEPE" OR "$WIF") min_faves:50',
        limit=5,
    )

    if tweets:
        for i, t in enumerate(tweets):
            author_uid = t.get("twitter_uid", "?")
            text = t["content"][:80].replace("\n", " ")
            print(f"  [{i+1}] @{author_uid}: {text}...")
            print(f"      ❤️ {t['like_count']:,}  🔁 {t['retweet_count']:,}")
        print(f"  ✅ 搜索到 {len(tweets)} 条!")
    else:
        print("  ❌ 未搜索到结果!")

    return tweets


async def main():
    print("=" * 60)
    print("KOL Collector 测试 — twitterapi.io")
    print(f"API Key: {API_KEY[:8]}...{API_KEY[-4:]}")
    print("=" * 60)

    # Test 1: 用户信息
    await test_user_info()

    # Test 2: 用户推文
    await test_user_tweets()

    # Test 3: 搜索
    await test_search()

    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
