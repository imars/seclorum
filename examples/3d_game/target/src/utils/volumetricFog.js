// src/utils/volumetricFog.js
import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { getSetting } from '../settings.js';

export function initVolumetricFog(scene, camera, renderer) {
  console.log('Attempting volumetric fog initialization');
  try {
    if (!renderer) throw new Error('Renderer not provided');
    if (!EffectComposer || !RenderPass || !ShaderPass) {
      throw new Error('Three.js postprocessing addons missing');
    }
    console.log('Postprocessing addons verified:', { EffectComposer: !!EffectComposer });

    const fogSettings = getSetting('volumetricFog');
    console.log('Fog settings:', fogSettings);
    if (!fogSettings.enabled) {
      console.log('Volumetric fog disabled');
      return { success: true, composer: null, updateFog: () => {} };
    }

    const composer = new EffectComposer(renderer);
    const renderPass = new RenderPass(scene, camera);
    composer.addPass(renderPass);

    const fogShader = {
      uniforms: {
        tDiffuse: { value: null },
        fogDensity: { value: fogSettings.density },
        fogColor: { value: new THREE.Color(fogSettings.color) },
      },
      vertexShader: `
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform sampler2D tDiffuse;
        uniform float fogDensity;
        uniform vec3 fogColor;
        varying vec2 vUv;
        void main() {
          vec4 color = texture2D(tDiffuse, vUv);
          float fogAmount = clamp(fogDensity * 20.0, 0.0, 0.4); // Increased amplification
          color.rgb = mix(color.rgb, fogColor, fogAmount);
          gl_FragColor = color;
        }
      `,
    };

    const fogPass = new ShaderPass(fogShader);
    composer.addPass(fogPass);

    function updateFog() {
      if (!fogPass) {
        console.warn('Fog pass not initialized');
        return;
      }
      fogPass.uniforms.fogDensity.value = getSetting('volumetricFog.density');
      fogPass.uniforms.fogColor.value.set(getSetting('volumetricFog.color'));
      console.log('Fog updated:', { density: fogPass.uniforms.fogDensity.value });
    }

    console.log('Volumetric fog initialized:', {
      composer: !!composer,
      renderPass: !!renderPass,
      fogPass: !!fogPass,
    });

    return { success: true, composer, updateFog };
  } catch (error) {
    console.error('Volumetric fog initialization failed:', error);
    return { success: false, composer: null, updateFog: () => {} };
  }
}
