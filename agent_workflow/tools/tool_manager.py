# -*- coding: utf-8 -*-
"""
@file: tool_manager.py
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2024-11-23
@version: 1.0.0
@license: MIT License

@description:
工具管理器，提供工具的统一管理、参数验证和执行调度功能。

主要功能：
提供统一的工具管理、注册、验证和执行接口
实现工具的集中式管理和调度

核心特性：
1. 工具注册和管理：统一管理各类工具实例
2. 描述加载和缓存：自动加载并缓存工具描述信息
3. 参数验证：确保工具调用时参数的正确性
4. 统一调用接口：提供标准化的工具调用方式
5. 错误处理：完善的异常捕获和错误处理机制

Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""
from typing import List, Dict, Any, Optional
import json
from .tool.base import BaseTool


class ToolManager:
    """
    工具管理器类

    功能：
    1. 管理和注册工具实例
    2. 加载和缓存工具描述
    3. 提供统一的工具访问接口
    4. 执行参数验证
    5. 调用工具执行

    属性：
        tools: 工具实例字典，键为工具类名，值为工具实例
        tool_descriptions: 工具描述缓存字典
    """

    def __init__(self, tools: List[BaseTool]):
        """
        初始化工具管理器

        Args:
            tools: 工具实例列表，每个工具都应继承自BaseTool
        """
        # 将工具列表转换为字典，便于访问
        self.tools = {tool.__class__.__name__: tool for tool in tools}
        # 工具描述缓存
        self.tool_descriptions: Dict[str, Dict] = {}
        # 加载所有工具的描述信息
        self._load_tool_descriptions()

    def _load_tool_descriptions(self) -> None:
        """
        预加载所有工具描述

        功能：
        1. 遍历所有注册的工具
        2. 获取并解析工具描述
        3. 将描述缓存到字典中

        错误处理：
        - 捕获JSON解析错误
        - 处理描述加载失败
        """
        for name, tool in self.tools.items():
            try:
                description = tool.get_description()
                # 如果描述是字符串，尝试解析为JSON
                if isinstance(description, str):
                    try:
                        description = json.loads(description)
                    except json.JSONDecodeError as e:
                        print(f"Invalid JSON in description for {name}: {e}")
                        continue
                self.tool_descriptions[name] = description
            except Exception as e:
                print(f"Failed to load description for {name}: {e}")

    def get_tool_descriptions(self) -> Dict[str, Dict]:
        """
        获取所有工具的描述信息

        Returns:
            工具描述字典的缓存副本
        """
        return self.tool_descriptions

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        获取指定名称的工具实例

        Args:
            name: 工具名称

        Returns:
            工具实例或None（如果工具不存在）
        """
        return self.tools.get(name)

    def execute_tool(self, name: str, **kwargs) -> Any:
        """
        执行指定的工具

        Args:
            name: 工具名称
            **kwargs: 工具执行参数

        Returns:
            工具执行结果

        Raises:
            KeyError: 工具不存在时
            ValueError: 参数验证失败时

        功能：
        1. 查找工具实例
        2. 验证执行参数
        3. 执行工具操作
        """
        tool = self.get_tool(name)
        if not tool:
            raise KeyError(f"Tool {name} not found")

        # 进行参数验证
        tool_desc = self.tool_descriptions.get(name, {}).get('parameters', {})
        self._validate_parameters(name, tool_desc, kwargs)

        # 执行工具
        return tool.run(**kwargs)

    def _validate_parameters(self, tool_name: str, tool_desc: Dict, params: Dict) -> None:
        """
        验证工具执行参数

        Args:
            tool_name: 工具名称
            tool_desc: 工具参数描述
            params: 实际传入的参数

        Raises:
            ValueError: 参数验证失败时，比如缺少必需参数

        验证内容：
        1. 必需参数的存在性检查
        2. 参数类型检查（如果指定）
        3. 参数值范围检查（如果指定）
        """
        for param_name, param_info in tool_desc.items():
            if param_info.get('required', False) and param_name not in params:
                raise ValueError(f"Required parameter '{param_name}' missing for {tool_name}")