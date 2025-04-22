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
      renderDistance: 1, // 9 tiles for close-up view
    },
    thirdPerson: {
      renderDistance: 2, // 18 tiles for broader view
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
    far: 1000,
    initialPosition: { x: 0, y: 30, z: 50 },
  },
  fog: {
    enabled: true,
    firstPerson: {
      near: 50, // Closer fog for immersion
      far: 200, // Tighter range for performance
    },
    thirdPerson: {
      near: 100, // Wider fog for visibility
      far: 400, // Broader range for atmosphere
    },
  },
  renderer: {
    antialias: false,
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
