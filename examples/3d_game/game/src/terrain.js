import * as THREE from 'three';
import { createNoise2D } from 'simplex-noise';

let terrain;

function initTerrain() {
  const noise2D = createNoise2D();
  const geometry = new THREE.PlaneGeometry(100, 100, 50, 50);
  for (let i = 0; i < geometry.attributes.position.array.length; i += 3) {
    const x = geometry.attributes.position.array[i];
    const y = geometry.attributes.position.array[i + 1];
    const z = noise2D(x / 10, y / 10) * 5;
    geometry.attributes.position.array[i + 2] = z;
  }
  geometry.computeVertexNormals();
  const material = new THREE.MeshPhongMaterial({ color: 0x888888 });
  terrain = new THREE.Mesh(geometry, material);
  terrain.rotation.x = -Math.PI / 2;

  // Assign to global only in Node.js (e.g., for Jest tests)
  if (typeof document === 'undefined') {
    global.terrain = terrain;
  }

  return terrain;
}

export { initTerrain };
