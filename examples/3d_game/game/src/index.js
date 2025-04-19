import * as THREE from 'three';
import { createNoise2D } from 'simplex-noise';
import { initScene } from './scene.js';
import { initTerrain } from './terrain.js';
import { initDrones, animate } from './drones.js';
import { initUI } from './ui.js';

// Only import CSS and set globals in browser environments (Webpack)
if (typeof window !== 'undefined') {
  import('./styles.css');
  window.THREE = THREE;
  window.simplexNoise = createNoise2D();
}

console.log('Initializing game');
initScene();
initTerrain();
initDrones();
initUI().then(() => {
  animate();
});
console.log('Game initialized');
