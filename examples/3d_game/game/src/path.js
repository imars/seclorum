// src/path.js
import * as THREE from 'three';

function aStarPath2D(start, goal, obstacles, gridSize = 10, gridRange = 200, maxNodes = 10000) {
  console.log('Calculating 2D A* path from', start, 'to', goal);
  const grid = [];
  for (let x = -gridRange; x <= gridRange; x += gridSize) {
    grid[x] = [];
    for (let z = -gridRange; z <= gridRange; z += gridSize) {
      grid[x][z] = obstacles.some((o) => new THREE.Vector3(x, 10, z).distanceTo(o.position) < 10) ? Infinity : 1;
    }
  }

  const open = [{ pos: start.clone(), g: 0, h: start.distanceTo(goal), f: start.distanceTo(goal), path: [] }];
  const closed = new Set();
  let nodeCount = 0;

  while (open.length) {
    if (nodeCount++ > maxNodes) {
      console.warn('A* 2D exceeded max nodes, returning empty path');
      return [];
    }
    open.sort((a, b) => a.f - b.f);
    const current = open.shift();
    const key = `${Math.round(current.pos.x / gridSize)},${Math.round(current.pos.z / gridSize)}`;
    if (closed.has(key)) continue;
    closed.add(key);

    if (current.pos.distanceTo(goal) < 10) {
      console.log('A* 2D path found:', current.path.concat([goal]));
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
  console.log('No A* 2D path found');
  return [];
}

function aStarPath3D(start, goal, obstacles, gridSize = 10, maxNodes = 10000) {
  console.log('Calculating 3D A* path from', start, 'to', goal);

  // Dynamic grid bounds
  const gridRange = Math.max(
    Math.abs(start.x - goal.x),
    Math.abs(start.z - goal.z),
    200
  ) + gridSize;
  const yRange = Math.max(Math.abs(start.y - goal.y), 20) + gridSize;
  const minX = Math.min(start.x, goal.x) - gridRange;
  const maxX = Math.max(start.x, goal.x) + gridRange;
  const minZ = Math.min(start.z, goal.z) - gridRange;
  const maxZ = Math.max(start.z, goal.z) + gridRange;
  const minY = Math.min(start.y, goal.y, 0) - yRange;
  const maxY = Math.max(start.y, goal.y, 30) + yRange;

  const grid = {};
  for (let x = minX; x <= maxX; x += gridSize) {
    grid[x] = grid[x] || {};
    for (let z = minZ; z <= maxZ; z += gridSize) {
      grid[x][z] = grid[x][z] || {};
      for (let y = minY; y <= maxY; y += gridSize) {
        grid[x][z][y] = obstacles.some((o) => new THREE.Vector3(x, y, z).distanceTo(o.position) < 10) ? Infinity : 1;
      }
    }
  }

  const open = [{ pos: start.clone(), g: 0, h: start.distanceTo(goal), f: start.distanceTo(goal), path: [] }];
  const closed = new Set();
  let nodeCount = 0;

  while (open.length) {
    if (nodeCount++ > maxNodes) {
      console.warn('A* 3D exceeded max nodes, returning empty path');
      return [];
    }
    open.sort((a, b) => a.f - b.f);
    const current = open.shift();
    const key = `${Math.round(current.pos.x / gridSize)},${Math.round(current.pos.y / gridSize)},${Math.round(current.pos.z / gridSize)}`;
    if (closed.has(key)) continue;
    closed.add(key);

    if (current.pos.distanceTo(goal) < 10) {
      console.log('A* 3D path found:', current.path.concat([goal]));
      return current.path.concat([goal]);
    }

    for (let dx of [-gridSize, 0, gridSize]) {
      for (let dy of [-gridSize, 0, gridSize]) {
        for (let dz of [-gridSize, 0, gridSize]) {
          if (dx === 0 && dy === 0 && dz === 0) continue;
          const nextPos = current.pos.clone().add(new THREE.Vector3(dx, dy, dz));
          const nextKey = `${Math.round(nextPos.x / gridSize)},${Math.round(nextPos.y / gridSize)},${Math.round(nextPos.z / gridSize)}`;
          const nx = Math.round(nextPos.x), ny = Math.round(nextPos.y), nz = Math.round(nextPos.z);
          if (closed.has(nextKey) || (grid[nx] && grid[nx][nz] && grid[nx][nz][ny] === Infinity)) continue;
          const g = current.g + gridSize * Math.sqrt(dx * dx + dy * dy + dz * dz) / gridSize; // Euclidean distance
          const h = nextPos.distanceTo(goal);
          open.push({ pos: nextPos, g, h, f: g + h, path: current.path.concat([nextPos]) });
        }
      }
    }
  }
  console.log('No A* 3D path found');
  return [];
}

export { aStarPath2D, aStarPath3D };
