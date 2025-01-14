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
from typing import Generator, Optional

from config.config import OLLAMA_DATA, CHATGPT_DATA
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
