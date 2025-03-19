from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting Selenium test")
options = Options()
options.add_argument("--headless")
options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
service = Service(executable_path='/usr/local/bin/chromedriver')
logger.info("Initializing ChromeDriver with explicit path")
driver = webdriver.Chrome(service=service, options=options)
logger.info("ChromeDriver initialized")
driver.get("https://www.google.com")
logger.info("Page loaded: " + driver.title)
driver.quit()
logger.info("Test complete")
