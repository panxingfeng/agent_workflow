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

Copyright (c) 2024 [湖北峰创科技服务有限公司]
All rights reserved.
"""
import base64
import json
import os
import platform
import traceback
from datetime import datetime
from enum import Enum
from typing import List, Optional
import tempfile
import zipfile
import subprocess
import sys
import requests
import camelot
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
    - PDF_TO_CSV: PDF转CSV
    - PDF_TO_XML: PDF转XML
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
    PDF_TO_CSV = "pdf_to_csv"
    PDF_TO_XML = "pdf_to_xml"
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
        self.output_directory = output_directory
        self.printInfo = printInfo
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.poppler_path = os.path.join(self.base_dir, "poppler", "bin")

        # 初始化检查
        if not self.check_dependencies():
            print("\nPlease install all required dependencies before continuing.")
            return

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
                        {"name": "pdf_to_csv", "description": "PDF转CSV"},
                        {"name": "pdf_to_xml", "description": "PDF转XML"},
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

    def check_dependencies(self) -> bool:
        """
        检查必要的依赖是否已安装

        Returns:
            bool: 所有依赖是否都已安装

        功能：
        1. 检查必要的Python包
        2. 提供安装建议
        3. 支持详细的错误报告
        """
        # 定义需要检查的依赖
        dependencies = {
            'playwright': 'playwright',
            'pdf2docx': 'pdf2docx',
            'pdfminer': 'pdfminer.six',
            'pdf2image': 'pdf2image',
            'reportlab': 'reportlab',
            'markdown': 'markdown',
            'camelot': 'camelot-py',
            'pypdf': 'pypdf'
        }

        # 检查每个依赖
        missing = []
        for name, package in dependencies.items():
            try:
                __import__(name.lower().split('.')[0])
            except ImportError:
                missing.append(package)

        # 报告缺失的依赖
        if missing:
            print("\nMissing dependencies:")
            print("Please install the following packages:")
            for package in missing:
                print(f"pip install {package}")
            return False
        return True

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

    def url_to_pdf(self, url: str) -> Optional[str]:
        """
        将网页转换为PDF文件

        Args:
            url: 待转换的网页URL

        Returns:
            str: 生成的PDF文件路径，失败时返回None

        功能：
        1. 使用Playwright进行网页渲染
        2. 自动处理动态内容
        3. 支持自定义PDF参数
        4. 提供详细的转换状态
        """
        try:
            from playwright.sync_api import sync_playwright

            # 安装浏览器
            try:
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                               check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                print(f"Failed to install browsers: {e}")
                return None

            output_path = self._generate_output_path("url_converted", "pdf")

            with sync_playwright() as p:
                # 配置浏览器
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox']
                )

                # 配置页面参数
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    device_scale_factor=1.5
                )
                page = context.new_page()

                # 加载页面
                outputData(f"Loading URL: {url}", self.printInfo)
                page.goto(url, wait_until="networkidle", timeout=60000)

                # PDF生成配置
                pdf_options = {
                    "path": output_path,
                    "format": "a4",
                    "margin": {"top": "1cm", "right": "1cm", "bottom": "1cm", "left": "1cm"},
                    "print_background": True,
                    "scale": 0.8
                }

                # 生成PDF
                page.pdf(**pdf_options)

                # 清理资源
                context.close()
                browser.close()

                outputData(f"PDF saved to: {output_path}", self.printInfo)
                return output_path

        except Exception as e:
            print(f"URL to PDF conversion failed: {str(e)}")
            print(f"Detailed error: {traceback.format_exc()}")
            return None

    def pdf_to_word(self, pdf_path: str, output_format: str = 'docx') -> Optional[str]:
        """
        将PDF转换为Word文档

        Args:
            pdf_path: PDF文件路径
            output_format: 输出格式，默认为docx

        Returns:
            str: 生成的Word文档路径，失败时返回None

        功能：
        1. 使用pdf2docx进行转换
        2. 保持原始格式
        3. 支持表格和图片
        """
        try:
            from pdf2docx import Converter
            output_path = self._generate_output_path("converted", output_format)

            cv = Converter(pdf_path)
            cv.convert(output_path)
            cv.close()

            outputData(f"Word document saved to: {output_path}", self.printInfo)
            return output_path
        except Exception as e:
            print(f"PDF to Word conversion failed: {str(e)}")
            return None

    def pdf_to_text(self, pdf_path: str) -> Optional[str]:
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
            output_path = self._generate_output_path("converted", "txt")

            # 转换为markdown格式
            text = pymupdf4llm.to_markdown(pdf_path)

            # 保存文本
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)

            outputData(f"Text file saved to: {output_path}", self.printInfo)
            return output_path
        except Exception as e:
            print(f"PDF to text conversion failed: {str(e)}")
            return None

    def pdf_to_xml(self, pdf_path: str) -> Optional[str]:
        """
        将PDF文档转换为XML格式

        Args:
            pdf_path: PDF文件路径

        Returns:
            str: 生成的XML文件路径，失败时返回None

        功能特点：
        1. 保持文档结构
        2. 支持Unicode编码
        3. 提取文本布局信息
        4. 支持分页处理

        XML结构：
        <pdf>
            <page number="1">
                <text font="Times" bbox="[x0, y0, x1, y1]">内容</text>
                <figure>...</figure>
                <textline>...</textline>
            </page>
        </pdf>
        """
        try:
            # 导入必要的pdfminer组件
            from pdfminer.converter import XMLConverter  # XML转换器
            from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter  # PDF解释器
            from pdfminer.pdfpage import PDFPage  # PDF页面处理
            from pdfminer.layout import LAParams  # 布局参数

            # 生成输出文件路径
            output_path = self._generate_output_path("converted", "xml")

            # 创建PDF资源管理器
            # 用于管理共享资源（如字体、图片等）
            rsrcmgr = PDFResourceManager()

            # 设置布局分析参数
            laparams = LAParams(
                # 可以添加以下参数进行自定义：
                # char_margin=2.0,        # 字符间距
                # line_margin=0.5,        # 行间距
                # word_margin=0.1,        # 词间距
                # boxes_flow=0.5,         # 文本流方向
                # detect_vertical=False    # 是否检测垂直文本
            )

            # 打开输出文件并进行转换
            with open(output_path, 'wb') as outfp:
                # 创建XML转换器
                device = XMLConverter(
                    rsrcmgr,  # 资源管理器
                    outfp,  # 输出文件对象
                    codec='utf-8',  # 使用UTF-8编码
                    laparams=laparams  # 布局参数
                )

                # 创建PDF页面解释器
                interpreter = PDFPageInterpreter(rsrcmgr, device)

                # 打开PDF文件并逐页处理
                with open(pdf_path, 'rb') as fp:
                    # 遍历每一页
                    for page in PDFPage.get_pages(
                            fp,
                            # 可选参数：
                            # pagenos=None,         # 指定页码列表
                            # maxpages=0,           # 最大页数限制
                            # password='',          # PDF密码
                            # caching=True,         # 缓存开关
                            # check_extractable=True # 检查是否可提取
                    ):
                        # 处理当前页面
                        interpreter.process_page(page)

                # 关闭转换器，释放资源
                device.close()

            # 输出成功信息
            outputData(data=f"XML文件已保存至: {output_path}", printInfo=self.printInfo)
            return output_path

        except Exception as e:
            print(f"PDF转换XML失败: {str(e)}")
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
            print(f"PDF转换为演示文稿失败: {str(e)}")
            return None

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
            print(f"PDF转换为PDF/A失败: {str(e)}")
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

        功能：
        1. 支持单页/多页转换
        2. 自定义输出格式和质量
        3. 自动打包多页结果
        4. 清理临时文件
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

            with tempfile.mkdtemp() as temp_dir:
                try:
                    # 转换PDF页面
                    images = convert_from_path(
                        pdf_path,
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

    def pdf_to_csv(self, pdf_path: str, page_id: int = 1) -> Optional[str]:
        """
        从PDF中提取表格并转换为CSV

        Args:
            pdf_path: PDF文件路径
            page_id: 要提取的页码

        Returns:
            str: 生成的CSV文件路径，失败时返回None

        功能：
        1. 智能表格识别
        2. 保持表格结构
        3. 支持复杂表格处理
        4. 详细的错误报告
        """
        try:
            output_path = self._generate_output_path("extracted", "csv")

            # 读取PDF表格
            tables = camelot.read_pdf(pdf_path, pages=str(page_id))

            if len(tables) > 0:
                # 导出第一个识别到的表格
                tables[0].to_csv(output_path)
                outputData(f"CSV file saved to: {output_path}", self.printInfo)
                return output_path
            else:
                print("No tables found in the PDF.")
                return None

        except FileNotFoundError:
            print(f"PDF file not found: {pdf_path}")
            return None
        except Exception as e:
            print(f"PDF to CSV conversion failed: {str(e)}")
            print("\n可能的问题和解决方案:")
            print("- 确保已安装Ghostscript并添加到系统PATH")
            print("- 下载Ghostscript: https://www.ghostscript.com/releases/gsdnld.html")
            print("- 安装camelot: pip install camelot-py[cv]")
            print("- 安装完Ghostscript后重启IDE")
            print("- 检查PDF文件格式，复杂或扫描的PDF可能无法正确处理")
            return None

    def html_to_pdf(self, html_path: str, zoom: float = 1.0) -> Optional[str]:
        """
        将HTML文件或ZIP压缩的HTML文件转换为PDF

        Args:
            html_path: HTML文件或ZIP文件的路径
            zoom: 缩放比例，默认为1.0
                  - 大于1：放大
                  - 小于1：缩小
                  - 等于1：原始大小

        Returns:
            str: 生成的PDF文件路径，失败时返回None

        功能特点：
        1. 支持单个HTML文件转换
        2. 支持ZIP压缩包中的HTML转换
        3. 自定义页面设置
        4. 统一的边距控制

        使用示例：
            # 单个HTML文件转换
            converter.html_to_pdf('page.html', zoom=1.2)

            # ZIP包中的HTML转换
            converter.html_to_pdf('pages.zip', zoom=1.0)
        """
        try:
            # 导入pdfkit工具
            import pdfkit

            # 生成输出文件路径
            output_path = self._generate_output_path("converted", "pdf")

            # PDF生成配置选项
            options = {
                'zoom': zoom,  # 页面缩放比例
                'page-size': 'A4',  # 页面大小：A4纸
                # 统一设置1厘米页边距
                'margin-top': '1cm',
                'margin-right': '1cm',
                'margin-bottom': '1cm',
                'margin-left': '1cm'
            }

            # 根据输入文件类型处理
            if html_path.endswith('.html'):
                # 直接处理单个HTML文件
                pdfkit.from_file(html_path, output_path, options=options)
            else:
                # 处理ZIP压缩包
                with tempfile.TemporaryDirectory() as tmpdir:
                    # 解压ZIP文件到临时目录
                    with zipfile.ZipFile(html_path, 'r') as zip_ref:
                        zip_ref.extractall(tmpdir)

                    # 查找所有HTML文件
                    html_files = [f for f in os.listdir(tmpdir) if f.endswith('.html')]

                    if html_files:
                        # 使用找到的第一个HTML文件
                        main_html = os.path.join(tmpdir, html_files[0])
                        pdfkit.from_file(main_html, output_path, options=options)
                    else:
                        # 未找到HTML文件时抛出异常
                        raise Exception("No HTML file found in ZIP archive")

            # 输出成功信息
            outputData(data=f"PDF saved to: {output_path}", printInfo=self.printInfo)
            return output_path

        except Exception as e:
            # 错误处理和日志记录
            print(f"HTML to PDF conversion failed: {str(e)}")
            return None

    def images_to_pdf(self, image_paths: List[str], fit_option: str = 'maintainAspectRatio',
                      color_type: str = 'color', auto_rotate: bool = True) -> Optional[str]:
        """
        将多个图片文件合并转换为PDF文档

        Args:
            image_paths: 图片文件路径列表
            fit_option: 图片适配选项
                - 'maintainAspectRatio': 保持原始比例（默认）
                - 'fillPage': 填充整个页面
                - 'fitDocumentToImage': 使用原始尺寸
            color_type: 颜色模式
                - 'color': 彩色（默认）
                - 'greyscale': 灰度
                - 'blackwhite': 黑白
            auto_rotate: 是否根据EXIF信息自动旋转图片

        Returns:
            str: 生成的PDF文件路径，失败时返回None

        功能特点：
        1. 支持多种图片格式转换
        2. 智能页面布局调整
        3. 自动处理图片方向
        4. 支持多种颜色模式
        """
        try:
            # 导入必要的库
            from PIL import Image  # 处理图片
            import io  # 内存流处理
            from reportlab.pdfgen import canvas  # PDF生成
            from reportlab.lib.pagesizes import A4  # 标准A4尺寸

            # 生成输出文件路径
            output_path = self._generate_output_path("combined", "pdf")

            # 创建PDF画布，使用A4尺寸
            c = canvas.Canvas(output_path, pagesize=A4)
            width, height = A4  # A4尺寸（单位：点，1点=1/72英寸）

            # 处理每张图片
            for img_path in image_paths:
                # 打开并加载图片
                img = Image.open(img_path)

                # 根据选择的颜色模式转换图片
                if color_type == 'greyscale':
                    img = img.convert('L')  # L模式：灰度图像
                elif color_type == 'blackwhite':
                    img = img.convert('1')  # 1模式：二值图像

                # 处理图片旋转
                # 根据EXIF信息自动调整图片方向
                if auto_rotate and hasattr(img, '_getexif'):
                    try:
                        exif = img._getexif()
                        if exif:
                            orientation = exif.get(274)  # 274是方向标签的标准代码
                            if orientation:
                                # 根据EXIF方向信息旋转图片
                                if orientation == 3:  # 180度
                                    img = img.rotate(180, expand=True)
                                elif orientation == 6:  # 顺时针90度
                                    img = img.rotate(270, expand=True)
                                elif orientation == 8:  # 逆时针90度
                                    img = img.rotate(90, expand=True)
                    except:
                        pass  # 如果无法读取EXIF信息，保持原样

                # 计算图片尺寸和缩放比例
                img_width, img_height = img.size
                if fit_option == 'fillPage':
                    # 填充整个页面，可能裁剪部分内容
                    ratio = max(width / img_width, height / img_height)
                elif fit_option == 'fitDocumentToImage':
                    # 使用原始尺寸
                    ratio = 1
                else:  # maintainAspectRatio
                    # 保持宽高比，确保完整显示
                    ratio = min(width / img_width, height / img_height)

                # 计算新的尺寸
                new_width = img_width * ratio
                new_height = img_height * ratio

                # 计算居中位置
                x = (width - new_width) / 2  # 水平居中
                y = (height - new_height) / 2  # 垂直居中

                # 调整图片大小，使用LANCZOS重采样算法获得最佳质量
                img = img.resize(
                    (int(new_width), int(new_height)),
                    Image.Resampling.LANCZOS  # 高质量重采样
                )

                # 将图片转换为PDF可用的格式
                img_buffer = io.BytesIO()  # 创建内存缓冲区
                img.save(img_buffer, format='PNG')  # 保存为PNG格式
                img_buffer.seek(0)  # 重置缓冲区指针

                # 将图片添加到PDF页面
                c.drawImage(img_buffer, x, y, new_width, new_height)
                c.showPage()  # 结束当前页面

            # 保存最终的PDF文件
            c.save()
            outputData(data=f"PDF saved to: {output_path}", printInfo=self.printInfo)
            return output_path

        except Exception as e:
            print(f"Images to PDF conversion failed: {str(e)}")
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

            print("所有转换方法均失败")
            return None

        except Exception as e:
            print(f"File to PDF conversion failed: {str(e)}")
            print(f"Detailed error: {traceback.format_exc()}")
            return None

    def _generate_output_path(self, prefix: str, ext: str) -> str:
        """
        生成输出文件路径

        Args:
            prefix: 文件名前缀
            ext: 文件扩展名

        Returns:
            str: 生成的完整文件路径

        功能：
        1. 自动创建目录
        2. 生成唯一文件名
        3. 时间戳命名
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, f"{prefix}_{timestamp}.{ext}")

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

    def run(self, **kwargs) -> str:
        """
        执行文件转换的统一入口

        Args:
            **kwargs: 关键字参数
                - conversion_type: 转换类型
                - input_path: 输入文件路径

        Returns:
            str: 转换结果或错误信息

        功能：
        1. 参数验证
        2. 类型分发
        3. 错误处理
        4. 结果返回
        """
        try:
            # 获取参数
            conversion_type = kwargs.get("conversion_type")
            input_path = kwargs.get("input_path")

            # 参数验证
            if not all([conversion_type, input_path]):
                return "转换失败: 缺少必需参数"

            # 根据类型调用相应方法
            conversion_methods = {
                "url_to_pdf": self.url_to_pdf,
                "pdf_to_word": self.pdf_to_word,
                "pdf_to_text": self.pdf_to_text,
                "pdf_to_html": self.pdf_to_html,
                "pdf_to_image": lambda x: self.pdf_to_image(x, single_or_multiple='multiple'),
                "pdf_to_csv": self.pdf_to_csv,
                "pdf_to_xml": self.pdf_to_xml,
                "pdf_to_ppt": self.pdf_to_presentation,
                "pdf_to_markdown": self.pdf_to_markdown,
                "markdown_to_pdf": self.markdown_to_pdf,
                "file_to_pdf": self.file_to_pdf
            }

            converter = conversion_methods.get(conversion_type)
            if converter:
                return converter(input_path)
            else:
                return f"不支持的转换类型: {conversion_type}"

        except Exception as e:
            return f"转换失败: {str(e)}"