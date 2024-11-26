import os
import shutil
import logging
from datetime import datetime
import time
from typing import Optional, Any, Dict, List, Tuple, BinaryIO, Iterator
from enum import Enum
from dataclasses import dataclass
from pydantic import BaseModel, Field
from gradio_client import Client, handle_file
from pydub import AudioSegment
import numpy as np
import librosa.feature


@dataclass
class TTSResponse:
    audio_path: str
    spectrogram: Optional[Dict] = None
    reference_text: Optional[str] = None


class TTSModel(str, Enum):
    F5_TTS = "f5-tts"
    E2_TTS = "e2-tts"
    CUSTOM = "custom"

    @classmethod
    def list_models(cls) -> list[str]:
        return [model.value for model in cls]


class AudioConfig(BaseModel):
    ref_text: str = Field("", description="参考文本")
    gen_text: str = Field(..., description="要生成的文本内容")
    remove_silence: bool = Field(False, description="是否移除静音")
    cross_fade_duration: float = Field(0.15, description="交叉淡入淡出持续时间")
    speed: float = Field(1.0, description="语速")


class AudioToolClient:
    def __init__(self,
                 host: str = "http://127.0.0.1:7860",
                 model: TTSModel = TTSModel.F5_TTS,
                 timeout: float = 60.0):
        self.client = Client(host)
        self.model = model
        self.timeout = timeout
        self._setup_logging()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def _get_output_path(self, project_dir: str, original_filename: str) -> str:
        current_date = datetime.now().strftime('%Y-%m-%d')
        timestamp = int(time.time() * 1000)
        original_name = os.path.splitext(original_filename)[0]
        output_dir = os.path.join(project_dir, "output", current_date)
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, f"{original_name}-output-{timestamp}.wav")

    def _cleanup_temp_files(self, *file_paths):
        for path in file_paths:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
                    self.logger.info(f"Cleaned up temp file: {path}")

                    # Try to remove parent directory if empty
                    parent_dir = os.path.dirname(path)
                    if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                        os.rmdir(parent_dir)
                        self.logger.info(f"Removed empty directory: {parent_dir}")
            except Exception as e:
                self.logger.warning(f"Error cleaning up {path}: {str(e)}")

    def switch_model(self, model_type: TTSModel):
        try:
            result = self.client.predict(str(model_type.value), api_name="/switch_tts_model")
            self.model = model_type
            return result
        except Exception as e:
            self.logger.error(f"Error switching model: {str(e)}")
            raise

    def set_custom_model(self, ckpt_path: str, vocab_path: str):
        try:
            return self.client.predict(
                custom_ckpt_path=ckpt_path,
                custom_vocab_path=vocab_path,
                api_name="/set_custom_model"
            )
        except Exception as e:
            self.logger.error(f"Error setting custom model: {str(e)}")
            raise

    def basic_tts(self, input_file: str, config: AudioConfig) -> Dict[str, Any]:
        try:
            # Setup paths
            project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            input_path = os.path.join(project_dir, "upload", input_file)
            temp_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "gradio", "audio_tool")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, input_file)

            # Validate input
            if not os.path.exists(input_path):
                return {"success": False, "error": f"Input file not found: {input_path}"}

            # Copy to temp directory
            shutil.copy2(input_path, temp_path)
            self.logger.info(f"Copied to temp location: {temp_path}")

            # Process audio
            file_data = handle_file(temp_path)
            result = self.client.predict(
                ref_audio_input=file_data,
                ref_text_input=config.ref_text,
                gen_text_input=config.gen_text,
                remove_silence=config.remove_silence,
                cross_fade_duration_slider=config.cross_fade_duration,
                speed_slider=config.speed,
                api_name="/basic_tts"
            )

            # Handle result
            if isinstance(result, tuple) and len(result) == 3:
                temp_audio_path, temp_spectrogram, ref_text = result
                output_path = self._get_output_path(project_dir, input_file)
                shutil.copy2(temp_audio_path, output_path)

                self._cleanup_temp_files(temp_path, temp_audio_path)

                return {
                    "success": True,
                    "output_file": output_path,
                    "spectrogram": temp_spectrogram,
                    "reference_text": ref_text
                }
            else:
                return {"success": False, "error": "Unexpected API response format"}

        except Exception as e:
            self.logger.error("TTS processing error", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "details": "Check logs for full traceback"
            }

    def generate_multistyle_speech(self,
                                   text: str,
                                   ref_audios: List[str],
                                   ref_texts: List[str],
                                   speech_types: List[str],
                                   remove_silence: bool = True) -> Tuple[str, List[str]]:
        if len(ref_audios) != len(ref_texts) or len(ref_texts) != len(speech_types):
            raise ValueError("ref_audios, ref_texts and speech_types must have same length")

        n = 100  # API requirement
        params = {
            "gen_text": text,
            "param_301": remove_silence
        }

        # Pad and add parameters
        for i, (speech_type, ref_audio, ref_text) in enumerate(
                zip(
                    speech_types + ["Regular"] * (n - len(speech_types)),
                    ref_audios + [ref_audios[0]] * (n - len(ref_audios)),
                    ref_texts + [ref_texts[0]] * (n - len(ref_texts))
                ),
                start=1
        ):
            params[f"param_{i}"] = speech_type
            if i <= n:
                params[f"param_{i + 100}"] = handle_file(ref_audio)
                params[f"param_{i + 200}"] = ref_text

        return self.client.predict(api_name="/generate_multistyle_speech", **params)

    def chat_functions(self):
        return {
            "load_model": lambda: self.client.predict(api_name="/load_chat_model"),
            "update_prompt": lambda prompt: self.client.predict(new_prompt=prompt, api_name="/update_system_prompt"),
            "clear_chat": lambda: self.client.predict(api_name="/clear_conversation"),
            "process_input": lambda audio, text, history=None: self.client.predict(
                audio_path=audio,
                text=text,
                history=history or [],
                api_name="/process_audio_input"
            ),
            "generate_response": lambda history, ref_audio, ref_text, remove_silence=True: self.client.predict(
                history=history,
                ref_audio=ref_audio,
                ref_text=ref_text,
                remove_silence=remove_silence,
                api_name="/generate_audio_response"
            )
        }

    def batch_process(self, files: List[str], config: AudioConfig) -> List[Dict[str, Any]]:
        """批量处理音频文件"""
        results = []
        for file in files:
            try:
                result = self.basic_tts(file, config)
                results.append(result)
                self.logger.info(f"Processed {file}")
            except Exception as e:
                self.logger.error(f"Error processing {file}: {str(e)}")
                results.append({"success": False, "error": str(e), "file": file})
        return results

    def split_audio(self, audio_file: str, segment_duration: float) -> List[str]:
        """
        将音频切分为固定时长片段

        Args:
            audio_file: 输入音频文件
            segment_duration: 片段时长(秒)

        Returns:
            片段文件路径列表
        """
        audio = AudioSegment.from_file(audio_file)
        segments = []

        for i, start in enumerate(range(0, len(audio), int(segment_duration * 1000))):
            end = start + int(segment_duration * 1000)
            segment = audio[start:end]

            segment_path = f"{os.path.splitext(audio_file)[0]}_segment_{i}.wav"
            segment.export(segment_path, format="wav")
            segments.append(segment_path)

        return segments

    def concat_audio(self, audio_files: List[str]) -> str:
        """合并多个音频文件"""
        combined = AudioSegment.empty()
        output_path = f"combined_{int(time.time())}.wav"

        for file in audio_files:
            segment = AudioSegment.from_file(file)
            combined += segment

        combined.export(output_path, format="wav")
        return output_path

    def style_transfer(self, source_audio: str, target_style: str, strength: float = 0.8) -> str:
        """
        音频风格迁移

        Args:
            source_audio: 源音频
            target_style: 目标风格音频
            strength: 迁移强度
        """
        try:
            result = self.client.predict(
                source_audio,
                target_style,
                strength,
                api_name="/style_transfer"
            )
            return result[0] if isinstance(result, tuple) else result
        except Exception as e:
            self.logger.error(f"Style transfer error: {str(e)}")
            raise

    def stream_process(self, input_stream: BinaryIO, chunk_size: int = 1024,
                       callback: Optional[callable] = None) -> Iterator[bytes]:
        """
        实时音频流处理

        Args:
            input_stream: 输入音频流
            chunk_size: 数据块大小
            callback: 处理回调函数
        """
        while True:
            chunk = input_stream.read(chunk_size)
            if not chunk:
                break

            processed_chunk = self.client.predict(
                chunk,
                api_name="/process_stream"
            )

            if callback:
                callback(processed_chunk)
            yield processed_chunk

    def export(self, audio_file: str, format: str = 'wav',
               sample_rate: int = 44100) -> str:
        """导出音频为指定格式"""
        audio = AudioSegment.from_file(audio_file)
        output_path = f"{os.path.splitext(audio_file)[0]}.{format}"

        audio = audio.set_frame_rate(sample_rate)
        audio.export(output_path, format=format)
        return output_path

    def analyze_audio(self, audio_file: str) -> Dict[str, Any]:
        """
        分析音频特征
        返回音高、音量、语速等特征
        """
        y, sr = librosa.load(audio_file)

        # 提取特征
        tempo = librosa.beat.tempo(y=y, sr=sr)[0]
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        rms = librosa.feature.rms(y=y)[0]

        return {
            "tempo": float(tempo),
            "avg_pitch": float(np.mean(pitches[magnitudes > 0])),
            "avg_volume": float(np.mean(rms)),
            "duration": float(len(y) / sr),
            "sample_rate": sr
        }
