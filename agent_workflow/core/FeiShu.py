# -*- coding: utf-8 -*-
"""
@file: feishu.py
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2024-12-12
@version: 1.0.0
@license: MIT License

@description:
飞书机器人实现类，实现与飞书平台的对接和消息处理。

功能特性:
1. 消息加解密处理
2. 飞书消息接收和发送
3. 用户信息管理
4. 多媒体文件处理
5. 群聊和私聊支持
6. 事件处理机制
7. 文件上传功能

工作流程:
1. 接收飞书平台消息
2. 解密和验证消息
3. 处理不同类型消息
4. 调用对应处理函数
5. 返回处理结果

Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""

import base64
import hashlib
import re
import subprocess
from datetime import datetime
from pathlib import Path

import aiohttp
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from agent_workflow.tools.base import FeishuUserQuery
from config.config import FEISHU_DATA
import json
import os
import requests
from requests_toolbelt import MultipartEncoder # 输入pip install requests_toolbelt 安装依赖库

from flask import Flask, request, jsonify

from lark_oapi.api.im.v1 import *
import lark_oapi as lark
from lark_oapi.api.contact.v3 import *

# 当前时间
current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class AESCipher:
    """
    AES加解密类，用于处理飞书消息的加解密

    属性:
        key: 加密密钥
        bs: AES block size
    """

    def __init__(self, key=FEISHU_DATA.get('encrypt_key')):
        """
        初始化加密器

        Args:
            key: 加密密钥，默认从配置文件获取
        """
        self.bs = AES.block_size
        self.key = hashlib.sha256(self.str_to_bytes(key)).digest()

    @staticmethod
    def str_to_bytes(data):
        """
        将字符串转换为字节

        Args:
            data: 输入数据

        Returns:
            bytes: 转换后的字节数据
        """
        if isinstance(data, str):
            return data.encode('utf8')
        return data

    def decrypt(self, enc):
        """
        解密数据

        Args:
            enc: 加密的数据

        Returns:
            bytes: 解密后的数据
        """
        iv = enc[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(enc[AES.block_size:])
        return unpad(decrypted, AES.block_size)

    def decrypt_string(self, enc):
        """
        解密字符串

        Args:
            enc: Base64编码的加密字符串

        Returns:
            str: 解密后的字符串
        """
        enc = base64.b64decode(enc)
        return self.decrypt(enc).decode('utf8')


class MessageTypeGroup:
    """
    格式化群用户回复用户的消息的格式
    """
    def __init__(self,query,send_id,receive_id,receive_id_type):
        self.query = query
        self.send_id = send_id
        self.receive_id = receive_id
        self.receive_id_type = receive_id_type

    def handle(self, message):
        # 获取文件扩展名并转换为小写
        _, file_extension = os.path.splitext(message)
        file_extension = file_extension.lower()

        if file_extension == ".png":
            # 假设返回是一个图片文件地址
            image_key = get_image_key(message)
            return self.image_message(image_key)
        else:
            return self.text_message(message)

    def text_message(self,message):
        return {
            "receive_id": self.receive_id,
            "content": json.dumps({
                        "text": f"<at user_id=\"{self.send_id}\"></at> {message}",
                    }),
            "msg_type": "text",
            "receive_id_type": self.receive_id_type
        }

    def image_message(self,image_key):
        if image_key:
            return {
                "receive_id": self.receive_id,
                "content":json.dumps({
                        "zh_cn": {
                            "title":"生成的图像结果",
                            "content":[
                                [
                                    {
                                        "tag": "at",
                                        "user_id": self.send_id,
                                        "style": ["bold"]
                                    },
                                    {
                                        "tag": "text",
                                        "text":"描述信息:",
                                        "style": ["blob"]
                                    },
                                    {
                                        "tag": "text",
                                        "text":self.query,
                                        "style": ["underline"]
                                    }
                                ],
                                [{
                                    "tag":"img",
                                    "image_key":image_key
                                }]
                            ]
                        }
                    }),
                "msg_type":"post",
                "receive_id_type": self.receive_id_type
            }
        else:
            return None

class MessageTypePrivate:
    """
    格式化用户回复用户的消息的格式
    """
    def __init__(self,receive_id,receive_id_type):
        self.receive_id = receive_id
        self.receive_id_type = receive_id_type

    def handle(self, message):
        global file_extension, file_path
        try:
            match = re.search(r"输出路径：(.+)", message)
            file_path = match.group(1).strip()  # 提取出的文件路径
            # 获取文件扩展名并转换为小写
            _, file_extension = os.path.splitext(file_path)
            file_extension = file_extension.lower()
        except Exception:
            file_extension = None

        # message 返回的内容是地址值
        if file_extension == ".png":
            image_key = get_image_key(file_path)
            return self.image_message(image_key)
        elif file_extension == ".mp3":
            audio_key = get_audio_key(file_path)
            return self.audio_message(audio_key)
        elif file_extension in [".txt", ".doc", ".pdf"]:
            file_key = get_file_key(file_path)
            return self.file_message(file_key)
        elif file_extension in [".mp4"]:
            file_key = get_file_key(file_path)
            # 视频的封面图 可以设置一个固定的封面图,也可以不设置封面图
            image_path = None
            image_key = get_image_key(image_path)
            return self.vidio_message(file_key,image_key)
        else:
            return self.text_message(message)

    def text_message(self,message):
        return {
            "receive_id": self.receive_id,
            "content": json.dumps({
                        "text": message,
                    }),
            "msg_type": "text",
            "receive_id_type": self.receive_id_type
        }

    def image_message(self,image_key):
        if image_key:
            return {
                "receive_id": self.receive_id,
                "content":json.dumps({
                        "image_key": image_key,
                    }),
                "msg_type":"image",
                "receive_id_type": self.receive_id_type
            }
        else:
            return None

    def audio_message(self,audio_key):
        if audio_key:
            return {
                "receive_id": self.receive_id,
                "content":json.dumps({
                        "file_key": audio_key,
                    }),
                "msg_type":"audio",
                "receive_id_type": self.receive_id_type
            }
        else:
            return None

    def file_message(self,file_key):
        if file_key:
            return {
                "receive_id": self.receive_id,
                "content":json.dumps({
                        "file_key": file_key
                    }),
                "msg_type":"file",
                "receive_id_type": self.receive_id_type
            }
        else:
            return None

    def vidio_message(self,file_key,image_key):
        if file_key:
            return {
                "receive_id": self.receive_id,
                "content":json.dumps({
                        "file_key": file_key,
                        "image_key": image_key
                    }),
                "msg_type":"media",
                "receive_id_type": self.receive_id_type
            }
        else:
            return None

class SendMessage:
    def __init__(self, log_level=lark.LogLevel.INFO):
        self.app_id = FEISHU_DATA.get('app_id')
        self.app_secret = FEISHU_DATA.get('app_secret')
        self.client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(log_level) \
            .build()

    def send_message(self, message_params) -> dict:
        """
        发送消息给指定用户
        """
        # 构造请求对象
        receive_id_type = message_params.get('receive_id_type')
        receive_id = message_params.get('receive_id')
        msg_type = message_params.get('msg_type')
        content = message_params.get('content')
        request = CreateMessageRequest.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(CreateMessageRequestBody.builder()
                          .receive_id(receive_id)
                          .msg_type(msg_type)
                          .content(content)  # 将文本内容转换为JSON
                          .build()) \
            .build()

        # 发起请求
        response = self.client.im.v1.message.create(request)

        # 处理失败返回
        if not response.success():
            error_message = f"client.im.v1.message.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            lark.logger.error(error_message)
            return {"success": False, "error": error_message}

        # 处理业务结果
        result = lark.JSON.marshal(response.data, indent=4)
        lark.logger.info(result)
        return {"success": True, "data": result}

class FeishuUser:
    def __init__(self):
        """
        初始化 FeishuUser 类，设置 App ID 和 App Secret。
        """
        self.app_id = FEISHU_DATA.get('app_id')
        self.app_secret = FEISHU_DATA.get('app_secret')
        self.client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(lark.LogLevel.DEBUG) \
            .build()
        self.token = FEISHU_DATA.get('tenant_access_token')

    def get_user_info_by_id(self, user_id: str, user_id_type: str = "open_id"):
        """
        通过用户 ID 获取用户信息
        :param user_id: 用户的 ID（open_id 或 user_id）
        :param user_id_type: ID 类型，默认为 "open_id"
        :return: 用户信息字典
        """
        # 构造请求对象
        request = GetUserRequest.builder() \
            .user_id(user_id) \
            .user_id_type(user_id_type) \
            .department_id_type("open_department_id") \
            .build()

        # 构造请求选项
        option = lark.RequestOption.builder().user_access_token(self.token).build()

        # 发起请求
        response = self.client.contact.v3.user.get(request, option)

        # 处理失败返回
        if not response.success():
            error_message = (
                f"获取用户信息失败, 错误代码: {response.code}, "
                f"错误消息: {response.msg}, log_id: {response.get_log_id()}"
            )
            lark.logger.error(error_message)
            return {"success": False, "error": error_message}

        # 将用户信息转换为字典格式
        user_info = json.loads(lark.JSON.marshal(response.data))
        return {"success": True, "data": user_info}

    def format_user_info(self, user_info):
        """
        格式化用户主要信息
        :param user_info: 用户信息字典
        :return: name、gender、mobile、department_ids、job_title、is_tenant_manager
        """
        user = user_info['user']

        return {
            "name": user.get('name', 'N/A'),
            "gender": 'man' if user.get('gender') == 1 else 'women' if user.get('gender') == 0 else '未知',
            "mobile": user.get('mobile', 'N/A'),
            "department_ids": ', '.join(user.get('department_ids', [])),
            "job_title": user.get('job_title', 'N/A'),
            "is_tenant_manager": True if user.get('is_tenant_manager') else False,
            }


class FeishuMessageHandler:
    def __init__(self,task_processor):
        # 创建 client
        self.feishu_user = FeishuUser()
        self.task_processor = task_processor
        # 存储已处理过的 message_id
        self.processed_messages = set()
        self.send_message_tool = SendMessage()
        self.message_type_private = MessageTypePrivate
        self.message_type_group = MessageTypeGroup

    async def handle_message(self, event_data, event_type):
        if event_type == "im.message.receive_v1":
            message = event_data.get('message', {})
            message_id = message.get('message_id')
            chat_type = message.get('chat_type')
            query = json.loads(message.get('content', '{}')).get('text', '')
            sender_id = event_data.get('sender', {}).get('sender_id', {}).get('open_id')
            attachments: List[Path] = []

            if chat_type == "p2p":
                # 私聊消息处理
                if message_id in self.processed_messages:
                    print(f"消息 {message_id} 已经处理过，跳过处理")
                    return {"success": False, "message": "消息已处理"}

                self.processed_messages.add(message_id)

                user_info = self.feishu_user.get_user_info_by_id(
                    user_id=sender_id,
                    user_id_type="open_id"
                )
                formatted_info = self.feishu_user.format_user_info(user_info.get("data", {}))
                user_name = formatted_info.get("name", "未知用户")

                query = FeishuUserQuery(
                    text=query,
                    attachments=attachments
                )
                response = await self.task_processor.process(query)

                message_params = self.message_type_private(
                    receive_id=sender_id,
                    receive_id_type="open_id"
                ).handle(response['result'])

                self.send_message_tool.send_message(message_params=message_params)

                return {
                    "message": f"消息处理成功，来自用户 {user_name} 的消息已回复。",
                    "success": True
                }
            elif chat_type == "group":
                chat_id = message.get('chat_id')
                mentions = message.get('mentions')
                key_value = mentions[0].get('name', None)
                # 清除群聊消息中@聊天机器人携带类似@_user_1字眼的内容
                query = re.sub(r'@\w+', '', query)
                if key_value == FEISHU_DATA['name']:
                    # 检查是否已经处理过这条消息
                    if message_id in self.processed_messages:
                        return {"success": False, "message": "消息已处理"}

                    # 标记消息为已处理
                    self.processed_messages.add(message_id)

                    user_info = self.feishu_user.get_user_info_by_id(
                        user_id=sender_id,
                        user_id_type="open_id"
                    )
                    formatted_info = self.feishu_user.format_user_info(user_info.get("data", {}))
                    user_name = formatted_info.get("name", "未知用户")

                    query = FeishuUserQuery(
                        text=query,
                        attachments=attachments
                    )
                    response = await self.task_processor.process(query)

                    message_params = self.message_type_group(
                        query=query,
                        send_id=sender_id,
                        receive_id=chat_id,
                        receive_id_type="chat_id"
                    ).handle(response)

                    self.send_message_tool.send_message(message_params=message_params)

                    # 发送回复消息
                    return jsonify({
                        "message": f"消息处理成功，来自用户 {user_name} 的消息已回复。",
                        "success": True
                    })
                else:
                    return jsonify({
                        "message": f"消息处理失败",
                        "success": False
                    })

        elif event_type == "im.message.message_read_v1":
            return jsonify({
                "message": "消息已读",
                "success": True
            })

def get_image_key(image_path):
    url = "https://open.feishu.cn/open-apis/im/v1/images"
    form = {'image_type': 'message',
            'image': (open(image_path, 'rb'))}  # 需要替换具体的path
    multi_form = MultipartEncoder(form)
    headers = {'Authorization': "Bearer " + FEISHU_DATA.get('tenant_access_token'),
               'Content-Type': multi_form.content_type}
    response = requests.request("POST", url, headers=headers, data=multi_form)
    # 解析 JSON 响应
    response_data = response.json()
    if response_data.get("code") == 0:  # 检查请求是否成功
        image_key = response_data['data']['image_key']
        return image_key
    else:
        print("Error:", response_data.get("msg"))
        return None


def convert_to_opus(source_file, output_dir, output_filename):
    # 确保 output_filename 包含 .opus 扩展名
    if not output_filename.endswith(".opus"):
        output_filename += ".opus"

    target_file = os.path.join(output_dir, output_filename)

    # 需要安装 ffmpeg ，安装教程网上搜索即可
    command = [
        "ffmpeg",
        "-i", source_file,
        "-acodec", "libopus",
        "-ac", "1",
        "-ar", "16000",
        "-f", "opus",
        target_file
    ]

    # 执行转换
    subprocess.run(command)
    return target_file

def get_audio_key(file_path):
    url = "https://open.feishu.cn/open-apis/im/v1/files"
    file_name = os.path.basename(file_path)
    form = {
        'file_type': 'opus',
        'file_name': file_name,
        'file': (file_name, open(file_path, 'rb'), 'audio/opus')
    }

    multi_form = MultipartEncoder(form)
    headers = {'Authorization': "Bearer " + FEISHU_DATA.get('tenant_access_token'),
               'Content-Type': multi_form.content_type}

    response = requests.request("POST", url, headers=headers, data=multi_form)
    response_data = response.json()
    if response_data.get("code") == 0:  # 检查请求是否成功
        audio_key = response_data['data']['file_key']
        return audio_key
    else:
        print("Error:", response_data.get("msg"))
        return None

def get_file_key(file_path):
    global file_type,mime_type
    url = "https://open.feishu.cn/open-apis/im/v1/files"
    file_name = os.path.basename(file_path)
    if ".pdf" in file_name:
        file_type = 'pdf'
        mime_type = 'application/pdf'  # mime值参考 https://www.w3school.com.cn/media/media_mimeref.asp
    elif ".doc" in file_name:
        file_type = 'doc'
        mime_type = 'application/msword'
    elif ".xls" in file_name:
        file_type = 'xls'
        mime_type = 'application/vnd.ms-excel'
    elif ".ppt" in file_name:
        file_type = 'ppt'
        mime_type = 'application/vnd.ms-powerpoint'
    elif ".mp4" in file_name:
        file_type = 'mp4'
        mime_type = 'video/mp4'

    form = {
        'file_type': file_type,
        'file_name': file_name,
        'file': (file_name, open(file_path, 'rb'), mime_type)
    }

    multi_form = MultipartEncoder(form)
    headers = {'Authorization': "Bearer " + FEISHU_DATA.get('tenant_access_token'),
               'Content-Type': multi_form.content_type}

    response = requests.request("POST", url, headers=headers, data=multi_form)
    response_data = response.json()
    if response_data.get("code") == 0:  # 检查请求是否成功
        file_key = response_data['data']['file_key']
        print(file_key)
        return file_key
    else:
        print("Error:", response_data.get("msg"))
        return None


class Feishu:
    def __init__(self, task_processor):
        self.app = Flask(__name__)
        self.task_processor = task_processor
        self.feishu_handler = FeishuMessageHandler(task_processor)
        self.setup_routes()

    def setup_routes(self):
        @self.app.route("/", methods=["POST"])
        async def event():
            try:
                data = request.get_json()
                decrypted_data = {}

                if "encrypt" in data:
                    try:
                        cipher = AESCipher()
                        decrypted_message = cipher.decrypt_string(data["encrypt"])
                        decrypted_data = json.loads(decrypted_message)
                    except Exception as e:
                        print(f"Decryption error: {e}")
                        return {"error": "Decryption failed"}, 400

                event_type = decrypted_data.get('header', {}).get('event_type')
                event_data = decrypted_data.get('event', {})

                if 'challenge' in decrypted_data:
                    return {"challenge": decrypted_data['challenge']}

                # 处理消息
                result = await self.feishu_handler.handle_message(event_data, event_type)
                return result  # 直接返回handle_message的结果

            except Exception as e:
                print(f"Processing failed: {e}")
                return {"error": f"Processing failed: {str(e)}"}, 500

    def start(self, port: int = 8070):
        """启动Flask服务器"""
        print(f"\n飞书机器人服务启动成功!")
        print(f"监听端口: {port}")
        print("等待消息中...\n")

        self.app.run(port=port)


    async def get_tenant_token(self):
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "app_id": FEISHU_DATA['app_id'],
            "app_secret": FEISHU_DATA['app_secret']
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                return await response.json()
