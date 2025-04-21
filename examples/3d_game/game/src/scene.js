// src/scene.js
import * as THREE from 'three';

console.log('THREE.WebGLRenderer in scene.js:', THREE.WebGLRenderer);
console.log('Three.js version:', THREE.REVISION);

let scene, camera, renderer, clock;

function initScene() {
  console.log('THREE.Scene in initScene:', THREE.Scene);
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x87ceeb);
  console.log('Scene created:', scene);

  const width = typeof window !== 'undefined' ? window.innerWidth : 800;
  const height = typeof window !== 'undefined' ? window.innerHeight : 600;
  camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
  console.log('Camera created:', camera);

  let canvas = typeof document !== 'undefined' ? document.getElementById('gameCanvas') : undefined;
  if (!canvas) {
    console.error('Canvas element #gameCanvas not found in DOM');
    throw new Error('Canvas element #gameCanvas not found');
  }

  // Try manual WebGL 2 context creation
  let gl = null;
  try {
    gl = canvas.getContext('webgl2', { antialias: true });
    if (!gl) {
      console.error('WebGL 2 context creation failed');
      throw new Error('WebGL 2 is not supported by this environment');
    }
    console.log('Manual WebGL 2 context created:', gl.getParameter(gl.VERSION));
  } catch (error) {
    console.error('Failed to create WebGL 2 context:', error);
    throw new Error('WebGL 2 context creation failed: ' + error.message);
  }

  // Initialize renderer with manual context
  try {
    renderer = new THREE.WebGLRenderer({ canvas, context: gl, antialias: true });
    renderer.setSize(width, height);
    renderer.setClearColor(0x87ceeb, 1);
  } catch (error) {
    console.error('Failed to initialize WebGLRenderer:', error);
    throw new Error('WebGLRenderer initialization failed: ' + error.message);
  }

  // Verify WebGL 2 context
  const glVersion = gl.getParameter(gl.VERSION);
  console.log('WebGL context initialized:', glVersion);
  if (!glVersion.includes('WebGL 2')) {
    console.error('WebGL 2 not detected. Context version:', glVersion);
    throw new Error('WebGL 2 is required but not supported');
  }

  // Add lighting
  scene.add(new THREE.AmbientLight(0x404040, 1));
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.7);
  directionalLight.position.set(0, 100, 50);
  scene.add(directionalLight);
  console.log('Lighting added:', scene.children.filter(c => c.type === 'Light'));

  clock = new THREE.Clock();
  camera.position.set(0, 50, 100);
  console.log('Camera position:', camera.position);

  if (typeof window !== 'undefined') {
    window.addEventListener('resize', () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
      console.log('Window resized:', { width: window.innerWidth, height: window.innerHeight });
    });
  }

  if (typeof document === 'undefined') {
    global.scene = scene;
    global.camera = camera;
    global.renderer = renderer;
    global.clock = clock;
  }

  console.log('Scene initialized with sky blue background and lighting');
  console.log('Scene children after init:', scene.children.map(c => c.type));
  console.log('Renderer info:', renderer.info);
}

export { initScene, scene, camera, renderer, clock };
