# -*- coding: utf-8 -*-
"""
@file: master_agent.py
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2024-12-12
@version: 1.0.0
@license: MIT License

@description:
主控代理类，负责任务的分发和管理。

功能特性:
1. 多代理管理和调度
2. 智能任务分发
3. 状态管理和监控
4. 多平台接入支持(FastAPI/飞书/VChat)
5. 错误处理和恢复机制
6. 调试信息输出
7. 任务执行流程管理

Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""

import re
from enum import Enum
from typing import List, Dict, Any, Optional
from .VChat import VChat
from .FeiShu import Feishu
from agent_workflow.agent import BaseAgent
from agent_workflow.llm.llm import LLM
from agent_workflow.tools.base import MessageInput, InputType, FeishuUserQuery


class AgentStatus(Enum):
    """代理状态枚举类"""
    IDLE = "idle"  # 空闲状态
    RUNNING = "running"  # 运行中
    SUCCESS = "success"  # 执行成功
    FAILED = "failed"  # 执行失败
    VALIDATING = "validating"  # 验证中


class MasterAgent:
    """
    主控代理类

    负责管理和协调多个子代理，实现智能任务分发和执行。
    支持多种平台接入（FastAPI、飞书、微信）。

    属性:
        agents: 可用代理字典，key为代理类名，value为代理实例
        llm: 语言模型实例，用于智能选择代理
        status: 当前代理状态
        current_task: 当前正在执行的任务
    """

    def __init__(self, agents: List[BaseAgent], stream: bool = False):
        """
        初始化主控代理

        Args:
            agents: 代理实例列表
            stream: 是否使用流式输出，默认False
        """
        self.agents = {agent.__class__.__name__: agent for agent in agents}
        self.llm = LLM(stream=stream)
        self.status = AgentStatus.IDLE
        self.current_task = None

    def _print_debug(self, message: str):
        """
        打印调试信息

        Args:
            message: 调试信息内容
        """
        print(f"[Debug] {message}")

    async def _select_agent_with_llm(self, query: str) -> Optional[str]:
        """
        使用LLM智能选择合适的代理

        通过分析用户输入和代理描述，选择最匹配的处理代理。

        Args:
            query: 用户输入的查询文本

        Returns:
            Optional[str]: 选中的代理名称，如果未找到返回None
        """
        prompt = """你是一个智能任务分发助手，负责根据用户输入选择最合适的处理代理。
        分析每个代理的功能描述和参数信息，选择最匹配的代理。
        只需返回代理名称，不要包含其他任何文字。

        规则：
        1. 仔细分析每个代理的功能描述
        2. 考虑代理支持的参数类型
        3. 根据用户输入的特征选择最合适的代理
        4. 如果有多个候选，选择最专业的那个
        5. 如果没有完全匹配的，选择功能最接近的

        示例：
        用户输入："北京天气怎么样" -> "WeatherAgent"
        用户输入："搜索人工智能资料" -> "SearchAgent"
        用户输入："我想生成一张xxx的图像" -> "ImageAgent"
        """

        message = f"""
        可用的代理及其描述：
        {[f"{name}: {agent.get_description()}" for name, agent in self.agents.items()]}

        用户输入: {query}
        """

        try:
            self._print_debug(f"发送消息<{query}>到LLM")
            response = self.llm.chat(prompt=prompt, message=message)
            agent_name = response.strip().replace('"', '').replace("'", "")
            self._print_debug(f"LLM返回的agent名称: {agent_name}")

            # 验证返回的代理名称
            if agent_name in self.agents:
                return agent_name
            else:
                self._print_debug(f"LLM返回的agent名称 '{agent_name}' 不在可用agent列表中")
            return None

        except Exception as e:
            self._print_debug(f"LLM选择agent时发生错误: {str(e)}")
            return None

    def _update_status(self, message: str):
        """
        更新并打印状态信息

        Args:
            message: 状态信息内容
        """
        print(f"当前状态: {self.status.value} - {message}")

    async def process(self, message_input: MessageInput | FeishuUserQuery) -> Dict[str, Any]:
        """
        处理用户消息的主要方法

        处理流程：
        1. 设置运行状态
        2. 处理输入消息
        3. 选择合适的代理
        4. 执行代理任务
        5. 返回处理结果

        Args:
            message_input: 用户消息输入，支持普通消息和飞书消息

        Returns:
            Dict[str, Any]: 处理结果字典
        """
        try:
            self.status = AgentStatus.RUNNING

            # 处理不同类型的输入
            if isinstance(message_input, MessageInput):
                user_query = message_input.process_input()
            else:
                user_query = message_input

            # 使用LLM选择代理
            self._update_status("正在选择处理agent...")
            agent_name = await self._select_agent_with_llm(user_query.text)

            if not agent_name:
                self.status = AgentStatus.FAILED
                self._print_debug("无法确定合适的agent")
                return {"error": "未找到合适的处理agent"}

            selected_agent = self.agents[agent_name]
            self._update_status(f"已选择agent: {agent_name}")

            # 执行代理任务
            self._update_status("正在执行任务...")
            result = await selected_agent.run(
                query=user_query.text,
                images=[att.content for att in user_query.attachments if att.type == InputType.IMAGE],
                files=[att.content for att in user_query.attachments if att.type == InputType.FILE]
            )

            self.status = AgentStatus.SUCCESS
            self._update_status("任务完成")
            return {"success": True, "result": result}

        except Exception as e:
            self.status = AgentStatus.FAILED
            self._update_status(f"处理失败: {str(e)}")
            self._print_debug(f"详细错误信息: {str(e)}")
            return {"error": f"处理失败: {str(e)}"}

    async def vchat_demo(self):
        """启动VChat服务，实现微信公众号接入"""
        bot = VChat(self)
        await bot.start()

    async def feishu_demo(self, port: int = 8070):
        """
        启动飞书服务

        Args:
            port: 服务端口号，默认8070
        """
        bot = Feishu(self)
        await bot.start(port=port)

    async def fastapi_demo(self, host="localhost", port=8000):
        """
        启动FastAPI服务器，提供HTTP接口

        Args:
            host: 服务主机地址，默认localhost
            port: 服务端口号，默认8000
        """
        from fastapi import HTTPException, FastAPI
        import uvicorn
        from pydantic import BaseModel

        app = FastAPI()

        class MessageRequest(BaseModel):
            """接口请求模型"""
            query: str  # 查询文本
            images: Optional[List[str]] = None  # 图片列表
            files: Optional[List[str]] = None  # 文件列表
            urls: Optional[List[str]] = None  # URL列表

        @app.post("/api/process", response_model=None)
        async def process_message(message: MessageRequest):
            """
            处理消息的API接口

            Args:
                message: 消息请求对象

            Returns:
                处理结果

            Raises:
                HTTPException: 处理失败时抛出的异常
            """
            try:
                input_msg = MessageInput(
                    query=message.query,
                    images=message.images,
                    files=message.files,
                    urls=message.urls
                )
                result = await self.process(input_msg)
                try:
                    match = re.search(r"输出路径：(.+)", str(result))
                    result = match.group(1).strip()  # 提取出的文件路径

                except Exception:
                    result = result
                return {"result": result}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        config = uvicorn.Config(app, host=host, port=port)
        server = uvicorn.Server(config)
        await server.serve()