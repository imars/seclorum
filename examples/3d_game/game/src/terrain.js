// src/terrain.js
import * as THREE from 'three';
import { scene, camera, renderer } from './scene.js';
import { createNoise2D } from 'simplex-noise';

const noise2D = createNoise2D();

function initTerrain() {
  console.log('Starting initTerrain');
  try {
    // Precompute height data like the example
    const width = 17, height = 17; // 16x16 segments = 17x17 vertices
    const data = new Float32Array(width * height);
    for (let i = 0; i < data.length; i++) {
      const x = (i % width) - width / 2;
      const z = Math.floor(i / width) - height / 2;
      data[i] = noise2D(x / 10, z / 10) * 10; // Match example's scale
    }

    const geometry = new THREE.PlaneGeometry(200, 200, 16, 16);
    geometry.rotateX(-Math.PI / 2); // Rotate immediately like example
    const vertices = geometry.attributes.position.array;

    for (let i = 0, j = 0, l = vertices.length; i < l; i++, j += 3) {
      vertices[j + 1] = data[i]; // Apply precomputed heights
    }
    geometry.attributes.position.needsUpdate = true;

    const material = new THREE.MeshBasicMaterial({ color: 0x228B22 }); // Simplify material
    const terrain = new THREE.Mesh(geometry, material);
    terrain.position.set(0, 0, 0);
    scene.add(terrain);

    const wireframe = new THREE.WireframeGeometry(geometry);
    const wireframeMesh = new THREE.LineSegments(wireframe, new THREE.LineBasicMaterial({ color: 0xffffff }));
    wireframeMesh.position.set(0, 0, 0);
    scene.add(wireframeMesh);

    console.log('Terrain geometry vertices:', vertices.length / 3, 'widthSegments:', geometry.parameters.widthSegments, 'heightSegments:', geometry.parameters.heightSegments);
    console.log('Sample vertex positions:', vertices.slice(0, 15));
    console.log('Sample height data:', data.slice(0, 5));
    if (camera) {
      const frustum = new THREE.Frustum();
      frustum.setFromProjectionMatrix(new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse));
      const boundingBox = new THREE.Box3().setFromObject(terrain);
      console.log('Terrain in frustum:', frustum.intersectsBox(boundingBox));
    } else {
      console.warn('Camera not initialized');
    }

    if (renderer && camera && scene) {
      renderer.render(scene, camera);
      console.log('Terrain render attempted');
    } else {
      console.warn('Renderer, camera, or scene not initialized');
    }

    console.log('Terrain initialized:', {
      vertices: vertices.length / 3,
      inScene: scene.children.includes(terrain),
      terrainPosition: terrain.position,
      cameraPosition: camera ? camera.position : 'Not initialized',
    });

    if (typeof document === 'undefined') {
      global.terrain = terrain;
    }
    return terrain;
  } catch (error) {
    console.error('Error in initTerrain:', error);
    throw error;
  }
}

export { initTerrain };
