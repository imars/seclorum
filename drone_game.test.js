describe('Game Initialization and Components', () => {
  beforeEach(() => {
ing libraries.
    window.THREE = {
      Scene: jest.fn(),
      PerspectiveCamera: jest.fn(),
      WebGLRenderer: jest.fn(),
      PlaneGeometry: jest.fn(),
      MeshBasicMaterial: jest.fn(),
      Mesh: jest.fn(),
      BoxGeometry: jest.fn(),
      TorusGeometry: jest.fn(),
    };
    document.body.innerHTML = '<canvas id="myCanvas"></canvas>';
  });

  afterEach(() => {
    delete window.THREE;
  });


  it('initializes scene, camera, and renderer', () => {
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({canvas: document.getElementById('myCanvas')});
    renderer.setSize(window.innerWidth, window.innerHeight);

    expect(scene).toBeDefined();
    expect(camera).toBeDefined();
    expect(renderer).toBeDefined();
    expect(THREE.Scene).toHaveBeenCalledTimes(1);
    expect(THREE.PerspectiveCamera).toHaveBeenCalledTimes(1);
    expect(THREE.WebGLRenderer).toHaveBeenCalledTimes(1);
  });

  it('creates at least 3 drones', () => {
    playerDrone = createDrone(0, 5, 0, 0xff0000);
    drones = [createDrone(50, 5, 0, 0x0000ff), createDrone(-50, 5, 0, 0x00ff00), createDrone(100,5,0, 0x00ff00)];

    expect(drones).toBeDefined();
    expect(drones.length).toBeGreaterThanOrEqual(3);
  });

  it('creates a procedural terrain with modified vertices', () => {
    const terrainSize = 1000;
    const terrainGeometry = new THREE.PlaneGeometry(terrainSize, terrainSize, 100, 100);