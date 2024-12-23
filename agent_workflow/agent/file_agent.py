import json
from typing import Dict, Any, AsyncGenerator
from agent_workflow.core.task import Task, ToolManager
from agent_workflow.agent import BaseAgent
from agent_workflow.tools.base import MessageInput
from agent_workflow.tools.tool import FileConverterTool


class FileConverterAgent(BaseAgent):
    def __init__(self, print_info: bool = True):
        self.print_info = print_info
        self.tools = [FileConverterTool()]
        self.task = Task(
            tool_manager=ToolManager(
                tools=self.tools
            )
        )

    def get_description(self) -> str:
        agent_info = {
            "name": "FileConverterAgent",
            "description": "多功能文件转换代理，支持PDF、图像、Word等格式互转"
        }
        return json.dumps(agent_info, ensure_ascii=False, indent=2)

    def _create_message_input(self, query: str, files: list = None, images: list = None) -> MessageInput:
        return MessageInput(
            query=query,
            files=files or [],
            images=images or [],
            urls=[]
        )

    async def process_conversion(self, query: str, files: list = None, images: list = None) -> str:
        message_input = self._create_message_input(query, files, images)
        return await self.task.process(
            message_input.process_input(),
            printInfo=self.print_info
        )

    async def run(self, **kwargs) -> dict[str, str] | str:
        query = kwargs.get('query')
        files = kwargs.get('files', [])
        images = kwargs.get('images', [])

        if not query:
            return {"error": "缺少查询参数"}

        return await self.process_conversion(query, files, images)

    async def run_with_status(self, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        query = kwargs.get('query')
        message_id = kwargs.get('message_id', 'default_id')
        files = kwargs.get('files', [])
        images = kwargs.get('images', [])

        if not query:
            yield {
                "type": "error",
                "message_id": message_id,
                "content": "缺少所需参数信息"
            }
            return

        message_input = MessageInput(
            query=query,
            files=files,
            images=images,
            urls=[]
        )

        # 构建工具参数
        yield {
            "type": "thinking_process",
            "message_id": message_id,
            "content": f"构建执行工具的参数信息:\n{str(message_input.process_input())}\n发送到文件工具进行处理"
        }

        try:
            # 执行文件转换
            result = await self.task.process(
                message_input.process_input(),
                printInfo=self.print_info
            )

            # 返回结果
            yield {
                "type": "result",
                "message_id": message_id,
                "content": result
            }

        except Exception as e:
            yield {
                "type": "error",
                "message_id": message_id,
                "content": f"[ERROR] 转换失败: {str(e)}"
            }