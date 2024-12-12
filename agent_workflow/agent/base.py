from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseAgent(ABC):
    """Agent基类"""

    @abstractmethod
    def get_description(self) -> str:
        """获取Agent描述信息"""
        pass

    @abstractmethod
    def get_parameter_rules(self) -> str:
        """返回Agent的参数设置规则"""
        raise NotImplementedError

    @abstractmethod
    async def run(self, **kwargs) -> Dict[str, Any]:
        """
        执行Agent

        Args:
            **kwargs: 输入参数

        Returns:
            Dict[str, Any]: 执行结果
        """
        pass