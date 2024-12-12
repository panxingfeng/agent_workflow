from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from config.config import OLLAMA_DATA, CHATGPT_DATA


@dataclass
class ModelInput:
    """模型输入结构"""
    query: str
    prompt: str
    context: Optional[str] = None

    def validate(self):
        if not self.prompt.strip() and not self.query.strip():
            raise ValueError("提示词/用户问题不能为空")


def get_llm_instance(model_name: str, api_key: str) -> tuple[OpenAI, str, str]:
    """根据模型名称选择不同的LLM实现"""
    if model_name.lower().startswith("gpt"):
        llm = OpenAI(
            base_url=CHATGPT_DATA["api_url"],
            api_key=api_key,
        )
    else:
        llm = OpenAI(
            base_url=OLLAMA_DATA["api_url"],
            api_key="Empty",
        )
    return llm, model_name, api_key
