describe('Game Initialization', () => {
  beforeEach(() => {
    // Mock THREE.js for testing purposes.  Replace with actual THREE.js if available in your test environment.
    window.THREE = {
      Scene: jest.fn(),
      PerspectiveCamera: jest.fn(),
      WebGLRenderer: jest.fn(),
      PlaneGeometry: jest.fn(),
      MeshBasicMaterial: jest.fn(),
      Mesh: jest.fn(),
      BoxGeometry: jest.fn(),
    };

    // Mock document.getElementById for testing
ReturnValue({getContext: jest.fn()});

    init();
  });

  it('initializes scene, camera, and renderer', () => {
    expect(scene).toBeDefined();
    expect(camera).toBeDefined();
    expect(renderer).toBeDefined();
    expect(window.THREE.Scene).toHaveBeenCalled();
    expect(window.THREE.PerspectiveCamera).toHaveBeenCalled();
    expect(window.THREE.WebGLRenderer).toHaveBeenCalled();

  });

  it('creates at least 3 drones', () => {
    expect(drones).toBeDefined();
    expect(drones.length).toBeGreaterThanOrEqual(3);
    expect(drones[0]).toBeDefined();
    expect(drones[0].position).toBeDefined();
    //check that at least one drone has a red color
    expect(drones[0].material.color.r).toBeGreaterThan(0.9);

  });

  it('creates a procedural terrain', () => {
    expect(terrain).toBeDefined();
    expect(terrain.geometry).toBeDefined();
    expect(terrain.geometry.type).toBe('PlaneGeometry');
    //check that vertices are modified
    const terrainVertices = terrain.geometry.attributes.position.array;
    expect(terrainVertices.some(v => v !== 0)).toBe(true);

  });


  it('has at least 5 checkpoints', () => {
    //This test requires checkpoints to be initialized and populated in your `init()` function.  Adjust as needed.
    expect(checkpoints).toBeDefined();
    expect(checkpoints.length).toBeGreaterThanOrEqual(checkpointCount);
  });

  it('initializes UI elements', () => {
    expect(timer).toBeDefined(); // Or however