"""项目根目录主入口 — 供 `python main.py` 调用。

等价于 `python -m entry.main`。
"""

from __future__ import annotations

from entry.main import main

if __name__ == "__main__":
    main()
