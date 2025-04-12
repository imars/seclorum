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

  it('should add ambient light to the scene', () => {
    expect(scene.children.some(child => child instanceof THREE.AmbientLight)).toBe(true);
  });

  it('should add directional light to the scene', () => {
    expect(scene.children.some(child => child instanceof THREE.DirectionalLight)).toBe(true);
  });

  it('should generate terrain', () => {
    expect(terrain).toBeDefined();
    expect(terrain.geometry).toBeDefined();
    expect(terrain.material).toBeDefined();
  });

  it('should position the camera', () => {
    expect(camera.position.x).toBeCloseTo(0);
    expect(camera.position.y).toBeCloseTo(20);
    expect(camera.position.z).toBeCloseTo(30);
  });

  it('should add drone to scene after loading', (done) => {
    setTimeout(() => {
      expect(scene.children.some(child => child === drone)).toBe(true);
      done();
    }, 100); // Adjust timeout as needed
  });

  it('should position the drone', () => {
    setTimeout(() => {
      expect(drone.position.x).toBeCloseTo(0);
      expect(drone.position.y).toBeCloseTo(5);
      expect(drone.position.z).toBeCloseTo(0);
    }, 100);
  });

});

describe('Terrain Generation', () => {
  it('should generate a plane geometry', () => {
    expect(terrain.geometry).toBeInstanceOf(THREE.PlaneGeometry);
  });
  it('should have modified vertices', () => {
    expect(terrain.geometry.vertices.some(vertex => vertex.z !== 0)).toBe(true);
  });
});