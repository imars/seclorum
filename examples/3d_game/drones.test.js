const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');
const { TextEncoder, TextDecoder } = require('util');

// Polyfill TextEncoder and TextDecoder for jsdom
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

describe('Drones', () => {
  let dom, window, document;

  beforeEach(() => {
    dom = new JSDOM('<!DOCTYPE html><body><canvas id="gameCanvas"></canvas></body>', {
      runScripts: 'outside-only',
    });
    window = dom.window;
    document = window.document;
    global.window = window;
    global.document = document;

    // Mock THREE.js
    window.THREE = {
      Scene: jest.fn(() => ({})),
      PerspectiveCamera: jest.fn(),
      WebGLRenderer: jest.fn(),
      Mesh: jest.fn(() => ({ position: { x: 0, y: 0, z: 0, set: jest.fn(), clone: jest.fn() }, rotation: {} })),
      SphereGeometry: jest.fn(),
      MeshStandardMaterial: jest.fn(),
      TorusGeometry: jest.fn(),
      MeshBasicMaterial: jest.fn(),
      CylinderGeometry: jest.fn(),
      BoxGeometry: jest.fn(),
      Vector3: jest.fn(() => ({
        add: jest.fn(),
        sub: jest.fn(),
        normalize: jest.fn(),
        multiplyScalar: jest.fn(),
        distanceTo: jest.fn(),
        clone: jest.fn(),
        clampLength: jest.fn(),
      })),
      Euler: jest.fn(),
      Clock: jest.fn(() => ({ getDelta: jest.fn(() => 0.016) })),
    };

    // Mock scene and globals
    global.scene = { add: jest.fn() };
    global.renderer = { render: jest.fn() };
    global.camera = { position: { lerp: jest.fn(), clone: jest.fn() }, lookAt: jest.fn() };
    global.timer = 0;
    global.clock = { getDelta: jest.fn(() => 0.016) };

    // Load scripts
    require('./scene.js');
    require('./drones.js');
  });

  test('initializes player and AI drones', () => {
    initScene();
    initDrones();
    expect(scene.add).toHaveBeenCalled();
    expect(window.THREE.Mesh).toHaveBeenCalled();
  });

  test('handles player controls with momentum', () => {
    initScene();
    initDrones();
    playerDrone.controls = {};
    updatePlayerDrone(0.016);
    expect(playerDrone.momentum.add).toHaveBeenCalled();
  });

  test('orients player drone with mouse', () => {
    initScene();
    initDrones();
    const event = { movementX: 100, movementY: 50 };
    onMouseMove(event);
    expect(playerDrone.rotation.y).toBeLessThan(0);
  });

  test('moves AI drones to checkpoints', () => {
    initScene();
    initDrones();
    updateAIDrones(0.016);
    expect(aiDrones[0].position.add).toHaveBeenCalled();
  });

  test('advances AI checkpoints on collision', () => {
    initScene();
    initDrones();
    aiDrones[0].position.distanceTo = jest.fn(() => 5);
    checkCollisions();
    expect(aiDrones[0].checkpoints).toContain(0);
  });

  afterEach(() => {
    jest.resetAllMocks();
    dom.window.close();
  });
});
