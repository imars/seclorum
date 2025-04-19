import * as THREE from 'three';

console.log('THREE.WebGLRenderer in scene.js:', THREE.WebGLRenderer);

let scene, camera, renderer, clock;
let width = 800;
let height = 600;

function initScene() {
  console.log('THREE.Scene in initScene:', THREE.Scene);
  scene = new THREE.Scene();
  console.log('scene after creation:', scene);
  camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
  renderer = new THREE.WebGLRenderer({
    canvas: typeof document !== 'undefined' ? document.getElementById('gameCanvas') : undefined,
  });
  console.log('Renderer after creation:', renderer);
  renderer.setSize(width, height);
  scene.add(new THREE.AmbientLight(0x404040));
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
  directionalLight.position.set(0, 100, 50);
  scene.add(directionalLight);
  clock = new THREE.Clock();

  // Assign to global only in Node.js (e.g., for Jest tests)
  if (typeof document === 'undefined') {
    global.scene = scene;
    global.camera = camera;
    global.renderer = renderer;
    global.clock = clock;
  }

  console.log('Scene initialized');
}

export { initScene, scene, camera, renderer, clock };
