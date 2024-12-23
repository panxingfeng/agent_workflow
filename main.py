import asyncio

from agent_workflow import ToolManager, UserQuery
from agent_workflow.agent.audio_agent import AudioAgent
from agent_workflow.agent.file_agent import FileConverterAgent
from agent_workflow.core.task import Task
from agent_workflow.agent.chat_agent import ChatAgent
from agent_workflow.agent.image_agent import ImageAgent
from agent_workflow.agent.search_agent import SearchAgent
from agent_workflow.agent.wealther_agent import WeatherAgent
from agent_workflow.core.FeiShu import Feishu
from agent_workflow.core.task_agent import MasterAgent
from agent_workflow.llm.llm import ChatTool
from agent_workflow.tools import MessageInput
from agent_workflow.tools.tool import WeatherTool
from agent_workflow.utils.func import asyncio_run


async def main():
    ################################### 获取飞书tenant_access_token值 ###################################

    # # 获取feishu的tenant_access_token，把返回值中的tenant_access_token填入config.py中的FEISHU_DATA中，
    # # 重要：先把app_id和app_secret填入到FEISHU_DATA中
    # tenant_access_token = await Feishu(None).get_tenant_token()
    # print(str(tenant_access_token))

###################################-------- 多智能体创建 --------###################################

    # 创建需要的智能体
    agents = [
        ChatAgent(),
        WeatherAgent(),
        ImageAgent(),
        SearchAgent(),
        FileConverterAgent(),
        AudioAgent()
    ]
    # 创建智能体调度
    master = MasterAgent(agents)

    # 需要怎么启动就可以把注释关闭

    ################################### 控制台启动 ###################################

    # 创建用户消息输入
    message = MessageInput(
        query="你好啊",
        images=[],
        files=[],
        urls=[]
    )
    print("-----------------------------多智能体回答-----------------------------")
    # 处理消息
    await master.process(message)

    ################################## 微信启动 ###################################

    # await master.vchat_demo()

    ################################### 飞书启动 ###################################

    # await master.feishu_demo()

    ################################### fastapi启动 ###################################

    # await master.fastapi_demo()



if __name__ == "__main__":
    # 启动多智能体
    asyncio.run(main())

    ###################################-------- 单智能体创建 --------###################################

    # tools = [
    #     WeatherTool(),
    #     ChatTool(),
    # ]

    ################################### 控制台启动 ###################################

    # print("-----------------------------单智能体回答-----------------------------")
    # asyncio_run(
    #     demo=Task(
    #         tool_manager=ToolManager(
    #             tools=tools,
    #         )
    #     ).process(
    #         MessageInput(
    #             query="你是谁",
    #             images=[],
    #             files=[],
    #             urls=[]
    #         ).process_input(),
    #         printInfo=True  # 控制台打印结果信息
    #     )
    # )  # 控制台启动

    ################################### 微信启动 ###################################

    # asyncio_run(
    #     demo=Task(
    #         tool_manager=ToolManager(
    #             tools=tools,
    #         )
    #     ).vchat_demo() # 微信启动
    # )

    ################################### 微信启动 ###################################

    # asyncio_run(
    #     demo=Task(
    #         tool_manager=ToolManager(
    #             tools=tools,
    #         )
    #     ).feishu_demo() # 飞书启动
    # )

    ################################### fastapi启动 ###################################

    # asyncio_run(
    #     demo=Task(
    #         tool_manager=ToolManager(
    #             tools=tools,
    #         )
    #     ).fastapi_demo() # fastapi启动
    # )
