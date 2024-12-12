import json
from typing import Dict, Any
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
            "description": "搜索代理，支持多种搜索模式和优化选项",
            "parameters": {
                "query": {
                    "type": "string",
                    "description": "搜索查询内容",
                    "required": True
                },
                "focus_mode": {
                    "type": "string",
                    "description": "搜索焦点模式",
                    "required": False,
                    "default": "webSearch",
                    "enum": [
                        {"name": "webSearch", "description": "网页搜索模式"},
                        {"name": "academicSearch", "description": "学术搜索模式"},
                        {"name": "writingAssistant", "description": "写作辅助模式"},
                        {"name": "wolframAlphaSearch", "description": "Wolfram Alpha搜索"},
                        {"name": "youtubeSearch", "description": "YouTube视频搜索"},
                        {"name": "redditSearch", "description": "Reddit社区搜索"}
                    ]
                },
                "optimization_mode": {
                    "type": "string",
                    "description": "优化模式",
                    "required": False,
                    "default": "speed",
                    "enum": [
                        {"name": "speed", "description": "速度优先模式"},
                        {"name": "balanced", "description": "平衡模式"}
                    ]
                }
            },
            "execution_options": {
                "async_support": True,
                "batch_processing": False,
                "max_tokens": 1024,
                "timeout": 60.0
            }
        }
        return json.dumps(agent_info, ensure_ascii=False, indent=2)

    def get_parameter_rules(self) -> str:
        """返回代理的参数设置规则"""
        return """
        Search Agent 参数规则:
        - query: 搜索查询内容
        - focus_mode: 搜索模式（可选）
          * webSearch（默认）
          * academicSearch
          * writingAssistant
          * wolframAlphaSearch
          * youtubeSearch
          * redditSearch
        - optimization_mode: 优化模式（可选）
          * speed（默认）
          * balanced
        """

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

        focus_mode = kwargs.get('focus_mode')
        optimization_mode = kwargs.get('optimization_mode')

        return await self.process_query(query, focus_mode, optimization_mode)

    def query(self, query: str, focus_mode: str = None, optimization_mode: str = None) -> Dict[str, Any]:
        """
        同步方式搜索查询

        Args:
            query: 查询内容
            focus_mode: 搜索模式
            optimization_mode: 优化模式

        Returns:
            Dict[str, Any]: 查询结果
        """
        return asyncio_run(
            self.run(
                query=query,
                focus_mode=focus_mode,
                optimization_mode=optimization_mode
            )
        )
