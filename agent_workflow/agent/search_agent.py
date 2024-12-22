import json
from typing import Dict, Any, AsyncGenerator
from agent_workflow.core.task import Task, ToolManager
from agent_workflow.agent import BaseAgent
from agent_workflow.tools.base import MessageInput
from agent_workflow.tools.tool import SearchTool
from agent_workflow.utils.func import asyncio_run


class SearchAgent(BaseAgent):
    """搜索代理"""

    def __init__(self, print_info: bool = True):
        """
        初始化搜索代理

        Args:
            print_info: 是否打印详细信息
        """
        self.print_info = print_info
        self.tools = [SearchTool()]
        self.task = Task(
            tool_manager=ToolManager(
                tools=self.tools
            )
        )

    def get_description(self) -> str:
        """
        获取代理描述信息

        Returns:
            JSON格式的代理描述字符串，包含：
            - 代理名称和描述
            - 参数说明
            - 执行选项
        """
        agent_info = {
            "name": "SearchAgent",
            "description": "搜索代理，支持多种搜索模式和优化选项"
        }
        return json.dumps(agent_info, ensure_ascii=False, indent=2)

    def _create_message_input(self, query: str) -> MessageInput:
        """创建消息输入对象"""
        return MessageInput(
            query=query,
            images=[],
            urls=[],
            files=[]
        )

    async def process_query(self, query: str, focus_mode: str = None, optimization_mode: str = None) -> str:
        """
        处理搜索查询

        Args:
            query: 查询内容
            focus_mode: 搜索模式
            optimization_mode: 优化模式

        Returns:
            Dict[str, Any]: 搜索结果
        """
        message_input = self._create_message_input(query)
        return await self.task.process(
            message_input.process_input(),
            printInfo=self.print_info
        )

    async def run(self, **kwargs) -> dict[str, str] | str:
        """
        执行代理

        Args:
            **kwargs: 必须包含query参数，可选focus_mode和optimization_mode

        Returns:
            Dict[str, Any]: 执行结果
        """
        query = kwargs.get('query')
        if not query:
            return {"error": "缺少查询参数"}

        return await self.process_query(query)

    def query(self, query: str) -> Dict[str, Any]:
        """
        同步方式搜索查询

        Args:
            query: 查询内容

        Returns:
            Dict[str, Any]: 查询结果
        """
        return asyncio_run(
            self.run(
                query=query
            )
        )

    async def run_with_status(self, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """执行搜索查询代理并提供状态反馈

        Args:
            query: 搜索查询语句
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

        message_input = MessageInput(
            query=query,
            images=[],
            urls=[],
            files=[]
        )

        # 构建工具参数
        yield {
            "type": "thinking_process",
            "message_id": message_id,
            "content": f"构建执行工具的参数信息:\n{str(message_input.process_input())}\n发送到搜索工具进行处理"
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