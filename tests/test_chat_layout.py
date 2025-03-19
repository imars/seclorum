import unittest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestChatLayout(unittest.TestCase):
    def setUp(self):
        logger.info("Setting up test environment")
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--window-size=1200,720")
        options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        service = Service(executable_path='/usr/local/bin/chromedriver')
        logger.info("Initializing ChromeDriver")
        self.driver = webdriver.Chrome(service=service, options=options)
        logger.info("ChromeDriver initialized, setting timeout")
        self.driver.set_page_load_timeout(30)
        for attempt in range(3):
            try:
                logger.info("Loading page")
                self.driver.get("http://127.0.0.1:5000/chat?mode=user")
                logger.info("Page loaded successfully")
                logger.info("Page title: " + self.driver.title)
                break
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed to load page: {e}")
                if attempt == 2:
                    raise
                time.sleep(2)
        time.sleep(1)

    def tearDown(self):
        logger.info("Tearing down test environment")
        self.driver.quit()

    def test_textarea_resize_upward(self):
        logger.info("Testing textarea resize upward")
        textarea = self.driver.find_element(By.NAME, "input")
        initial_height = textarea.size['height']
        self.driver.execute_script("arguments[0].value = 'Line1\\nLine2\\nLine3'; arguments[0].dispatchEvent(new Event('input'));", textarea)
        time.sleep(0.5)
        new_height = textarea.size['height']
        self.assertGreater(new_height, initial_height, "Textarea height did not increase")

    def test_column_widths(self):
        logger.info("Testing column widths")
        # User mode
        columns = self.driver.find_elements(By.CSS_SELECTOR, ".columns-container > div")
        logger.info(f"Found {len(columns)} columns in user mode")
        logger.info(f"User mode viewport width: {self.driver.execute_script('return window.innerWidth')}")
        widths = [col.size['width'] for col in columns]
        logger.info(f"User mode widths: {widths}")
        self.assertEqual(len(columns), 3, "Expected 3 columns in user mode")
        self.assertEqual(len(set(widths)), 1, "Columns are not equal width in user mode")
        
        # Agent mode with pre-set selectedAgent
        self.driver.execute_script("localStorage.setItem('selectedAgent', 'master');")
        self.driver.get("http://127.0.0.1:5000/chat?mode=agent")
        WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".agent-output strong"))
        )
        # Wait for stretch to settle
        WebDriverWait(self.driver, 5).until(
            lambda driver: all(col.size['width'] >= 270 for col in driver.find_elements(By.CSS_SELECTOR, ".columns-container > div"))
        )
        columns_agent = self.driver.find_elements(By.CSS_SELECTOR, ".columns-container > div")
        logger.info(f"Found {len(columns_agent)} columns in agent mode")
        logger.info(f"Agent mode viewport width: {self.driver.execute_script('return window.innerWidth')}")
        widths_agent = [col.size['width'] for col in columns_agent]
        logger.info(f"Agent mode widths: {widths_agent}")
        self.assertEqual(len(columns_agent), 3, "Expected 3 columns in agent mode")
        self.assertEqual(widths, widths_agent, "Column widths differ between modes")

    def test_ui_elements_on_screen(self):
        logger.info("Testing UI elements visibility")
        viewport_height = self.driver.execute_script("return window.innerHeight")
        history = self.driver.find_element(By.CSS_SELECTOR, ".history-container")
        input_area = self.driver.find_element(By.CSS_SELECTOR, ".input-container")
        footer = self.driver.find_element(By.TAG_NAME, "footer")
        self.assertLess(history.location['y'] + history.size['height'], viewport_height, "History overflows viewport")
        self.assertLess(input_area.location['y'] + input_area.size['height'], viewport_height, "Input area overflows viewport")
        self.assertLess(footer.location['y'] + footer.size['height'], viewport_height, "Footer overflows viewport")

if __name__ == "__main__":
    unittest.main()
