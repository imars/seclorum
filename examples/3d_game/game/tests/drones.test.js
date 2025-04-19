const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');
const { TextEncoder, TextDecoder } = require('util');
const { initScene } = require('../src/scene');
const {
  initDrones,
  playerDrone,
  updatePlayerDrone,
  onMouseMove,
  updateAIDrones,
  checkCollisions,
  aiDrones,
} = require('../src/drones');

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

    // Mock globals
    global.camera = { position: { lerp: jest.fn(), clone: jest.fn() }, lookAt: jest.fn() };
    global.renderer = null; // Let initScene set this
    global.timer = 0;
    global.clock = { getDelta: jest.fn(() => 0.016) };
    global.checkpoints = [];
    global.aiDrones = [];
    global.playerDrone = null;

    // Override WebGLRenderer mock
    const THREE = require('three');
    jest.spyOn(THREE, 'WebGLRenderer').mockImplementation(() => {
      const instance = {
        setSize: jest.fn(),
        render: jest.fn(),
        domElement: global.document.createElement('canvas'),
      };
      console.log('Mocked WebGLRenderer returning:', instance);
      return instance;
    });

    jest.clearAllMocks();
  });

  test('initializes player and AI drones', () => {
    console.log('THREE.Scene before initScene:', require('three').Scene);
    console.log('THREE.WebGLRenderer before initScene:', require('three').WebGLRenderer);
    initScene();
    initDrones();
    expect(global.scene.add).toHaveBeenCalled();
    expect(require('three').Mesh).toHaveBeenCalled();
  });

  test('handles player controls with momentum', () => {
    console.log('THREE.Scene before initScene:', require('three').Scene);
    console.log('THREE.WebGLRenderer before initScene:', require('three').WebGLRenderer);
    initScene();
    console.log('global.renderer after initScene:', global.renderer);
    console.log('global.scene after initScene:', global.scene);
    initDrones();
    global.playerDrone.controls = {};
    updatePlayerDrone(0.016);
    expect(global.playerDrone.momentum.add).toHaveBeenCalled();
  });

  test('orients player drone with mouse', () => {
    console.log('THREE.Scene before initScene:', require('three').Scene);
    console.log('THREE.WebGLRenderer before initScene:', require('three').WebGLRenderer);
    initScene();
    console.log('global.renderer after initScene:', global.renderer);
    console.log('global.scene after initScene:', global.scene);
    initDrones();
    const event = { movementX: 100, movementY: 50 };
    onMouseMove(event);
    expect(global.playerDrone.rotation.y).toBeLessThan(0);
  });

  test('moves AI drones to checkpoints', () => {
    console.log('THREE.Scene before initScene:', require('three').Scene);
    console.log('THREE.WebGLRenderer before initScene:', require('three').WebGLRenderer);
    initScene();
    console.log('global.renderer after initScene:', global.renderer);
    console.log('global.scene after initScene:', global.scene);
    initDrones();
    updateAIDrones(0.016);
    expect(global.aiDrones[0].position.add).toHaveBeenCalled();
  });

  test('advances AI checkpoints on collision', () => {
    console.log('THREE.Scene before initScene:', require('three').Scene);
    console.log('THREE.WebGLRenderer before initScene:', require('three').WebGLRenderer);
    initScene();
    console.log('global.renderer after initScene:', global.renderer);
    console.log('global.scene after initScene:', global.scene);
    initDrones();
    global.aiDrones[0].position.distanceTo = jest.fn(() => 5);
    checkCollisions();
    expect(global.aiDrones[0].checkpoints).toContain(0);
  });

  afterEach(() => {
    jest.resetAllMocks();
    if (dom && dom.window) {
      dom.window.close();
    }
  });
});
