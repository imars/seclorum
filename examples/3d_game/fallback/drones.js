// examples/3d_game/fallback/drones.js
console.log('Initializing drones');
let playerDrone = null, aiDrones = [], checkpoints = [], obstacles = [];
const { updateStandings } = require('./ui.js'); // Import updateStandings

function initDrones() {
  if (!window.THREE) {
    console.error('THREE.js not loaded');
    return;
  }
  playerDrone = createDrone(0x0000ff, { x: 0, y: 10, z: 0 });
  playerDrone.momentum = new window.THREE.Vector3();
  playerDrone.rotation = new window.THREE.Euler(0, 0, 0);
  global.scene.add(playerDrone);
  global.playerDrone = playerDrone;
  aiDrones = [];
  for (let i = 0; i < 3; i++) {
    const aiDrone = createDrone(0xff0000, { x: i * 20 - 20, y: 10, z: 0 });
    aiDrone.path = [];
    aiDrone.targetCheckpoint = 0;
    global.scene.add(aiDrone);
    aiDrones.push(aiDrone);
  }
  global.aiDrones = aiDrones;
  for (let i = 0; i < 6; i++) {
    const checkpoint = new window.THREE.Mesh(
      new window.THREE.TorusGeometry(8, 1, 16, 100),
      new window.THREE.MeshBasicMaterial({ color: 0xffff00 })
    );
    checkpoint.position.set(Math.random() * 100 - 50, 10, -i * 150 - 50);
    global.scene.add(checkpoint);
    checkpoints.push(checkpoint);
  }
  global.checkpoints = checkpoints;
  for (let i = 0; i < 20; i++) {
    const type = Math.random() < 0.5 ? 'tree' : 'rock';
    const obstacle = new window.THREE.Mesh(
      type === 'tree' ? new window.THREE.CylinderGeometry(2, 2, 15, 16) : new window.THREE.BoxGeometry(5, 5, 5),
      new window.THREE.MeshStandardMaterial({ color: type === 'tree' ? 0x8B4513 : 0x808080 })
    );
    obstacle.position.set(Math.random() * 200 - 100, type === 'tree' ? 7.5 : 2.5, Math.random() * -800 - 50);
    global.scene.add(obstacle);
    obstacles.push(obstacle);
  }
  window.addEventListener('keydown', onKeyDown);
  window.addEventListener('keyup', onKeyUp);
  window.addEventListener('mousemove', onMouseMove);
  console.log('Drones initialized');
}

function createDrone(color, pos) {
  const drone = new window.THREE.Mesh(
    new window.THREE.SphereGeometry(2, 16, 16),
    new window.THREE.MeshStandardMaterial({ color })
  );
  drone.position.set(pos.x, pos.y, pos.z);
  drone.checkpoints = [];
  drone.time = 0;
  return drone;
}

function onKeyDown(event) {
  if (!global.playerDrone) return;
  global.playerDrone.controls = global.playerDrone.controls || {};
  switch (event.key) {
    case 'ArrowUp': case 'w': global.playerDrone.controls.forward = true; break;
    case 'ArrowDown': case 's': global.playerDrone.controls.backward = true; break;
    case 'ArrowLeft': global.playerDrone.controls.left = true; break;
    case 'ArrowRight': global.playerDrone.controls.right = true; break;
  }
}

function onKeyUp(event) {
  if (!global.playerDrone) return;
  global.playerDrone.controls = global.playerDrone.controls || {};
  switch (event.key) {
    case 'ArrowUp': case 'w': global.playerDrone.controls.forward = false; break;
    case 'ArrowDown': case 's': global.playerDrone.controls.backward = false; break;
    case 'ArrowLeft': global.playerDrone.controls.left = false; break;
    case 'ArrowRight': global.playerDrone.controls.right = false; break;
  }
}

function onMouseMove(event) {
  if (!global.playerDrone) return;
  console.log('Mouse moved:', event.movementX, event.movementY);
  const sensitivity = 0.002;
  global.playerDrone.rotation.y -= event.movementX * sensitivity;
  global.playerDrone.rotation.x -= event.movementY * sensitivity;
  global.playerDrone.rotation.x = Math.max(-Math.PI / 4, Math.min(Math.PI / 4, global.playerDrone.rotation.x));
}

function updatePlayerDrone(delta) {
  if (!global.playerDrone) return;
  const accel = 0.5, friction = 0.9, maxSpeed = 5;
  global.playerDrone.controls = global.playerDrone.controls || {};
  const move = new window.THREE.Vector3();
  if (global.playerDrone.controls.forward) move.z -= accel;
  if (global.playerDrone.controls.backward) move.z += accel;
  if (global.playerDrone.controls.left) move.x -= accel;
  if (global.playerDrone.controls.right) move.x += accel;
  const forward = new window.THREE.Vector3(0, 0, -1).applyEuler(global.playerDrone.rotation);
  const right = new window.THREE.Vector3(1, 0, 0).applyEuler(global.playerDrone.rotation);
  move.copy(forward.multiplyScalar(move.z)).add(right.multiplyScalar(move.x));
  global.playerDrone.momentum.add(move.multiplyScalar(delta));
  global.playerDrone.momentum.clampLength(0, maxSpeed);
  global.playerDrone.momentum.multiplyScalar(friction);
  global.playerDrone.position.add(global.playerDrone.momentum);
  global.playerDrone.position.y = 10;
  console.log('Player drone updated:', global.playerDrone.position);
}

function updateAIDrones(delta) {
  global.aiDrones.forEach((d) => {
    if (d.targetCheckpoint >= global.checkpoints.length) return;
    const target = global.checkpoints[d.targetCheckpoint].position;
    if (d.path.length === 0 || d.position.distanceTo(d.path[d.path.length - 1]) < 5) {
      d.path = aStarPath(d.position, target, obstacles);
    }
    if (d.path.length > 0) {
      const next = d.path.shift();
      const direction = next.clone().sub(d.position).normalize();
      d.position.add(direction.multiplyScalar(3 * delta));
      d.position.y = 10;
    }
    console.log(`AI drone ${global.aiDrones.indexOf(d)} updated: target=${d.targetCheckpoint}, pos=`, d.position);
  });
}

function aStarPath(start, goal, obstacles) {
  console.log('Calculating A* path from', start, 'to', goal);
  const gridSize = 10, grid = [];
  for (let x = -500; x <= 500; x += gridSize) {
    grid[x] = [];
    for (let z = -1000; z <= 0; z += gridSize) {
      grid[x][z] = obstacles.some((o) => new window.THREE.Vector3(x, 10, z).distanceTo(o.position) < 10) ? Infinity : 1;
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
        const nextPos = current.pos.clone().add(new window.THREE.Vector3(dx, 0, dz));
        const nextKey = `${Math.round(nextPos.x / gridSize)},${Math.round(nextPos.z / gridSize)}`;
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
  const drones = global.playerDrone && global.aiDrones ? [global.playerDrone, ...global.aiDrones] : [];
  drones.forEach((d, i) => {
    global.checkpoints.slice(0, 6).forEach((c, j) => { // Limit to 6 checkpoints
      if (!d.checkpoints.includes(j) && d.position.distanceTo(c.position) < 8) {
        d.checkpoints.push(j);
        console.log(`Drone ${i} hit checkpoint ${j}`);
        if (d !== global.playerDrone) {
          d.targetCheckpoint = Math.min(d.targetCheckpoint + 1, global.checkpoints.length);
        }
        if (d.checkpoints.length === global.checkpoints.length) {
          d.time = global.timer;
          updateStandings();
          console.log(`Drone ${i} finished race at ${d.time}s`);
        }
      }
    });
    obstacles.forEach((o) => {
      if (d.position.distanceTo(o.position) < 5) {
        d.momentum ? d.momentum.multiplyScalar(0.5) : d.position.set(d.position.x, 10, d.position.z);
        console.log(`Drone ${i} hit obstacle`);
        if (d === global.playerDrone) global.standings.push({ drone: i + 1, time: Infinity, penalty: true });
      }
    });
  });
}

function animate() {
  console.log('Animating frame');
  requestAnimationFrame(animate);
  const delta = global.clock.getDelta();
  global.timer += delta;
  updatePlayerDrone(delta);
  updateAIDrones(delta);
  checkCollisions();
  updateUI();
  global.camera.position.lerp(global.playerDrone.position.clone().add(new window.THREE.Vector3(0, 20, 30)), 0.1);
  global.camera.lookAt(global.playerDrone.position);
  global.renderer.render(global.scene, global.camera);
}

module.exports = {
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
};
