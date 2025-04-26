// src/debugKeys.js
import { scene, camera, updateScene } from './scene.js';
import { getSetting, setSetting } from './settings.js';
import * as THREE from 'three';

export function initDebugKeys() {
  window.addEventListener('keydown', (event) => {
    if (event.key === 't') {
      console.log('Debug: Setting sun to noon');
      setSetting('skybox.sun.debugFixedPosition', false);
      setSetting('skybox.sun.timeOfDay', 12);
      updateScene();
    } else if (event.key === 'y') {
      console.log('Debug: Using fixed sun position');
      setSetting('skybox.sun.debugFixedPosition', true);
      setSetting('skybox.sun.timeOfDay', null);
      updateScene();
    } else if (event.key === 'l') {
      console.log('Debug: Looking at sun');
      const sunPos = scene.children.find(c => (c.type === 'Mesh' || c.type === 'Sprite') && c.material?.color?.getHex() === getSetting('skybox.sun.color'))?.position;
      if (sunPos) {
        camera.lookAt(sunPos);
        const viewDir = new THREE.Vector3();
        camera.getWorldDirection(viewDir);
        console.log('Camera looking at sun:', {
          sunPos,
          cameraPos: camera.position,
          viewDir: { x: viewDir.x, y: viewDir.y, z: viewDir.z }
        });
      } else {
        console.warn('Sun mesh/sprite not found');
      }
    } else if (event.key === 's') {
      const useSprite = !getSetting('skybox.sun.useSprite');
      console.log('Debug: Toggling sun to', useSprite ? 'sprite' : 'mesh');
      setSetting('skybox.sun.useSprite', useSprite);
      scene.remove(scene.children.find(c => (c.type === 'Mesh' || c.type === 'Sprite') && c.material?.color?.getHex() === getSetting('skybox.sun.color')));
      scene.remove(scene.children.find(c => c.type === 'DirectionalLight'));
      const newSkybox = initSkybox(scene, new Date(), camera);
      skybox.success = newSkybox.success;
      skybox.updateSunPosition = newSkybox.updateSunPosition;
      skybox.update = newSkybox.update;
    } else if (event.key === 'x') {
      const enabled = !getSetting('skybox.enabled');
      console.log('Debug: Toggling skybox', enabled ? 'on' : 'off');
      setSetting('skybox.enabled', enabled);
      if (enabled) {
        const newSkybox = initSkybox(scene, new Date(), camera);
        skybox.success = newSkybox.success;
        skybox.updateSunPosition = newSkybox.updateSunPosition;
        skybox.update = newSkybox.update;
      } else {
        scene.background = new THREE.Color(getSetting('skybox.fallbackColor'));
      }
    } else if (event.key === 'h') {
      const currentHour = getSetting('skybox.sun.timeOfDay') || 0;
      const newHour = (currentHour + 6) % 24;
      console.log('Debug: Setting time of day to', newHour);
      setSetting('skybox.sun.timeOfDay', newHour);
      setSetting('skybox.sun.debugFixedPosition', false);
      updateScene();
    } else if (event.key === 'd') {
      const currentDistance = getSetting('skybox.sun.distance') || 5000;
      const newDistance = currentDistance === 5000 ? 1000 : 5000;
      console.log('Debug: Setting sun distance to', newDistance);
      setSetting('skybox.sun.distance', newDistance);
      updateScene();
    } else if (event.key === 'p') {
      console.log('Debug: Logging sun and light positions');
      const sunPos = scene.children.find(c => (c.type === 'Mesh' || c.type === 'Sprite') && c.material?.color?.getHex() === getSetting('skybox.sun.color'))?.position;
      const light = scene.children.find(c => c.type === 'DirectionalLight');
      console.log('Current positions:', {
        sun: sunPos ? { x: sunPos.x, y: sunPos.y, z: sunPos.z } : 'not found',
        light: light ? { position: light.position, intensity: light.intensity } : 'not found',
      });
    } else if (event.key === 'v') {
      const disableCulling = !getSetting('skybox.sun.disableFrustumCulling');
      console.log('Debug: Toggling frustum culling', disableCulling ? 'off' : 'on');
      setSetting('skybox.sun.disableFrustumCulling', disableCulling);
      const sunMesh = scene.children.find(c => (c.type === 'Mesh' || c.type === 'Sprite') && c.material?.color?.getHex() === getSetting('skybox.sun.color'));
      if (sunMesh) {
        sunMesh.frustumCulled = !disableCulling;
        console.log('Sun frustum culling updated:', sunMesh.frustumCulled);
      }
    } else if (event.key === 'f') {
      const currentOpacity = getSetting('fog.sunFogOpacity') || 0.8;
      const opacities = [0.2, 0.5, 0.8, 1.0];
      const newOpacity = opacities[(opacities.indexOf(currentOpacity) + 1) % opacities.length];
      console.log('Debug: Setting fog sun opacity to', newOpacity);
      setSetting('fog.sunFogOpacity', newOpacity);
      const sunMesh = scene.children.find(c => (c.type === 'Mesh' || c.type === 'Sprite') && c.material?.color?.getHex() === getSetting('skybox.sun.color'));
      if (sunMesh) {
        sunMesh.material.opacity = newOpacity;
        console.log('Sun opacity updated:', newOpacity);
      }
      const cloudGroup = scene.children.find(c => c.type === 'Group' && c.children.some(child => child.type === 'Sprite'));
      if (cloudGroup) {
        const cloudOpacity = getSetting('skybox.clouds.opacity') * newOpacity;
        cloudGroup.children.forEach(sprite => {
          sprite.material.opacity = cloudOpacity;
        });
        console.log('Cloud opacity updated:', cloudOpacity);
      }
    } else if (event.key === 'r') {
      const currentRenderOrder = scene.children.find(c => (c.type === 'Mesh' || c.type === 'Sprite') && c.material?.color?.getHex() === getSetting('skybox.sun.color'))?.renderOrder || -10000;
      const renderOrders = [-10000, -1000, -100, -1];
      const newRenderOrder = renderOrders[(renderOrders.indexOf(currentRenderOrder) + 1) % renderOrders.length];
      console.log('Debug: Setting render order to', newRenderOrder);
      const sunMesh = scene.children.find(c => (c.type === 'Mesh' || c.type === 'Sprite') && c.material?.color?.getHex() === getSetting('skybox.sun.color'));
      if (sunMesh) {
        sunMesh.renderOrder = newRenderOrder;
        console.log('Sun render order updated:', newRenderOrder);
      }
      const cloudGroup = scene.children.find(c => c.type === 'Group' && c.children.some(child => child.type === 'Sprite'));
      if (cloudGroup) {
        cloudGroup.children.forEach(sprite => {
          sprite.renderOrder = newRenderOrder;
        });
        console.log('Cloud render order updated:', newRenderOrder);
      }
    } else if (event.key === 'c') {
      console.log('Debug: Logging cloud positions');
      const cloudGroup = scene.children.find(c => c.type === 'Group' && c.children.some(child => child.type === 'Sprite'));
      if (cloudGroup) {
        const tileSize = getSetting('terrain.tileSize') || 200;
        const positions = cloudGroup.children.map(sprite => ({
          position: sprite.position,
          grid: {
            x: Math.round(sprite.position.x / tileSize),
            z: Math.round(sprite.position.z / tileSize),
          },
          quaternion: sprite.quaternion,
        }));
        console.log('Cloud positions:', positions);
      } else {
        console.warn('Cloud group not found');
      }
    } else if (event.key === 'k') {
      console.log('Debug: Toggling cloud visibility');
      const cloudGroup = scene.children.find(c => c.type === 'Group' && c.children.some(child => child.type === 'Sprite'));
      if (cloudGroup) {
        cloudGroup.visible = !cloudGroup.visible;
        console.log('Cloud visibility:', cloudGroup.visible);
      } else {
        console.warn('Cloud group not found');
      }
    } else if (event.key === 'b') {
      console.log('Debug: Toggling billboard world alignment');
      const cloudGroup = scene.children.find(c => c.type === 'Group' && c.children.some(child => child.type === 'Sprite'));
      if (cloudGroup) {
        const aligned = !cloudGroup.children[0]?.worldAligned;
        cloudGroup.children.forEach(sprite => {
          sprite.worldAligned = aligned; // Custom property
          if (aligned) {
            sprite.quaternion.set(0, 0, 0, 1);
            sprite.lookAt(sprite.position.clone().add(new THREE.Vector3(0, 0, -1)));
          }
        });
        console.log('Cloud world alignment:', aligned ? 'world-fixed' : 'camera-facing');
      } else {
        console.warn('Cloud group not found');
      }
    }
  });
}
