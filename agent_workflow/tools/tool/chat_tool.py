# -*- coding: utf-8 -*-
"""
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2025-1-11
@version: 2.0.0
@license: MIT License
Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""
import json
import logging

from agent_workflow.llm import LLM
from agent_workflow.tools.tool.base import BaseTool, ThreadPoolToolDecorator
from config.bot import CHATBOT_PROMPT_DATA, BOT_DATA

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@ThreadPoolToolDecorator(max_workers=20)
class ChatTool(BaseTool):
    """聊天工具"""

    def __init__(self, stream: bool = False, is_gpt: bool = False):
        self.stream = stream
        self.is_gpt = is_gpt

    def get_description(self) -> str:
        tool_info = {
            "name": "ChatTool",
            "description": "处理用户聊天的工具，包括问候、闲聊、问答",
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
                },
                "context": {
                    "type": "array",
                    "description": "对话上下文，包含历史消息",
                    "items": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "用户的提问"
                            },
                            "response": {
                                "type": "string",
                                "description": "系统的回答"
                            }
                        },
                        "required": ["query", "response"]
                    },
                    "required": True,
                    "default": []
                }
            },
            "examples": [
                {"input": "你好", "output": "回复问候"},
                {"input": "最近好吗", "output": "日常对话"},
                {"input": "介绍一下你自己", "output": "自我介绍"}
            ]
        }
        return json.dumps(tool_info, ensure_ascii=False)

    async def run(self, **kwargs) -> str:
        try:
            message = kwargs.get("message", "")
            context = kwargs.get("context", [])
            history = kwargs.get("history", [])
            logger.info("context:" + str(context))
            if not message:
                return "请输入您想说的话"

            llm = LLM(stream=self.stream)

            # 构建系统提示词
            system_prompt = CHATBOT_PROMPT_DATA.get("description").format(
                name=BOT_DATA["agent"].get("name"),
                capabilities=BOT_DATA["agent"].get("capabilities"),
                welcome_message=BOT_DATA["agent"].get("default_responses").get("welcome_message"),
                unknown_command=BOT_DATA["agent"].get("default_responses").get("unknown_command"),
                language_support=BOT_DATA["agent"].get("language_support"),
                formatted_context=context,
                history=history if history else "无历史记录",
                query=message,
            )

            # 调用 LLM 生成回复
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
