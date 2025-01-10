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
import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, Type, Optional
import json
import logging
import colorlog
from langchain.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
import os
import importlib
import inspect
from agent_workflow.tools.tool.base import BaseTool
from agent_workflow.tools.result_formatter import ResultFormatter
from agent_workflow.tools.base import UserQuery
from agent_workflow.tools.base import FeishuUserQuery
from config.bot import TOOL_INTENT_PARSER, PARAMETER_OPTIMIZER
from config.config import OLLAMA_DATA

ollama_model = OLLAMA_DATA['inference_model']


# 配置带颜色的logging
def setup_colored_logger(name, level=logging.INFO):
    logger = colorlog.getLogger(name)
    if not logger.handlers:
        handler = colorlog.StreamHandler()
        handler.setFormatter(colorlog.ColoredFormatter(
            '%(log_color)s%(message)s',
            log_colors={
                'INFO': 'cyan',  # 使用青色显示一般信息
                'SUCCESS': 'green',  # 使用绿色显示成功信息
                'WARNING': 'yellow',  # 使用黄色显示警告
                'ERROR': 'red',  # 使用红色显示错误
            }
        ))
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


# 创建不同类型的日志记录器
logger = setup_colored_logger('tool_executor', logging.INFO)
result_logger = setup_colored_logger('result', logging.INFO)
intent_logger = setup_colored_logger('intent', logging.WARNING)
param_logger = setup_colored_logger('param', logging.DEBUG)


class ToolRegistry:
    """工具注册器，负责自动发现和注册工具"""

    @staticmethod
    def get_project_root() -> str:
        """
        获取项目根目录路径（main.py所在目录）

        Returns:
            str: 项目根目录的绝对路径
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        while current_dir != os.path.dirname(current_dir):
            if os.path.exists(os.path.join(current_dir, 'main.py')):
                return current_dir
            current_dir = os.path.dirname(current_dir)

        return os.getcwd()

    @staticmethod
    def scan_tools(relative_tool_dir: str = "agent_workflow/tools/tool") -> Dict[str, Type[BaseTool]]:
        """
        扫描指定目录下的所有工具类

        Args:
            relative_tool_dir: 相对于项目根目录的工具目录路径

        Returns:
            Dict[str, Type[BaseTool]]: 工具名称到工具类的映射
        """
        tools = {}

        # 获取项目根目录
        project_root = ToolRegistry.get_project_root()
        logger.info(f"📂 项目根目录: {project_root}")

        # 构建工具目录的完整路径
        tool_dir = os.path.join(project_root, relative_tool_dir)
        logger.info(f"🔍 扫描工具目录: {tool_dir}")

        if not os.path.exists(tool_dir):
            logger.warning(f"⚠️ 工具目录不存在: {tool_dir}")
            return tools

        # 遍历目录下的所有 .py 文件
        for root, _, files in os.walk(tool_dir):
            for file in files:
                if file.endswith('.py') and not file.startswith('__'):
                    # 构建模块路径
                    rel_path = os.path.relpath(root, project_root)
                    module_path = os.path.join(rel_path, file[:-3]).replace(os.path.sep, '.')

                    try:
                        # 导入模块
                        module = importlib.import_module(module_path)

                        # 查找模块中的工具类
                        for name, obj in inspect.getmembers(module):
                            if (inspect.isclass(obj) and
                                    issubclass(obj, BaseTool) and
                                    obj != BaseTool):
                                # 使用类名作为工具名称
                                tool_name = name
                                tools[tool_name] = obj
                                # 使用 SUCCESS 级别记录成功注册的工具
                                logger.info(f"✅ 已注册工具: {tool_name} from {module_path}")

                    except Exception as e:
                        logger.error(f"❌ 加载模块 {module_path} 失败: {str(e)}")

        return tools

    @staticmethod
    def register_tool(tools: Dict[str, Type[BaseTool]],
                      tool_class: Type[BaseTool],
                      name: Optional[str] = None) -> None:
        """
        注册单个工具

        Args:
            tools: 现有的工具字典
            tool_class: 要注册的工具类
            name: 工具名称，如果不提供则使用类名
        """
        tool_name = name or tool_class.__name__
        tools[tool_name] = tool_class
        logger.info(f"✅ 已手动注册工具: {tool_name}")


class ToolIntentParser:
    """根据用户输入识别工具意图和执行顺序"""

    def __init__(self, tools: Dict[str, Type['BaseTool']]):
        self.tools = tools
        self.llm = ChatOllama(model=ollama_model)
        self.logger = logging.getLogger(__name__)
        self.message_id = None
        # 创建工具描述列表
        self.tool_descriptions = {}
        for tool_name, tool_class in tools.items():
            tool_instance = tool_class()
            self.tool_descriptions[tool_name] = json.loads(tool_instance.get_description())

        # 简化后的意图识别模板，专注于执行顺序
        self.intent_template = ChatPromptTemplate.from_messages([
            ("system", TOOL_INTENT_PARSER)
        ])

    def format_tool_list(self) -> str:
        """格式化工具列表信息，只包含名称和描述"""
        tool_list = []
        for tool_name, desc in self.tool_descriptions.items():
            tool_list.append(f"工具名称: {tool_name}")
            tool_list.append(f"描述: {desc.get('description', '无描述')}")
            tool_list.append("")
        return "\n".join(tool_list)

    def parse_intent(self, query: UserQuery | FeishuUserQuery, verbose: bool) -> Dict[str, Any]:
        """解析用户意图，返回工具执行顺序"""
        try:
            start_time = time.time()
            messages = self.intent_template.format_messages(
                tool_list=self.format_tool_list(),
                query=query
            )

            response = self.llm.invoke(messages)
            content = response.content.strip()

            if verbose:
                result_logger.info(f"意图推理用时: {time.time() - start_time:.3f} 秒")

            # 清理响应内容
            content = self._clean_response(content)
            result = json.loads(content)

            # 验证和规范化任务
            valid_tasks = []
            for task in result.get("tasks", []):
                if not isinstance(task, dict):
                    continue

                tool_name = task.get("tool_name")
                if tool_name not in self.tools:
                    continue

                valid_tasks.append({
                    "id": task.get("id", f"task_{len(valid_tasks) + 1}"),
                    "tool_name": tool_name,
                    "reason": task.get("reason", ""),
                    "order": task.get("order", len(valid_tasks) + 1),
                    "depends_on": task.get("depends_on", [])
                })

            execution_info = {
                "tasks": valid_tasks,
                "execution_mode": result.get("execution_mode", "串行"),
                "execution_strategy": result.get("execution_strategy", {
                    "parallel_groups": [],
                    "reason": "默认串行执行"
                })
            }

            if verbose:
                logger.info("任务规划方案:\n%s",
                            json.dumps(execution_info, indent=2, ensure_ascii=False))

            return execution_info

        except Exception as e:
            logger.error(f"意图解析失败: {str(e)}")
            return {"tasks": []}

    def _clean_response(self, content: str) -> str:
        """清理LLM响应内容"""
        if content.startswith('```json'):
            content = content[7:]
        if content.endswith('```'):
            content = content[:-3]

        # 移除注释
        lines = []
        for line in content.split('\n'):
            # 跳过注释行
            if line.strip().startswith(('#', '//')):
                continue
            # 移除行内注释
            comment_start = min(
                (pos for pos in (line.find('#'), line.find('//'))
                 if pos != -1),
                default=-1
            )
            if comment_start != -1:
                line = line[:comment_start]
            if line.strip():
                lines.append(line)

        return '\n'.join(lines)


class ParameterOptimizer:
    """参数优化器，负责根据上下文优化工具参数"""

    def __init__(self, llm: Optional[ChatOllama] = None):
        self.llm = llm or ChatOllama(model=ollama_model)
        self.logger = logging.getLogger(__name__)
        self.message_id = None

        self.parameter_template = ChatPromptTemplate.from_messages([
            ("system", PARAMETER_OPTIMIZER)
        ])

    async def optimize_parameters(self, tool_name: str, tool_description: Dict, context: Dict,
                                  query: UserQuery | FeishuUserQuery, intent_result, verbose: bool = False):
        max_retries = 3
        current_retry = 0

        while current_retry < max_retries:
            try:
                start_time = time.time()

                await asyncio.sleep(0.1)

                formatted_description = self._format_tool_description(tool_description)

                cleaned_context = []
                for item in context.get("history", []):
                    try:
                        cleaned_item = {
                            "task_id": str(item.get("task_id", "")),
                            "tool_name": str(item.get("tool_name", "")),
                            "result": str(item.get("result", "")).strip()
                        }
                        cleaned_context.append(cleaned_item)
                    except Exception as e:
                        self.logger.warning(f"跳过处理历史记录项: {str(e)}")
                        continue

                # 预处理 intent_result
                cleaned_intent = {}
                if intent_result:
                    try:
                        cleaned_intent = {
                            "tasks": intent_result.get("tasks", []),
                            "execution_mode": intent_result.get("execution_mode", "串行"),
                            "execution_strategy": intent_result.get("execution_strategy", {})
                        }
                    except Exception as e:
                        self.logger.warning(f"意图结果处理失败: {str(e)}")

                # 构建完整的上下文
                formatted_context = {
                    "history": cleaned_context,
                    "intent": cleaned_intent
                }

                try:
                    context_json = json.dumps(formatted_context, ensure_ascii=False,
                                              default=str, separators=(',', ':'))

                    messages = self.parameter_template.format_messages(
                        query=query,
                        tool_name=tool_name,
                        tool_description=formatted_description,
                        context=context_json,
                        intent_result=json.dumps(cleaned_intent, ensure_ascii=False)
                    )
                except Exception as json_error:
                    self.logger.error(f"尝试 {current_retry + 1}/{max_retries} - JSON序列化失败: {json_error}")
                    raise

                response = self.llm.invoke(messages)

                try:
                    result = json.loads(response.content)
                except json.JSONDecodeError:
                    cleaned_content = self._clean_response(response.content)
                    result = json.loads(cleaned_content)

                if verbose:
                    self.logger.info(f"参数优化用时: {time.time() - start_time:.3f} 秒")
                    if "explanation" in result:
                        self.logger.info(f"参数优化说明: {result['explanation']}")
                        yield {
                            "type": "thinking_process",
                            "message_id": self.message_id,
                            "content": f"[Debug] 参数优化说明: {result['explanation']}"
                        }
                        await asyncio.sleep(0.1)

                # 验证参数
                if tool_name in result:
                    parameters = result[tool_name]
                    if self._validate_parameters(parameters, tool_description):
                        yield {
                            "type": "result",
                            "content": result
                        }
                        return

                raise ValueError("参数验证失败")

            except Exception as e:
                current_retry += 1
                self.logger.error(f"参数优化失败 (尝试 {current_retry}/{max_retries}): {str(e)}")
                yield {
                    "type": "thinking_process",
                    "message_id": self.message_id,
                    "content": f"参数优化失败，正在重试... ({current_retry}/{max_retries})"
                }
                await asyncio.sleep(0.1)

                if current_retry >= max_retries:
                    yield {
                        "type": "thinking_process",
                        "message_id": self.message_id,
                        "content": "达到最大重试次数，返回空参数..."
                    }
                    await asyncio.sleep(0.1)
                    yield {
                        "type": "result",
                        "content": {tool_name: {}}
                    }
                    return
                await asyncio.sleep(1)

            finally:
                if current_retry >= max_retries:
                    self.logger.warning(f"达到最大重试次数 ({max_retries})，放弃重试")

        yield {
            "type": "result",
            "content": {tool_name: {}}
        }

    def _format_tool_description(self, description: Dict) -> str:
        """格式化工具描述，提供清晰的参数约束信息"""
        sections = []

        # 工具基本信息
        sections.append(f"【工具描述】\n{description.get('description', '无描述')}\n")

        # 参数详情
        sections.append("【参数要求】")
        parameters = description.get("parameters", {})
        if not parameters:
            sections.append("无参数要求")
        else:
            for param_name, param_info in parameters.items():
                param_parts = []
                # 参数名和必需标记
                param_parts.append(f"\n■ {param_name}")
                if param_info.get("required", False):
                    param_parts.append("(必需)")

                # 参数详细信息
                details = []
                if "type" in param_info:
                    details.append(f"类型: {param_info['type']}")
                if "enum" in param_info:
                    details.append(f"有效值: {param_info['enum']}")
                if "description" in param_info:
                    details.append(f"说明: {param_info['description']}")

                # 添加参数约束
                if "minimum" in param_info or "maximum" in param_info:
                    constraints = []
                    if "minimum" in param_info:
                        constraints.append(f"最小值: {param_info['minimum']}")
                    if "maximum" in param_info:
                        constraints.append(f"最大值: {param_info['maximum']}")
                    details.append(f"取值范围: {', '.join(constraints)}")

                # 合并所有参数信息
                sections.append(" ".join(param_parts))
                sections.append("  " + "\n  ".join(details))

        return "\n".join(sections)

    def _clean_response(self, content: str) -> str:
        """清理LLM响应内容"""
        # 移除可能的代码块标记
        if content.startswith('```json'):
            content = content[7:]
        if content.endswith('```'):
            content = content[:-3]

        return content.strip()

    def _validate_parameters(self, parameters: Dict, tool_description: Dict) -> bool:
        """验证参数是否符合工具要求"""
        try:
            required_params = {
                name: info
                for name, info in tool_description.get("parameters", {}).items()
                if info.get("required", False)
            }

            # 检查必需参数
            for param_name in required_params:
                if param_name not in parameters:
                    self.logger.error(f"缺少必需参数: {param_name}")
                    return False

            # 检查参数类型和约束
            for param_name, param_value in parameters.items():
                param_info = tool_description.get("parameters", {}).get(param_name)
                if not param_info:
                    continue

                # 检查枚举值
                if "enum" in param_info:
                    enum_values = param_info["enum"]
                    # 处理字典列表形式的枚举值
                    if isinstance(enum_values, list) and all(isinstance(x, dict) for x in enum_values):
                        valid_values = [item.get("name") for item in enum_values]
                        if param_value not in valid_values:
                            self.logger.error(
                                f"参数 {param_name} 的值 '{param_value}' 不在允许范围内。\n"
                                f"有效值: {valid_values}"
                            )
                            return False
                    # 处理普通列表形式的枚举值
                    elif isinstance(enum_values, list):
                        if param_value not in enum_values:
                            self.logger.error(
                                f"参数 {param_name} 的值 '{param_value}' 不在允许范围内。\n"
                                f"有效值: {enum_values}"
                            )
                            return False

            return True

        except Exception as e:
            self.logger.error(f"参数验证失败: {str(e)}")
            return False


@dataclass
class ToolExecutor:
    """工具执行器，负责工具的初始化和执行"""
    tools: Dict[str, Type['BaseTool']]
    llm: Optional[ChatOllama] = None
    verbose: bool = False
    message_id: str = None

    def __post_init__(self):
        """初始化组件"""
        self.llm = self.llm or ChatOllama(model=ollama_model)
        self.intent_parser = ToolIntentParser(self.tools)
        self.parameter_optimizer = ParameterOptimizer(self.llm)
        self.result_formatter = ResultFormatter()
        self.logger = logging.getLogger(__name__)

        # 获取工具描述
        self.tool_descriptions = {}
        for name, tool_class in self.tools.items():
            try:
                tool_instance = tool_class()
                description = tool_instance.get_description()
                if isinstance(description, str):
                    description = json.loads(description)
                self.tool_descriptions[name] = description
            except Exception as e:
                logger.error(f"加载工具描述失败 {name}: {e}")

    def _build_tool_context(self, current_task: Dict, context: Dict) -> Dict:
        """构建工具执行上下文"""
        return {
            "current_task": {
                "id": current_task["id"],
                "tool_name": current_task["tool_name"],
                "reason": current_task.get("reason", "")
            },
            "history": [
                {
                    "task_id": task_id,
                    "tool_name": result["tool_name"],
                    "result": result["formatted_result"]
                }
                for task_id, result in context.items()
            ]
        }

    async def _execute_single_tool(self, task_info: Dict, context: Dict, verbose: bool,
                                   query: UserQuery | FeishuUserQuery, history, intent_result,chat_ui) -> AsyncGenerator[
        Dict[str, Any], None]:
        """执行单个工具"""
        tool_name = task_info["tool_name"]
        task_id = task_info["id"]
        max_retries = 3  # 最大重试次数
        current_retry = 0

        while current_retry < max_retries:
            try:
                # 构建上下文
                tool_context = self._build_tool_context(task_info, context)

                # 获取参数优化结果
                optimized_result = None
                async for msg in self.parameter_optimizer.optimize_parameters(
                        tool_name=tool_name,
                        tool_description=self.tool_descriptions[tool_name],
                        context=tool_context,
                        query=query,
                        intent_result=intent_result,
                        verbose=verbose,
                ):
                    if msg["type"] == "thinking_process":
                        yield msg
                    elif msg["type"] == "result":
                        optimized_result = msg["content"]
                    else:
                        yield msg

                # 添加历史记录
                optimized_result[tool_name]["history"] = history

                if verbose:
                    logger.info(f"执行工具 {tool_name} 的优化参数:\n{json.dumps(optimized_result, ensure_ascii=False)}")

                    # 执行工具
                    # 执行工具
                    result = await self.tools[tool_name]().run(**optimized_result[tool_name])

                    # 检查结果是否为空
                    if result is None:
                        if current_retry < max_retries - 1:
                            yield {
                                "type": "thinking_process",
                                "message_id": self.message_id,
                                "content": f"工具执行返回空结果，准备重试... ({current_retry + 1}/{max_retries})"
                            }
                            await asyncio.sleep(1)
                            current_retry += 1
                            continue
                        else:
                            raise ValueError("工具执行多次返回空结果")

                    try:
                        formatted_result = await self.format_result(tool_name, result,chat_ui)
                    except Exception:
                        if current_retry < max_retries - 1:
                            yield {
                                "type": "thinking_process",
                                "message_id": self.message_id,
                                "content": f"结果格式化失败，准备重试... ({current_retry + 1}/{max_retries})"
                            }
                            await asyncio.sleep(1)
                            current_retry += 1
                            continue
                        raise

                    # 返回完整结果
                    final_result = {
                        "type": "tool_complete",
                        "tool_name": tool_name,
                        "task_id": task_id,
                        "result": {
                            "parameters": optimized_result,
                            "result": result,
                            "tool_name": tool_name,
                            "formatted_result": formatted_result["result"],
                            "context": tool_context,
                            "links": formatted_result["links"]
                        }
                    }

                    yield final_result
                    break  # 成功执行后跳出重试循环

            except Exception as e:
                current_retry += 1
                error_msg = f"工具 {tool_name} 执行失败: {str(e)}"
                logger.error(error_msg)

                if current_retry >= max_retries:
                    error_result = {
                        "type": "thinking_process",
                        "message_id": self.message_id,
                        "error": error_msg
                    }
                    yield error_result
                    raise Exception(f"达到最大重试次数 ({max_retries})，工具执行失败: {error_msg}")
                else:
                    yield {
                        "type": "thinking_process",
                        "message_id": self.message_id,
                        "content": f"执行失败，准备重试... ({current_retry}/{max_retries})"
                    }
                    await asyncio.sleep(1)

    async def execute_tools(self, query: UserQuery | FeishuUserQuery, history,chat_ui) -> AsyncGenerator[
        Dict[str, Any], None]:
        """执行工具链"""
        global execution_mode
        try:
            # 处理查询
            processed_query = self._process_query(query)
            if self.verbose:
                result_logger.info("开始处理查询: %s", processed_query)

            yield {
                "type": "thinking_process",
                "message_id": self.message_id,
                "content": "分析问题并选择合适的处理方式..."
            }
            await asyncio.sleep(0.1)

            # 获取执行计划
            intent_result = self.intent_parser.parse_intent(processed_query, self.verbose)

            yield {
                "type": "thinking_process",
                "message_id": self.message_id,
                "content": "[Debug] 意图分析结果: {}".format(intent_result)
            }
            await asyncio.sleep(0.2)

            if not intent_result.get("tasks"):
                yield {
                    "type": "error",
                    "message_id": self.message_id,
                    "content": "未找到合适的工具"
                }
                return

            async for step_result in self.serial_execute_tools(intent_result, processed_query, history,chat_ui):
                yield step_result

        except Exception as e:
            logger.error(f"工具执行失败: {str(e)}")
            yield {
                "type": "error",
                "message_id": self.message_id,
                "content": f"执行失败: {str(e)}"
            }

    def _process_query(self, query: UserQuery | FeishuUserQuery) -> UserQuery | FeishuUserQuery:
        """处理查询，添加附件信息"""
        if not hasattr(query, 'attachments') or not query.attachments:
            return query

        base_text = query.text
        if isinstance(query, FeishuUserQuery):
            # 处理飞书消息附件
            attachment_info = "\n附加信息:\n" + "\n".join(
                f"feishu_attachment: {att}"
                for att in query.attachments
            )
            return FeishuUserQuery(
                text=base_text + attachment_info,
                attachments=[str(att.content) for att in query.attachments]
            )
        else:
            # 处理标准UserQuery附件
            attachment_info = "\n附加信息:\n" + "\n".join(
                f"{att.type.name.lower()}: {att.content}"
                for att in query.attachments
            )
            return UserQuery(
                text=base_text + attachment_info,
                attachments=query.attachments
            )

    async def serial_execute_tools(
            self,
            intent_result: Dict[str, Any],
            query: UserQuery | FeishuUserQuery,
            history,
            chat_ui
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """串行执行工具"""
        global task_id, link_text
        try:
            tasks = intent_result.get("tasks", [])

            yield {
                "type": "thinking_process",
                "message_id": self.message_id,
                "content": "开始串行模式执行任务"
            }
            await asyncio.sleep(0.1)

            if not tasks:
                yield {"error": "未找到合适的工具"}

            # 按顺序排序任务
            tasks.sort(key=lambda x: x.get("order", 1))

            # 全局上下文和结果存储
            context = {}  # 存储所有已执行工具的结果
            tools_result = {}  # 存储最终返回的结果
            all_links = []
            # 按顺序执行任务
            for i, task in enumerate(tasks):
                try:
                    if self.verbose:
                        current_task = i + 1
                        total_tasks = len(tasks)
                        tool_name = task['tool_name']

                        yield {
                            "type": "thinking_process",
                            "message_id": self.message_id,
                            "content": f"\n执行任务 {current_task}/{total_tasks}: {tool_name}"
                        }
                        await asyncio.sleep(0.1)

                        logger.info(f"\n执行任务 {current_task}/{total_tasks}: {tool_name}")
                        logger.info(f"任务原因: {task.get('reason', '无')}")

                    # 执行工具
                    final_result = None
                    async for step_result in self._execute_single_tool(
                            task_info=task,
                            context=context,
                            verbose=self.verbose,
                            query=query,
                            history=history,
                            intent_result=intent_result,
                            chat_ui=chat_ui
                    ):
                        if step_result["type"] == "tool_complete":
                            final_result = step_result
                            yield step_result  # 转发最终结果
                        else:
                            # 转发进度信息
                            yield step_result

                    if final_result:
                        # 使用最终结果更新上下文
                        task_id = task["id"]
                        context[task_id] = final_result["result"]

                        formatted_result = final_result["result"]["formatted_result"]
                        links = final_result["result"]["links"]

                        # 如果有链接，添加编号格式的链接引用
                        if links is not None:
                            link_text = "\n" + "\n".join(f"{link}" for i, link in enumerate(links))
                            all_links.extend(links)
                            result_text = formatted_result
                        else:
                            result_text = formatted_result

                        tools_result[task_id] = {
                            "tool_name": task["tool_name"],
                            "reason": task.get("reason", ""),
                            "result": result_text
                        }

                    if self.verbose:
                        logger.info(f"任务 {task_id} 执行完成")

                except Exception as e:
                    logger.error(f"任务 {task.get('id', '')} 执行失败: {str(e)}")
                    continue

            if self.verbose:
                result_logger.info(f"\n所有任务执行完成:\n{tools_result}")

            yield {
                "status": "success",
                "result": tools_result,
                "link": "\n".join(all_links) if all_links else ""
            }

        except Exception as e:
            logger.error(f"串行执行失败: {str(e)}")
            yield {"error": f"执行失败: {str(e)}"}

    async def format_result(self, tool_name: str, result: Any, chat_ui: bool = False) -> Dict:
        """格式化工具执行结果"""
        try:
            output = []
            links = []

            if tool_name == "SearchTool" and isinstance(result, dict):
                links = await self.result_formatter.format_search_results(result, output)
            elif tool_name == "WeatherTool":
                await self.result_formatter.format_weather_results(result, output)
            elif tool_name == "FileConverterTool":
                self.result_formatter.format_file_converter_results(result, output,chat_ui)
            elif tool_name == "DescriptionImageTool":
                await self.result_formatter.format_image_description_results(result, output)
            elif tool_name == "ImageGeneratorTool":
                self.result_formatter.format_image_generator_results(result, output)
            elif tool_name == "AudioTool":
                self.result_formatter.format_audio_results(result, output,chat_ui)
            elif tool_name == "ChatTool":
                output.extend([f"{str(result)}"])
            else:
                output.extend([f"----------{tool_name}----------", str(result)])

            # 返回字典格式的结果
            return {
                "result": "\n".join(str(item) for item in output),
                "links": links
            }

        except Exception as e:
            error_msg = f"结果格式化失败: {str(e)}\n原始结果: {str(result)}"
            logger.error(error_msg)
            return {
                "result": error_msg,
                "links": []
            }
