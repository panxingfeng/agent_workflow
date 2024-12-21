# -*- coding: utf-8 -*-
"""
@file: llm.py
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2024-11-23
@version: 1.0.0
@license: MIT License

@description:
LLM调用和聊天工具的核心实现模块，提供与大语言模型交互的统一接口。

功能特性:
1. 多模型支持（Ollama、ChatGPT）
2. 流式输出处理
3. 统一的聊天接口
4. 灵活的参数配置
5. 聊天历史管理
6. 错误处理和恢复
7. 提示词模板支持

系统架构:
1. LLM类：底层模型调用封装
  - 模型初始化和切换
  - 请求参数管理
  - 响应处理

2. ChatTool类：高层聊天功能实现
  - 对话管理
  - 上下文维护
  - 模板应用

Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""
import json
from typing import Generator, Optional

from config.bot import CHATBOT_PROMPT_DATA, BOT_DATA
from config.config import OLLAMA_DATA, CHATGPT_DATA
from agent_workflow.tools.tool.base import BaseTool
from ..llm.base import get_llm_instance


class LLM:
    """LLM调用的主类"""
    def __init__(self, stream: bool = False):
        self.llm, self.model_name, self.api_key = self.ollama()
        self.stream = stream

    def chat_completion(
            self,
            messages: list[dict],
            is_gpt: bool = False,
            temperature: float = 0.7,
            max_tokens: Optional[int] = 1024,
    ) -> Generator[str, None, None] | str:
        """
        执行聊天补全请求

        Args:
            messages: 消息列表，包含角色和内容
            temperature: 温度参数，控制输出随机性
            max_tokens: 最大标记数限制

        Returns:
            如果stream=True，返回字符串生成器
            如果stream=False，返回完整响应字符串
        """
        if is_gpt:
            self.llm, self.model_name, self.api_key = self.chatgpt()

        response = self.llm.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=self.stream,
            temperature=temperature,
            max_tokens=max_tokens
        )

        if self.stream:
            return self._handle_stream_response(response)
        return response.choices[0].message.content

    def chat(
            self,
            prompt: str,
            message: str,
            is_gpt: bool = False
    ) -> Generator[str, None, None] | str:
        """
        简化的聊天接口
        Args:
            prompt: 系统提示词
            message: 用户消息

        Returns:
            如果stream=True，返回字符串生成器
            如果stream=False，返回完整响应字符串
        """
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": message}
        ]
        return self.chat_completion(messages, is_gpt)

    def _handle_stream_response(self, response) -> Generator[str, None, None]:
        """处理流式响应"""
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def ollama(self):
        return get_llm_instance(
            model_name=OLLAMA_DATA['model'],
            api_key="none"
        )

    def chatgpt(self):
        return get_llm_instance(
            model_name=CHATGPT_DATA['model'],
            api_key=CHATGPT_DATA['key']
        )

class ChatTool(BaseTool):
    """聊天工具"""
    def __init__(self, stream: bool = False, is_gpt: bool = False):
        self.stream = stream
        self.chat_history = []
        self.is_gpt = is_gpt

    def get_description(self) -> str:
        tool_info = {
            "name": "ChatTool",
            "description": "处理用户聊天的工具，包括问候、闲聊、问答等",
            "capabilities": [
                "回复问候",
                "进行日常对话",
                "回答问题",
                "信息咨询"
            ],
            "input_types": [
                "问候语",
                "聊天内容",
                "问题"
            ],
            "parameters": {
                "message": {
                    "type": "string",
                    "description": "用户的聊天内容",
                    "required": True
                }
            },
            "examples": [
                {"input": "你好", "output": "回复问候"},
                {"input": "最近好吗", "output": "日常对话"},
                {"input": "介绍一下你自己", "output": "自我介绍"}
            ]
        }
        return json.dumps(tool_info, ensure_ascii=False)

    def get_parameter_rules(self) -> str:
        """返回聊天工具的参数设置规则"""
        rules = """
        ChatTool 需要设置:
        - message: 用户的聊天内容
          - 必填参数
          - 类型: 字符串
          - 示例输入: "你好啊", "你好","介绍一下自己", "最近好吗"等等需要你自我介绍或者问候的内容
          - 规则: 直接使用用户的原始输入

        示例:
        输入: "你好啊"
        参数设置: {
            "message": "你好啊"
        }

        注意:
        - 基础对话、问候、自我介绍等一般性交谈使用此工具
        - 特定功能（如天气查询、搜索等）应使用对应的专门工具
        """
        return rules

    async def run(self, **kwargs) -> str:
        try:
            message = kwargs.get("message", "")

            if not message:
                return "请输入您想说的话"

            llm = LLM(stream=self.stream)

            system_prompt = CHATBOT_PROMPT_DATA.get("description").format(
                name=BOT_DATA["agent"].get("name"),
                capabilities=BOT_DATA["agent"].get("capabilities"),
                welcome_message=BOT_DATA["agent"].get("default_responses").get("welcome_message"),
                unknown_command=BOT_DATA["agent"].get("default_responses").get("unknown_command"),
                language_support=BOT_DATA["agent"].get("language_support"),
                history=self.chat_history,
                query=message,
            )

            response = llm.chat(
                prompt=system_prompt,
                message=message,
                is_gpt=self.is_gpt
            )

            if self.stream:
                response_text = ""
                for chunk in response:
                    response_text += chunk
                return response_text
            return response

        except Exception as e:
            import traceback
            return f"对话失败: {str(e)}\n{traceback.format_exc()}"
