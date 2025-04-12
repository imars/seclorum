test('Canvas element exists', () => {
  const canvas = document.getElementById('myCanvas');
  expect(canvas).toBeDefined();
});

test('Timer element exists', () => {
  const timer = document.getElementById('timer');
  expect(timer).toBeDefined();
});

test('Speed element exists', () => {
  const speed = document.getElementById('speed');
  expect(speed).toBeDefined();
});

test('Standings element exists', () => {
  const standings = document.getElementById('standings');
  expect(standings).toBeDefined();
});

test('Start/Reset button exists', () => {
  const button = document.getElementById('startButton');
  expect(button).toBeDefined();
});