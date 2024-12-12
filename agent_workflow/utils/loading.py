import logging
import sys
import time
from threading import Thread


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

def loadingInfo():
    logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    logger = logging.getLogger(__name__)
    return logger