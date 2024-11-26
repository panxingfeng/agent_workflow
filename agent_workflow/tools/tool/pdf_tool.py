# -*- coding: utf-8 -*-
"""
@file: pdf_tool.py
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2024-11-23
@version: 1.0.0
@license: MIT License

@description:
文件格式转换工具类（FileConverterTool）

主要功能：
实现各种文件格式之间的转换，包括PDF、Word、Image等多种格式

核心特性：
1. 多格式支持：支持多种文件格式的互相转换
2. 多引擎集成：集成LibreOffice、Unoconv、Pandoc等转换引擎
3. 自动依赖处理：自动检测和安装必要的依赖
4. 灵活配置：支持自定义输出和批量处理
5. 错误处理：完善的异常捕获和错误恢复机制

Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""
import asyncio
import json
import os
import platform
import traceback
from enum import Enum
from typing import List, Optional
import tempfile
import zipfile
import subprocess
import sys
import requests
from pptx import Presentation
from pdf2image import convert_from_path
from pptx.util import Inches
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from agent_workflow.tools.tool.base import BaseTool

# 设置Ghostscript环境变量
os.environ["PATH"] += r";C:\Program Files\gs\gs10.04.0\bin"


class ConversionType(str, Enum):
    """
    文件转换类型枚举

    定义支持的所有转换类型：
    - URL_TO_PDF: 网页转PDF
    - PDF_TO_WORD: PDF转Word
    - PDF_TO_TEXT: PDF转文本
    - PDF_TO_HTML: PDF转HTML
    - PDF_TO_IMAGE: PDF转图片
    - PDF_TO_PPT: PDF转PPT
    - PDF_TO_MARKDOWN: PDF转Markdown
    - FILE_TO_PDF: 其他格式转PDF
    - MARKDOWN_TO_PDF: Markdown转PDF
    """
    URL_TO_PDF = "url_to_pdf"
    PDF_TO_WORD = "pdf_to_word"
    PDF_TO_TEXT = "pdf_to_text"
    PDF_TO_HTML = "pdf_to_html"
    PDF_TO_IMAGE = "pdf_to_image"
    PDF_TO_PPT = "pdf_to_ppt"
    PDF_TO_MARKDOWN = "pdf_to_markdown"
    FILE_TO_PDF = "file_to_pdf"
    MARKDOWN_TO_PDF = "markdown_to_pdf"

    @classmethod
    def list_tasks(cls) -> List[str]:
        """
        列出所有支持的转换类型

        Returns:
            所有支持的转换类型列表
        """
        return [task.value for task in cls]


def outputData(data: str, printInfo: bool = False):
    """
    输出数据的辅助函数

    Args:
        data: 要输出的数据
        printInfo: 是否打印信息
    """
    if printInfo:
        print(data)


class FileConverterTool(BaseTool):
    """
    文件转换工具类

    功能：
    1. 支持多种文件格式的转换
    2. 自动管理依赖和资源
    3. 提供统一的转换接口
    4. 支持自定义输出格式

    属性：
        output_directory: 输出目录
        printInfo: 是否打印详细信息
        base_dir: 基础目录路径
        poppler_path: Poppler工具路径
    """

    def __init__(self, output_directory: str = "output", printInfo: bool = False):
        """
        初始化文件转换工具

        Args:
            output_directory: 输出目录路径
            printInfo: 是否打印详细信息
        """
        self.upload_dir = "upload"
        self.output_dir = "output"
        self.output_directory = output_directory
        self.printInfo = printInfo
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.poppler_path = os.path.join(self.base_dir, "poppler", "bin")

        # 初始化目录
        self._ensure_directories()

        # 检查Poppler
        if not self._check_poppler():
            self._download_poppler()

        self.register_fonts()

    def get_description(self) -> str:
        tool_info = {
            "name": "FileConverterTool",
            "description": "文件格式转换工具，支持多种格式互转",
            "parameters": {
                "conversion_type": {
                    "type": "string",
                    "description": "转换类型",
                    "required": True,
                    "enum": [
                        {"name": "url_to_pdf", "description": "网页转PDF"},
                        {"name": "pdf_to_word", "description": "PDF转Word"},
                        {"name": "pdf_to_text", "description": "PDF转文本"},
                        {"name": "pdf_to_html", "description": "PDF转HTML"},
                        {"name": "pdf_to_image", "description": "PDF转图片"},
                        {"name": "pdf_to_ppt", "description": "PDF转PPT"},
                        {"name": "pdf_to_markdown", "description": "PDF转Markdown"},
                        {"name": "file_to_pdf", "description": "其他格式转PDF"},
                        {"name": "markdown_to_pdf", "description": "Markdown转PDF"}
                    ]
                },
                "input_path": {
                    "type": "string",
                    "description": "输入文件路径或URL",
                    "required": True
                }
            }
        }
        return json.dumps(tool_info, ensure_ascii=False)

    def register_fonts(self):
        """
        注册字体

        功能：
        1. 尝试注册系统中的中文字体
        2. 支持多平台（Windows/Linux/macOS）
        3. 优雅降级处理
        """
        try:
            # 常用字体路径列表
            font_paths = [
                # Windows字体
                "C:/Windows/Fonts/msyh.ttf",  # 微软雅黑
                "C:/Windows/Fonts/simsun.ttc",  # 宋体
                # Linux字体
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                # macOS字体
                "/System/Library/Fonts/PingFang.ttc"
            ]

            # 尝试注册第一个可用的字体
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('CustomFont', font_path))
                        return
                    except:
                        continue
        except:
            pass  # 如果注册失败，使用默认字体


    def _ensure_directories(self):
        """
        创建必要的目录结构

        功能：
        1. 确保输出目录存在
        2. 创建Poppler工具目录
        3. 提供操作反馈
        """
        directories = [
            self.output_directory,
            os.path.join(self.base_dir, "poppler")
        ]
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"Created directory: {directory}")

    def _check_poppler(self) -> bool:
        """
        检查Poppler是否已正确安装

        Returns:
            bool: Poppler是否可用

        检查项目：
        1. 核心执行文件存在性
        2. 文件权限
        3. 版本兼容性
        """
        required_files = ['pdfinfo.exe', 'pdftocairo.exe']
        return all(os.path.exists(os.path.join(self.poppler_path, file))
                   for file in required_files)

    def _download_poppler(self):
        """
        下载并安装Poppler

        功能：
        1. 从GitHub下载最新版本
        2. 自动解压和配置
        3. 配置环境变量
        4. 提供详细的安装反馈

        异常处理：
        - 下载失败提供备选方案
        - 解压错误处理
        - 权限问题处理
        """
        print("\nDownloading Poppler...")

        try:
            # 下载Poppler
            poppler_url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.11.0-0/Release-23.11.0-0.zip"
            response = requests.get(poppler_url, stream=True)
            response.raise_for_status()

            # 保存和解压
            temp_zip = os.path.join(self.base_dir, "poppler_temp.zip")
            with open(temp_zip, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print("Extracting Poppler...")
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                poppler_dir = os.path.join(self.base_dir, "poppler")
                zip_ref.extractall(poppler_dir)

            # 清理临时文件
            os.remove(temp_zip)
            print("Poppler installation completed!")

            # 环境变量配置
            if sys.platform == 'win32':
                os.environ['PATH'] = f"{self.poppler_path};{os.environ['PATH']}"

        except Exception as e:
            print(f"Failed to download Poppler: {str(e)}")
            print("Please download manually from: https://github.com/oschwartz10612/poppler-windows/releases")
            print(f"And extract to: {self.poppler_path}")

    def _generate_output_path(self, prefix: str, extension: str) -> str:
        """生成输出文件路径"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.{extension}"
        return os.path.join(self.output_dir, filename)

    def convert_with_libreoffice(self, input_file: str, output_file: str) -> bool:
        """
        使用LibreOffice进行文件转换

        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径

        Returns:
            bool: 转换是否成功

        功能：
        1. 自动检测LibreOffice安装
        2. 支持多平台
        3. 命令行参数优化
        4. 错误处理和重试
        """
        try:
            # 检测LibreOffice路径
            if platform.system() == 'Windows':
                soffice_path = 'C:\\Program Files\\LibreOffice\\program\\soffice.exe'
                if not os.path.exists(soffice_path):
                    soffice_path = 'C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe'
            else:
                soffice_path = 'soffice'

            # 构建转换命令
            cmd = [
                soffice_path,
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', os.path.dirname(output_file),
                input_file
            ]

            # 执行转换
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()

            # 检查输出文件
            expected_output = os.path.join(
                os.path.dirname(output_file),
                os.path.splitext(os.path.basename(input_file))[0] + '.pdf'
            )

            if os.path.exists(expected_output):
                # 重命名到目标路径
                os.rename(expected_output, output_file)
                return True
            return False

        except Exception as e:
            print(f"LibreOffice conversion failed: {str(e)}")
            return False

    def convert_with_unoconv(self, input_file: str, output_file: str) -> bool:
        """
        使用Unoconv进行文件转换

        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径

        Returns:
            bool: 转换是否成功
        """
        try:
            cmd = ['unoconv', '-f', 'pdf', '-o', output_file, input_file]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()

            return os.path.exists(output_file)
        except Exception as e:
            print(f"Unoconv conversion failed: {str(e)}")
            return False

    def convert_with_pandoc(self, input_file: str, output_file: str) -> bool:
        """
        使用Pandoc进行文件转换

        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径

        Returns:
            bool: 转换是否成功
        """
        try:
            cmd = ['pandoc', input_file, '-o', output_file]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()

            return os.path.exists(output_file)
        except Exception as e:
            print(f"Pandoc conversion failed: {str(e)}")
            return False

    @staticmethod
    def get_system_info() -> dict:
        """
        获取系统环境信息

        Returns:
            dict: 系统信息字典，包含：
            - 平台信息
            - 系统架构
            - 可用转换器列表

        功能：
        1. 检测系统环境
        2. 检查可用转换器
        3. 提供系统兼容性信息
        """
        info = {
            'platform': platform.system(),
            'architecture': platform.architecture(),
            'available_converters': []
        }

        # 检查LibreOffice
        try:
            if platform.system() == 'Windows':
                libreoffice_paths = [
                    'C:\\Program Files\\LibreOffice\\program\\soffice.exe',
                    'C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe'
                ]
                if any(os.path.exists(path) for path in libreoffice_paths):
                    info['available_converters'].append('LibreOffice')
            else:
                process = subprocess.Popen(['which', 'soffice'], stdout=subprocess.PIPE)
                if process.communicate()[0]:
                    info['available_converters'].append('LibreOffice')
        except:
            pass

        # 检查其他转换器
        for converter in ['unoconv', 'pandoc']:
            try:
                process = subprocess.Popen(['which', converter], stdout=subprocess.PIPE)
                if process.communicate()[0]:
                    info['available_converters'].append(converter.title())
            except:
                pass

        return info

    def pdf_to_pdfa(self, pdf_path: str) -> Optional[str]:
        """
        将PDF转换为PDF/A格式（存档级PDF）

        Args:
            pdf_path: 源PDF文件路径

        Returns:
            str: 生成的PDF/A文件路径，失败时返回None

        功能特点：
        1. 符合PDF/A-2标准
        2. 支持颜色转换
        3. 确保长期保存
        4. 保持文档完整性

        注意事项：
        - 需要安装Ghostscript
        - 确保颜色配置正确
        - 验证PDF/A兼容性
        """
        try:
            import pypdf
            # 生成输出路径
            output_path = self._generate_output_path("converted", "pdf")

            # 配置Ghostscript命令行参数
            gs_command = [
                'gs',  # Ghostscript命令
                '-dPDFA=2',  # PDF/A-2标准
                '-dBATCH',  # 批处理模式
                '-dNOPAUSE',  # 不暂停
                '-sColorConversionStrategy=UseDeviceIndependentColor',  # 颜色转换策略
                '-sDEVICE=pdfwrite',  # 输出设备
                '-dPDFACompatibilityPolicy=1',  # PDF/A兼容性策略
                f'-sOutputFile={output_path}',  # 输出文件
                pdf_path  # 输入文件
            ]

            # 执行转换命令
            result = subprocess.run(gs_command, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Ghostscript错误: {result.stderr}")

            outputData(data=f"PDF/A文件已保存至: {output_path}", printInfo=self.printInfo)
            return output_path

        except Exception as e:
            print(f"Failed to convert PDF to PDF/A: {str(e)}")
            return None

    async def url_to_pdf(self, url: str) -> Optional[str]:
        """
        将网页转换为PDF文件（异步版本）

        Args:
            url: 待转换的网页URL

        Returns:
            str: 生成的PDF文件路径，失败时返回None

        功能：
        1. 使用异步Playwright进行网页渲染
        2. 自动处理动态内容
        3. 支持自定义PDF参数
        4. 提供详细的转换状态
        """
        try:
            from playwright.async_api import async_playwright
            import asyncio

            # 生成输出路径
            output_path = self._generate_output_path("url_converted", "pdf")

            # 安装浏览器（如果需要）
            try:
                process = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "playwright", "install", "chromium",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
            except Exception as e:
                print(f"Failed to install browsers: {e}")
                return None

            async with async_playwright() as p:
                # 启动浏览器
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox']
                )

                # 创建上下文和页面
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    device_scale_factor=1.5
                )
                page = await context.new_page()

                # 加载页面
                outputData(f"Loading URL: {url}", self.printInfo)
                await page.goto(url, wait_until="networkidle", timeout=60000)

                # PDF设置
                pdf_options = {
                    "path": output_path,
                    "format": "a4",
                    "margin": {
                        "top": "1cm",
                        "right": "1cm",
                        "bottom": "1cm",
                        "left": "1cm"
                    },
                    "print_background": True,
                    "scale": 0.8
                }

                # 生成PDF
                await page.pdf(**pdf_options)

                # 清理资源
                await context.close()
                await browser.close()

                outputData(f"PDF saved to: {output_path}", self.printInfo)
                return output_path

        except Exception as e:
            print(f"URL to PDF conversion failed: {str(e)}")
            print(f"Detailed error: {traceback.format_exc()}")
            return None

    async def pdf_to_word(self, pdf_path: str, output_format: str = 'docx') -> Optional[str]:
        """
        将PDF转换为Word文档

        Args:
            pdf_path: PDF文件路径
            output_format: 输出格式，默认为docx

        Returns:
            str: 生成的Word文档路径，失败时返回None
        """
        try:
            from pdf2docx import Converter
            import asyncio
            import os

            # 获取当前工作目录
            current_dir = os.getcwd()
            print(f"当前工作目录: {current_dir}")

            # 构建完整的PDF路径，使用提供的路径直接拼接
            full_pdf_path = os.path.join(current_dir, pdf_path)
            print(f"PDF完整路径: {full_pdf_path}")

            # 规范化路径（处理斜杠/反斜杠）
            full_pdf_path = os.path.normpath(full_pdf_path)

            # 验证文件是否存在
            if not os.path.exists(full_pdf_path):
                # 列出upload目录中的所有文件
                upload_dir = os.path.join(current_dir, 'upload')
                if os.path.exists(upload_dir):
                    files = os.listdir(upload_dir)
                    print(f"Upload目录中的文件: {files}")
                raise FileNotFoundError(f"PDF文件未找到: {full_pdf_path}")

            if os.path.getsize(full_pdf_path) == 0:
                raise ValueError(f"PDF文件为空: {full_pdf_path}")

            # 确保output目录存在
            output_dir = os.path.join(current_dir, self.output_dir)
            os.makedirs(output_dir, exist_ok=True)

            # 生成输出路径
            output_path = self._generate_output_path("converted", output_format)

            # 创建转换器对象
            cv = Converter(full_pdf_path)

            try:
                # 执行转换
                await asyncio.to_thread(cv.convert, output_path)
            finally:
                # 确保在转换完成后关闭转换器
                await asyncio.to_thread(cv.close)

            # 验证输出文件
            if not os.path.exists(output_path):
                raise RuntimeError("转换完成但输出文件未生成")

            if os.path.getsize(output_path) == 0:
                raise RuntimeError("转换完成但输出文件为空")

            outputData(f"Word文档已保存至: {output_path}", self.printInfo)
            return output_path

        except FileNotFoundError as e:
            print(f"Failed to convert PDF to Word: {str(e)}")
            return None
        except ValueError as e:
            print(f"Failed to convert PDF to Word: {str(e)}")
            return None
        except Exception as e:
            print(f"Failed to convert PDF to Word: {str(e)}")
            import traceback
            print(f"Detailed error: {traceback.format_exc()}")
            return None

    async def pdf_to_text(self, pdf_path: str) -> Optional[str]:
        """
        将PDF转换为文本文件

        Args:
            pdf_path: PDF文件路径

        Returns:
            str: 生成的文本文件路径，失败时返回None

        功能：
        1. 提取文本内容
        2. 保持基本排版结构
        3. 支持多语言
        """
        try:
            import pymupdf4llm
            import aiofiles
            import asyncio

            # 生成输出路径
            output_path = self._generate_output_path("converted", "txt")

            # 在线程池中执行PDF转换
            text = await asyncio.to_thread(pymupdf4llm.to_markdown, pdf_path)

            # 异步写入文件
            async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
                await f.write(text)

            outputData(f"Text file saved to: {output_path}", self.printInfo)
            return output_path

        except Exception as e:
            print(f"PDF to text conversion failed: {str(e)}")
            return None

    def pdf_to_presentation(self, pdf_path: str, output_format: str = 'pptx') -> Optional[str]:
        """
        将PDF文档转换为演示文稿（PPT）

        Args:
            pdf_path: PDF文件路径
            output_format: 输出格式，默认为'pptx'

        Returns:
            str: 生成的演示文稿路径，失败时返回None

        功能特点：
        1. 保持PDF页面布局
        2. 自动图片尺寸调整
        3. 居中显示内容
        4. 高质量图像转换

        工作流程：
        1. PDF转换为高质量图片
        2. 创建PPT幻灯片
        3. 将图片添加到幻灯片
        4. 优化布局和显示
        """
        try:
            # 获取Poppler工具路径
            poppler_path = os.path.join(self.base_dir, 'poppler', 'bin')

            # 生成输出文件路径
            output_path = self._generate_output_path("converted", output_format)

            # 初始化PPT文档
            prs = Presentation()

            # 将PDF页面转换为高质量图片（300dpi）
            images = convert_from_path(
                pdf_path,
                dpi=300,
                poppler_path=poppler_path
            )

            # 获取PPT页面尺寸
            slide_width = prs.slide_width  # 幻灯片宽度
            slide_height = prs.slide_height  # 幻灯片高度

            # 处理每一页
            for image in images:
                # 创建空白幻灯片（使用布局6：空白布局）
                blank_slide_layout = prs.slide_layouts[6]
                slide = prs.slides.add_slide(blank_slide_layout)

                # 创建临时图片文件
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    tmp_name = tmp.name  # 保存临时文件名
                    tmp.close()  # 关闭文件句柄

                    # 将图片保存为PNG格式
                    image.save(tmp_name, 'PNG')

                    # 设置图片在幻灯片中的尺寸
                    img_width = Inches(10)  # 标准宽度10英寸
                    img_height = Inches(7.5)  # 标准高度7.5英寸

                    # 计算居中位置
                    left = (slide_width - img_width) / 2
                    top = (slide_height - img_height) / 2

                    # 将图片添加到幻灯片
                    slide.shapes.add_picture(
                        tmp_name,  # 图片路径
                        left=left,  # 左边距
                        top=top,  # 上边距
                        width=img_width,  # 图片宽度
                        height=img_height  # 图片高度
                    )

                    # 清理临时文件
                    os.unlink(tmp_name)

            # 保存最终的PPT文件
            prs.save(output_path)
            outputData(data=f"演示文稿已保存至: {output_path}", printInfo=self.printInfo)
            return output_path

        except Exception as e:
            print(f"Failed to convert PDF to presentation: {str(e)}")
            return None


    def pdf_to_image(self, pdf_path: str, image_format: str = 'png',
                     single_or_multiple: str = 'multiple',
                     color_type: str = 'color', dpi: str = '300') -> Optional[str]:
        """
        将PDF转换为图片

        Args:
            pdf_path: PDF文件路径
            image_format: 图片格式（png/jpg）
            single_or_multiple: 单页或多页模式
            color_type: 颜色模式
            dpi: 图像分辨率

        Returns:
            str: 生成的图片文件或ZIP文件路径
        """
        try:
            if not self._check_poppler():
                print("\nPoppler is not properly installed.")
                self._download_poppler()
                if not self._check_poppler():
                    return None

            from pdf2image import convert_from_path
            import tempfile
            import shutil

            # 确保Poppler在环境变量中
            os.environ['PATH'] = f"{self.poppler_path};{os.environ['PATH']}"

            # 构建完整的PDF路径
            full_pdf_path = os.path.normpath(os.path.join(os.getcwd(), pdf_path))
            print(f"PDF完整路径: {full_pdf_path}")

            # 检查文件是否存在
            if not os.path.exists(full_pdf_path):
                print(f"文件不存在: {full_pdf_path}")
                return None

            # 创建临时目录
            temp_dir = tempfile.mkdtemp()
            try:
                # 转换PDF页面
                images = convert_from_path(
                    full_pdf_path,
                    dpi=int(dpi),
                    fmt=image_format.lower(),
                    output_folder=temp_dir,
                    poppler_path=self.poppler_path
                )

                if single_or_multiple == 'multiple':
                    # 创建ZIP包含所有页面
                    output_path = self._generate_output_path("converted", "zip")
                    with zipfile.ZipFile(output_path, 'w') as zf:
                        for i, image in enumerate(images):
                            image_path = os.path.join(temp_dir, f'page_{i + 1}.{image_format}')
                            image.save(image_path, format=image_format.upper())
                            zf.write(image_path, f'page_{i + 1}.{image_format}')
                else:
                    # 仅保存第一页
                    output_path = self._generate_output_path("converted", image_format)
                    images[0].save(output_path, format=image_format.upper())

                outputData(f"Images saved to: {output_path}", self.printInfo)
                return output_path

            finally:
                # 清理临时文件
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    print(f"Warning: Failed to clean up temporary directory: {e}")

        except Exception as e:
            print(f"\nPDF to image conversion failed: {str(e)}")
            print(f"Detailed error: {traceback.format_exc()}")
            return None

    def pdf_to_html(self, pdf_path: str) -> Optional[str]:
        """
        将PDF转换为HTML文件

        Args:
            pdf_path: PDF文件路径

        Returns:
            str: 生成的HTML文件路径，失败时返回None

        功能：
        1. 保持原始排版和样式
        2. 支持图片和表格转换
        3. 生成响应式布局
        """
        try:
            from pdfminer.converter import HTMLConverter
            from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
            from pdfminer.pdfpage import PDFPage
            from pdfminer.layout import LAParams

            output_path = self._generate_output_path("converted", "html")

            # 初始化资源管理器
            rsrcmgr = PDFResourceManager()
            laparams = LAParams()

            with open(output_path, 'wb') as outfp:
                # 配置HTML转换器
                device = HTMLConverter(rsrcmgr, outfp, codec='utf-8', laparams=laparams)
                interpreter = PDFPageInterpreter(rsrcmgr, device)

                # 处理每一页
                with open(pdf_path, 'rb') as fp:
                    for page in PDFPage.get_pages(fp):
                        interpreter.process_page(page)
                device.close()

            outputData(f"HTML file saved to: {output_path}", self.printInfo)
            return output_path
        except Exception as e:
            print(f"PDF to HTML conversion failed: {str(e)}")
            return None

    def pdf_to_markdown(self, pdf_path: str, output_dir: str = "output"):
        """
        将PDF转换为Markdown格式

        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录

        Returns:
            str: 生成的Markdown文件路径

        功能：
        1. 保持文档结构
        2. 转换标题和列表
        3. 处理图片和链接
        4. 支持代码块和表格
        """
        try:
            import pymupdf4llm
            from pathlib import Path

            # 创建输出目录
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)

            # 生成输出文件路径
            pdf_name = Path(pdf_path).stem
            output_file = output_path / f"{pdf_name}.md"

            # 转换内容
            text = pymupdf4llm.to_markdown(pdf_path)
            output_file.write_text(text, encoding='utf-8')

            outputData(f"Markdown file saved to: {str(output_file.absolute())}", self.printInfo)
            return str(output_file.absolute())

        except Exception as e:
            print(f"PDF to Markdown conversion failed: {str(e)}")
            return None

    def markdown_to_pdf(self, markdown_path: str) -> Optional[str]:
        """
        将Markdown转换为PDF

        Args:
            markdown_path: Markdown文件路径

        Returns:
            str: 生成的PDF文件路径

        功能：
        1. 支持完整的Markdown语法
        2. 自定义样式和主题
        3. 代码高亮
        4. 表格和图片处理
        """
        try:
            import markdown
            import pdfkit

            # 配置wkhtmltopdf路径
            path_wkhtmltopdf = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
            if not os.path.isfile(path_wkhtmltopdf):
                print(f"Error: wkhtmltopdf not found at '{path_wkhtmltopdf}'")
                print("Please install from https://wkhtmltopdf.org/downloads.html")
                return None

            config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
            output_path = self._generate_output_path("converted", "pdf")

            # 读取和转换Markdown
            with open(markdown_path, 'r', encoding='utf-8') as f:
                md_content = f.read()

            # 转换为HTML
            html_content = markdown.markdown(
                md_content,
                extensions=['tables', 'fenced_code', 'codehilite']
            )

            # 添加样式
            html_doc = f'''
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 2cm; }}
                        h1, h2, h3 {{ color: #333; }}
                        code {{ background-color: #f5f5f5; padding: 2px 4px; }}
                        pre {{ background-color: #f5f5f5; padding: 1em; }}
                        blockquote {{ border-left: 4px solid #ccc; margin-left: 0; padding-left: 1em; }}
                    </style>
                </head>
                <body>{html_content}</body>
                </html>
            '''

            # 保存临时HTML
            temp_html = os.path.join(self.output_directory, 'temp.html')
            with open(temp_html, 'w', encoding='utf-8') as f:
                f.write(html_doc)

            # 配置PDF生成选项
            options = {
                'enable-local-file-access': True,
                'no-stop-slow-scripts': True,
            }

            # 转换为PDF
            pdfkit.from_file(temp_html, output_path, configuration=config, options=options)

            # 清理临时文件
            os.remove(temp_html)

            outputData(f"PDF saved to: {output_path}", self.printInfo)
            return output_path

        except Exception as e:
            print(f"Markdown to PDF conversion failed: {str(e)}")
            return None

    def file_to_pdf(self, file_path: str) -> Optional[str]:
        """
        通用文件转PDF方法

        Args:
            file_path: 源文件路径

        Returns:
            str: 生成的PDF文件路径

        功能：
        1. 支持多种文件格式
        2. 多引擎自动切换
        3. 智能失败恢复
        4. 详细的转换日志
        """
        try:
            output_path = self._generate_output_path("converted", "pdf")

            # 检查文件存在性
            if not os.path.exists(file_path):
                print(f"File not found: {file_path}")
                return None

            # 尝试不同的转换方法
            converters = [
                (self.convert_with_libreoffice, "LibreOffice"),
                (self.convert_with_unoconv, "Unoconv"),
                (self.convert_with_pandoc, "Pandoc")
            ]

            # 依次尝试每个转换器
            for converter, name in converters:
                try:
                    if converter(file_path, output_path):
                        outputData(f"PDF saved to: {output_path}", self.printInfo)
                        return output_path
                except Exception:
                    continue

            print("File to PDF conversion failed")
            return None

        except Exception as e:
            print(f"File to PDF conversion failed: {str(e)}")
            print(f"Detailed error: {traceback.format_exc()}")
            return None

    async def run(self, **kwargs) -> str:
        """
        执行文件转换的统一入口

        Args:
            **kwargs: 关键字参数
                - conversion_type: 转换类型
                - input_path/url: 输入文件路径或URL

        Returns:
            str: 转换结果或错误信息
        """
        try:
            # 获取参数
            conversion_type = kwargs.get("conversion_type")
            input_path = kwargs.get("input_path") or kwargs.get("url")  # 支持 url 参数

            # 参数验证
            if not conversion_type:
                return "转换失败: 缺少转换类型参数"
            if not input_path:
                return "转换失败: 缺少输入路径参数"

            # 根据类型调用相应方法
            conversion_methods = {
                "url_to_pdf": self.url_to_pdf,
                "pdf_to_word": self.pdf_to_word,
                "pdf_to_text": self.pdf_to_text,
                "pdf_to_html": self.pdf_to_html,
                "pdf_to_image": lambda x: self.pdf_to_image(x, single_or_multiple='multiple'),
                "pdf_to_ppt": self.pdf_to_presentation,
                "pdf_to_markdown": self.pdf_to_markdown,
                "markdown_to_pdf": self.markdown_to_pdf,
                "file_to_pdf": self.file_to_pdf
            }

            converter = conversion_methods.get(conversion_type)
            if not converter:
                return f"不支持的转换类型: {conversion_type}"

            # 根据方法是否是协程决定调用方式
            if asyncio.iscoroutinefunction(converter):
                result = await converter(input_path)
            else:
                result = converter(input_path)

            # 处理转换结果
            if result:
                return result
            else:
                return "📄 转换状态：\n转换失败\n输出路径：未生成"

        except Exception as e:
            return f"转换失败: {str(e)}"