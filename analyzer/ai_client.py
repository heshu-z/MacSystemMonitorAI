"""
ai_client — DeepSeek API integration for AI-powered system analysis.

Sends recent monitoring data to the DeepSeek model and returns
structured analysis including system status, performance bottlenecks,
and optimization recommendations.
"""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from analyzer.ai_analyzer import SystemStatus, analyze

# ------------------------------------------------------------------
# DeepSeek API configuration
# ------------------------------------------------------------------
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

_SYSTEM_PROMPT = """\
你是一位资深的 macOS 系统性能分析专家。用户会提供一份包含 CPU、内存、磁盘、网络指标统计数据的 JSON，你需要据此输出中文分析报告。

请严格按以下 Markdown 格式输出：

## 系统状态分析
- 用 2-3 句话总结当前系统整体健康状况
- 指出正常和异常的指标

## 性能瓶颈分析
- 识别当前系统的性能瓶颈（CPU / 内存 / 磁盘 I/O / 网络）
- 引用数据中的具体数值来说明依据
- 如果没有明显瓶颈，说明系统资源充裕

## 优化建议
- 给出 3-5 条可操作的优化建议
- 按优先级排列
- 每条建议包含具体步骤或命令

要求：
- 语言简洁专业
- 数值引用准确
- 如果所有指标正常，不要强行编造问题
"""


def _build_prompt(status: SystemStatus) -> str:
    """Build a JSON payload describing the system state for the model."""
    data = {
        "data_points": status.data_points,
        "cpu": {
            "severity": status.cpu.severity,
            "summary": status.cpu.summary,
            "details": status.cpu.details,
            "stats": status.cpu.stats,
        },
        "memory": {
            "severity": status.memory.severity,
            "summary": status.memory.summary,
            "details": status.memory.details,
            "stats": status.memory.stats,
        },
        "disk": {
            "severity": status.disk.severity,
            "summary": status.disk.summary,
            "details": status.disk.details,
            "stats": status.disk.stats,
        },
        "network": {
            "severity": status.network.severity,
            "summary": status.network.summary,
            "details": status.network.details,
            "stats": status.network.stats,
        },
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def get_ai_analysis(
    duration_minutes: int = 30,
    api_key: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Run local analysis, send results to DeepSeek, and return the AI report.

    Args:
        duration_minutes: History window in minutes.
        api_key: DeepSeek API key. If ``None``, reads ``DEEPSEEK_API_KEY``
            from the environment.
        db_path: Optional SQLite database path.

    Returns:
        dict with keys:
            - ``ok`` (bool): whether the call succeeded
            - ``local_analysis`` (dict): the local rule-based result
            - ``ai_report`` (str | None): the AI-generated Markdown report
            - ``error`` (str | None): error message if the call failed
    """
    # 1. Run local analysis
    local = analyze(duration_minutes=duration_minutes, db_path=db_path)

    # 2. Build the prompt
    user_prompt = _build_prompt(local)

    # 3. Call DeepSeek
    key = api_key or os.getenv("DEEPSEEK_API_KEY")
    if not key:
        return {
            "ok": False,
            "local_analysis": local.to_dict(),
            "ai_report": None,
            "error": "未设置 DEEPSEEK_API_KEY 环境变量，无法调用 AI 分析",
        }

    try:
        client = OpenAI(api_key=key, base_url=DEEPSEEK_BASE_URL)
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        report = response.choices[0].message.content
        return {
            "ok": True,
            "local_analysis": local.to_dict(),
            "ai_report": report,
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "local_analysis": local.to_dict(),
            "ai_report": None,
            "error": f"DeepSeek API 调用失败: {exc}",
        }
