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
import json
import os
from enum import Enum
from typing import Optional, Tuple, List

import httpx
from pydantic import BaseModel, Field

from config.config import GAODE_WEATHER_API_KEY
from agent_workflow.tools.tool.base import BaseTool


class WeatherResponse(BaseModel):
    """
    天气响应数据模型

    属性：
        province: 省份名称
        city: 城市名称
        adcode: 区域编码
        weather: 天气状况
        temperature: 温度
        winddirection: 风向
        windpower: 风力
        humidity: 湿度
        reporttime: 发布时间
        administrative_level: 行政级别
        matched_region: 匹配到的地区
    """
    province: str = Field(..., description="省份")
    city: str = Field(..., description="城市")
    adcode: str = Field(..., description="区域编码")
    weather: str = Field(..., description="天气状况")
    temperature: str = Field(..., description="温度")
    winddirection: str = Field(..., description="风向")
    windpower: str = Field(..., description="风力")
    humidity: str = Field(..., description="湿度")
    reporttime: str = Field(..., description="发布时间")
    administrative_level: str = Field(..., description="行政级别")
    matched_region: str = Field(..., description="匹配到的地区")


class AdministrativeLevel(str, Enum):
    """
    行政区划等级枚举

    等级类型：
    - PROVINCE: 省级
    - CITY: 市级
    - DISTRICT: 区县级
    """
    PROVINCE = "province"
    CITY = "city"
    DISTRICT = "district"

    @classmethod
    def list_levels(cls) -> List[str]:
        """获取所有行政级别列表"""
        return [level.value for level in cls]


class WeatherTool(BaseTool):
    """
    天气查询工具类

    功能：
    1. 精确的地区匹配
    2. 多级行政区划支持
    3. 实时天气查询
    4. 格式化结果展示

    属性：
        api_key: 高德地图API密钥
        location: 查询位置
        printInfo: 是否打印详细信息
        base_url: API基础URL
        timeout: 请求超时时间
        df: 区域编码数据表
    """

    def __init__(self, location: str = None,
                 api_key: str = GAODE_WEATHER_API_KEY,
                 base_url: str = "https://restapi.amap.com/v3/weather/weatherInfo",
                 region_data_path: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "config", "citycode.xlsx"),
                 timeout: float = 10.0):
        """
        初始化天气查询工具

        Args:
            location: 查询位置
            api_key: 高德地图API密钥
            base_url: API基础URL
            region_data_path: 区域编码数据文件路径
            timeout: 请求超时时间
        """
        self.api_key = api_key
        self.location = location
        self.base_url = base_url
        self.timeout = timeout
        self._init_region_lookup(region_data_path)


    def get_description(self):
        """
        返回工具的描述信息，包括名称、功能和所需参数。
        """
        tool_info = {
            "name": "WeatherTool",
            "description": "查询天气的工具",
            "parameters": {
                "location": {"type": "string", "description": "需要查询天气的城市"}
            }
        }
        return json.dumps(tool_info, ensure_ascii=False)


    def _init_region_lookup(self, file_path: str) -> None:
        """
        初始化区域数据查询表

        Args:
            file_path: Excel文件路径

        功能：
        1. 加载区域编码数据
        2. 数据预处理
        3. 建立查询索引

        异常处理：
        - 文件不存在
        - 格式不支持
        - 数据不完整
        """
        try:
            # 使用绝对路径
            abs_file_path = os.path.abspath(file_path)

            # 使用 list 存储数据
            self.region_data = []

            # 直接使用 openpyxl 读取
            import openpyxl
            wb = openpyxl.load_workbook(abs_file_path)
            ws = wb.active

            # 创建一个简单的数据结构来存储数据
            self.region_lookup = {}

            # 跳过表头，直接读取数据
            for row in list(ws.rows)[1:]:  # 跳过表头
                chinese_name = str(row[0].value)
                adcode = str(row[1].value)
                if chinese_name and adcode:
                    self.region_lookup[chinese_name] = {
                        'adcode': adcode,
                        'citycode': str(row[2].value) if row[2].value else ''
                    }

            # 初始化区域代码列表
            self.province_codes = []
            self.city_codes = []

            # 分类处理区域代码
            for adcode in [info['adcode'] for info in self.region_lookup.values()]:
                if adcode.endswith('0000'):
                    self.province_codes.append(adcode)
                elif adcode.endswith('00'):
                    self.city_codes.append(adcode)

        except Exception as e:
            print(f"区域数据初始化错误：{str(e)}")
            # 创建空的数据结构
            self.region_lookup = {}
            self.province_codes = []
            self.city_codes = []

    def _get_administrative_level(self, adcode: str) -> str:
        """判断行政区划等级"""
        if str(adcode).endswith('0000'):
            return AdministrativeLevel.PROVINCE
        elif str(adcode).endswith('00'):
            return AdministrativeLevel.CITY
        else:
            return AdministrativeLevel.DISTRICT

    def _get_adcode(self, address: str) -> Tuple[Optional[str], str, str]:
        """
        获取地址的行政区划代码

        Args:
            address: 地址名称

        Returns:
            Tuple[str, str, str]: (区域代码, 匹配地区名, 行政级别)
        """
        try:
            address = address.strip()

            # 预处理地址：处理可能的后缀
            clean_address = address.replace('市', '').replace('区', '').replace('县', '')

            # 1. 精确匹配（包括处理带"市"和不带"市"的情况）
            if address in self.region_lookup:
                adcode = self.region_lookup[address]['adcode']
                return adcode, address, self._get_administrative_level(adcode)

            # 尝试带"市"的匹配
            if address + "市" in self.region_lookup:
                full_name = address + "市"
                adcode = self.region_lookup[full_name]['adcode']
                return adcode, full_name, self._get_administrative_level(adcode)

            # 2. 模糊匹配城市名
            for region_name, info in self.region_lookup.items():
                # 处理直辖市和普通城市
                if clean_address in region_name.replace('市', ''):
                    if info['adcode'].endswith('0000'):  # 省级或直辖市
                        return info['adcode'], region_name, AdministrativeLevel.PROVINCE
                    elif info['adcode'].endswith('00'):  # 地级市
                        return info['adcode'], region_name, AdministrativeLevel.CITY

            # 3. 区县级匹配
            if len(address) > 2:  # 确保地址名足够长
                for region_name, info in self.region_lookup.items():
                    if (not info['adcode'].endswith('00') and  # 不是市级
                            clean_address in region_name):  # 包含区名
                        return info['adcode'], region_name, AdministrativeLevel.DISTRICT

            return None, "", ""

        except Exception as e:
            print(f"区域编码查询错误：{str(e)}")
            return None, "", ""

    def _format_weather_display(self, weather_data: WeatherResponse) -> str:
        """格式化天气信息显示，实现右侧对齐"""
        # 定义常量
        width = 20  # 总宽度
        border = "=" * width

        def format_line(icon: str, label: str, value: str) -> str:
            """格式化单行内容，确保右侧对齐"""
            content = f"{icon} {label}: {value}"
            return f"{content}"

        return f"""\
{border}
                 {weather_data.matched_region}天气信息
{border}
{format_line("📍", "位置", f"{weather_data.province} {weather_data.city} ({weather_data.administrative_level})")}
{format_line("🌤", "天气", weather_data.weather)}
{format_line("🌡", "温度", f"{weather_data.temperature}")}
{format_line("💨", "风向", weather_data.winddirection)}
{format_line("💪", "风力", weather_data.windpower)}
{format_line("💧", "湿度", weather_data.humidity)}
{format_line("🕒", "发布时间", weather_data.reporttime)}
{border}"""

    async def query_weather(self) -> str:
        """
        查询指定地点的天气信息

        功能流程：
        1. 获取地区编码
        2. 调用天气API
        3. 解析返回数据
        4. 格式化展示结果

        Returns:
            str: 格式化的天气信息
        """
        try:
            adcode, matched_name, level = self._get_adcode(self.location)
            if not adcode:
                return f"未找到{self.location}的区域编码"

            params = {
                "city": adcode,
                "key": self.api_key
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.base_url, params=params)

            if response.status_code == 200:
                data = response.json()
                if data["status"] == "1" and data["info"] == "OK" and data["lives"]:
                    weather_data = WeatherResponse(
                        province=data["lives"][0]["province"],
                        city=data["lives"][0]["city"],
                        adcode=data["lives"][0]["adcode"],
                        weather=data["lives"][0]["weather"],
                        temperature=f"{data['lives'][0]['temperature_float']}℃",
                        winddirection=data["lives"][0]["winddirection"],
                        windpower=data["lives"][0]["windpower"],
                        humidity=f"{data['lives'][0]['humidity_float']}%",
                        reporttime=data["lives"][0]["reporttime"],
                        administrative_level=level,
                        matched_region=matched_name
                    )
                    result = self._format_weather_display(weather_data)
                    return result

            return "获取天气信息失败"

        except Exception as e:
            return f"天气查询失败：{str(e)}"

    async def run(self, **kwargs) -> str:
        """
        工具执行入口

        Args:
            **kwargs: 包含location的参数字典

        Returns:
            str: 查询结果或错误信息
        """
        self.location = kwargs.get('location', self.location)
        if not self.location:
            return "错误：未提供位置参数"
        return await self.query_weather()
