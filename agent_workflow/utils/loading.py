import logging
import os
import sys
import time
from threading import Thread

import colorlog


class LoadingIndicator:
    def __init__(self, message="正在搜索"):
        self.message = message
        self.is_running = False
        self._thread = None

    def _animate(self):
        chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        i = 0
        while self.is_running:
            sys.stdout.write('\r' + self.message + ' ' + chars[i % len(chars)])
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1

    def start(self):
        self.is_running = True
        self._thread = Thread(target=self._animate)
        self._thread.start()

    def stop(self):
        self.is_running = False
        if self._thread is not None:
            self._thread.join()
        sys.stdout.write('\r' + ' ' * (len(self.message) + 10) + '\r')
        sys.stdout.flush()

# 配置带颜色的logging
def loadingInfo(name, level=logging.INFO, log_file='agent_workflow.log'):
    # 确保日志文件所在目录存在
    log_dir = os.path.dirname(os.path.abspath(log_file))
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = colorlog.getLogger(name)
    if not logger.handlers:
        # 控制台处理器（带颜色）
        console_handler = colorlog.StreamHandler()
        console_handler.setFormatter(colorlog.ColoredFormatter(
            '%(log_color)s%(message)s',
            log_colors={
                'INFO': 'cyan',  # 使用青色显示一般信息
                'SUCCESS': 'green',  # 使用绿色显示成功信息
                'WARNING': 'yellow',  # 使用黄色显示警告
                'ERROR': 'red',  # 使用红色显示错误
            }
        ))

        # 文件处理器（不带颜色）
        # FileHandler会自动创建不存在的日志文件
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(message)s'
        ))

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    logger.setLevel(level)
    logger.propagate = False
    return logger

