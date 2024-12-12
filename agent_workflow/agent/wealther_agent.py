import json

from agent_workflow.core.task import Task, ToolManager
from agent_workflow.agent.base import BaseAgent
from agent_workflow.tools.base import MessageInput
from agent_workflow.tools.tool import WeatherTool
from agent_workflow.utils.func import asyncio_run
from typing import Dict, Any


class WeatherAgent(BaseAgent):
    """天气查询代理"""

    def __init__(self, print_info: bool = True):
        """初始化天气代理"""
        self.print_info = print_info
        self.tools = [WeatherTool()]
        self.task = Task(
            tool_manager=ToolManager(
                tools=self.tools
            )
        )

    def get_description(self) -> str:
        """获取代理描述信息"""
        agent_info = {
            "name": "WeatherAgent",
            "description": "天气查询代理，用于获取指定地区的天气信息",
            "parameters": {
                "location": {
                    "type": "string",
                    "description": "需要查询天气的地区",
                    "required": True
                }
            }
        }
        return json.dumps(agent_info, ensure_ascii=False)

    def get_parameter_rules(self) -> str:
        """返回代理的参数设置规则"""
        return """
        Weather Agent 参数规则:
        - query: 天气查询语句
          - 示例: "北京天气怎么样？"
          - 格式: 支持省市区县级查询
        """

    async def run(self, **kwargs) -> dict[str, str] | str:
        """
        执行代理

        Args:
            **kwargs: 必须包含 query 参数

        Returns:
            Dict[str, Any]: 查询结果
        """
        query = kwargs.get('query')
        if not query:
            return {"error": "缺少查询参数"}
        return await self.process_query(query)

    def _create_message_input(self, query: str) -> MessageInput:
        """创建消息输入对象"""
        return MessageInput(
            query=query,
            images=[],
            urls=[],
            files=[]
        )

    async def process_query(self, query: str) -> str:
        """处理天气查询"""
        message_input = self._create_message_input(query)
        return await self.task.process(
            message_input.process_input(),
            printInfo=self.print_info
        )

    def query(self, query: str) -> Dict[str, Any]:
        """同步方式查询天气"""
        return asyncio_run(self.run(query=query))

