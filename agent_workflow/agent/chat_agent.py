import json
from typing import Dict, Any
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
            "description": "聊天代理，处理用户的对话请求",
            "parameters": {
                "message": {
                    "type": "string",
                    "description": "用户的聊天内容",
                    "required": True
                }
            }
        }
        return json.dumps(agent_info, ensure_ascii=False, indent=2)

    def get_parameter_rules(self) -> str:
        """返回代理的参数设置规则"""
        return """
        Chat Agent 参数规则:
        - message: 用户的聊天内容
          * 必填参数
          * 支持任何形式的对话内容
          * 如："你好"、"介绍一下自己"等
        """

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
        print(str(user_query))
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