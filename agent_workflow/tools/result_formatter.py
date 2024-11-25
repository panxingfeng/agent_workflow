# -*- coding: utf-8 -*-
"""
@file: result_formatter.py
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2024-11-23
@version: 1.0.0
@license: MIT License

@description:
工具结果格式化处理器，为不同工具的输出提供统一的格式化和解析能力。

功能特性:
1. 多工具结果格式化支持（搜索、天气、文案、图像等）
2. 智能结果分析和总结生成
3. 统一的输出格式标准
4. 专业解读和建议生成
5. 错误处理和优雅降级
6. 模块化的提示词管理
7. 自定义格式化模板

Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""
from typing import Dict, Any, List
import re


class ResultFormatter:
    """
    结果格式化处理器类

    功能：
    1. 处理各类工具的输出结果
    2. 生成专业的分析和总结
    3. 提供统一的格式化输出

    属性：
        llm: 语言模型实例，用于生成分析和总结
        summary_prompts: 不同工具的提示词模板
    """

    def __init__(self, llm=None):
        """
        初始化格式化处理器

        Args:
            llm: 语言模型实例，用于生成分析总结
        """
        self.llm = llm
        # 各工具的提示词模板
        self.summary_prompts = {
            'SearchTool': "分析以下内容的核心观点、可信度和建议：\n{content}",
            'WeatherTool': "分析天气数据：{weather_data}，提供天气概况、温度变化和出行建议",
            'XHSTool': """从以下小红书文案分析:
            1. 标题吸引力
            2. 内容结构和叙述方式
            3. 情感渲染和互动性
            4. 优化建议

            文案内容：{content}""",
            'ImageTool': "专业解读图像分析结果：\n{content}",
            'URLTool': "分析API响应状态和关键信息：\n{content}",
            'FileConverterTool': "总结文件转换结果：\n{content}"
        }

    def format_search_results(self, search_result: Dict[str, Any], output: List[str]) -> None:
        """
        格式化搜索结果

        Args:
            search_result: 搜索结果字典，包含答案和来源
            output: 输出列表，用于存储格式化结果

        功能：
        1. 提取搜索答案和来源
        2. 生成引用索引
        3. 添加专业总结
        """
        # 提取答案和来源
        answer = search_result.get('answer', '')
        sources = search_result.get('sources', [])
        citation_text = answer.split('这些信息来源于')[-1]
        cited_indices = [int(idx) for idx in re.findall(r'\[(\d+)\]', citation_text)]

        # 格式化搜索结果
        output.extend([
            "---------------SearchTool---------------",
            "🔍 搜索结果：",
            answer
        ])

        # 添加参考来源
        if sources:
            output.append("\n📚 主要参考来源：")
            for idx in cited_indices:
                if 0 <= idx - 1 < len(sources):
                    source = sources[idx - 1]
                    output.append(f"{idx}. {source.get('title', '未知标题')}\n   {source.get('url', '未知链接')}")

        # 生成总结
        try:
            summary = self._generate_summary(answer, "SearchTool")
            output.extend(["\n💡 核心总结：", summary, "\n"])
        except Exception:
            output.append("\n无法生成搜索总结\n")

    def format_image_results(self, result: str, output: List[str]) -> None:
        """
        格式化图像分析结果

        Args:
            result: 图像分析结果
            output: 输出列表
        """
        output.extend([
            "---------------ImageTool---------------",
            "📷 图像分析结果：",
            result
        ])

        try:
            summary = self._generate_summary(result, "ImageTool")
            output.extend(["\n💡 专业解读：", summary, "\n"])
        except Exception as e:
            output.append(f"\n无法生成解读: {str(e)}\n")

    def format_weather_results(self, query: str, weather_data: Any, output: List[str]) -> None:
        """
        格式化天气结果

        Args:
            query: 用户查询
            weather_data: 天气数据
            output: 输出列表

        功能：
        1. 展示原始天气数据
        2. 生成天气分析和建议
        """
        output.extend([
            "---------------WeatherTool---------------",
            str(weather_data)
        ])

        try:
            formatted_content = self.summary_prompts['WeatherTool'].format(
                weather_data=str(weather_data)
            )
            summary = ''.join(self.llm.chat(
                message=formatted_content,
                prompt="请提供天气分析和建议"
            )).strip()
            output.extend([f"\n🌈 天气分析：\n{summary}\n"])
        except Exception as e:
            output.append(f"\n无法生成天气总结: {str(e)}\n")

    def format_file_converter_results(self, result: str, output: List[str]) -> None:
        """
        格式化文件转换结果

        Args:
            result: 文件转换结果（通常是输出路径）
            output: 输出列表
        """
        output.extend([
            "---------------FileConverterTool---------------",
            "📄 转换状态：",
            "转换成功" if result else "转换失败",
            f"\n输出路径：{result if result else '未生成'}\n"
        ])

    def _generate_summary(self, content: str, tool_name: str) -> str:
        """
        生成内容总结

        Args:
            content: 需要总结的内容
            tool_name: 工具名称

        Returns:
            生成的总结文本

        功能：
        1. 获取对应工具的提示词模板
        2. 使用语言模型生成专业分析
        3. 处理可能的错误
        """
        prompt_template = self.summary_prompts.get(tool_name, "")
        if not prompt_template:
            return content

        formatted_prompt = prompt_template.format(content=content)
        if self.llm is None:
            from ..llm.llm import LLM
            self.llm = LLM()
        return ''.join(self.llm.chat(
            message=formatted_prompt,
            prompt="请提供专业分析"
        )).strip()
