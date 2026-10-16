"""AI业务调研提效分析系统 — 图形界面（Tkinter）

功能:
    - 选择输入文件（.md/.txt/.docx/.json）
    - 输出格式选择（Markdown/Excel/JSON）
    - 分析深度选择（快速/标准/深度）
    - 提交/取消按钮
    - 进度条 + 状态提示
    - 后台线程执行分析（不阻塞 GUI）
    - 完成后弹出提示
    - 跨平台打开文件目录
    - 快捷键：Ctrl+O 打开文件，Ctrl+S 提交，Ctrl+Q 退出
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from domain.config import ModelConfig

from core.ai_engine import AIAnalysisEngine
from core.data_collector import DataCollector
from core.report_generator import ReportGenerator
from core.template_manager import TemplateManager

from infra.event_bus import EventBus
from infra.llm_client import create_llm_client
from infra.config import ConfigManager
from infra.logger import get_logger, setup_logging

logger = get_logger()


class App:
    """主应用程序类，封装所有 GUI 界面逻辑。"""

    OUTPUT_FORMATS = ["Markdown", "Excel", "JSON"]
    ANALYSIS_DEPTHS = ["快速", "标准", "深度"]

    def __init__(self) -> None:
        # 初始化配置和日志
        setup_logging()
        self.config_manager = ConfigManager()
        self.config_manager.load()
        self.config = self.config_manager.get_config()

        # 初始化组件
        self.event_bus = EventBus()
        self.template_manager = TemplateManager()
        self.data_collector = DataCollector(event_bus=self.event_bus)

        # 创建 LLM 客户端
        model_config = ModelConfig(
            provider=self.config.model.provider,
            api_key=self.config.model.api_key,
            base_url=self.config.model.base_url,
            model_name=self.config.model.model_name,
        )
        self.llm_client = create_llm_client(model_config)

        # 创建分析引擎
        self.analysis_engine = AIAnalysisEngine(
            llm_client=self.llm_client,
            event_bus=self.event_bus,
            max_concurrency=self.config.analysis.max_concurrent,
        )

        # 创建报告生成器
        self.report_generator = ReportGenerator(event_bus=self.event_bus)

        # 创建 GUI
        self.root = tk.Tk()
        self.root.title("AI业务调研提效分析系统")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)

        # 状态变量
        self._input_file = tk.StringVar(value="")
        self._output_format = tk.StringVar(value=self.OUTPUT_FORMATS[0])
        self._analysis_depth = tk.StringVar(value=self.ANALYSIS_DEPTHS[1])
        self._progress_value = tk.DoubleVar(value=0.0)
        self._status_text = tk.StringVar(value="就绪")
        self._is_running = False

        # 构建界面
        self._build_ui()

        # 绑定快捷键
        self._bind_shortcuts()

        # 加载模板
        self.template_manager.load_all()

    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 文件选择区域
        file_frame = ttk.LabelFrame(main_frame, text="输入文件", padding=10)
        file_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(file_frame, text="选择调研数据文件:").pack(anchor=tk.W)
        ttk.Entry(file_frame, textvariable=self._input_file, width=60).pack(
            fill=tk.X, pady=(5, 5)
        )
        ttk.Button(
            file_frame, text="浏览文件", command=self._select_file
        ).pack(anchor=tk.W, pady=(0, 5))

        # 输出设置区域
        settings_frame = ttk.LabelFrame(main_frame, text="输出设置", padding=10)
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        # 输出格式
        format_frame = ttk.Frame(settings_frame)
        format_frame.pack(fill=tk.X)
        ttk.Label(format_frame, text="输出格式:").pack(side=tk.LEFT, padx=(0, 10))
        for fmt in self.OUTPUT_FORMATS:
            ttk.Radiobutton(
                format_frame,
                text=fmt,
                variable=self._output_format,
                value=fmt,
            ).pack(side=tk.LEFT, padx=5)

        # 分析深度
        depth_frame = ttk.Frame(settings_frame)
        depth_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(depth_frame, text="分析深度:").pack(side=tk.LEFT, padx=(0, 10))
        for depth in self.ANALYSIS_DEPTHS:
            ttk.Radiobutton(
                depth_frame,
                text=depth,
                variable=self._analysis_depth,
                value=depth,
            ).pack(side=tk.LEFT, padx=5)

        # 进度条区域
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(progress_frame, text="进度:").pack(side=tk.LEFT, padx=(0, 10))
        self.progress = ttk.Progressbar(
            progress_frame,
            variable=self._progress_value,
            maximum=100.0,
        )
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.progress_label = ttk.Label(progress_frame, text="0%")
        self.progress_label.pack(side=tk.LEFT, padx=(10, 0))

        # 状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(status_frame, text="状态:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(
            status_frame, textvariable=self._status_text, foreground="blue"
        ).pack(side=tk.LEFT)

        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(
            button_frame,
            text="提交分析",
            command=self._start_analysis,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            button_frame,
            text="取消",
            command=self._cancel_analysis,
            state=tk.DISABLED,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            button_frame,
            text="打开输出目录",
            command=self._open_output_dir,
        ).pack(side=tk.LEFT, padx=5)

        # 日志输出区域
        log_frame = ttk.LabelFrame(main_frame, text="运行日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(log_frame, height=10, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 绑定日志回调
        logger.addHandler(_LogHandler(self.log_text))

    def _bind_shortcuts(self) -> None:
        """绑定快捷键。"""
        self.root.bind("<Control-o>", lambda e: self._select_file())
        self.root.bind("<Control-s>", lambda e: self._start_analysis())
        self.root.bind("<Control-q>", lambda e: self._quit())

    def _select_file(self) -> None:
        """弹出文件选择对话框。"""
        filetypes = [
            ("调研数据文件", "*.md *.txt *.docx *.json"),
            ("Markdown 文件", "*.md"),
            ("文本文件", "*.txt"),
            ("Word 文档", "*.docx"),
            ("JSON 文件", "*.json"),
            ("所有文件", "*.*"),
        ]
        filepath = filedialog.askopenfilename(
            title="选择调研数据文件",
            filetypes=filetypes,
        )
        if filepath:
            self._input_file.set(filepath)
            self._status_text.set(f"已选择: {Path(filepath).name}")

    def _start_analysis(self) -> None:
        """启动分析任务（后台线程）。"""
        input_file = self._input_file.get().strip()
        if not input_file:
            messagebox.showwarning("提示", "请先选择输入文件")
            return

        if not Path(input_file).exists():
            messagebox.showerror("错误", f"文件不存在: {input_file}")
            return

        self._is_running = True
        self._progress_value.set(0.0)
        self._status_text.set("正在加载文件...")
        self._update_buttons(state="running")

        # 在后台线程执行分析
        thread = threading.Thread(
            target=self._run_analysis,
            args=(input_file,),
            daemon=True,
        )
        thread.start()

    def _update_progress(self, value: float) -> None:
        """线程安全地更新进度条。"""
        self.root.after(0, lambda v=value: self._set_progress(v))

    def _set_progress(self, value: float) -> None:
        """主线程更新进度条。"""
        self._progress_value.set(value)
        self.progress_label.configure(text=f"{int(value)}%")

    def _run_analysis(self, input_file: str) -> None:
        """在后台线程中执行完整分析流程。"""
        try:
            # 1. 解析文件
            self._update_progress(10.0)
            self._update_status("正在解析调研数据...")
            parsed_data = self.data_collector.parse_file(input_file)

            # 2. 验证数据
            self._update_progress(30.0)
            self._update_status("正在验证数据...")
            templates = self.template_manager.list_templates()
            if templates:
                validation = self.data_collector.validate(
                    parsed_data.get("answers", {}),
                    self.template_manager.get_template(templates[0]),
                )
                if not validation["valid"]:
                    self._update_status(f"数据验证失败: {'; '.join(validation['errors'])}")
                    self.root.after(0, lambda: messagebox.showwarning("验证失败", "; ".join(validation["errors"])))
                    return

            # 3. 构建分析数据
            self._progress_value.set(50.0)
            self._update_status("正在准备分析数据...")
            dept_data = {
                "department": Path(input_file).stem,
                "answers": parsed_data.get("answers", {}),
            }

            # 4. 执行 AI 分析
            self._update_status("正在进行 AI 分析（可能需要几分钟）...")
            result = asyncio.run(self.analysis_engine.analyze_department(dept_data))

            # 5. 生成报告
            self._progress_value.set(80.0)
            self._update_status("正在生成报告...")
            format_choice = self._output_format.get()
            output_dir = self.config.output.directory
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if format_choice == "Excel":
                output_path = self.report_generator.generate_excel(
                    result, f"{output_dir}/report_{timestamp}.xlsx"
                )
            elif format_choice == "JSON":
                output_path = self.report_generator.generate_json(
                    result, f"{output_dir}/report_{timestamp}.json"
                )
            else:
                # Markdown
                content = self.report_generator.generate_markdown(result)
                output_path = f"{output_dir}/report_{timestamp}.md"
                Path(output_path).write_text(content, encoding="utf-8")

            # 6. 完成
            self._progress_value.set(100.0)
            self._update_status("分析完成！")
            self.root.after(0, lambda: messagebox.showinfo(
                "完成",
                f"分析报告已生成:\n{output_path}",
            ))
            self._update_buttons(state="idle")

        except Exception as e:
            logger.error("分析失败: %s", e, exc_info=True)
            self.root.after(0, lambda: messagebox.showerror("错误", f"分析失败: {e}"))
            self._update_status("分析失败")
            self._update_buttons(state="idle")
            self._is_running = False

    def _cancel_analysis(self) -> None:
        """取消分析。"""
        self._is_running = False
        self._update_status("已取消")
        self._update_buttons(state="idle")

    def _open_output_dir(self) -> None:
        """跨平台打开输出文件目录。"""
        output_dir = self.config.output.directory
        if not Path(output_dir).exists():
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(output_dir)
        elif sys.platform == "darwin":
            subprocess.run(["open", output_dir])
        else:
            subprocess.run(["xdg-open", output_dir])

    def _quit(self) -> None:
        """退出程序。"""
        if self._is_running:
            self._cancel_analysis()
        self.root.quit()

    def _update_status(self, message: str) -> None:
        """更新状态文本（线程安全）。"""
        self.root.after(0, lambda: self._status_text.set(message))

    def _update_buttons(self, state: str = "idle") -> None:
        """更新按钮状态。"""
        if state == "running":
            self._is_running = True
            for btn in self.root.winfo_children():
                for child in btn.winfo_children():
                    if isinstance(child, ttk.Button):
                        text = child.cget("text")
                        if text == "提交分析":
                            child.configure(state=tk.DISABLED)
                        elif text == "取消":
                            child.configure(state=tk.NORMAL)
                        elif text == "打开输出目录":
                            child.configure(state=tk.DISABLED)

        elif state == "idle":
            self._is_running = False
            for btn in self.root.winfo_children():
                for child in btn.winfo_children():
                    if isinstance(child, ttk.Button):
                        text = child.cget("text")
                        if text == "提交分析":
                            child.configure(state=tk.NORMAL)
                        elif text == "取消":
                            child.configure(state=tk.DISABLED)
                        elif text == "打开输出目录":
                            child.configure(state=tk.NORMAL)


class _LogHandler(logging.Handler):
    """将日志输出到 GUI 的 Text 组件。"""

    def __init__(self, text_widget: tk.Text) -> None:
        super().__init__()
        self._text = text_widget

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._text.configure(state=tk.NORMAL)
            self._text.insert(tk.END, msg + "\n")
            self._text.configure(state=tk.DISABLED)
            self._text.see(tk.END)
        except Exception:
            self.handleError(record)


def main() -> None:
    """启动 GUI 应用程序。"""
    app = App()
    app.root.mainloop()


if __name__ == "__main__":
    main()
