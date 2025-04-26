// src/settings.js
const settings = {
  playerDrone: {
    accel: 1.5,
    maxSpeed: 10,
    friction: 0.9,
  },
  aiDrone: {
    accel: 1.5,
    maxSpeed: 10,
    friction: 0.9,
    pathUpdateInterval: 3,
    count: 3,
  },
  terrain: {
    tileSize: 200,
    segments: 6,
    firstPerson: {
      renderDistance: 1,
    },
    thirdPerson: {
      renderDistance: 2,
    },
    noiseScale: 100,
    noiseAmplitude: 10,
  },
  track: {
    checkpointSpacing: 150,
    checkpointOffset: 50,
  },
  camera: {
    fov: 75,
    near: 0.1,
    far: 5000,
    initialPosition: { x: 0, y: 30, z: 50 },
  },
  fog: {
    enabled: true,
    sunFogOpacity: 0.8,
    firstPerson: {
      near: 50,
      far: 1500,
    },
    thirdPerson: {
      near: 100,
      far: 1500,
    },
  },
  volumetricFog: {
    enabled: false,
    density: 0.05,
    color: 0x87ceeb,
    height: 50,
  },
  renderer: {
    antialias: false,
  },
  skybox: {
    enabled: false, // Re-enabled for visuals
    textures: {
      posx: '/assets/skybox/sky_right.jpeg',
      negx: '/assets/skybox/sky_left.jpeg',
      posy: '/assets/skybox/sky_up.jpeg',
      negy: '/assets/skybox/sky_down.jpeg',
      posz: '/assets/skybox/sky_back.jpeg',
      negz: '/assets/skybox/sky_front.jpeg',
    },
    fallbackColor: 0x87ceeb,
    clouds: {
      enabled: true,
      count: 40,
      texture: '/assets/skybox/cloud.png',
      distanceMin: 1000,
      distanceMax: 3000,
      sizeMin: 600,
      sizeMax: 1500,
      opacity: 0.5,
    },
    sun: {
      position: { x: 100, y: 100, z: -100 },
      radius: 1000,
      spriteScale: 2000,
      spriteTexture: '/assets/skybox/sun.png',
      useSprite: true,
      color: 0xffffff,
      intensity: 1.5,
      latitude: 0,
      longitude: -3.19648,
      distance: 1000,
      disableFrustumCulling: true,
      debugFixedPosition: false,
      timeOfDay: 16,
    },
  },
};

function getSetting(path) {
  try {
    const keys = path.split('.');
    let value = settings;
    for (const key of keys) {
      value = value[key];
      if (value === undefined) throw new Error(`Setting ${path} not found`);
    }
    return value;
  } catch (error) {
    console.error('Error getting setting:', error);
    return null;
  }
}

function setSetting(path, value) {
  try {
    const keys = path.split('.');
    let obj = settings;
    for (let i = 0; i < keys.length - 1; i++) {
      obj = obj[keys[i]];
      if (!obj) throw new Error(`Setting path ${path} invalid`);
    }
    obj[keys[keys.length - 1]] = value;
    console.log(`Set setting ${path} to:`, value);
  } catch (error) {
    console.error('Error setting setting:', error);
  }
}

export { getSetting, setSetting };
