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
        # 处理输入列表，确保列表元素是字符串类型
        self.images = self._process_input_list(images) if images and any(images) else None
        self.files = self._process_input_list(files) if files and any(files) else None
        self.urls = self._process_input_list(urls) if urls and any(urls) else None
        self.supported_extensions = {
            InputType.IMAGE: ['.jpg', '.png', '.jpeg', '.gif'],  # 添加前端支持的格式
            InputType.FILE: ['.txt', '.pdf', '.doc', '.docx', '.md', '.json'],  # 添加 json 支持
            InputType.AUDIO: ['.mp3', '.wav']
        }

    def _process_input_list(self, input_list: List[Any]) -> List[str]:
        """处理输入列表，确保元素是字符串类型"""
        if not input_list:
            return []

        processed = []
        for item in input_list:
            if isinstance(item, list):
                # 如果是列表，取第一个元素
                if item and item[0]:
                    processed.append(str(item[0]))
            else:
                if item:
                    processed.append(str(item))
        return processed if processed else None

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

        try:
            # 处理前端文件路径格式
            if '/' in file_path:
                dir_name = file_path.split('/')[0]
                if dir_name == 'images':
                    return InputType.IMAGE
                elif dir_name == 'files':
                    return InputType.FILE

            # 原有的文件类型判断逻辑
            ext = os.path.splitext(file_path)[1].lower()
            if not ext:
                return None

            for input_type, extensions in self.supported_extensions.items():
                if ext in extensions:
                    return input_type

            return None

        except Exception as e:
            print(f"[Error] 获取文件类型失败: {str(e)}")
            return None

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

        try:
            # 确保处理的是字符串类型的路径
            file_path = str(file_path)

            # 处理前端上传的文件路径
            if file_path.startswith(('images/', 'files/')):
                full_path = os.path.join('upload', file_path)
            else:
                # 原有的路径处理逻辑
                if not os.path.exists("upload/" + file_path):
                    full_path = os.path.join('upload', input_type.value.lower(), file_path)
                else:
                    full_path = "upload/" + file_path

            # 验证文件存在性
            if not os.path.exists(full_path):
                print(f"[Warning] 文件不存在: {full_path}")
                return False

            # 验证文件类型
            actual_type = self.get_file_type(file_path)
            if actual_type is None or actual_type != input_type:
                print(f"[Warning] 文件类型不匹配: 预期 {input_type}, 实际 {actual_type}")
                return False

            return True

        except Exception as e:
            print(f"[Error] 验证文件失败: {str(e)}")
            return False

    def validate_url(self, url: str) -> bool:
        """验证URL有效性"""
        if not url or not isinstance(url, str):
            return False
        return validators.url(url) is True

    def process_input(self) -> UserQuery:
        """
        处理输入并生成用户查询对象
        Returns:
            UserQuery: 用户查询对象
        """
        attachments = []

        try:
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

            query = UserQuery(text=self.query, attachments=attachments)
            return query

        except Exception as e:
            print(f"[Error] 处理输入失败: {str(e)}")
            # 发生错误时返回只包含文本的查询对象
            return UserQuery(text=self.query, attachments=[])

    def __str__(self) -> str:
        """提供友好的字符串表示"""
        parts = [f"query='{self.query}'"]
        if self.images:
            parts.append(f"images={self.images}")
        if self.files:
            parts.append(f"files={self.files}")
        if self.urls:
            parts.append(f"urls={self.urls}")
        return f"MessageInput({', '.join(parts)})"

    def __repr__(self) -> str:
        """提供详细的对象表示"""
        return str(self)


class Message(TypedDict):
    role: str
    content: str


class TaskState(TypedDict):
    messages: List[Message]
    task_ledger: Dict[str, Any]
    task_plan: List[Tuple[str, str]]
    tool_results: Dict[str, Any]
    files: Dict[str, str]
