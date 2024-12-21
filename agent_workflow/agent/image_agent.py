import json
from typing import Dict, Any, List, Optional, AsyncGenerator
from agent_workflow.core.task import Task, ToolManager, UserQuery
from agent_workflow.agent import BaseAgent
from agent_workflow.tools import MessageInput
from agent_workflow.tools.tool import DescriptionImageTool, ImageGeneratorTool
from agent_workflow.tools.tool.image_tool import DescriptionModelType, GenerationModelType, PromptGenMode


class ImageAgent(BaseAgent):
    """图像代理，支持图像分析和生成任务"""

    def __init__(self, print_info: bool = True,
                 description_mode: str = DescriptionModelType.LLAMA,
                 imageGenerator_mode: str = GenerationModelType.COMFYUI,
                 prompt_gen_mode=PromptGenMode.NONE):
        """初始化图像代理"""
        self.print_info = print_info
        self.task = Task(
            tool_manager=ToolManager(
                tools=[
                    DescriptionImageTool(
                        model=description_mode
                    ),
                    ImageGeneratorTool(
                        model_type=imageGenerator_mode,
                        prompt_gen_mode=prompt_gen_mode)
                ]
            )
        )

    def get_description(self) -> str:
        """获取代理描述信息"""
        agent_info = {
            "name": "ImageAgent",
            "description": "图像智能代理，支持图像分析和图像生成，mode模式设置规格：分析任务(analyze),图像生成(generate)"
        }
        return json.dumps(agent_info, ensure_ascii=False, indent=2)

    def _create_message_input(self, query: str, image_path: Optional[str] = None) -> MessageInput:
        """创建消息输入对象

        Args:
            query: 用户查询内容
            image_path: 可选的图像路径

        Returns:
            MessageInput: 消息输入对象
        """
        return MessageInput(
            query=query,
            images=[image_path] if image_path else [],
            urls=[],
            files=[]
        )

    async def process_query(
            self,
            query: str,
            image_path: Optional[str] = None
    ) -> str:
        """处理图像相关查询

        Args:
            query: 用户查询内容
            mode: 处理模式 ("analyze" 或 "generate")
            image_path: 可选的图像路径（分析模式必需）

        Returns:
            str: 处理结果
        """
        from agent_workflow.tools import Input, InputType

        # 创建用户查询对象并处理
        user_query = UserQuery(
            text=query,
            attachments=[Input(
                type=InputType.IMAGE,
                content=image_path
            )] if image_path else [],
        )

        # 执行任务处理
        return await self.task.process(
            user_query,
            printInfo=self.print_info
        )
    async def run(self, **kwargs) -> Dict[str, Any] | str | List[str]:
        """执行图像代理"""
        query = kwargs.get('query')
        image_path = kwargs.get('images')

        return await self.process_query(
            query=query,
            image_path=image_path
        )

    def process(self, **kwargs) -> Dict[str, Any] | str | List[str]:
        """同步方式执行代理"""
        import asyncio
        return asyncio.run(self.run(**kwargs))

    async def run_with_status(self, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """执行图像代理并提供状态反馈

        Args:
            query: 提示词
            message_id: 消息ID
        """
        query = kwargs.get('query')
        image_path = kwargs.get('images')
        message_id = kwargs.get('message_id', 'default_id')

        if not query:
            yield {
                "type": "error",
                "message_id": message_id,
                "content": "缺少所需参数信息"
            }
            return

        message_input = MessageInput(
            query=query,
            images=[image_path],
            urls=[],
            files=[]
        )

        # 构建工具参数
        yield {
            "type": "thinking_process",
            "message_id": message_id,
            "content": f"构建执行工具的参数信息:\n{str(message_input.process_input())}\n发送到图像工具进行处理"
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
