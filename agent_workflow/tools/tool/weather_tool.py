# -*- coding: utf-8 -*-
"""
@file: weather_tool.py
@author: [PanXingFeng]
@contact: [1115005803@qq.com、canomiguelittle@gmail.com]
@date: 2024-11-23
@version: 1.0.0
@license: MIT License

@description:
天气查询工具

主要功能：
1. 基于高德地图API实现天气查询
2. 支持省市区三级行政区划查询
3. 智能地区名称识别和匹配
4. 结果格式化展示

技术特点：
1. 多级行政区划支持
2. 模糊匹配和复合地址解析
3. 完整的错误处理机制
4. 自定义输出格式化

Copyright (c) 2024 [PanXingFeng]
All rights reserved.
"""
import json
import re
import os
from enum import Enum
from typing import Optional, Tuple, List

import httpx
import requests
import pandas as pd
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

    def __init__(self, printInfo: bool = False,
                 location: str = None,
                 api_key: str = GAODE_WEATHER_API_KEY,
                 base_url: str = "https://restapi.amap.com/v3/weather/weatherInfo",
                 region_data_path: str = './config/citycode.xlsx',
                 timeout: float = 10.0):
        """
        初始化天气查询工具

        Args:
            printInfo: 是否打印详细信息
            location: 查询位置
            api_key: 高德地图API密钥
            base_url: API基础URL
            region_data_path: 区域编码数据文件路径
            timeout: 请求超时时间
        """
        self.api_key = api_key
        self.location = location
        self.printInfo = printInfo
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
                "location": {"type": "string", "description": "需要查询天气的城市"},
                "date": {"type": "string", "description": "查询天气的日期"}
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
            abs_file_path = os.path.abspath(file_path)

            # 检查文件存在性
            if not os.path.exists(abs_file_path):
                raise FileNotFoundError(f"区域数据文件不存在: {abs_file_path}")

            # 根据文件类型选择处理方式
            file_extension = os.path.splitext(abs_file_path)[1].lower()
            if file_extension == '.xlsx':
                self.df = pd.read_excel(abs_file_path, engine='openpyxl')
            elif file_extension == '.xls':
                self.df = pd.read_excel(abs_file_path, engine='xlrd')
            else:
                raise ValueError(f"不支持的文件格式: {file_extension}")

            # 验证数据完整性
            required_columns = ['adcode', '中文名']
            missing_columns = [col for col in required_columns if col not in self.df.columns]
            if missing_columns:
                raise ValueError(f"Excel文件缺少必要的列: {', '.join(missing_columns)}")

            # 数据预处理
            self.df['adcode'] = self.df['adcode'].astype(str)

            # 初始化区域代码列表
            self.province_codes = self.df[self.df['adcode'].str.endswith('0000')]['adcode'].tolist()
            self.city_codes = self.df[
                (self.df['adcode'].str.endswith('00')) &
                (~self.df['adcode'].str.endswith('0000'))
                ]['adcode'].tolist()

        except Exception as e:
            print(f"区域数据初始化错误：{str(e)}")
            raise

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

        匹配策略：
        1. 精确匹配
        2. 去后缀匹配
        3. 复合地址解析
        4. 模糊匹配
        """
        try:
            address = address.strip()

            # 1. 精确匹配
            direct_match = self.df[self.df['中文名'] == address]
            if len(direct_match) > 0:
                adcode = str(direct_match['adcode'].iloc[0])
                return adcode, direct_match['中文名'].iloc[0], self._get_administrative_level(adcode)

            # 2. 处理省略"区"字的情况
            district_match = self.df[self.df['中文名'].str.endswith('区')]['中文名'].tolist()
            for district in district_match:
                district_no_suffix = district.replace('区', '')
                if address == district_no_suffix:
                    result = self.df[self.df['中文名'] == district]
                    adcode = str(result['adcode'].iloc[0])
                    return adcode, district, self._get_administrative_level(adcode)

            # 3. 复合地址处理
            if len(address) > 3:
                city_matches = self.df[self.df['adcode'].astype(str).str.endswith('00')]['中文名']
                for city in city_matches:
                    if address.startswith(city.replace('市', '')):
                        remaining = address[len(city.replace('市', '')):].strip()
                        district_matches = self.df[
                            (self.df['中文名'].str.startswith(remaining)) &
                            (self.df['中文名'].str.endswith('区'))
                            ]
                        if len(district_matches) > 0:
                            adcode = str(district_matches['adcode'].iloc[0])
                            return adcode, district_matches['中文名'].iloc[0], AdministrativeLevel.DISTRICT

            # 4. 模糊匹配
            clean_address = re.sub(r'[市区县]', '', address)
            fuzzy_match = self.df[self.df['中文名'].str.contains(clean_address, na=False)]
            if len(fuzzy_match) > 0:
                # 优先匹配区县级
                district_result = fuzzy_match[fuzzy_match['adcode'].astype(str).str.endswith(r'\d{2}')]
                if len(district_result) > 0:
                    adcode = str(district_result['adcode'].iloc[0])
                    return adcode, district_result['中文名'].iloc[0], AdministrativeLevel.DISTRICT

                # 其次匹配市级
                city_result = fuzzy_match[fuzzy_match['adcode'].astype(str).str.endswith('00')]
                if len(city_result) > 0:
                    adcode = str(city_result['adcode'].iloc[0])
                    return adcode, city_result['中文名'].iloc[0], AdministrativeLevel.CITY

            return None, "", ""

        except Exception as e:
            print(f"区域编码查询错误：{str(e)}")
            return None, "", ""

    def _format_weather_display(self, weather_data: WeatherResponse) -> str:
        """格式化天气信息显示，实现右侧对齐"""
        # 定义常量
        width = 45  # 总宽度
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
                    if self.printInfo:
                        print(result)
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


    def get_parameter_rules(self) -> str:
        """返回天气工具的参数设置规则"""
        rules = """
        WeatherTool 需要设置:
        - location: 从用户查询中提取城市名称
          - 示例输入: "武汉今天天气怎么样？"
          - 参数设置: {"location": "武汉"}
          - 规则: 提取查询中的城市名，包括可能的区县名
        """
        return rules
