# -*- coding: utf-8 -*-
"""
自定义工具示例代码

创建步骤：
1. 定义数据模型（可选）
2. 定义工具类
3. 实现必要的方法
4. 添加错误处理
"""

import json
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from agent_workflow.tools.tool.base import BaseTool


# 第一步：定义数据模型（如果需要）
class CustomResponse(BaseModel):
    """响应数据模型"""
    field1: str = Field(..., description="字段1说明")
    field2: str = Field(..., description="字段2说明")
    extra_info: Optional[Dict[str, Any]] = Field(default=None)


# 可选：定义枚举类型
class CustomMode(str, Enum):
    """工具模式枚举"""
    MODE1 = "mode1"
    MODE2 = "mode2"

    @classmethod
    def list_modes(cls) -> List[str]:
        """获取所有模式"""
        return [mode.value for mode in cls]


# 第二步：创建工具类
class CustomTool(BaseTool):
    """自定义工具类"""

    def __init__(self, param1: str = None, param2: str = None):
        """
        初始化工具

        Args:
            param1: 参数1说明
            param2: 参数2说明
        """
        self.param1 = param1
        self.param2 = param2
        # 添加其他需要的初始化

    def get_description(self) -> str:
        """返回工具描述信息"""
        tool_info = {
            "name": "CustomTool",
            "description": "工具功能描述",
            "parameters": {
                "param1": {
                    "type": "string",
                    "description": "参数1说明",
                    "required": True
                },
                "param2": {
                    "type": "string",
                    "description": "参数2说明",
                    "required": False
                }
            }
        }
        return json.dumps(tool_info, ensure_ascii=False)

    def get_parameter_rules(self) -> str:
        """返回参数设置规则说明"""
        return """
        CustomTool 参数规则:
        - param1: 参数1说明
          - 示例: "示例值"
          - 规则: 参数规则说明
        - param2: 参数2说明
          - 示例: "示例值"
          - 规则: 参数规则说明
        """

    def _format_result(self, response: CustomResponse) -> str:
        """格式化结果输出"""
        # 实现结果格式化逻辑
        return f"Field1: {response.field1}\nField2: {response.field2}"

    async def run(self, **kwargs) -> str:
        """
        执行工具逻辑

        Args:
            **kwargs: 参数字典

        Returns:
            str: 执行结果
        """
        try:
            # 1. 获取参数
            self.param1 = kwargs.get('param1', self.param1)
            if not self.param1:
                return "错误：缺少必要参数param1"

            # 2. 执行主要逻辑
            response = CustomResponse(
                field1="处理结果1",
                field2="处理结果2"
            )

            # 3. 格式化并返回结果
            return self._format_result(response)

        except Exception as e:
            return f"工具执行出错: {str(e)}"
