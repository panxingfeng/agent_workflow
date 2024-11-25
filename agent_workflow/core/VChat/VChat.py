"""
微信机器人实现类
负责处理微信消息的接收、处理和回复
包括登录认证、消息处理和状态管理等功能
感谢vchat作者<z2z63>,框架地址<https://github.com/z2z63/VChat>, 框架itchat-uos原作者<LittleCoder(https://github.com/littlecodersh)>
"""

import asyncio
import logging
import os

from vchat import Core
from vchat.model import ContentTypes, ContactTypes
from agent_workflow.tools.base import UserQuery


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

    async def setup_message_handlers(self):
        """
        设置消息处理器
        配置接收到不同类型消息时的处理方法
        """

        @self.core.msg_register(msg_types=ContentTypes.TEXT, contact_type=ContactTypes.USER)
        async def handle_message(msg):
            """
            处理接收到的文本消息

            Args:
                msg: 接收到的消息对象，包含发送者信息和消息内容

            Returns:
                处理结果或None（处理失败时）
            """
            try:
                # 提取消息信息
                user_id = msg.from_.username
                user_name = msg.from_.nickname
                message_content = msg.content.content
                self.logger.info(f"收到好友<{user_name}>消息<{message_content}>")

                # 创建查询对象
                query = UserQuery(
                    text=message_content,
                    attachments=[]  # 目前仅处理文本，不包含附件
                )

                # 处理消息并获取结果
                result = await self.task_processor.process(query)
                self.logger.info(f"处理结果: {result}")

                # 发送回复
                if result:
                    await self.core.send_msg(str(result), to_username=user_id)
                return result

            except Exception as e:
                # 错误处理
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