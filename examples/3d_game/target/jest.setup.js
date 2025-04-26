import { TextEncoder, TextDecoder } from 'util';
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

import 'jest-canvas-mock';

global.requestAnimationFrame = (callback) => {
  callback(0);
  return 1;
};
global.cancelAnimationFrame = () => {};

jest.mock('three', () => {
  console.log('Mocking three module in jest.setup.js');
  const mockDocument = global.document || { createElement: jest.fn(() => ({})) };
  const rendererInstance = {
    setSize: jest.fn(),
    render: jest.fn(),
    domElement: mockDocument.createElement('canvas'),
  };
  const WebGLRenderer = jest.fn(function () {
    console.log('WebGLRenderer called, returning:', rendererInstance);
    return rendererInstance;
  });
  const Scene = jest.fn(() => {
    const instance = { add: jest.fn() };
    console.log('Scene called, returning:', instance);
    return instance;
  });
  return {
    Scene,
    PerspectiveCamera: jest.fn(() => ({
      position: { lerp: jest.fn(), clone: jest.fn(), set: jest.fn() },
      lookAt: jest.fn(),
    })),
    WebGLRenderer,
    Mesh: jest.fn(function () {
      return {
        position: {
          x: 0,
          y: 0,
          z: 0,
          set: jest.fn(function (x, y, z) {
            this.x = x;
            this.y = y;
            this.z = z;
            return this;
          }),
          clone: jest.fn(() => ({ ...this.position })),
          distanceTo: jest.fn(() => 5),
        },
        rotation: { x: 0, y: 0, z: 0, set: jest.fn() },
        checkpoints: [],
        momentum: {
          add: jest.fn().mockReturnThis(),
          multiplyScalar: jest.fn().mockReturnThis(),
          clampLength: jest.fn().mockReturnThis(),
          length: jest.fn(() => 0),
          set: jest.fn().mockReturnThis(),
        },
        path: [],
        targetCheckpoint: 0,
        time: 0,
      };
    }),
    SphereGeometry: jest.fn(),
    MeshStandardMaterial: jest.fn(),
    TorusGeometry: jest.fn(),
    MeshBasicMaterial: jest.fn(),
    CylinderGeometry: jest.fn(),
    BoxGeometry: jest.fn(),
    PlaneGeometry: jest.fn(() => ({
      attributes: { position: { array: [], needsUpdate: true } },
      computeVertexNormals: jest.fn(),
    })),
    Vector3: jest.fn(() => ({
      add: jest.fn().mockReturnThis(),
      sub: jest.fn().mockReturnThis(),
      normalize: jest.fn().mockReturnThis(),
      multiplyScalar: jest.fn().mockReturnThis(),
      distanceTo: jest.fn(() => 5),
      clone: jest.fn(() => ({
        add: jest.fn(),
        sub: jest.fn(),
        normalize: jest.fn(),
        multiplyScalar: jest.fn(),
        distanceTo: jest.fn(),
        clone: jest.fn(),
        clampLength: jest.fn(),
      })),
      clampLength: jest.fn().mockReturnThis(),
      copy: jest.fn().mockReturnThis(),
      set: jest.fn().mockReturnThis(),
      applyEuler: jest.fn().mockReturnThis(),
      length: jest.fn(() => 0),
    })),
    Euler: jest.fn(() => ({ x: 0, y: 0, z: 0, set: jest.fn() })),
    Clock: jest.fn(() => ({ getDelta: jest.fn(() => 0.016) })),
    AmbientLight: jest.fn(),
    DirectionalLight: jest.fn(() => ({ position: { set: jest.fn() } })),
  };
});
