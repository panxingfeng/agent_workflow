import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, TypedDict, Dict, Any, Tuple, Union

import validators


class InputType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    URL = "url",
    AUDIO = "audio"


@dataclass
class Input:
    type: InputType
    content: str


@dataclass
class WeChatUserQuery:
    def __init__(self, text: str, attachments: List[Union[str, Path]]):
        self.text = text
        self.attachments: List[Input] = []

        # 转换所有附件为 Input 对象
        for attachment in attachments:
            path = Path(attachment)
            # 根据文件扩展名判断类型
            ext = path.suffix.lower()
            if ext in ['.jpg', '.png']:
                input_type = InputType.IMAGE
            elif ext in ['.mp3', '.wav']:
                input_type = InputType.AUDIO
            else:
                input_type = InputType.FILE

            self.attachments.append(Input(
                type=input_type,
                content=str(path)
            ))

@dataclass
class FeishuUserQuery:
    def __init__(self, text: str, attachments: List[Union[str, Path]]):
        self.text = text
        self.attachments: List[Input] = []

        # 转换所有附件为 Input 对象
        for attachment in attachments:
            path = Path(attachment)
            # 根据文件扩展名判断类型
            ext = path.suffix.lower()
            if ext in ['.jpg', '.png']:
                input_type = InputType.IMAGE
            elif ext in ['.mp3', '.wav']:
                input_type = InputType.AUDIO
            else:
                input_type = InputType.FILE

            self.attachments.append(Input(
                type=input_type,
                content=str(path)
            ))

@dataclass
class UserQuery:
    text: str
    attachments: List[Input] | None


class MessageInput:
    def __init__(self, query: str, images: List[str] = None, files: List[str] = None, urls: List[str] = None):
        self.query = query
        self.images = images if images and any(images) else None
        self.files = files if files and any(files) else None
        self.urls = urls if urls and any(urls) else None
        self.supported_extensions = {
            InputType.IMAGE: ['.jpg', '.png', '.jpeg'],
            InputType.FILE: ['.txt', '.pdf', '.doc', '.docx', '.md'],
            InputType.AUDIO: ['.mp3', '.wav']
        }

    def get_file_type(self, file_path: str) -> InputType | None:
        """
        根据文件扩展名判断文件类型
        Args:
            file_path: 文件路径
        Returns:
            InputType: 文件类型
        """
        if not file_path or not isinstance(file_path, str):
            return None

        ext = os.path.splitext(file_path)[1].lower()
        if not ext:  # 如果没有扩展名
            return None

        for input_type, extensions in self.supported_extensions.items():
            if ext in extensions:
                return input_type

        return None  # 如果找不到匹配的类型，返回 None 而不是抛出异常

    def validate_file(self, file_path: str, input_type: InputType) -> bool:
        """
        验证文件有效性
        Args:
            file_path: 文件路径
            input_type: 预期的输入类型
        Returns:
            bool: 验证结果
        """
        if not file_path or not input_type:
            return False

        if not os.path.exists("upload/" + file_path):
            return False

        actual_type = self.get_file_type(file_path)
        if actual_type is None or actual_type != input_type:
            return False

        return True

    def validate_url(self, url: str) -> bool:
        """验证URL有效性"""
        if not url or not isinstance(url, str):
            return False
        return validators.url(url) is True  # 确保返回布尔值

    def process_input(self) -> UserQuery:
        """
        处理输入并生成用户查询对象
        Returns:
            UserQuery: 用户查询对象
        """
        attachments = []

        # 处理图片
        if self.images:
            for image in self.images:
                if image and self.validate_file(image, InputType.IMAGE):
                    attachments.append(Input(type=InputType.IMAGE, content=image))

        # 处理文件
        if self.files:
            for file in self.files:
                if file:
                    file_type = self.get_file_type(file)
                    if file_type and self.validate_file(file, file_type):
                        attachments.append(Input(type=file_type, content=file))

        # 处理URL
        if self.urls:
            for url in self.urls:
                if url and self.validate_url(url):
                    attachments.append(Input(type=InputType.URL, content=url))

        return UserQuery(text=self.query, attachments=attachments)


class Message(TypedDict):
    role: str
    content: str


class TaskState(TypedDict):
    messages: List[Message]
    task_ledger: Dict[str, Any]
    task_plan: List[Tuple[str, str]]
    tool_results: Dict[str, Any]
    files: Dict[str, str]
