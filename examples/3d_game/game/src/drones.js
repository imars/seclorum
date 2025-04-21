// src/drones.js
import * as THREE from 'three';
import { scene, clock, camera, renderer } from './scene.js';
import { updateStandings, updateUI } from './ui.js';
import { getTimer, setTimer, getStandings, setStandings } from './state.js';

let playerDrone = null, aiDrones = [], checkpoints = [], obstacles = [];
let isAnimating = false;

function startAnimation() {
  if (!isAnimating) {
    isAnimating = true;
    console.log('Starting animation loop');
    if (!renderer || !renderer.getContext()) {
      console.error('Renderer not initialized for animation');
      return;
    }
    // Animation loop handled in game.js
  }
}

function initDrones() {
  playerDrone = createDrone(0x0000ff, { x: 0, y: 10, z: 0 });
  playerDrone.momentum = new THREE.Vector3();
  playerDrone.rotation.set(0, Math.PI / 2, 0);
  playerDrone.rotation.set(0, 0, 0);
  scene.add(playerDrone);
  aiDrones = [];
  for (let i = 0; i < 3; i++) {
    const aiDrone = createDrone(0xff0000, { x: i * 20 - 20, y: 10, z: 0 });
    aiDrone.path = [];
    aiDrone.targetCheckpoint = 0;
    scene.add(aiDrone);
    aiDrones.push(aiDrone);
  }
  for (let i = 0; i < 6; i++) {
    const checkpoint = new THREE.Mesh(
      new THREE.TorusGeometry(8, 1, 16, 100),
      new THREE.MeshBasicMaterial({ color: 0xffff00 })
    );
    checkpoint.position.set(Math.random() * 100 - 50, 5 + Math.random() * 15, -i * 150 - 50); // Y: 5-20
    scene.add(checkpoint);
    checkpoints.push(checkpoint);
  }
  for (let i = 0; i < 20; i++) {
    const type = Math.random() < 0.5 ? 'tree' : 'rock';
    const obstacle = new THREE.Mesh(
      type === 'tree' ? new THREE.CylinderGeometry(2, 2, 15, 16) : new THREE.BoxGeometry(5, 5, 5),
      new THREE.MeshStandardMaterial({ color: type === 'tree' ? 0x8B4513 : 0x808080 })
    );
    obstacle.position.set(
      Math.random() * 200 - 100,
      5 + Math.random() * 15, // Y: 5-20
      Math.random() * -800 - 50
    );
    scene.add(obstacle);
    obstacles.push(obstacle);
  }
  if (typeof document === 'undefined') {
    global.playerDrone = playerDrone;
    global.aiDrones = aiDrones;
    global.checkpoints = checkpoints;
    global.obstacles = obstacles;
    global.timer = getTimer();
    global.standings = getStandings();
  }
  const canvas = document.getElementById('gameCanvas');
  if (canvas) {
    canvas.addEventListener('click', () => {
      console.log('Requesting pointer lock');
      canvas.requestPointerLock();
    });
    document.addEventListener('pointerlockchange', () => {
      console.log(document.pointerLockElement === canvas ? 'Mouse locked' : 'Mouse unlocked');
    });
    document.addEventListener('pointerlockerror', (event) => {
      console.error('Pointer lock error:', event);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && document.pointerLockElement) {
        document.exitPointerLock();
      }
    });
    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mouseup', onMouseUp);
  } else {
    console.warn('Canvas element not found for pointer lock');
  }
  window.addEventListener('keydown', onKeyDown);
  window.addEventListener('keyup', onKeyUp);
  window.addEventListener('mousemove', onMouseMove);
  console.log('Drones initialized');
}

function createDrone(color, pos) {
  const drone = new THREE.Group(); // Use Group to combine multiple parts

  // Central body (small box)
  const bodyGeometry = new THREE.BoxGeometry(2, 0.5, 2);
  const bodyMaterial = new THREE.MeshStandardMaterial({ color });
  const body = new THREE.Mesh(bodyGeometry, bodyMaterial);
  drone.add(body);

  // Four arms (thin boxes, diagonal)
  const armGeometry = new THREE.BoxGeometry(2, 0.2, 0.2);
  const armMaterial = new THREE.MeshStandardMaterial({ color: 0x666666 }); // Grey arms
  const armPositions = [
    { x: 1, z: 1 },  // Top-right
    { x: 1, z: -1 }, // Bottom-right
    { x: -1, z: 1 }, // Top-left
    { x: -1, z: -1 } // Bottom-left
  ];
  armPositions.forEach((pos) => {
    const arm = new THREE.Mesh(armGeometry, armMaterial);
    arm.position.set(pos.x * 1.5, 0, pos.z * 1.5); // Extend arms diagonally
    drone.add(arm);
  });

  // Four engines (small cylinders at arm ends)
  const engineGeometry = new THREE.CylinderGeometry(0.3, 0.3, 0.4, 16);
  const engineMaterial = new THREE.MeshStandardMaterial({ color: 0x333333 }); // Dark engines
  armPositions.forEach((pos) => {
    const engine = new THREE.Mesh(engineGeometry, engineMaterial);
    engine.position.set(pos.x * 2, 0.2, pos.z * 2); // At arm ends, slightly raised
    engine.rotation.x = Math.PI / 2; // Align cylinders vertically
    drone.add(engine);
  });

  // Forward marker (red cone to indicate front)
  const forwardGeometry = new THREE.ConeGeometry(0.2, 0.5, 16);
  const forwardMaterial = new THREE.MeshStandardMaterial({ color: 0xff0000 });
  const forwardMarker = new THREE.Mesh(forwardGeometry, forwardMaterial);
  forwardMarker.position.set(0, 0.3, -1.5); // Front of drone (-Z)
  forwardMarker.rotation.x = -Math.PI / 2; // Point forward
  drone.add(forwardMarker);

  drone.position.set(pos.x, pos.y, pos.z);
  drone.checkpoints = [];
  drone.time = 0;
  return drone;
}

function onKeyDown(event) {
  if (!playerDrone) return;
  playerDrone.controls = playerDrone.controls || {};
  switch (event.key) {
    case 'ArrowUp': case 'w': playerDrone.controls.forward = true; break;
    case 'ArrowDown': case 's': playerDrone.controls.backward = true; break;
    case 'ArrowLeft': playerDrone.controls.left = true; break;
    case 'ArrowRight': playerDrone.controls.right = true; break;
  }
}

function onKeyUp(event) {
  if (!playerDrone) return;
  playerDrone.controls = playerDrone.controls || {};
  switch (event.key) {
    case 'ArrowUp': case 'w': playerDrone.controls.forward = false; break;
    case 'ArrowDown': case 's': playerDrone.controls.backward = false; break;
    case 'ArrowLeft': playerDrone.controls.left = false; break;
    case 'ArrowRight': playerDrone.controls.right = false; break;
  }
}

function onMouseDown(event) {
  if (!playerDrone) return;
  playerDrone.controls = playerDrone.controls || {};
  if (event.button === 0) { // Left mouse button
    playerDrone.controls.throttleUp = true;
  } else if (event.button === 2) { // Right mouse button
    playerDrone.controls.throttleDown = true;
  }
}

function onMouseUp(event) {
  if (!playerDrone) return;
  playerDrone.controls = playerDrone.controls || {};
  if (event.button === 0) {
    playerDrone.controls.throttleUp = false;
  } else if (event.button === 2) {
    playerDrone.controls.throttleDown = false;
  }
}

function onMouseMove(event) {
  if (!playerDrone || !document.pointerLockElement) return;
  console.log('Mouse moved:', event.movementX, event.movementY);
  const sensitivity = 0.002;
  playerDrone.rotation.y -= event.movementX * sensitivity; // Yaw
  playerDrone.rotation.x -= event.movementY * sensitivity; // Pitch
  playerDrone.rotation.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, playerDrone.rotation.x)); // Clamp pitch
}

function updatePlayerDrone(delta) {
  if (!playerDrone) return;
  const accel = 0.5, friction = 0.9, maxSpeed = 5;
  playerDrone.controls = playerDrone.controls || {};
  const move = new THREE.Vector3();

  // Movement relative to drone orientation
  const forward = new THREE.Vector3(0, 0, -1).applyEuler(playerDrone.rotation);
  const right = new THREE.Vector3(1, 0, 0).applyEuler(playerDrone.rotation);

  // Fixed: Forward/backward and strafe controls
  if (playerDrone.controls.forward) move.add(forward.multiplyScalar(accel)); // Forward
  if (playerDrone.controls.backward) move.add(forward.multiplyScalar(-accel)); // Backward
  if (playerDrone.controls.left) move.add(right.multiplyScalar(-accel)); // Strafe right
  if (playerDrone.controls.right) move.add(right.multiplyScalar(accel)); // Strafe left

  // Altitude control (mouse buttons only)
  if (playerDrone.controls.throttleUp) move.y += accel;
  if (playerDrone.controls.throttleDown) move.y -= accel;

  playerDrone.momentum.add(move.multiplyScalar(delta));
  playerDrone.momentum.clampLength(0, maxSpeed);
  playerDrone.momentum.multiplyScalar(friction);
  playerDrone.position.add(playerDrone.momentum);
  console.log('Player drone updated:', playerDrone.position);
}

function updateAIDrones(delta) {
  aiDrones.forEach((d) => {
    if (d.targetCheckpoint >= checkpoints.length) return;
    const target = checkpoints[d.targetCheckpoint].position;
    if (d.path.length === 0 || d.position.distanceTo(d.path[d.path.length - 1]) < 5) {
      d.path = aStarPath(d.position, target, obstacles);
    }
    if (d.path.length > 0) {
      const next = d.path.shift();
      const direction = next.clone().sub(d.position).normalize();
      d.position.add(direction.multiplyScalar(3 * delta));
      d.position.y = 10; // AI drones at fixed altitude
    }
    console.log(`AI drone ${aiDrones.indexOf(d)} updated: target=${d.targetCheckpoint}, pos=`, d.position);
  });
}

function aStarPath(start, goal, obstacles) {
  console.log('Calculating A* path from', start, 'to', goal);
  const gridSize = 10, grid = [];
  for (let x = -500; x <= 500; x += gridSize) {
    grid[x] = [];
    for (let z = -1000; z <= 0; z += gridSize) {
      grid[x][z] = obstacles.some((o) => new THREE.Vector3(x, 10, z).distanceTo(o.position) < 10) ? Infinity : 1;
    }
  }
  const open = [{ pos: start.clone(), g: 0, h: start.distanceTo(goal), f: start.distanceTo(goal), path: [] }];
  const closed = new Set();
  while (open.length) {
    open.sort((a, b) => a.f - b.f);
    const current = open.shift();
    const key = `${Math.round(current.pos.x / gridSize)},${Math.round(current.pos.z / gridSize)}`;
    if (closed.has(key)) continue;
    closed.add(key);
    if (current.pos.distanceTo(goal) < 10) {
      console.log('A* path found:', current.path.concat([goal]));
      return current.path.concat([goal]);
    }
    for (let dx of [-gridSize, 0, gridSize]) {
      for (let dz of [-gridSize, 0, gridSize]) {
        if (dx === 0 && dz === 0) continue;
        const nextPos = current.pos.clone().add(new THREE.Vector3(dx, 0, dz));
        const nextKey = `${Math.round(nextPos.x / gridSize)},${Math.round(nextPos.z / gridSize)}`;
        if (closed.has(nextKey) || (grid[Math.round(nextPos.x)] && grid[Math.round(nextPos.x)][Math.round(nextPos.z)] === Infinity)) continue;
        const g = current.g + gridSize;
        const h = nextPos.distanceTo(goal);
        open.push({ pos: nextPos, g, h, f: g + h, path: current.path.concat([nextPos]) });
      }
    }
  }
  console.log('No A* path found');
  return [];
}

function checkCollisions() {
  console.log('Checking collisions');
  const drones = playerDrone && aiDrones ? [playerDrone, ...aiDrones] : [];
  drones.forEach((d, i) => {
    checkpoints.forEach((c, j) => {
      if (!d.checkpoints.includes(j) && d.position.distanceTo(c.position) < 10) {
        d.checkpoints.push(j);
        console.log(`Drone ${i} hit checkpoint ${j} at position`, d.position);
        if (d !== playerDrone) {
          d.targetCheckpoint = Math.min(d.targetCheckpoint + 1, checkpoints.length);
        }
        if (d.checkpoints.length === checkpoints.length) {
          d.time = getTimer();
          console.log(`Drone ${i} finished race at ${d.time}s`);
        }
        updateStandings();
      }
    });
    obstacles.forEach((o) => {
      if (d.position.distanceTo(o.position) < 5) {
        d.momentum ? d.momentum.multiplyScalar(0.5) : d.position.set(d.position.x, d.position.y, d.position.z);
        console.log(`Drone ${i} hit obstacle`);
        if (d === playerDrone) {
          const standings = getStandings();
          standings.push({ drone: i + 1, time: Infinity, penalty: true });
          setStandings(standings);
        }
      }
    });
  });
}

export {
  playerDrone,
  createDrone,
  initDrones,
  checkCollisions,
  aStarPath,
  updateAIDrones,
  updatePlayerDrone,
  onMouseMove,
  onKeyUp,
  onKeyDown,
  aiDrones,
  checkpoints,
  obstacles,
  startAnimation,
};
