"""
微信机器人实现类
负责处理微信消息的接收、处理和回复
包括登录认证、消息处理和状态管理等功能
感谢vchat作者<z2z63>,框架地址<https://github.com/z2z63/VChat>, 框架itchat原作者<LittleCoder(https://github.com/littlecodersh)>
"""

import asyncio
import logging
import os
import re
import time
from pathlib import Path
from typing import List, Optional

from vchat import Core
from vchat.model import ContentTypes, ContactTypes

from agent_workflow.utils.handler import ImageHandler, VoiceHandler, FileHandler, VideoHandler
from agent_workflow.tools.base import WeChatUserQuery


class VChat:
    """
    VChat机器人核心类

    功能：
    1. 微信登录和认证
    2. 消息接收和处理
    3. 自动回复
    4. 状态管理
    5. 错误处理

    属性：
        task_processor: 任务处理器，处理接收到的消息
        core: VChat核心实例，处理与微信的交互
        logger: 日志记录器
    """

    def __init__(self, task_processor):
        """
        初始化VChat实例

        Args:
            task_processor: 任务处理器实例，用于处理接收到的消息
        """
        self.task_processor = task_processor
        self.core = Core()
        self.setup_logging()

    def setup_logging(self):
        """
        配置日志系统
        设置日志格式和级别
        """
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    async def initialize_core(self):
        """
        初始化Core核心组件

        功能：
        1. 清理旧的登录缓存
        2. 初始化Core组件

        Raises:
            Exception: 初始化过程中的任何错误
        """
        try:
            # 清理旧登录状态
            if os.path.exists('wx_login_cache'):
                import shutil
                shutil.rmtree('wx_login_cache')
                self.logger.info("已清理旧的登录缓存")

            await self.core.init()
            self.logger.info("Core 初始化完成")
        except Exception as e:
            self.logger.error(f"初始化失败: {e}", exc_info=True)
            raise

    async def login(self, max_retries=3):
        """
        处理微信登录流程

        Args:
            max_retries: 最大重试次数，默认3次

        Returns:
            bool: 登录是否成功

        Raises:
            RuntimeError: 超过最大重试次数后仍然失败
        """
        for i in range(max_retries):
            try:
                self.logger.info(f"尝试登录 (第 {i + 1} 次)")
                await self.core.auto_login(hot_reload=False)
                self.logger.info("登录成功")
                return True
            except Exception as e:
                self.logger.error(f"登录尝试 {i + 1} 失败: {e}")
                if i < max_retries - 1:
                    await asyncio.sleep(2)  # 失败后等待2秒再重试
                else:
                    raise RuntimeError(f"登录失败，已尝试 {max_retries} 次")

    def _extract_file_path(self, message: str) -> Optional[str]:
        """提取文件路径"""
        match = re.search(r"输出路径：(.+)", message)
        return match.group(1).strip() if match else None

    def _extract_answer(self, message: str) -> Optional[str]:
        """提取回答内容"""
        match = re.search(r"回答：(.+)", message)
        return match.group(1).strip() if match else None

    async def _send_file_by_type(self, user_id: str, file_path: str):
        """根据文件类型发送文件"""
        result_path = Path(file_path)
        suffix = result_path.suffix.lower()

        if suffix in ['.jpg', '.jpeg', '.png', '.gif']:
            await self.core.send_image(to_username=user_id, file_path=result_path)
        elif suffix in ['.mp4', '.avi', '.mov']:
            await self.core.send_video(to_username=user_id, file_path=result_path)
        elif suffix in ['.mp3', '.wav', '.pdf', '.md', '.txt', '.docs', '.pptx']:
            await self.core.send_file(to_username=user_id, file_path=result_path)

    async def setup_message_handlers(self):
        """
        设置消息处理器
        配置接收到不同类型消息时的处理方法
        """
        # 初始化附件管理器和处理器
        self.upload_dir = Path("upload")
        self.upload_dir.mkdir(exist_ok=True)

        self.image_handler = ImageHandler(str(self.upload_dir))
        self.voice_handler = VoiceHandler(str(self.upload_dir))
        self.file_handler = FileHandler(str(self.upload_dir))
        self.video_handler = VideoHandler(str(self.upload_dir))

        # 用于存储用户上传的文件 {user_id: Path}
        self.user_attachments = {}

        @self.core.msg_register(msg_types=ContentTypes.TEXT, contact_type=ContactTypes.USER)
        @self.core.msg_register(msg_types=ContentTypes.ATTACH, contact_type=ContactTypes.USER)
        @self.core.msg_register(msg_types=ContentTypes.IMAGE, contact_type=ContactTypes.USER)
        @self.core.msg_register(msg_types=ContentTypes.VOICE, contact_type=ContactTypes.USER)
        @self.core.msg_register(msg_types=ContentTypes.VIDEO, contact_type=ContactTypes.USER)
        async def handle_message(msg):
            try:
                user_id = msg.from_.username
                user_name = msg.from_.nickname
                attachments: List[Path] = []

                async def handle_text(message_content):
                    """处理文本消息"""
                    try:
                        # 处理附件
                        if user_id in self.user_attachments:
                            attachments.append(self.user_attachments[user_id])

                        # 创建查询对象
                        query = WeChatUserQuery(
                            text=message_content,
                            attachments=attachments
                        )

                        # 处理消息
                        result = await self.task_processor.process(query)
                        message = result['result']
                        self.logger.info(f"处理结果: {result}")

                        # 处理文件路径
                        file_path = self._extract_file_path(message)
                        if file_path:
                            await self._send_file_by_type(user_id, file_path)
                            return

                        # 处理普通文本回答
                        result = self._extract_answer(message) or message
                        await self.core.send_msg(result, to_username=user_id)
                        return result

                    except Exception as e:
                        self.logger.error(f"处理消息失败: {str(e)}")
                        error_msg = "消息处理失败，请重试"
                        await self.core.send_msg(error_msg, to_username=user_id)
                        return error_msg

                if msg.content.type == ContentTypes.TEXT:
                    message_content = msg.content.content
                    self.logger.info(f"收到好友<{user_name}>文本消息<{message_content}>")
                    await handle_text(message_content)

                elif msg.content.type == ContentTypes.IMAGE:
                    self.logger.info(f"收到好友{user_name}的图片消息")
                    file_data = await msg.content.download_fn()
                    if file_data:
                        tmp_file_path = await self.image_handler.save_image(file_data)
                        file_name = Path(tmp_file_path).name
                        if file_name:
                            self.user_attachments[user_id] = Path(file_name)
                            attachments.append(Path(file_name))
                            await self.core.send_msg("图片已保存", to_username=user_id)
                        else:
                            await self.core.send_msg("图片保存失败", to_username=user_id)
                    else:
                        await self.core.send_msg("图片下载失败", to_username=user_id)

                elif msg.content.type == ContentTypes.VOICE:
                    import whisper
                    self.logger.info(f"收到好友{user_name}的语音消息")
                    file_data = await msg.content.download_fn()
                    if file_data:
                        tmp_file_path = await self.voice_handler.save_voice(file_data)
                        model = whisper.load_model("turbo")
                        result = model.transcribe(tmp_file_path)
                        if result is not None:
                            await handle_text(result["text"])
                        else:
                            await self.core.send_msg("语音识别失败", to_username=user_id)
                    else:
                        await self.core.send_msg("语音下载失败", to_username=user_id)


                elif msg.content.type in [ContentTypes.ATTACH, ContentTypes.VIDEO]:
                    self.logger.info(f"收到好友{user_name}的文件消息")
                    file_data = await msg.content.download_fn()
                    # 获取原始文件名
                    original_filename = getattr(msg.content, 'file_name', None)
                    try:
                        # 尝试从content中获取原始文件名
                        if not original_filename and hasattr(msg.content, 'content'):
                            content_info = msg.content.content
                            if isinstance(content_info, dict) and 'file_name' in content_info:
                                original_filename = content_info['file_name']
                    except:
                        pass
                    # 如果还是没有文件名，使用一个临时名称
                    if not original_filename:
                        original_filename = f"file_{int(time.time())}.mp3"  # 默认为mp3，稍后会根据内容检测
                    try:
                        # 确保文件名是UTF-8编码
                        original_filename = original_filename.encode('utf-8').decode('utf-8')
                    except UnicodeError:
                        original_filename = f"file_{int(time.time())}.mp3"
                    if file_data:
                        # 检查文件头部特征来判断实际文件类型
                        file_header = file_data[:4] if len(file_data) > 4 else file_data
                        # 识别MP3文件的特征 (常见的MP3文件头：ID3 或 MPEG ADTS)
                        is_mp3 = (file_header.startswith(b'ID3') or
                                  file_header.startswith(b'\xFF\xFB') or
                                  file_header.startswith(b'\xFF\xF3') or
                                  file_header.startswith(b'\xFF\xF2'))
                        if is_mp3 or original_filename.lower().endswith('.mp3'):
                            # 确保文件扩展名是.mp3
                            if not original_filename.lower().endswith('.mp3'):
                                original_filename = os.path.splitext(original_filename)[0] + '.mp3'
                            tmp_file_path = await self.voice_handler.save_voice(
                                file_data,
                                file_extension='.mp3'
                            )
                            file_type = "音频"
                        else:
                            tmp_file_path = await self.file_handler.save_file(file_data, original_filename)
                            file_type = "文件"
                        if tmp_file_path:
                            file_path = tmp_file_path.replace("upload/", "")
                            self.user_attachments[user_id] = Path(file_path)
                            attachments.append(Path(file_path))
                            await self.core.send_msg(f"{file_type}已保存", to_username=user_id)
                        else:
                            await self.core.send_msg(f"{file_type}保存失败", to_username=user_id)
                    else:
                        await self.core.send_msg("文件下载失败", to_username=user_id)

                return

            except Exception as e:
                error_msg = f"处理消息时出错: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                await self.core.send_msg(error_msg, to_username=msg.from_.username)
                return None

    async def start(self):
        """
        启动VChat机器人

        流程：
        1. 初始化核心组件
        2. 设置消息处理器
        3. 登录微信
        4. 发送启动通知
        5. 运行消息循环

        异常处理：
        - 记录所有错误
        - 保证正常关闭
        - 发送关闭通知
        """
        try:
            # 初始化核心组件
            await self.initialize_core()

            # 设置消息处理器
            await self.setup_message_handlers()
            self.logger.info("消息处理器设置完成")

            # 登录微信
            await self.login()

            # 发送启动通知
            try:
                await self.core.send_msg("VChat Bot已启动", to_username="filehelper")
                self.logger.info("启动通知发送成功")
            except Exception as e:
                self.logger.warning(f"发送启动通知失败: {e}")

            # 运行消息循环
            self.logger.info("开始运行消息循环")
            await self.core.run()

        except Exception as e:
            self.logger.error(f"VChat运行错误: {e}", exc_info=True)
            raise
        finally:
            try:
                # 发送关闭通知
                await self.core.send_msg("VChat Bot正在关闭", to_username="filehelper")
            except:
                pass
