"""AI业务调研提效分析系统 — 主入口

支持两种运行模式：
    - GUI 模式（默认）：启动图形界面
    - CLI 模式：命令行模式，需要 --cli 参数，之后可跟随子命令

用法:
    python main.py                    # GUI 模式
    python main.py --cli              # CLI 模式（显示帮助）
    python main.py --cli departments  # CLI 模式 + 子命令透传
    python main.py --help             # 显示帮助信息
"""

from __future__ import annotations

import argparse
import sys

from infra.logger import setup_logging
from infra.config import ConfigManager
from infra.event_bus import EventBus


def parse_gui_args() -> argparse.Namespace:
    """解析 GUI 模式的命令行参数，剩余参数透传给 CLI。"""
    parser = argparse.ArgumentParser(
        prog="AI业务调研提效分析系统",
        description="通过结构化调研收集各部门业务场景信息，利用AI大模型分析识别各业务环节中可引入AI提效的具体环节。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
用法示例:
    python main.py                启动图形界面
    python main.py --cli          启动命令行模式
    python main.py --cli analyze --input ./调研.md   CLI 子命令
    python main.py --help         显示帮助信息
        """,
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        default=False,
        help="启动命令行模式（默认启动GUI），其后参数透传给 CLI",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="配置文件路径（默认: config.yaml）",
    )
    args, _extra = parser.parse_known_args()
    return args


def main() -> None:
    """主入口函数。"""
    args = parse_gui_args()

    # 初始化日志
    setup_logging()

    # 加载配置
    config_manager = ConfigManager(config_path=args.config)
    config_manager.load()

    # 初始化事件总线
    event_bus = EventBus()

    if args.cli:
        # CLI 模式：把 --cli 之后的参数透传给 click
        from entry.cli import main as cli_main

        cli_args = []
        if "--cli" in sys.argv:
            idx = sys.argv.index("--cli")
            cli_args = sys.argv[idx + 1:]
        if not cli_args:
            cli_args = ["--help"]
        cli_main(args=cli_args)
    else:
        # GUI 模式
        from entry.gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
