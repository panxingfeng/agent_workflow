# -*- coding: utf-8 -*-
"""
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2025-1-11
@version: 2.0.0
@license: MIT License
Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""
import logging
import os
from typing import Dict, Any, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

    async def format_search_results(self, search_result: Dict[str, Any], output: List[str]) -> List[str]:
        """格式化搜索结果，优化展示效果"""
        try:
            # 提取答案和链接
            answer = search_result.get('answer', '')

            # 如果有引用来源，构建链接数据
            sources = search_result.get('sources', [])

            # 遍历 sources，生成 URL 列表
            url_list = []
            if sources:
                for index, source in enumerate(sources, start=1):
                    url = source.get('url', '无链接')
                    url_list.append(f"{index}. {url}")

            output.append(answer)
            return url_list

        except Exception as e:
            logger.error(f"格式化搜索结果失败: {str(e)}")
            error_msg = "格式化搜索结果时发生错误"
            output.append(error_msg)
            return []

    async def format_image_description_results(self, result: str, output: List[str]) -> None:
        """
        格式化图像分析结果

        Args:
            result: 图像分析结果
            output: 输出列表
        """
        output.extend([
            "图像分析结果：",
            result
        ])

    def format_image_generator_results(self, result: str, output: List[str]) -> Tuple[bool, str]:
        """
        格式化图片生成结果

        Args:
            result: 处理结果（通常是输出路径）
            output: 输出列表

        Returns:
            Tuple[bool, str]:
                - bool: 是否成功
                - str: 错误信息（如果失败）或空字符串（如果成功）

        Raises:
            ValueError: 当格式化失败需要重试时抛出
        """
        try:
            if not result:
                raise ValueError("生成结果为空")

            if not isinstance(result, str):
                raise ValueError(f"无效的结果类型: {type(result)}")

            # 验证路径是否存在
            if not os.path.exists(result):
                raise ValueError(f"输出路径不存在: {result}")

            output.extend([
                f"输出路径：{result}\n"
            ])
            return True, ""

        except Exception as e:
            error_msg = f"格式化图片生成结果时发生错误: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    async def format_weather_results(self, weather_data: Any, output: List[str]) -> None:
        """
        格式化天气结果

        Args:
            weather_data: 天气数据
            output: 输出列表

        功能：
        1. 展示原始天气数据
        2. 生成天气分析和建议
        """
        output.extend([
            str(weather_data)
        ])

    def format_file_converter_results(self, result: str, output: List[str], chat_ui: bool = False) -> None:
        """
        格式化文件转换结果

        Args:
            result: 文件转换结果（通常是输出路径）
            output: 输出列表
            chat_ui: 是否是前端ui
        """
        import os

        if chat_ui:
            output.extend([
                f"\n输出路径：{result}\n"
            ])
        else:
            # 获取项目的根目录
            root_dir = os.getcwd()

            # 拼接完整的输出路径
            full_path = os.path.join(root_dir, result) if result else "未生成"

            # 添加格式化内容到输出列表
            output.extend([
                f"\n输出路径：{full_path}\n"
            ])

    def format_audio_results(self, result: str, output: List[str],chat_ui):
        """
        格式化音频处理结果

        Args:
            result: 音频处理结果（通常是输出路径）
            output: 输出列表
        """
        if chat_ui:
            parts = result.split('output')
            if len(parts) > 1:
                output.extend([
                    f"输出路径：{'output' + parts[1]}\n"
                ])
        else:
            output.extend([
                f"输出路径：{result if result else '未生成'}\n"
            ])
