// src/settings.js
const settings = {
  // Drone settings
  playerDrone: {
    accel: 1.5, // Tripled from 0.5
    maxSpeed: 10,
    friction: 0.9,
  },
  aiDrone: {
    accel: 1.5, // Tripled from 0.5 for NPC performance
    maxSpeed: 10,
    friction: 0.9,
    pathUpdateInterval: 1, // Seconds between A* path updates (new)
    count: 3, // Number of AI drones
  },
  // Terrain settings
  terrain: {
    tileSize: 200,
    segments: 8,
    renderDistance: 2,
    noiseScale: 100, // For noise2D(x / noiseScale, z / noiseScale)
    noiseAmplitude: 10, // For noise2D * noiseAmplitude
  },
  // Track settings
  track: {
    checkpointSpacing: 150, // Distance between checkpoints
    checkpointOffset: 50, // Z-offset for first checkpoint
  },
  // Camera settings
  camera: {
    fov: 75,
    near: 0.1,
    far: 1000,
    initialPosition: { x: 0, y: 30, z: 50 },
  },
};

// Get a setting value
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

// Set a setting value (for dynamic updates)
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
