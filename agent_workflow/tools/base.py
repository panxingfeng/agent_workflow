import os
from dataclasses import dataclass
from enum import Enum
from typing import List, TypedDict, Dict, Any, Tuple

import validators


class InputType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    URL = "url"


@dataclass
class Input:
    type: InputType
    content: str


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
            InputType.FILE: ['.txt', '.pdf', '.doc', '.docx']
        }

    def validate_file(self, file_path: str, input_type: InputType) -> bool:
        if not os.path.exists(file_path):
            raise ValueError(f"文件不存在: {file_path}")
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.supported_extensions[input_type]:
            raise ValueError(f"不支持的文件类型: {ext}")
        return True

    def validate_url(self, url: str) -> bool:
        if not validators.url(url):
            raise ValueError("无效的URL地址")
        return True

    def process_input(self) -> UserQuery:
        attachments = []

        # 处理图片
        if self.images:
            for image in self.images:
                if self.validate_file(image, InputType.IMAGE):
                    attachments.append(Input(type=InputType.IMAGE, content=image))

        # 处理文件
        if self.files:
            for file in self.files:
                if self.validate_file(file, InputType.FILE):
                    attachments.append(Input(type=InputType.FILE, content=file))

        # 处理URL
        if self.urls:
            for url in self.urls:
                if self.validate_url(url):
                    attachments.append(Input(type=InputType.URL, content=url))

        return UserQuery(text=self.query, attachments=attachments)


class ConversionType(str, Enum):
    """转换类型"""
    URL_TO_PDF = "url_to_pdf"
    PDF_TO_WORD = "pdf_to_word"
    PDF_TO_TEXT = "pdf_to_text"
    PDF_TO_HTML = "pdf_to_html"
    PDF_TO_IMAGE = "pdf_to_image"
    PDF_TO_CSV = "pdf_to_csv"
    PDF_TO_XML = "pdf_to_xml"
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