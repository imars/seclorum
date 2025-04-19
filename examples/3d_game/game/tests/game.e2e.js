// tests/game.e2e.js
import puppeteer from 'puppeteer';

describe('Drone Game E2E', () => {
  beforeEach(async () => {
    await page.goto('http://localhost:8080');
    await page.waitForSelector('#gameCanvas', { timeout: 5000 });
  });

  test('initializes game and UI', async () => {
    const canvas = await page.$('#gameCanvas');
    expect(canvas).not.toBeNull();

    const ui = await page.$('#ui');
    expect(ui).not.toBeNull();

    const timer = await page.$eval('#timer', (el) => el.textContent);
    expect(timer).toBe('0.0');

    const speed = await page.$eval('#speed', (el) => el.textContent);
    expect(speed).toBe('0.0');
  });

  test('starts race on button click', async () => {
    await page.click('#startReset');
    await page.waitForFunction('parseFloat(document.querySelector("#timer").textContent) > 0', { timeout: 5000 });

    const timer = await page.$eval('#timer', (el) => el.textContent);
    expect(parseFloat(timer)).toBeGreaterThan(0);

    const standings = await page.$eval('#standings table', (el) => el.textContent);
    expect(standings).toContain('Drone 1');
  });

  test('moves player drone with mouse', async () => {
    await page.click('#startReset');
    await page.waitForFunction('parseFloat(document.querySelector("#timer").textContent) > 0', { timeout: 5000 });

    await page.mouse.move(100, 100, { steps: 10 });
    await page.waitForTimeout(500);

    const speed = await page.$eval('#speed', (el) => el.textContent);
    expect(parseFloat(speed)).toBeGreaterThan(0);
  });

  test('captures screenshot of game', async () => {
    await page.click('#startReset');
    await page.waitForFunction('parseFloat(document.querySelector("#timer").textContent) > 0', { timeout: 5000 });
    await page.screenshot({ path: 'screenshots/game.png' });
    expect(true).toBe(true); // Placeholder for visual validation
  });
});
