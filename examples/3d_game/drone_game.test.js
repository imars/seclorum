jest.mock('three');

test('initializes scene, camera, renderer, and drone', () => {
  require('./your-file'); // Replace your-file with the actual filename
  const { scene, camera, renderer, drone } = window;
  expect(scene).toBeDefined();
  expect(camera).toBeDefined();
  expect(renderer).toBeDefined();
  expect(drone).toBeDefined();
  expect(camera.position.x).toBe(0);
  expect(camera.position.y).toBe(5);
  expect(camera.position.z).toBe(10);
  expect(drone.geometry).toBeDefined();
  expect(drone.material).toBeDefined();
  expect(renderer.domElement).toBeDefined();
});

test('updates camera aspect and renderer size on resize', () => {
  require('./your-file');
  const { camera, renderer } = window;
  const originalWidth = window.innerWidth;
  const originalHeight = window.innerHeight;
  window.innerWidth = 1000;
  window.innerHeight = 500;
  const resizeEvent = new Event('resize');
  window.dispatchEvent(resizeEvent);
  expect(camera.aspect).toBe(2);
  expect(renderer.getSize().width).toBe(1000);
  expect(renderer.getSize().height).toBe(500);
  window.innerWidth = originalWidth;
  window.innerHeight = originalHeight;

});


test('moves drone with arrow keys', () => {
  require('./your-file');
  const { drone, controls } = window;
  const originalPosition = { ...drone.position };
  const keyEventUp = new KeyboardEvent('keydown', { key: 'ArrowUp' });
  const keyEventDown = new KeyboardEvent('keydown', { key: 'ArrowDown' });
  const keyEventLeft = new KeyboardEvent('keydown', { key: 'ArrowLeft' });
  const keyEventRight = new KeyboardEvent('keydown', { key: 'ArrowRight' });

  window.dispatchEvent(keyEventUp);
  expect(drone.position.z).toBe(originalPosition.z - controls.speed);

  window.dispatchEvent(keyEventDown);
  expect(drone.position.z).toBe(originalPosition.z);