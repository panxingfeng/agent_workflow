from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from dataclasses import dataclass
from datetime import datetime
import os
import shutil
import time
import json
import asyncio
from pydub import AudioSegment
from gradio_client import Client, handle_file

from agent_workflow.utils import loadingInfo


class TTSModel(str, Enum):
    """TTS模型枚举类型"""
    F5_TTS = "f5-tts"
    E2_TTS = "e2-tts"
    CUSTOM = "custom"

    @classmethod
    def list_models(cls) -> List[str]:
        """获取所有可用的TTS模型列表"""
        return [model.value for model in cls]


@dataclass
class TTSResponse:
    """TTS响应数据类"""
    audio_path: str
    spectrogram: Optional[Dict] = None
    reference_text: Optional[str] = None


class AudioConfig(BaseModel):
    """音频配置模型"""
    ref_text: str = Field("", description="参考文本")
    gen_text: str = Field(..., description="要生成的文本内容")
    remove_silence: bool = Field(False, description="是否移除静音")
    cross_fade_duration: float = Field(0.15, description="交叉淡入淡出持续时间")
    speed: float = Field(1.0, description="语速")

    class Config:
        """Pydantic配置"""
        validate_assignment = True  # 启用赋值验证

    @validator('ref_text', 'gen_text', pre=True)
    def validate_text(cls, v):
        """验证文本输入"""
        return str(v).strip()

    @validator('cross_fade_duration', 'speed', pre=True)
    def validate_float(cls, v):
        """验证浮点数值"""
        try:
            value = float(v)
            if value <= 0:
                raise ValueError("Value must be positive")
            return value
        except (TypeError, ValueError):
            raise ValueError(f"Invalid float value: {v}")

    @validator('remove_silence', pre=True)
    def validate_boolean(cls, v):
        """验证布尔值"""
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes')
        return bool(v)


class AudioTool:
    """
    音频处理工具类

    功能：s
    1. 文本转语音(TTS)处理
    2. 音频导出转换
    3. 音频参数调整
    4. 静音移除
    """

    def __init__(self,
                 host: str = "http://127.0.0.1:7860",
                 model: TTSModel = TTSModel.F5_TTS,
                 timeout: float = 60.0,
                 project_root: Optional[str] = None):
        """
        初始化音频工具

        Args:
            host: API服务器地址
            model: TTS模型选择
            timeout: 请求超时时间（秒）
            project_root: 项目根目录路径
        """
        self.client = Client(host)
        self.model = model
        self.timeout = timeout
        self.logger = loadingInfo()
        # 设置项目根目录
        self.project_root = project_root or self._find_project_root()
        if not self.project_root:
            raise ValueError("Could not find project root directory")

        # 确保必要的目录存在
        self.upload_dir = os.path.join(self.project_root, "upload")
        self.output_dir = os.path.join(self.project_root, "output")
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

    def get_description(self) -> str:
        """
        获取工具描述信息，用于任务规划

        Returns:
            JSON格式的工具描述字符串
        """
        tool_info = {
            "name": "AudioTool",
            "description": "将文本内容转换为语音的工具",
            "parameters": {
                "text": {
                    "type": "string",
                    "description": "要转换为语音的文本内容",
                    "required": True,
                    "example": "从引号中提取的文本，如：'你好，世界'"
                },
                "audio": {
                    "type": "string",
                    "description": "作为声音参考的音频文件路径",
                    "required": True,
                    "example": "upload/特朗普.mp3"
                }
            },
            "example_queries": [
                "我想生成'你好，世界'的语音",
                "帮我把'今天天气真好'转成语音",
                "生成一段'欢迎光临'的语音"
            ]
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
                    self.logger.info(f"Cleaned up temp file: {path}")

                    parent_dir = os.path.dirname(path)
                    if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                        os.rmdir(parent_dir)
                        self.logger.info(f"Removed empty directory: {parent_dir}")
            except Exception as e:
                self.logger.warning(f"Error cleaning up {path}: {str(e)}")

    async def basic_tts(self, input_file: str, config: AudioConfig) -> Dict[str, Any]:
        """
        基础TTS处理，带有重试和错误处理机制

        Args:
            input_file: 输入文件路径
            config: 音频配置对象

        Returns:
            处理结果字典
        """
        global temp_path
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
                    "error": f"Input file not found: {input_path}",
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
                            raise FileNotFoundError("Generated audio file not found")

                        # 获取输出路径并确保目录存在
                        output_path = await self._get_output_path(input_file)
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)

                        # 复制文件
                        shutil.copy2(temp_audio_path, output_path)

                        # 验证复制的文件
                        if not os.path.exists(output_path):
                            raise FileNotFoundError("Failed to copy output file")

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
        """
        执行TTS任务并返回输出文件路径

        Args:
            **kwargs: 关键字参数，包括：
                input_file: 输入音频文件完整路径或文件名
                text: 要生成的文本内容
                ref_text: 参考文本（可选）
                remove_silence: 是否移除静音（可选）
                cross_fade_duration: 交叉淡入淡出持续时间（可选）
                speed: 语速（可选）

        Returns:
            如果成功，返回输出文件路径字符串
            如果失败，返回包含错误信息的字典
        """
        try:
            # 从kwargs中获取音频文件路径
            input_file_path = kwargs.get("audio") or kwargs.get("input_file")
            if not input_file_path:
                return {"error": "Required parameter 'input_file' or 'audio' missing"}

            # 清理路径中的 'upload/' 前缀
            input_file_path = input_file_path.replace('upload/', '')

            # 获取生成文本（从query或text参数）
            text = kwargs.get("text", "").strip()
            if not text:
                # 尝试从 query 中获取文本
                query = kwargs.get("query", "").strip()
                # 提取引号中的文本
                import re
                match = re.search(r'"([^"]*)"', query)
                if match:
                    text = match.group(1)
                else:
                    return {"error": "Missing text parameter and cannot extract text from query"}

            # 从kwargs构建AudioConfig
            config = AudioConfig(
                gen_text=text,  # 使用提取的文本
                ref_text=kwargs.get("ref_text", ""),
                remove_silence=kwargs.get("remove_silence", False),
                cross_fade_duration=kwargs.get("cross_fade_duration", 0.15),
                speed=kwargs.get("speed", 1.0)
            )

            # 获取文件名
            file_name = os.path.basename(input_file_path)

            # 构建目标路径
            source_path = os.path.join(self.upload_dir, file_name)

            self.logger.info(f"Processing audio file: {source_path}")
            self.logger.info(f"Generating text: {text}")

            # 执行TTS处理，只传入文件名
            result = await self.basic_tts(file_name, config)

            # 返回结果
            if result["success"]:
                return result["output_file"]
            else:
                return {"error": result.get("error", "Unknown error occurred")}

        except Exception as e:
            self.logger.error("Error in run method", exc_info=True)
            return {"error": f"Error in run method: {str(e)}"}

    def get_parameter_rules(self) -> str:
        """返回音频工具的参数设置规则"""
        rules = """
        AudioTool: 文本转语音工具，将输入的文本内容转换成语音。

        使用场景:
        1. 用户明确表示要"生成语音"、"转成语音"等需求
        2. 需要将文本内容转换为音频
        3. 通常文本内容在引号中，如:"你好，世界"

        参数说明:
        {
            "text": 必填，要转换成语音的文本内容。从用户输入的引号中提取。
            "audio": 必填，作为声音参考的音频文件路径，从用户附件中获取。
        }

        示例:
        用户输入: "我想生成'你好，世界'的语音"
        附件信息: audio: upload/特朗普.mp3

        返回参数:
        {
            "known_facts": "用户想要生成'你好，世界'的语音文件",
            "tools_needed": ["AudioTool"],
            "parameters": {
                "AudioTool": {
                    "text": "你好，世界",
                    "audio": "upload/特朗普.mp3"
                }
            }
        }
        """
        return rules
