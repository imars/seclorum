// examples/3d_game/fallback/drones.test.js
const { JSDOM } = require('jsdom');

// Debug to confirm file version
console.log('Using drones.test.js version: 2025-04-17');

// Set up JSDOM
const dom = new JSDOM(
  `<!DOCTYPE html><body>
    <canvas id="gameCanvas"></canvas>
    <div id="ui">
      <div>Time: <span id="timer">0.0</span>s</div>
      <div>Speed: <span id="speed">0.0</span></div>
      <div id="standings"><table></table></div>
      <button id="startReset">Start</button>
    </div>
  </body>`,
  { resources: 'usable', runScripts: 'dangerously' } // Changed to 'dangerously' for immediate DOM parsing
);
global.window = dom.window;
global.document = dom.window.document;
console.log('Initial DOM content:', global.document.body.innerHTML); // Log immediately after setup

// Mock THREE.js
const mockRenderer = {
  setSize: jest.fn(),
  render: jest.fn(),
  domElement: dom.window.document.createElement('canvas'),
};
const mockVector3 = () => {
  const vector = {
    add: jest.fn(function () { return this; }),
    sub: jest.fn(function () { return this; }), // Return self for chaining
    normalize: jest.fn(function () { return this; }), // Return self for chaining
    multiplyScalar: jest.fn(function () { return this; }), // Return self for chaining
    distanceTo: jest.fn(() => 5),
    clone: jest.fn(() => mockVector3()),
    clampLength: jest.fn(function () { return this; }), // Return self for chaining
    copy: jest.fn(function () { return this; }), // Add copy method
    x: 0,
    y: 0,
    z: 0,
    set: jest.fn(function () { return this; }), // Return self for chaining
    applyEuler: jest.fn(function () { return this; }),
    length: jest.fn(() => 0),
  };
  return vector;
};
global.window.THREE = {
  Scene: jest.fn().mockImplementation(() => ({ add: jest.fn() })),
  PerspectiveCamera: jest.fn().mockImplementation(() => ({
    position: { lerp: jest.fn(), clone: jest.fn(), set: jest.fn() },
    lookAt: jest.fn(),
  })),
  WebGLRenderer: jest.fn().mockImplementation(() => mockRenderer),
  Mesh: jest.fn().mockImplementation(() => ({
    position: mockVector3(),
    rotation: { x: 0, y: 0, z: 0, set: jest.fn() },
    checkpoints: [],
    momentum: mockVector3(),
    path: [],
    targetCheckpoint: 0,
    time: 0,
  })),
  SphereGeometry: jest.fn(),
  MeshStandardMaterial: jest.fn(),
  TorusGeometry: jest.fn(),
  MeshBasicMaterial: jest.fn(),
  CylinderGeometry: jest.fn(),
  BoxGeometry: jest.fn(),
  PlaneGeometry: jest.fn().mockImplementation(() => ({
    attributes: { position: { array: [], needsUpdate: true } },
    computeVertexNormals: jest.fn(),
  })),
  Vector3: jest.fn().mockImplementation(mockVector3),
  Euler: jest.fn().mockImplementation(() => ({ x: 0, y: 0, z: 0, set: jest.fn() })),
  Clock: jest.fn().mockImplementation(() => ({ getDelta: jest.fn(() => 0.016) })),
  AmbientLight: jest.fn(),
  DirectionalLight: jest.fn().mockImplementation(() => ({ position: { set: jest.fn() } })),
};

// Mock simplexNoise
global.window.simplexNoise = {
  createNoise2D: jest.fn(() => jest.fn(() => 0)),
};

// Mock requestAnimationFrame
jest.spyOn(global.window, 'requestAnimationFrame').mockImplementation((cb) => setTimeout(cb, 0));

// Import modules after mocks
const { initScene, scene, camera, renderer, clock } = require('./scene.js');
const { initTerrain } = require('./terrain.js');
const {
  playerDrone,
  initDrones,
  onMouseMove,
  onKeyDown,
  onKeyUp,
  updatePlayerDrone,
  updateAIDrones,
  checkCollisions,
  createDrone,
  aiDrones,
} = require('./drones.js');
const { initUI, updateUI, startRace } = require('./ui.js');

describe('Drones', () => {
  beforeEach(async () => {
    // Reset global variables
    global.scene = null;
    global.camera = null;
    global.renderer = null;
    global.timer = 0;
    global.clock = null;
    global.standings = [];
    global.playerDrone = null;
    global.aiDrones = [];
    global.checkpoints = [];

    // Clear mocks
    jest.clearAllMocks();

    // Debug DOM and mocks
    console.log('DOM content:', document.body.innerHTML);
    console.log('startReset exists:', !!document.getElementById('startReset'));
    console.log('window.THREE.Mesh defined:', !!window.THREE.Mesh);
    console.log('window.THREE.WebGLRenderer defined:', !!window.THREE.WebGLRenderer);

    // Initialize components
    initScene();
    initTerrain();
    initDrones();
    await initUI();
  });

  test('initializes player and AI drones', () => {
    expect(global.scene.add).toHaveBeenCalled();
    expect(window.THREE.Mesh).toHaveBeenCalled();
  });

  test('handles player controls with momentum', () => {
    if (!global.playerDrone) throw new Error('playerDrone is undefined');
    global.playerDrone.controls = {};
    onKeyDown({ key: 'ArrowUp' });
    updatePlayerDrone(0.016);
    expect(global.playerDrone.momentum.add).toHaveBeenCalled();
  });

  test('orients player drone with mouse', () => {
    if (!global.playerDrone) throw new Error('playerDrone is undefined');
    const event = { movementX: 100, movementY: 50 };
    onMouseMove(event);
    expect(global.playerDrone.rotation.y).toBeLessThan(0);
  });

  test('moves AI drones to checkpoints', () => {
    if (!global.aiDrones.length) throw new Error('aiDrones is empty');
    // Mock aStarPath to return a simple path
    jest.spyOn(require('./drones.js'), 'aStarPath').mockReturnValue([mockVector3()]);
    updateAIDrones(0.016);
    expect(window.THREE.Vector3).toHaveBeenCalled();
    jest.restoreAllMocks(); // Restore original implementation
  });

  test('advances AI checkpoints on collision', () => {
    if (!global.aiDrones.length) throw new Error('aiDrones is empty');
    global.aiDrones[0].position.distanceTo = jest.fn(() => 5);
    checkCollisions();
    expect(global.aiDrones[0].checkpoints).toContain(0);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  afterAll(() => {
    dom.window.close();
  });
});
