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
import asyncio
import json
import os
from typing import Optional, List

from agent_workflow.llm import LLM
from agent_workflow.rag import LightsRAG
from agent_workflow.tools.tool.base import BaseTool, ThreadPoolToolDecorator
from agent_workflow.utils import loadingInfo
from config.bot import CHATBOT_PROMPT_DATA, BOT_DATA

logger = loadingInfo("chat_tool")

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


class RagQATool(BaseTool):
    """RAG知识库问答工具"""

    def __init__(self, query: str = None, rag_names: List[str] = None):
        """
        初始化RAG问答工具

        Args:
            query: 查询问题
            rag_names: 要使用的RAG知识库名称列表
        """
        self.query = query
        self.rag_names = rag_names or []
        self.rags = {}  # 存储多个RAG实例
        self.logger = logger

    def get_description(self) -> str:
        """返回工具的描述信息"""
        tool_info = {
            "name": "RagQATool",
            "description": "基于本地知识库的问答工具，可以使用多个知识库同时回答问题",
            "parameters": {
                "query": {
                    "type": "string",
                    "description": "需要查询的问题"
                },
                "rag_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要使用的知识库名称列表"
                }
            }
        }
        return json.dumps(tool_info, ensure_ascii=False)

    async def run(self, **kwargs) -> str:
        """
        执行 RAG 问答，并返回整合后的所有答案。
        """
        try:
            self.query = kwargs.get('query', self.query)
            self.rag_names = kwargs.get('rag_names', self.rag_names)
            results = []

            for rag_name in self.rag_names:
                path = os.path.join('data', 'rag_data', rag_name)
                rag = LightsRAG(path_name=str(path))
                answer = await rag.ask(self.query)

                results.append({
                    'rag_name': rag_name,
                    'answer': answer
                })

            combined_answers = "\n".join([result['answer'] for result in results])
            return combined_answers

        except Exception as e:
            self.logger.error(f"RAG 执行出错: {str(e)}")
            return f"执行过程中出现错误: {str(e)}"

        finally:
            # 清理不需要的 RAG 实例
            self._cleanup_unused_rags()

    def _cleanup_unused_rags(self):
        """清理未使用的 RAG 实例"""
        try:
            current_rags = set(self.rag_names)
            for rag_name in list(self.rags.keys()):
                if rag_name not in current_rags:
                    try:
                        del self.rags[rag_name]
                        self.logger.info(f"清理未使用的 RAG 实例: {rag_name}")
                    except Exception as e:
                        self.logger.error(f"清理 RAG {rag_name} 时出错: {str(e)}")
        except Exception as e:
            self.logger.error(f"清理未使用的 RAG 实例时出错: {str(e)}")
