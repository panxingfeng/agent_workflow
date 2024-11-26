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
            if ext in ['.jpg', '.jpeg', '.png', '.gif']:
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
    attachments: List[Input]


class MessageInput:
    def __init__(self, query: str, images: List[str] = None, files: List[str] = None, urls: List[str] = None):
        self.query = query
        self.images = images
        self.files = files
        self.urls = urls
        self.supported_extensions = {
            InputType.IMAGE: ['.jpg', '.png', '.jpeg'],
            InputType.FILE: ['.txt', '.pdf', '.doc', '.docx', '.md'],
            InputType.AUDIO: ['.mp3', '.wav', '.flac', '.ogg', '.m4a']
        }

    def get_file_type(self, file_path: str) -> InputType:
        """
        根据文件扩展名判断文件类型

        Args:
            file_path: 文件路径

        Returns:
            InputType: 文件类型
        """
        ext = os.path.splitext(file_path)[1].lower()

        # 检查文件类型
        for input_type, extensions in self.supported_extensions.items():
            if ext in extensions:
                return input_type

        # 如果没找到匹配的类型，列出所有支持的格式
        supported_exts = []
        for exts in self.supported_extensions.values():
            supported_exts.extend(exts)
        raise ValueError(f"不支持的文件类型: {ext}\n支持的文件类型: {', '.join(supported_exts)}")

    def validate_file(self, file_path: str, input_type: InputType) -> bool:
        """
        验证文件有效性

        Args:
            file_path: 文件路径
            input_type: 预期的输入类型

        Returns:
            bool: 验证结果
        """
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise ValueError(f"文件不存在: {file_path}")

        # 检查文件类型是否匹配
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.supported_extensions[input_type]:
            # 尝试自动判断文件类型
            actual_type = self.get_file_type(file_path)
            if actual_type != input_type:
                supported = ', '.join(self.supported_extensions[input_type])
                raise ValueError(f"文件类型不匹配: 期望 {input_type.value} ({supported}), 实际是 {actual_type.value}")
        return True

    def validate_url(self, url: str) -> bool:
        """验证URL有效性"""
        if not validators.url(url):
            raise ValueError("无效的URL地址")
        return True

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
                try:
                    if self.validate_file(image, InputType.IMAGE):
                        attachments.append(Input(type=InputType.IMAGE, content=image))
                except ValueError as e:
                    print(f"处理图片时出错: {str(e)}")

        # 处理文件
        if self.files:
            for file in self.files:
                try:
                    # 尝试判断文件类型
                    file_type = self.get_file_type(file)
                    if self.validate_file(file, file_type):
                        attachments.append(Input(type=file_type, content=file))
                except ValueError as e:
                    print(f"处理文件时出错: {str(e)}")

        # 处理URL
        if self.urls:
            for url in self.urls:
                try:
                    if self.validate_url(url):
                        attachments.append(Input(type=InputType.URL, content=url))
                except ValueError as e:
                    print(f"处理URL时出错: {str(e)}")

        return UserQuery(text=self.query, attachments=attachments)


class ConversionType(str, Enum):
    """转换类型"""
    URL_TO_PDF = "url_to_pdf"
    PDF_TO_WORD = "pdf_to_word"
    PDF_TO_TEXT = "pdf_to_text"
    PDF_TO_HTML = "pdf_to_html"
    PDF_TO_IMAGE = "pdf_to_image"
    PDF_TO_PPT = "pdf_to_ppt"
    PDF_TO_MARKDOWN = "pdf_to_markdown"
    FILE_TO_PDF = "file_to_pdf"
    MARKDOWN_TO_PDF = "markdown_to_pdf"


class Message(TypedDict):
    role: str
    content: str


class TaskState(TypedDict):
    messages: List[Message]
    task_ledger: Dict[str, Any]
    task_plan: List[Tuple[str, str]]
    tool_results: Dict[str, Any]
    files: Dict[str, str]
