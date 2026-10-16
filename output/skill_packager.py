"""Skill 打包 — SkillPackager，将项目产物打包为可分发的 Skill 目录"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from infra.event_bus import PACK_DONE, EventBus
from infra.exceptions import AppError, PackError
from infra.logger import get_logger

logger = get_logger()

# 项目级元信息
_SKILL_NAME = "ai-efficiency-analyzer"
_SKILL_VERSION = "0.1.0"
_SKILL_AUTHOR = "AI业务调研提效系统"
_SKILL_CATEGORY = "business-analysis"
_SKILL_ENTRY_POINT = "entry.main:main"

# 完整模式下需要一并导出的 Python 代码目录
_CODE_DIRS = ("domain", "core", "infra", "entry", "output")
_DEPENDENCIES_FILE = "requirements.txt"


class SkillPackager:
    """Skill 打包器。

    支持两种模式:
        - 轻量模式 (:meth:`pack_light`): 导出 SKILL.md + manifest.json + prompts/ + 模板 JSON
        - 完整模式 (:meth:`pack_full`): 轻量模式 + Python 代码 + 依赖清单

    打包完成后在事件总线上发布 ``pack.done`` 事件。
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        """初始化打包器。

        Args:
            project_root: 项目根目录，缺省时取本文件上两级目录
            event_bus: 事件总线，缺省时使用独立实例
        """
        self._project_root = (project_root or Path(__file__).resolve().parent.parent).resolve()
        self._event_bus = event_bus or EventBus()

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------
    def pack_light(self, output_dir: Union[str, Path]) -> Path:
        """轻量模式打包。

        导出内容: SKILL.md + manifest.json + prompts/ + 模板 JSON。

        Args:
            output_dir: 目标 Skill 目录（不存在时自动创建）

        Returns:
            打包产物的目录路径

        Raises:
            PackError: 打包或验证失败
        """
        skill_dir = self._prepare_output_dir(output_dir)
        try:
            self.generate_skill_md(skill_dir)
            self.generate_manifest(skill_dir)
            self._copy_prompts(skill_dir)
            self._copy_template_jsons(skill_dir)

            self.validate(skill_dir)
        except PackError:
            raise
        except AppError as e:
            raise PackError(f"轻量打包失败: {e.message}", code=e.code) from e
        except OSError as e:
            raise PackError(f"轻量打包失败（文件系统错误）: {e}", code="PACK_IO_ERROR") from e

        self._publish_pack_done(skill_dir, mode="light")
        return skill_dir

    def pack_full(self, output_dir: Union[str, Path]) -> Path:
        """完整模式打包。

        在轻量模式基础上，额外导出 Python 代码目录与依赖清单。

        Args:
            output_dir: 目标 Skill 目录（不存在时自动创建）

        Returns:
            打包产物的目录路径

        Raises:
            PackError: 打包或验证失败
        """
        skill_dir = self._prepare_output_dir(output_dir)
        try:
            # 轻量部分
            self.generate_skill_md(skill_dir)
            self.generate_manifest(skill_dir)
            self._copy_prompts(skill_dir)
            self._copy_template_jsons(skill_dir)
            # 完整部分
            self._copy_python_code(skill_dir)
            self._copy_dependencies(skill_dir)

            self.validate(skill_dir)
        except PackError:
            raise
        except AppError as e:
            raise PackError(f"完整打包失败: {e.message}", code=e.code) from e
        except OSError as e:
            raise PackError(f"完整打包失败（文件系统错误）: {e}", code="PACK_IO_ERROR") from e

        self._publish_pack_done(skill_dir, mode="full")
        return skill_dir

    def generate_skill_md(self, skill_dir: Union[str, Path]) -> Path:
        """生成 SKILL.md。

        包含: 描述、何时使用、触发条件、功能、输入、输出、依赖、入口、版本。

        Args:
            skill_dir: Skill 目录，文件写入其中的 SKILL.md

        Returns:
            生成的 SKILL.md 路径

        Raises:
            PackError: 生成失败
        """
        skill_dir = Path(skill_dir)
        skill_dir.mkdir(parents=True, exist_ok=True)
        try:
            content = self._build_skill_md_content()
            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        except OSError as e:
            raise PackError(f"SKILL.md 生成失败: {e}", code="PACK_IO_ERROR") from e
        return skill_dir / "SKILL.md"

    def generate_manifest(self, skill_dir: Union[str, Path]) -> Path:
        """生成 manifest.json。

        字段: name / version / author / category / entry_point / dependencies。

        Args:
            skill_dir: Skill 目录，文件写入其中的 manifest.json

        Returns:
            生成的 manifest.json 路径

        Raises:
            PackError: 生成失败
        """
        skill_dir = Path(skill_dir)
        skill_dir.mkdir(parents=True, exist_ok=True)
        try:
            manifest = {
                "name": _SKILL_NAME,
                "version": _SKILL_VERSION,
                "author": _SKILL_AUTHOR,
                "category": _SKILL_CATEGORY,
                "entry_point": _SKILL_ENTRY_POINT,
                "dependencies": self._load_requirements(),
                "generated_at": datetime.now().isoformat(),
            }
            (skill_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            raise PackError(f"manifest.json 生成失败: {e}", code="PACK_IO_ERROR") from e
        return skill_dir / "manifest.json"

    def validate(self, skill_dir: Union[str, Path]) -> Dict[str, Any]:
        """验证打包产物完整性。

        检查:
            - SKILL.md 存在且非空
            - manifest.json 存在且为合法 JSON，并包含必需字段
            - templates/*.json 均能解析为合法 JSON

        Args:
            skill_dir: 待验证的 Skill 目录

        Returns:
            验证报告: ``{"valid": bool, "errors": [...], "files_checked": int}``

        Raises:
            PackError: 目录不存在或验证未通过（错误详情在报告中）
        """
        skill_dir = Path(skill_dir)
        if not skill_dir.is_dir():
            raise PackError(f"Skill 目录不存在: {skill_dir}", code="PACK_VALIDATE_FAILED")

        errors: List[str] = []
        files_checked = 0

        # 1) SKILL.md
        skill_md = skill_dir / "SKILL.md"
        files_checked += 1
        if not skill_md.is_file():
            errors.append("SKILL.md 缺失")
        elif skill_md.stat().st_size == 0:
            errors.append("SKILL.md 为空文件")

        # 2) manifest.json
        manifest_file = skill_dir / "manifest.json"
        files_checked += 1
        if not manifest_file.is_file():
            errors.append("manifest.json 缺失")
        else:
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"manifest.json 不是合法 JSON: {e}")
                manifest = None
            if manifest is not None:
                required_keys = {"name", "version", "author", "category", "entry_point", "dependencies"}
                missing = required_keys - set(manifest)
                if missing:
                    errors.append(f"manifest.json 缺少字段: {sorted(missing)}")

        # 3) 模板 JSON 合法性
        for tpl in self._iter_template_jsons(skill_dir / "templates"):
            files_checked += 1
            try:
                json.loads(tpl.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"模板 JSON 解析失败 {tpl.name}: {e}")

        report = {"valid": not errors, "errors": errors, "files_checked": files_checked}
        if errors:
            logger.warning("Skill 打包验证未通过: %s", "; ".join(errors))
            raise PackError(
                f"打包验证未通过: {'; '.join(errors)}",
                code="PACK_VALIDATE_FAILED",
            )
        logger.info("Skill 打包验证通过: %s (检查 %d 个文件)", skill_dir, files_checked)
        return report

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    def _prepare_output_dir(self, output_dir: Union[str, Path]) -> Path:
        target = Path(output_dir).resolve()
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise PackError(f"无法创建打包目录 {target}: {e}", code="PACK_IO_ERROR") from e
        return target

    def _copy_prompts(self, skill_dir: Path) -> None:
        """导出 prompts/ 目录（不存在时创建空目录，保证结构完整）。"""
        src = self._project_root / "prompts"
        dst = skill_dir / "prompts"
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            dst.mkdir(parents=True, exist_ok=True)
            (dst / ".gitkeep").write_text("", encoding="utf-8")

    def _copy_template_jsons(self, skill_dir: Path) -> None:
        """导出 templates/ 下的 JSON 模板（没有则保留空目录）。"""
        src = self._project_root / "templates"
        dst = skill_dir / "templates"
        dst.mkdir(parents=True, exist_ok=True)
        jsons = self._iter_template_jsons(src) if src.is_dir() else []
        for f in jsons:
            target = dst / f.name
            shutil.copy2(f, target)
        if not jsons:
            (dst / ".gitkeep").write_text("", encoding="utf-8")

    def _copy_python_code(self, skill_dir: Path) -> None:
        """导出 Python 代码目录（domain / core / infra / entry）。"""
        code_root = skill_dir / "code"
        for name in _CODE_DIRS:
            src = self._project_root / name
            if not src.is_dir():
                logger.warning("完整打包: 代码目录缺失 %s，跳过", src)
                continue
            dst = code_root / name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
            )

    def _copy_dependencies(self, skill_dir: Path) -> None:
        """导出依赖清单 requirements.txt。"""
        src = self._project_root / _DEPENDENCIES_FILE
        dst = skill_dir / _DEPENDENCIES_FILE
        if src.is_file():
            shutil.copy2(src, dst)
        else:
            (dst).write_text("", encoding="utf-8")

    def _iter_template_jsons(self, dir_path: Path) -> List[Path]:
        """收集目录下所有 *.json 模板文件。"""
        if not dir_path.is_dir():
            return []
        return sorted(dir_path.glob("*.json"))

    def _load_requirements(self) -> List[str]:
        """解析 requirements.txt 为依赖清单（manifest 用）。"""
        req_file = self._project_root / _DEPENDENCIES_FILE
        if not req_file.is_file():
            return []
        deps: List[str] = []
        for line in req_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 只保留 “包名 约束” 部分，去掉行内注释
            line = re.split(r"\s+", line, maxsplit=1)[0]
            deps.append(line)
        return deps

    def _build_skill_md_content(self) -> str:
        deps = "、".join(self._load_requirements()) or "（见 requirements.txt）"
        return f"""# {_SKILL_NAME}

## 描述
AI业务调研提效分析系统。基于业务调研数据，利用 LLM 识别各部门痛点与 AI 提效机会点，
自动生成多格式分析报告（Markdown / Excel / JSON），并可打包为可分发的 Skill。

## 何时使用
- 需要对组织内多个部门开展 AI 落地机会调研，并形成结构化结论时
- 已有调研数据（问答、访谈记录），希望快速产出痛点清单与提效建议时
- 需要向管理层交付可视化分析报告（Excel/JSON 便于下游消费）时

## 触发条件
- 用户提及 "AI 调研"、"提效分析"、"业务机会点"、"部门痛点" 等关键词
- 提供了调研模板（templates/）与对应调研答案，需要产出分析报告
- 需要打包 / 分发本 Skill（light 或 full 模式）

## 功能
- 模板管理：扫描 templates/ 目录，支持 Markdown / JSON 调研模板
- 数据采集：收集、缓存各部门调研答案
- AI 分析：调用 LLM 识别痛点与 AI 提效机会点，输出置信度与优先级
- 报告构建：md / xlsx / json 三种格式，生成后发布 report.generated 事件
- Skill 打包：light（SKILL.md + manifest + prompts + 模板）/ full（+ 代码 + 依赖）

## 输入
- 调研模板（Markdown / JSON），位于 templates/ 目录
- 各业务环节的调研答案（文本）
- 输出格式（md / xlsx / json）与输出目录

## 输出
- 分析报告文件（.md / .xlsx / .json），含执行摘要、部门明细、机会点、综合建议
- 打包产物目录（SKILL.md、manifest.json、prompts/、templates/*.json、可选 code/ 与 requirements.txt）
- 事件：analysis.done / report.generated / pack.done

## 依赖
{deps}

## 入口
```python
{_SKILL_ENTRY_POINT}
# 或 CLI / GUI：
python -m entry.main
```

## 版本
{_SKILL_VERSION}（{_SKILL_AUTHOR}）
"""

    def _publish_pack_done(self, skill_dir: Path, mode: str) -> None:
        self._event_bus.publish(
            PACK_DONE,
            {
                "skill_dir": str(skill_dir),
                "mode": mode,
                "name": _SKILL_NAME,
                "version": _SKILL_VERSION,
            },
        )
