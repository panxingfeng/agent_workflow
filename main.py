from agent_workflow import Task, ToolManager
from agent_workflow.llm.llm import ChatTool
from agent_workflow.tools.base import MessageInput
from agent_workflow.tools.tool import WeatherTool, FileConverterTool, ImageTool, SearchTool, AudioTool
from agent_workflow.utils.func import asyncio_run

if __name__ == '__main__':
    tools = [
        WeatherTool(),
        FileConverterTool(),
        ChatTool(),
        ImageTool(),
        SearchTool(),
        AudioTool()
    ]

    asyncio_run(
        demo=Task(
            tool_manager=ToolManager(
                tools=tools
            )
        ).process(
            MessageInput(
                query="你好啊",
                images=[],
                urls=[],
                files=["特朗普.mp3"]
            ).process_input(),
            printInfo=True  # 打印结果信息
        ))  # 控制台启动

    asyncio_run(
        demo=Task(
            tool_manager=ToolManager(
                tools=tools
            )
        ).vchat_demo())  # 微信启动
