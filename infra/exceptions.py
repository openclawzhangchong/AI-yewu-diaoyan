"""自定义异常层次 — AppError 基类及业务异常"""

from __future__ import annotations


class AppError(Exception):
    """所有自定义异常的基类"""

    def __init__(self, message: str = "应用错误", code: str = "APP_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class ConfigError(AppError):
    """配置异常"""

    def __init__(self, message: str = "配置错误", code: str = "CONFIG_ERROR"):
        super().__init__(message, code)


class TemplateError(AppError):
    """模板异常"""

    def __init__(self, message: str = "模板错误", code: str = "TEMPLATE_ERROR"):
        super().__init__(message, code)


class CollectionError(AppError):
    """调研数据收集异常"""

    def __init__(self, message: str = "数据收集错误", code: str = "COLLECTION_ERROR"):
        super().__init__(message, code)


class AnalysisError(AppError):
    """分析错误"""

    def __init__(self, message: str = "分析错误", code: str = "ANALYSIS_ERROR"):
        super().__init__(message, code)


class LLMError(AppError):
    """LLM 调用异常"""

    def __init__(self, message: str = "LLM 调用错误", code: str = "LLM_ERROR"):
        super().__init__(message, code)


class ReportError(AppError):
    """报告生成异常"""

    def __init__(self, message: str = "报告生成错误", code: str = "REPORT_ERROR"):
        super().__init__(message, code)


class PackError(AppError):
    """打包异常"""

    def __init__(self, message: str = "打包错误", code: str = "PACK_ERROR"):
        super().__init__(message, code)
