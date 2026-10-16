"""业务调研模板定义 — QuestionType, Question, BusinessTemplate"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class QuestionType(str, Enum):
    """调研问题类型"""

    BUSINESS_PROCESS = "business_process"  # 业务环节
    PAIN_POINT = "pain_point"  # 痛点
    AI_OPPORTUNITY = "ai_opportunity"  # AI提效机会
    RESOURCE = "resource"  # 资源投入
    EXPECTATION = "expectation"  # 期望与目标


@dataclass
class Question:
    """单个调研问题"""

    id: str  # 问题编号，如 "Q1"
    text: str  # 问题文本
    question_type: QuestionType  # 问题类型
    required: bool = True  # 是否必填
    options: List[str] = field(default_factory=list)  # 选项（当类型为选择题时）
    description: Optional[str] = None  # 问题描述/提示


@dataclass
class BusinessTemplate:
    """业务调研模板"""

    title: str  # 模板标题
    description: str  # 模板描述
    questions: List[Question] = field(default_factory=list)  # 问题列表
    department_hint: Optional[str] = None  # 适用部门提示
