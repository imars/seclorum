// src/scene.js
import * as THREE from 'three';
import { getSetting } from './settings.js';
import { initSkybox } from './skybox.js';
import { initVolumetricFog } from './utils/volumetricFog.js';

console.log('Three.js version:', THREE.REVISION);

let scene, camera, renderer, clock;
let isFirstPerson = false;
let skybox, fogComposer, updateFog;

function initScene() {
  console.log('Initializing scene');
  try {
    const canvas = document.getElementById('gameCanvas');
    if (!canvas) {
      throw new Error('Canvas element #gameCanvas not found');
    }

    scene = new THREE.Scene();

    renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: getSetting('renderer.antialias'),
      context: canvas.getContext('webgl2', { alpha: false }) || canvas.getContext('webgl'),
    });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.shadowMap.enabled = false;
    renderer.sortObjects = true;
    console.log('Renderer initialized:', {
      webgl2: renderer.getContext().constructor.name === 'WebGL2RenderingContext',
      sortObjects: renderer.sortObjects,
    });

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

    skybox = initSkybox(scene, new Date(), camera);
    console.log('Skybox initialization:', skybox.success ? 'successful' : 'failed');

    const fogInit = initVolumetricFog(scene, camera, renderer);
    fogComposer = fogInit.composer;
    updateFog = fogInit.updateFog;
    console.log('Volumetric fog initialization:', fogInit.success ? 'successful' : 'failed', { composer: !!fogComposer });

    updateFogSettings();

    const ambientLight = new THREE.AmbientLight(0x404040, 1.5);
    scene.add(ambientLight);

    clock = new THREE.Clock();
    clock.start();

    window.addEventListener('resize', () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
      if (fogComposer) fogComposer.setSize(window.innerWidth, window.innerHeight);
    });

    console.log('Scene initialized:', {
      scene: !!scene,
      camera: !!camera,
      renderer: !!renderer,
      clock: !!clock,
      shadowMap: renderer.shadowMap.enabled,
      antialias: renderer.antialias,
      fog: !!scene.fog,
      skybox: !!scene.background,
      volumetricFog: !!fogComposer,
      sortObjects: renderer.sortObjects,
    });

    return { scene, camera, renderer, clock, fogComposer, updateScene };
  } catch (error) {
    console.error('Error in initScene:', error);
    return { scene: null, camera: null, renderer: null, clock: null, fogComposer: null, updateScene: () => {} };
  }
}

function updateFogSettings(newIsFirstPerson) {
  if (newIsFirstPerson !== undefined) {
    isFirstPerson = newIsFirstPerson;
  }
  if (!camera) {
    console.warn('Cannot update fog: camera undefined');
    return;
  }
  if (getSetting('fog.enabled')) {
    const fogSettings = isFirstPerson ? getSetting('fog.firstPerson') : getSetting('fog.thirdPerson');
    scene.fog = new THREE.Fog(getSetting('skybox.fallbackColor') || 0x87ceeb, fogSettings.near, fogSettings.far);
    camera.far = fogSettings.far;
    camera.updateProjectionMatrix();
    console.log(`Normal fog updated for ${isFirstPerson ? 'first-person' : 'third-person'}:`, {
      near: fogSettings.near,
      far: fogSettings.far,
      color: scene.fog.color.getHex()
    });
  } else {
    scene.fog = null;
    camera.far = getSetting('camera.far');
    camera.updateProjectionMatrix();
    console.log('Normal fog disabled');
  }
}

function updateScene() {
  if (skybox && skybox.success && skybox.update) {
    skybox.update();
    if (updateFog) {
      updateFog();
    }
  } else {
    console.warn('Skybox not initialized or update not available');
  }
}

export { initScene, scene, camera, renderer, clock, fogComposer, updateFogSettings, updateScene };
