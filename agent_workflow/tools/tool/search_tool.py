# -*- coding: utf-8 -*-
"""
@file: task.py
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2024-11-23
@version: 1.0.0
@license: MIT License

@description:
搜索工具模块

主要功能：
1. 多模式搜索支持（网页、学术、写作等）
2. 异步搜索处理
3. 结果格式化
4. 错误处理和恢复
5. 灵活的参数配置

Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""
import httpx
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
import json

from pydantic import BaseModel, Field

from agent_workflow.tools.tool.base import BaseTool
from agent_workflow.utils.loading import LoadingIndicator
from config.config import SEARCH_TOOL_OLLAMA_CONFIG, SEARCH_TOOL_EMBEDDING_CONFIG


class FocusMode(str, Enum):
    """
    搜索焦点模式枚举

    可选模式：
    - WEB_SEARCH: 网页搜索，用于一般网络内容
    - ACADEMIC_SEARCH: 学术搜索，用于研究文献
    - WRITING_ASSISTANT: 写作助手，用于创作支持
    - WOLFRAM_ALPHA: Wolfram Alpha搜索，用于数学和科学计算
    - YOUTUBE_SEARCH: YouTube搜索，用于视频内容
    - REDDIT_SEARCH: Reddit搜索，用于社区讨论
    """
    WEB_SEARCH = "webSearch"
    ACADEMIC_SEARCH = "academicSearch"
    WRITING_ASSISTANT = "writingAssistant"
    WOLFRAM_ALPHA = "wolframAlphaSearch"
    YOUTUBE_SEARCH = "youtubeSearch"
    REDDIT_SEARCH = "redditSearch"

    @classmethod
    def list_modes(cls) -> List[str]:
        """获取所有可用的搜索模式列表"""
        return [mode.value for mode in cls]


class OptimizationMode(str, Enum):
    """
    优化模式枚举

    模式选项：
    - SPEED: 速度优先，快速返回结果
    - BALANCED: 平衡模式，兼顾速度和质量
    """
    SPEED = "speed"
    BALANCED = "balanced"

    @classmethod
    def list_modes(cls) -> List[str]:
        """获取所有可用的优化模式列表"""
        return [mode.value for mode in cls]


class SourceMetadata(BaseModel):
    """
    参考来源元数据模型

    属性：
        title: 来源标题
        url: 来源链接
    """
    title: str = Field(..., description="参考来源的标题")
    url: str = Field(..., description="参考来源的链接")


class Source(BaseModel):
    """
    参考来源数据模型

    属性：
        pageContent: 页面内容摘要（可选）
        metadata: 来源元数据
    """
    pageContent: Optional[str] = Field(None, description="页面内容的摘要")
    metadata: SourceMetadata = Field(..., description="来源的元数据")


class SearchResponse(BaseModel):
    """
    搜索响应数据模型

    属性：
        message: 搜索结果主要内容
        sources: 参考来源列表
    """
    message: str = Field(..., description="搜索结果的主要内容")
    sources: List[Source] = Field([], description="参考来源列表")


class SearchTool(BaseTool):
    """
    知识搜索工具类

    功能：
    1. 支持多种搜索模式
    2. 可配置的优化选项
    3. 异步搜索处理
    4. 结果格式化

    属性：
        base_url: API服务器地址
        timeout: 请求超时时间
        optimizationMode: 优化模式
        focusMode: 搜索焦点模式
        query: 搜索查询
        chat_model: 聊天模型配置
        embedding_model: 嵌入模型配置
    """

    def __init__(self,
                 query: str = None,
                 base_url: str = "http://localhost:3001",
                 timeout: float = 60.0,
                 optimizationMode: str = None,
                 focusMode: str = None,
                 chat_model: Dict[str, str] = None,
                 embedding_model: Dict[str, str] = None):
        """
        初始化搜索工具

        Args:
            query: 搜索查询内容
            base_url: API服务器地址
            timeout: 请求超时时间（秒）
            optimizationMode: 优化模式
            focusMode: 搜索焦点模式
            chat_model: 聊天模型配置
            embedding_model: 嵌入模型配置
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.optimizationMode = optimizationMode or OptimizationMode.SPEED
        self.focusMode = focusMode or FocusMode.WEB_SEARCH
        self.query = query
        self.chat_model = chat_model or SEARCH_TOOL_OLLAMA_CONFIG
        self.embedding_model = embedding_model or SEARCH_TOOL_EMBEDDING_CONFIG

    def get_description(self) -> str:
        """
        获取工具描述信息

        Returns:
            JSON格式的工具描述字符串，包含：
            - 工具名称和描述
            - 参数说明
            - 模型配置
        """
        tool_info = {
            "name": "SearchTool",
            "description": "知识搜索工具，支持多种搜索模式和优化选项",
            "parameters": {
                "query": {
                    "type": "string",
                    "description": "搜索查询内容",
                    "required": True
                },
                "focus_mode": {
                    "type": "string",
                    "description": "搜索焦点模式",
                    "required": False,
                    "default": "webSearch",
                    "enum": [
                        {"name": mode.value, "description": mode.name}
                        for mode in FocusMode
                    ]
                },
                "optimization_mode": {
                    "type": "string",
                    "description": "优化模式",
                    "required": False,
                    "default": "speed",
                    "enum": [
                        {"name": mode.value, "description": mode.name}
                        for mode in OptimizationMode
                    ]
                },
                "history": {
                    "type": "array",
                    "description": "对话历史",
                    "required": False
                }
            },
            "models": {
                "chat_model": self.chat_model,
                "embedding_model": self.embedding_model
            }
        }
        return json.dumps(tool_info, ensure_ascii=False, indent=2)

    def get_parameter_rules(self) -> str:
        """返回搜索工具的参数设置规则"""
        rules = """
        SearchTool 需要设置:
        - query: 用户的搜索查询内容
        - focus_mode: 可选的搜索模式，从以下选项选择:
          * webSearch (默认)
          * academicSearch
          * writingAssistant
          * wolframAlphaSearch
          * youtubeSearch
          * redditSearch

        示例:
        输入: "搜索关于人工智能的最新进展"
        参数设置: {
            "query": "人工智能的最新进展",
            "focus_mode": "academicSearch"
        }
        """
        return rules

    @staticmethod
    def _format_result(response_data: dict) -> Dict[str, Any]:
        """
        格式化搜索结果

        Args:
            response_data: API返回的原始数据

        Returns:
            格式化后的结果字典，包含：
            - answer: 搜索回答
            - sources: 参考来源列表
        """
        try:
            result = SearchResponse(**response_data)
            return {
                "answer": result.message,
                "sources": [
                    {
                        "title": source.metadata.title,
                        "url": source.metadata.url
                    }
                    for source in result.sources
                ]
            }
        except Exception as e:
            return {
                "error": f"结果格式化失败: {str(e)}",
                "raw_data": response_data
            }

    async def search(self,
                     history: List[Tuple[str, str]] = None,
                     optimization_mode: OptimizationMode = OptimizationMode.BALANCED,
                     focus_mode: FocusMode = FocusMode.WEB_SEARCH) -> Optional[Dict[str, Any]]:
        """
        执行搜索请求

        Args:
            history: 对话历史
            optimization_mode: 优化模式
            focus_mode: 焦点模式
        Returns:
            搜索结果字典或None（如果失败）
        """
        url = f"{self.base_url}/api/search"

        payload = {
            "chatModel": self.chat_model,
            "embeddingModel": self.embedding_model,
            "optimizationMode": optimization_mode.value,
            "focusMode": focus_mode.value,
            "query": self.query,
            "history": history or []
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        loading = LoadingIndicator(f"正在搜索 '{self.query}' (模式: {focus_mode.value})")
        loading.start()

        try:
            timeout = httpx.Timeout(self.timeout, connect=self.timeout)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    response_data = response.json()
                    loading.stop()
                    return response_data
                else:
                    loading.stop()
                    error_msg = f"请求失败: HTTP {response.status_code}"
                    try:
                        error_details = response.json()
                    except:
                        error_details = response.text
                    return {"error": error_msg, "details": error_details}

        except httpx.TimeoutException:
            loading.stop()
            return {"error": "请求超时，但后台仍在处理...请稍后重试查看结果"}
        except Exception as e:
            loading.stop()
            return {"error": f"发生错误: {str(e)}"}

    async def run(self, **kwargs) -> str | dict[str, Any]:
        try:
            query = kwargs.get("query", self.query)
            focus_mode = kwargs.get("focus_mode", self.focusMode)
            optimization_mode = kwargs.get("optimization_mode", self.optimizationMode)

            response = await self._async_search(
                query=query,
                focus_mode=focus_mode,
                optimization_mode=optimization_mode
            )

            if response is None:
                return "搜索请求失败"

            return self._format_result(response)

        except Exception as e:
            return f"搜索工具运行错误: {str(e)}"

    async def _async_search(self, query: str, focus_mode: str, optimization_mode: str) -> Optional[Dict[str, Any]]:
        """异步搜索实现"""
        url = f"{self.base_url}/api/search"

        payload = {
            "chatModel": self.chat_model,
            "embeddingModel": self.embedding_model,
            "optimizationMode": optimization_mode,
            "focusMode": focus_mode,
            "query": query,
            "history": []
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        loading = LoadingIndicator(f"正在搜索 '{query}' (模式: {focus_mode})")
        loading.start()

        try:
            timeout = httpx.Timeout(self.timeout, connect=self.timeout)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                loading.stop()

                if response.status_code == 200:
                    return response.json()
                else:
                    error_msg = f"请求失败: HTTP {response.status_code}"
                    try:
                        error_details = response.json()
                        return {"error": f"{error_msg} - {error_details}"}
                    except:
                        return {"error": f"{error_msg} - {response.text}"}

        except httpx.TimeoutException:
            loading.stop()
            return {"error": "请求超时"}
        except Exception as e:
            loading.stop()
            return {"error": f"请求出错: {str(e)}"}
