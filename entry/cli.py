"""AI业务调研提效分析系统 — 命令行界面（rich + click）

命令:
    analyze   — 分析指定文件
    collect   — 交互式采集调研数据
    departments — 查看支持的部门
    quick-start — 快速开始

用法:
    python main.py analyze --input ./调研总结.md
    python main.py collect
    python main.py departments
    python main.py quick-start
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.ai_engine import AIAnalysisEngine
from core.data_collector import DataCollector
from core.report_generator import ReportGenerator
from core.template_manager import TemplateManager

from domain.analysis import FullAnalysisReport
from domain.config import ModelConfig

from infra.config import ConfigManager
from infra.event_bus import EventBus
from infra.llm_client import LLMClient, create_llm_client
from infra.logger import setup_logging

console = Console()


def _print_header(title: str, subtitle: str = "") -> None:
    """打印标题面板。"""
    console.print(Panel(f"[bold blue]{title}[/bold blue]\n{subtitle}", style="blue"))


def _print_progress(current: float, total: float, label: str = "") -> None:
    """打印进度条。"""
    percent = current / total * 100 if total > 0 else 0
    bar_width = 40
    filled = int(bar_width * percent / 100)
    bar = "[green]" + "█" * filled + "[dim]" + "░" * (bar_width - filled) + "[/]"
    if label:
        console.print(f"{bar} {percent:.0f}% — {label}")
    else:
        console.print(f"{bar} {percent:.0f}%")


def _print_error(msg: str) -> None:
    """打印错误信息。"""
    console.print(f"[red]错误: {msg}[/red]")


def _print_success(msg: str) -> None:
    """打印成功信息。"""
    console.print(f"[green]✓ {msg}[/green]")


@click.group()
def main() -> None:
    """AI业务调研提效分析系统 — 命令行工具"""
    setup_logging()


@main.command()
@click.option("--input", "input_file", required=True, help="输入文件路径 (.md/.txt/.docx/.json)")
@click.option("--output-dir", default=None, help="输出目录（默认: ./output）")
@click.option("--output-format", default=None, help="输出格式 (markdown/excel/json)")
@click.option("--model-name", default=None, help="AI 模型名称")
@click.option("--api-key", default=None, help="API 密钥")
@click.option("--base-url", default=None, help="API 基础 URL")
@click.option("--provider", default=None, help="模型提供商 (openai/qwen/zhipu)")
@click.option("--max-concurrent", type=int, default=None, help="最大并发数")
@click.option("--timeout", type=int, default=None, help="超时秒数")
@click.option("--log-level", default=None, help="日志级别 (DEBUG/INFO/WARNING/ERROR)")
@click.option("--log-file", default=None, help="日志文件路径")
@click.option("--output-format", "output_format", default=None, help="输出格式 (markdown/excel/json)")
def analyze(
    input_file: str,
    output_dir: str | None,
    output_format: str | None,
    model_name: str | None,
    api_key: str | None,
    base_url: str | None,
    provider: str | None,
    max_concurrent: int | None,
    timeout: int | None,
    log_level: str | None,
    log_file: str | None,
) -> None:
    """分析指定调研文件。"""
    _print_header("AI业务调研提效分析系统", "分析调研数据并生成提效建议报告")

    # 加载配置
    config_manager = ConfigManager()
    config_manager.load()
    config = config_manager.get_config()

    # 命令行参数覆盖配置
    if provider:
        config.model.provider = provider
    if api_key:
        config.model.api_key = api_key
    if base_url:
        config.model.base_url = base_url
    if model_name:
        config.model.model_name = model_name
    if max_concurrent:
        config.analysis.max_concurrent = max_concurrent
    if timeout:
        config.analysis.timeout_seconds = timeout
    if output_dir:
        config.output.directory = output_dir
    if output_format:
        config.output.default_format = output_format

    # 验证输入文件
    input_path = Path(input_file)
    if not input_path.exists():
        _print_error(f"文件不存在: {input_file}")
        sys.exit(1)

    console.print(f"\n[blue]输入文件:[/blue] {input_path.absolute()}")

    # 初始化组件
    event_bus = EventBus()
    template_manager = TemplateManager()
    data_collector = DataCollector(event_bus=event_bus)

    # 创建 LLM 客户端
    model_config = ModelConfig(
        provider=config.model.provider,
        api_key=config.model.api_key,
        base_url=config.model.base_url,
        model_name=config.model.model_name,
    )
    llm_client = create_llm_client(model_config)

    # 创建分析引擎
    analysis_engine = AIAnalysisEngine(
        llm_client=llm_client,
        event_bus=event_bus,
        max_concurrency=config.analysis.max_concurrent,
    )

    # 创建报告生成器
    report_generator = ReportGenerator(event_bus=event_bus)

    try:
        # 1. 解析文件
        console.print("[cyan]步骤 1/4: 解析调研数据...[/cyan]")
        _print_progress(10, 100, "解析文件")
        parsed_data = data_collector.parse_file(input_file)

        answers = parsed_data.get("answers", {})
        console.print(f"  找到 [green]{len(answers)}[/green] 个有效答案")
        if not answers:
            _print_error("未找到有效的调研数据")
            console.print("[dim]请检查文件格式，应使用 Markdown 格式 (### Q1 问题文本 / 答案: 内容)[/dim]")
            sys.exit(1)

        # 2. 执行分析
        console.print("\n[cyan]步骤 2/4: 执行 AI 分析...[/cyan]")
        _print_progress(30, 100, "分析进行中（可能需要几分钟）")

        dept_data = {
            "department": input_path.stem,
            "answers": answers,
        }

        # 使用同步方式调用异步方法
        import asyncio
        result = asyncio.run(analysis_engine.analyze_department(dept_data))

        # 3. 生成报告
        console.print("\n[cyan]步骤 3/4: 生成报告...[/cyan]")
        _print_progress(80, 100, "生成报告")

        output_path = Path(config.output.directory)
        output_path.mkdir(parents=True, exist_ok=True)
        timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")

        # 根据选择生成不同格式
        fmt = output_format or config.output.default_format
        if fmt == "excel":
            output_path = report_generator.generate_excel(
                result, str(output_path / f"report_{timestamp}.xlsx")
            )
        elif fmt == "json":
            output_path = report_generator.generate_json(
                result, str(output_path / f"report_{timestamp}.json")
            )
        else:
            content = report_generator.generate_markdown(result)
            output_path = str(output_path / f"report_{timestamp}.md")
            Path(output_path).write_text(content, encoding="utf-8")

        # 4. 输出结果
        _print_progress(100, 100, "完成")
        console.print("\n")
        _print_success("分析完成！报告已生成:")
        console.print(f"  [dim]{output_path}[/dim]")

        # 打印摘要
        console.print("\n[bold]分析摘要:[/bold]")
        console.print(f"  部门: {result.department}")
        console.print(f"  痛点: {len(result.pain_points)} 个")
        console.print(f"  机会点: {len(result.opportunities)} 个")
        console.print(f"  置信度: {result.confidence:.0%}")

        if result.opportunities:
            console.print("\n[bold]高优先级机会点:[/bold]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("优先级", style="bold")
            table.add_column("业务环节")
            table.add_column("AI建议")
            table.add_column("提效")
            table.add_column("难度")

            for opp in sorted(result.opportunities, key=lambda x: x.priority, reverse=True)[:5]:
                table.add_row(
                    str(opp.priority),
                    opp.process,
                    opp.ai_suggestion,
                    opp.expected_efficiency_gain,
                    opp.difficulty,
                )

            console.print(table)

    except Exception as e:
        _print_error(f"分析失败: {e}")
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


@main.command()
@click.option("--template", default=None, help="模板标题（默认: 加载第一个模板）")
def collect(template: str | None) -> None:
    """交互式采集调研数据。"""
    _print_header("AI业务调研提效分析系统", "交互式采集调研数据")

    # 加载模板
    template_manager = TemplateManager()
    templates = template_manager.load_all()

    if not templates:
        _print_error("未找到任何模板，请先在 templates/ 目录下添加模板文件")
        sys.exit(1)

    # 选择模板
    if template:
        tpl = template_manager.get_template(template)
        if not tpl:
            _print_error(f"模板不存在: {template}")
            sys.exit(1)
    else:
        # 显示模板列表
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#")
        table.add_column("模板名称")
        table.add_column("问题数")
        table.add_column("适用部门")

        for i, t in enumerate(templates, 1):
            table.add_row(
                str(i),
                t.title,
                str(len(t.questions)),
                t.department_hint or "全部",
            )

        console.print(table)
        console.print()

        # 选择模板
        while True:
            try:
                choice = input("请选择模板编号 (1-{n}): ".format(n=len(templates)))
                idx = int(choice) - 1
                if 0 <= idx < len(templates):
                    tpl = templates[idx]
                    break
                else:
                    console.print("[red]请输入有效编号[/red]")
            except ValueError:
                console.print("[red]请输入数字[/red]")

    console.print(f"\n[blue]模板:[/blue] {tpl.title}")
    console.print(f"[dim]{tpl.description}[/dim]\n")

    # 交互式采集
    data_collector = DataCollector()
    try:
        answers = data_collector.collect_interactive(tpl)
        console.print("\n[green]✓ 数据采集完成![/green]")
        console.print(f"  共采集 {len(answers)} 个问题的答案")

        # 询问是否保存
        save = input("\n是否保存采集的数据? (y/n): ").strip().lower()
        if save == "y":
            output_path = input("输出文件路径 (默认: ./collected_data.json): ").strip()
            if not output_path:
                output_path = "./collected_data.json"
            data_collector.export({"answers": answers}, output_path)
            console.print(f"[green]✓ 数据已保存: {output_path}[/green]")
    except KeyboardInterrupt:
        console.print("\n[red]采集已取消[/red]")
        sys.exit(0)
    except Exception as e:
        _print_error(f"采集失败: {e}")
        sys.exit(1)


@main.command()
def departments() -> None:
    """查看支持的部门和模板。"""
    _print_header("AI业务调研提效分析系统", "支持的部门和模板")

    template_manager = TemplateManager()
    templates = template_manager.load_all()

    if not templates:
        console.print("[yellow]当前没有加载任何模板。[/yellow]")
        console.print("[dim]请在 templates/ 目录下添加模板文件 (.md/.json)[/dim]")
        return

    # 按部门分组
    dept_templates: dict[str, list] = {}
    for tpl in templates:
        dept = tpl.department_hint or "通用"
        dept_templates.setdefault(dept, []).append(tpl)

    for dept, tpls in sorted(dept_templates.items()):
        console.print(f"\n[bold cyan]{dept}[/bold cyan]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("标题")
        table.add_column("问题数")
        table.add_column("描述")

        for tpl in tpls:
            table.add_row(
                tpl.title,
                str(len(tpl.questions)),
                tpl.description,
            )

        console.print(table)


@main.command()
def quick_start() -> None:
    """快速开始 — 引导用户完成初始化配置。"""
    _print_header("AI业务调研提效分析系统", "快速开始")

    console.print("[cyan]欢迎使用 AI业务调研提效分析系统![/cyan]\n")

    # 1. 配置 API Key
    console.print("[bold]1. 配置 API Key[/bold]")
    api_key = input("  请输入 API Key (或留空跳过): ").strip()

    if api_key:
        # 保存到环境变量
        import os
        os.environ["LLM_API_KEY"] = api_key
        console.print("  [green]✓ API Key 已设置[/green]")

    # 2. 选择模型
    console.print("\n[bold]2. 选择 AI 模型[/bold]")
    console.print("  [1] Qwen (通义千问)")
    console.print("  [2] OpenAI")
    console.print("  [3] Zhipu (智谱)")
    while True:
        choice = input("  请选择 (1-3): ").strip()
        if choice == "1":
            model_name = "qwen-turbo"
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            break
        elif choice == "2":
            model_name = "gpt-4o"
            base_url = "https://api.openai.com/v1"
            break
        elif choice == "3":
            model_name = "glm-4"
            base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
            break
        else:
            console.print("  [red]请输入有效选项 (1-3)[/red]")

    # 3. 创建示例调研文件
    console.print("\n[bold]3. 创建示例调研文件[/bold]")
    example_file = "./调研总结.md"
    if not Path(example_file).exists():
        example_content = """# 运营部

## 用户增长

当前流程：人工分析渠道数据，手动制定投放策略
耗时：每天约2小时
痛点：数据量大，人工统计慢

## 内容运营

当前流程：手动撰写和编辑内容，人工审核
耗时：每天约3小时
痛点：内容创作效率低，审核标准不一
"""
        Path(example_file).write_text(example_content, encoding="utf-8")
        console.print(f"  [green]✓ 已创建示例文件: {example_file}[/green]")
    else:
        console.print(f"  [yellow]示例文件已存在: {example_file}[/yellow]")

    # 4. 运行分析
    console.print("\n[bold]4. 运行分析[/bold]")
    console.print(f"  python main.py analyze --input {example_file}")

    # 5. 查看帮助
    console.print("\n[bold]更多命令[/bold]")
    console.print("  python main.py --help")
    console.print("  python main.py collect  # 交互式采集")
    console.print("  python main.py departments  # 查看模板")
    console.print("\n[bold green]开始使用吧![/bold green]")


if __name__ == "__main__":
    main()
