import unittest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestChatLayout(unittest.TestCase):
    def setUp(self):
        logger.info("Setting up test environment")
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--window-size=1200,720")
        options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        options.add_argument("--enable-logging")
        service = Service(executable_path='/usr/local/bin/chromedriver', log_path='chromedriver.log')
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_page_load_timeout(30)

    def tearDown(self):
        logger.info("Tearing down test environment")
        console_logs = self.driver.get_log('browser')
        logger.info("Browser console logs:")
        for log in console_logs:
            logger.info(log['message'])
        self.driver.quit()
        if os.path.exists('chromedriver.log'):
            with open('chromedriver.log', 'r') as f:
                logger.info("Last 10 lines of chromedriver.log:")
                logger.info('\n'.join(f.read().splitlines()[-10:]))

    def load_page(self, url):
        for attempt in range(3):
            try:
                logger.info(f"Loading {url}")
                self.driver.get(url)
                logger.info("Page loaded successfully")
                break
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed to load page: {e}")
                if attempt == 2:
                    raise
                time.sleep(2)
        time.sleep(1)  # Wait for page render

    def test_middle_column_alignment(self):
        modes = ['design', 'agent']
        for mode in modes:
            # Test initial load
            self.load_page(f"http://127.0.0.1:5000/chat?mode={mode}")
            logger.info(f"Testing initial alignment in {mode} mode")
            input_panel = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".middle-column .input-panel"))
            )
            viewport_height = self.driver.execute_script("return window.innerHeight")
            panel_rect = input_panel.rect
            panel_bottom = panel_rect['y'] + panel_rect['height']
            logger.info(f"{mode} mode initial: Viewport height={viewport_height}, Panel bottom={panel_bottom}")
            self.assertLessEqual(abs(viewport_height - panel_bottom), 100, f"Input panel not at bottom on initial load in {mode} mode")

            # Test mode switch
            toggle_button = self.driver.find_element(By.XPATH, "//button[span[text()='Design' or text()='Agent']]")
            toggle_button.click()
            time.sleep(1)  # Wait for mode switch
            new_mode = 'agent' if mode == 'design' else 'design'
            logger.info(f"Testing alignment after switching to {new_mode} mode")
            input_panel = self.driver.find_element(By.CSS_SELECTOR, ".middle-column .input-panel")
            panel_rect = input_panel.rect
            panel_bottom = panel_rect['y'] + panel_rect['height']
            logger.info(f"{new_mode} mode after switch: Viewport height={viewport_height}, Panel bottom={panel_bottom}")
            self.assertLessEqual(abs(viewport_height - panel_bottom), 100, f"Input panel not at bottom after mode switch to {new_mode}")

    def test_textarea_resize_upward(self):
        self.load_page("http://127.0.0.1:5000/chat?mode=design")
        logger.info("Testing textarea resize upward")
        textarea = self.driver.find_element(By.NAME, "input")
        initial_height = textarea.size['height']
        self.driver.execute_script("arguments[0].value = 'Line1\\nLine2\\nLine3'; arguments[0].dispatchEvent(new Event('input'));", textarea)
        time.sleep(0.5)
        new_height = textarea.size['height']
        self.assertGreater(new_height, initial_height, "Textarea height did not increase")

if __name__ == "__main__":
    unittest.main()
