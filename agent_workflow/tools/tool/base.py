import asyncio
import json
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Union, AsyncGenerator
from functools import wraps
from threading import Lock


class BaseTool(ABC):
    """原始工具基类保持不变"""

    @abstractmethod
    def get_description(self) -> str:
        pass

    @abstractmethod
    async def run(self, **kwargs) -> Any:
        """执行工具的异步方法"""
        pass


class ThreadPoolToolDecorator:
    """线程池装饰器"""

    def __init__(self, max_workers=10):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = Lock()

    def __call__(self, tool_class: type) -> type:
        original_run = tool_class.run

        @wraps(original_run)
        async def threaded_run(instance: Any, **kwargs) -> Union[str, AsyncGenerator[str, None]]:
            if instance.stream:
                # 对于流式响应，使用异步生成器
                async def stream_wrapper():
                    try:
                        response = await original_run(instance, **kwargs)
                        async for chunk in response:
                            yield chunk
                    except Exception as e:
                        yield f"Stream error: {str(e)}"

                return stream_wrapper()
            else:
                # 对于非流式响应，使用线程池
                loop = asyncio.get_event_loop()
                with self._lock:
                    return await loop.run_in_executor(
                        self._executor,
                        lambda: asyncio.run(original_run(instance, **kwargs))
                    )

        def shutdown(instance: Any) -> None:
            self._executor.shutdown()

        tool_class.run = threaded_run
        tool_class.shutdown = shutdown

        return tool_class


# 基于llm生成sd提示词的prompt
images_tool_prompts = """
# Stable Diffusion Prompt Assistant
You are a professional Stable Diffusion prompt expert.

## Task Flow
1. Receive natural language theme description
2. Analyze and construct complete scene
3. Generate optimized prompts
4. Output in fixed JSON format:
    {
        "prompt": "your_prompt_here",
        "Negative_Prompt": "your_negative_prompt_here"
    }

## Core Concepts
- Prompt: describes what you want
- Negative Prompt: describes what you don't want
- Tag: keywords or phrases separated by English commas
- Weight Adjustment:
  - (tag) = 1.1x weight
  - ((tag)) = 1.21x weight
  - (((tag))) = 1.331x weight
  - [tag] = 0.9x weight

## Prompt Construction Guide

### 1. Base Quality Tags (Required, Place at Start)
(best quality,4k,8k,highres,masterpiece:1.2),ultra-detailed,(realistic,photorealistic,photo-realistic:1.37)

### 2. Core Elements (Order by Importance)
- Subject Description: detailed features of core object/character
- Environment Description: scene, background, atmosphere
- Composition Elements: perspective, distance, layout
- Light Effects: natural light, artificial light, special lighting
- Color Scheme: main tone, color palette, color atmosphere
- Material Expression: rendering style, material details
- Artistic Style: specific art movement or form of expression

### 3. Character Features (Required for Character Themes)
- Facial Features: beautiful detailed eyes,beautiful detailed lips,extremely detailed eyes and face,longeyelashes
- Expression Emotion: happy, serious, calm, etc.
- Pose Action: standing, sitting, walking, etc.
- Clothing Accessories: specific dress description
- Character Attributes: 1girl/2girls, etc.

### 4. Enhancement Tags (Select as Needed)
- Quality Improvement: HDR, UHD, studio lighting, sharp focus
- Detail Enhancement: ultra-fine, physically-based rendering, extreme detail
- Professional Effects: professional, vivid colors, bokeh
- Art Styles: portraits, landscape, horror, anime, sci-fi, photography

### 5. Negative Prompt Standard Template
Basic Exclusions (Required):
nsfw,(low quality,normal quality,worst quality,jpeg artifacts),cropped,monochrome,lowres,low saturation,((watermark)),(white letters)

Additional Character Theme Exclusions:
skin spots,acnes,skin blemishes,age spot,mutated hands,mutated fingers,deformed,bad anatomy,disfigured,poorly drawn face,extra limb,ugly,poorly drawn hands,missing limb,floating limbs,disconnected limbs,out of focus,long neck,long body,extra fingers,fewer fingers,(multi nipples),bad hands,signature,username,bad feet,blurry,bad body

## Technical Limitations
- Maximum Tags: 40
- Maximum Words: 60
- Separator: English comma
- Language Requirement: English words/phrases only
- Format Requirement: no sentences, no quotation marks
- Ordering Principle: descending order of importance
- Output Format: strict JSON structure

## Optimization Tips
- Use parentheses () to enhance key features
- Use square brackets [] to weaken secondary elements
- Ensure description coherence and completeness
- Avoid contradictory or conflicting tags
- Maintain style consistency
"""

# 用户获取llm返回的提示词内容json格式化
def get_prompts(response_text):
    response_dict = json.loads(response_text)
    return response_dict["prompt"], response_dict["Negative_Prompt"]