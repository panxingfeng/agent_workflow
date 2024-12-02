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

支持模型:
- llama3.2-vision: 基于Ollama API的识别模型
- glm-edge-v-5b: 智谱AI开源的中英双语图像理解模型
- MiniCPM-V-2_6: 清华开源的视觉语言大模型

主要功能：
实现多种图像分析功能，包括图像描述、文字提取、物体检测和场景分析

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
import torch
from PIL import Image
from typing import List, Dict, Any, Optional
from enum import Enum
import ollama
from modelscope import snapshot_download, AutoModel
from transformers import (
    AutoTokenizer,
    AutoImageProcessor,
    AutoModelForCausalLM,
)

from agent_workflow.tools.tool.base import BaseTool


class ModelType(str, Enum):
    LLAMA = "llama3.2-vision"
    GLM = "glm-edge-v-5b"
    MINICPM_V_2_6 = "OpenBMB/MiniCPM-V-2_6"

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
        model: 使用的模型名称  支持llama3.2-vision,glm-edge-v-5b,MiniCPM-V-2_6
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

    def __init__(self, model: str = ModelType.LLAMA):
        """初始化图像识别工具
        Args:
            model: 选择模型类型
                llama3.2-vision: Ollama推理API、响应快速
                glm-edge-v-5b: 智谱开源、中英双语支持
                MiniCPM-V-2_6: 清华开源、支持图文理解
        """
        self.model = model
        self.model_components = None

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

    def _init_model(self):
        """根据选择的模型类型加载对应组件"""
        if self.model_components is not None:
            return

        if self.model == ModelType.GLM:
            model_dir = snapshot_download("ZhipuAI/glm-edge-v-5b")
            self.model_components = {
                'processor': AutoImageProcessor.from_pretrained(model_dir, trust_remote_code=True),
                'tokenizer': AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True),
                'model': AutoModelForCausalLM.from_pretrained(
                    model_dir, torch_dtype=torch.bfloat16, device_map="cuda", trust_remote_code=True
                )
            }

        elif self.model == ModelType.MINICPM_V_2_6:
            model = AutoModel.from_pretrained(
                ModelType.MINICPM_V_2_6,
                trust_remote_code=True,
                attn_implementation='sdpa',
                torch_dtype=torch.bfloat16
            ).eval().cuda()

            tokenizer = AutoTokenizer.from_pretrained(
                ModelType.MINICPM_V_2_6,
                trust_remote_code=True
            )

            self.model_components = {
                'model': model,
                'tokenizer': tokenizer
            }

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

    def _analyze_with_ollama(self, image_path: str, task_type: ImageTaskType, user_question: Optional[str]) -> Dict[
        str, Any]:
        """
        使用Ollama API进行图像分析

        Args:
            image_path: 图像路径
            task_type: 任务类型
            user_question: 用户问题

        Returns:
            分析结果字典,包含模型响应内容

        处理流程:
        1. 图像编码为base64
        2. 构建prompt和消息体
        3. 调用API获取结果
        """
        image_data = self.encode_image("upload/" + image_path)
        prompt = self.PROMPT_TEMPLATES[task_type]
        if user_question:
            prompt += f"\n\n用户问题: {user_question}\n请根据图像内容和用户问题生成回答。"

        return ollama.chat(
            model=self.model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [image_data],
            }],
        )

    def _analyze_with_glm(self, image_path: str, task_type: ImageTaskType, user_question: Optional[str]) -> Dict[
        str, Any]:
        """
        使用GLM模型进行图像分析

        Args:
            image_path: 图像路径
            task_type: 任务类型
            user_question: 用户问题

        Returns:
            分析结果字典,包含生成的文本内容

        处理流程:
        1. 初始化/加载GLM模型
        2. 构建消息和输入数据
        3. 处理图像并生成结果
        4. 解码并返回结果
        """
        if self.model_components is None:
            model_dir = snapshot_download("ZhipuAI/glm-edge-v-5b")
            self.model_components = {
                'processor': AutoImageProcessor.from_pretrained(model_dir, trust_remote_code=True),
                'tokenizer': AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True),
                'model': AutoModelForCausalLM.from_pretrained(
                    model_dir, torch_dtype=torch.bfloat16, device_map="cuda", trust_remote_code=True
                )
            }
        image = Image.open("upload/" + image_path)

        messages = [{"role": "user", "content": [
            {"type": "image"},
            {"type": "text", "text": f"{self.PROMPT_TEMPLATES[task_type]}\n\n{user_question}" if user_question else
            self.PROMPT_TEMPLATES[task_type]}
        ]}]

        inputs = self.model_components['tokenizer'].apply_chat_template(
            messages, add_generation_prompt=True, return_dict=True, tokenize=True, return_tensors="pt"
        ).to(next(self.model_components['model'].parameters()).device)

        pixel_values = self.model_components['processor'](image).pixel_values
        generate_kwargs = {
            **inputs,
            "pixel_values": torch.tensor(pixel_values).to(next(self.model_components['model'].parameters()).device)
        }

        output = self.model_components['model'].generate(**generate_kwargs, max_new_tokens=100)
        content = self.model_components['tokenizer'].decode(
            output[0][len(inputs["input_ids"][0]):], skip_special_tokens=True
        )
        return {"message": {"content": content}}

    def _analyze_with_minicpm(self, image_path: str, task_type: ImageTaskType, user_question: Optional[str]) -> Dict[
        str, Any]:
        """
        使用MiniCPM模型分析图像

        参数:
            image_path: 图像路径 (需以upload/开头)
            task_type: 分析任务类型
            user_question: 用户问题(可选)

        返回:
            Dict[str, Any]: {
                "message": {"content": str} # 分析结果
            }

        流程:
        1. 模型初始化
        2. 图像预处理
        3. 提示词构建
        4. 生成分析结果
        """
        if self.model_components is None:
            model = AutoModel.from_pretrained(
                ModelType.MINICPM_V_2_6,
                trust_remote_code=True,
                attn_implementation='sdpa',
                torch_dtype=torch.bfloat16
            ).eval().cuda()

            tokenizer = AutoTokenizer.from_pretrained(ModelType.MINICPM_V_2_6, trust_remote_code=True)

            self.model_components = {
                'model': model,
                'tokenizer': tokenizer
            }

        image = Image.open("upload/" + image_path).convert('RGB')
        prompt = self.PROMPT_TEMPLATES[task_type]
        if user_question:
            prompt += f"\n\n{user_question}"

        msgs = [{'role': 'user', 'content': [image, prompt]}]
        output = self.model_components['model'].chat(
            image=None,
            msgs=msgs,
            tokenizer=self.model_components['tokenizer']
        )
        return {"message": {"content": output}}

    def analyze_image(self, image_path: str, task_type: ImageTaskType, user_question: Optional[str] = None) -> Dict[
        str, Any]:
        """
        执行图像分析任务并路由到对应模型处理

        Args:
            image_path: 图像文件路径 (需要以upload/开头)
            task_type: 分析任务类型 (描述/文本提取/物体检测/场景分析)
            user_question: 特定分析问题 (可选)

        Returns:
            Dict[str, Any]: {
                "message": {"content": str}, # 成功时返回分析结果
                "error": str                 # 失败时返回错误信息
            }

        处理流程:
        1. 校验任务类型合法性
        2. 根据当前模型类型路由到对应处理函数
        3. 异常捕获并返回统一格式错误信息

        错误处理:
        - 不支持的任务类型
        - 不支持的模型类型
        - 处理过程异常
        """

        if task_type not in ImageTaskType.list_tasks():
            return {"error": f"不支持的任务类型: {task_type}"}

        try:
            if self.model == ModelType.LLAMA:
                return self._analyze_with_ollama(image_path, task_type, user_question)
            elif self.model == ModelType.GLM:
                return self._analyze_with_glm(image_path, task_type, user_question)
            elif self.model == ModelType.MINICPM_V_2_6:
                return self._analyze_with_minicpm(image_path, task_type, user_question)
            else:
                return {"error": f"不支持的模型类型: {self.model}"}
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
