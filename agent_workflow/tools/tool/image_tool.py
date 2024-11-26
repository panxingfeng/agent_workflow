# -*- coding: utf-8 -*-
"""
@file: image_tool.py
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2024-11-23
@version: 1.0.0
@license: MIT License

@description:
图像识别工具类模块 (ImageTool)

主要功能：
基于 Ollama API 实现多种图像分析功能，包括图像描述、文字提取、物体检测和场景分析

核心特性：
1. 多任务支持：支持多种图像分析任务类型
2. 统一接口：提供标准化的任务处理接口
3. 灵活配置：支持自定义用户问题和分析需求
4. 错误处理：完善的异常捕获和错误处理机制
5. 结果格式化：统一的结果输出格式

Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""
import base64
import json
from typing import List, Dict, Any, Optional
from enum import Enum
import ollama

from agent_workflow.tools.tool.base import BaseTool


class ImageTaskType(str, Enum):
    """
    图像任务类型枚举

    定义支持的图像分析任务类型：
    - DESCRIBE: 图像描述
    - EXTRACT_TEXT: 文字提取
    - DETECT_OBJECTS: 物体检测
    - ANALYZE_SCENE: 场景分析
    """
    DESCRIBE = "describe"
    EXTRACT_TEXT = "extract_text"
    DETECT_OBJECTS = "detect_objects"
    ANALYZE_SCENE = "analyze_scene"

    @classmethod
    def list_tasks(cls) -> List[str]:
        """
        列出所有支持的任务类型

        Returns:
            任务类型列表
        """
        return [task.value for task in cls]


class ImageTool(BaseTool):
    """
    图像识别工具类

    功能：
    1. 图像内容描述
    2. 文字内容提取
    3. 物体检测分析
    4. 场景内容解析

    属性：
        model: 使用的模型名称
        PROMPT_TEMPLATES: 不同任务类型的提示词模板
    """

    # 各任务类型的提示词模板
    PROMPT_TEMPLATES = {
        "describe": """图像内容描述任务

    1. 视觉元素分析：
       - 主体内容识别和位置描述
       - 关键视觉元素的空间关系
       - 色彩、光线和构图特点

    2. 细节描述要求：
       - 前景与背景的区分
       - 重要对象的特征描述
       - 动作、表情或状态的捕捉

    3. 场景评估：
       - 图片质量和清晰度评价
       - 可见度和光照条件说明
       - 如遇模糊或不确定，标注"图像不清晰，可能包含..."

    请按照重要性顺序组织描述，确保全面性和准确性。""",

        "extract_text": """图像文字提取任务

    1. 文字检测流程：
       - 扫描全图定位所有文字区域
       - 分析文字排列方式(横向/竖向)
       - 识别特殊符号和标点

    2. 文本内容提取：
       - 按区域提取并分类文字
       - 识别多语种文本并注明语言
       - 保持原始文本格式和布局

    3. 质量评估：
       - 标注文字清晰度等级
       - 指出模糊或难以辨认的部分
       - 提供文字可信度评估

    4. 结果整理：
       - 按区域或语言分类展示
       - 标注重要文字的位置信息
       - 提供完整性和准确性说明""",

        "detect_objects": """图像物体检测任务

    1. 物体识别与定位：
       - 扫描并定位所有可见物体
       - 标注物体的精确坐标 [x1, y1, x2, y2]
       - 计算检测框的置信度

    2. 物体属性分析：
       - 对象分类和类别确定
       - 尺寸和比例估计
       - 姿态和朝向描述

    3. 关系分析：
       - 物体间的空间关系
       - 重叠和遮挡情况
       - 互动和组合模式

    4. 结果输出要求：
       - 按置信度排序展示结果
       - 提供详细的属性描述
       - 标注不确定因素""",

        "analyze_scene": """图像场景分析任务

    1. 环境类型判断：
       - 场景类别(室内/室外/自然/城市等)
       - 环境特征和布局分析
       - 光照和天气条件

    2. 场景要素分析：
       - 主要建筑或自然元素
       - 人物和活动状态
       - 重要标志性特征

    3. 氛围评估：
       - 整体视觉风格
       - 色彩和光影效果
       - 环境情绪和氛围

    4. 场景功能分析：
       - 空间用途判断
       - 活动类型识别
       - 时间和季节特征

    5. 综合信息：
       - 场景的整体布局和构成
       - 独特或显著的视觉特征
       - 环境状态和使用情况"""
    }

    def __init__(self, model: str = "llama3.2-vision"):
        """
        初始化图像识别工具类。
        :param model: 使用的模型名称，默认为 "llama3.2-vision"。
        """
        self.model = model

    def get_description(self) -> str:
        """
        返回工具的描述信息，包括名称、功能和所需参数。
        """
        tool_info = {
            "name": "ImageTool",
            "description": "图像分析工具，可以根据用户问题分析图像内容并生成相关结果。",
            "capabilities": [
                "描述图像内容",
                "提取图像中的文字",
                "检测图像中的物体",
                "分析图像的场景"
            ],
            "parameters": {
                "image_path": {
                    "type": "string",
                    "description": "图像文件路径"
                },
                "user_question": {
                    "type": "string",
                    "description": "用户提问的问题"
                },
                "task_type": {
                    "type": "enum",
                    "options": ImageTaskType.list_tasks(),
                    "description": "需要执行的图像分析任务类型"
                }
            }
        }
        return json.dumps(tool_info, ensure_ascii=False)

    @staticmethod
    def encode_image(file_path: str) -> str:
        """
        将图像文件编码为 Base64 格式。
        :param file_path: 图像文件路径。
        :return: Base64 编码后的字符串。
        """
        try:
            with open(file_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode("utf-8")
        except Exception as e:
            raise ValueError(f"图像编码错误: {e}")

    def describe_image(self, image_path: str, user_question: Optional[str] = None) -> str:
        """
        图像描述方法

        功能：
        1. 分析图像的主要内容和视觉元素
        2. 生成详细的描述性文本
        3. 可根据用户问题进行针对性描述

        Args:
            image_path: 图像文件的路径
            user_question: 可选的用户问题，用于生成针对性描述

        Returns:
            str: 图像描述文本，包含：
            - 主要内容描述
            - 视觉元素分析
            - 场景细节说明

        Raises:
            返回错误信息字符串，如果：
            - 图像分析失败
            - 文件路径无效
            - 处理过程出错
        """
        response = self.analyze_image(image_path, task_type=ImageTaskType.DESCRIBE, user_question=user_question)
        if "error" in response:
            return f"分析失败: {response['error']}"
        return response.get("message", {}).get("content", "未返回结果")

    def extract_text(self, image_path: str, user_question: Optional[str] = None) -> str:
        """
        图像文字提取方法

        功能：
        1. 识别和提取图像中的所有文本内容
        2. 支持多语言文本识别
        3. 保持文本的原始格式和布局

        Args:
            image_path: 图像文件的路径
            user_question: 可选的用户问题，用于定向提取特定文本

        Returns:
            str: 提取的文本内容，包含：
            - 识别到的文本
            - 文本位置信息
            - 文字清晰度评估

        Raises:
            返回错误信息字符串，如果：
            - 文本提取失败
            - 图像质量不足
            - 处理过程出错
        """
        response = self.analyze_image(image_path, task_type=ImageTaskType.EXTRACT_TEXT, user_question=user_question)
        if "error" in response:
            return f"提取失败: {response['error']}"
        return response.get("message", {}).get("content", "未提取到文本")

    def detect_objects(self, image_path: str, user_question: Optional[str] = None) -> str:
        """
        物体检测方法

        功能：
        1. 检测和定位图像中的所有物体
        2. 分析物体的属性和特征
        3. 计算物体间的空间关系

        Args:
            image_path: 图像文件的路径
            user_question: 可选的用户问题，用于检测特定物体

        Returns:
            str: 检测结果描述，包含：
            - 检测到的物体列表
            - 物体位置和大小
            - 物体间的关系描述
            - 置信度评分

        Raises:
            返回错误信息字符串，如果：
            - 物体检测失败
            - 图像不清晰
            - 处理过程出错
        """
        response = self.analyze_image(image_path, task_type=ImageTaskType.DETECT_OBJECTS, user_question=user_question)
        if "error" in response:
            return f"检测失败: {response['error']}"
        return response.get("message", {}).get("content", "未检测到物体")

    def analyze_scene(self, image_path: str, user_question: Optional[str] = None) -> str:
        """
        场景分析方法

        功能：
        1. 分析图像的整体场景类型
        2. 识别环境特征和氛围
        3. 评估场景的功能和用途

        Args:
            image_path: 图像文件的路径
            user_question: 可选的用户问题，用于针对性场景分析

        Returns:
            str: 场景分析结果，包含：
            - 场景类型判断
            - 环境特征描述
            - 氛围和情境分析
            - 功能和用途评估

        Raises:
            返回错误信息字符串，如果：
            - 场景分析失败
            - 图像不适合场景分析
            - 处理过程出错

        分析维度：
        1. 环境类型：
           - 室内/室外判断
           - 自然/人造环境识别
           - 场景功能判定

        2. 环境特征：
           - 光照条件
           - 天气状况
           - 时间特征

        3. 氛围评估：
           - 整体风格
           - 环境情绪
           - 视觉效果

        4. 使用场景：
           - 可能的用途
           - 活动类型
           - 人员容量
        """
        response = self.analyze_image(image_path, task_type=ImageTaskType.ANALYZE_SCENE, user_question=user_question)
        if "error" in response:
            return f"分析失败: {response['error']}"
        return response.get("message", {}).get("content", "未返回场景分析结果")

    def analyze_image(self, image_path: str, task_type: ImageTaskType, user_question: Optional[str] = None) -> Dict[
        str, Any]:
        """
        执行图像分析任务

        Args:
            image_path: 图像文件路径
            task_type: 任务类型
            user_question: 用户问题（可选）

        Returns:
            分析结果字典

        功能：
        1. 图像编码和验证
        2. 任务类型匹配
        3. 调用模型进行分析
        4. 结果格式化处理
        """
        if task_type not in ImageTaskType.list_tasks():
            return {"error": f"不支持的任务类型: {task_type}"}

        try:
            # 编码图像
            image_data = self.encode_image("upload/" + image_path)

            # 获取任务提示词
            prompt = self.PROMPT_TEMPLATES[task_type]
            if user_question:
                prompt += f"\n\n用户问题: {user_question}\n请根据图像内容和用户问题生成回答。"

            # 调用模型进行分析
            response = ollama.chat(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [image_data],
                }],
            )

            return response
        except Exception as e:
            return {"error": str(e)}

    async def run(self, **kwargs) -> str:
        """
        执行图像分析任务的统一接口

        Args:
            **kwargs: 包含必要的参数
                - image_path: 图像路径
                - task_type: 任务类型
                - user_question: 用户问题（可选）

        Returns:
            分析结果或错误信息

        流程：
        1. 参数验证
        2. 图像加载
        3. 任务执行
        4. 结果处理
        """
        try:
            # 参数验证
            image_path = kwargs.get("image_path")
            user_question = kwargs.get("user_question")
            task_type = kwargs.get("task_type")

            if not image_path:
                return "错误: 未提供图像文件路径。"
            if not task_type or task_type not in ImageTaskType.list_tasks():
                return f"错误: 无效或未提供任务类型。支持的任务类型: {ImageTaskType.list_tasks()}"

            # 执行分析
            response = self.analyze_image(image_path, task_type=task_type, user_question=user_question)
            if "error" in response:
                return f"分析失败: {response['error']}"

            return response.get("message", {}).get("content", "未返回分析结果")

        except Exception as e:
            return f"执行任务时发生错误: {str(e)}"
