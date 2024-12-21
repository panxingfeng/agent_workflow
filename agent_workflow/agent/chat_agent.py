import asyncio
import json
from typing import Dict, Any, AsyncGenerator
from agent_workflow.core.task import Task, ToolManager, UserQuery
from agent_workflow.agent import BaseAgent
from agent_workflow.llm.llm import ChatTool


class ChatAgent(BaseAgent):
    """聊天代理，处理基础对话功能"""

    def __init__(self, print_info: bool = True, stream: bool = False, is_gpt: bool = False):
        """初始化聊天代理

        Args:
            print_info: 是否打印处理信息
            stream: 是否使用流式响应
            is_gpt: 是否使用GPT模型
        """
        self.print_info = print_info
        self.task = Task(
            tool_manager=ToolManager(
                tools=[ChatTool(stream=stream, is_gpt=is_gpt)]
            )
        )

    def get_description(self) -> str:
        """获取代理描述信息"""
        agent_info = {
            "name": "ChatAgent",
            "description": "聊天代理，处理用户的对话请求"
        }
        return json.dumps(agent_info, ensure_ascii=False, indent=2)

    async def process_query(self, message: str) -> str:
        """处理聊天查询

        Args:
            message: 用户消息内容

        Returns:
            str: 处理结果
        """
        if not message:
            return "请输入您想说的话"

        user_query = UserQuery(
            text=message,
            attachments=[]
        )
        return await self.task.process(
            user_query,
            printInfo=self.print_info
        )

    async def run(self, **kwargs) -> Dict[str, Any] | str:
        """执行聊天代理

        Args:
            query: 用户文本消息
            images: 图片列表（可选）
            files: 文件列表（可选）
        """
        query = kwargs.get('query')

        if not query:
            return {"error": "缺少聊天内容"}

        # 构建工具参数
        user_query = UserQuery(
            text=query,
            attachments=[]
        )

        # 执行工具处理
        return await self.task.process(
            user_query,
            printInfo=self.print_info
        )

    async def run_with_status(self, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """执行聊天代理并提供状态反馈

        Args:
            query: 用户文本消息
            images: 图片列表（可选）
            files: 文件列表（可选）
            message_id: 消息ID
        """
        query = kwargs.get('query')
        message_id = kwargs.get('message_id', 'default_id')

        if not query:
            yield {
                "type": "error",
                "message_id": message_id,
                "content": "缺少所需参数信息"
            }
            return

        user_query = UserQuery(
            text=query,
            attachments=[]
        )

        # 构建工具参数
        yield {
            "type": "thinking_process",
            "message_id": message_id,
            "content": f"构建执行工具的参数信息:\n{str(user_query)}\n发送到chat工具进行处理"
        }

        try:
            # 执行工具处理
            result = await self.task.process(
                user_query,
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