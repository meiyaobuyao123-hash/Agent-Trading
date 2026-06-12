"""
测试全局隔离:切断生产 .env 对测试行为的泄漏。

背景(R71 审计发现):模块 import 时 load_dotenv 把生产 .env 注入 os.environ,
而下列开关是运行时 os.getenv 读取的,导致在服务器上跑测试时:
- DRY_RUN_LIVE_TRADES=true → trade_executor 提前返 mock,router 的 mock 永远不被
  调用 → test_trade_executor_risk_params 8 个测试 call_args=None 全挂
- ANTHROPIC_API_KEY 存在 → test_execute_l2_no_api_key 之类"无 key"测试真调
  Anthropic API(花真钱 + 全套跑时触发限流导致连环挂)

需要这些开关的测试,用 monkeypatch.setenv 在测试内自行设置。
"""
import pytest

_PROD_ENV_LEAKS = [
    "DRY_RUN_LIVE_TRADES",
    "ANTHROPIC_API_KEY",
]


@pytest.fixture(autouse=True)
def _isolate_prod_env(monkeypatch):
    for var in _PROD_ENV_LEAKS:
        monkeypatch.delenv(var, raising=False)
