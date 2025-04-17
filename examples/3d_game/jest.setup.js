// jest.setup..js

const { TextEncoder, TextDecoder } = require('util');
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

// Mock canvas for WebGL
require('jest-canvas-mock');

// Mock requestAnimationFrame
global.requestAnimationFrame = (callback) => {
  callback(0);
  return 1;
};
global.cancelAnimationFrame = () => {};

jest.mock('three', () => ({
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
  AmbientLight: jest.fn(),
  DirectionalLight: jest.fn(),
}));
