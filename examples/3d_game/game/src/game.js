// src/game.js
import * as THREE from 'three';
import { scene, camera, renderer, clock } from './scene.js';
import { playerDrone, aiDrones, checkpoints, obstacles, updatePlayerDrone, updateAIDrones, checkCollisions } from './drones.js';
import { updateUI, updateStandings } from './ui.js';
import { getTimer, setTimer, getStandings, setStandings } from './state.js';

let timer = 0;
let standings = [];
let isFirstPerson = false;
let isAnimating = false;

function initGame() {
  console.log('Initializing game logic');
  timer = 0;
  standings = [];

  camera.position.set(0, 30, 50);
  window.addEventListener('keydown', onKeyDownGame);
  const startResetButton = document.getElementById('startReset');
  if (startResetButton) {
    startResetButton.addEventListener('click', startRace);
    console.log('Start/Reset button listener added');
  } else {
    console.error('Start/Reset button not found');
  }

  updateStandings();
  startAnimation();
}

function startRace() {
  console.log('Starting race');
  setTimer(0);
  setStandings([]);
  if (playerDrone) {
    playerDrone.position.set(0, 10, 0);
    playerDrone.momentum.set(0, 0, 0);
    playerDrone.rotation.set(0, Math.PI / 2, 0);
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
    });
  }
  updateStandings();
  startAnimation();
}

function onKeyDownGame(event) {
  if (event.key === 'f' || event.key === 'F') {
    isFirstPerson = !isFirstPerson;
    console.log('Camera mode:', isFirstPerson ? 'First-person' : 'Third-person');
    if (isFirstPerson && document.pointerLockElement !== document.getElementById('gameCanvas')) {
      document.getElementById('gameCanvas').requestPointerLock();
    }
  }
}

function animate() {
  if (!isAnimating) return;
  console.log('Animation frame');
  requestAnimationFrame(animate);
  const delta = clock.getDelta();
  setTimer(getTimer() + delta);
  console.log('Timer updated:', getTimer());

  updatePlayerDrone(delta);
  updateAIDrones(delta);
  checkCollisions();
  updateUI();

  if (isFirstPerson && playerDrone) {
    camera.position.copy(playerDrone.position);
    camera.rotation.copy(playerDrone.rotation);
  } else {
    camera.position.lerp(
      playerDrone.position.clone().add(new THREE.Vector3(0, 20, 30)),
      0.1
    );
    camera.lookAt(playerDrone.position);
  }

  renderer.render(scene, camera);
}

function startAnimation() {
  if (!isAnimating) {
    isAnimating = true;
    console.log('Starting game animation');
    if (!renderer || !scene || !camera) {
      console.error('Cannot start animation: missing renderer, scene, or camera');
      return;
    }
    animate();
  }
}

export { initGame, startRace };
