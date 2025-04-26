// src/utils/billboards.js
import * as THREE from 'three';
import { getSetting } from '../settings.js';

class Billboard {
  constructor(scene, texture, position, scale, materialOptions = {}) {
    this.scene = scene;
    this.sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      ...materialOptions,
    }));
    this.sprite.position.copy(position);
    this.sprite.scale.set(scale, scale, 1);
    this.worldAligned = false; // Default: camera-facing
    this.scene.add(this.sprite);
  }

  setPosition(position) {
    this.sprite.position.copy(position);
  }

  setScale(scale) {
    this.sprite.scale.set(scale, scale, 1);
  }

  setWorldAligned(aligned) {
    this.worldAligned = aligned;
    if (aligned) {
      // Align to world up vector (face forward, e.g., along z-axis)
      this.sprite.quaternion.set(0, 0, 0, 1); // Reset rotation
      this.sprite.lookAt(this.sprite.position.clone().add(new THREE.Vector3(0, 0, -1))); // Face z-negative
    }
  }

  update(camera) {
    if (!this.worldAligned) {
      // Default sprite behavior: face camera
      this.sprite.quaternion.copy(camera.quaternion);
    }
    // Else, keep fixed world orientation
  }

  setRenderOrder(order) {
    this.sprite.renderOrder = order;
  }

  setOpacity(opacity) {
    this.sprite.material.opacity = opacity;
  }

  getSprite() {
    return this.sprite;
  }
}

class Cloud extends Billboard {
  constructor(scene, position, scale) {
    const textureLoader = new THREE.TextureLoader();
    const cloudTexture = textureLoader.load(
      getSetting('skybox.clouds.texture'),
      () => console.log(`Cloud texture ${getSetting('skybox.clouds.texture')} loaded`),
      undefined,
      (error) => {
        console.error(`Cloud texture ${getSetting('skybox.clouds.texture')} failed to load:`, error);
        throw new Error(`Cloud texture load failed: ${error.message}`);
      }
    );
    cloudTexture.colorSpace = THREE.SRGBColorSpace;

    const sunFogOpacity = getSetting('fog.sunFogOpacity') || 1.0;
    super(scene, cloudTexture, position, scale, {
      opacity: getSetting('skybox.clouds.opacity') * sunFogOpacity,
      fog: false,
      depthWrite: false,
      depthTest: true,
    });

    this.setRenderOrder(-10000);
    this.setWorldAligned(true); // Fix orientation to world
  }
}

export function initClouds(scene) {
  console.log('Attempting cloud initialization');
  try {
    const cloudSettings = getSetting('skybox.clouds');
    console.log('Cloud settings:', cloudSettings);
    if (!cloudSettings.enabled) {
      console.log('Clouds disabled');
      return { success: true, cloudGroup: null };
    }

    const cloudGroup = new THREE.Group();
    const tileSize = getSetting('terrain.tileSize') || 200;
    const gridExtent = 20; // ±4000 units
    const minHeight = 50;
    const maxHeight = 200;

    const clouds = [];
    for (let i = 0; i < cloudSettings.count; i++) {
      const gridX = Math.floor(THREE.MathUtils.randFloat(-gridExtent, gridExtent));
      const gridZ = Math.floor(THREE.MathUtils.randFloat(-gridExtent, gridExtent));
      const x = gridX * tileSize + THREE.MathUtils.randFloat(-tileSize / 2, tileSize / 2);
      const z = gridZ * tileSize + THREE.MathUtils.randFloat(-tileSize / 2, tileSize / 2);
      const y = THREE.MathUtils.randFloat(minHeight, maxHeight);
      const position = new THREE.Vector3(x, y, z);
      const size = THREE.MathUtils.randFloat(cloudSettings.sizeMin, cloudSettings.sizeMax);
      const cloud = new Cloud(scene, position, size);
      cloudGroup.add(cloud.getSprite());
      clouds.push(cloud);
    }

    scene.add(cloudGroup);
    console.log('Clouds initialized:', {
      count: cloudSettings.count,
      opacity: cloudSettings.opacity * (getSetting('fog.sunFogOpacity') || 1.0),
      renderOrder: -10000,
      gridExtent: [-gridExtent * tileSize, gridExtent * tileSize],
    });

    return {
      success: true,
      cloudGroup,
      update: (camera) => {
        clouds.forEach(cloud => cloud.update(camera));
      }
    };
  } catch (error) {
    console.error('Cloud initialization failed:', error);
    return { success: false, cloudGroup: null, update: () => {} };
  }
}
