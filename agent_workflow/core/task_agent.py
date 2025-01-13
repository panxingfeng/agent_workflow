# -*- coding: utf-8 -*-
"""
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2025-1-11
@version: 2.0.0
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
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, AsyncGenerator
from typing import List

import aiofiles
import uvicorn
from fastapi import HTTPException, FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent_workflow.tools.base import MessageInput
from config.config import LOCAL_PORT_ADDRESS, UI_HOST, UI_PORT
from .FeiShu import Feishu
from .VChat import VChat
from .tool_executor import ToolExecutor


# 获取项目根目录
def get_project_root():
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        if (parent / 'main.py').exists():
            return parent
    raise RuntimeError("Could not find project root directory")


# 获取项目根目录和输出目录
project_root = get_project_root()
output_dir = project_root / 'output'
upload_dir = project_root / 'upload'
upload_images_dir = upload_dir / 'images'
upload_files_dir = upload_dir / 'files'
history_data_dir = project_root / 'data'

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


class MasterAgent:
    """
    主控代理类

    负责管理和协调多个子代理，实现智能任务分发和执行。
    支持多种平台接入（FastAPI、飞书、微信）。

    属性:
        agents: 可用代理字典，key为代理类名，value为代理实例
        llm: 语言模型实例，用于智能选择代理
        status: 当前代理状态
        execution_mode: 执行模式
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

        # 创建任务执行器
        self.executor = tool_executor

    async def process(self, message_input: MessageInput) -> str:
        """处理用户消息"""
        async with self._execution_lock:
            try:
                self.status = AgentStatus.RUNNING

                # 获取生成器的最后一个结果
                result = None
                async for item in self.executor.execute_tools(
                        message_input.process_input(),
                        history=None,
                        chat_ui=False
                ):
                    result = item

                link = result["link"]
                # 提取最后一个任务的结果
                if isinstance(result, dict):
                    # 如果有外层的 result 字段，先提取
                    if "result" in result and "status" in result:
                        result = result["result"]

                    if result:
                        # 获取最后一个任务的结果
                        last_task = list(result.values())[-1]
                        final_result = last_task.get('result', '') + "\n" + link
                        logger.info("最终结果: {}".format(final_result))
                        self.status = AgentStatus.SUCCESS
                        return final_result

                self.status = AgentStatus.FAILED
                return "处理失败: 无法获取结果"

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

        @app.post("/api/process", response_model=None)
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
                    result = match.group(1).strip()  # 提取出的文件路径

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
            self.status = AgentStatus.RUNNING
            self.message_id = message_id
            # 准备上下文
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
                                context_data = [{'query': msg['query'], 'response': msg['response']} for msg in context]

            # 确保数据目录存在
            try:
                if not isinstance(data_dir, Path):
                    data_dir = Path(data_dir)
                data_dir.mkdir(exist_ok=True, parents=True)
            except Exception as e:
                print(f"[Error] 创建数据目录失败: {str(e)}")
                raise

            # 开始处理
            yield {
                "type": "thinking_process",
                "message_id": message_id,
                "content": "正在思考..."
            }
            await asyncio.sleep(0.1)

            # 处理输入并处理附件信息
            attachments_info = {
                'images': [],
                'files': []
            }
            attachments_info_history = {
                'images': [],
                'files': []
            }

            try:
                if isinstance(input_msg, MessageInput):
                    processed_query = input_msg
                    # 处理图片路径
                    if input_msg.images:
                        for img_path in input_msg.images:
                            try:
                                if isinstance(img_path, str):
                                    path = Path(img_path)
                                    if path.exists():
                                        attachments_info['images'].append({
                                            'original_name': path.name,
                                            'saved_path': str(path),
                                            'size': os.path.getsize(path)
                                        })
                                        attachments_info_history['images'].append({
                                            'original_name': path.name,
                                            'saved_path': str(f"{url}/static/upload/images/{path.name}"),
                                            'size': os.path.getsize(path)
                                        })
                                    else:
                                        print(f"[Warning] 图片文件不存在: {path}")
                            except Exception as e:
                                print(f"[Error] 处理图片路径失败: {str(e)}")
                                continue

                    # 处理文件路径
                    if input_msg.files:
                        for file_path in input_msg.files:
                            try:
                                if isinstance(file_path, str):
                                    path = Path(file_path)
                                    if path.exists():
                                        attachments_info['files'].append({
                                            'original_name': path.name,
                                            'saved_path': str(path),
                                            'size': os.path.getsize(path)
                                        })
                                        attachments_info_history['files'].append({
                                            'original_name': path.name,
                                            'saved_path': str(f"{url}/static/upload/files/{path.name}"),
                                            'size': os.path.getsize(path)
                                        })
                                    else:
                                        print(f"[Warning] 文件不存在: {path}")
                            except Exception as e:
                                print(f"[Error] 处理文件路径失败: {str(e)}")
                                continue
                else:
                    processed_query = input_msg
                    print(f"[Debug] 直接使用输入作为查询: {processed_query}")

            except Exception as e:
                print(f"[Error] 处理用户输入时出错: {str(e)}")
                raise

            # 使用执行器处理任务
            try:
                async for result in self.executor.execute_tools(
                        query=processed_query.process_input(),
                        history=context_data,
                        chat_ui=chat_ui
                ):
                    files = []
                    images = []
                    if isinstance(result, dict):
                        if "error" in result:
                            yield {
                                "type": "error",
                                "message_id": message_id,
                                "content": result.get("error", "处理失败")
                            }
                            return

                        elif result.get("status") == "success" and "result" in result:
                            tool_response = result.get("result", {})
                            link_text  = result.get("link", {})
                            if tool_response:
                                final_result = list(tool_response.values())[-1]["result"]

                                if isinstance(final_result, str):
                                    if 'output\\' in final_result or 'output/' in final_result:
                                        try:
                                            match = re.search(r'输出路径：[ \t]*(.+?)(?:\n|$)', final_result)
                                            if match:
                                                file_path = match.group(1).strip().replace('\\', '/')
                                                file_extension = Path(file_path).suffix.lower()

                                                try:
                                                    # 构造 URL 和文件信息
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

                                                    else:
                                                        logger.error(f"输出文件不存在: {output_file_path}")
                                                except Exception as e:
                                                    logger.error(f"处理文件URL失败 {file_path}: {e}")
                                        except Exception as e:
                                            logger.error(f"处理输出路径失败: {e}")

                                # 保存历史记录
                                if history_mode == "json":
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
                                                (conv for conv in history_data if
                                                 conv['conversation_id'] == conversation_id),
                                                None
                                            )

                                            processed_result = {
                                                'type': 'mixed',
                                                'text': final_result,
                                                'files': files if files else files,
                                                'images': images if images else images,
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
                                        print(f"[Error] 保存历史记录失败: {str(e)}")

                                # 返回结果
                                yield {
                                    "type": "result",
                                    "message_id": message_id,
                                    "content": processed_result['text']
                                }

                        elif "type" in result:
                            # 转发带类型的消息
                            if result["type"] == "thinking_process":
                                yield {
                                    "type": "thinking_process",
                                    "message_id": message_id,
                                    "content": result.get("content", "处理中...")
                                }
                            else:
                                # 转发其他类型的消息
                                yield {
                                    **result,
                                    "message_id": message_id
                                }

                # 完成处理
                self.status = AgentStatus.SUCCESS
                yield {
                    "type": "thinking_process",
                    "message_id": message_id,
                    "content": "✓ 处理完成"
                }

            except Exception as e:
                self.status = AgentStatus.FAILED
                error_msg = f"处理失败: {str(e)}"
                print(f"[Error] {error_msg}")
                import traceback
                print(f"[Debug] 错误详情: {traceback.format_exc()}")
                yield {
                    "type": "error",
                    "message_id": message_id,
                    "content": error_msg
                }

        except Exception as e:
            self.status = AgentStatus.FAILED
            error_msg = f"处理失败: {str(e)}"
            print(f"[Error] {error_msg}")
            import traceback
            print(f"[Debug] 错误详情: {traceback.format_exc()}")
            yield {
                "type": "error",
                "message_id": message_id,
                "content": error_msg
            }

    async def chat_ui_demo(self, url=LOCAL_PORT_ADDRESS, history_mode: str = "json"):
        """
        启动FastAPI服务器，提供HTTP接口和静态文件服务
        """
        app = FastAPI()

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

        # 配置静态文件目录
        app.mount("/static/output", StaticFiles(directory=str(output_dir)), name="static")
        app.mount("/static/upload", StaticFiles(directory=str(upload_dir)), name="static")

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
                print(f"[Debug] 文件不存在: {file_name}")
                raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

            except Exception as e:
                print(f"Error in get_file_url: {str(e)}")
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
                            # 生成唯一文件名但保留原始文件名
                            original_name = image.filename
                            unique_filename = f"{uuid.uuid4()}{Path(original_name).suffix}"
                            file_path = upload_images_dir / unique_filename

                            # 保存文件
                            async with aiofiles.open(file_path, 'wb') as f:
                                content = await image.read()
                                await f.write(content)

                            # 获取文件URL
                            file_info = await get_file_url(f"images/{unique_filename}")
                            results.append({
                                "url": file_info['url'],
                                "path": str(unique_filename),  # 只保存文件名部分
                                "name": original_name,
                                "size": file_info['size']
                            })

                        except Exception as e:
                            print(f"[Error] Failed to upload images {image.filename}: {e}")

                # 处理文件上传
                if files:
                    for file in files:
                        try:
                            original_name = file.filename
                            unique_filename = f"{uuid.uuid4()}{Path(original_name).suffix}"
                            file_path = upload_files_dir / unique_filename  # 使用 files_dir

                            async with aiofiles.open(file_path, 'wb') as f:
                                content = await file.read()
                                await f.write(content)

                            file_info = await get_file_url(f"files/{unique_filename}")
                            results.append({
                                "url": file_info['url'],
                                "path": str(unique_filename),
                                "name": original_name,
                                "size": file_info['size']
                            })

                        except Exception as e:
                            print(f"[Error] Failed to upload files {file.filename}: {e}")

                return {
                    "files": results
                }

            except Exception as e:
                print(f"[Error] Upload failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.delete("/api/delete")
        async def delete_file(path: str):
            try:
                # 确保路径是有效的
                if not path or '..' in path:
                    raise HTTPException(status_code=400, detail="Invalid path")

                # 判断文件类型和路径
                if any(path.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                    file_path = project_root / 'upload' / 'images' / path
                else:
                    file_path = project_root / 'upload' / 'files' / path

                # 规范化路径
                file_path = file_path.resolve()
                upload_dir = (project_root / 'upload').resolve()

                # 安全检查：确保文件在上传目录中
                if not str(file_path).startswith(str(upload_dir)):
                    print(f"[Error] Access denied - files path: {file_path} not in upload dir: {upload_dir}")
                    raise HTTPException(status_code=403, detail="Access denied")

                if not file_path.exists():
                    print(f"[Warning] File not found: {file_path}")
                    raise HTTPException(status_code=404, detail="File not found")

                if not file_path.is_file():
                    print(f"[Error] Path is not a files: {file_path}")
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

        # 聊天消息
        @app.post("/api/chat")
        async def process_message(
                message_id: str = Form(...),
                query: str = Form(default=""),
                context_length: int = Form(default=10),
                conversation_id: str = Form(...),
                images: List[str] = Form(default=[]),
                files: List[str] = Form(default=[])
        ):
            """处理新消息"""
            try:
                # 处理附件路径
                processed_images = []
                if images:
                    for image_path in images:
                        if image_path:
                            try:
                                # 构造完整的文件路径
                                full_path = str(upload_dir / 'images' / image_path)
                                if Path(full_path).exists():
                                    processed_images.append(full_path)
                                    print(f"[Debug] 成功处理图片路径: {full_path}")
                                else:
                                    print(f"[Warning] 图片文件不存在: {full_path}")
                            except Exception as e:
                                print(f"[Error] 处理图片路径失败: {str(e)}")

                processed_files = []
                if files:
                    for files_path in files:
                        if files_path:
                            try:
                                # 构造完整的文件路径
                                full_path = str(upload_dir / 'files' / files_path)
                                if Path(full_path).exists():
                                    processed_files.append(full_path)
                                else:
                                    print(f"[Warning] 图片文件不存在: {full_path}")
                            except Exception as e:
                                print(f"[Error] 处理图片路径失败: {str(e)}")

                # 创建消息输入
                input_msg = MessageInput(
                    query=query,
                    images=processed_images if processed_images else None,
                    files=processed_files if processed_files else None
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
                    history_file = history_data_dir / 'chat_history.json'

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
                    history_file = history_data_dir / 'chat_history.json'

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
                    history_file = history_data_dir / 'chat_history.json'

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

                    return {"success": True, "message": "会话删除成功"}

                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            else:
                pass

        config = uvicorn.Config(app, host=UI_HOST, port=UI_PORT)
        server = uvicorn.Server(config)
        await server.serve()
