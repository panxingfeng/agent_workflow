import asyncio

from agent_workflow.core.tool_executor import ToolExecutor, ToolRegistry
from agent_workflow.core.FeiShu import Feishu
from agent_workflow.core.task_agent import MasterAgent
from agent_workflow.tools import MessageInput


async def main():
    ################################### 获取飞书tenant_access_token值 ###################################

    # # 获取feishu的tenant_access_token，把返回值中的tenant_access_token填入config.py中的FEISHU_DATA中，
    # # 重要：先把app_id和app_secret填入到FEISHU_DATA中
    # tenant_access_token = await Feishu(None).get_tenant_token()
    # print(str(tenant_access_token))

    # 创建智能体调度
    master = MasterAgent(
        # 创建工具执行器，tools是注册可使用的工具，relative_tool_dir是工具代码的存放地址，verbose是是否打印执行过程到控制台
        tool_executor=ToolExecutor(
            tools=ToolRegistry().scan_tools(relative_tool_dir="agent_workflow/tools/tool"),
            verbose=True
        ),
        verbose=True
    )

    # 需要怎么启动就可以把注释关闭

    ################################### 控制台启动 ###################################
    #
    # 创建用户消息输入
    # message = MessageInput(
    #     query="你好啊",
    #     images=[],
    #     files=[],
    #     urls=[]
    # )
    # # 处理消息
    # await master.process(message)

    ################################## 微信启动 ###################################

    # await master.vchat_demo()

    ################################### 飞书启动 ###################################

    # await master.feishu_demo()

    ################################### fastapi启动 ###################################

    # await master.fastapi_demo()

    ################################### chat_ui启动 ###################################

    await master.chat_ui_demo()


if __name__ == "__main__":
    # 启动多智能体
    asyncio.run(main())
