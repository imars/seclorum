import unittest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestFocusChat(unittest.TestCase):
    def setUp(self):
        logger.info("Setting up test environment")
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--window-size=1200,720")
        options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        options.add_argument("--enable-logging")  # Enable console logs
        options.add_argument("--log-level=0")  # Max verbosity
        service = Service(executable_path='/usr/local/bin/chromedriver', log_path='chromedriver.log')
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_page_load_timeout(30)
        self.load_page("http://127.0.0.1:5000/focus_chat?task_id=master")

    def tearDown(self):
        logger.info("Tearing down test environment")
        console_logs = self.driver.get_log('browser')
        logger.info("Browser console logs:")
        for log in console_logs:
            logger.info(log['message'])
        self.driver.quit()
        log_file = '/Users/ian/dev/projects/agents/local/app.log'
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logger.info("Last 10 lines of server log:")
                logger.info('\n'.join(f.read().splitlines()[-10:]))
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
        time.sleep(1)

    def test_history_updates(self):
        logger.info("Testing chat history updates")
        initial_entries = len(self.driver.find_elements(By.CSS_SELECTOR, ".chat-container > div:not(.flex-1)"))
        logger.info(f"Initial chat entries: {initial_entries}")
        textarea = self.driver.find_element(By.NAME, "input")
        textarea.send_keys("Test message")
        self.driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
        logger.info("Submitted 'Test message'")
        WebDriverWait(self.driver, 10).until(
            lambda driver: len(driver.find_elements(By.CSS_SELECTOR, ".chat-container > div:not(.flex-1)")) > initial_entries,
            "Chat history did not update after submission"
        )
        new_entries = len(self.driver.find_elements(By.CSS_SELECTOR, ".chat-container > div:not(.flex-1)"))
        logger.info(f"New chat entries: {new_entries}")
        self.assertGreater(new_entries, initial_entries, "Chat history did not update")

if __name__ == "__main__":
    unittest.main()
