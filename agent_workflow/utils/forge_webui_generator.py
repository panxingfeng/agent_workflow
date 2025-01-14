import os
import time

import requests
from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config.tool_config import FORGE_SDWEBUI_PORT


class ForgeImageGenerator:
    def __init__(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        self.driver = webdriver.Chrome(options=options)

    def click_flux(self):
        wait = WebDriverWait(self.driver, 5)
        flux_radio = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'label[data-testid="flux-radio-label"] input[type="radio"]')))
        self.driver.execute_script("arguments[0].click();", flux_radio)
        time.sleep(0.5)

    def select_model(self, model_name):
        wait = WebDriverWait(self.driver, 5)
        input_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[role="listbox"]')))
        current_value = input_el.get_attribute("value")

        if model_name in current_value:
            return

        input_el.click()
        time.sleep(0.5)

        options = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'ul.options.svelte-y6qw75 li.item')))
        for option in options:
            if model_name in option.get_attribute('aria-label'):
                option.click()
                time.sleep(0.5)
                return
        time.sleep(0.5)
        raise Exception(f"未找到模型: {model_name}")

    def input_prompt(self, prompt_text):
        wait = WebDriverWait(self.driver, 10)
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, '.options.svelte-y6qw75')))

        textarea = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'textarea.scroll-hide')))
        self.driver.execute_script("""
           arguments[0].value = arguments[1];
           arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
       """, textarea, prompt_text)
        time.sleep(0.5)

    def select_sampling_method(self, method_name):
        wait = WebDriverWait(self.driver, 5)
        input_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[aria-label="Sampling method"]')))
        current_value = input_el.get_attribute("value")

        if method_name in current_value:
            return

        input_el.click()
        time.sleep(1)

        options = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'ul.options.svelte-y6qw75 li.item')))
        for option in options:
            if method_name == option.text.strip():
                option.click()
                time.sleep(0.5)
                return
        time.sleep(0.5)
        raise Exception(f"未找到采样方法: {method_name}")

    def input_steps(self, steps):
        if steps == 20:
            return

        wait = WebDriverWait(self.driver, 5)
        steps_input = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, 'div#txt2img_steps input[data-testid="number-input"]'
        )))
        self.driver.execute_script("arguments[0].value = arguments[1]", steps_input, steps)
        steps_input.send_keys(Keys.ENTER)

    def input_dimensions(self, width, height):
        if width == 896 and height == 1152:
            return

        wait = WebDriverWait(self.driver, 5)

        if width != 896:
            width_input = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, 'div#txt2img_width input[data-testid="number-input"]'
            )))
            self.driver.execute_script("arguments[0].value = arguments[1]", width_input, width)
            width_input.send_keys(Keys.ENTER)

        if height != 1152:
            height_input = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, 'div#txt2img_height input[data-testid="number-input"]'
            )))
            self.driver.execute_script("arguments[0].value = arguments[1]", height_input, height)
            height_input.send_keys(Keys.ENTER)

    def input_batch_values(self, batch_count, batch_size):
        wait = WebDriverWait(self.driver, 5)

        if batch_count != 1:
            batch_count_input = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, 'div#txt2img_batch_count input[data-testid="number-input"]'
            )))
            self.driver.execute_script("arguments[0].value = arguments[1]", batch_count_input, batch_count)
            batch_count_input.send_keys(Keys.ENTER)

        if batch_size != 1:
            batch_size_input = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, 'div#txt2img_batch_size input[data-testid="number-input"]'
            )))
            self.driver.execute_script("arguments[0].value = arguments[1]", batch_size_input, batch_size)
            batch_size_input.send_keys(Keys.ENTER)

    def input_cfg_scale(self, scale):
        if scale == 1:
            return

        wait = WebDriverWait(self.driver, 5)
        scale_input = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, 'div#txt2img_cfg_scale input[data-testid="number-input"]'
        )))
        self.driver.execute_script("arguments[0].value = arguments[1]", scale_input, scale)
        scale_input.send_keys(Keys.ENTER)

    def input_seed(self, seed):
        if seed == -1:
            return

        wait = WebDriverWait(self.driver, 5)
        seed_input = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, 'input[aria-label="Seed"]'
        )))
        self.driver.execute_script("arguments[0].value = arguments[1]", seed_input, seed)
        seed_input.send_keys(Keys.ENTER)

    def generate_image(self):
        wait = WebDriverWait(self.driver, 5)
        textarea = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'textarea.scroll-hide')))
        textarea.send_keys(Keys.CONTROL + Keys.ENTER)

    def wait_and_save_image(self, base_path):
        wait = WebDriverWait(self.driver, 300)

        img_path = os.path.join(base_path, "output/images")
        os.makedirs(img_path, exist_ok=True)

        img = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'img[data-testid="detailed-images"]')))
        img_url = img.get_attribute('src')
        info_text = self.driver.find_element(By.CSS_SELECTOR, 'div#html_info_txt2img').text
        filename = img_url.split('/')[-1]

        img_response = requests.get(img_url)
        with open(os.path.join(img_path, filename), 'wb') as f:
            f.write(img_response.content)

        final_path = os.path.join(img_path, filename)

        return final_path, info_text

    def run(self, prompt, model_name, sampling_method, steps, width, height, batch_count, batch_size, cfg_scale, seed):
        try:
            self.driver.get(f"http://localhost:{FORGE_SDWEBUI_PORT}/?__theme=dark")
            self.click_flux()
            self.select_model(model_name)
            self.input_prompt(prompt)
            self.select_sampling_method(sampling_method)
            self.input_steps(steps)
            self.input_dimensions(width, height)
            self.input_batch_values(batch_count, batch_size)
            self.input_cfg_scale(cfg_scale)
            self.input_seed(seed)
            self.generate_image()
            return self.wait_and_save_image(os.getcwd())
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.driver.quit()
