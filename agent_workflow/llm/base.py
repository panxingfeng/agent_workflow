from openai import OpenAI

from config.config import OLLAMA_DATA, CHATGPT_DATA

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
