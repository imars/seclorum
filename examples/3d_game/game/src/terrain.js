// src/terrain.js
import * as THREE from 'three';
import { scene, camera, renderer } from './scene.js';
import { getSetting } from './settings.js';
import { createNoise2D } from 'simplex-noise';

const tiles = new Map();
let lastGridX = null;
let lastGridZ = null;
let lastUpdateTime = 0;
const minUpdateInterval = 1000;
let terrainWorker = null;
const noise2D = createNoise2D();
const maxPendingTiles = 1;
let isFirstPerson = false; // Track perspective

function initTerrain() {
  console.log('Starting initTerrain');
  try {
    if (!THREE || !scene || !camera || !renderer) {
      throw new Error('Missing dependencies');
    }

    console.warn('Using synchronous tile generation');
    initializeTilesSynchronously(0, 0);
    terrainWorker = null;

    console.log('Terrain initialized, tiles:', tiles.size);
    return { updateTerrain, setPerspective };
  } catch (error) {
    console.error('Error in initTerrain:', error);
    return null;
  }
}

function setPerspective(newIsFirstPerson) {
  if (newIsFirstPerson !== isFirstPerson) {
    isFirstPerson = newIsFirstPerson;
    lastGridX = null; // Force tile update
    lastGridZ = null;
    console.log(`Terrain perspective set to ${isFirstPerson ? 'first-person' : 'third-person'}`);
  }
}

function streamTiles(gridX, gridZ) {
  const tileSize = getSetting('terrain.tileSize');
  const renderDistance = isFirstPerson ?
    getSetting('terrain.firstPerson.renderDistance') :
    getSetting('terrain.thirdPerson.renderDistance');
  let pendingCount = Array.from(tiles.values()).filter(t => t.pending).length;

  const tileQueue = [];
  for (let x = gridX - renderDistance; x <= gridX + renderDistance; x++) {
    for (let z = gridZ - renderDistance; z <= gridZ + renderDistance; z++) {
      const key = `${x},${z}`;
      if (!tiles.has(key)) {
        const distance = Math.sqrt((x - gridX) ** 2 + (z - gridZ) ** 2);
        tileQueue.push({ x, z, distance });
      }
    }
  }
  tileQueue.sort((a, b) => a.distance - b.distance);

  for (const { x, z } of tileQueue) {
    if (pendingCount >= maxPendingTiles) break;
    queueTileGeneration(x, z);
    pendingCount++;
  }
}

function initializeTilesSynchronously(gridX, gridZ) {
  console.log('Generating tiles synchronously for grid:', gridX, gridZ);
  const tileSize = getSetting('terrain.tileSize');
  const renderDistance = isFirstPerson ?
    getSetting('terrain.firstPerson.renderDistance') :
    getSetting('terrain.thirdPerson.renderDistance');
  for (let x = gridX - renderDistance; x <= gridX + renderDistance; x++) {
    for (let z = gridZ - renderDistance; z <= gridZ + renderDistance; z++) {
      generateTileSynchronous(x, z);
    }
  }
}

function queueTileGeneration(gridX, gridZ) {
  const key = `${gridX},${gridZ}`;
  if (tiles.has(key)) return;

  tiles.set(key, { terrain: null, pending: true });
  terrainWorker.postMessage({
    gridX,
    gridZ,
    tileSize: getSetting('terrain.tileSize'),
    segments: getSetting('terrain.segments'),
    noiseScale: getSetting('terrain.noiseScale'),
    noiseAmplitude: getSetting('terrain.noiseAmplitude'),
  });
  console.log(`Queued tile ${key}`);
}

function handleWorkerMessage(e) {
  const { gridX, gridZ, geometryData, error } = e.data;
  const key = `${gridX},${gridZ}`;
  console.log(`Received worker message for ${key}:`, { geometryData, error });

  if (!tiles.has(key)) {
    console.warn(`Tile ${key} not in map`);
    return;
  }

  if (error) {
    console.error(`Error generating tile ${key}:`, error);
    tiles.delete(key);
    generateTileSynchronous(gridX, gridZ);
    return;
  }

  try {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(geometryData.vertices, 3));
    geometry.setIndex(geometryData.indices);
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({ color: 0x228B22, roughness: 0.8, metalness: 0.2 });
    const terrain = new THREE.Mesh(geometry, material);
    terrain.position.set(gridX * getSetting('terrain.tileSize'), 0, gridZ * getSetting('terrain.tileSize'));
    terrain.castShadow = false;
    terrain.receiveShadow = true;
    scene.add(terrain);

    tiles.set(key, { terrain, pending: false });
    console.log(`Added tile ${key}`);
  } catch (err) {
    console.error(`Error processing tile ${key}:`, err);
    tiles.delete(key);
    generateTileSynchronous(gridX, gridZ);
  }
}

function generateTileSynchronous(gridX, gridZ) {
  const key = `${gridX},${gridZ}`;
  if (tiles.has(key)) return;

  try {
    const tileSize = getSetting('terrain.tileSize');
    const segments = getSetting('terrain.segments');
    const geometry = new THREE.BufferGeometry();
    const width = segments + 1;
    const vertices = new Float32Array(width * width * 3);
    const data = new Float32Array(width * width);

    for (let i = 0; i < data.length; i++) {
      const localX = (i % width) * (tileSize / segments) - tileSize / 2;
      const localZ = Math.floor(i / width) * (tileSize / segments) - tileSize / 2;
      const globalX = localX + gridX * tileSize;
      const globalZ = localZ + gridZ * tileSize;
      const height = noise2D(globalX / getSetting('terrain.noiseScale'), globalZ / getSetting('terrain.noiseAmplitude')) * getSetting('terrain.noiseAmplitude');
      if (!Number.isFinite(height)) {
        console.error(`Invalid height at ${globalX},${globalZ}: ${height}`);
        return;
      }
      data[i] = height;
    }

    for (let i = 0, j = 0; i < width * width; i++, j += 3) {
      const x = (i % width) * (tileSize / segments) - tileSize / 2;
      const z = Math.floor(i / width) * (tileSize / segments) - tileSize / 2;
      vertices[j] = x;
      vertices[j + 1] = data[i];
      vertices[j + 2] = z;
    }

    const indices = [];
    for (let z = 0; z < segments; z++) {
      for (let x = 0; x < segments; x++) {
        const a = x + width * z;
        const b = x + width * (z + 1);
        const c = x + 1 + width * (z + 1);
        const d = x + 1 + width * z;
        indices.push(a, b, d);
        indices.push(b, c, d);
      }
    }

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({ color: 0x228B22, roughness: 0.8, metalness: 0.2 });
    const terrain = new THREE.Mesh(geometry, material);
    terrain.position.set(gridX * tileSize, 0, gridZ * tileSize);
    terrain.castShadow = false;
    terrain.receiveShadow = true;
    scene.add(terrain);

    tiles.set(key, { terrain, pending: false });
    console.log(`Added synchronous tile ${key}`);
  } catch (error) {
    console.error(`Error generating tile ${key} synchronously:`, error);
    tiles.delete(key);
  }
}

function updateTerrain(playerPos) {
  try {
    if (!playerPos || !Number.isFinite(playerPos.x) || !Number.isFinite(playerPos.z)) {
      console.warn('Invalid player position:', playerPos);
      return;
    }

    const now = performance.now();
    if (now - lastUpdateTime < minUpdateInterval) return;
    lastUpdateTime = now;

    const tileSize = getSetting('terrain.tileSize');
    const renderDistance = isFirstPerson ?
      getSetting('terrain.firstPerson.renderDistance') :
      getSetting('terrain.thirdPerson.renderDistance');
    const gridX = Math.round(playerPos.x / tileSize);
    const gridZ = Math.round(playerPos.z / tileSize);

    if (gridX === lastGridX && gridZ === lastGridZ) return;
    lastGridX = gridX;
    lastGridZ = gridZ;

    console.log(`Updating terrain grid: ${gridX},${gridZ}, playerPos:`, playerPos, `renderDistance: ${renderDistance}`);
    if (terrainWorker) {
      streamTiles(gridX, gridZ);
    } else {
      initializeTilesSynchronously(gridX, gridZ);
    }

    for (const [key, { terrain, pending }] of tiles) {
      const [x, z] = key.split(',').map(Number);
      if (Math.abs(x - gridX) > renderDistance || Math.abs(z - gridZ) > renderDistance) {
        if (terrain) {
          scene.remove(terrain);
          terrain.geometry.dispose();
          terrain.material.dispose();
        }
        tiles.delete(key);
        console.log(`Removed tile ${key}`);
      }
    }

    console.log('Terrain update:', {
      tiles: tiles.size,
      pending: Array.from(tiles.values()).filter(t => t.pending).length,
      playerPos,
      grid: `${gridX},${gridZ}`,
      renderDistance,
    });
  } catch (error) {
    console.error('Error in updateTerrain:', error);
  }
}

export { initTerrain, updateTerrain, setPerspective };
