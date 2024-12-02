from abc import ABC, abstractmethod

class BaseTool(ABC):
    """工具体基类"""

    @abstractmethod
    def get_description(self) -> str:
        """获取工具描述信息"""
        pass

    def get_parameter_rules(self) -> str:
        """返回工具的参数设置规则"""
        raise NotImplementedError

    @abstractmethod
    def run(self, **kwargs):
        """执行工具"""
        pass