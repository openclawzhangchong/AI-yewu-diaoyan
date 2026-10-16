"""AI分析结果定义 — AnalysisResult, OpportunityPoint, FullAnalysisReport"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class OpportunityPoint:
    """AI提效机会点"""

    department: str  # 所属部门
    process: str  # 业务环节
    current_process: str  # 当前流程描述
    ai_suggestion: str  # AI建议方案
    expected_efficiency_gain: str  # 预期提效幅度
    difficulty: str  # 实施难度（低/中/高）
    priority: int = 0  # 优先级
    expected_roi: Optional[str] = None  # 预期ROI
    timeline: Optional[str] = None  # 预计实施周期


@dataclass
class AnalysisResult:
    """单个部门/业务环节的AI分析结果"""

    department: str  # 部门名称
    process: str  # 业务环节
    pain_points: List[str] = field(default_factory=list)  # 识别到的痛点
    opportunities: List[OpportunityPoint] = field(default_factory=list)  # AI提效机会
    summary: str = ""  # 分析总结
    confidence: float = 0.0  # 分析置信度 (0.0 - 1.0)
    raw_insights: Optional[List[str]] = None  # 原始分析要点


@dataclass
class FullAnalysisReport:
    """完整分析报告"""

    departments: List[AnalysisResult] = field(default_factory=list)  # 各部门分析结果
    total_opportunities: int = 0  # 总机会点数
    high_priority_opportunities: int = 0  # 高优先级机会点数量
    overall_summary: str = ""  # 总体总结
    generated_at: Optional[str] = None  # 生成时间戳

