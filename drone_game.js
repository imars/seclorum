let scene, camera, renderer, playerDrone, drones, checkpoints, obstacles, clock, timer, speedDisplay, standingsDisplay;

const checkpointCount = 5;
const obstacleCount = 10;
const droneCount = 3;

init();
animate();

function init() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('myCanvas') });
  renderer.setSize(window.innerWidth, window.innerHeight);

  const terrainSize = 1000;
  const terrainGeometry = new THREE.PlaneGeometry(terrainSize, terrainSize, 100, 100);
  const terrainVertices = terrainGeometry.attributes.position.array;
  for (let i = 0; i < terrainVertices.length; i += 3) {
    terrainVertices[i + 1] = Math.sin(terrainVertices[i] / 10) * 10 + Math.random() * 20 - 10;
  }
  const terrainMaterial = new THREE.MeshBasicMaterial({ color: 0x00ff00 });
  const terrain = new THREE.Mesh(terrainGeometry, terrainMaterial);
  scene.add(terrain);


  drones = [];
  for (let i = 0; i < droneCount; i++) {
    const droneGeometry = new THREE.BoxGeometry(5, 2, 5);
    const droneMaterial = new THREE.MeshBasicMaterial({ color: i === 0 ? 0xff0000 : 0x0000ff });
    const drone = new THREE.Mesh(droneGeometry, droneMaterial);
    drone.position.set(Math.random() * 200 - 100, 20, Math.random() * 200 -100);
    scene.add(drone);
    drones.push(drone);
  }
  playerDrone = drones[0];
  camera.position.set(playerDrone.position.x, playerDrone.position.y + 20, playerDrone.position.z + 30