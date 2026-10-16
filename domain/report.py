"""报告结构定义 — ReportSection, DepartmentReport"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ReportSection:
    """报告章节"""

    title: str  # 章节标题
    content: str  # 章节正文
    subsections: List[ReportSection] = field(default_factory=list)  # 子章节


@dataclass
class DepartmentReport:
    """部门报告"""

    department: str  # 部门名称
    executive_summary: str = ""  # 执行摘要
    pain_points: List[str] = field(default_factory=list)  # 痛点列表
    opportunities: List[str] = field(default_factory=list)  # AI提效机会列表
    recommendation: str = ""  # 建议方案
    sections: List[ReportSection] = field(default_factory=list)  # 报告章节

