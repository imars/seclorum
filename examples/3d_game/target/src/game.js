// src/game.js
import * as THREE from 'three';
import { scene, camera, renderer, clock, fogComposer, updateFogSettings, updateScene } from './scene.js';
import { playerDrone, aiDrones, checkpoints, obstacles, updatePlayerDrone, updateAIDrones, checkCollisions, onKeyDown, onKeyUp, onMouseMove, onMouseDown, onMouseUp } from './drones.js';
import { updateStandings, updateUI } from './ui.js';
import { getTimer, setTimer, getStandings, setStandings } from './state.js';
import { initTerrain, updateTerrain, setPerspective } from './terrain.js';
import { getSetting, setSetting } from './settings.js';
import { initDebugKeys } from './debugKeys.js';

let timer = 0;
let standings = [];
let isFirstPerson = false;
let isAnimating = false;
let terrainManager = null;
let isPaused = false;
let fpsElement = null;
let lastFrameTime = performance.now();
let frameCount = 0;
let fps = 0;
let cloudGroup = null;

function initGame() {
  console.log('Initializing game logic');
  timer = 0;
  standings = [];

  if (!camera) {
    console.error('Camera not initialized');
    return;
  }
  const cameraPos = getSetting('camera.initialPosition') || { x: 0, y: 30, z: 50 };
  camera.position.set(cameraPos.x, cameraPos.y, cameraPos.z);

  window.addEventListener('keydown', onKeyDownGame);
  window.addEventListener('keydown', onKeyDown);
  window.addEventListener('keyup', onKeyUp);
  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mousedown', onMouseDown);
  window.addEventListener('mouseup', onMouseUp);
  document.addEventListener('pointerlockchange', () => {
    console.log('Pointer lock:', document.pointerLockElement ? 'Locked' : 'Unlocked');
  });
  document.addEventListener('pointerlockerror', (e) => {
    console.error('Pointer lock error:', e);
  });

  const canvas = document.getElementById('gameCanvas');
  if (!canvas) {
    console.error('Canvas #gameCanvas not found');
  } else {
    canvas.addEventListener('click', () => {
      console.log('Canvas clicked, requesting pointer lock');
      if (!document.pointerLockElement) {
        canvas.requestPointerLock();
      }
    });
  }

  const startResetButton = document.getElementById('startReset');
  if (startResetButton) {
    startResetButton.addEventListener('click', startRace);
  } else {
    console.error('Start/Reset button not found');
  }

  fpsElement = document.createElement('div');
  fpsElement.id = 'fpsDisplay';
  fpsElement.style.position = 'absolute';
  fpsElement.style.top = '10px';
  fpsElement.style.left = '10px';
  fpsElement.style.color = 'white';
  fpsElement.style.background = 'rgba(0, 0, 0, 0.7)';
  fpsElement.style.padding = '5px';
  fpsElement.style.fontFamily = 'Arial, sans-serif';
  fpsElement.style.zIndex = '1000';
  fpsElement.style.pointerEvents = 'none';
  document.body.appendChild(fpsElement);
  console.log('FPS display initialized:', fpsElement);

  terrainManager = initTerrain();
  console.log('Terrain manager:', terrainManager ? 'success' : 'failed');
  console.log('Player drone:', playerDrone ? 'success' : 'failed');
  updateStandings();
  initDebugKeys();
  startAnimation();

  // Store cloud group for updates
  cloudGroup = scene.children.find(c => c.type === 'Group' && c.children.some(child => child.type === 'Sprite'));
}

function startRace() {
  console.log('Starting race');
  setTimer(0);
  setStandings([]);
  if (playerDrone) {
    playerDrone.position.set(0, 10, 0);
    playerDrone.momentum.set(0, 0, 0);
    playerDrone.rotation.set(0, 0, 0);
    playerDrone.checkpoints = [];
    playerDrone.time = 0;
  }
  if (aiDrones) {
    aiDrones.forEach((d, i) => {
      d.position.set(i * 20 - 20, 10, 0);
      d.checkpoints = [];
      d.time = 0;
      d.targetCheckpoint = 0;
      d.path = [];
      d.lastPathUpdate = getTimer();
    });
  }
  updateStandings();
  startAnimation();
}

function onKeyDownGame(event) {
  if (event.key === 'f' || event.key === 'F') {
    isFirstPerson = !isFirstPerson;
    console.log('Camera mode:', isFirstPerson ? 'first-person' : 'third-person');
    updateFogSettings(isFirstPerson);
    if (terrainManager) {
      terrainManager.setPerspective(isFirstPerson);
    } else {
      console.warn('Cannot set terrain perspective: terrainManager not initialized');
    }
  } else if (event.key === 'Escape') {
    if (document.pointerLockElement) {
      console.log('Escape pressed, exiting pointer lock');
      document.exitPointerLock();
    }
  }
}

function togglePause() {
  isPaused = !isPaused;
  console.log('Game', isPaused ? 'paused' : 'resumed');
  const pauseButton = document.getElementById('pause');
  if (pauseButton) {
    pauseButton.innerText = isPaused ? 'Resume' : 'Pause';
  }
}

function animate() {
  if (!isAnimating) return;
  try {
    requestAnimationFrame(animate);
    const now = performance.now();
    let delta = clock.getDelta();
    if (delta === 0) {
      delta = (now - lastFrameTime) / 1000;
      console.warn('clock.getDelta 0, fallback:', delta);
    }
    delta = Math.min(delta, 0.1);
    lastFrameTime = now;

    frameCount++;
    if (now - lastFrameTime >= 1000) {
      fps = frameCount;
      frameCount = 0;
      lastFrameTime = now;
      if (fpsElement) {
        fpsElement.textContent = `FPS: ${fps}`;
      }
    }

    setTimer(getTimer() + delta);

    if (!isPaused) {
      updatePlayerDrone(delta);
      checkCollisions();
      updateUI();

      if (playerDrone && terrainManager && playerDrone.position) {
        terrainManager.updateTerrain(playerDrone.position);
        if (playerDrone.position.y > 100) {
          playerDrone.position.y = 100;
          playerDrone.momentum.y = Math.min(playerDrone.momentum.y, 0);
        }
        // Update clouds to stay aligned with terrain
        if (cloudGroup && terrainManager.getTerrainOrigin) {
          const terrainOrigin = terrainManager.getTerrainOrigin();
          cloudGroup.position.set(terrainOrigin.x, terrainOrigin.y + 50, terrainOrigin.z);
          console.log('Clouds updated:', { position: cloudGroup.position });
        }
      }

      if (isFirstPerson && playerDrone) {
        camera.position.copy(playerDrone.position);
        camera.rotation.copy(playerDrone.rotation);
      } else if (playerDrone) {
        camera.position.lerp(
          playerDrone.position.clone().add(new THREE.Vector3(0, 20, 30)),
          0.1
        );
        camera.lookAt(playerDrone.position);
      }

      updateScene();
    }

    if (renderer && scene && camera) {
      if (fogComposer) {
        console.log('Rendering with fogComposer');
        fogComposer.render();
      } else {
        console.log('Rendering with renderer (no fogComposer)');
        renderer.render(scene, camera);
      }
    }
  } catch (error) {
    console.error('Animate error:', error);
    isAnimating = false;
  }
}

function startAnimation() {
  if (!isAnimating) {
    isAnimating = true;
    console.log('Starting animation');
    if (!renderer || !scene || !camera || !clock) {
      console.error('Missing dependencies:', {
        renderer: !!renderer,
        scene: !!scene,
        camera: !!camera,
        clock: !!clock
      });
      return;
    }
    lastFrameTime = performance.now();
    clock.start();
    animate();
  }
}

export { initGame, startRace, togglePause, isFirstPerson };
