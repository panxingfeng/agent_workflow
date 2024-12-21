# -*- coding: utf-8 -*-
"""
@file: image_tool.py
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2024-12-12
@version: 1.0.0
@license: MIT License

@description:
图像工具类模块 (ImageTool)

支持模型:
1. 图像识别模型(2024-11-23):
    - llama3.2-vision: 基于Ollama API的识别模型
    - glm-edge-v-5b: 智谱AI开源的中英双语图像理解模型
    - MiniCPM-V-2_6: 清华开源的视觉语言大模型

2. 图像生成模:
    - flux: FLUX.1-dev开发版模型
    - sd3: Stable Diffusion 3.5大型模型
    - sdwebui_forge: SD WebUI Forge模型
    - comfyui: 使用comfyui进行生图

主要功能：
1. 图像识别：
    - 图像描述生成
    - 文字内容提取
    - 物体检测分析
    - 场景内容理解

2. 图像生成：
    - 文本生成图像
    - 多模型支持
    - 风格迁移(Lora)
    - 参数优化配置

Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""
import base64
import json
import logging
import os

import torch
from PIL import Image
from typing import List, Dict, Any, Optional
from enum import Enum
import ollama
from diffusers import BitsAndBytesConfig, StableDiffusion3Pipeline, FluxPipeline
from pydantic import BaseModel, Field

from agent_workflow.llm.llm import LLM
from agent_workflow.rag.lightrag_mode import LightsRAG
from agent_workflow.tools.tool.base import BaseTool, images_tool_prompts, get_prompts
from agent_workflow.utils import ForgeImageGenerator, ForgeAPI
from agent_workflow.utils.comfyui_api import ComfyuiAPI
from config.config import QUALITY_PROMPTS, NEGATIVE_PROMPTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['OMP_NUM_THREADS'] = '1'


class DescriptionModelType(str, Enum):
    LLAMA = "llama3.2-vision"
    GLM = "glm-edge-v-5b"
    MINICPM = "OpenBMB/MiniCPM-V-2_6"


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

    def __str__(self):
        return self.value

    @classmethod
    def list_tasks(cls) -> List[str]:
        """
        列出所有支持的任务类型

        Returns:
            任务类型列表
        """
        return [task.value for task in cls]


class GenerationModelType(str, Enum):
    FLUX_1_DEV = "flux"
    SD3_5_LARGE = "sd3"
    SDWEBUI_FORGE = "sdwebui_forge"
    SDWEBUI = "sdwebui"
    COMFYUI = "comfyui"

    def __str__(self):
        return self.value


class GenerationConfig(BaseModel):
    prompt: str = Field(..., description="英文生成提示词")
    negative_prompt: Optional[str] = Field(
        default=NEGATIVE_PROMPTS,
        description="负面提示词"
    )
    width: int = Field(default=512)
    height: int = Field(default=512)
    output_dir: str = Field(default="output")


class ForgeGenerationConfig(BaseModel):
    prompt: str = Field(..., description="生成提示词")
    model_name: str = Field(default="基础_F.1基础算法模型.safetensors", description="模型名称")
    sampling_method: str = Field(default="Euler", description="采样方法")
    steps: int = Field(default=25, description="迭代步数")
    width: int = Field(default=896, description="图像宽度")
    height: int = Field(default=1152, description="图像高度")
    batch_count: int = Field(default=1, description="总批次数")
    batch_size: int = Field(default=1, description="单批数量")
    cfg_scale: float = Field(default=3.5, description="CFG系数")
    seed: int = Field(default=-1, description="随机种子")
    output_dir: str = Field(default="output", description="输出目录")


class ComfyuiGenerationConfig(BaseModel):
    task_mode: str = Field(default="基础文生图", description="生图模式")
    prompt: str = Field(..., description="生成提示词")
    negative_prompt: Optional[str] = Field(
        default=NEGATIVE_PROMPTS,
        description="负面提示词"
    )
    model_name: str = Field(default="基础_F.1基础算法模型.safetensors", description="模型名称")
    image_name: str = Field(default=None,description="上传的图像内容")
    sampling_method: str = Field(default="euler", description="采样方法")
    steps: int = Field(default=25, description="迭代步数")
    width: int = Field(default=512, description="图像宽度")
    height: int = Field(default=768, description="图像高度")
    batch_count: int = Field(default=1, description="总批次数")
    batch_size: int = Field(default=1, description="单批数量")
    cfg_scale: float = Field(default=8.0, description="CFG系数")
    output_dir: str = Field(default="output", description="输出目录")


class PromptGenMode(str, Enum):
    RAG = "rag" # 基于lightrag提前预处理的关系图
    LLM = "llm" # 基于部署的ollama的模型进行生成回复
    NONE = "none" # 使用智能体提供的提示词

    def __str__(self):
        return self.value


class SDPromptGenerator:
    """sd提示词生成器"""
    def __init__(self):
        self.quality_tags = QUALITY_PROMPTS

    def process_keywords(self, kw_data: dict) -> Dict[str, List[str]]:
        """处理关键词数据"""
        result = {
            "subject": [],
            "style": [],
            "details": []
        }

        high_level = kw_data.get("high_level_keywords", [])
        for kw in high_level:
            kw = kw.lower()
            if "style" in kw:
                result["style"].append(kw.replace(" style", ""))
            elif any(x in kw.lower() for x in ["photography", "photo"]):
                result["style"].extend(["photorealistic", "professional photo"])
            else:
                result["subject"].append(kw)

        low_level = kw_data.get("low_level_keywords", [])
        for kw in low_level:
            kw = kw.lower()
            if any(x in kw.lower() for x in ["dress", "veil", "clothing"]):
                result["details"].append(kw)
            else:
                result["subject"].append(kw)

        return result

    def merge_tags(self, *tag_sets: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """合并多个标签集"""
        result = {
            "subject": [],
            "style": [],
            "details": []
        }

        # 合并所有标签
        for tags in tag_sets:
            if not tags:
                continue
            for category in result:
                if category in tags:
                    result[category].extend(tags[category])

        # 清理和去重
        for category in result:
            # 转换为小写并去重
            unique_tags = set(tag.lower() for tag in result[category] if tag)
            result[category] = list(unique_tags)

        return result

    def format_prompt(self, tags: Dict[str, List[str]]) -> str:
        """格式化提示词"""
        parts = [
            ", ".join(tags.get("subject", [])),
            ", ".join(tags.get("style", [])),
            ", ".join(tags.get("details", [])),
            self.quality_tags,
        ]
        return ", ".join(filter(None, parts))


async def generate_stable_diffusion_prompt(rag: LightsRAG, user_input: str) -> str:
    """生成提示词"""
    generator = SDPromptGenerator()

    prompt_template = f'''示例输入：写实风格的带光效的全身像女生
    示例输出：
    {{
        "subject": ["1girl", "female", "woman", "full body", "standing"],
        "style": ["realistic", "photorealistic", "ultra-detailed"],
        "details": ["volumetric lighting", "light rays", "lens flare", "cinematic lighting", "studio lighting", "professional photography"]
    }}

    将此描述转为相同格式的英文标签：{user_input}'''

    try:
        # 获取RAG响应
        response = await rag.ask(prompt_template)

        # 确保 response 是字符串类型
        response_text = response
        if isinstance(response, tuple):
            response_text = "".join(map(str, response))
        elif not isinstance(response, str):
            response_text = str(response)

        # 提取JSON和关键词数据
        tags_from_response = {}
        kw_tags = {}

        # 处理JSON响应
        import re
        json_pattern = r'\{[^{}]*\}'
        matches = list(re.finditer(json_pattern, response_text))

        if matches:
            for match in matches:
                try:
                    json_str = match.group()
                    data = json.loads(json_str)

                    if all(key in data for key in ["subject", "style", "details"]):
                        tags_from_response = data
                        break
                except Exception as e:
                    logger.warning(f"执行sd_prompt的JSON解析失败: {str(e)}")
                    continue

        # 处理关键词数据
        try:
            # 使用原始 response 对象处理关键词
            kw_prompt = getattr(response, 'kw_prompt', None)
            if kw_prompt:
                if isinstance(kw_prompt, str):
                    kw_data = json.loads(kw_prompt)
                elif isinstance(kw_prompt, (tuple, list)):
                    kw_data = json.loads("".join(map(str, kw_prompt)))
                else:
                    kw_data = json.loads(str(kw_prompt))
                kw_tags = generator.process_keywords(kw_data)
        except Exception as e:
            logger.warning(f"执行sd_prompt的关键词处理失败: {str(e)}")

        # 合并所有标签
        final_tags = generator.merge_tags(tags_from_response, kw_tags)

        # 如果没有有效标签，使用基础标签
        if not any(final_tags.values()):
            logger.warning("使用sd_prompt的基础标签")

            # 基础主体标签
            subject_tags = []
            if "女" in user_input:
                subject_tags = ["1girl", "woman", "female"]
            elif "男" in user_input:
                subject_tags = ["1boy", "man", "male"]
            else:
                subject_tags = ["person", "portrait"]

            # 基础风格标签
            style_tags = []
            if "写实" in user_input:
                style_tags = ["realistic", "photorealistic", "professional photo"]
            elif "动漫" in user_input or "二次元" in user_input:
                style_tags = ["anime", "manga style", "cartoon"]
            elif "水彩" in user_input:
                style_tags = ["watercolor", "painting", "artistic"]
            elif "油画" in user_input:
                style_tags = ["oil painting", "fine art", "masterpiece painting"]
            elif "素描" in user_input:
                style_tags = ["pencil drawing", "sketch", "graphite"]
            elif "赛博朋克" in user_input:
                style_tags = ["cyberpunk", "sci-fi", "futuristic"]
            elif "科幻" in user_input:
                style_tags = ["sci-fi", "futuristic", "cosmic"]
            elif "奇幻" in user_input:
                style_tags = ["fantasy", "magical", "mystical"]
            elif "插画" in user_input:
                style_tags = ["illustration", "digital art", "concept art"]
            else:
                style_tags = ["digital art", "illustration"]

            # 基础细节标签
            detail_tags = []
            if "肖像" in user_input:
                detail_tags = ["portrait shot", "detailed face", "professional lighting"]
            elif "全身" in user_input:
                detail_tags = ["full body", "full shot", "standing pose"]
            elif "风景" in user_input:
                detail_tags = ["landscape", "scenic", "beautiful environment"]
            elif "特写" in user_input:
                detail_tags = ["close-up", "detailed features", "high detail"]

            # 根据场景添加标签
            if "婚纱" in user_input:
                detail_tags.extend(["wedding dress", "white dress", "veil", "elegant"])
            elif "校园" in user_input:
                detail_tags.extend(["school uniform", "campus background", "school setting"])
            elif "商务" in user_input:
                detail_tags.extend(["business attire", "formal wear", "professional setting"])
            elif "休闲" in user_input:
                detail_tags.extend(["casual wear", "natural pose", "relaxed atmosphere"])

            # 设置基础标签
            basic_tags = {
                "subject": subject_tags,
                "style": style_tags,
                "details": detail_tags
            }

            final_tags = basic_tags

        return generator.format_prompt(final_tags)

    except Exception as e:
        logger.error(f"sd_prompt的生成过程中发生错误: {str(e)}")
        return generator.format_prompt({})


class DescriptionImageTool(BaseTool):
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

    def __init__(self, model: str = DescriptionModelType.LLAMA):
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
            "name": "DescriptionImageTool",
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

    def get_parameter_rules(self) -> str:
        """返回图像处理工具的参数设置规则"""
        rules = """
       DescriptionImageTool 需要设置:
       - image_path: 从用户消息中提取图片路径
         - 示例输入: "分析upload/test.jpg这张图片"
         - 参数设置: {"image_path": "test.jpg"}
         - 规则: 提取图片文件名或完整路径

       - task_type: 从用户意图判断任务类型
         - 示例输入: "描述这张图片的内容"
         - 参数设置: {"task_type": "describe"}
         - 规则: 根据用户描述匹配任务类型:[describe, extract_text, detect_objects, analyze_scene]

       - user_question: 提取用户具体问题(可选)
         - 示例输入: "图片里有几个人?"
         - 参数设置: {"user_question": "图片里有几个人?"}
         - 规则: 保留用户原始问题描述
       """
        return rules

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
        try:
            if self.model_components is None:
                from modelscope import snapshot_download
                from transformers import (
                    AutoTokenizer,
                    AutoImageProcessor,
                    AutoModelForCausalLM,
                )
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

            # 修改这部分：确保像素值是正确的张量类型
            pixel_values = self.model_components['processor'](image).pixel_values
            pixel_values = torch.tensor(pixel_values, dtype=torch.float32).to(
                next(self.model_components['model'].parameters()).device)

            generate_kwargs = {
                **inputs,
                "pixel_values": pixel_values
            }

            output = self.model_components['model'].generate(**generate_kwargs, max_new_tokens=100)
            content = self.model_components['tokenizer'].decode(
                output[0][len(inputs["input_ids"][0]):], skip_special_tokens=True
            )

            # 清理显存
            if self.model_components:
                self.model_components['model'].cpu()
                del self.model_components['model']
                del self.model_components['tokenizer']
                del self.model_components['processor']
                self.model_components = None
                torch.cuda.empty_cache()

            return {"message": {"content": content}}
        except Exception as e:
            # 确保即使发生错误也清理显存
            if self.model_components:
                self.model_components['model'].cpu()
                del self.model_components['model']
                del self.model_components['tokenizer']
                del self.model_components['processor']
                self.model_components = None
                torch.cuda.empty_cache()
            raise e

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
        try:
            if self.model_components is None:
                from modelscope import AutoModel, AutoTokenizer
                import torch
                model = AutoModel.from_pretrained(
                    'OpenBMB/MiniCPM-V-2_6',
                    trust_remote_code=True,
                    attn_implementation='sdpa',
                    torch_dtype=torch.bfloat16,
                ).eval().cuda()

                tokenizer = AutoTokenizer.from_pretrained('OpenBMB/MiniCPM-V-2_6', trust_remote_code=True)

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

        except Exception as e:
            return {"error": str(e)}

        finally:
            # 无论是否发生异常，都确保清理资源
            if self.model_components:
                try:
                    self.model_components['model'].cpu()  # 先将模型移到 CPU
                    del self.model_components['model']  # 删除模型
                    del self.model_components['tokenizer']  # 删除分词器
                    self.model_components = None
                    import torch
                    torch.cuda.empty_cache()  # 清空 CUDA 缓存
                except Exception as cleanup_error:
                    print(f"清理资源时发生错误: {cleanup_error}")

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
            if self.model == DescriptionModelType.LLAMA:
                return self._analyze_with_ollama(image_path, task_type, user_question)
            elif self.model == DescriptionModelType.GLM:
                return self._analyze_with_glm(image_path, task_type, user_question)
            elif self.model == DescriptionModelType.MINICPM:
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


class ImageGeneratorTool(BaseTool):
    """图像生成工具类，支持多种AI图像生成模型

    包含三种主要模型配置：
    - flux: FLUX.1-dev 模型
    - sd3: Stable Diffusion 3.5 大型模型
    - sdwebui_forge: SD WebUI Forge模型
    - sdwebui sd原生ui
    """

    # 模型配置字典，定义了不同模型的参数和配置
    MODELS = {
        "flux": {
            "path": "black-forest-labs/FLUX.1-dev",  # 模型路径
            "pipeline": FluxPipeline,  # 使用的管道类
            "quantization": False,  # 是否使用量化
            "use_negative_prompt": False,  # 是否使用反向提示词
            "model_args": {"torch_dtype": torch.bfloat16},  # 模型参数
            "generation_args": {  # 生成参数
                "guidance_scale": 3.5,  # 引导系数
                "num_inference_steps": 30,  # 推理步数
                "max_sequence_length": 512  # 最大序列长度
            }
        },
        "sd3": {
            "path": "stabilityai/stable-diffusion-3.5-large",
            "pipeline": StableDiffusion3Pipeline,
            "quantization": True,
            "use_negative_prompt": True,
            "model_args": {
                "torch_dtype": torch.bfloat16,
                "use_safetensors": True
            },
            "generation_args": {
                "guidance_scale": 4.5,
                "num_inference_steps": 28,
                "max_sequence_length": 512
            }
        },
        "sdwebui_forge": {
            "path": None,
            "pipeline": None,
            "quantization": False,
            "use_negative_prompt": False,
            "model_args": {},
            "generation_args": {}
        }
    }

    def __init__(self, model_type: str = GenerationModelType.COMFYUI,
                 prompt_gen_mode: str = PromptGenMode.NONE,
                 use_local: bool = True):
        """初始化图像生成工具

        Args:
            model_type: 模型类型
            prompt_gen_mode: 提示词生成模式
            use_local: 是否使用本地模型
        """
        self.model_type = model_type
        self.use_local = use_local
        self.prompt_mode = prompt_gen_mode
        if model_type not in [GenerationModelType.SDWEBUI_FORGE, GenerationModelType.SDWEBUI,GenerationModelType.COMFYUI]:
            self._setup_model()

    def get_description(self) -> str:
        """获取工具描述信息，包括支持的模型和功能说明"""
        global supported_models, supported_loras
        if self.model_type == GenerationModelType.SDWEBUI_FORGE:
            supported_models = ForgeAPI().get_models()
            supported_loras = ForgeAPI().get_loras()
            return json.dumps({
                "name": "ImageGeneratorTool",
                "description": f"""AI图像生成工具，
                                           model_name可只支持模型<{supported_models}>,
                                           根据用户描述的内容进行选择更合适的基础模型，如果无法选择到适应的基础模型就返回默认值:<F.1基础算法模型>,
                                           lora_name可支持模型<{supported_loras}>,
                                           根据用户的描述选择更合适的lora风格模型,支持两个lora配置(基础风格lora和场景lora),无lora可选时使用默认值:<aidmaImageUpraderv0.3>,
                                           如果用户的内容,在支持的模型中只有lora_name的模型符合，就使用基础模型<F.1基础算法模型>和对应的lora_name,
                                           model_name和lora_name必须是可支持模型中的名称,禁止修改成英文,""",
                "parameters": {
                    "prompt": {"type": "string", "description": "必须是英文内容的提示词", "required": True},
                    "lora_name": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "风格模型列表"
                    },
                    "model_name": {"type": "string", "description": "生图的基础模型"}
                }
            }, ensure_ascii=False, indent=2)
        elif self.model_type == GenerationModelType.COMFYUI:
            supported_models = ComfyuiAPI().get_models()
            return json.dumps({
                "name": "ImageGeneratorTool",
                "description": f"""AI图像生成工具，
                                           model_name可只支持模型<{supported_models}>,
                                           根据用户描述的内容进行选择更合适的基础模型，如果无法选择到适应的基础模型就返回默认值:<majicmixRealistic_v5.safetensors>,
                                           model_name必须是可支持模型中的名称,禁止修改成英文,""",
                "parameters": {
                    "prompt": {"type": "string", "description": "必须是英文内容的提示词", "required": True},
                    "model_name": {"type": "string", "description": "生图的基础模型"}
                }
            }, ensure_ascii=False, indent=2)


    def get_parameter_rules(self) -> str:
        """返回参数设置规则说明"""
        rules = """
    ImageGeneratorTool 参数配置指南：

    1. prompt (图像提示词)
       - 格式：英文提示词
       - 用途：描述想要生成的图像内容
       - 示例：
         * 用户输入："生成一个女孩的图片"
         * 参数配置：{"prompt": "a girl"}
       - 处理规则：自动将用户中文描述转换为英文提示词

    2. lora_name (风格模型)
       - 格式：模型名称列表
       - 用途：定义图像的风格特征
       - 示例：
         * 用户输入："生成一个女孩的图片"
         * 参数配置：{"lora_name": ["aidmaImageUpraderv0.3"]}
       - 处理规则：基于用户描述选择合适的风格模型
       - 默认值：aidmaImageUpraderv0.3

    3. model_name (基础模型)
       - 格式：模型名称
       - 用途：选择图像生成的基础模型
       - 示例：
         * 用户输入："生成一张港风风格的女生图像"
         * 参数配置：{"model_name": "港风风格模型"}
       - 处理规则：根据用户需求选择最适合的模型
       - 默认值：F.1基础算法模型
    """
        return rules

    def _setup_model(self):
        """设置模型配置，包括加载模型和设置优化参数"""
        model_info = self.MODELS[self.model_type]
        model_args = {
            "local_files_only": self.use_local,
            **model_info["model_args"]
        }

        # 设置量化配置
        if model_info.get("quantization"):
            model_args["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True
            )

        # 加载模型管道
        self.pipe = model_info["pipeline"].from_pretrained(
            model_info["path"],
            **model_args
        )
        self._enable_optimizations()

    def _enable_optimizations(self):
        """启用各种优化选项，提高性能"""
        if torch.cuda.is_available():
            # 启用各种优化功能
            if hasattr(self.pipe, 'enable_model_cpu_offload'):
                self.pipe.enable_model_cpu_offload()
            if hasattr(self.pipe, 'enable_vae_slicing'):
                self.pipe.enable_vae_slicing()
            if hasattr(self.pipe, 'enable_vae_tiling'):
                self.pipe.enable_vae_tiling()
            torch.backends.cuda.matmul.allow_tf32 = True

    async def run(self, **kwargs) -> list[str] | str | list[Any] | Any:
        """运行图像生成

        Args:
            **kwargs: 生成参数，包括prompt、model_name、lora_name等

        Returns:
            List[str]: 生成的图像路径列表
        """
        try:
            # SDWEBUI_FORGE模型的处理逻辑
            if self.model_type == GenerationModelType.SDWEBUI_FORGE:
                config = ForgeGenerationConfig(**kwargs)
                generator = ForgeImageGenerator()

                # 根据不同的提示词生成模式处理prompt
                if self.prompt_mode == "rag":
                    # 使用RAG模式生成提示词
                    path = os.path.join(os.path.dirname(__file__), "sd_prompt_rag")
                    prompt = await generate_stable_diffusion_prompt(rag=LightsRAG(path_name=path),
                                                                    user_input=kwargs.get("prompt"))
                elif self.prompt_mode == "llm":
                    # 使用LLM模式生成提示词
                    response = LLM().chat(images_tool_prompts, kwargs.get("prompt"))
                    positive_prompt, negative_prompt = get_prompts(response)
                    prompt = positive_prompt
                else:
                    prompt = kwargs.get("prompt")

                # 获取和处理模型配置
                base_model_config = ForgeAPI().get_model_config(kwargs.get("model_name"))
                base_trigger_word = base_model_config['trigger_word'] if base_model_config is not None else ""
                lora_prompt = ForgeAPI().add_loras_to_prompt(prompt, kwargs.get("lora_name"))
                final_prompt = f"{base_trigger_word}, {lora_prompt}" if base_trigger_word else lora_prompt

                # 生成图像
                img_path, info_text = generator.run(
                    prompt=final_prompt,
                    model_name=kwargs.get("model_name"),
                    sampling_method=base_model_config['sampling_method'] if base_model_config.get(
                        'sampling_method') else config.sampling_method,
                    steps=base_model_config['steps'] if base_model_config.get('steps') else config.steps,
                    width=base_model_config['width'] if base_model_config.get('width') else config.width,
                    height=base_model_config['height'] if base_model_config.get('height') else config.height,
                    batch_count=config.batch_count,
                    batch_size=config.batch_size,
                    cfg_scale=base_model_config['cfg_scale'] if base_model_config.get(
                        'cfg_scale') else config.cfg_scale,
                    seed=config.seed,
                )

                return img_path

            elif self.model_type == GenerationModelType.COMFYUI:
                config = ComfyuiGenerationConfig(**kwargs)
                generator = ComfyuiAPI()

                img_path = generator.run(
                    task_mode=kwargs.get("task_mode") if kwargs.get("task_mode") else config.task_mode,
                    model_name=kwargs.get("model_name"),
                    prompt_text=kwargs.get("prompt") if kwargs.get("prompt") else config.prompt + QUALITY_PROMPTS,
                    negative_prompt_text=kwargs.get("negative_prompt") if kwargs.get("negative_prompt") else config.negative_prompt,
                    image_name=kwargs.get("image_name") if kwargs.get("image_name") else config.image_name,
                    width=kwargs.get("width") if kwargs.get("width") else config.width,
                    height=kwargs.get("height") if kwargs.get("height") else config.height,
                    steps=kwargs.get("steps") if kwargs.get("steps") else config.steps,
                    batch_count=kwargs.get("batch_count") if kwargs.get("batch_count") else config.batch_size,
                    batch_size=kwargs.get("batch_size") if kwargs.get("batch_size") else config.batch_size,
                    sampling_method=kwargs.get("sampling_method") if kwargs.get("sampling_method") else config.sampling_method,
                    cfg_scale=kwargs.get("cfg_scale") if kwargs.get("cfg_scale") else config.cfg_scale,
                    output_dir=kwargs.get("output_dir") if kwargs.get("output_dir") else config.output_dir,
                )

                return img_path

            # FLUX或SD3.5模型的处理逻辑
            elif self.model_type in [GenerationModelType.FLUX_1_DEV, GenerationModelType.SD3_5_LARGE]:
                config = GenerationConfig(**kwargs)
                output_dir = os.path.join(os.getcwd(), config.output_dir)
                os.makedirs(output_dir, exist_ok=True)

                # 设置生成参数
                model_info = self.MODELS[self.model_type]
                generation_args = {
                    "prompt": kwargs.get("prompt", "") + QUALITY_PROMPTS,
                    "height": config.height,
                    "width": config.width,
                    "generator": torch.Generator("cuda").manual_seed(42),
                    "num_images_per_prompt": 1,
                    **model_info["generation_args"]
                }

                if model_info.get("use_negative_prompt"):
                    generation_args["negative_prompt"] = config.negative_prompt

                # 生成并保存图像
                images = self.pipe(**generation_args).images
                img_path = [self._save_image(img, idx, output_dir) for idx, img in enumerate(images)]
                return img_path

            else:
                return "不支持这个模型"

        except Exception as e:
            print(f"生成失败: {str(e)}")
            return None

    def _save_image(self, image, idx: int, output_dir: str) -> str:
        """保存生成的图像

        Args:
            image: 生成的图像对象
            idx: 图像索引
            output_dir: 输出目录

        Returns:
            str: 保存的图像路径
        """
        path = os.path.join(output_dir, f"generated_{idx}.png")
        image.save(path)
        return path