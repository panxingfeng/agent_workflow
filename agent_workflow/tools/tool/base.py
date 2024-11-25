from abc import ABC, abstractmethod

from config.config import SUMMARY_PROMPTS


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


def generate_summary(llm, content: str, tool_name: str) -> str:
    """生成内容总结"""
    prompt_template = SUMMARY_PROMPTS[tool_name, ""]
    if not prompt_template:
        return content

    formatted_prompt = prompt_template.format(content=content)
    return ''.join(llm.chat(
        message=formatted_prompt,
        prompt="请提供专业分析"
    )).strip()
