import json
from typing import Dict, Any, AsyncGenerator, Optional
from agent_workflow.core.task import Task, ToolManager
from agent_workflow.agent import BaseAgent
from agent_workflow.tools.base import MessageInput
from agent_workflow.utils.func import asyncio_run
from agent_workflow.tools.tool.audio_tool import AudioTool, TTSModel


class AudioAgent(BaseAgent):
    """音频处理代理类，支持文本转语音、语音克隆等功能"""

    def __init__(self,
                 print_info: bool = True,
                 model = TTSModel.SOVITS ):
        """
        初始化音频代理

        Args:
            print_info: 是否打印详细信息
        """
        self.print_info = print_info
        self.task = Task(
            tool_manager=ToolManager(
                tools=[
                    AudioTool(
                        model=model
                    )
                ]
            )
        )

    def get_description(self) -> str:
        """获取代理描述信息"""
        agent_info = {
            "name": "AudioAgent",
            "description": "音频处理代理，支持多种TTS模型和语音处理功能"
        }
        return json.dumps(agent_info, ensure_ascii=False, indent=2)

    def _create_message_input(self,
                              text: str,
                              audio_path: Optional[str] = None,
                              character: Optional[str] = None,
                              **kwargs) -> MessageInput:
        """
        创建消息输入对象

        Args:
            text: 要转换的文本内容
            audio_path: 参考音频文件路径（可选）
            character: 游戏角色名称（可选）
            **kwargs: 其他参数

        Returns:
            MessageInput对象
        """
        files = [audio_path] if audio_path else []

        # 构建查询字符串
        query_parts = []
        if character:
            query_parts.append(f"用{character}的声音说")
        query_parts.append(f'"{text}"')

        speed = kwargs.get('speed')
        if speed and speed != 1.0:
            query_parts.append(f"语速{speed}")

        query = " ".join(query_parts)

        return MessageInput(
            query=query,
            images=[],
            urls=[],
            files=files
        )

    async def process_audio(self,
                            text: str,
                            audio_path: Optional[str] = None,
                            character: Optional[str] = None,
                            **kwargs) -> str:
        """
        处理音频生成请求

        Args:
            text: 要转换的文本内容
            audio_path: 参考音频文件路径（可选）
            character: 游戏角色名称（可选）
            **kwargs: 其他参数

        Returns:
            生成的音频文件路径
        """
        message_input = self._create_message_input(
            text=text,
            audio_path=audio_path,
            character=character,
            **kwargs
        )

        return await self.task.process(
            message_input.process_input(),
            printInfo=self.print_info
        )

    async def run(self, **kwargs) -> Dict[str, Any] | str:
        """
        执行代理

        Args:
            **kwargs: 必须包含text参数，可选audio_path和character等参数

        Returns:
            执行结果
        """
        text = kwargs.get('text')
        if not text:
            return {"error": "缺少文本参数"}

        return await self.process_audio(**kwargs)

    def generate_audio(self, text: str, **kwargs) -> str:
        """
        同步方式生成音频

        Args:
            text: 要转换的文本内容
            **kwargs: 其他参数

        Returns:
            生成的音频文件路径
        """
        return asyncio_run(
            self.run(
                text=text,
                **kwargs
            )
        )

    async def run_with_status(self, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        执行音频生成并提供状态反馈

        Args:
            text: 要转换的文本内容
            message_id: 消息ID（可选）
            其他参数
        """
        query = kwargs.get('query')
        files = kwargs.get('files')
        message_id = kwargs.get('message_id', 'default_id')

        if not query:
            yield {
                "type": "error",
                "message_id": message_id,
                "content": "缺少文本参数"
            }
            return

        # 构建消息输入
        message_input = MessageInput(
            query=query,
            images=[],
            urls=[],
            files=[files]
        )

        yield {
            "type": "thinking_process",
            "message_id": message_id,
            "content": f"构建执行工具的参数信息:\n{str(message_input.process_input())}\n发送到音频工具进行处理"
        }

        try:
            # 执行工具处理
            result = await self.task.process(
                message_input.process_input(),
                printInfo=self.print_info
            )

            yield {
                "type": "result",
                "message_id": message_id,
                "content": result
            }

        except Exception as e:
            yield {
                "type": "error",
                "message_id": message_id,
                "content": f"[ERROR] 处理失败: {str(e)}"
            }
