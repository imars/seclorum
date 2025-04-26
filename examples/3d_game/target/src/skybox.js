// src/skybox.js
import * as THREE from 'three';
import { getSetting } from './settings.js';
import { getSunPosition } from './utils/sunPosition.js';
import { initClouds } from './utils/billboards.js';

export function initSkybox(scene, time = new Date(), camera) {
  console.log('Initializing skybox');
  let textureCube = null;
  let sunMesh = null;
  let directionalLight = null;
  let cloudGroup = null;
  let updateClouds = null;

  function updateSunPosition(currentTime = new Date()) {
    if (!sunMesh || !directionalLight) {
      console.warn('Cannot update sun position: sunMesh or directionalLight not initialized');
      return;
    }
    const debugFixedPosition = getSetting('skybox.sun.debugFixedPosition') || false;
    let sunPosition;
    let sunDirection;

    try {
      if (debugFixedPosition) {
        const fixedPos = getSetting('skybox.sun.position') || { x: 100, y: 100, z: -100 };
        sunPosition = new THREE.Vector3(fixedPos.x, fixedPos.y, fixedPos.z);
        sunDirection = sunPosition.clone().normalize();
      } else {
        const latitude = getSetting('skybox.sun.latitude') || 0;
        const longitude = getSetting('skybox.sun.longitude') || 0;
        const sunDistance = getSetting('skybox.sun.distance') || 1000;

        sunDirection = getSunPosition(currentTime, latitude, longitude);
        sunPosition = sunDirection.multiplyScalar(sunDistance);
      }

      directionalLight.position.copy(sunPosition);
      directionalLight.target.position.set(0, 0, 0);
      directionalLight.target.updateMatrixWorld();
      sunMesh.position.copy(sunPosition);

      if (sunMesh.geometry && sunMesh.geometry.boundingSphere) {
        sunMesh.geometry.boundingSphere.radius = getSetting('skybox.sun.spriteScale') || 2000;
        sunMesh.geometry.boundingSphere.center.copy(sunPosition);
      }

      if (camera) {
        const vector = sunPosition.clone().project(camera);
        const isInView = (vector.x >= -1 && vector.x <= 1 && vector.y >= -1 && vector.y <= 1 && vector.z < 1);
        const depth = camera.position.distanceTo(sunPosition);
        console.log('Sun updated:', {
          time: currentTime.toISOString(),
          position: { x: sunPosition.x, y: sunPosition.y, z: sunPosition.z },
          direction: { x: sunDirection.x, y: sunDirection.y, z: sunDirection.z },
          screenPos: { x: vector.x, y: vector.y, z: vector.z },
          isInView,
          visible: sunMesh.visible,
          frustumCulled: sunMesh.frustumCulled,
          renderOrder: sunMesh.renderOrder,
          depthTest: sunMesh.material.depthTest,
          depth: depth.toFixed(2),
          lightPosition: { x: directionalLight.position.x, y: directionalLight.position.y, z: directionalLight.position.z },
        });
      }
    } catch (error) {
      console.error('Error updating sun position:', error);
    }

    return sunPosition;
  }

  if (getSetting('skybox.enabled')) {
    try {
      const skyboxTextures = getSetting('skybox.textures');
      if (skyboxTextures) {
        const loader = new THREE.CubeTextureLoader();
        const textures = [
          skyboxTextures.posx,
          skyboxTextures.negx,
          skyboxTextures.posy,
          skyboxTextures.negy,
          skyboxTextures.posz,
          skyboxTextures.negz,
        ];

        textures.forEach((tex) => {
          const img = new Image();
          img.src = tex;
          img.onload = () => console.log(`Texture ${tex} accessible`);
          img.onerror = () => console.error(`Texture ${tex} not accessible`);
        });

        textureCube = loader.load(
          textures,
          () => console.log('Skybox textures loaded successfully:', textures),
          undefined,
          (error) => {
            console.error('Skybox texture loading failed:', error.message, 'Textures:', textures);
            throw new Error(`Failed to load skybox textures: ${error.message}`);
          }
        );
        textureCube.colorSpace = THREE.SRGBColorSpace;
        scene.background = textureCube;
        console.log('Skybox textures applied');
      } else {
        console.warn('Skybox textures not found in settings');
      }
    } catch (error) {
      console.error('Skybox texture initialization failed:', error);
      const fallbackColor = getSetting('skybox.fallbackColor') || 0x87ceeb;
      scene.background = new THREE.Color(fallbackColor);
      console.log(`Applied fallback background color: ${fallbackColor.toString(16)}`);
    }
  } else {
    const fallbackColor = getSetting('skybox.fallbackColor') || 0x87ceeb;
    scene.background = new THREE.Color(fallbackColor);
    console.log('Skybox disabled, applied fallback color');
  }

  try {
    const cloudInit = initClouds(scene);
    if (cloudInit.success) {
      cloudGroup = cloudInit.cloudGroup;
      updateClouds = cloudInit.update;
      console.log('Clouds added to scene');
    } else {
      console.warn('Cloud initialization failed');
    }
  } catch (error) {
    console.error('Cloud initialization failed:', error);
  }

  try {
    const sunSettings = getSetting('skybox.sun');
    directionalLight = new THREE.DirectionalLight(0xffffff, sunSettings.intensity);
    directionalLight.target = new THREE.Object3D();
    scene.add(directionalLight);
    scene.add(directionalLight.target);

    if (sunSettings.useSprite) {
      const textureLoader = new THREE.TextureLoader();
      const sunTexture = textureLoader.load(
        sunSettings.spriteTexture,
        () => console.log(`Sun sprite texture ${sunSettings.spriteTexture} loaded`),
        undefined,
        (error) => {
          console.error(`Sun sprite texture ${sunSettings.spriteTexture} failed to load:`, error);
          throw new Error(`Sun sprite texture load failed: ${error.message}`);
        }
      );
      sunTexture.colorSpace = THREE.SRGBColorSpace;

      const sunFogOpacity = getSetting('fog.sunFogOpacity') || 1.0;
      const sunMaterial = new THREE.SpriteMaterial({
        map: sunTexture,
        color: sunSettings.color,
        transparent: true,
        opacity: sunFogOpacity,
        fog: false,
        depthTest: false,
        depthWrite: false,
      });
      sunMesh = new THREE.Sprite(sunMaterial);
      sunMesh.scale.set(sunSettings.spriteScale, sunSettings.spriteScale, 1);
    } else {
      const sunGeometry = new THREE.SphereGeometry(sunSettings.radius, 32, 32);
      const sunFogOpacity = getSetting('fog.sunFogOpacity') || 1.0;
      const sunMaterial = new THREE.MeshBasicMaterial({
        color: sunSettings.color,
        fog: false,
        depthTest: false,
        depthWrite: false,
        transparent: true,
        opacity: sunFogOpacity,
      });
      sunMesh = new THREE.Mesh(sunGeometry, sunMaterial);
    }

    sunMesh.visible = true;
    if (sunSettings.disableFrustumCulling) {
      sunMesh.frustumCulled = false;
      console.log('Sun frustum culling disabled');
    }

    sunMesh.renderOrder = -10000;
    scene.add(sunMesh);
    console.log('Sun mesh added:', {
      visible: sunMesh.visible,
      position: sunMesh.position,
      frustumCulled: sunMesh.frustumCulled,
      depthTest: sunMesh.material.depthTest,
      opacity: sunMesh.material.opacity,
      renderOrder: sunMesh.renderOrder,
    });

    updateSunPosition(time);
  } catch (error) {
    console.error('Sun initialization failed:', error);
  }

  return {
    success: textureCube !== null || (sunMesh && directionalLight),
    updateSunPosition,
    update: () => {
      updateSunPosition(new Date());
      if (updateClouds) updateClouds(camera);
    }
  };
}
