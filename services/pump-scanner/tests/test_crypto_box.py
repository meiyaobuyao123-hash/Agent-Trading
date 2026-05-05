"""
R42 P1 — crypto_box AES-256-GCM 测试

覆盖:
  - is_master_key_configured 检测
  - encrypt → decrypt 来回(round trip)
  - 不同明文加密结果不同(nonce 随机)
  - 同一明文连续加密结果不同(nonce 随机)
  - master_key 缺失 → encrypt/decrypt 抛 RuntimeError
  - 篡改 blob → decrypt InvalidTag → 抛 RuntimeError
  - 用错 master_key → decrypt 抛 RuntimeError
  - generate_new_master_key_b64 返合法 32 字节 b64

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_crypto_box.py -v
"""
from __future__ import annotations
import base64
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def with_master_key():
    """fixture:设置 32 字节 master_key,清缓存,跑完恢复"""
    from agent.crypto_box import _reset_cache_for_test, generate_new_master_key_b64
    old_env = os.environ.get("WALLET_MASTER_KEY")
    test_key = generate_new_master_key_b64()
    os.environ["WALLET_MASTER_KEY"] = test_key
    _reset_cache_for_test()
    yield test_key
    if old_env is not None:
        os.environ["WALLET_MASTER_KEY"] = old_env
    else:
        os.environ.pop("WALLET_MASTER_KEY", None)
    _reset_cache_for_test()


@pytest.fixture
def no_master_key():
    """fixture:确保 env 没 master_key"""
    from agent.crypto_box import _reset_cache_for_test
    old_env = os.environ.get("WALLET_MASTER_KEY")
    os.environ.pop("WALLET_MASTER_KEY", None)
    _reset_cache_for_test()
    yield
    if old_env is not None:
        os.environ["WALLET_MASTER_KEY"] = old_env
    _reset_cache_for_test()


# ═══════════════════════════════════════════════════════
# is_master_key_configured
# ═══════════════════════════════════════════════════════

class TestMasterKeyConfigured:

    def test_returns_true_when_set(self, with_master_key):
        from agent.crypto_box import is_master_key_configured
        assert is_master_key_configured() is True

    def test_returns_false_when_missing(self, no_master_key):
        from agent.crypto_box import is_master_key_configured
        assert is_master_key_configured() is False

    def test_returns_false_when_invalid_length(self):
        """不是 32 字节的 base64 → 返 False"""
        from agent.crypto_box import is_master_key_configured, _reset_cache_for_test
        old = os.environ.get("WALLET_MASTER_KEY")
        os.environ["WALLET_MASTER_KEY"] = base64.b64encode(b"too_short").decode()
        _reset_cache_for_test()
        try:
            assert is_master_key_configured() is False
        finally:
            if old is not None:
                os.environ["WALLET_MASTER_KEY"] = old
            else:
                os.environ.pop("WALLET_MASTER_KEY", None)
            _reset_cache_for_test()


# ═══════════════════════════════════════════════════════
# encrypt / decrypt round trip
# ═══════════════════════════════════════════════════════

class TestRoundTrip:

    def test_encrypt_decrypt_returns_original(self, with_master_key):
        from agent.crypto_box import encrypt_private_key, decrypt_private_key
        plain = "5KQwrPbwdL6PhXujxW37FSSQZ1JiwsST4cqQzDeyXtP79zkvFD3"
        blob = encrypt_private_key(plain)
        decrypted = decrypt_private_key(blob)
        assert decrypted == plain

    def test_encrypt_evm_hex_key(self, with_master_key):
        from agent.crypto_box import encrypt_private_key, decrypt_private_key
        plain = "0x" + "a" * 64
        blob = encrypt_private_key(plain)
        assert decrypt_private_key(blob) == plain

    def test_blob_is_base64(self, with_master_key):
        from agent.crypto_box import encrypt_private_key
        blob = encrypt_private_key("any private key")
        # 应能 base64 解码
        decoded = base64.b64decode(blob)
        # 至少 12 nonce + 16 tag = 28 字节
        assert len(decoded) >= 28

    def test_different_plain_different_blob(self, with_master_key):
        from agent.crypto_box import encrypt_private_key
        b1 = encrypt_private_key("key_a")
        b2 = encrypt_private_key("key_b")
        assert b1 != b2

    def test_same_plain_different_blob(self, with_master_key):
        """nonce 随机 → 同一明文每次加密 blob 都不同"""
        from agent.crypto_box import encrypt_private_key
        plain = "same key"
        b1 = encrypt_private_key(plain)
        b2 = encrypt_private_key(plain)
        assert b1 != b2  # 不应一样


# ═══════════════════════════════════════════════════════
# 失败路径
# ═══════════════════════════════════════════════════════

class TestFailures:

    def test_encrypt_no_master_key_raises(self, no_master_key):
        from agent.crypto_box import encrypt_private_key
        with pytest.raises(RuntimeError) as exc:
            encrypt_private_key("any")
        assert "WALLET_MASTER_KEY" in str(exc.value)

    def test_decrypt_no_master_key_raises(self, no_master_key):
        from agent.crypto_box import decrypt_private_key
        with pytest.raises(RuntimeError):
            decrypt_private_key("anyblob")

    def test_encrypt_empty_raises(self, with_master_key):
        from agent.crypto_box import encrypt_private_key
        with pytest.raises(ValueError):
            encrypt_private_key("")

    def test_decrypt_empty_raises(self, with_master_key):
        from agent.crypto_box import decrypt_private_key
        with pytest.raises(ValueError):
            decrypt_private_key("")

    def test_decrypt_tampered_blob_raises(self, with_master_key):
        from agent.crypto_box import encrypt_private_key, decrypt_private_key
        blob = encrypt_private_key("real key")
        # 篡改最后一个字节(auth tag 部分)
        raw = bytearray(base64.b64decode(blob))
        raw[-1] ^= 0xFF
        tampered = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(RuntimeError) as exc:
            decrypt_private_key(tampered)
        assert "auth tag" in str(exc.value) or "失败" in str(exc.value)

    def test_decrypt_wrong_master_key_raises(self, with_master_key):
        """A 加密,换 master_key 后 B 解密 → 失败"""
        from agent.crypto_box import (
            encrypt_private_key, decrypt_private_key,
            generate_new_master_key_b64, _reset_cache_for_test,
        )
        blob = encrypt_private_key("real key")
        # 换 master_key
        os.environ["WALLET_MASTER_KEY"] = generate_new_master_key_b64()
        _reset_cache_for_test()
        with pytest.raises(RuntimeError):
            decrypt_private_key(blob)


# ═══════════════════════════════════════════════════════
# generate_new_master_key_b64
# ═══════════════════════════════════════════════════════

class TestGenerate:

    def test_generates_32_bytes_b64(self):
        from agent.crypto_box import generate_new_master_key_b64
        key = generate_new_master_key_b64()
        decoded = base64.b64decode(key)
        assert len(decoded) == 32

    def test_unique_across_calls(self):
        """连续生成 5 个,全不同"""
        from agent.crypto_box import generate_new_master_key_b64
        keys = {generate_new_master_key_b64() for _ in range(5)}
        assert len(keys) == 5
