const { JSDOM } = require('jsdom');
import * as THREE from 'three';
import { createNoise2D } from 'simplex-noise';
import { initScene, scene, camera, renderer, clock } from '../src/scene';
import { initTerrain } from '../src/terrain';
import {
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
} from '../src/drones';
import { initUI, updateUI, startRace } from '../src/ui';

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
  { resources: 'usable', runScripts: 'dangerously' }
);
global.window = dom.window;
global.document = dom.window.document;

global.window.THREE = THREE;
global.window.simplexNoise = createNoise2D();

jest.spyOn(global.window, 'requestAnimationFrame').mockImplementation(cb => setTimeout(cb, 0));

describe('Drones', () => {
  beforeEach(async () => {
    global.scene = null;
    global.camera = null;
    global.renderer = null;
    global.timer = 0;
    global.clock = null;
    global.standings = [];
    global.playerDrone = null;
    global.aiDrones = [];
    global.checkpoints = [];
    jest.clearAllMocks();
    initScene();
    initTerrain();
    initDrones();
    await initUI();
  });

  test('initializes game components', () => {
    expect(global.scene).toBeDefined();
    expect(global.camera).toBeDefined();
    expect(global.renderer).toBeDefined();
    expect(global.playerDrone).toBeDefined();
    expect(global.aiDrones.length).toBeGreaterThan(0);
  });

  test('starts race correctly', () => {
    startRace();
    expect(global.timer).toBe(0);
    expect(global.standings).toEqual([
      { drone: 1, checkpoints: 0, time: Infinity },
      { drone: 2, checkpoints: 0, time: Infinity },
      { drone: 3, checkpoints: 0, time: Infinity },
      { drone: 4, checkpoints: 0, time: Infinity },
    ]);
    expect(global.playerDrone.position).toMatchObject({ x: 0, y: 10, z: 0 });
  });

  afterAll(() => {
    dom.window.close();
  });
});
