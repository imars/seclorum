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
  it('should add drone to the scene', () => {
    expect(scene.children).toContain(drone);
  });
  it('should add terrain to the scene', () => {
    expect(scene.children).toContain(terrain);
  });
  it('should have 3 checkpoints', () => {
    expect(checkpoints.length).toBe(3);
  });
  it('should add opponent drone to the scene', () => {
    expect(scene.children).toContain(opponentDrone);
  });
  it('checkpoints should have correct radius', () => {
    checkpoints.forEach(checkpoint => {
      expect(checkpoint.geometry.parameters.radius).toBe(checkpointRadius);
    })
  })
});