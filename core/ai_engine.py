"""AI 分析引擎 — AIAnalysisEngine，支持异步并发分析"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from domain.analysis import AnalysisResult, FullAnalysisReport, OpportunityPoint
from domain.template import BusinessTemplate
from infra.exceptions import AnalysisError, LLMError
from infra.event_bus import ANALYSIS_DONE, EventBus
from infra.llm_client import LLMClient
from infra.logger import get_logger

logger = get_logger()


class AIAnalysisEngine:
    """AI 分析引擎，支持异步并发分析。

    分析维度:
        - 重复性: 业务环节的重复操作识别
        - 数据密集度: 数据处理密集程度
        - 人力成本: 人力投入成本
        - AI成熟度: AI技术成熟度评估
        - 落地难度: 实施落地难度
        - 提效预期: 预期提效幅度
    """

    def __init__(self, llm_client: LLMClient, event_bus: Optional[EventBus] = None, max_concurrency: int = 3) -> None:
        """初始化分析引擎。

        Args:
            llm_client: LLM 客户端
            event_bus: 事件总线
            max_concurrency: 最大并发数（默认 3）
        """
        self._llm_client = llm_client
        self._event_bus = event_bus or EventBus()
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_concurrency = max_concurrency

    async def analyze_department(self, dept_data: Dict[str, Any]) -> AnalysisResult:
        """分析单个部门/业务环节的调研数据。

        Args:
            dept_data: 部门数据，包含 {"department": str, "answers": Dict[str, str], "template": BusinessTemplate}

        Returns:
            分析结果
        """
        async with self._semaphore:
            department = dept_data.get("department", "未知部门")
            template = dept_data.get("template")
            answers = dept_data.get("answers", {})

            prompt = self._build_analysis_prompt(department, template, answers)
            logger.info("开始分析部门: %s", department)

            try:
                response = await self._llm_client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=4096,
                )
            except LLMError as e:
                logger.error("LLM 调用失败: %s", e)
                raise AnalysisError(f"分析失败: {e}")

            result = self._parse_llm_response(response, department)
            logger.info("部门 %s 分析完成, 发现 %d 个机会点", department, len(result.opportunities))
            self._event_bus.publish(ANALYSIS_DONE, {"department": department, "result": result})
            return result

    async def analyze_all(self, all_data: List[Dict[str, Any]]) -> FullAnalysisReport:
        """并发分析所有部门的调研数据。

        Args:
            all_data: 所有部门数据列表，每个元素为 {"department": str, "answers": Dict, "template": BusinessTemplate}

        Returns:
            完整分析报告
        """
        tasks = [self.analyze_department(data) for data in all_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 分离成功和失败结果
        success_results: list[AnalysisResult] = []
        errors: list[str] = []

        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
                logger.error("分析失败: %s", result)
            elif isinstance(result, AnalysisResult):
                success_results.append(result)

        # 汇总统计
        total_opportunities = sum(len(r.opportunities) for r in success_results)
        high_priority = sum(
            sum(1 for op in r.opportunities if op.priority >= 3)
            for r in success_results
        )

        # 生成总体总结
        overall_summary = self._generate_overall_summary(success_results, errors)

        report = FullAnalysisReport(
            departments=success_results,
            total_opportunities=total_opportunities,
            high_priority_opportunities=high_priority,
            overall_summary=overall_summary,
        )

        logger.info("全部门分析完成, 共 %d 个部门, %d 个机会点", len(success_results), total_opportunities)
        return report

    def _build_analysis_prompt(
        self, department: str, template: Optional[BusinessTemplate], answers: Dict[str, str]
    ) -> str:
        """构建 LLM 分析 prompt。

        分析维度:
            - 重复性: 业务环节的重复操作识别
            - 数据密集度: 数据处理密集程度
            - 人力成本: 人力投入成本
            - AI成熟度: AI技术成熟度评估
            - 落地难度: 实施落地难度
            - 提效预期: 预期提效幅度
        """
        prompt = f"""你是一位资深的AI咨询顾问，请分析以下{department}的调研数据，识别AI提效机会。

## 调研数据
"""
        if template:
            for question in template.questions:
                answer = answers.get(question.id, "未回答")
                prompt += f"\n### {question.id} [{question.question_type.value}]\n{question.text}\n答案: {answer}"
        else:
            for qid, answer in answers.items():
                prompt += f"\n### {qid}\n答案: {answer}"

        prompt += """

## 分析要求
请从以下维度进行分析，并以 JSON 格式返回结果：

1. **重复性分析**: 识别部门中重复性高的业务环节
2. **数据密集度**: 评估数据处理密集程度
3. **人力成本**: 估算各环节人力投入
4. **AI成熟度**: 评估AI技术在该环节的成熟度
5. **落地难度**: 分析实施落地的难度
6. **提效预期**: 预期提效幅度

## 输出格式
请严格按照以下 JSON 格式返回（不要包含其他内容）:

{
  "pain_points": ["痛点1", "痛点2"],
  "opportunities": [
    {
      "department": "部门名",
      "process": "业务环节",
      "current_process": "当前流程描述",
      "ai_suggestion": "AI建议方案",
      "expected_efficiency_gain": "预期提效幅度",
      "difficulty": "低/中/高",
      "priority": 1-5,
      "expected_roi": "预期ROI",
      "timeline": "预计实施周期"
    }
  ],
  "summary": "分析总结",
  "confidence": 0.85
}

注意:
- pain_points 是痛点列表
- opportunities 是AI提效机会点列表，priority 1-5 表示优先级（5最高）
- difficulty 只能是 "低"、"中"、"高"
- confidence 是 0.0-1.0 的置信度
- 请确保返回的是有效的 JSON
"""
        return prompt

    def _parse_llm_response(self, response: str, department: str) -> AnalysisResult:
        """解析 LLM 返回的 JSON 响应。

        Args:
            response: LLM 响应文本
            department: 部门名称

        Returns:
            AnalysisResult 对象
        """
        try:
            # 尝试提取 JSON
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                json_str = json_match.group()
            else:
                json_str = response

            data = json.loads(json_str)

            # 构建机会点
            opportunities: list[OpportunityPoint] = []
            for op_data in data.get("opportunities", []):
                opportunities.append(
                    OpportunityPoint(
                        department=op_data.get("department", department),
                        process=op_data.get("process", ""),
                        current_process=op_data.get("current_process", ""),
                        ai_suggestion=op_data.get("ai_suggestion", ""),
                        expected_efficiency_gain=op_data.get("expected_efficiency_gain", ""),
                        difficulty=op_data.get("difficulty", "中"),
                        priority=op_data.get("priority", 0),
                        expected_roi=op_data.get("expected_roi"),
                        timeline=op_data.get("timeline"),
                    )
                )

            return AnalysisResult(
                department=department,
                pain_points=data.get("pain_points", []),
                opportunities=opportunities,
                summary=data.get("summary", ""),
                confidence=data.get("confidence", 0.0),
                raw_insights=data.get("raw_insights"),
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("解析 LLM 响应失败: %s", e)
            raise AnalysisError(f"解析分析结果失败: {e}")

    def _generate_overall_summary(self, results: List[AnalysisResult], errors: List[str]) -> str:
        """生成总体分析总结。

        Args:
            results: 成功的分析结果
            errors: 错误信息

        Returns:
            总体总结文本
        """
        if not results:
            return "所有部门分析失败，请检查配置和 API 可用性。"

        total = len(results)
        total_opp = sum(len(r.opportunities) for r in results)
        avg_confidence = sum(r.confidence for r in results) / len(results)

        summary_parts = [f"本次对 {total} 个部门进行了 AI 提效分析分析，共识别出 {total_opp} 个提效机会点。"]

        # 按部门汇总
        for r in results:
            opp_count = len(r.opportunities)
            summary_parts.append(
                f"- {r.department}: 发现 {opp_count} 个提效机会，置信度 {r.confidence:.0%}。{r.summary}"
            )

        if errors:
            summary_parts.append(f"\n分析失败: {'; '.join(errors)}")

        return "\n".join(summary_parts)
