"""AI业务调研提效分析系统 — 主入口

支持两种运行模式：
    - GUI 模式（默认）：启动图形界面
    - CLI 模式：命令行模式，需要 --cli 参数

用法:
    python main.py                    # GUI 模式
    python main.py --cli              # CLI 模式
    python main.py --help             # 显示帮助信息
"""

from __future__ import annotations

import argparse
import sys

from infra.logger import setup_logging
from infra.config import ConfigManager
from infra.event_bus import EventBus


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        prog="AI业务调研提效分析系统",
        description="通过结构化调研收集各部门业务场景信息，利用AI大模型分析识别各业务环节中可引入AI提效的具体环节。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
用法示例:
    python main.py                启动图形界面
    python main.py --cli          启动命令行模式
    python main.py --help         显示帮助信息
        """,
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        default=False,
        help="启动命令行模式（默认启动GUI）",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="配置文件路径（默认: config.yaml）",
    )
    return parser.parse_args()


def main() -> None:
    """主入口函数。"""
    args = parse_args()

    # 初始化日志
    setup_logging()

    # 加载配置
    config_manager = ConfigManager(config_path=args.config)
    config_manager.load()

    # 初始化事件总线
    event_bus = EventBus()

    if args.cli:
        # CLI 模式
        from entry.cli import main as cli_main
        cli_main()
    else:
        # GUI 模式
        from entry.gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
