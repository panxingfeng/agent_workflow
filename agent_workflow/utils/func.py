import asyncio
import logging
import os
import random
import re
import string

from agent_workflow.utils.loading import loadingInfo


def create_event_loop():
    """创建并配置事件循环"""
    if os.name == 'nt':  # Windows平台
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop


def asyncio_run(demo):
    logger = loadingInfo("asyncio_run")
    loop = create_event_loop()
    try:
        loop.run_until_complete(demo)
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行错误: {e}", exc_info=True)
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as e:
            logger.error(f"清理任务时出错: {e}", exc_info=True)
        finally:
            loop.close()
            logger.info("程序已关闭")


def get_url(message):
    try:
        start = message.find("(") + 1
        end = message.find(")")
        if start == 0 or end == -1 or start >= end:
            raise ValueError("未找到有效的 URL 或格式不正确")

        link = message[start:end]

        # 简单的 URL 验证，可以检查前缀
        if not (link.startswith("http://") or link.startswith("https://")):
            raise ValueError("提取的链接不是有效的 URL")

        return link

    except Exception as e:
        print(f"提取 URL 失败: {e}")
        return None  # 返回 None 或其他默认值


async def generate_random_filename(extension=".png", length=10):
    """生成随机文件名，并确保返回的是字符串"""
    try:
        # 生成随机字符的列表（字母和数字）
        characters = string.ascii_letters + string.digits

        # 生成随机文件名
        file_name = ''.join(random.choice(characters) for _ in range(length)) + extension

        # 使用 str() 确保返回的是字符串
        return str(file_name)
    except Exception as e:
        logging.error(f"生成文件名时出错: {e}")
        return None  # 出错时返回 None


def get_username_chatroom(message):
    """从消息中提取并返回 'in' 之前和 'ber' 之后内容的交集。"""
    match_before_in = re.search(r"^(.*?) in", message)
    content_before_in = match_before_in.group(1).strip() if match_before_in else ''

    match_after_ber = re.search(r"ber(.*?)(?=>>)", message)
    content_after_ber = match_after_ber.group(1).strip() if match_after_ber else ''

    words_before_in = set(content_before_in.split())
    words_after_ber = set(content_after_ber.split())

    intersection = words_before_in & words_after_ber

    return ' '.join(intersection)
