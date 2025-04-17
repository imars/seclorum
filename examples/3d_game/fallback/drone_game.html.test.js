const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

describe('Drone Game UI', () => {
  let dom, document;

  beforeEach(() => {
    // Load the HTML file
    const html = fs.readFileSync(path.resolve(__dirname, './fallback/drone_game.html'), 'utf8');
    dom = new JSDOM(html, { runScripts: 'outside-only', resources: 'usable' });
    document = dom.window.document;
    window = dom.window;
  });

  test('includes required scripts', () => {
    const scripts = Array.from(document.getElementsByTagName('script')).map(s => s.src);
    expect(scripts.some(src => src.includes('three.min.js'))).toBe(true);
    expect(scripts.some(src => src.includes('simplex-noise'))).toBe(true);
    expect(scripts.some(src => src.includes('scene.js'))).toBe(true);
    expect(scripts.some(src => src.includes('terrain.js'))).toBe(true);
    expect(scripts.some(src => src.includes('drones.js'))).toBe(true);
    expect(scripts.some(src => src.includes('ui.js'))).toBe(true);
  });

  test('styles start button correctly', () => {
    const button = document.getElementById('startReset');
    const styles = window.getComputedStyle(button);
    expect(styles.backgroundColor).toMatch(/rgb\(0,\s*123,\s*255\)/);
  });

  afterEach(() => {
    dom.window.close();
  });
});

describe('Three.js script tag exists', () => {
  test('Three.js script is included', () => {
    const html = fs.readFileSync(path.resolve(__dirname, './fallback/drone_game.html'), 'utf8');
    const dom = new JSDOM(html);
    const scripts = dom.window.document.getElementsByTagName('script');
    const threejsScript = Array.from(scripts).find(script => script.src.includes('three.min.js'));
    expect(threejsScript).toBeDefined();
  });
});
