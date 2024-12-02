from agent_workflow import Task, ToolManager
from agent_workflow.llm.llm import ChatTool
from agent_workflow.tools.base import MessageInput
from agent_workflow.tools.tool import WeatherTool, FileConverterTool, ImageTool, SearchTool, AudioTool
from agent_workflow.tools.tool.audio_tool import TTSModel
from agent_workflow.tools.tool.image_tool import ModelType
from agent_workflow.utils.func import asyncio_run

if __name__ == '__main__':
    tools = [
        WeatherTool(),
        FileConverterTool(),
        ChatTool(is_gpt=True),  # 默认ollama模型，可选项(gpt模型设置 is_gpt=True)
        ImageTool(model=ModelType.GLM),  # 默认llama3.2vision，可选项(ModelType.GLM ModelType.MINICPM_V_2_6)
        SearchTool(),
        AudioTool(model=TTSModel.F5_TTS)  # 默认F5-TTS，可选项(TTSModel.SOVITS)
    ]

    ##################### 打开其中一种方式运行即可 #####################
    asyncio_run(
        demo=Task(
            tool_manager=ToolManager(
                tools=tools
            )
        ).process(
            MessageInput(
                query="你是谁",
                images=[],
                urls=[],
                files=[]
            ).process_input(),
            printInfo=True  # 打印结果信息
        ))  # 控制台启动

    # asyncio_run(
    #     demo=Task(
    #         tool_manager=ToolManager(
    #             tools=tools
    #         )
    #     ).vchat_demo())  # 微信启动
