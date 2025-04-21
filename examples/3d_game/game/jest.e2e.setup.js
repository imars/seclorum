// jest.e2e.setup.js
import puppeteer from 'puppeteer';

let browser, page;

beforeAll(async () => {
  console.log('Launching Puppeteer browser');
  browser = await puppeteer.launch({
    headless: true,
    args: [
      '--enable-webgl',
      '--use-gl=desktop',
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-gpu-sandbox',
      '--enable-logging',
      '--disable-webgl=0', // Explicitly enable WebGL
      '--enable-accelerated-2d-canvas', // Ensure GPU acceleration
    ],
  });
  page = await browser.newPage();
  console.log('Puppeteer page created');

  // Debug WebGL support
  const webglSupport = await page.evaluate(() => {
    const canvas = document.createElement('canvas');
    const webgl1 = canvas.getContext('webgl');
    const webgl2 = canvas.getContext('webgl2');
    return {
      webgl1: !!webgl1,
      webgl1Version: webgl1 ? webgl1.getParameter(webgl1.VERSION) : 'N/A',
      webgl2: !!webgl2,
      webgl2Version: webgl2 ? webgl2.getParameter(webgl2.VERSION) : 'N/A',
    };
  });
  console.log('WebGL support in Puppeteer:', webglSupport);
});

afterAll(async () => {
  console.log('Closing Puppeteer browser');
  await browser.close();
  console.log('Puppeteer browser closed');
});

export { page };
