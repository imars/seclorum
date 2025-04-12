describe('Three.js scene', () => {
  beforeEach(() => {
    window.innerWidth = 500;
    window.innerHeight = 500;
    init();
  });

  it('should initialize the scene', () => {
    expect(scene).toBeDefined();
    expect(camera).toBeDefined();
    expect(renderer).toBeDefined();
    expect(renderer.domElement).toBeDefined();
    expect(scene.children.length).toBeGreaterThan(0);
  });

  it('should create drones', () => {
    expect(drones).toBeDefined();
    expect(drones.length).toBe(3);
    drones.forEach(drone => {
      expect(drone.model).toBeDefined();
      expect(drone.speed).toBe(0);
      expect(drone.acceleration).toBe(0.1);
    });
  });

  it('should handle keydown events', () => {
    const initialSpeed = drones[0].speed;
    const eventUp = new KeyboardEvent('keydown', { key: 'ArrowUp' });
    window.dispatchEvent(eventUp);
    expect(drones[0].speed).toBe(initialSpeed + 0.5);

    const eventDown = new KeyboardEvent('keydown', { key: 'ArrowDown' });
    window.dispatchEvent(eventDown);
    expect(drones[0].speed).toBe(initialSpeed);
  });

  afterEach(() => {
    document.body.removeChild(renderer.domElement);
  });
});