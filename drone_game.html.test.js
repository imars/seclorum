test('Canvas element exists', () => {
  const canvas = document.getElementById('myCanvas');
  expect(canvas).toBeDefined();
});

test('UI elements exist', () => {
  const timer = document.getElementById('timer');
  const speed = document.getElementById('speed');
  const standings = document.getElementById('standings');
  const startButton = document.getElementById('startButton');

  expect(timer).toBeDefined();
  expect(speed).toBeDefined();
  expect(standings).toBeDefined();
  expect(startButton).toBeDefined();
});

test('Three.js script tag exists', () => {
  const scripts = document.getElementsByTagName('script');
  const threejsScript = Array.from(scripts).find(script => script.src.includes('three.js'));
  expect(threejsScript).toBeDefined();
});