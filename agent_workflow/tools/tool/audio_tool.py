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
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from dataclasses import dataclass
from datetime import datetime
import os
import shutil
import time
import json
import asyncio
from pydub import AudioSegment
from gradio_client import Client, handle_file

from agent_workflow.tools.tool.base import BaseTool
from agent_workflow.utils import loadingInfo
from config.tool_config import F5_TTS_PORT, GPT_SoVITS_PORT


class TTSModel(str, Enum):
    """TTS模型枚举类型"""
    F5_TTS = "f5-tts"
    SOVITS = "sovits"

    @classmethod
    def list_models(cls) -> List[str]:
        """获取所有可用的TTS模型列表"""
        return [model.value for model in cls]


class SoVitsConfig(BaseModel):
    """GPT-SoVITS模型配置"""
    character: str = Field("Hutao", description="角色名称")
    emotion: str = Field("default", description="情感类型")
    text_lang: str = Field("auto", description="文本语言")
    cut_method: str = Field("auto_cut", description="文本切割方法")
    max_len: int = Field(50, description="文本切割最大长度")
    batch_size: int = Field(10, description="批处理大小")
    seed: int = Field(-1, description="随机种子")
    parallel: bool = Field(True, description="是否并行推理")
    top_k: float = Field(5, description="采样Top K")
    top_p: float = Field(0.8, description="采样Top P")
    temperature: float = Field(0.8, description="采样温度")
    repetition_penalty: float = Field(1.35, description="重复惩罚")


@dataclass
class TTSResponse:
    """TTS响应数据类"""
    audio_path: str
    spectrogram: Optional[Dict] = None
    reference_text: Optional[str] = None


class AudioConfig(BaseModel):
    """音频配置模型扩展"""
    model: TTSModel = Field(TTSModel.SOVITS, description="TTS模型选择")
    ref_text: str = Field("", description="参考文本")
    gen_text: str = Field(..., description="要生成的文本内容")
    remove_silence: bool = Field(False, description="是否移除静音")
    cross_fade_duration: float = Field(0.15, description="交叉淡入淡出持续时间")
    speed: float = Field(1.0, description="语速")
    sovits_config: Optional[SoVitsConfig] = Field(None, description="GPT-SoVITS配置")


class AudioTool(BaseTool):
    """
    音频处理工具类

    功能：
    1. 文本转语音(TTS)处理
    2. 音频导出转换
    3. 音频参数调整
    4. 静音移除
    """
    def __init__(self,
                 f5_host: str = f"http://127.0.0.1:{F5_TTS_PORT}",
                 sovits_host: str = f"http://127.0.0.1:{GPT_SoVITS_PORT}",
                 model: TTSModel = TTSModel.SOVITS,
                 timeout: float = 60.0,
                 project_root: Optional[str] = None):
        """
        初始化音频工具

        Args:
            f5_host: F5-tts服务器地址
            sovits_host: GPT-SoVITS服务器地址
            model: TTS模型选择
            timeout: 请求超时时间（秒）
            project_root: 项目根目录路径
        """
        self._f5_host = f5_host
        self._sovits_host = sovits_host
        self.model = model
        self.timeout = timeout
        self.logger = loadingInfo("audio_tool")
        self.project_root = project_root or self._find_project_root()

        # 延迟初始化的客户端
        self._client = None
        self._sovits_client = None

        # 确保必要的目录存在
        self.upload_dir = os.path.join(self.project_root, "upload")
        self.output_dir = os.path.join(self.project_root, "output")
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)


    @property
    def all_characters(self) -> List[str]:
        """获取所有可用角色列表"""
        if self.sovits_client is not None:
            try:
                # 调用API获取角色列表
                result = self.sovits_client.predict(
                    api_name="/change_character_list"
                )
                if isinstance(result, tuple) and len(result) > 0:
                    return result[0]
            except Exception as e:
                self.logger.warning(f"获取角色列表失败: {e}")
        return []

    def list_characters(self) -> None:
        """列出所有可用角色"""
        characters = self.all_characters
        if not characters:
            print("未能获取角色列表，请确保服务已启动")
            return

        print("\n可用角色列表:")
        for char in sorted(characters):  # 按字母顺序排序
            print(f"- {char}")
        print(f"\n总计: {len(characters)} 个角色")

    @property
    def client(self):
        """延迟初始化的F5-TTS客户端"""
        if self._client is None:
            try:
                self._client = Client(self._f5_host)
            except Exception as e:
                self.logger.warning(f"Failed to initialize F5-TTS client: {e}")
        return self._client

    @property
    def sovits_client(self):
        """延迟初始化的GPT-SoVITS客户端"""
        if self._sovits_client is None:
            try:
                self._sovits_client = Client(self._sovits_host)
            except Exception as e:
                self.logger.warning(f"Failed to initialize GPT-SoVITS client: {e}")
        return self._sovits_client

    def get_description(self) -> str:
        """
        获取工具描述信息，用于任务规划

        Returns:
            JSON格式的工具描述字符串
        """
        tool_info = {
            "name": "AudioTool",
            "description": "将文本内容转换为语音的工具，支持多种TTS模型和角色声音。不提供参考音频时默认使用角色声音生成。",
            "parameters": {
                "text": {
                    "type": "string",
                    "description": "要转换为语音的文本内容",
                    "required": True,
                    "example": "从引号中提取的文本，如：'你好，世界'"
                },
                "audio": {
                    "type": "string",
                    "description": "可选的参考音频文件路径，如果提供则使用声音克隆",
                    "required": False,
                    "example": "reference.mp3"
                },
                "character": {
                    "type": "string",
                    "description": "游戏角色名称（当不使用参考音频时有效）",
                    "required": False,
                    "default": "Hutao",
                    "example": "派蒙-30h"
                },
                "speed": {
                    "type": "number",
                    "description": "语音速度，范围0.5-2.0",
                    "required": False,
                    "default": 1.0,
                    "minimum": 0.5,
                    "maximum": 2.0,
                    "example": 1.2
                },
                "text_lang": {
                    "type": "string",
                    "description": "文本语言（当不使用参考音频时有效）",
                    "required": False,
                    "default": "auto",
                    "enum": ["auto", "zh", "en", "ja"],
                    "example": "auto"
                }
            },
            "model_specific_examples": {
                "default": {
                    "query": "生成'你好，世界'的语音",
                    "parameters": {
                        "text": "你好，世界",
                        "character": "Hutao"
                    }
                },
                "character": {
                    "query": "用派蒙的声音说'今天天气真好'",
                    "parameters": {
                        "text": "今天天气真好",
                        "character": "派蒙-30h",
                        "speed": 1.0
                    }
                }
            }
        }
        return json.dumps(tool_info, ensure_ascii=False, indent=2)


    def _find_project_root(self) -> Optional[str]:
        """
        智能查找项目根目录

        查找策略:
        1. 首先检查当前工作目录
        2. 检查当前文件的父级目录
        3. 检查当前工作目录的父级目录
        4. 如果都没找到,自动在当前工作目录创建必要的目录结构

        Returns:
            找到的项目根目录路径
        """
        # 定义要查找的必需目录
        REQUIRED_DIRS = ['upload', 'output']

        def has_required_dirs(path: str) -> bool:
            """检查目录是否包含必需的子目录"""
            return all(os.path.exists(os.path.join(path, d)) for d in REQUIRED_DIRS)

        def create_project_structure(path: str) -> str:
            """创建项目目录结构"""
            for d in REQUIRED_DIRS:
                dir_path = os.path.join(path, d)
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path)
                    self.logger.info(f"Created directory: {dir_path}")
            return path

        cwd = os.getcwd()
        if has_required_dirs(cwd):
            self.logger.info(f"Found project root in current working directory: {cwd}")
            return cwd

        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        current_dir = current_file_dir
        while True:
            if has_required_dirs(current_dir):
                self.logger.info(f"Found project root in parent directory: {current_dir}")
                return current_dir
            parent = os.path.dirname(current_dir)
            if parent == current_dir:  # 已到达根目录
                break
            current_dir = parent

        current_dir = cwd
        while True:
            if has_required_dirs(current_dir):
                self.logger.info(f"Found project root in working directory parent: {current_dir}")
                return current_dir
            parent = os.path.dirname(current_dir)
            if parent == current_dir:  # 已到达根目录
                break
            current_dir = parent

        self.logger.info(f"Creating new project structure in: {cwd}")
        return create_project_structure(cwd)


    async def _get_output_path(self, original_filename: str) -> str:
        """
        生成输出文件路径

        Args:
            original_filename: 原始文件名

        Returns:
            输出文件路径
        """
        current_date = datetime.now().strftime('%Y-%m-%d')
        timestamp = int(time.time() * 1000)
        original_name = os.path.splitext(original_filename)[0]
        daily_output_dir = os.path.join(self.output_dir, current_date)
        os.makedirs(daily_output_dir, exist_ok=True)
        return os.path.join(daily_output_dir, f"{original_name}-output-{timestamp}.wav")

    async def _cleanup_temp_files(self, *file_paths):
        """
        清理临时文件

        Args:
            file_paths: 要清理的文件路径列表
        """
        for path in file_paths:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
                    self.logger.info(f"Cleaned up temp files: {path}")

                    parent_dir = os.path.dirname(path)
                    if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                        os.rmdir(parent_dir)
                        self.logger.info(f"Removed empty directory: {parent_dir}")
            except Exception as e:
                self.logger.warning(f"Error cleaning up {path}: {str(e)}")

    async def sovits_tts(self, config: AudioConfig) -> Dict[str, Any]:
        """GPT-SoVITS模型的TTS处理"""
        try:
            # 获取SoVITS配置
            sovits_config = config.sovits_config or SoVitsConfig()

            try:
                # 切换角色
                await asyncio.to_thread(
                    self.sovits_client.predict,
                    str(sovits_config.character),
                    api_name="/load_character_emotions"
                )

                # 设置情感
                await asyncio.to_thread(
                    self.sovits_client.predict,
                    str(sovits_config.character),  # 转换为字符串
                    str(sovits_config.emotion),  # 转换为字符串
                    api_name="/change_character_list"
                )

                # 生成语音文本
                await asyncio.to_thread(
                    self.sovits_client.predict,
                    str(config.gen_text),  # 转换为字符串
                    api_name="/lambda"
                )

                # 生成音频文件，所有参数转换为字符串或基本类型
                result = await asyncio.to_thread(
                    self.sovits_client.predict,
                    str(config.gen_text),  # 文本
                    str(sovits_config.character),  # 角色
                    str(sovits_config.emotion),  # 情感
                    None,  # ref_audio
                    "",  # ref_text
                    "auto",  # ref_lang
                    float(config.speed),  # 语速
                    str(sovits_config.text_lang),  # 语言
                    str(sovits_config.cut_method),  # 切割方法
                    int(sovits_config.max_len),  # 长度
                    int(sovits_config.batch_size),  # 批大小
                    int(sovits_config.seed),  # 种子
                    bool(sovits_config.parallel),  # 并行
                    float(sovits_config.top_k),  # top_k
                    float(sovits_config.top_p),  # top_p
                    float(sovits_config.temperature),  # 温度
                    float(sovits_config.repetition_penalty),  # 重复惩罚
                    api_name="/get_audio"
                )

                self.logger.info(f"API result type: {type(result)}")
                self.logger.info(f"API result content: {result}")

                if result and isinstance(result, str) and os.path.exists(result):
                    # 生成输出路径
                    current_date = datetime.now().strftime('%Y-%m-%d')
                    daily_output_dir = os.path.join(self.output_dir, current_date)
                    os.makedirs(daily_output_dir, exist_ok=True)

                    # 生成新的文件名
                    timestamp = int(time.time() * 1000)
                    cleaned_text = "".join(c for c in config.gen_text[:10] if c.isalnum() or c in '，。！？')
                    cleaned_text = cleaned_text.strip().replace(" ", "_")
                    file_name = f"{sovits_config.character}_{cleaned_text}_{timestamp}.wav"
                    output_path = os.path.join(daily_output_dir, file_name)

                    # 复制文件到输出目录
                    shutil.copy2(result, output_path)

                    # 清理临时文件
                    await self._cleanup_temp_files(result)

                    return {
                        "success": True,
                        "output_file": output_path,
                    }
                else:
                    raise ValueError(f"Invalid result from API: {result}")

            except Exception as api_error:
                self.logger.error(f"API call failed: {str(api_error)}")
                return {
                    "success": False,
                    "error": f"API call failed: {str(api_error)}"
                }

        except Exception as e:
            self.logger.error("SoVITS TTS processing error", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def change_character(self, character_name: str):
        """更改当前角色"""
        try:
            await asyncio.to_thread(
                self.sovits_client.predict,
                character_name,  # 角色名称
                "default",  # emotion参数
                api_name="/change_character_list"
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to change character: {e}")
            return False

    async def load_character_emotions(self):
        """加载角色的情感列表"""
        try:
            result = await asyncio.to_thread(
                self.sovits_client.predict,
                api_name="/load_character_emotions"
            )
            return result
        except Exception as e:
            self.logger.error(f"Failed to load character emotions: {e}")
            return None

    async def basic_tts(self, input_file: str, config: AudioConfig) -> Dict[str, Any]:
        """根据选择的模型调用相应的TTS处理方法"""
        global temp_path
        if config.model == TTSModel.SOVITS:
            return await self.sovits_tts(config)
        else:
            max_retries = 3
            retry_delay = 2  # 秒

            try:
                input_path = os.path.join(self.upload_dir, input_file)
                temp_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "gradio", "audio_tool")
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, input_file)

                # 验证输入
                if not os.path.exists(input_path):
                    return {
                        "success": False,
                        "error": f"Input files not found: {input_path}",
                        "project_root": self.project_root,
                        "upload_dir": self.upload_dir
                    }

                # 验证音频文件格式
                file_ext = os.path.splitext(input_file)[1].lower()
                if file_ext not in ['.mp3', '.wav', '.flac', '.ogg', '.m4a']:
                    return {
                        "success": False,
                        "error": f"Unsupported audio format: {file_ext}. Supported formats: .mp3, .wav, .flac, .ogg, .m4a"
                    }

                # 验证配置参数
                if not config.gen_text.strip():
                    return {
                        "success": False,
                        "error": "Generation text cannot be empty"
                    }

                # 复制到临时目录
                shutil.copy2(input_path, temp_path)
                self.logger.info(f"Copied to temp location: {temp_path}")

                # 处理音频
                file_data = handle_file(temp_path)

                # 将配置参数转换为正确的类型并验证范围
                predict_kwargs = {
                    "ref_audio_input": file_data,  # 文件数据
                    "ref_text_input": str(config.ref_text),  # 参考文本
                    "gen_text_input": str(config.gen_text),  # 生成文本
                    "remove_silence": bool(config.remove_silence),  # 是否移除静音
                    "cross_fade_duration_slider": max(0.0, min(float(config.cross_fade_duration), 1.0)),  # 限制范围0-1
                    "speed_slider": max(0.5, min(float(config.speed), 2.0)),  # 限制范围0.5-2
                    "api_name": "/basic_tts"
                }

                # 重试机制
                for attempt in range(max_retries):
                    try:
                        result = await asyncio.to_thread(
                            self.client.predict,
                            **predict_kwargs
                        )

                        if isinstance(result, tuple) and len(result) == 3:
                            temp_audio_path, temp_spectrogram, ref_text = result

                            # 验证生成的文件
                            if not os.path.exists(temp_audio_path):
                                raise FileNotFoundError("Generated audio files not found")

                            # 获取输出路径并确保目录存在
                            output_path = await self._get_output_path(input_file)
                            os.makedirs(os.path.dirname(output_path), exist_ok=True)

                            # 复制文件
                            shutil.copy2(temp_audio_path, output_path)

                            # 验证复制的文件
                            if not os.path.exists(output_path):
                                raise FileNotFoundError("Failed to copy output files")

                            # 清理临时文件
                            await self._cleanup_temp_files(temp_path, temp_audio_path)

                            return {
                                "success": True,
                                "output_file": output_path,
                                "spectrogram": temp_spectrogram,
                                "reference_text": ref_text
                            }
                        else:
                            raise ValueError("Unexpected API response format")

                    except Exception as e:
                        self.logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                        else:
                            raise  # 最后一次尝试失败时抛出异常

            except Exception as e:
                self.logger.error("TTS processing error", exc_info=True)
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "suggestion": "Please check the server status and configuration"
                }
                return {
                    "success": False,
                    "error": "TTS processing failed",
                    "details": error_details,
                    "project_root": self.project_root
                }

            finally:
                # 确保清理所有临时文件
                try:
                    await self._cleanup_temp_files(temp_path)
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup temp files: {str(e)}")

    async def export(self, audio_file: str, format: str = 'wav',
                     sample_rate: int = 44100) -> str:
        """
        导出音频为指定格式

        Args:
            audio_file: 音频文件路径
            format: 导出格式
            sample_rate: 采样率

        Returns:
            导出文件路径
        """
        audio = AudioSegment.from_file(audio_file)
        output_path = f"{os.path.splitext(audio_file)[0]}.{format}"

        audio = audio.set_frame_rate(sample_rate)
        await asyncio.to_thread(audio.export, output_path, format=format)
        return output_path

    async def run(self, **kwargs) -> str | dict[str, Any]:
        """执行TTS任务并返回输出文件路径"""
        try:
            # 获取文本内容
            text = kwargs.get("text", "").strip()
            if not text:
                query = kwargs.get("query", "").strip()
                import re
                match = re.search(r'"([^"]*)"', query)
                if match:
                    text = match.group(1)
                else:
                    return {"error": "Missing text parameter and cannot extract text from query"}

            # 检查是否提供了参考音频
            input_file_path = kwargs.get("audio") or kwargs.get("input_file")

            # 根据是否有参考音频自动选择模型
            if input_file_path and not kwargs.get("model") == TTSModel.SOVITS:
                # 有参考音频且未指定使用SOVITS，使用F5-TTS模型
                model = TTSModel.F5_TTS
                input_file_path = input_file_path.replace('upload/', '')
                config = AudioConfig(
                    model=model,
                    gen_text=text,
                    ref_text=kwargs.get("ref_text", ""),
                    remove_silence=kwargs.get("remove_silence", False),
                    cross_fade_duration=kwargs.get("cross_fade_duration", 0.15),
                    speed=kwargs.get("speed", 1.0)
                )
                file_name = os.path.basename(input_file_path)
                result = await self.basic_tts(file_name, config)
            else:
                # 无参考音频或指定使用SOVITS，使用GPT-SoVITS模型
                model = TTSModel.SOVITS
                character = kwargs.get("character", "Hutao")

                # 先切换角色
                await self.change_character(character)

                # 生成文件名：角色_生成的语音内容_时间毫秒值.wav
                timestamp = int(time.time() * 1000)
                # 清理文本内容，只保留前10个字符，并移除特殊字符
                cleaned_text = "".join(c for c in text[:10] if c.isalnum() or c in '，。！？')
                cleaned_text = cleaned_text.strip().replace(" ", "_")
                virtual_filename = f"{character}_{cleaned_text}_{timestamp}"

                sovits_config = SoVitsConfig(
                    character=character,
                    emotion=kwargs.get("emotion", "default"),
                    text_lang=kwargs.get("text_lang", "auto"),
                    cut_method=kwargs.get("cut_method", "auto_cut"),
                    max_len=kwargs.get("max_len", 50),
                    batch_size=kwargs.get("batch_size", 10),
                    seed=kwargs.get("seed", -1),
                    parallel=kwargs.get("parallel", True),
                    top_k=kwargs.get("top_k", 5),
                    top_p=kwargs.get("top_p", 0.8),
                    temperature=kwargs.get("temperature", 0.8),
                    repetition_penalty=kwargs.get("repetition_penalty", 1.35)
                )
                config = AudioConfig(
                    model=model,
                    gen_text=text,
                    speed=kwargs.get("speed", 1.0),
                    sovits_config=sovits_config
                )

                result = await self.basic_tts(virtual_filename, config)

            # 返回结果
            if result["success"]:
                return result["output_file"]
            else:
                return {"error": result.get("error", "Unknown error occurred")}

        except Exception as e:
            self.logger.error("Error in run method", exc_info=True)
            return {"error": f"Error in run method: {str(e)}"}
