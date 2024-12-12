import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List
from datetime import datetime

from agent_workflow.utils.handler import ImageHandler, VoiceHandler, FileHandler, VideoHandler

SUPPORTED_FILE_TYPES = {
    'pdf': 'PDF文档',
    'doc': 'Word文档',
    'docx': 'Word文档',
    'txt': '文本文件',
    'md': 'Markdown文件',
    'jpg': '图片文件',
    'jpeg': '图片文件',
    'png': '图片文件',
    'mp3': '音频文件',
    'wav': '音频文件'
}

user_file_mapping = {}


class AttachmentManager:
    """管理用户上传的附件"""

    def __init__(self, max_files_per_user: int = 10):
        self.max_files = max_files_per_user
        # 确保upload目录存在
        self.upload_dir = Path("upload")
        self.upload_dir.mkdir(exist_ok=True)

        # 初始化各种文件处理器
        self.image_handler = ImageHandler(str(self.upload_dir))
        self.voice_handler = VoiceHandler(str(self.upload_dir))
        self.file_handler = FileHandler(str(self.upload_dir))
        self.video_handler = VideoHandler(str(self.upload_dir))

        self.user_files: Dict[str, Dict[str, List[tuple]]] = defaultdict(lambda: defaultdict(list))

    async def add_file(self, user_id: str, file_data: bytes, file_name: str) -> Path | None:
        """
        添加新文件到用户的文件列表

        Args:
            user_id: 用户ID
            file_data: 文件二进制数据
            file_name: 原始文件名

        Returns:
            Path: 新文件在upload目录下的路径
        """
        file_ext = os.path.splitext(file_name)[1].lower()

        # 根据文件类型选择对应的处理器并等待异步操作完成
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
            saved_path = await self.image_handler.save_image(file_data)
        elif file_ext in ['.mp3', '.wav']:
            saved_path = await self.voice_handler.save_voice(file_data, file_extension=file_ext)
        elif file_ext in ['.mp4', '.avi', '.mov']:
            saved_path = await self.video_handler.save_video(file_data)
        else:
            saved_path = await self.file_handler.save_file(file_data, file_name)

        if saved_path:
            # 转换为相对路径并存储
            relative_path = Path(saved_path).relative_to(os.getcwd())
            timestamp = datetime.now()

            files = self.user_files[user_id][file_ext]
            files.append((timestamp, relative_path))

            # 如果超过最大数量，删除最旧的文件
            if len(files) > self.max_files:
                files.sort(key=lambda x: x[0])
                old_file = files.pop(0)
                old_file_path = Path(old_file[1])
                if old_file_path.exists():
                    old_file_path.unlink()

            return relative_path
        return None

    async def get_recent_files(self, user_id: str, extension: str) -> List[Path]:
        """获取用户特定类型的最近文件列表"""
        if not extension.startswith('.'):
            extension = f'.{extension}'
        files = self.user_files[user_id][extension]
        return [f[1] for f in sorted(files, key=lambda x: x[0], reverse=True)]

    async def save_file_message_to_local(self, file_handler, file_path, file_name, user_name):
        file_extension = os.path.splitext(file_name)[1].lower().strip('.')

        if file_extension in SUPPORTED_FILE_TYPES:
            if file_path:
                bound_filename = f"{user_name}_{file_name}"
                tmp_file_path = await file_handler.save_file(file_path, bound_filename)

                if tmp_file_path:
                    user_file_mapping[user_name] = tmp_file_path
        else:
            print(f"收到不支持的文件类型: {file_extension}")
