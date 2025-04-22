// src/index.js
import * as THREE from 'three';
import { createNoise2D } from 'simplex-noise';
import { initScene } from './scene.js';
import { initTerrain } from './terrain.js';
import { initDrones } from './drones.js';
import { initUI } from './ui.js';
import { initGame } from './game.js';

if (typeof window !== 'undefined') {
  import('./styles.css').catch((error) => console.error('Failed to load styles.css:', error));
  window.THREE = THREE;
  window.simplexNoise = createNoise2D();
}

async function init() {
  console.log('Initializing game');
  try {
    await new Promise((resolve) => {
      if (document.readyState === 'complete') {
        resolve();
      } else {
        window.addEventListener('load', resolve, { once: true });
      }
    });

    const canvas = document.getElementById('gameCanvas');
    if (!canvas) {
      throw new Error('Canvas element #gameCanvas not found in DOM');
    }

    initScene();
    console.log('Scene initialized');
    initDrones();
    console.log('Drones initialized');
    await initUI();
    console.log('UI initialized');
    initGame();
    console.log('Game logic initialized');
  } catch (error) {
    console.error('Initialization error:', error.message, error.stack);
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
console.log('Game initialization started');
