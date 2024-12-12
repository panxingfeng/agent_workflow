# -*- coding: utf-8 -*-
"""
@file: custom_agent.py
@description: 自定义智能体示例代码
"""
import json
from typing import Dict, Any
from agent_workflow import Task, ToolManager, UserQuery
from agent_workflow.agent import BaseAgent
from agent_workflow.tools import MessageInput
from agent_workflow.tools.tool import *  # 替换为你的工具


class CustomAgent(BaseAgent):
    """自定义智能体"""

    def __init__(self, print_info: bool = True):
        """初始化智能体

        Args:
            print_info: 是否打印处理信息
        """
        self.print_info = print_info
        self.task = Task(
            tool_manager=ToolManager(
                tools=[CustomTool()]  # 添加你需要的工具
            )
        )

    def get_description(self) -> str:
        """获取智能体描述信息"""
        agent_info = {
            "name": "CustomAgent",
            "description": "智能体描述",
            "parameters": {
                "param1": {
                    "type": "string",
                    "description": "参数1说明",
                    "required": True
                },
                "param2": {
                    "type": "string",
                    "description": "参数2说明",
                    "required": False
                }
            }
        }
        return json.dumps(agent_info, ensure_ascii=False, indent=2)

    def get_parameter_rules(self) -> str:
        """返回智能体的参数设置规则"""
        return """
        Custom Agent 参数规则:
        - param1: 参数1说明
          * 规则说明
          * 示例说明
        - param2: 参数2说明
          * 规则说明
          * 示例说明
        """

    async def process_query(self, query: str, **kwargs) -> str:
        """处理查询请求

        Args:
            query: 用户查询内容
            **kwargs: 其他参数

        Returns:
            str: 处理结果
        """
        user_query = UserQuery(
            text=query,
            attachments=[]  # 根据需要添加附件
        )

        return await self.task.process(
            user_query,
            printInfo=self.print_info
        )

    async def run(self, **kwargs) -> Dict[str, Any] | str:
        """执行智能体

        Args:
            **kwargs: 包含所需参数的字典
        """
        query = kwargs.get('query')
        if not query:
            return {"error": "缺少查询内容"}

        return await self.process_query(
            query=query,
            **kwargs
        )

    def process(self, **kwargs) -> Dict[str, Any] | str:
        """同步方式执行智能体"""
        import asyncio
        return asyncio.run(self.run(**kwargs))
