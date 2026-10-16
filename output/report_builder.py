"""报告构建 — ReportBuilder，调用 core 层 ReportGenerator 产出 md / xlsx / json 报告"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from core.report_generator import ReportGenerator
from domain.analysis import FullAnalysisReport
from infra.event_bus import REPORT_GENERATED, EventBus
from infra.exceptions import AppError, ReportError
from infra.logger import get_logger

logger = get_logger()

# 支持格式 -> 文件扩展名
_FORMAT_EXTENSIONS = {
    "md": ".md",
    "markdown": ".md",
    "xlsx": ".xlsx",
    "excel": ".xlsx",
    "json": ".json",
}


class ReportBuilder:
    """报告构建器。

    内部调用 core 层的 :class:`ReportGenerator`，将
    :class:`FullAnalysisReport` 写盘为 md / xlsx / json 三种格式之一，
    生成完成后在事件总线上发布 ``report.generated`` 事件。
    """

    def __init__(
        self,
        templates_dir: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
        project_root: Optional[Path] = None,
    ) -> None:
        """初始化报告构建器。

        Args:
            templates_dir: Jinja2 报告模板目录，缺省时取项目根目录下 templates/
            event_bus: 事件总线，缺省时使用独立实例
            project_root: 项目根目录，缺省时取本文件上两级目录
        """
        root = project_root or Path(__file__).resolve().parent.parent
        self._templates_dir = templates_dir or str(root / "templates")
        self._event_bus = event_bus or EventBus()
        self._generator = ReportGenerator(
            templates_dir=self._templates_dir,
            event_bus=self._event_bus,
        )

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------
    def build(
        self,
        analysis_report: FullAnalysisReport,
        output_format: str,
        output_dir: Union[str, Path],
    ) -> Path:
        """构建并写出报告文件。

        Args:
            analysis_report: 完整的分析报告
            output_format: 输出格式，支持 ``md`` / ``xlsx`` / ``json``
                （大小写不敏感，别名 markdown / excel 同样可用）
            output_dir: 输出目录（不存在时自动创建）

        Returns:
            生成的报告文件的绝对路径

        Raises:
            ReportError: 格式不支持、报告无效、生成或写盘失败等
        """
        fmt = (output_format or "").strip().lower()
        if fmt not in _FORMAT_EXTENSIONS:
            supported = ", ".join(sorted(_FORMAT_EXTENSIONS))
            raise ReportError(
                f"不支持的输出格式: {output_format!r}，支持: {supported}",
                code="REPORT_FORMAT_ERROR",
            )

        if not isinstance(analysis_report, FullAnalysisReport):
            raise ReportError(
                f"build() 需要 FullAnalysisReport 实例，收到 {type(analysis_report).__name__}",
                code="REPORT_INVALID_INPUT",
            )

        out_dir = Path(output_dir)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ReportError(f"无法创建输出目录 {out_dir}: {e}", code="REPORT_OUTPUT_DIR_ERROR") from e

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"report_{ts}"
        filepath = out_dir / (stem + _FORMAT_EXTENSIONS[fmt])

        try:
            if fmt in ("md", "markdown"):
                content = self._generator.generate_markdown(analysis_report)
                filepath.write_text(content, encoding="utf-8")
            elif fmt in ("xlsx", "excel"):
                self._generator.generate_excel(analysis_report, str(filepath))
            else:  # json
                self._generator.generate_json(analysis_report, str(filepath))
        except ReportError:
            raise
        except (OSError, AppError) as e:
            raise ReportError(f"报告生成失败: {e}", code="REPORT_GENERATION_FAILED") from e
        except Exception as e:  # 兜底：模板渲染、序列化等异常统一归口为 ReportError
            raise ReportError(f"报告生成失败: {e}", code="REPORT_GENERATION_FAILED") from e

        logger.info("报告已生成: %s (格式: %s)", filepath, fmt)

        # 发布 report.generated 事件
        self._event_bus.publish(
            REPORT_GENERATED,
            {
                "filepath": str(filepath),
                "output_path": str(filepath),
                "format": fmt,
                "total_opportunities": analysis_report.total_opportunities,
                "high_priority_opportunities": analysis_report.high_priority_opportunities,
                "generated_at": filepath.stat().st_mtime if filepath.exists() else None,
            },
        )
        return filepath

    @property
    def generator(self) -> ReportGenerator:
        """暴露内部 ReportGenerator，便于高级用法。"""
        return self._generator

    @property
    def event_bus(self) -> EventBus:
        """暴露内部事件总线。"""
        return self._event_bus
