"""
全局 scanner 引用 — 避免 main ↔ api 循环导入
"""

_scanner = None


def set_scanner(s):
    global _scanner
    _scanner = s


def get_scanner():
    return _scanner
