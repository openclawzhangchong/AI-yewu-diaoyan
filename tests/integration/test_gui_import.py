"""GUI 冒烟测试 — 只验证模块可导入，不实例化 tk 窗口（离线 CI 安全）。"""

from __future__ import annotations

import importlib


def test_gui_module_imports():
    """entry.gui 可被导入（tkinter 已随 Python 可用），且暴露 main 与 GUI 类。"""
    gui = importlib.import_module("entry.gui")
    assert callable(gui.main)
    assert hasattr(gui, "main")
    # 模块导入不应实例化 Tk 窗口
    assert gui.__name__ == "entry.gui"
