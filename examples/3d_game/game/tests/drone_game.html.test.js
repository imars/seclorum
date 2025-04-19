const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

describe('Drone Game UI', () => {
  let dom, document;

  beforeEach(() => {
    const html = fs.readFileSync(path.resolve(__dirname, '../public/index.html'), 'utf8');
    dom = new JSDOM(html, { runScripts: 'outside-only', resources: 'usable' });
    document = dom.window.document;
    global.window = dom.window; // Ensure global.window is set

    // Inject CSS for testing
    const style = document.createElement('style');
    style.textContent = fs.readFileSync(path.resolve(__dirname, '../src/styles.css'), 'utf8');
    document.head.appendChild(style);

    // Wait for DOM to be ready
    return new Promise((resolve) => dom.window.addEventListener('load', resolve));
  });

  test('includes required UI elements', () => {
    expect(document.getElementById('gameCanvas')).toBeTruthy();
    expect(document.getElementById('ui')).toBeTruthy();
    expect(document.getElementById('startReset')).toBeTruthy();
  });

  test('styles start button correctly', () => {
    const button = document.getElementById('startReset');
    expect(button).toBeTruthy(); // Ensure button exists
    if (button) {
      const styles = dom.window.getComputedStyle(button);
      expect(styles.backgroundColor).toMatch(/rgb\(0,\s*123,\s*255\)/);
    } else {
      throw new Error('Start button not found in DOM');
    }
  });

  afterEach(() => {
    if (dom && dom.window) {
      dom.window.close();
    }
  });
});
