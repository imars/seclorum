describe('Scene Initialization', () => {
  it('should create a scene', () => {
    expect(scene).toBeDefined();
  });

  it('should create a camera', () => {
    expect(camera).toBeDefined();
  });

  it('should create a renderer', () => {
    expect(renderer).toBeDefined();
  });

  it('should add terrain to the scene', () => {
    expect(scene.children).toContain(terrain);
  });

  it('should add checkpoints to the scene', () => {
    expect(scene.children).toContain(checkpoints[0]);
  });

  it('should add drones to the scene', () => {
    expect(drones.length).toBe(2);
    expect(scene.children).toContain(drones[0]);
    expect(scene.children).toContain(drones[1]);
  });

  it('should have ambient and directional lighting', () => {
    expect(scene.children.some(child => child instanceof THREE.AmbientLight)).toBe(true);
    expect(scene.children.some(child => child instanceof THREE.DirectionalLight)).toBe(true);
  });

  it('should set camera position', () => {
    expect(camera.position.z).toBe(5);
  });

  it('should initialize clock', () => {
    expect(clock).toBeDefined();
  });

});