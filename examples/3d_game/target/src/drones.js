// src/drones.js
import * as THREE from 'three';
import { scene, clock, camera, renderer } from './scene.js';
import { updateStandings, updateUI } from './ui.js';
import { getTimer, setTimer, getStandings, setStandings } from './state.js';
import { getSetting } from './settings.js';
import { aStarPath3D } from './path.js';

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
  }
}

function initDrones() {
  console.log('Initializing drones');
  playerDrone = createDrone(0x0000ff, { x: 0, y: 10, z: 0 });
  playerDrone.momentum = new THREE.Vector3();
  playerDrone.rotation.set(0, 0, 0);
  playerDrone.controls = {};
  scene.add(playerDrone);

  aiDrones = [];
  const aiCount = getSetting('aiDrone.count');
  for (let i = 0; i < aiCount; i++) {
    const aiDrone = createDrone(0xff0000, { x: i * 20 - 20, y: 10, z: 0 });
    aiDrone.path = [];
    aiDrone.targetCheckpoint = 0;
    aiDrone.lastPathUpdate = getTimer() - getSetting('aiDrone.pathUpdateInterval');
    scene.add(aiDrone);
    aiDrones.push(aiDrone);
  }

  checkpoints = [];
  const checkpointSpacing = getSetting('track.checkpointSpacing');
  const checkpointOffset = getSetting('track.checkpointOffset');
  for (let i = 0; i < 10; i++) {
    const checkpoint = new THREE.Mesh(
      new THREE.RingGeometry(10, 12, 16),
      new THREE.MeshBasicMaterial({ color: 0xffff00, side: THREE.DoubleSide })
    );
    const x = (Math.random() - 0.5) * 100;
    const y = 10;
    const z = -i * checkpointSpacing - checkpointOffset;
    checkpoint.position.set(x, y, z);
    checkpoint.castShadow = false;
    checkpoint.receiveShadow = false;
    checkpoint.renderOrder = 10; // Increased
    scene.add(checkpoint);
    checkpoints.push(checkpoint);
    console.log(`Checkpoint ${i} at position:`, checkpoint.position);
  }

  obstacles = [];
  for (let i = 0;  i < 5; i++) {
    const obstacle = new THREE.Mesh(
      new THREE.BoxGeometry(10, 10, 10),
      new THREE.MeshStandardMaterial({ color: 0x888888 })
    );
    obstacle.position.set(
      Math.random() * 100 - 50,
      5,
      Math.random() * -1000 - 50
    );
    obstacle.castShadow = true;
    obstacle.receiveShadow = true;
    obstacle.renderOrder = 10; // Increased
    scene.add(obstacle);
    obstacles.push(obstacle);
  }
}

function createDrone(color, pos) {
  const drone = new THREE.Group();
  const bodyGeometry = new THREE.BoxGeometry(2, 0.5, 2);
  const bodyMaterial = new THREE.MeshStandardMaterial({ color });
  const body = new THREE.Mesh(bodyGeometry, bodyMaterial);
  body.castShadow = true;
  body.receiveShadow = true;
  body.renderOrder = 10; // Increased
  drone.add(body);

  const armGeometry = new THREE.BoxGeometry(2, 0.2, 0.2);
  const armMaterial = new THREE.MeshStandardMaterial({ color: 0x666666 });
  const armPositions = [
    { x: 1, z: 1 }, { x: 1, z: -1 }, { x: -1, z: 1 }, { x: -1, z: -1 }
  ];
  armPositions.forEach((pos) => {
    const arm = new THREE.Mesh(armGeometry, armMaterial);
    arm.position.set(pos.x * 1.5, 0, pos.z * 1.5);
    arm.castShadow = true;
    arm.receiveShadow = true;
    arm.renderOrder = 10; // Increased
    drone.add(arm);
  });

  const engineGeometry = new THREE.CylinderGeometry(0.3, 0.3, 0.4, 16);
  const engineMaterial = new THREE.MeshStandardMaterial({ color: 0x333333 });
  armPositions.forEach((pos) => {
    const engine = new THREE.Mesh(engineGeometry, engineMaterial);
    engine.position.set(pos.x * 2, 0.2, pos.z * 2);
    engine.rotation.x = Math.PI / 2;
    engine.castShadow = true;
    engine.receiveShadow = true;
    engine.renderOrder = 10; // Increased
    drone.add(engine);
  });

  const forwardGeometry = new THREE.ConeGeometry(0.2, 0.5, 16);
  const forwardMaterial = new THREE.MeshStandardMaterial({ color: 0xff0000 });
  const forwardMarker = new THREE.Mesh(forwardGeometry, forwardMaterial);
  forwardMarker.position.set(0, 0.3, -1.5);
  forwardMarker.rotation.x = -Math.PI / 2;
  forwardMarker.castShadow = true;
  forwardMarker.receiveShadow = true;
  forwardMarker.renderOrder = 10; // Increased
  drone.add(forwardMarker);

  drone.momentum = new THREE.Vector3();
  drone.position.set(pos.x, pos.y, pos.z);
  drone.checkpoints = [];
  drone.time = 0;
  drone.renderOrder = 10; // Increased
  return drone;
}

function onKeyDown(event) {
  if (!playerDrone) {
    console.warn('playerDrone not initialized in onKeyDown');
    return;
  }
  playerDrone.controls = playerDrone.controls || {};
  switch (event.key) {
    case 'ArrowUp': case 'w':
      playerDrone.controls.forward = true;
      console.log('Key down: forward');
      break;
    case 'ArrowDown': case 's':
      playerDrone.controls.backward = true;
      console.log('Key down: backward');
      break;
    case 'ArrowLeft':
      playerDrone.controls.setLeft = true;
      console.log('Key down: left');
      break;
    case 'ArrowRight':
      playerDrone.controls.right = true;
      console.log('Key down: right');
      break;
  }
}

function onKeyUp(event) {
  if (!playerDrone) {
    console.warn('playerDrone not initialized in onKeyUp');
    return;
  }
  playerDrone.controls = playerDrone.controls || {};
  switch (event.key) {
    case 'ArrowUp': case 'w':
      playerDrone.controls.forward = false;
      console.log('Key up: forward');
      break;
    case 'ArrowDown': case 's':
      playerDrone.controls.backward = false;
      console.log('Key up: backward');
      break;
    case 'ArrowLeft':
      playerDrone.controls.left = false;
      console.log('Key up: left');
      break;
    case 'ArrowRight':
      playerDrone.controls.right = false;
      console.log('Key up: right');
      break;
  }
}

function onMouseDown(event) {
  if (!playerDrone) {
    console.warn('playerDrone not initialized in onMouseDown');
    return;
  }
  playerDrone.controls = playerDrone.controls || {};
  if (event.button === 0) {
    playerDrone.controls.throttleUp = true;
    console.log('Mouse down: throttle up');
  } else if (event.button === 2) {
    playerDrone.controls.throttleDown = true;
    console.log('Mouse down: throttle down');
  }
}

function onMouseUp(event) {
  if (!playerDrone) {
    console.warn('playerDrone not initialized in onMouseUp');
    return;
  }
  playerDrone.controls = playerDrone.controls || {};
  if (event.button === 0) {
    playerDrone.controls.throttleUp = false;
    console.log('Mouse up: throttle up');
  } else if (event.button === 2) {
    playerDrone.controls.throttleDown = false;
    console.log('Mouse up: throttle down');
  }
}

function onMouseMove(event) {
  if (!playerDrone || !document.pointerLockElement) return;
  console.log('Mouse moved:', event.movementX, event.movementY);
  const sensitivity = 0.002;
  playerDrone.rotation.y -= event.movementX * sensitivity;
  playerDrone.rotation.x -= event.movementY * sensitivity;
  playerDrone.rotation.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, playerDrone.rotation.x));
}

function updatePlayerDrone(delta) {
  if (!playerDrone) {
    console.warn('playerDrone not initialized in updatePlayerDrone');
    return;
  }
  const accel = getSetting('playerDrone.accel');
  const friction = getSetting('playerDrone.friction');
  const maxSpeed = getSetting('playerDrone.maxSpeed');
  playerDrone.controls = playerDrone.controls || {};
  const move = new THREE.Vector3();

  const forward = new THREE.Vector3(0, 0, -1).applyEuler(playerDrone.rotation);
  const right = new THREE.Vector3(1, 0, 0).applyEuler(playerDrone.rotation);

  if (playerDrone.controls.forward) move.add(forward.multiplyScalar(accel));
  if (playerDrone.controls.backward) move.add(forward.multiplyScalar(-accel));
  if (playerDrone.controls.left) move.add(right.multiplyScalar(-accel));
  if (playerDrone.controls.right) move.add(right.multiplyScalar(accel));
  if (playerDrone.controls.throttleUp) move.y += accel;
  if (playerDrone.controls.throttleDown) move.y -= accel;

  playerDrone.momentum.add(move.multiplyScalar(delta));
  playerDrone.momentum.clampLength(0, maxSpeed);
  playerDrone.momentum.multiplyScalar(friction);
  playerDrone.position.add(playerDrone.momentum);
  console.log('Player drone updated:', playerDrone.position);
}

function updateAIDrones(delta) {
  if (!aiDrones) {
    console.warn('aiDrones not initialized in updateAIDrones');
    return;
  }
  const aiAccel = getSetting('aiDrone.accel');
  const aiMaxSpeed = getSetting('aiDrone.maxSpeed');
  const aiFriction = getSetting('aiDrone.friction');
  const pathUpdateInterval = getSetting('aiDrone.pathUpdateInterval');

  aiDrones.forEach((drone, i) => {
    if (drone.targetCheckpoint >= checkpoints.length) return;

    const now = getTimer();
    console.log(`AI drone ${i} check: now=${now}, lastUpdate=${drone.lastPathUpdate}, interval=${pathUpdateInterval}, pathLength=${drone.path.length}`);
    if (now - drone.lastPathUpdate > pathUpdateInterval || drone.path.length === 0) {
      const target = checkpoints[drone.targetCheckpoint].position;
      console.log(`Calculating A* path for drone ${i} from`, drone.position, 'to', target);
      const startTime = performance.now();
      const path = aStarPath3D(drone.position, target, obstacles);
      console.log(`A* path for drone ${i} took ${(performance.now() - startTime).toFixed(2)}ms, path:`, path);
      if (path.length > 0) {
        drone.path = path;
        drone.lastPathUpdate = now;
      } else {
        console.warn(`No path found for drone ${i}, retrying in ${pathUpdateInterval}s`);
        drone.lastPathUpdate = now + pathUpdateInterval;
      }
    }

    if (drone.path.length > 0) {
      const target = drone.path[0];
      const direction = target.clone().sub(drone.position).normalize();
      if (!drone.momentum) {
        console.warn(`Momentum undefined for AI drone ${i}, initializing`);
        drone.momentum = new THREE.Vector3();
      }
      drone.momentum.add(direction.multiplyScalar(aiAccel * delta));
      drone.momentum.clampLength(0, aiMaxSpeed);
      drone.momentum.multiplyScalar(aiFriction);
      drone.position.add(drone.momentum);

      if (drone.position.distanceTo(target) < 5) {
        drone.path.shift();
      }

      const toTarget = checkpoints[drone.targetCheckpoint].position.clone().sub(drone.position);
      if (toTarget.length() < 15) {
        drone.checkpoints.push(drone.targetCheckpoint);
        drone.targetCheckpoint++;
        console.log(`AI drone ${i} reached checkpoint ${drone.targetCheckpoint - 1}`);
        if (drone.targetCheckpoint >= checkpoints.length && drone.checkpoints.length === checkpoints.length) {
          drone.time = getTimer();
          console.log(`AI drone ${i} finished race at ${drone.time}`);
        }
      }
    } else {
      console.log(`AI drone ${i} has no path, stationary at`, drone.position);
    }
    console.log(`AI drone ${i} updated: target=${drone.targetCheckpoint}, pos=`, drone.position);
  });
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
  updateAIDrones,
  updatePlayerDrone,
  onMouseDown,
  onMouseMove,
  onMouseUp,
  onKeyUp,
  onKeyDown,
  aiDrones,
  checkpoints,
  obstacles,
  startAnimation,
};
