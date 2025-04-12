test('Canvas element exists', () => {
  expect(document.getElementById('myCanvas')).toBeDefined();
});

test('UI elements exist', () => {
  expect(document.getElementById('timer')).toBeDefined();
  expect(document.getElementById('speed')).toBeDefined();
  expect(document.getElementById('standings')).toBeDefined();
  expect(document.getElementById('startButton')).toBeDefined();
});

test('Three.js script tag exists', () => {
  const scripts = document.getElementsByTagName('script');
  const threejsScript = Array.from(scripts).find(script => script.src.includes('three.js'));
  expect(threejsScript).toBeDefined();
});