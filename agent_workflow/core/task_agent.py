# -*- coding: utf-8 -*-
"""
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2025-1-16
@version: 2.1.0
@license: MIT License
Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""
import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Any, Optional, AsyncGenerator, TypeVar, Generic
from typing import List

import aiofiles
import psutil
import uvicorn
from fastapi import HTTPException, FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from faster_whisper import WhisperModel
from pydantic import BaseModel

from agent_workflow.tools.base import MessageInput
from config.config import MAX_CONCURRENT
from config.tool_config import LOCAL_PORT_ADDRESS, UI_HOST, UI_PORT
from .FeiShu import Feishu
from .VChat import VChat
from .tool_executor import ToolExecutor
from ..rag.lightrag_mode import DocumentProcessor
from ..utils import loadingInfo
from ..utils.read_files import get_project_root
import weakref

# 获取项目根目录和输出目录
project_root = get_project_root()
output_dir = project_root / 'output'
upload_dir = project_root / 'upload'
upload_images_dir = upload_dir / 'images'
upload_files_dir = upload_dir / 'files'
history_data_dir = project_root / 'data'
rag_data_dir = history_data_dir / 'rag_data'

# 配置日志
logger = loadingInfo("task_agent")


class AgentStatus(Enum):
    """代理状态枚举类"""
    IDLE = "idle"  # 空闲状态
    RUNNING = "running"  # 运行中
    SUCCESS = "success"  # 执行成功
    FAILED = "failed"  # 执行失败
    VALIDATING = "validating"  # 验证中


class ExecutionMode(Enum):
    """执行模式枚举类"""
    SINGLE = "single"  # 单智能体模式
    MULTI = "multi"  # 多智能体模式
    AUTO = "auto"  # 自动选择模式


class ChatMessage(BaseModel):
    """聊天消息模型"""
    query: str
    response: str
    timestamp: datetime


class HistoryRecord(BaseModel):
    """历史记录数据模型"""
    conversation_id: str
    message_id: str
    title: Optional[str] = None
    timestamp: datetime
    messages: List[ChatMessage]
    pinned: bool = False
    starred: bool = False

class RagProcessRequest(BaseModel):
    """处理 RAG 任务的请求模型。"""
    files: List[str]
    rag_name: str

class DeleteRequest(BaseModel):
    """删除 RAG 相关数据或目录的请求模型。"""
    rag_name: str


class Segment(BaseModel):
    """语音识别片段模型"""
    start: float
    end: float
    text: str

class TranscriptionInfo(BaseModel):
    """转录信息模型"""
    language: str
    language_probability: float

class TranscriptionResponse(BaseModel):
    """完整的转录响应模型"""
    segments: List[Segment]
    info: TranscriptionInfo
    full_text: str

# 支持的音频格式
SUPPORTED_AUDIO_FORMATS = {
    '.mp3', '.wav', '.m4a', '.ogg', '.flac'
}

def check_and_rename(filename: str, directory: Path) -> str:
    """
    检查文件是否存在，如果存在则在末尾添加递增的数字
    """
    name = Path(filename).stem
    suffix = Path(filename).suffix

    counter = 1
    new_filename = filename

    while (directory / new_filename).exists():
        new_filename = f"{name}{counter}{suffix}"
        counter += 1

    return new_filename

sys_monitor_logger = loadingInfo(
    name="system_monitor",
    level=logging.INFO,
    log_file='system_monitor.log'
)

monitor_handler = RotatingFileHandler(
    filename='system_monitor.log',
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)

monitor_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

for handler in sys_monitor_logger.handlers[:]:
    if isinstance(handler, logging.FileHandler) and not isinstance(handler, RotatingFileHandler):
        sys_monitor_logger.removeHandler(handler)
sys_monitor_logger.addHandler(monitor_handler)


@dataclass
class SystemLoad:
    """系统负载信息"""
    cpu_percent: float
    memory_percent: float
    disk_usage_percent: float
    num_threads: int
    process_count: int
    timestamp: datetime


class SystemMonitor:
    """系统负载监控器"""
    def __init__(self,
                 cpu_threshold: float = 80.0,
                 memory_threshold: float = 85.0,
                 disk_threshold: float = 90.0):
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.disk_threshold = disk_threshold
        self._monitoring = False
        self._current_load = None

    def get_current_load(self) -> SystemLoad:
        """获取当前系统负载"""
        try:
            # CPU 使用率
            cpu_percent = psutil.cpu_percent(interval=1)

            # 内存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # 磁盘使用率
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent

            # 线程和进程数量
            current_process = psutil.Process()
            num_threads = current_process.num_threads()
            process_count = len(psutil.pids())

            self._current_load = SystemLoad(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_usage_percent=disk_percent,
                num_threads=num_threads,
                process_count=process_count,
                timestamp=datetime.now()
            )

            return self._current_load

        except Exception as e:
            sys_monitor_logger.error(f"获取系统负载失败: {e}")
            raise

    def is_system_overloaded(self) -> bool:
        """检查系统是否过载"""
        try:
            load = self.get_current_load()
            is_overloaded = (load.cpu_percent > self.cpu_threshold or
                             load.memory_percent > self.memory_threshold or
                             load.disk_usage_percent > self.disk_threshold)

            if is_overloaded:
                sys_monitor_logger.warning(f"系统负载过高! CPU: {load.cpu_percent}%, "
                                           f"内存: {load.memory_percent}%, "
                                           f"磁盘: {load.disk_usage_percent}%")
            return is_overloaded
        except Exception as e:
            sys_monitor_logger.error(f"检查系统负载失败: {e}")
            return True

    def get_detailed_status(self) -> Dict[str, Any]:
        """获取详细的系统状态"""
        try:
            memory = psutil.virtual_memory()
            cpu_freq = psutil.cpu_freq()
            disk = psutil.disk_usage('/')

            status = {
                'cpu': {
                    'percent': psutil.cpu_percent(interval=1),
                    'count': psutil.cpu_count(),
                    'freq_current': cpu_freq.current if cpu_freq else None,
                    'freq_max': cpu_freq.max if cpu_freq else None
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk.percent
                },
                'process': {
                    'count': len(psutil.pids()),
                    'threads': psutil.Process().num_threads()
                },
                'timestamp': datetime.now().isoformat()
            }

            return status

        except Exception as e:
            sys_monitor_logger.error(f"获取系统详细状态失败: {e}")
            raise

    async def start_monitoring(self, interval: float = 5.0):
        """开始持续监控系统负载"""
        self._monitoring = True
        while self._monitoring:
            try:
                load = self.get_current_load()
                status = self.get_detailed_status()

                # 检查是否需要报警
                if self.is_system_overloaded():
                    sys_monitor_logger.warning(
                        f"系统负载警告 - "
                        f"CPU({self.cpu_threshold}%): {status['cpu']['percent']}% | "
                        f"内存({self.memory_threshold}%): {status['memory']['percent']}% | "
                        f"磁盘({self.disk_threshold}%): {status['disk']['percent']}%"
                    )

                await asyncio.sleep(interval)

            except Exception as e:
                sys_monitor_logger.error(f"监控过程中出错: {e}")
                await asyncio.sleep(interval)

    def stop_monitoring(self):
        """停止监控"""
        self._monitoring = False

# 定义泛型类型
T = TypeVar('T')


class WeakSetManager(Generic[T]):
    """WeakSet管理器，支持类型提示"""

    def __init__(self):
        self._items: weakref.WeakSet = weakref.WeakSet()

    def add(self, item: T) -> None:
        """添加项目到集合"""
        self._items.add(item)

    def remove(self, item: T) -> None:
        """从集合中移除项目"""
        self._items.discard(item)

    def __len__(self) -> int:
        """获取集合大小"""
        return len(self._items)

    def __iter__(self):
        """迭代集合项目"""
        yield from self._items


class ResourceManager:
    """资源管理器"""
    def __init__(self, max_concurrent: int = 3):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_tasks: WeakSetManager[asyncio.Task] = WeakSetManager()
        self._lock = asyncio.Lock()
        self.system_monitor = SystemMonitor(
            cpu_threshold=80.0,
            memory_threshold=85.0,
            disk_threshold=90.0
        )
        asyncio.create_task(self.system_monitor.start_monitoring(interval=5.0))

    async def acquire(self) -> bool:
        """获取资源"""
        # 检查系统负载
        if self.system_monitor.is_system_overloaded():
            sys_monitor_logger.warning("系统负载过高，拒绝新任务")
            return False

        await self.semaphore.acquire()
        async with self._lock:
            current_task = asyncio.current_task()
            if current_task:
                self.active_tasks.add(current_task)
                sys_monitor_logger.info(f"任务获取资源 - 当前活动任务数: {len(self.active_tasks)}")
        return True

    async def release(self) -> None:
        """释放资源"""
        self.semaphore.release()
        async with self._lock:
            if current_task := asyncio.current_task():
                self.active_tasks.remove(current_task)
                sys_monitor_logger.info(f"任务释放资源 - 当前活动任务数: {len(self.active_tasks)}")

    def get_active_tasks(self) -> int:
        """获取当前活动任务数"""
        count = len(self.active_tasks)
        sys_monitor_logger.debug(f"当前活动任务数: {count}")
        return count

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return self.system_monitor.get_detailed_status()

class MasterAgent:
    """
    主控代理类
    负责管理和协调多个子代理，实现智能任务分发和执行。
    支持多种平台接入（FastAPI、飞书、微信）。
    """

    def __init__(self, tool_executor: ToolExecutor, verbose: bool):
        """
        初始化主控代理

        Args:
            tool_executor:工具执行器
        """
        self.status = AgentStatus.IDLE
        self._execution_lock = asyncio.Lock()
        self._file_lock = asyncio.Lock()
        self.message_id = None
        self.verbose = verbose

        self.executor = tool_executor
        self.resource_manager = ResourceManager(max_concurrent=MAX_CONCURRENT)
        self.task_queue = asyncio.Queue()

        asyncio.create_task(self._process_task_queue())

    async def _process_task_queue(self):
        """处理任务队列的后台任务"""
        while True:
            try:
                task_data = await self.task_queue.get()
                await asyncio.create_task(self._handle_single_task(task_data))
            except Exception as e:
                logger.error(f"任务处理错误: {e}")
            finally:
                self.task_queue.task_done()

    async def _handle_single_task(self, task_data: Dict):
        """处理单个任务"""
        try:
            if not await self.resource_manager.acquire():
                sys_monitor_logger.warning(f"资源不足，任务 {task_data.get('message_id')} 重新排队")
                await self.task_queue.put(task_data)
                await asyncio.sleep(1)
                return

            try:
                sys_monitor_logger.info(f"开始处理任务 {task_data.get('message_id')}")

                async for result in self.chat_ui_process(**task_data):
                    if isinstance(result, dict):
                        result_type = result.get("type")
                        if result_type == "error":
                            sys_monitor_logger.error(f"任务执行错误: {result.get('content')}")
                        elif result_type == "result":
                            sys_monitor_logger.info(f"任务产生结果: {result.get('content')[:100]}...")
                        elif result_type == "thinking_process":
                            sys_monitor_logger.debug(f"任务处理中: {result.get('content')}")

                sys_monitor_logger.info(f"完成任务 {task_data.get('message_id')}")

            except asyncio.CancelledError:
                sys_monitor_logger.warning(f"任务 {task_data.get('message_id')} 被取消")
                raise
            except Exception as inner_e:
                sys_monitor_logger.error(f"任务执行出错: {str(inner_e)}")
                raise
            finally:
                await self.resource_manager.release()
                sys_monitor_logger.debug(f"释放任务 {task_data.get('message_id')} 资源")

        except Exception as e:
            sys_monitor_logger.error(f"任务处理失败: {str(e)}")
            try:
                import traceback
                sys_monitor_logger.error(f"错误详情: {traceback.format_exc()}")
            except Exception:
                pass

    async def process(self, message_input: MessageInput) -> str:
        """处理用户消息"""
        try:
            # 检查系统负载
            if self.resource_manager.get_active_tasks() >= 3:  # 可配置的阈值
                return "系统负载较高，请稍后重试"

            # 获取资源锁
            if not await self.resource_manager.acquire():
                return "资源暂时不可用，请稍后重试"

            try:
                self.status = AgentStatus.RUNNING

                # 创建和等待任务结果
                result_future = asyncio.Future()
                await self.task_queue.put({
                    'type': 'process',
                    'input': message_input,
                    'future': result_future
                })

                # 等待处理完成
                result = await result_future

                if isinstance(result, dict):
                    link = result.get("link", "")
                    if "result" in result and "status" in result:
                        result_data = result["result"]
                        if result_data:
                            last_task = list(result_data.values())[-1]
                            final_result = last_task.get('result', '') + "\n" + link
                            logger.info("最终结果: {}".format(final_result))
                            self.status = AgentStatus.SUCCESS
                            return final_result

                self.status = AgentStatus.FAILED
                return "处理失败: 无法获取结果"

            finally:
                await self.resource_manager.release()

        except Exception as e:
            self.status = AgentStatus.FAILED
            error_msg = f"处理失败: {str(e)}"
            logger.error(error_msg)
            return error_msg

    async def vchat_demo(self):
        """启动VChat服务，实现微信接入"""
        bot = VChat(self)
        await bot.start()

    async def feishu_demo(self, port: int = 8070):
        """
        启动飞书服务

        Args:
            port: 服务端口号，默认8070
        """
        bot = Feishu(self)
        await bot.start(port=port)

    async def fastapi_demo(self, host="localhost", port=8000):
        """
        启动FastAPI服务器，提供HTTP接口

        Args:
            host: 服务主机地址，默认localhost
            port: 服务端口号，默认8000
        """
        from fastapi import HTTPException, FastAPI
        import uvicorn
        from pydantic import BaseModel

        app = FastAPI()

        class MessageRequest(BaseModel):
            """接口请求模型"""
            query: str  # 查询文本
            images: Optional[List[str]] = None  # 图片列表
            files: Optional[List[str]] = None  # 文件列表
            urls: Optional[List[str]] = None  # URL列表

        @app.post("/api/chat", response_model=None)
        async def process_message(message: MessageRequest):
            """
            处理消息的API接口

            Args:
                message: 消息请求对象

            Returns:
                处理结果

            Raises:
                HTTPException: 处理失败时抛出的异常
            """
            try:
                input_msg = MessageInput(
                    query=message.query,
                    images=message.images,
                    files=message.files,
                    urls=message.urls
                )
                result = await self.process(input_msg)
                try:
                    match = re.search(r"输出路径：(.+)", str(result))
                    result = match.group(1).strip()

                except Exception:
                    result = result
                return {"result": result}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        config = uvicorn.Config(app, host=host, port=port)
        server = uvicorn.Server(config)
        await server.serve()

    async def chat_ui_process(self,
                              url: str,
                              input_msg: MessageInput,
                              message_id: str,
                              conversation_id: str,
                              data_dir: Path,
                              context_length: int,
                              history_mode: str,
                              chat_ui) -> AsyncGenerator[Dict[str, Any], None]:
        global image_url, audio_url, file_url, file_name, output_file_path
        try:
            # 检查系统负载
            if self.resource_manager.get_active_tasks() >= MAX_CONCURRENT:
                yield {
                    "type": "warning",
                    "message_id": message_id,
                    "content": "系统负载较高，请稍后重试..."
                }
                return

            # 获取资源锁
            if not await self.resource_manager.acquire():
                yield {
                    "type": "error",
                    "message_id": message_id,
                    "content": "资源暂时不可用，请稍后重试"
                }
                return

            try:
                self.status = AgentStatus.RUNNING
                self.message_id = message_id

                # 开始处理
                yield {
                    "type": "thinking_process",
                    "message_id": message_id,
                    "content": "正在准备资源..."
                }

                async def load_context():
                    context_data = []
                    if history_mode == "json":
                        history_file = data_dir / 'chat_history.json'
                        if history_file.exists():
                            async with aiofiles.open(history_file, 'r', encoding='utf-8') as f:
                                content = await f.read()
                                if content.strip():
                                    history_data = json.loads(content)
                                    conversation = next(
                                        (conv for conv in history_data if conv['conversation_id'] == conversation_id),
                                        None
                                    )
                                    if conversation and conversation['messages']:
                                        context = conversation['messages'][-context_length:]
                                        context_data = [{'query': msg['query'], 'response': msg['response']} for msg in
                                                        context]
                    return context_data

                async def process_attachments():
                    attachments_info = {'images': [], 'files': []}
                    attachments_info_history = {'images': [], 'files': []}

                    async def process_single_file(file_path, file_type):
                        try:
                            if isinstance(file_path, str):
                                path = Path(file_path)
                                if path.exists():
                                    size = await asyncio.to_thread(os.path.getsize, path)
                                    info = {
                                        'original_name': path.name,
                                        'saved_path': str(path),
                                        'size': size
                                    }
                                    history_info = {
                                        'original_name': path.name,
                                        'saved_path': str(f"{url}/static/upload/{file_type}/{path.name}"),
                                        'size': size
                                    }
                                    return file_type, info, history_info
                        except Exception as e:
                            logger.error(f"处理文件失败 {file_path}: {e}")
                            return None

                    # 并行处理所有文件
                    tasks = []
                    if isinstance(input_msg, MessageInput):
                        if input_msg.images:
                            tasks.extend([process_single_file(img_path, 'images') for img_path in input_msg.images])
                        if input_msg.files:
                            tasks.extend([process_single_file(file_path, 'files') for file_path in input_msg.files])

                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        for result in results:
                            if result and not isinstance(result, Exception):
                                file_type, info, history_info = result
                                attachments_info[file_type].append(info)
                                attachments_info_history[file_type].append(history_info)

                    return attachments_info, attachments_info_history

                if not isinstance(data_dir, Path):
                    data_dir = Path(data_dir)
                data_dir.mkdir(exist_ok=True, parents=True)

                context_data, (attachments_info, attachments_info_history) = await asyncio.gather(
                    load_context(),
                    process_attachments()
                )

                processed_query = input_msg

                async for result in self.executor.execute_tools(
                        query=processed_query.process_input(),
                        history=context_data,
                        chat_ui=chat_ui
                ):
                    if isinstance(result, dict):
                        if "error" in result:
                            yield {
                                "type": "error",
                                "message_id": message_id,
                                "content": result.get("error", "处理失败")
                            }
                            return

                        elif result.get("status") == "success" and "result" in result:
                            async def process_result():
                                tool_response = result.get("result", {})
                                link_text = result.get("link", {})
                                if not tool_response:
                                    return None, None, None, None, None

                                final_result = list(tool_response.values())[-1]["result"]
                                files = []
                                images = []

                                if isinstance(final_result, str):
                                    if 'output\\' in final_result or 'output/' in final_result:
                                        try:
                                            match = re.search(r'输出路径：[ \t]*(.+?)(?:\n|$)', final_result)
                                            if match:
                                                file_path = match.group(1).strip().replace('\\', '/')
                                                file_extension = Path(file_path).suffix.lower()
                                                file_name = Path(file_path).name
                                                output_file_path = output_dir

                                                if output_file_path.exists():
                                                    if file_extension in ['.png', '.jpg', '.jpeg', '.gif']:
                                                        relative_path = f"{file_name}"
                                                        image_url = f"{url}/static/output/{relative_path}"
                                                        images.append({
                                                            'url': image_url,
                                                            'name': file_name
                                                        })
                                                        final_result = ""
                                                    elif file_extension == '.wav':
                                                        relative_path = f"{datetime.now().strftime('%Y-%m-%d')}/{file_name}"
                                                        audio_url = f"{url}/static/output/{relative_path}"
                                                        files.append({
                                                            'url': audio_url,
                                                            'name': file_name
                                                        })
                                                        final_result = ""
                                                    else:
                                                        relative_path = f"{file_name}"
                                                        file_url = f"{url}/static/output/{relative_path}"
                                                        files.append({
                                                            'url': file_url,
                                                            'name': file_name
                                                        })
                                                        final_result = ""
                                        except Exception as e:
                                            logger.error(f"处理文件失败: {e}")

                                return final_result, files, images, tool_response, link_text

                            final_result, files, images, tool_response, link_text = await process_result()
                            if final_result is not None:
                                if history_mode == "json":
                                    await asyncio.create_task(self._save_history(
                                        data_dir=data_dir,
                                        conversation_id=conversation_id,
                                        message_id=message_id,
                                        final_result=final_result,
                                        files=files,
                                        images=images,
                                        tool_response=tool_response,
                                        link_text=link_text,
                                        processed_query=processed_query,
                                        attachments_info_history=attachments_info_history
                                    ))

                                processed_result = {
                                    'type': 'mixed',
                                    'text': final_result,
                                    'files': files if files else [],
                                    'images': images if images else [],
                                }

                                if link_text:
                                    processed_result['text'] = final_result + "\n" + link_text

                                yield {
                                    "type": "result",
                                    "message_id": message_id,
                                    "content": processed_result['text']
                                }

                        elif "type" in result:
                            if result["type"] == "thinking_process":
                                yield {
                                    "type": "thinking_process",
                                    "message_id": message_id,
                                    "content": result.get("content", "处理中...")
                                }
                            else:
                                yield {
                                    **result,
                                    "message_id": message_id
                                }

                self.status = AgentStatus.SUCCESS
                yield {
                    "type": "thinking_process",
                    "message_id": message_id,
                    "content": "✓ 处理完成"
                }

            finally:
                await self.resource_manager.release()

        except Exception as e:
            self.status = AgentStatus.FAILED
            error_msg = f"处理失败: {str(e)}"
            logger.error(f"{error_msg}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            yield {
                "type": "error",
                "message_id": message_id,
                "content": error_msg
            }

    async def _save_history(self, data_dir, conversation_id, message_id, final_result,
                            files, images, tool_response, link_text, processed_query,
                            attachments_info_history):
        """异步保存历史记录"""
        try:
            async with self._file_lock:
                history_file = data_dir / 'chat_history.json'
                history_data = []

                if history_file.exists():
                    async with aiofiles.open(history_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        if content.strip():
                            history_data = json.loads(content)

                current_time = datetime.now().isoformat()
                conversation = next(
                    (conv for conv in history_data if conv['conversation_id'] == conversation_id),
                    None
                )

                processed_result = {
                    'type': 'mixed',
                    'text': final_result,
                    'files': files if files else [],
                    'images': images if images else [],
                }

                if link_text:
                    processed_result['text'] = final_result + "\n" + link_text

                new_message = {
                    'query': processed_query.query,
                    'response': processed_result,
                    'timestamp': current_time,
                    'reason': tool_response,
                    'attachments': attachments_info_history
                }

                if conversation:
                    conversation['timestamp'] = current_time
                    conversation['messages'].append(new_message)
                else:
                    conversation = {
                        'conversation_id': conversation_id,
                        'message_id': message_id,
                        'title': processed_query.query[:30] or '新对话',
                        'timestamp': current_time,
                        'pinned': False,
                        'starred': False,
                        'messages': [new_message]
                    }
                    history_data.append(conversation)

                async with aiofiles.open(history_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(history_data, ensure_ascii=False, indent=2))

        except Exception as e:
            logger.error(f"保存历史记录失败: {str(e)}")

    async def chat_ui_demo(self, url=LOCAL_PORT_ADDRESS, history_mode: str = "json"):
        """
        启动FastAPI服务器，提供HTTP接口和静态文件服务
        """
        app = FastAPI()

        try:
            model = WhisperModel(
                model_size_or_path="large-v3",
                device="cuda",
                compute_type="float16"
            )
            logger.info("Whisper模型加载成功")
        except Exception as e:
            logger.error(f"加载Whisper模型失败: {str(e)}")
            model = None

        def check_ffmpeg():
            try:
                subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return True
            except FileNotFoundError:
                logger.error("ffmpeg not found. Please install ffmpeg.")
                return False

        def convert_audio(input_path: str) -> str:
            """转换音频到合适的格式"""
            output_path = input_path + '.converted.wav'
            try:
                cmd = [
                    'ffmpeg',
                    '-i', input_path,
                    '-ar', '16000',
                    '-ac', '1',
                    '-y',
                    output_path
                ]

                process = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                if process.returncode != 0:
                    logger.error(f"音频转换失败: {process.stderr}")
                    raise Exception(f"音频转换失败: {process.stderr}")

                return output_path
            except Exception as e:
                logger.error(f"音频转换出错: {str(e)}")
                raise

        # CORS配置
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 确保输出目录存在
        output_dir.mkdir(exist_ok=True)
        history_data_dir.mkdir(exist_ok=True)
        upload_images_dir.mkdir(exist_ok=True)
        upload_files_dir.mkdir(exist_ok=True)
        upload_dir.mkdir(exist_ok=True)
        rag_data_dir.mkdir(exist_ok=True)

        # 配置静态文件目录
        app.mount("/static/output", StaticFiles(directory=str(output_dir)), name="static")
        app.mount("/static/upload", StaticFiles(directory=str(upload_dir)), name="static")

        @app.post("/api/speech-to-text", response_model=TranscriptionResponse)
        async def speech_to_text(audio_file: UploadFile):
            """处理音频文件并返回识别结果"""
            if not model:
                raise HTTPException(status_code=500, detail="语音识别模型未正确加载")

            if not check_ffmpeg():
                raise HTTPException(status_code=500, detail="服务器未安装ffmpeg")

            temp_input_path = None
            temp_converted_path = None

            try:
                with tempfile.NamedTemporaryFile(delete=False,
                                                 suffix=os.path.splitext(audio_file.filename)[1]) as temp_input:
                    content = await audio_file.read()
                    temp_input.write(content)
                    temp_input_path = temp_input.name

                temp_converted_path = convert_audio(temp_input_path)

                segments, info = model.transcribe(
                    temp_converted_path,
                    beam_size=5,
                    language="zh",
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=500
                    )
                )

                segments_list = []
                full_text = []

                for segment in segments:
                    segments_list.append(Segment(
                        start=segment.start,
                        end=segment.end,
                        text=segment.text.strip()
                    ))
                    full_text.append(segment.text.strip())

                response = TranscriptionResponse(
                    segments=segments_list,
                    info=TranscriptionInfo(
                        language=info.language,
                        language_probability=info.language_probability
                    ),
                    full_text=" ".join(full_text)
                )
                return response

            except Exception as e:
                logger.error(f"处理音频时发生错误: {str(e)}")
                raise HTTPException(status_code=500, detail=f"处理音频失败: {str(e)}")

            finally:
                for temp_file in [temp_input_path, temp_converted_path]:
                    if temp_file and os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except Exception as e:
                            logger.error(f"删除临时文件失败 {temp_file}: {str(e)}")

        @app.get("/api/file-url")
        async def get_file_url(file_path: str):
            try:
                file_name = Path(file_path).name
                file_extension = Path(file_path).suffix.lower()

                # 如果传入的是完整路径（包含子目录），解析出子目录
                sub_dir = str(Path(file_path).parent)
                if sub_dir == '.':
                    sub_dir = ''

                # 在 upload_dir 中查找（考虑子目录）
                if sub_dir:
                    # 有子目录的情况
                    upload_file_path = upload_dir / sub_dir / file_name
                    if upload_file_path.exists():
                        relative_path = f"upload/{sub_dir}/{file_name}"
                        return {
                            "url": f"{url}/static/{relative_path}",
                            "filename": file_name,
                            "size": os.path.getsize(upload_file_path)
                        }
                else:
                    # 没有子目录的情况，检查常见子目录
                    # 检查 images 子目录
                    upload_image_path = upload_dir / 'images' / file_name
                    if upload_image_path.exists():
                        return {
                            "url": f"{url}/static/upload/images/{file_name}",
                            "filename": file_name,
                            "size": os.path.getsize(upload_image_path)
                        }

                    # 检查 files 子目录
                    upload_file_path = upload_dir / 'files' / file_name
                    if upload_file_path.exists():
                        return {
                            "url": f"{url}/static/upload/files/{file_name}",
                            "filename": file_name,
                            "size": os.path.getsize(upload_file_path)
                        }

                    # 检查根目录
                    upload_root_path = upload_dir / file_name
                    if upload_root_path.exists():
                        return {
                            "url": f"{url}/static/upload/{file_name}",
                            "filename": file_name,
                            "size": os.path.getsize(upload_root_path)
                        }

                # 在 output_dir 中查找
                output_file_path = output_dir
                if output_file_path.exists():
                    if file_extension in ['.png', '.jpg', '.jpeg', '.gif']:
                        relative_path = f"{file_name}"
                    elif file_extension == '.wav':
                        relative_path = f"{datetime.now().strftime('%Y-%m-%d')}/{file_name}"
                    else:
                        relative_path = f"{file_name}"
                    return {
                        "url": f"{url}/static/output/{relative_path}",
                        "filename": file_name,
                        "size": os.path.getsize(output_file_path)
                    }

                # 如果所有位置都没找到文件
                logger.info(f"文件不存在: {file_name}")
                raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

            except Exception as e:
                logger.error(f"Error in get_file_url: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/upload")
        async def upload_file(
                images: List[UploadFile] = File(None),
                files: List[UploadFile] = File(None)
        ):
            try:
                results = []

                # 处理图片上传
                if images:
                    for image in images:
                        try:
                            # 检查文件名是否存在
                            filename = check_and_rename(image.filename, upload_images_dir)
                            file_path = upload_images_dir / filename

                            # 保存文件
                            async with aiofiles.open(file_path, 'wb') as f:
                                content = await image.read()
                                await f.write(content)

                            # 获取文件URL
                            file_info = await get_file_url(f"images/{filename}")
                            results.append({
                                "url": file_info['url'],
                                "path": str(filename),
                                "name": image.filename,
                                "size": file_info['size']
                            })

                        except Exception as e:
                            logger.error(f"Failed to upload image {image.filename}: {e}")
                            raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")

                # 处理文件上传
                if files:
                    for file in files:
                        try:
                            # 检查文件名是否存在
                            filename = check_and_rename(file.filename, upload_files_dir)
                            file_path = upload_files_dir / filename

                            async with aiofiles.open(file_path, 'wb') as f:
                                content = await file.read()
                                await f.write(content)

                            file_info = await get_file_url(f"files/{filename}")
                            results.append({
                                "url": file_info['url'],
                                "path": str(filename),
                                "name": file.filename,
                                "size": file_info['size']
                            })

                        except Exception as e:
                            logger.error(f"Failed to upload file {file.filename}: {e}")
                            raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

                return {
                    "files": results
                }

            except Exception as e:
                logger.error(f"Upload failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.delete("/api/delete")
        async def delete_file(path: str):
            try:
                # 确保路径是有效的
                if not path or '..' in path:
                    raise HTTPException(status_code=400, detail="Invalid path")

                # 判断文件类型和路径
                if any(path.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                    file_path = (project_root / 'upload' / 'images' / path).resolve()
                else:
                    file_path = (project_root / 'upload' / 'files' / path).resolve()

                # 规范化路径
                file_path = file_path.resolve()
                upload_dir = (project_root / 'upload').resolve()

                # 安全检查：确保文件在上传目录中
                if not str(file_path).startswith(str(upload_dir)):
                    logger.error(f"Access denied - files path: {file_path} not in upload dir: {upload_dir}")
                    raise HTTPException(status_code=403, detail="Access denied")

                if not file_path.exists():
                    logger.info(f"File not found: {file_path}")
                    raise HTTPException(status_code=404, detail="File not found")

                if not file_path.is_file():
                    logger.error(f"Path is not a files: {file_path}")
                    raise HTTPException(status_code=400, detail="Not a files")

                # 删除文件
                file_path.unlink()

                return {
                    "success": True,
                    "path": str(path),
                    "message": "File deleted successfully"
                }

            except HTTPException:
                raise
            except Exception as e:
                print(f"[Error] Delete failed: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to delete files: {str(e)}")

        @app.get("/api/rag/list")
        async def list_rags():
            try:
                rag_base_dir = (project_root / 'data' / 'rag_data').resolve()
                if not rag_base_dir.exists():
                    return {
                        "success": True,
                        "rags": []
                    }

                rags_info = []
                for rag_dir in rag_base_dir.iterdir():
                    if rag_dir.is_dir():
                        metadata_file = (project_root / 'data' / 'rag_data.json').resolve()
                        try:
                            if metadata_file.exists():
                                with open(metadata_file, 'r', encoding='utf-8') as f:
                                    metadata = json.load(f)
                                    rags_info.append({
                                        "name": rag_dir.name,
                                        "created_at": metadata.get('created_at'),
                                        "files_info": metadata.get('files', []),
                                        "processed_files": metadata.get('processed_files', [])
                                    })
                            else:
                                rags_info.append({
                                    "name": rag_dir.name,
                                    "files_info": []
                                })
                        except Exception as e:
                            logger.error(f"Error reading metadata for {rag_dir.name}: {str(e)}")
                            rags_info.append({
                                "name": rag_dir.name,
                                "error": str(e)
                            })

                return {
                    "success": True,
                    "rags": rags_info
                }
            except Exception as e:
                logger.error(f"Failed to list RAGs: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        # @app.post("/api/rag/rename")
        # async def rename_rag(old_name: str, new_name: str):
        #     try:
        #         rag_base_dir = (project_root / 'data' / 'rag_data').resolve()
        #         rag_data_dir = (project_root / 'data').resolve()
        #         old_path = (rag_base_dir / old_name).resolve()
        #         new_path = (rag_base_dir / new_name).resolve()
        #
        #         if not old_path.exists():
        #             raise HTTPException(status_code=404, detail="RAG not found")
        #
        #         if new_path.exists():
        #             raise HTTPException(status_code=400, detail="New name already exists")
        #
        #         old_path.rename(new_path)
        #
        #         rag_data_file = rag_data_dir / 'rag_data.json'
        #         if rag_data_file.exists():
        #             with open(rag_data_file, 'r', encoding='utf-8') as f:
        #                 metadata = json.load(f)
        #                 metadata['rag_name'] = new_name
        #
        #             with open(rag_data_file, 'w', encoding='utf-8') as f:
        #                 json.dump(metadata, f, ensure_ascii=False, indent=2)
        #
        #         return {
        #             "success": True,
        #             "new_name": new_name
        #         }
        #
        #     except HTTPException:
        #         raise
        #     except Exception as e:
        #         logger.error(f"Failed to rename RAG: {str(e)}")
        #         raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/rag/process")
        async def process_rag_files(request: RagProcessRequest):
            try:
                if not request.files:
                    raise HTTPException(status_code=400, detail="No files provided")

                if not request.rag_name:
                    raise HTTPException(status_code=400, detail="RAG name is required")

                rag_dir = (project_root / 'data' / 'rag_data' / request.rag_name).resolve()
                metadata_file = (project_root / 'data' / 'rag_data.json').resolve()

                if rag_dir.exists():
                    logger.info(f"RAG directory already exists: {rag_dir}")
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                            return {
                                "success": True,
                                "message": "RAG already exists",
                                "rag_name": metadata.get('rag_name', []),
                                "save_path": str(rag_dir),
                                "files_info": metadata.get('files', []),
                                "created_at": metadata.get('created_at'),
                                "skipped": True
                            }
                    except (FileNotFoundError, json.JSONDecodeError) as e:
                        logger.warning(f"Failed to read metadata file: {str(e)}")
                        return {
                            "success": True,
                            "message": "RAG exists but metadata not available",
                            "rag_name": request.rag_name,
                            "save_path": str(rag_dir),
                            "skipped": True
                        }

                full_paths = []
                files_info = []

                for file_path in request.files:
                    if not file_path or '..' in file_path:
                        raise HTTPException(status_code=400, detail=f"Invalid path: {file_path}")

                    source_path = (project_root / 'upload' / 'files' / file_path).resolve()

                    if not source_path.exists():
                        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

                    full_paths.append(str(source_path))
                    files_info.append({
                        "name": request.original_filenames[file_path] if hasattr(request,
                                                                                 'original_filenames') else os.path.basename(
                            file_path),
                        "size": os.path.getsize(source_path),
                        "created_at": datetime.fromtimestamp(os.path.getctime(source_path)).isoformat()
                    })

                processor = DocumentProcessor(
                    path_name=str(rag_dir),
                    files_path_name=None
                )

                try:
                    results = await processor.process_documents_async(full_paths)

                    # 验证 results 存在且格式正确
                    if not results or not isinstance(results, dict):
                        raise HTTPException(
                            status_code=500,
                            detail="Invalid processing results format"
                        )

                    # 验证必要的键存在
                    if 'success' not in results or 'failed' not in results:
                        raise HTTPException(
                            status_code=500,
                            detail="Missing required result categories"
                        )

                    # 检查是否有成功处理的文件
                    successful_files = results.get('success', [])
                    failed_files = results.get('failed', [])

                    if not successful_files and failed_files:
                        failed_filenames = [
                            result.filename for result in failed_files
                            if hasattr(result, 'filename')
                        ]
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to process files: {', '.join(failed_filenames)}"
                        )

                    metadata = {
                        "rag_name": request.rag_name,
                        "created_at": datetime.now().isoformat(),
                        "files": files_info,
                        "processed_files": [
                            result.filename for result in successful_files
                            if hasattr(result, 'filename')
                        ]
                    }

                    # 确保目录存在
                    rag_dir.mkdir(parents=True, exist_ok=True)
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, ensure_ascii=False, indent=2)

                    return {
                        "success": True,
                        "message": "RAG processing completed successfully",
                        "rag_name": request.rag_name,
                        "save_path": str(rag_dir),
                        "files_info": files_info,
                        "processed_files": metadata["processed_files"],
                        "created_at": metadata["created_at"],
                        "skipped": False
                    }

                finally:
                    processor.cleanup()

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"RAG processing failed: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/rag/delete")
        async def delete_rag(request: DeleteRequest):
            try:
                rag_name = request.rag_name
                rag_dir = (project_root / 'data' / 'rag_data' / rag_name).resolve()

                if rag_dir.exists() and rag_dir.is_dir():
                    shutil.rmtree(rag_dir)
                    logger.info(f"<{rag_name}>文件已删除 ")
                else:
                    return {"success": False, "message": "Directory does not exist or is not a folder"}

                return {"success": True}
            except OSError as e:
                return {"success": False, "message": f"Failed to delete directory: {str(e)}"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        # 聊天消息
        @app.post("/api/chat")
        async def process_message(
                message_id: str = Form(...),
                query: str = Form(default=""),
                context_length: int = Form(default=10),
                conversation_id: str = Form(...),
                images: List[str] = Form(default=[]),
                files: List[str] = Form(default=[]),
                rags: List[str] = Form(default=[])
        ):
            """处理新消息"""
            try:
                # 处理附件路径
                processed_images = []
                if images:
                    for image_path in images:
                        if image_path:
                            try:
                                full_path = (upload_dir / 'images' / image_path).resolve()
                                if Path(full_path).exists():
                                    processed_images.append(full_path)
                                    logger.info(f"成功处理图片路径: {full_path}")
                                else:
                                    logger.error(f"图片文件不存在: {full_path}")
                            except Exception as e:
                                logger.error(f"处理图片路径失败: {str(e)}")

                processed_files = []
                if files:
                    for files_path in files:
                        if files_path:
                            try:
                                full_path = (upload_dir / 'files' / files_path).resolve()
                                if Path(full_path).exists():
                                    processed_files.append(full_path)
                                else:
                                    print(f"[Warning] 文件不存在: {full_path}")
                            except Exception as e:
                                print(f"[Error] 处理文件路径失败: {str(e)}")

                # 处理 RAG 文件名称
                processed_rags = []
                if rags:
                    for rag_name in rags:
                        if rag_name:
                            try:
                                rag_dir = (project_root / 'data' / 'rag_data' / rag_name).resolve()
                                if rag_dir.exists():
                                    processed_rags.append(rags)
                                    logger.info(f"成功处理RAG文件: {rags}")
                                else:
                                    logger.error(f"RAG目录不存在: {rags}")
                            except Exception as e:
                                logger.error(f"处理RAG路径失败: {str(e)}")

                # 创建消息输入
                input_msg = MessageInput(
                    query=query,
                    images=processed_images if processed_images else None,
                    files=processed_files if processed_files else None,
                    rags=processed_rags if processed_rags else None
                )

                async def generate():
                    try:
                        async for update in self.chat_ui_process(
                                url=url,
                                input_msg=input_msg,
                                message_id=message_id,
                                conversation_id=conversation_id,
                                context_length=context_length,
                                data_dir=history_data_dir,
                                history_mode=history_mode,
                                chat_ui=True
                        ):
                            if isinstance(update.get('content'), str):
                                content = update['content']

                                # 检查并转换 output 路径
                                if 'output\\' in content or 'output/' in content:
                                    try:
                                        match = re.search(r'输出路径：[ \t]*(.+?)(?:\n|$)', content)
                                        if match:
                                            file_path = match.group(1).strip().replace('\\', '/')
                                            file_extension = Path(file_path).suffix.lower()

                                            try:
                                                file_info = await get_file_url(file_path)
                                                if file_extension in ['.png', '.jpg', '.jpeg', '.gif']:
                                                    update['content'] = {
                                                        'type': 'mixed',
                                                        'text': '生成的图片如下：',
                                                        'images': [{'url': file_info['url']}]
                                                    }
                                                elif file_extension in ['.wav', '.mp3']:
                                                    update['content'] = {
                                                        'type': 'mixed',
                                                        'text': '音频处理完成：',
                                                        'files': [{
                                                            'url': file_info['url'],
                                                            'name': file_info['filename'],
                                                            'size': file_info['size']
                                                        }]
                                                    }
                                                else:
                                                    update['content'] = {
                                                        'type': 'mixed',
                                                        'text': '文件转换完成：',
                                                        'files': [{
                                                            'url': file_info['url'],
                                                            'name': file_info['filename'],
                                                            'size': file_info['size']
                                                        }]
                                                    }
                                            except Exception as e:
                                                print(f"[Error] 转换文件URL失败 {file_path}: {e}")
                                    except Exception as e:
                                        print(f"[Error] 处理输出路径失败: {e}")

                                # 转换本地文件路径
                                elif any(path in content for path in ['upload/', 'images/', 'files/']):
                                    try:
                                        path_pattern = r'(?:upload|images|files)/[^/\\:*?"<>|\r\n]+\.(?:png|jpg|jpeg|gif|pdf|doc|docx|txt|md|json)'
                                        paths = re.findall(path_pattern, content)

                                        for file_path in paths:
                                            try:
                                                file_info = await get_file_url(file_path)
                                                content = content.replace(file_path, file_info['url'])
                                            except Exception as e:
                                                print(f"[Error] 转换路径失败 {file_path}: {e}")

                                        update['content'] = content
                                    except Exception as e:
                                        print(f"[Error] URL转换错误: {e}")

                            yield json.dumps(update) + '\n'

                    except Exception as e:
                        error_msg = f"处理消息时出错: {str(e)}"
                        print(f"[Error] {error_msg}")
                        import traceback
                        print(f"[Debug] 异常详情: {traceback.format_exc()}")
                        yield json.dumps({
                            "type": "error",
                            "message_id": message_id,
                            "content": error_msg
                        }) + '\n'

                return StreamingResponse(
                    generate(),
                    media_type='application/x-ndjson',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                    }
                )

            except Exception as e:
                error_msg = f"处理请求时出错: {str(e)}"
                print(f"[Error] {error_msg}")
                import traceback
                print(f"[Debug] 异常详情: {traceback.format_exc()}")
                raise HTTPException(status_code=500, detail=error_msg)

        @app.get("/api/chat/history")
        async def get_all_conversations():
            if history_mode == "json":
                try:
                    history_file = (history_data_dir / 'chat_history.json').resolve()

                    if not history_file.exists():
                        return []

                    async with aiofiles.open(history_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        if not content.strip():
                            return []

                        history_data = json.loads(content)
                        return history_data

                except Exception as e:
                    print(f"[Error] 获取所有历史记录失败: {str(e)}")
                    raise HTTPException(status_code=500, detail=str(e))
            else:
                pass

        # 获取会话历史记录
        @app.get("/api/chat/history/{conversation_id}")
        async def get_conversation_history(conversation_id: str):
            """获取指定会话的历史记录"""
            if history_mode == "json":
                try:
                    history_file = (history_data_dir / 'chat_history.json').resolve()

                    if not history_file.exists():
                        return {"messages": [], "title": "新对话"}

                    async with aiofiles.open(history_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        if not content.strip():
                            return {"messages": [], "title": "新对话"}

                        history_data = json.loads(content)

                    conversation = next(
                        (conv for conv in history_data if conv['conversation_id'] == conversation_id),
                        None
                    )

                    if not conversation:
                        return {"messages": [], "title": "新对话"}
                    logger.info(f"获取会话id <{conversation_id}> 成功")
                    return {
                        "conversation_id": conversation['conversation_id'],
                        "title": conversation.get('title', "新对话"),
                        "timestamp": conversation['timestamp'],
                        "pinned": conversation.get('pinned', False),
                        "starred": conversation.get('starred', False),
                        "messages": conversation['messages']
                    }

                except Exception as e:
                    print(f"[Error] 获取会话历史记录失败: {str(e)}")
                    raise HTTPException(status_code=500, detail=str(e))
            else:
                pass

        # 删除会话
        @app.delete("/api/chat/history/{conversation_id}")
        async def delete_conversation(conversation_id: str):
            """删除指定会话"""
            if history_mode == "json":
                try:
                    history_file = (history_data_dir / 'chat_history.json').resolve()

                    if not history_file.exists():
                        return {"success": True, "message": "无历史记录"}

                    async with aiofiles.open(history_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        history_data = json.loads(content) if content.strip() else []

                    # 过滤要删除的记录
                    filtered_data = [
                        conv for conv in history_data
                        if conv['conversation_id'] != conversation_id
                    ]

                    # 保存更新后的记录
                    async with aiofiles.open(history_file, 'w', encoding='utf-8') as f:
                        await f.write(json.dumps(filtered_data, ensure_ascii=False, indent=2))

                    # 清理相关文件
                    temp_dir = project_root / 'temp' / conversation_id
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir)
                    logger.info(f"会话id <{conversation_id}> 会话删除成功")
                    return {"success": True, "message": "会话删除成功"}

                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            else:
                pass

        config = uvicorn.Config(app, host=UI_HOST, port=UI_PORT)
        server = uvicorn.Server(config)
        await server.serve()
