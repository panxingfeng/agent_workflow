#########################################  离线/本地的大模型信息  #########################################

CHATGPT_DATA = {
    'use': False,
    'model': 'gpt-4o-mini',  # 模型名称，GPT 模型的具体版本
    'key': '',  # 你的 OpenAI API 密钥
    'api_url': 'https://api.openai.com/v1',  # OpenAI API 的地址
    'temperature': 0.7,  # 生成内容的多样性程度，0-1 范围内
}

OLLAMA_DATA = {
    'use': True,
    'model': 'qwen2.5',  # ollama运行的模型名称
    'inference_model': 'qwen2.5',
    'code_model': 'qwen2.5',
    'embedding_model': 'bge-m3',
    'key': 'EMPTY',
    'url': 'http://localhost:11434/api/chat',  # 本地 Ollama 服务地址
    'api_url': "http://localhost:11434/v1/"
}

MOONSHOT_DATA = {
    'use': False,
    'key': "",
    'url': "https://api.moonshot.cn/v1",
    'model': "moonshot-v1-8k",
    "prompt": ""
}

BAICHUAN_DATA = {
    'use': False,
    'key': "",
    'url': "https://api.baichuan-ai.com/v1/",
    'model': "Baichuan2-Turbo"
    # 百川模型不支持自定义提示词内容#
}

#########################################  本地数据库信息  #########################################

# 本地mysql数据库信息
DB_DATA = {
    'host': 'localhost',  # 数据库地址
    'user': 'root',  # 数据库用户
    'password': '1234',  # 数据库密码
    'database': 'agent'  # 数据库名称
}

# redis信息
REDIS_DATA = {
    'host': 'localhost',
    'port': 6379,
    'db': 0
}

#########################################  wechat信息  #########################################

# 微信中的文件保存到本地的地址信息#
DOWNLOAD_ADDRESS = {
    'files': 'D:\\xxxx\\files',
    'vidio': 'D:\\xxxx\\vidio',
    'audio': 'D:\\xxxx\\audio',
    'images': 'D:\\xxxx\\images'
}

# 登录微信的基本信息
LOGIN_WECHAT_DATA = {
    "name": "xxx",  # 微信用户名（对方@xxx的xxx）
    "manner_name": ""  # 群管理人员信息
}

#########################################  feishu信息  #########################################

FEISHU_DATA = {
    "name": "智能体机器人",  # 机器人界面显示的名字
    "app_id": "",  # 应用凭证中的App ID
    "app_secret": "",  # 应用凭证中的App Secret
    "encrypt_key": "",  # 自建应用中的“事件与回调”下的加密策略中的Encrypt Key
    "tenant_access_token": ""  # 把main方法中的获取飞书tenant_access_token值打开后执行一次就可以获取到
}

#########################################  工具API信息  #########################################

GAODE_WEATHER_API_KEY = "" # 高德天气API

# sdwebui的api账户信息
FORGE_SDWEBUI_USERNAME = "*******"  # 模型包中的forge.exe启动器中的点开“高级选项”->“登录凭证管理”->“API鉴权-管理API 账号和密码”设置以后填入此处即可
FORGE_SDWEBUI_PASSWORD = "*******"

# 生图质量词
QUALITY_PROMPTS = """masterpiece, best quality, highly detailed, 8k uhd, perfect composition, professional lighting, high quality, ultra-detailed, sharp focus, high resolution, detailed, award winning, stunning, breathtaking, remarkable, beautiful, intricate details, ultra realistic, photorealistic quality, cinematic lighting, dramatic lighting, excellent composition"""
# 负面提示词
NEGATIVE_PROMPTS = "nsfw,"

# forge-sdwebui的端口信息
FORGE_SDWEBUI_PORT = 7862

# F5-TTS端口信息
F5_TTS_PORT = 7860

# GPT-SoVITS端口信息
GPT_SoVITS_PORT = 5000

# comfyui的端口信息
COMFYUI_PORT = 8188

# 前端ui的端口信息
UI_HOST = "localhost"
UI_PORT = 8000
# UI_PORT可以根据内网穿透指定的端口设置，
# 例如，指定的网址是：http://xxx.xxx.xx 内网穿透软件将本地的8000端口开放到http://xxx.xxx.xx使用 LOCAL_PORT_ADDRESS=http://xxx.xxx.xx
# 默认：http://localhost:8000
LOCAL_PORT_ADDRESS = "http://localhost:8000"

COMFYUI_PATH = "D:\BaiduNetdiskDownload\ComfyUI-aki-v1.4"  # comfyui文件的路径地址

COMFYUI_MODEL_PATH = "models\checkpoints" # 不需要修改

# forge默认模型
FORGE_MODEL = "xxxxx"  # 不用包含.safetensors

# comfyui默认模型
COMFYUI_MODEL = "dreamshaper.safetensors"  # 包含.safetensors

#########################################  其他信息  #########################################

# Perplexica中的ollama模型配置信息
SEARCH_TOOL_OLLAMA_CONFIG = {
    "provider": "ollama",
    "model": "qwen2.5:latest"
}
SEARCH_TOOL_EMBEDDING_CONFIG = {
    "provider": "ollama",
    "model": "bge-m3:latest"
}
