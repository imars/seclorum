// src/terrainWorker.js
import { createNoise2D } from 'simplex-noise';

console.log('Terrain worker initialized');

const noise2D = createNoise2D();

self.onmessage = (e) => {
  console.log('Worker received message:', e.data);
  const { gridX, gridZ, tileSize, segments, noiseScale, noiseAmplitude } = e.data;
  try {
    if (!Number.isFinite(gridX) || !Number.isFinite(gridZ) || !Number.isFinite(tileSize) || !Number.isFinite(segments) || !Number.isFinite(noiseScale) || !Number.isFinite(noiseAmplitude)) {
      throw new Error('Invalid input parameters');
    }
    const geometryData = generateTileGeometry(gridX, gridZ, tileSize, segments, noiseScale, noiseAmplitude);
    if (!geometryData.vertices.length || !geometryData.indices.length) {
      throw new Error('Generated empty geometry');
    }
    self.postMessage({ gridX, gridZ, geometryData, error: null });
  } catch (error) {
    console.error('Worker error:', error);
    self.postMessage({ gridX, gridZ, geometryData: null, error: error.message });
  }
};

function generateTileGeometry(gridX, gridZ, tileSize, segments, noiseScale, noiseAmplitude) {
  const width = segments + 1;
  const vertices = new Float32Array(width * width * 3);
  const data = new Float32Array(width * width);

  for (let i = 0; i < data.length; i++) {
    const localX = (i % width) * (tileSize / segments) - tileSize / 2;
    const localZ = Math.floor(i / width) * (tileSize / segments) - tileSize / 2;
    const globalX = localX + gridX * tileSize;
    const globalZ = localZ + gridZ * tileSize;
    const height = noise2D(globalX / noiseScale, globalZ / noiseScale) * noiseAmplitude;
    if (!Number.isFinite(height)) {
      throw new Error(`Invalid height at ${globalX},${globalZ}: ${height}`);
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

  return { vertices, indices };
}
