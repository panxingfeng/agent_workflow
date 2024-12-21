# -*- coding: utf-8 -*-
"""
@file: comfyui_generator.py
@author: PanXingFeng
@contact: 1115005803@qq.com、canomiguelittle@gmail.com
@date: 2024-12-12
@version: 1.0.0
@license: MIT License

@description:
ComfyUI图像生成工具类 (ComfyuiImageGenerator)

模型支持:
- checkpoint模型系列支持
- 各类Lora模型支持
- VAE优化模型支持
- ControlNet系列模型支持

功能特性:
1. 工作流管理:
    - 多工作流配置支持
    - 动态参数更新
    - 工作流模板管理

2. 图像生成:
    - 文本生图(Text2Image)
    - 图生图(Image2Image)
    - 高级参数控制
    - 批量生成支持

3. 系统集成:
    - WebSocket实时连接
    - 异步图像保存
    - 状态监控和回调
    - 错误处理和恢复

Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""
import os
import pandas as pd
import websocket
import json
import requests
import time
import threading
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from agent_workflow.utils.loading import LoadingIndicator
from config.config import COMFYUI_MODEL_PATH


class ComfyuiAPI:
    """AI图像生成客户端类

    该类提供了与AI图像生成服务器交互的完整功能，包括WebSocket连接、
    工作流管理、参数更新和图像生成等功能。

    Attributes:
        server_url (str): 服务器URL地址
        client_id (str): 客户端ID
        ws (websocket.WebSocketApp): WebSocket连接实例
        is_connected (bool): WebSocket连接状态
        connection_event (threading.Event): 连接状态事件
        loading (LoadingIndicator): 加载指示器
        ws_thread (threading.Thread): WebSocket线程
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, server_url: str = "127.0.0.1:8188", client_id: str = "123456"):
        """初始化AI图像客户端（只在第一次创建实例时执行）"""
        # 确保初始化代码只运行一次
        if not ComfyuiAPI._initialized:
            self.server_url = server_url
            self.client_id = client_id
            self.ws = None
            self.is_connected = False
            self.connection_event = threading.Event()
            self.loading = None
            self.ws_thread = None

            # 初始化连接
            self._setup_websocket()
            # 等待连接建立
            if not self.ensure_connection(timeout=10):
                print("警告：WebSocket连接未能在初始化时建立")

            ComfyuiAPI._initialized = True

    def reinit_connection(self) -> bool:
        """重新初始化连接

        Returns:
            bool: 是否成功重新建立连接
        """
        try:
            # 先清理现有连接
            self.close()

            # 重置状态
            self.ws = None
            self.is_connected = False
            self.connection_event.clear()
            self.loading = None

            # 重新建立连接
            self._setup_websocket()
            return self.ensure_connection(timeout=10)

        except Exception as e:
            print(f"重新初始化连接时出错: {e}")
            return False

    def _setup_websocket(self) -> None:
        """设置并启动WebSocket连接"""
        ws_url = f"ws://{self.server_url}/ws?clientId={self.client_id}"
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )

        # 在新线程中启动WebSocket
        self.ws_thread = threading.Thread(target=self._run_websocket)
        self.ws_thread.daemon = True
        self.ws_thread.start()

    def _run_websocket(self) -> None:
        """在独立线程中运行WebSocket"""
        try:
            self.ws.run_forever()
        except Exception as e:
            print(f"WebSocket运行错误: {e}")
            self.is_connected = False
            self.connection_event.clear()

    def _on_open(self, ws) -> None:
        """WebSocket连接建立时的回调"""
        print("WebSocket连接已建立")
        self.is_connected = True
        self.connection_event.set()

    def _on_error(self, ws, error) -> None:
        """WebSocket错误处理回调"""
        print(f"WebSocket错误: {error}")
        self.is_connected = False
        self.connection_event.clear()
        if self.loading:
            self.loading.stop()
            self.loading = None

    def _on_close(self, ws, close_status_code, close_msg) -> None:
        """WebSocket关闭时的回调"""
        print(f"WebSocket连接已关闭（状态码：{close_status_code}，消息：{close_msg}）")
        self.is_connected = False
        self.connection_event.clear()
        if self.loading:
            self.loading.stop()
            self.loading = None

    def _on_message(self, ws, message) -> None:
        """处理WebSocket消息"""
        try:
            if isinstance(message, bytes):
                return

            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "executing":
                execution_data = data.get("data", {})
                if execution_data.get("prompt_id"):  # 生成完成
                    prompt_id = execution_data["prompt_id"]
                    self._handle_generation_complete(prompt_id)

        except Exception:
            pass

    def _handle_generation_complete(self, prompt_id: str) -> None:
        """处理生成完成事件"""
        try:
            response = requests.get(
                f"http://{self.server_url}/history/{prompt_id}",
                timeout=10
            )
            if not response.ok:
                return

            history_data = response.json()
            if prompt_id not in history_data:
                return

            # 查找输出图片
            output_images = None
            for node_output in history_data[prompt_id].get("outputs", {}).values():
                if "images" in node_output:
                    output_images = node_output["images"]
                    break

            if not output_images:
                return

            # 获取图片URL
            image_filename = output_images[0]["filename"]
            image_url = f"http://{self.server_url}/view?filename={image_filename}&type=output"

            # 下载图片
            img_response = requests.get(image_url, stream=True, timeout=30)
            if not img_response.ok:
                return

            # 准备保存路径
            if hasattr(self, '_save_path'):
                save_path = self._save_path
            else:
                save_path = Path("output")
            save_path.mkdir(parents=True, exist_ok=True)

            if hasattr(self, '_image_filename'):
                save_filename = self._image_filename
            else:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                save_filename = f"image_{timestamp}.png"

            full_path = save_path / save_filename

            # 直接保存图片
            try:
                with open(full_path, 'wb') as f:
                    for chunk in img_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                if hasattr(self, '_save_callback'):
                    self._save_callback(True)
            except Exception:
                if hasattr(self, '_save_callback'):
                    self._save_callback(False)

        except Exception:
            if hasattr(self, '_save_callback'):
                self._save_callback(False)

    def _load_workflow(self, chinese_name: str) -> Tuple[Optional[Dict], Optional[str]]:
        """加载工作流配置文件

        Args:
            chinese_name: 工作流的中文名称

        Returns:
            Tuple[Optional[Dict], Optional[str]]: 工作流数据和检查点
        """
        try:
            # 读取工作流映射表
            workflow_map = pd.read_excel("config/workflow_json.xlsx")
            row = workflow_map[workflow_map['chinese_name'] == chinese_name]

            if row.empty:
                print(f"未找到工作流配置：{chinese_name}")
                return None, None

            json_name = row['json_name'].values[0]
            checkpoint = row['checkpoint'].values[0]

            # 加载工作流JSON文件
            file_path = Path("config/json_file") / f"{json_name}.json"
            if not file_path.exists():
                print(f"找不到配置文件: {file_path}")
                return None, None

            with open(file_path, 'r', encoding='utf-8') as f:
                prompt_data = json.load(f)
                workflow_data = {
                    "client_id": self.client_id,
                    "prompt": prompt_data
                }
                return workflow_data, checkpoint

        except Exception as e:
            print(f"加载工作流配置文件失败: {e}")
            return None, None

    def _update_workflow_params(self, data: Any, params: Dict) -> None:
        """更新工作流参数

        Args:
            data: 工作流数据
            params: 要更新的参数字典
        """
        try:
            def recursive_update(data_item: Any) -> None:
                """递归更新参数"""
                if isinstance(data_item, dict):
                    for key, value in data_item.items():
                        if isinstance(value, str) and value.endswith('_data_json_workflow'):
                            if key == 'seed':
                                # 生成随机种子
                                data_item[key] = int(time.time() * 1000) % (2 ** 32)
                            elif key == 'cfg':
                                # 设置CFG比例
                                data_item[key] = params.get('cfg_scale_data_json_workflow', 8.0)
                            else:
                                # 更新其他参数
                                data_item[key] = params.get(value)
                        elif isinstance(value, (dict, list)):
                            recursive_update(value)
                elif isinstance(data_item, list):
                    for item in data_item:
                        if isinstance(item, (dict, list)):
                            recursive_update(item)

            recursive_update(data)

        except Exception as e:
            print(f"参数更新错误: {str(e)}")

    def _save_image_async(self, img_response, full_path: Path) -> None:
        """异步保存图片"""

        def save_worker():
            try:
                with open(full_path, 'wb') as f:
                    for chunk in img_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                if hasattr(self, '_save_callback'):
                    self._save_callback(True)
            except Exception as e:
                if hasattr(self, '_save_callback'):
                    self._save_callback(False)

        save_thread = threading.Thread(target=save_worker)
        save_thread.daemon = False
        save_thread.start()

    def wait_for_connection(self, timeout: int = 10) -> bool:
        """等待WebSocket连接建立

        Args:
            timeout: 等待超时时间（秒）

        Returns:
            bool: 连接是否成功建立
        """
        return self.connection_event.wait(timeout)

    def ensure_connection(self, timeout: int = 10) -> bool:
        """确保WebSocket连接已建立

        Args:
            timeout: 等待超时时间（秒）

        Returns:
            bool: 连接是否就绪
        """
        if self.is_connected:
            return True

        # 测试HTTP连接
        try:
            response = requests.get(f"http://{self.server_url}/", timeout=5)
            if not response.ok:
                print("错误：ComfyUI服务器未响应")
                return False
        except requests.exceptions.RequestException as e:
            print(f"错误：无法连接到ComfyUI服务器：{e}")
            return False

        # 等待WebSocket连接
        if not self.wait_for_connection(timeout):
            print(f"错误：WebSocket连接超时（{timeout}秒）")
            return False

        return True

    def get_models(self, models_dir: str = COMFYUI_MODEL_PATH) -> list:
        """遍历指定目录下的模型文件"""
        model_files = []
        if os.path.exists(models_dir):
            for file in os.listdir(models_dir):
                if os.path.isfile(os.path.join(models_dir, file)) and file.endswith('.safetensors'):
                    model_files.append(file)
        return model_files

    def close(self) -> None:
        """关闭连接并清理资源"""
        try:
            if self.ws:
                self.ws.close()
            if self.loading:
                self.loading.stop()
            self.is_connected = False
            self.connection_event.clear()
            print("已关闭所有连接并清理资源")
        except Exception as e:
            print(f"关闭连接时出错: {e}")

    def run(self,
            task_mode: str = "基础文生图",
            model_name: str = None,
            prompt_text: str = None,
            image_name: Optional[str] = None,
            negative_prompt_text: str = None,
            width: int = 512,
            height: int = 768,
            steps: int = 20,
            batch_count: int = 1,
            batch_size: int = 1,
            sampling_method: str = "euler",
            cfg_scale: float = 8.0,
            output_dir: Optional[str] = "output",
            custom_filename: Optional[str] = None,
            timeout: int = 60
            ) -> Optional[str]:
        """运行图像生成任务"""
        try:
            # 基本检查
            if not prompt_text or not self.is_connected:
                print("警告: 参数无效或未连接")
                return None

            # 加载工作流
            workflow_data, checkpoint = self._load_workflow(task_mode)
            if workflow_data is None:
                return None

            # 准备保存路径和文件名
            save_path = Path(output_dir)
            save_path.mkdir(parents=True, exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            if custom_filename:
                image_filename = f"{custom_filename}.png"
            else:
                safe_prompt = "".join(x for x in prompt_text[:30] if x.isalnum() or x in (' ', '_', '-'))
                image_filename = f"{timestamp}_{safe_prompt}.png"

            # 保存路径信息供WebSocket回调使用
            self._save_path = save_path
            self._image_filename = image_filename
            expected_image_path = str(save_path / image_filename)

            # 更新参数
            params_to_update = {
                "checkpoint_data_json_workflow": model_name if model_name else checkpoint,
                "prompt_data_json_workflow": prompt_text,
                "negative_data_json_workflow": negative_prompt_text if negative_prompt_text else "",
                "width_data_json_workflow": width,
                "height_data_json_workflow": height,
                "sampling_method_data_json_workflow": sampling_method,
                "steps_data_json_workflow": steps,
                "batch_count_data_json_workflow": batch_count,
                "batch_size_data_json_workflow": batch_size,
                "cfg_scale_data_json_workflow": cfg_scale,
            }

            if image_name:
                params_to_update["image_data_json_workflow"] = image_name

            self._update_workflow_params(workflow_data, params_to_update)

            # 启动加载动画
            loading = LoadingIndicator("正在生成")
            loading.start()

            try:
                # 发送请求
                response = requests.post(
                    f"http://{self.server_url}/prompt",
                    json=workflow_data,
                    timeout=timeout
                )
                if not response.ok:
                    return None

                # 等待生成完成
                generation_successful = threading.Event()

                def save_callback(success: bool):
                    if success:
                        generation_successful.set()

                self._save_callback = save_callback

                # 等待生成完成或超时
                if generation_successful.wait(timeout):
                    if Path(expected_image_path).exists():
                        return expected_image_path

                return None

            finally:
                loading.stop()
                if hasattr(self, '_save_callback'):
                    delattr(self, '_save_callback')
                if hasattr(self, '_save_path'):
                    delattr(self, '_save_path')
                if hasattr(self, '_image_filename'):
                    delattr(self, '_image_filename')

        except Exception:
            return None