# -*- coding: utf-8 -*-
"""
@file: task.py
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2024-11-23
@version: 1.0.0
@license: MIT License

@description:
任务处理核心类，负责任务的解析、规划、执行和结果处理。

功能特性:
1. 任务状态管理和初始化
2. 动态任务计划生成
3. 多工具协调执行
4. 结果格式化处理
5. 错误处理和恢复机制
6. 用户查询解析和分析
7. 统一的任务处理流程

工作流程:
1. 接收并解析用户查询
2. 创建任务账本记录
3. 生成执行计划
4. 调用相关工具
5. 格式化处理结果
6. 返回最终响应

Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
import json
import uuid

from .VChat.VChat import VChat
from ..llm.llm import LLM
from ..tools.result_formatter import ResultFormatter
from ..tools.base import TaskState, InputType, UserQuery
from ..tools.tool_manager import ToolManager


@dataclass
class Task:
    """
    任务处理核心类

    属性:
        tool_manager: 工具管理器，用于管理和执行各种工具
        llm: 语言模型实例，用于处理自然语言交互
        state: 任务状态，包含消息、任务账本、执行计划等信息
    """
    tool_manager: ToolManager
    llm: Optional[LLM] = None
    state: TaskState = field(default_factory=lambda: TaskState(
        messages=[],  # 消息历史
        task_ledger={},  # 任务账本记录
        task_plan=[],  # 执行计划
        tool_results={},  # 工具执行结果
        files={}  # 文件缓存
    ))

    def __post_init__(self):
        """初始化后的处理，设置语言模型和结果格式化器"""
        self.llm = self.llm or LLM(stream=True)
        self.result_formatter = ResultFormatter(self.llm)

    def init_task_state(self, query: UserQuery) -> None:
        """
        初始化任务状态

        Args:
            query: 用户查询对象，包含文本和附件信息
        """
        # 设置用户消息
        self.state["messages"] = [{"role": "user", "content": query.text}]
        # 处理附件（图片和文件）
        self.state["files"] = {
            attachment.type: attachment.content
            for attachment in query.attachments
            if attachment.type in [InputType.IMAGE, InputType.FILE]
        }

    def generate_task_plan(self) -> List[Tuple[str, str]]:
        """
        生成任务执行计划

        Returns:
            返回工具名称和描述的列表
        """
        tools_needed = self.state["task_ledger"].get("tools_needed", [])
        return [
            (tool, self.tool_manager.get_tool(tool).get_description())
            for tool in tools_needed
            if self.tool_manager.get_tool(tool)
        ]

    async def execute_tools(self) -> None:
        """
        执行工具任务

        遍历所需的工具列表，依次执行每个工具，并记录结果
        """
        self.state["tool_results"] = {}
        task_ledger = self.state["task_ledger"]
        tools_needed = task_ledger.get("tools_needed", [])
        parameters = task_ledger.get("parameters", {})

        for tool_name in tools_needed:
            try:
                tool = self.tool_manager.get_tool(tool_name)
                if tool:
                    tool_params = parameters.get(tool_name, {})
                    result = await self.tool_manager.execute_tool(tool_name, **tool_params)
                    self.state["tool_results"][tool_name] = result
                else:
                    self.state["tool_results"][tool_name] = f"工具 {tool_name} 未找到"
            except Exception as e:
                self.state["tool_results"][tool_name] = f"工具执行失败: {str(e)}"

    def _process_tool_result(self, tool_name: str, result: Any, query: str, output: List[str]) -> None:
        """
        处理单个工具的结果

        Args:
            tool_name: 工具名称
            result: 工具执行结果
            query: 原始查询文本
            output: 输出结果列表
        """
        try:
            # 根据工具类型选择不同的格式化方法
            if tool_name == "SearchTool" and isinstance(result, dict):
                self.result_formatter.format_search_results(result, output)
            elif tool_name == "WeatherTool":
                self.result_formatter.format_weather_results(query, result, output)
            elif tool_name == "FileConverterTool":
                self.result_formatter.format_file_converter_results(result, output)
            elif tool_name == "ImageTool":
                self.result_formatter.format_image_results(result, output)
            elif tool_name == "ChatTool":
                output.extend([
                    "----------ChatTool----------",
                    f"回答：{str(result)}"
                ])
            else:
                output.extend([f"----------{tool_name}----------", str(result)])
        except Exception as e:
            output.extend([
                f"----------{tool_name}----------",
                f"处理结果出错: {str(e)}",
                f"原始结果: {str(result)}"
            ])

    def create_task_ledger(self) -> Dict[str, Any]:
        """
        创建任务账本

        根据用户输入分析需求，确定需要使用的工具和参数

        Returns:
            包含任务ID、已知信息、所需工具和参数的字典
        """
        try:
            # 获取所有工具的描述
            tool_descriptions = self.tool_manager.get_tool_descriptions()
            user_message = self.state["messages"][-1]["content"]

            # 构建工具参数说明
            tool_params = {}
            for tool_name, desc in tool_descriptions.items():
                if isinstance(desc, str):
                    desc = json.loads(desc)
                tool_params[tool_name] = desc.get("parameters", {})

            # 构建系统提示
            system_prompt = f"""分析用户需求，返回JSON格式任务参数。
    可用工具及参数说明:
    {json.dumps(tool_params, ensure_ascii=False, indent=2)}

    识别用户的问题需求，按照工具设置的要求填入相应的参数值
    用户输入问候语/自我介绍之类的直接使用"ChatTool",参数内容就是用户输入的内容
    
    返回格式:
    {{
       "known_facts": "用户意图描述",
       "tools_needed": ["工具名称"],
       "parameters": {{
           "工具名": {{
               "参数名": "参数值"
           }}
       }}
    }}"""

            # 获取LLM响应并解析
            response = ''.join(self.llm.chat(
                message=system_prompt,
                prompt=f"用户输入: {user_message}"
            ))

            result = json.loads(response)

            # 补充文件路径
            for tool_name in result.get("tools_needed", []):
                if "image_path" in tool_params.get(tool_name, {}):
                    result["parameters"][tool_name]["image_path"] = self.state["files"].get(InputType.IMAGE)

            return {"task_id": str(uuid.uuid4()), **result}

        except Exception as e:
            # 错误处理，返回默认的ChatTool任务
            return {
                "task_id": str(uuid.uuid4()),
                "known_facts": f"解析失败: {str(e)}",
                "tools_needed": ["ChatTool"],
                "parameters": {"ChatTool": {"message": "解析错误,请重试"}}
            }

    async def process(self, query: UserQuery, printInfo: bool = False) -> str:
        """
        处理用户查询的主方法

        Args:
            query: 用户查询对象

        Returns:
            处理结果的字符串
            :param printInfo:控制台输出结果
        """
        # 初始化任务状态
        self.init_task_state(query)

        if query.attachments:
            attachment_info = "\n附加信息:\n" + "\n".join(
                f"{att.type.name.lower()}: {att.content}"
                for att in query.attachments
            )
            self.state["messages"][0]["content"] += attachment_info

        self.state["task_ledger"] = self.create_task_ledger()
        self.state["task_plan"] = self.generate_task_plan()
        await self.execute_tools()  # 添加await

        query_text = self.state['messages'][0]['content']
        tool_results = self.state['tool_results']

        output = [f"问题：{query_text}"]
        for tool_name, result in tool_results.items():
            self._process_tool_result(tool_name, result, query_text, output)

        result = "\n".join(str(item) for item in output)
        if printInfo:
            print("\n=============== 处理结果 =============== ")
            print(result)
            print("=======================================\n")
        return result

    async def vchat_demo(self):
        """启动vchat实现接入微信"""
        bot = VChat(self)
        await bot.start()
