#########################################  API信息  #########################################

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

#########################################  参数信息  #########################################
IMAGE_GEN_TOOL_DATA={
    "model_type":"comfyui", # 可选择comfyui、sdwebui_forge、flux、sd3
    "prompt_mode":"none" # 可选择rag、llm、none  可以选择none，参数优化会自动设置质量高的提示词
}

DESCRIPTION_IMAGE_TOOL_DATA={
    "model":"llama3.2-vision" # 可选择glm-edge-v-5b、OpenBMB/MiniCPM-V-2_6、llama3.2-vision 除了llama3.2的模型ollama支持，另外两个需要手动下载模型
}
