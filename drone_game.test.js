describe('3D Scene and Drone Movement', () => {
  beforeEach(() => {
    window.innerWidth = 500;
    window.innerHeight = 500;
    document.body.innerHTML = '<canvas id="canvas"></canvas>';
    init();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('should initialize the scene, camera, renderer, and drone', () => {
    expect(scene).toBeDefined();
    expect(camera).toBeDefined();
    expect(renderer).toBeDefined();
    expect(drone).toBeDefined();
    expect(drone.position.x).toBe(0);
    expect(drone.position.y).toBe(0);
    expect(drone.position.z).toBe(0);
  });

  it('should move the drone forward when ArrowUp is pressed', () => {
    const event = new KeyboardEvent('keydown', { key: 'ArrowUp' });
    document.dispatchEvent(event);
    requestAnimationFrame(() => {}); //Simulate a frame
    expect(drone.position.z).toBeGreaterThan(0);
  });


  it('should move the drone backward when ArrowDown is pressed', () => {
    const event = new KeyboardEvent('keydown', { key: 'ArrowDown' });
    document.dispatchEvent(event);
    requestAnimationFrame(() => {});
    expect(drone.position.z).toBeLessThan(0);
  });

  it('should move the drone left when ArrowLeft is pressed', () => {
    const event = new KeyboardEvent('keydown', { key: 'ArrowLeft' });
    document.dispatchEvent(event);
    requestAnimationFrame(() => {});
    expect(drone.position.x).toBeLessThan(0);
  });

  it('should move the drone right when ArrowRight is pressed', () => {
    const event = new KeyboardEvent('keydown', { key: 'ArrowRight' });
    document.dispatchEvent(event);
    requestAnimationFrame(() => {});
    expect(drone.position.x).toBeGreaterThan(0);
  });

  it('should stop drone movement on keyup', () => {
    const downEvent = new KeyboardEvent('keydown', { key: 'ArrowUp' });
    document.dispatchEvent(downEvent);
    requestAnimationFrame(() =>