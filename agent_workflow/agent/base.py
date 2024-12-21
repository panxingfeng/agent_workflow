from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator


class BaseAgent(ABC):
    """Agent基类"""

    @abstractmethod
    def get_description(self) -> str:
        """获取Agent描述信息"""
        pass

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

    @abstractmethod
    async def run_with_status(self, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        执行Agent并提供状态更新

        Args:
            **kwargs: 输入参数，必须包含 message_id

        Yields:
            Dict[str, Any]: 状态更新信息，格式如下：
            {
                "type": str,  # "thinking_process" | "result" | "error"
                "message_id": str,
                "content": str
            }
        """
        raise NotImplementedError