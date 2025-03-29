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
        time.sleep(1)

    def test_middle_column_alignment(self):
        modes = ['design', 'agent']
        for mode in modes:
            self.load_page(f"http://127.0.0.1:5000/chat?mode={mode}")
            logger.info(f"Testing initial alignment in {mode} mode")
            input_panel = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".middle-column .input-panel"))
            )
            viewport_height = self.driver.execute_script("return window.innerHeight")
            panel_rect = input_panel.rect
            panel_bottom = panel_rect['y'] + panel_rect['height']
            logger.info(f"{mode} mode initial: Viewport height={viewport_height}, Panel bottom={panel_bottom}")
            self.assertLessEqual(abs(viewport_height - panel_bottom), 100, f"Input panel not at bottom in {mode} mode")

            toggle_button = self.driver.find_element(By.XPATH, "//button[span[text()='Design' or text()='Agent']]")
            toggle_button.click()
            time.sleep(1)
            new_mode = 'agent' if mode == 'design' else 'design'
            logger.info(f"Testing alignment after switching to {new_mode} mode")
            input_panel = self.driver.find_element(By.CSS_SELECTOR, ".middle-column .input-panel")
            panel_rect = input_panel.rect
            panel_bottom = panel_rect['y'] + panel_rect['height']
            logger.info(f"{new_mode} mode after switch: Viewport height={viewport_height}, Panel bottom={panel_bottom}")
            self.assertLessEqual(abs(viewport_height - panel_bottom), 100, f"Input panel not at bottom after switch to {new_mode}")

    def test_textarea_resize_upward(self):
        self.load_page("http://127.0.0.1:5000/chat?mode=design")
        logger.info("Testing textarea resize upward")
        textarea = self.driver.find_element(By.NAME, "input")
        initial_height = textarea.size['height']
        self.driver.execute_script("arguments[0].value = 'Line1\\nLine2\\nLine3'; arguments[0].dispatchEvent(new Event('input'));", textarea)
        time.sleep(0.5)
        new_height = textarea.size['height']
        self.assertGreater(new_height, initial_height, "Textarea height did not increase")

    def test_additional_routes(self):
        pages = [
            ('dashboard', 'Dashboard'),
            ('settings', 'Settings'),
            ('favicon.ico', None)
        ]
        for page, expected_title in pages:
            self.load_page(f"http://127.0.0.1:5000/{page}")
            logger.info(f"Testing {page} page load")
            if expected_title:
                title = self.driver.find_element(By.TAG_NAME, "h1").text
                self.assertIn(expected_title, title, f"{page} page not loaded correctly")
            else:
                self.assertNotIn("404", self.driver.title, "Favicon returned 404")

    def test_navigation_links(self):
        pages = [
            ('dashboard', ['Back to Chat', 'Settings']),
            ('settings', ['Chat', 'Dashboard'])
        ]
        for page, link_texts in pages:
            self.load_page(f"http://127.0.0.1:5000/{page}?mode=design&task_id=master")
            logger.info(f"Testing navigation links on {page}")
            links = self.driver.find_elements(By.TAG_NAME, "a")
            found_texts = [link.text for link in links]
            for text in link_texts:
                self.assertIn(text, found_texts, f"{text} link missing on {page}")
            for link in links:
                href = link.get_attribute('href')
                self.assertTrue(href.startswith('http://127.0.0.1:5000/'), f"Invalid href on {page}: {href}")
                self.assertIn('mode=design', href, f"Mode not preserved in {page} link: {href}")
                self.assertIn('task_id=master', href, f"Task ID not preserved in {page} link: {href}")

        # Test delete task (assumes at least one task exists)
        self.load_page("http://127.0.0.1:5000/dashboard?mode=design&task_id=master")
        delete_buttons = self.driver.find_elements(By.CSS_SELECTOR, "form button[type='submit']")
        if delete_buttons:
            delete_buttons[0].click()
            WebDriverWait(self.driver, 5).until(
                EC.url_contains('/dashboard'),
                "Did not redirect to dashboard after delete"
            )
            logger.info("Delete task redirected successfully")

if __name__ == "__main__":
    unittest.main()
