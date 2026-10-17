"""项目根目录主入口 — 供 `python main.py` 调用。

等价于 `python -m entry.main`。
"""

from __future__ import annotations

from entry.main import main

if __name__ == "__main__":
    import sys

    # 双保险：让 stdout/stderr 优先使用 UTF-8（失败时保持原编码不崩）
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    main()
