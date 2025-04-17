// jest.setup..js

const { TextEncoder, TextDecoder } = require('util');
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

// Mock canvas for WebGL
require('jest-canvas-mock');
