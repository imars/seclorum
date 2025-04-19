// jest.e2e.setup.js
import puppeteer from 'puppeteer';

let browser;
let page;

beforeAll(async () => {
  browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'], // For CI compatibility
  });
  page = await browser.newPage();
});

afterAll(async () => {
  await browser.close();
});

global.browser = browser;
global.page = page;
