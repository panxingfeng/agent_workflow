from agent_workflow import Task, ToolManager
from agent_workflow.llm.llm import ChatTool
from agent_workflow.tools.tool import WeatherTool, FileConverterTool, ImageTool, SearchTool
from agent_workflow.utils.func import asyncio_run

if __name__ == '__main__':
    tools = [
        WeatherTool(),
        FileConverterTool(),
        ChatTool(),
        ImageTool(),
        SearchTool()
    ]

    asyncio_run(demo=Task(tool_manager=ToolManager(tools)).vchat_demo())  # 接入微信
