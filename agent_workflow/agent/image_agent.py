import json
from typing import Dict, Any, List, Optional
from agent_workflow.core.task import Task, ToolManager, UserQuery
from agent_workflow.agent import BaseAgent
from agent_workflow.tools import MessageInput
from agent_workflow.tools.tool import DescriptionImageTool, ImageGeneratorTool
from agent_workflow.tools.tool.image_tool import DescriptionModelType, GenerationModelType, PromptGenMode


class ImageAgent(BaseAgent):
    """图像代理，支持图像分析和生成任务"""

    def __init__(self, print_info: bool = True,
                 description_mode: str = DescriptionModelType.LLAMA,
                 imageGenerator_mode: str = GenerationModelType.SDWEBUI_FORGE,
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
            "description": "图像智能代理，支持图像分析和生成任务",
            "parameters": {
                "mode": {
                    "type": "string",
                    "description": "任务模式",
                    "required": True,
                    "enum": ["analyze", "generate"],
                    "detection_keywords": {
                        "analyze": ["分析", "识别", "检测", "看看", "描述", "是什么", "告诉我"],
                        "generate": ["生成", "创建", "画", "绘制", "制作", "做一个", "做一张"]
                    }
                },
                "query": {
                    "type": "string",
                    "description": "用户输入内容",
                    "required": True
                },
                "images": {
                    "type": "string",
                    "description": "图像路径",
                    "required_if": {"mode": "analyze"}
                }
            }
        }
        return json.dumps(agent_info, ensure_ascii=False, indent=2)

    def get_parameter_rules(self) -> str:
        """返回代理的参数设置规则"""
        return """
        Image Agent 参数规则:

        1. 图像分析模式 (mode="analyze"):
           - user_input: 用户问题或分析需求
           - image_path: 需要分析的图像路径

        2. 图像生成模式 (mode="generate"):
           - user_input: 用户描述的图像生成需求
        """

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
