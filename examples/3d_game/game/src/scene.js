// src/scene.js
import * as THREE from 'three';
import { getSetting } from './settings.js';

console.log('Three.js version:', THREE.REVISION);

let scene, camera, renderer, clock;
let isFirstPerson = false;

function initScene() {
  console.log('Initializing scene');
  try {
    const canvas = document.getElementById('gameCanvas');
    if (!canvas) {
      throw new Error('Canvas element #gameCanvas not found');
    }

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x87ceeb);

    const farPlane = getSetting('fog.enabled') ?
      (isFirstPerson ? getSetting('fog.firstPerson.far') : getSetting('fog.thirdPerson.far')) :
      getSetting('camera.far');
    camera = new THREE.PerspectiveCamera(
      getSetting('camera.fov'),
      window.innerWidth / window.innerHeight,
      getSetting('camera.near'),
      farPlane
    );
    const cameraPos = getSetting('camera.initialPosition') || { x: 0, y: 30, z: 50 };
    camera.position.set(cameraPos.x, cameraPos.y, cameraPos.z);

    renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: getSetting('renderer.antialias'),
      context: canvas.getContext('webgl2', { alpha: false }),
    });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.shadowMap.enabled = false;

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.7);
    directionalLight.position.set(50, 100, 50);
    scene.add(directionalLight);

    const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
    scene.add(ambientLight);

    clock = new THREE.Clock();
    clock.start();

    window.addEventListener('resize', () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    });

    updateFog(); // Moved after camera initialization

    console.log('Scene initialized:', {
      scene: !!scene,
      camera: !!camera,
      renderer: !!renderer,
      clock: !!clock,
      shadowMap: renderer.shadowMap.enabled,
      antialias: renderer.antialias,
      fog: !!scene.fog,
    });

    return { scene, camera, renderer, clock };
  } catch (error) {
    console.error('Error in initScene:', error);
    return { scene: null, camera: null, renderer: null, clock: null };
  }
}

function updateFog(newIsFirstPerson) {
  if (newIsFirstPerson !== undefined) {
    isFirstPerson = newIsFirstPerson;
  }
  if (!camera) {
    console.warn('Cannot update fog: camera undefined');
    return;
  }
  if (getSetting('fog.enabled')) {
    const fogSettings = isFirstPerson ? getSetting('fog.firstPerson') : getSetting('fog.thirdPerson');
    scene.fog = new THREE.Fog(0x87ceeb, fogSettings.near, fogSettings.far);
    camera.far = fogSettings.far;
    camera.updateProjectionMatrix();
    console.log(`Fog updated for ${isFirstPerson ? 'first-person' : 'third-person'}:`, fogSettings);
  } else {
    scene.fog = null;
    camera.far = getSetting('camera.far');
    camera.updateProjectionMatrix();
    console.log('Fog disabled');
  }
}

export { initScene, scene, camera, renderer, clock, updateFog };
