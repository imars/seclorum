// src/drones.js
import * as THREE from 'three';
import { updateStandings, updateUI } from './ui.js';
import { scene, clock, camera, renderer } from './scene.js';
import { getTimer, setTimer, getStandings, setStandings } from './state.js';

console.log('THREE.Mesh in drones.js:', THREE.Mesh);

let playerDrone = null, aiDrones = [], checkpoints = [], obstacles = [];

function initDrones() {
  playerDrone = createDrone(0x0000ff, { x: 0, y: 10, z: 0 });
  playerDrone.momentum = new THREE.Vector3();
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
    checkpoint.position.set(Math.random() * 100 - 50, 10, -i * 150 - 50);
    scene.add(checkpoint);
    checkpoints.push(checkpoint);
  }
  for (let i = 0; i < 20; i++) {
    const type = Math.random() < 0.5 ? 'tree' : 'rock';
    const obstacle = new THREE.Mesh(
      type === 'tree' ? new THREE.CylinderGeometry(2, 2, 15, 16) : new THREE.BoxGeometry(5, 5, 5),
      new THREE.MeshStandardMaterial({ color: type === 'tree' ? 0x8B4513 : 0x808080 })
    );
    obstacle.position.set(Math.random() * 200 - 100, type === 'tree' ? 7.5 : 2.5, Math.random() * -800 - 50);
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
  window.addEventListener('keydown', onKeyDown);
  window.addEventListener('keyup', onKeyUp);
  window.addEventListener('mousemove', onMouseMove);
  console.log('Drones initialized');
}

function createDrone(color, pos) {
  const drone = new THREE.Mesh(
    new THREE.SphereGeometry(2, 16, 16),
    new THREE.MeshStandardMaterial({ color })
  );
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

function onMouseMove(event) {
  if (!playerDrone) return;
  console.log('Mouse moved:', event.movementX, event.movementY);
  const sensitivity = 0.002;
  playerDrone.rotation.y -= event.movementX * sensitivity;
  playerDrone.rotation.x -= event.movementY * sensitivity;
  playerDrone.rotation.x = Math.max(-Math.PI / 4, Math.min(Math.PI / 4, playerDrone.rotation.x));
}

function updatePlayerDrone(delta) {
  if (!playerDrone) return;
  const accel = 0.5, friction = 0.9, maxSpeed = 5;
  playerDrone.controls = playerDrone.controls || {};
  const move = new THREE.Vector3();
  if (playerDrone.controls.forward) move.z -= accel;
  if (playerDrone.controls.backward) move.z += accel;
  if (playerDrone.controls.left) move.x -= accel;
  if (playerDrone.controls.right) move.x += accel;
  const forward = new THREE.Vector3(0, 0, -1).applyEuler(playerDrone.rotation);
  const right = new THREE.Vector3(1, 0, 0).applyEuler(playerDrone.rotation);
  move.copy(forward.multiplyScalar(move.z)).add(right.multiplyScalar(move.x));
  playerDrone.momentum.add(move.multiplyScalar(delta));
  playerDrone.momentum.clampLength(0, maxSpeed);
  playerDrone.momentum.multiplyScalar(friction);
  playerDrone.position.add(playerDrone.momentum);
  playerDrone.position.y = 10;
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
      d.position.y = 10;
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
        const nextKey = `${Math.round(nextPos.x / gridSize)},${Math.round(current.pos.z / gridSize)}`;
        if (closed.has(nextKey) || (grid[Math.round(nextPos.x)] && grid[Math.round(nextPos.x)][Math.round(nextPos.z)] === Infinity))
          continue;
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
    checkpoints.slice(0, 6).forEach((c, j) => {
      if (!d.checkpoints.includes(j) && d.position.distanceTo(c.position) < 8) {
        d.checkpoints.push(j);
        console.log(`Drone ${i} hit checkpoint ${j}`);
        if (d !== playerDrone) {
          d.targetCheckpoint = Math.min(d.targetCheckpoint + 1, checkpoints.length);
        }
        if (d.checkpoints.length === checkpoints.length) {
          d.time = getTimer();
          updateStandings();
          console.log(`Drone ${i} finished race at ${d.time}s`);
        }
      }
    });
    obstacles.forEach((o) => {
      if (d.position.distanceTo(o.position) < 5) {
        d.momentum ? d.momentum.multiplyScalar(0.5) : d.position.set(d.position.x, 10, d.position.z);
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

function animate() {
  console.log('Animating frame');
  requestAnimationFrame(animate);
  const delta = clock.getDelta();
  setTimer(getTimer() + delta); // Fix: Use setter
  updatePlayerDrone(delta);
  updateAIDrones(delta);
  checkCollisions();
  updateUI();
  camera.position.lerp(playerDrone.position.clone().add(new THREE.Vector3(0, 20, 30)), 0.1);
  camera.lookAt(playerDrone.position);
  renderer.render(scene, camera);
}

export {
  playerDrone,
  createDrone,
  initDrones,
  animate,
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
};
