"""模板管理 — TemplateManager，支持自动扫描 templates/ 目录注册模板"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List, Optional

from domain.template import BusinessTemplate, Question, QuestionType
from infra.exceptions import TemplateError
from infra.logger import get_logger

logger = get_logger()


def _default_template_dir() -> Path:
    """定位 templates/ 目录：CWD > PyInstaller 解包目录 > 源码相对位置。"""
    cwd_templates = Path("templates")
    if cwd_templates.is_dir():
        return cwd_templates
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and (Path(meipass) / "templates").is_dir():
        return Path(meipass) / "templates"
    return Path(__file__).resolve().parent.parent / "templates"


def _parse_template_from_markdown(content: str, source: str) -> BusinessTemplate:
    """从 Markdown 内容解析模板定义。

    格式约定:
        # 模板标题
        ## 描述
        ### Q1 问题文本
        - 类型: pain_point
        - 选项: A, B, C
    """
    lines = content.strip().splitlines()
    title = ""
    description = ""
    questions: list[Question] = []

    current_question: dict = {}
    current_options: list[str] = []
    question_type: Optional[QuestionType] = None

    def _resolve_type(raw: str) -> Optional[QuestionType]:
        mapping = {
            "business_process": QuestionType.BUSINESS_PROCESS,
            "pain_point": QuestionType.PAIN_POINT,
            "ai_opportunity": QuestionType.AI_OPPORTUNITY,
            "resource": QuestionType.RESOURCE,
            "expectation": QuestionType.EXPECTATION,
        }
        return mapping.get(raw.strip().lower())

    def _flush_question() -> None:
        nonlocal current_question, current_options, question_type
        if current_question.get("text") and question_type:
            questions.append(
                Question(
                    id=current_question.get("id", f"Q{len(questions) + 1}"),
                    text=current_question["text"],
                    question_type=question_type,
                    required=current_question.get("required", True),
                    options=list(current_options),
                    description=current_question.get("description"),
                )
            )
        current_question = {}
        current_options = []
        question_type = None

    for line in lines:
        stripped = line.strip()

        # 标题
        m_title = re.match(r"^#\s+(.+)$", stripped)
        if m_title and not title:
            title = m_title.group(1)
            continue

        # 描述
        m_desc = re.match(r"^##\s+(.+)$", stripped)
        if m_desc and not description:
            description = m_desc.group(1)
            continue

        # 问题编号
        m_qid = re.match(r"^###?\s+(Q\d+)\s+(.+)$", stripped)
        if m_qid:
            _flush_question()
            current_question = {"id": m_qid.group(1), "text": m_qid.group(2)}
            continue

        # 问题类型
        m_type = re.match(r"^-\s*类型:\s*(.+)$", stripped)
        if m_type:
            question_type = _resolve_type(m_type.group(1))
            continue

        # 选项
        m_opt = re.match(r"^-\s*选项:\s*(.+)$", stripped)
        if m_opt:
            current_options = [o.strip() for o in m_opt.group(1).split(",")]
            continue

        # 是否必填
        m_req = re.match(r"^-\s*必填:\s*(.+)$", stripped)
        if m_req:
            current_question["required"] = m_req.group(1).strip().lower() == "true"
            continue

        # 描述
        m_desc_q = re.match(r"^-\s*描述:\s*(.+)$", stripped)
        if m_desc_q:
            current_question["description"] = m_desc_q.group(1)
            continue

    _flush_question()

    if not title:
        title = source

    return BusinessTemplate(title=title, description=description, questions=questions)


def _parse_template_from_json(content: str, source: str) -> BusinessTemplate:
    """从 JSON 内容解析模板定义。"""
    data = json.loads(content)

    questions: list[Question] = []
    for q in data.get("questions", []):
        questions.append(
            Question(
                id=q["id"],
                text=q["text"],
                question_type=QuestionType(q["type"]),
                required=q.get("required", True),
                options=q.get("options", []),
                description=q.get("description"),
            )
        )

    return BusinessTemplate(
        title=data.get("title", source),
        description=data.get("description", ""),
        questions=questions,
        department_hint=data.get("department_hint"),
    )


class TemplateManager:
    """模板管理器，支持自动扫描 templates/ 目录注册模板。

    支持的文件格式:
        - Markdown (.md): 使用约定的标题/问题格式
        - JSON (.json): 使用 JSON schema
        - TXT (.txt): 使用 Markdown 格式解析
    """

    def __init__(self, template_dir: Optional[str] = None) -> None:
        self._templates: dict[str, BusinessTemplate] = {}
        self._template_dir = Path(template_dir) if template_dir else _default_template_dir()

    def register(self, template: BusinessTemplate) -> None:
        """注册一个模板，以 title 作为 key。

        Args:
            template: 要注册的模板
        """
        if not template.title:
            raise TemplateError("模板标题不能为空")
        if not template.questions:
            raise TemplateError(f"模板 '{template.title}' 没有定义问题")
        self._templates[template.title] = template
        logger.info("已注册模板: %s", template.title)

    def load_all(self) -> list[BusinessTemplate]:
        """加载 templates/ 目录下所有模板文件。

        Returns:
            已加载的模板列表
        """
        templates = self.load_all_from_directory(self._template_dir)
        return templates

    def load_all_from_directory(self, directory: Path) -> list[BusinessTemplate]:
        """从指定目录加载所有模板文件。

        Args:
            directory: 模板目录

        Returns:
            已加载的模板列表
        """
        templates: list[BusinessTemplate] = []

        if not directory.is_dir():
            logger.warning("模板目录不存在: %s", directory)
            return templates

        for file_path in sorted(directory.glob("**/*")):
            if not file_path.is_file():
                continue

            ext = file_path.suffix.lower()
            if ext not in (".md", ".json", ".txt"):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                if not content.strip():
                    continue

                if ext == ".json":
                    tpl = _parse_template_from_json(content, str(file_path))
                else:
                    tpl = _parse_template_from_markdown(content, str(file_path))

                self.register(tpl)
                templates.append(tpl)
                logger.info("已加载模板文件: %s -> %s", file_path.name, tpl.title)

            except (TemplateError, json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error("加载模板失败 %s: %s", file_path.name, e)

        return templates

    def get_by_department(self, department: str) -> list[BusinessTemplate]:
        """根据部门名称获取匹配的模板。

        匹配规则:
            1. department_hint 完全匹配
            2. 模板标题包含部门名称
            3. 模板描述包含部门名称

        Args:
            department: 部门名称

        Returns:
            匹配的模板列表
        """
        results: list[BusinessTemplate] = []

        for tpl in self._templates.values():
            if tpl.department_hint and tpl.department_hint.lower() == department.lower():
                results.append(tpl)
                continue

            if department.lower() in tpl.title.lower():
                results.append(tpl)
                continue

            if tpl.description and department.lower() in tpl.description.lower():
                results.append(tpl)
                continue

        return results

    def discover_templates(self) -> list[BusinessTemplate]:
        """发现并注册 templates/ 目录下的所有模板。

        Returns:
            已发现的模板列表
        """
        templates = self.load_all()
        logger.info("发现 %d 个模板", len(templates))
        return templates

    def get_template(self, title: str) -> Optional[BusinessTemplate]:
        """根据标题获取模板。

        Args:
            title: 模板标题

        Returns:
            模板对象，不存在则返回 None
        """
        return self._templates.get(title)

    def list_templates(self) -> list[str]:
        """列出所有已注册模板的标题。

        Returns:
            模板标题列表
        """
        return list(self._templates.keys())

    def remove_template(self, title: str) -> bool:
        """移除模板。

        Args:
            title: 模板标题

        Returns:
            是否成功移除
        """
        if title in self._templates:
            del self._templates[title]
            logger.info("已移除模板: %s", title)
            return True
        return False
